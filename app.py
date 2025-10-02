from flask import Flask, request, render_template, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
import json, os
from markupsafe import Markup  # al inicio del archivo
from datetime import datetime, timezone

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.secret_key = 'clave-secreta-para-flask'  # cámbiala en producción

def now_iso_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# -------- Datos de equipos --------
with open('soccerWiki.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    club_data = data.get('ClubData', [])
    international_data = data.get('InternationalData', [])

for nation in international_data:
    nation['Name'] = f"Selección: {nation['Name']}"
    nation['ID'] = str(nation['ID'])
for club in club_data:
    club['ID'] = str(club['ID'])

all_teams = club_data + international_data

# -------- Usuarios (hash en JSON) --------
USERS_FILE = 'users.json'
if not os.path.exists(USERS_FILE):
    # Arranque mínimo (vacío). Rellena con tus usuarios y hashes.
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

def cargar_usuarios():
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return {u['username']: u['password_hash'] for u in json.load(f)}

# --- Users helpers (lista completa) ---
def cargar_usuarios_lista():
    """Devuelve la lista cruda [{'username':..., 'password_hash':...}, ...]."""
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def guardar_usuarios_lista(users_list):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users_list, f, ensure_ascii=False, indent=2)

def buscar_usuario_en_lista(users_list, username):
    for u in users_list:
        if u.get('username') == username:
            return u
    return None

# -------- Persistencia de selecciones --------
DATA_FILE = 'selected_teams.json'
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f, ensure_ascii=False)

# --- Helpers de selección ---
def id_to_name(equipo_id: str) -> str:
    for t in all_teams:
        if t['ID'] == str(equipo_id):
            return t['Name']
    return equipo_id  # fallback

def cargar_items():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def guardar_items(items):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def obtener_seleccion_de_usuario(username: str):
    for item in cargar_items():
        if item.get('user') == username:
            return item
    return None

def obtener_seleccion_por_equipo(equipo_id: str):
    for item in cargar_items():
        if item.get('equipo_id') == str(equipo_id):
            return item
    return None

def actualizar_seleccion(username: str, nuevo_equipo_id: str):
    items = cargar_items()
    found = False
    for it in items:
        if it.get('user') == username:
            it['equipo_id'] = str(nuevo_equipo_id)
            it['timestamp'] = now_iso_utc()
            found = True
            break
    if not found:
        items.append({
            "user": username,
            "equipo_id": str(nuevo_equipo_id),
            "timestamp": now_iso_utc()
        })
    guardar_items(items)

# -------- Estado del sorteo --------
DRAW_FILE = 'draw.json'

def _ensure_draw_file():
    if not os.path.exists(DRAW_FILE):
        with open(DRAW_FILE, 'w', encoding='utf-8') as f:
            json.dump({"done": False, "assignments": {}, "forbidden_pairs": []}, f, ensure_ascii=False, indent=2)
_ensure_draw_file()

