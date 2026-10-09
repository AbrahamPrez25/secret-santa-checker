#!/usr/bin/env bash
set -e

# Directorio raíz del proyecto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "🔍 [1/4] Sincronizando repositorio con origin..."
git fetch origin --quiet

# Rama o tag objetivo (por defecto main)
OBJETIVO="${1:-main}"

COMMIT_ACTUAL=$(git rev-parse HEAD 2>/dev/null || echo "")
COMMIT_OBJETIVO=$(git rev-parse "origin/$OBJETIVO" 2>/dev/null || git rev-parse "$OBJETIVO^{commit}" 2>/dev/null || echo "")

if [ -n "$COMMIT_OBJETIVO" ] && [ "$COMMIT_ACTUAL" = "$COMMIT_OBJETIVO" ]; then
    echo "✨ secret-santa-checker ya se encuentra en la versión más reciente ($OBJETIVO)."
    echo "No hay cambios pendientes de desplegar."
    exit 0
fi

echo "🚀 [2/4] Nueva versión detectada. Actualizando a $OBJETIVO..."
if git rev-parse --verify "origin/$OBJETIVO" >/dev/null 2>&1; then
    git checkout "$OBJETIVO" --quiet
    git pull origin "$OBJETIVO" --quiet
else
    git checkout "$OBJETIVO" --quiet
fi

echo "📦 [3/4] Verificando dependencias de Python..."
if [ -f "$SCRIPT_DIR/.venv/bin/pip" ]; then
    "$SCRIPT_DIR/.venv/bin/pip" install -r requirements.txt --quiet
else
    echo "⚠️ .venv/bin/pip no encontrado. Asegúrate de tener el entorno virtual creado."
fi

echo "🔄 [4/4] Reiniciando servicio 'amigo-invisible' en systemd..."
sudo systemctl restart amigo-invisible

echo "✅ ¡Actualización completada! Estado actual del servicio:"
sudo systemctl status amigo-invisible --no-pager -n 5
