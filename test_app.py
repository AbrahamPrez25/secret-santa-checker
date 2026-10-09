import os
import json
import pytest
from werkzeug.security import generate_password_hash

# Set test environment
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["USERS_FILE"] = "test_users.json"

import app as myapp

@pytest.fixture
def test_env(tmp_path, monkeypatch):
    users_file = str(tmp_path / "users.json")
    draw_file = str(tmp_path / "draw.json")
    teams_file = str(tmp_path / "selected_teams.json")

    monkeypatch.setattr(myapp, "USERS_FILE", users_file)
    monkeypatch.setattr(myapp, "DRAW_FILE", draw_file)
    monkeypatch.setattr(myapp, "DATA_FILE", teams_file)

    users_data = [
        {"username": "admin", "password_hash": generate_password_hash("admin123")},
        {"username": "juan", "password_hash": generate_password_hash("juan123")},
        {"username": "pedro", "password_hash": generate_password_hash("pedro123")},
    ]
    with open(users_file, "w", encoding="utf-8") as f:
        json.dump(users_data, f)

    with open(draw_file, "w", encoding="utf-8") as f:
        json.dump({"done": False, "assignments": {}, "forbidden_pairs": []}, f)

    with open(teams_file, "w", encoding="utf-8") as f:
        json.dump([], f)

    myapp.app.config["TESTING"] = True
    client = myapp.app.test_client()

    yield {
        "client": client,
        "users_file": users_file,
        "draw_file": draw_file,
        "teams_file": teams_file,
    }


def test_draw_algorithm_two_users():
    users = ["A", "B"]
    res = myapp.compute_draw(users, [])
    assert res is not None
    assert res["A"] == "B"
    assert res["B"] == "A"


def test_draw_algorithm_three_users_no_two_cycles():
    users = ["A", "B", "C"]
    for _ in range(20):
        res = myapp.compute_draw(users, [])
        assert res is not None
        for giver, rec in res.items():
            assert giver != rec
            assert res[rec] != giver  # no 2-cycles for N > 2


def test_draw_algorithm_forbidden_pairs():
    users = ["A", "B", "C", "D"]
    forbidden = [("A", "B"), ("C", "D")]
    for _ in range(10):
        res = myapp.compute_draw(users, forbidden)
        assert res is not None
        assert res["A"] != "B"
        assert res["C"] != "D"


def test_parse_forbidden_pairs():
    raw = """
    A::B
    C -> D
    E:F
    G,H
    """
    parsed = myapp._parse_forbidden_pairs(raw)
    assert parsed == [("A", "B"), ("C", "D"), ("E", "F"), ("G", "H")]


def test_login_and_admin_protection(test_env):
    client = test_env["client"]

    # Non-authenticated redirect
    r = client.get("/admin", follow_redirects=True)
    assert b"Iniciar" in r.data

    # Login as regular user 'juan'
    r = client.post("/login", data={"username": "juan", "password": "juan123"}, follow_redirects=True)
    assert r.status_code == 200

    # Juan tries to access admin -> forbidden redirect
    r = client.get("/admin", follow_redirects=True)
    assert b"Acceso restringido" in r.data

    # Logout
    r = client.post("/logout", follow_redirects=True)
    assert b"Iniciar" in r.data

    # Login as admin
    r = client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
    assert r.status_code == 200
    r = client.get("/admin")
    assert b"panel de administraci" in r.data.lower()


def test_admin_draw_and_flow(test_env):
    client = test_env["client"]

    # Login as admin
    client.post("/login", data={"username": "admin", "password": "admin123"})

    # Team selection should fail before draw
    r = client.post("/seleccionar-equipo", data={"equipo_id": "1000"}, follow_redirects=True)
    assert b"sorteo" in r.data.lower()

    # Perform draw with restrictions
    r = client.post("/admin/draw", data={"forbidden_text": "admin::juan\njuan -> pedro"}, follow_redirects=True)
    assert b"Sorteo realizado" in r.data

    # Verify draw status in file
    with open(test_env["draw_file"], "r", encoding="utf-8") as f:
        d = json.load(f)
    assert d["done"] is True
    assert "admin::juan" in d["forbidden_pairs"]
    assert "juan::pedro" in d["forbidden_pairs"]

    # Perform another draw reset
    r = client.post("/admin/reset-draw", follow_redirects=True)
    assert b"Sorteo deshecho" in r.data

    # Restrictions must be preserved in historical list
    with open(test_env["draw_file"], "r", encoding="utf-8") as f:
        d_reset = json.load(f)
    assert d_reset["done"] is False
    assert "admin::juan" in d_reset["forbidden_pairs"]

    # Run draw again to test combining historical with new restrictions without ValueError crash
    r = client.post("/admin/draw", data={"forbidden_text": "pedro:admin"}, follow_redirects=True)
    assert r.status_code == 200
    assert b"Sorteo realizado" in r.data


