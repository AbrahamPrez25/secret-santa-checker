#!/usr/bin/env python3
import argparse, json, os, sys, tempfile
from getpass import getpass
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

DEFAULT_USERS_FILE = os.environ.get("USERS_FILE", "users.json")

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def load_users(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(path, users):
    # Guardado atómico para evitar corrupción
    dir_ = os.path.dirname(os.path.abspath(path)) or "."
    with tempfile.NamedTemporaryFile("w", delete=False, dir=dir_, encoding="utf-8") as tmp:
        json.dump(users, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name
    os.replace(tmp_path, path)

def find_index(users, username):
    for i, u in enumerate(users):
        if u.get("username") == username:
            return i
    return -1

def prompt_password(confirm=True):
    while True:
        p1 = getpass("Contraseña: ")
        if not confirm:
            return p1
        p2 = getpass("Repite la contraseña: ")
        if p1 == p2:
            return p1
        print("No coinciden. Intenta de nuevo.", file=sys.stderr)

def add_user(args):
    users = load_users(args.file)
    if find_index(users, args.username) != -1:
        print(f"ERROR: el usuario '{args.username}' ya existe.", file=sys.stderr)
        sys.exit(1)
    pwd = args.password or prompt_password()
    method = args.method  # e.g. 'scrypt' (por defecto) o 'pbkdf2:sha256:600000'
    hash_ = generate_password_hash(pwd, method=method) if method else generate_password_hash(pwd)
    users.append({
        "username": args.username,
        "password_hash": hash_,
        "last_password_change": now_iso()
    })
    save_users(args.file, users)
    print(f"Usuario '{args.username}' creado.")

def set_password(args):
    users = load_users(args.file)
    idx = find_index(users, args.username)
    if idx == -1:
        if not args.create:
            print(f"ERROR: el usuario '{args.username}' no existe. Usa --create para crearlo.", file=sys.stderr)
            sys.exit(1)
        # crear
        pwd = args.password or prompt_password()
        method = args.method
        hash_ = generate_password_hash(pwd, method=method) if method else generate_password_hash(pwd)
        users.append({
            "username": args.username,
            "password_hash": hash_,
            "last_password_change": now_iso()
        })

        save_users(args.file, users)
        print(f"Usuario '{args.username}' creado con contraseña.")
        return
    # actualizar
    pwd = args.password or prompt_password()
    method = args.method
    hash_ = generate_password_hash(pwd, method=method) if method else generate_password_hash(pwd)
    users[idx]["password_hash"] = hash_
    users[idx]["last_password_change"] = now_iso()
    save_users(args.file, users)
    print(f"Contraseña de '{args.username}' actualizada.")

def delete_user(args):
    users = load_users(args.file)
    idx = find_index(users, args.username)
    if idx == -1:
        print(f"ERROR: el usuario '{args.username}' no existe.", file=sys.stderr)
        sys.exit(1)
    users.pop(idx)
    save_users(args.file, users)
    print(f"Usuario '{args.username}' eliminado.")

def list_users(args):
    users = load_users(args.file)
    if not users:
        print("(sin usuarios)")
        return
    for u in users:
        algo = u.get("password_hash", "").split(":", 1)[0] if u.get("password_hash") else "?"
        print(f"- {u.get('username')}  [{algo}]")
    if args.show_hashes:
        print("\nHashes:")
        for u in users:
            print(f"{u.get('username')}: {u.get('password_hash')}")

def check_user(args):
    users = load_users(args.file)
    idx = find_index(users, args.username)
    if idx == -1:
        print(f"ERROR: el usuario '{args.username}' no existe.", file=sys.stderr)
        sys.exit(1)
    pwd = args.password or prompt_password(confirm=False)
    ok = check_password_hash(users[idx]["password_hash"], pwd)
    print("OK" if ok else "NO OK")
    sys.exit(0 if ok else 2)

def ensure_file_exists(path):
    if not os.path.exists(path):
        save_users(path, [])
        print(f"Inicializado {path} con una lista vacía.")

def main():
    p = argparse.ArgumentParser(description="Gestión de users.json (hash de contraseñas).")
    p.add_argument("--file", default=DEFAULT_USERS_FILE, help=f"Ruta del users.json (por defecto: {DEFAULT_USERS_FILE})")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Crear usuario nuevo")
    p_add.add_argument("username")
    p_add.add_argument("--password", help="(No recomendado) contraseña vía argumento; si se omite, se pedirá")
    p_add.add_argument("--method", help="Método de hash (p.ej. 'scrypt' o 'pbkdf2:sha256:600000')")
    p_add.set_defaults(func=add_user)

    p_set = sub.add_parser("set-password", help="Establecer/actualizar contraseña")
    p_set.add_argument("username")
    p_set.add_argument("--password", help="(No recomendado) contraseña vía argumento; si se omite, se pedirá")
    p_set.add_argument("--method", help="Método de hash (p.ej. 'scrypt' o 'pbkdf2:sha256:600000')")
    p_set.add_argument("--create", action="store_true", help="Crear el usuario si no existe")
    p_set.set_defaults(func=set_password)

    p_del = sub.add_parser("delete", help="Borrar usuario")
    p_del.add_argument("username")
    p_del.set_defaults(func=delete_user)

    p_list = sub.add_parser("list", help="Listar usuarios")
    p_list.add_argument("--show-hashes", action="store_true", help="Mostrar hashes completos")
    p_list.set_defaults(func=list_users)

    p_check = sub.add_parser("check", help="Verificar contraseña de un usuario")
    p_check.add_argument("username")
    p_check.add_argument("--password", help="Si se omite, se pedirá sin eco")
    p_check.set_defaults(func=check_user)

    args = p.parse_args()
    ensure_file_exists(args.file)
    args.func(args)

if __name__ == "__main__":
    main()
