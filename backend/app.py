from flask import Flask, request, jsonify
from database import datalake # Importamos la instancia única

app = Flask(__name__)

@app.route('/reset', methods=['POST'])
def reset_sistema():
    """ Endpoint para borrar todos los datos. """
    datalake.reset_datos()
    return jsonify({"status": "success", "message": "Sistema inicializado. Todos los datos han sido borrados."})

@app.route('/cargar-configuracion', methods=['POST'])
def cargar_configuracion():
    """ Endpoint para recibir y procesar el XML de configuración. """
    if 'archivo' not in request.files:
        return jsonify({"status": "error", "message": "No se encontró el archivo"}), 400
    
    archivo = request.files['archivo']
    if archivo.filename == '':
        return jsonify({"status": "error", "message": "No se seleccionó ningún archivo"}), 400

    if archivo:
        xml_string = archivo.read().decode('utf-8')
        resultado = datalake.cargar_desde_xml_string(xml_string)
        if resultado["status"] == "error":
            return jsonify(resultado), 500
        return jsonify(resultado), 200

@app.route('/consultar-datos', methods=['GET'])
def consultar_datos():
    """ Endpoint para obtener un resumen de los datos actuales. """
    datos = datalake.get_datos_generales()
    return jsonify(datos)

if __name__ == '__main__':
    app.run(debug=True, port=5000)