def test_team_selection_and_conflict(test_env):
    client = test_env["client"]

    # Perform draw as admin
    client.post("/login", data={"username": "admin", "password": "admin123"})
    client.post("/admin/draw", data={"forbidden_text": ""})
    client.post("/logout")

    # Pick a team with apostrophe (e.g. St. Patrick's Athletic, ID 1215 or similar)
    # Let's find a valid team with quote
    quote_team = next(t for t in myapp.all_teams if "'" in t["Name"])
    quote_team_id = quote_team["ID"]

    # Juan logs in and selects team with quote
    client.post("/login", data={"username": "juan", "password": "juan123"})
    r = client.post("/seleccionar-equipo", data={"equipo_id": quote_team_id}, follow_redirects=True)
    assert b"exitosamente" in r.data

    # Juan sees his selected team in index and espera
    import html
    r = client.get("/espera")
    page_text = html.unescape(r.data.decode("utf-8"))
    assert quote_team["Name"] in page_text

    client.post("/logout")

    # Pedro logs in and tries to select the same team
    client.post("/login", data={"username": "pedro", "password": "pedro123"})
    r = client.post("/seleccionar-equipo", data={"equipo_id": quote_team_id}, follow_redirects=True)
    assert b"ya ha sido seleccionado" in r.data

    # Pedro selects a different team
    diff_team = next(t for t in myapp.all_teams if t["ID"] != quote_team_id)
    r = client.post("/seleccionar-equipo", data={"equipo_id": diff_team["ID"]}, follow_redirects=True)
    assert b"exitosamente" in r.data

    # Pedro now tries to switch his team to quote_team_id (already taken by Juan)
    # 1) When attempting via /seleccionar-equipo, it returns the confirmation prompt
    r = client.post("/seleccionar-equipo", data={"equipo_id": quote_team_id}, follow_redirects=True)
    assert b"Confirmar cambio" in r.data

    # 2) When submitting the confirmation, the backend rejects because it is taken
    r = client.post("/confirmar-cambio", data={"new_id": quote_team_id}, follow_redirects=True)
    assert b"ya ha sido seleccionado" in r.data


def test_invalid_team_id_rejected(test_env):
    client = test_env["client"]
    client.post("/login", data={"username": "admin", "password": "admin123"})
    client.post("/admin/draw", data={})

    r = client.post("/seleccionar-equipo", data={"equipo_id": "<script>alert(1)</script>"}, follow_redirects=True)
    assert b"no es v\xc3\xa1lido" in r.data


def test_user_display_name_and_admin_update(test_env):
    client = test_env["client"]

    # 1) Admin logs in and updates juan's visible name
    client.post("/login", data={"username": "admin", "password": "admin123"})
    r = client.post("/admin/update-user-name", data={"username": "juan", "name": "Juan Perez"}, follow_redirects=True)
    assert b"actualizado" in r.data
    assert b"Juan Perez" in r.data

    # Perform draw
    client.post("/admin/draw", data={})
    client.post("/logout")

    # 2) Check that assignments file has assignments
    with open(test_env["draw_file"], "r", encoding="utf-8") as f:
        d = json.load(f)

    # Find who is assigned to juan
    giver_to_juan = next(g for g, r in d["assignments"].items() if r == "juan")
    # Giver logs in and checks /espera
    password = "admin123" if giver_to_juan == "admin" else f"{giver_to_juan}123"
    client.post("/login", data={"username": giver_to_juan, "password": password})
    r = client.get("/espera")
    assert b"Juan Perez" in r.data  # Should show the configured display name!
    assert b"@juan" in r.data       # Subtle username tag
    client.post("/logout")

    # 3) Check fallback: who is assigned to pedro (who has NO display name set)
    giver_to_pedro = next(g for g, r in d["assignments"].items() if r == "pedro")
    pwd_pedro_giver = "admin123" if giver_to_pedro == "admin" else f"{giver_to_pedro}123"
    client.post("/login", data={"username": giver_to_pedro, "password": pwd_pedro_giver})
    r = client.get("/espera")
    assert b"pedro" in r.data  # Fallback to username

