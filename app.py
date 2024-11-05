from flask import Flask, request, render_template, redirect, url_for, flash
import json
import os

app = Flask(__name__)
app.secret_key = 'ligacognatis'  # Cambia esto a algo más seguro

DATA_FILE = 'equipos.json'

# Inicializar archivo si no existe
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump([], f)

def cargar_equipos():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def guardar_equipo(equipo):
    equipos = cargar_equipos()
    equipos.append(equipo)
    with open(DATA_FILE, 'w') as f:
        json.dump(equipos, f)

def equipo_existe(equipo):
    equipos = cargar_equipos()
    return equipo in equipos

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        equipo = request.form.get('equipo').strip()

        if equipo_existe(equipo):
            flash('Este equipo ya ha sido elegido. Por favor, elige otro.')
        else:
            guardar_equipo(equipo)
            flash(f'¡El equipo {equipo} ha sido registrado exitosamente!')
        return redirect(url_for('index'))

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
