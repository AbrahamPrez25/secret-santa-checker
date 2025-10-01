# LIGA COGNATIS – Sorteo y selección de equipos

Aplicación Flask para organizar un **amigo invisible futbolero** 🎁⚽.  
Incluye autenticación, un **sorteo inicial gestionado por el administrador** y luego la **selección de equipos únicos**.

## 🧱 Estructura (resumen)

```

.
├── app.py
├── requirements.txt
├── soccerWiki.json             # datos fuente (ClubData + InternationalData)
├── selected_teams.json         # selecciones de equipos
├── users.json                  # hashes de contraseñas (no subir a repos públicos)
├── draw.json                   # estado del sorteo (asignaciones y restricciones)
├── manage_users.py             # CLI para gestionar users.json
├── templates/
│   ├── login.html              # login de usuario
│   ├── waiting.html            # pantalla de espera/asignación tras el sorteo
│   ├── admin.html              # panel del administrador
│   ├── index.html              # listado + búsqueda + selección de equipo
│   └── change_password.html    # cambio de contraseña
└── static/
├── favicon.ico
└── images/club_logos/{ID}.png

````

## ✨ Funcionalidad

### 1. Login y roles
- Autenticación con usuario/contraseña (`users.json`).
- El **primer usuario creado** es el **administrador**.

### 2. Sorteo
- Antes de realizarse el sorteo:
  - **Usuarios normales** → ven `waiting.html` con el mensaje *“Esperando que el administrador realice el sorteo”*.
  - **Administrador** → accede a `admin.html`, donde ve la lista de usuarios y un formulario para configurar restricciones.
- El administrador puede añadir **parejas prohibidas** (ej. resultados de sorteos anteriores) para evitar repeticiones.
- El algoritmo asigna a cada usuario un destinatario:
  - Nadie se asigna a sí mismo.
  - Se evita que haya parejas simétricas (A→B y B→A).
  - Se respetan las restricciones introducidas.
- Tras el sorteo:
  - Cada usuario ve en `waiting.html` el destinatario que le ha tocado.
  - Un botón permite pasar a `index.html` para elegir equipo.

### 3. Selección de equipos
- Lista de equipos (clubs + selecciones) con búsqueda local y logos.
- Reglas:
  1. Un equipo no puede ser elegido por más de un usuario.
  2. Cada usuario solo puede tener un equipo (puede cambiarlo con confirmación).
- Persistencia en `selected_teams.json`.

### 4. Cambio de contraseña
- Cualquier usuario puede actualizar su contraseña desde el menú de perfil (`change_password.html`).

---

## 🚀 Puesta en marcha (local)

1. Clona el repositorio y entra en la carpeta.
2. Crea un entorno virtual e instala dependencias:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
    ````

3. Crea usuarios con el CLI:

   ```bash
   python manage_users.py add admin   # primer usuario = administrador
   python manage_users.py add juan
   ```
4. Ejecuta el servidor:

   ```bash
   gunicorn app:app --bind 0.0.0.0:8000 --workers 2
   ```

Accede a [http://localhost:8000](http://localhost:8000).

---

## 🔐 Gestión de usuarios (CLI)

El script `manage_users.py` permite:

* Crear usuarios (`add`)
* Cambiar contraseñas (`set-password`)
* Eliminar usuarios (`delete`)
* Listar usuarios (`list`)
* Verificar contraseñas (`check`)

Ejemplo:

```bash
python manage_users.py add ana
python manage_users.py list
```

---

## 🌐 Rutas principales

* `GET  /login` – Formulario de login.
* `POST /login` – Valida credenciales.
* `POST /logout` – Cierra sesión.
* `GET  /admin` – Panel del administrador (solo primer usuario).
* `POST /admin/draw` – Ejecuta el sorteo con restricciones opcionales.
* `GET  /espera` – Página de espera/asignación (según estado del sorteo).
* `GET  /` – Lista de equipos (solo accesible tras sorteo).
* `POST /seleccionar-equipo` – Selección de equipo.
* `POST /confirmar-cambio` – Confirma cambio de equipo.
* `GET/POST /change-password` – Cambio de contraseña.

---

## 🗂️ Datos

* `users.json` – credenciales (hash).
* `draw.json` – estado del sorteo y restricciones.
* `selected_teams.json` – equipos elegidos por usuario.
* `soccerWiki.json` – lista de equipos y selecciones.

---

## 🛡️ Seguridad

* Cambia `app.secret_key` en producción (usa variable de entorno).
* Guarda `users.json`, `draw.json` y `selected_teams.json` en almacenamiento persistente.
* Contraseñas hasheadas (`scrypt` por defecto, también se admite `pbkdf2`).

---

## 🧪 Flujo típico

1. Admin inicia sesión → entra a `/admin`.
2. Admin revisa usuarios, introduce restricciones y pulsa **Realizar sorteo**.
3. Todos los usuarios → ven en `/espera` a quién deben regalar.
4. Cada usuario entra a **Elegir equipo** y selecciona uno único.

---

## 🧰 Despliegue

Recomendado usar:

* `gunicorn` + `nginx` como proxy inverso.
* HTTPS (Let’s Encrypt).
* Variables de entorno para claves y configuraciones.
* Volúmenes persistentes para JSON de usuarios, sorteos y equipos.