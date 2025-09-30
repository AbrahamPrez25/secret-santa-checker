# LIGA COGNATIS – Selector de equipos (con login)

Aplicación Flask para que usuarios autenticados elijan **un único equipo** de una lista (clubs + selecciones).
Cada equipo **solo puede ser elegido por una persona**. Si un usuario ya eligió un equipo y selecciona otro, se le muestra un **flash** con la pregunta de confirmación y un botón para **cambiar** su elección.

## 🧱 Estructura (resumen)

```
.
├── app.py
├── requirements.txt
├── soccerWiki.json             # datos fuente (ClubData + InternationalData)
├── selected_teams.json         # se genera en runtime (user/equipo)
├── users.json                  # hashes de contraseñas (no subir a repos públicos)
├── manage_users.py             # CLI para gestionar users.json
├── templates/
│   ├── login.html              # login de usuario
│   └── index.html              # listado + búsqueda + selección de equipo
└── static/
    ├── favicon.ico
    └── images/club_logos/{ID}.png
```

## ✨ Funcionalidad

* **Login** con usuario/contraseña (hash scrypt o pbkdf2).
* Lista de equipos (clubs + selecciones) con búsqueda local y logos por `ID`.
* **Reglas de negocio**:

  1. Un equipo no puede tener más de un dueño.
  2. Cada usuario solo puede tener un equipo.

     * Si intenta elegir otro: *“Ya elegiste el equipo XX. ¿Quieres cambiarlo por YY?”* + botón **Confirmar cambio** (como **flash message** en `index.html`).
* Persistencia en archivos JSON:

  * `selected_teams.json` → `{ user, equipo_id, timestamp }`
  * `users.json` → `{ username, password_hash }`
* Mensajes **flash** para todos los casos (éxito, error, confirmación).

---

## 🚀 Puesta en marcha (local)

> Requisitos: **Python 3.10+** (recomendado), `pip`, acceso a Internet para instalar dependencias.

1. Clona el repositorio y entra en la carpeta.

2. Crea un entorno virtual e instala dependencias:

```bash
python -m venv .venv
# Activa el entorno:
#   Windows: .venv\Scripts\activate
#   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

3. Asegúrate de tener `soccerWiki.json` en la raíz del proyecto.

   * El app usa `ClubData[]` y (si existe) `InternationalData[]`.
   * Convierte internamente los `ID` a `str` y antepone `“Selección: ”` a los nombres internacionales.
   * Los logos se buscan en `static/images/club_logos/{ID}.png`.

4. Crea usuarios y contraseñas (hash) con el **CLI**:

```bash
python manage_users.py add ana                  # pide contraseña (hash scrypt por defecto)
python manage_users.py add luis --method pbkdf2:sha256:600000
python manage_users.py list                     # muestra usuarios y algoritmo de hash
```

> **Importante:** `users.json` contiene *hashes*, no contraseñas en claro. **No** lo subas a repos públicos; añádelo a `.gitignore`.

5. Ejecuta el servidor:

```bash
# Opción A: Python directo
python app.py

# Opción B: Flask
# (si usas Flask CLI) 
# export FLASK_APP=app.py  (Linux/macOS)
# set FLASK_APP=app.py     (Windows)
flask run
```

Accede a **[http://localhost:5000](http://localhost:5000)**. Verás primero la página de **login** (`/login`).
Tras iniciar sesión, pasarás a `index` con la lista de equipos.

---

## 🔐 Gestión de usuarios (CLI)

Archivo: `manage_users.py` (requiere `werkzeug`)

```bash
# Crear usuario (pide contraseña con eco oculto)
python manage_users.py add ana

# Crear con PBKDF2 (ejemplo 600k iteraciones)
python manage_users.py add luis --method pbkdf2:sha256:600000

# Cambiar contraseña
python manage_users.py set-password ana

# Verificar credenciales
python manage_users.py check ana

# Listar usuarios (muestra el algoritmo del hash usado)
python manage_users.py list

# Borrar usuario
python manage_users.py delete luis

# Usar otro path para users.json
python manage_users.py --file /ruta/persistente/users.json list
```

> El CLI guarda JSON de forma **atómica** (archivo temporal + `os.replace`) para evitar corrupción.

---

## 🌐 Rutas principales

* `GET  /login` – Formulario de login.
* `POST /login` – Valida credenciales (`users.json` + `check_password_hash`).
* `POST /logout` – Cierra sesión y vuelve a `/login`.
* `GET  /` – (protegida) Muestra `index.html` con la lista de equipos y búsqueda.
* `POST /seleccionar-equipo` – Lógica de selección:

  * Si el equipo ya lo eligió otro usuario → **flash error**.
  * Si el usuario ya tenía equipo distinto → **flash de confirmación** con botón “Confirmar cambio”.
  * Si el usuario ya tenía el mismo equipo → **flash success** informativo.
  * Si es primera elección válida → guarda en `selected_teams.json` y **flash success**.
* `POST /confirmar-cambio` – Aplica el cambio (revalida que el equipo siga libre).

---

## 🗂️ Datos y plantillas

* `soccerWiki.json`

  * Usa campos `ID` y `Name`.
  * `ImageURL` y `ShortName` **no** se usan en la vista actual.
  * Para logos locales: `static/images/club_logos/{ID}.png`.
* `templates/index.html`

  * Búsqueda *client-side* con eliminación de tildes, límite dinámico de elementos visibles y selección con botón **Enviar**.
  * Muestra **todas** las flash messages (éxito/error/confirmación).
* `templates/login.html`

  * Formulario simple de usuario y contraseña.

---

## 🛡️ Seguridad y persistencia

* Cambia `app.secret_key` en producción (usa una variable de entorno).
* `users.json` y `selected_teams.json` deben estar en **almacenamiento persistente**.

  * **Ojo** con plataformas de hosting de **disco efímero** (p. ej. Heroku sin add-ons): tras reiniciar, los JSON vuelven al estado de la imagen. Monta un volumen o usa una DB si necesitas durabilidad.
* Las contraseñas se guardan **hasheadas** (por defecto `scrypt`; también se admite `pbkdf2:sha256[:iter]`). `check_password_hash()` detecta el método automáticamente.

---

## 🧪 Comprobación rápida

1. Arranca la app.
2. Crea dos usuarios (`ana`, `luis`).
3. Entra como `ana` y elige un equipo **A** → éxito.
4. Entra como `luis` e intenta elegir **A** → **flash** de error “ya seleccionado”.
5. Vuelve como `ana`, elige **B** → **flash** con “Ya elegiste A… ¿cambiar por B?” + botón.
6. Pulsa **Confirmar cambio** → éxito y `selected_teams.json` actualizado.

---

## 🧰 Despliegue (producción)

Con **gunicorn**:

```bash
pip install gunicorn
gunicorn app:app --bind 0.0.0.0:8000 --workers 2
```

Asegura:

* `SECRET_KEY` segura (p. ej. variable de entorno).
* Volúmenes persistentes para `users.json` y `selected_teams.json`.
* (Opcional) Proxy/Nginx delante de gunicorn y HTTPS.