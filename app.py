from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
import json
import os

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.secret_key = 'clave-secreta-para-flask'

# Cargar datos de los equipos y selecciones desde el JSON
with open('soccerWiki.json', 'r',
          encoding='utf-8') as f:
    data = json.load(f)
    club_data = data.get('ClubData', [])
    international_data = data.get('InternationalData', [])

# Añadir el prefijo "Selección:" a los nombres de las selecciones y convertir el ID a string
for nation in international_data:
    nation['Name'] = f"Selección: {nation['Name']}"
    nation['ID'] = str(nation['ID'])  # Convertir ID a string

for club in club_data:
    club['ID'] = str(club['ID'])  # Convertir ID a string

# Unificar listas de clubes y selecciones
all_teams = club_data + international_data

DATA_FILE = 'selected_teams.json'

# Inicializar archivo de equipos seleccionados si no existe
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump([], f)


def cargar_equipos_seleccionados():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)


def guardar_equipo_seleccionado(equipo_id):
    equipos_seleccionados = cargar_equipos_seleccionados()
    equipos_seleccionados.append(equipo_id)
    with open(DATA_FILE, 'w') as f:
        json.dump(equipos_seleccionados, f)


@app.route('/')
def index():
    return render_template('index.html', club_data=all_teams)  # Mostrar solo los primeros 10 elementos


@app.route('/seleccionar-equipo', methods=['POST'])
def seleccionar_equipo():
    equipo_id = request.form.get('equipo_id')
    equipos_seleccionados = cargar_equipos_seleccionados()

    if equipo_id in equipos_seleccionados:
        flash('Este equipo ya ha sido seleccionado. Por favor, elige otro.', 'error')
    else:
        guardar_equipo_seleccionado(equipo_id)
        flash('¡El equipo ha sido registrado exitosamente!', 'success')

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