def load_draw():
    _ensure_draw_file()
    with open(DRAW_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_draw(state: dict):
    import tempfile
    dir_ = os.path.dirname(os.path.abspath(DRAW_FILE)) or "."
    with tempfile.NamedTemporaryFile("w", delete=False, dir=dir_, encoding="utf-8") as tmp:
        json.dump(state, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name
    os.replace(tmp_path, DRAW_FILE)

def get_admin_username():
    users = cargar_usuarios_lista()
    return users[0]['username'] if users else None

def is_admin_user(username: str) -> bool:
    return username == get_admin_username()

@app.context_processor
def inject_roles():
    def is_admin():
        u = session.get('user')
        return is_admin_user(u) if u else False
    return dict(is_admin=is_admin)

def get_assigned_to(username: str):
    d = load_draw()
    return d.get('assignments', {}).get(username)

import random

def _parse_forbidden_pairs(text: str) -> list[tuple[str, str]]:
    """
    Parsea líneas tipo:
      A:B
      A -> B
      A,B
    Devuelve lista de tuplas (A, B) significando 'A no puede regalar a B'.
    """
    pairs = []
    if not text:
        return pairs
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        for sep in ["->", ":", ","]:
            if sep in line:
                a, b = [s.strip() for s in line.split(sep, 1)]
                if a and b:
                    pairs.append((a, b))
                break
        else:
            # si no hay separador, ignora la línea
            continue
    return pairs

def _build_forbidden_lookup(forbidden_pairs: list[tuple[str, str]]) -> dict[str, set[str]]:
    d: dict[str, set[str]] = {}
    for a, b in forbidden_pairs:
        d.setdefault(a, set()).add(b)
    return d

def _backtracking_assignment(users: list[str], forbidden: dict[str, set[str]]) -> dict[str, str] | None:
    """
    Encuentra asignación tal que:
      - nadie se asigna a sí mismo
      - respeta forbidden[a] (conjunto de receptores prohibidos para a)
      - evita parejas de 2 ciclos (A->B y B->A)
    Estrategia: backtracking ordenando por el que menos opciones tiene.
    """
    U = list(users)
    # mapa de opciones válidas
    options: dict[str, set[str]] = {}
    for u in U:
        opts = set(U) - {u} - forbidden.get(u, set())
        options[u] = opts

    # si alguien no tiene opciones, imposible
    if any(len(opts) == 0 for opts in options.values()):
        return None

    # ordena por menor dominio (heurística MRV)
    order = sorted(U, key=lambda x: len(options[x]))

    assigned: dict[str, str] = {}
    used_recipients: set[str] = set()

    def dfs(i: int) -> bool:
        if i == len(order):
            return True
        giver = order[i]
        # Probar en orden aleatorio para diversificar soluciones
        candidates = list(options[giver] - used_recipients)
        random.shuffle(candidates)
        for rec in candidates:
            # Evita 2-ciclos: si ya hemos asignado rec->giver, no permitir giver->rec
            if assigned.get(rec) == giver:
                continue
            assigned[giver] = rec
            used_recipients.add(rec)
            if dfs(i + 1):
                return True
            # backtrack
            used_recipients.remove(rec)
            del assigned[giver]
        return False

    ok = dfs(0)
    return assigned if ok else None

def compute_draw(users: list[str], forbidden_pairs: list[tuple[str, str]]) -> dict[str, str] | None:
    """
    Intenta varias veces con aleatoriedad para encontrar una asignación válida.
    """
    forbidden = _build_forbidden_lookup(forbidden_pairs)
    # pequeños N: unos cuantos intentos aleatorios por si el orden inicial bloquea
    for _ in range(200):
        random.shuffle(users)
        result = _backtracking_assignment(users, forbidden)
        if result:
            return result
    return None


# -------- Utilidad: requisito de login --------
def login_required(view_func):
    from functools import wraps
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)
    return wrapper


# -------- Rutas --------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = cargar_usuarios()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if username in users and check_password_hash(users[username], password):
            session['user'] = username
            d = load_draw()
            # Antes del sorteo: admin va a panel; resto a espera
            if not d.get('done'):
                if is_admin_user(username):
                    return redirect(url_for('admin_panel'))
                return redirect(url_for('espera'))
            # Después del sorteo: todos ven la pantalla con su asignación y botón a "Elegir equipo"
            return redirect(url_for('espera'))
        else:
            flash('Usuario o contraseña incorrectos.', 'error')
            return render_template('login.html')

    if 'user' in session:
        return redirect(url_for('espera'))
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    session.pop('user', None)
    flash('Sesión cerrada.', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    d = load_draw()
    if not d.get('done'):
        # Si el sorteo NO está hecho:
        # - el admin (primer usuario) va al panel
        # - el resto a la pantalla de espera
        username = session['user']
        if is_admin_user(username):
            return redirect(url_for('admin_panel'))
        return redirect(url_for('espera'))

    # Si el sorteo SÍ está hecho, se muestra la selección de equipo
    username = session['user']
    actual = obtener_seleccion_de_usuario(username)
    selected_team = id_to_name(actual['equipo_id']) if actual else None
    return render_template('index.html', club_data=all_teams, selected_team=selected_team)

@app.route('/espera')
@login_required
def espera():
    username = session['user']
    d = load_draw()
    assigned = d.get('assignments', {}).get(username)
    return render_template('waiting.html', draw_done=bool(d.get('done')), assigned_to=assigned)

@app.route('/admin')
@login_required
def admin_panel():
    username = session['user']
    if not is_admin_user(username):
        flash('Acceso restringido.', 'error')
        return redirect(url_for('espera'))
    users_list = [u['username'] for u in cargar_usuarios_lista()]
    d = load_draw()
    return render_template('admin.html',
                           users=users_list,
                           draw_done=bool(d.get('done')),
                           forbidden_pairs=d.get('forbidden_pairs', []))

@app.route('/admin/draw', methods=['POST'])
@login_required
def admin_draw():
    username = session['user']
    if not is_admin_user(username):
        flash('Acceso restringido.', 'error')
        return redirect(url_for('espera'))

    # Textarea con parejas prohibidas (incluye resultado anterior si el admin lo pega)
    forbidden_text = request.form.get('forbidden_text', '').strip()
    extra_pairs = _parse_forbidden_pairs(forbidden_text)

    # Prepara lista de usuarios
    users_list = [u['username'] for u in cargar_usuarios_lista()]
    if len(users_list) < 2:
        flash('Se necesitan al menos 2 usuarios para el sorteo.', 'error')
        return redirect(url_for('admin_panel'))

    # Calcula
    assignment = compute_draw(users_list[:], extra_pairs)
    if not assignment:
        # mensaje útil para depurar
        flash('No fue posible generar un sorteo con las restricciones dadas. Revisa las parejas prohibidas o reduce restricciones.', 'error')
        return redirect(url_for('admin_panel'))

    # Guarda estado
    d = load_draw()
    d['done'] = True
    d['assignments'] = assignment
    # Persistimos también las parejas prohibidas que usó el admin como referencia
    prev_forbidden = d.get('forbidden_pairs', [])
    merged = prev_forbidden + extra_pairs
    # normaliza en texto plano para lectura futura
    d['forbidden_pairs'] = list({f"{a}::{b}" for a, b in merged})
    save_draw(d)

    flash('Sorteo realizado correctamente.', 'success')
    # Tras el sorteo, redirige a la pantalla de espera que ya muestra el destinatario
    return redirect(url_for('espera'))

@app.route('/admin/reset-draw', methods=['POST'])
@login_required
def admin_reset_draw():
    if not is_admin_user(session.get('user')):
        flash('Acceso restringido.', 'error')
        return redirect(url_for('espera'))
    # Estado inicial del sorteo
    save_draw({"done": False, "assignments": {}, "forbidden_pairs": []})
    flash('Sorteo deshecho. Todos vuelven al estado inicial.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/seleccionar-equipo', methods=['POST'])
@login_required
def seleccionar_equipo():
    username = session['user']
    equipo_id = request.form.get('equipo_id')
    if not equipo_id:
        flash('No se recibió el equipo.', 'error')
        return redirect(url_for('index'))

    # 1) ¿El equipo ya está tomado por otro?
    tomado = obtener_seleccion_por_equipo(equipo_id)  # usa tu helper o recorre selected_teams.json
    if tomado and tomado.get('user') != username:
        flash('Este equipo ya ha sido seleccionado. Por favor, elige otro.', 'error')
        return redirect(url_for('index'))

    # 2) ¿El usuario ya tenía uno?
    actual = obtener_seleccion_de_usuario(username)   # usa tu helper o recorre selected_teams.json
    if actual:
        actual_id = str(actual.get('equipo_id'))
        if actual_id == str(equipo_id):
            flash(f'Ya elegiste el equipo {id_to_name(actual_id)}.', 'success')
            return redirect(url_for('index'))

        # Flash con confirmación (HTML seguro)
        old_name = id_to_name(actual_id)
        new_name = id_to_name(equipo_id)
        msg = Markup(
            f'Ya elegiste el equipo <strong>{old_name}</strong>. '
            f'¿Quieres cambiarlo por <strong>{new_name}</strong>? '
            f'<form method="POST" action="{url_for("confirmar_cambio")}" style="margin-top:8px;">'
            f'  <input type="hidden" name="new_id" value="{equipo_id}">'
            f'  <button type="submit" style="padding:8px 12px;border:0;border-radius:4px;background:#007bff;color:#fff;cursor:pointer;">Confirmar cambio</button>'
            f'</form>'
        )
        flash(msg, 'confirm')
        return redirect(url_for('index'))

    # 3) Primera elección del usuario (equipo libre)
    actualizar_seleccion(username, equipo_id)  # tu helper que guarda {user, equipo_id, timestamp}
    flash('¡El equipo ha sido registrado exitosamente!', 'success')
    return redirect(url_for('index'))

@app.route('/confirmar-cambio', methods=['POST'])
@login_required
def confirmar_cambio():
    username = session['user']
    new_id = request.form.get('new_id')
    if not new_id:
        flash('Solicitud inválida.', 'error')
        return redirect(url_for('index'))

    # Revalidar que el nuevo equipo siga libre
    tomado = obtener_seleccion_por_equipo(new_id)
    if tomado and tomado.get('user') != username:
        flash('Lo sentimos, alguien acaba de elegir ese equipo. Prueba con otro.', 'error')
        return redirect(url_for('index'))

    actualizar_seleccion(username, new_id)
    flash(f'Has cambiado tu equipo a {id_to_name(new_id)}.', 'success')
    return redirect(url_for('index'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    username = session['user']

    if request.method == 'GET':
        return render_template('change_password.html')

    # POST
    current_password = request.form.get('current_password', '')
    new_password     = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    # Validaciones mínimas
    if not current_password or not new_password or not confirm_password:
        flash('Faltan campos obligatorios.', 'error')
        return redirect(url_for('change_password'))

    if len(new_password) < 8:
        flash('La nueva contraseña debe tener al menos 8 caracteres.', 'error')
        return redirect(url_for('change_password'))

    if new_password != confirm_password:
        flash('La confirmación no coincide con la nueva contraseña.', 'error')
        return redirect(url_for('change_password'))

    if current_password == new_password:
        flash('La nueva contraseña no puede ser igual a la actual.', 'error')
        return redirect(url_for('change_password'))

    # Cargar usuarios y localizar al actual
    users_list = cargar_usuarios_lista()
    user_entry = buscar_usuario_en_lista(users_list, username)
    if not user_entry:
        flash('Usuario no encontrado en el sistema.', 'error')
        return redirect(url_for('change_password'))

    # Verificar contraseña actual
    if not check_password_hash(user_entry.get('password_hash', ''), current_password):
        flash('La contraseña actual no es correcta.', 'error')
        return redirect(url_for('change_password'))

    # Generar y guardar nuevo hash
    new_hash = generate_password_hash(new_password)
    user_entry['password_hash'] = new_hash

    user_entry['last_password_change'] = now_iso_utc()

    guardar_usuarios_lista(users_list)

    flash('Contraseña actualizada correctamente.', 'success')
    return redirect(url_for('index'))



if __name__ == '__main__':
    app.run(debug=False)
