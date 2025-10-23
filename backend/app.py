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

@app.route('/cargar-consumo', methods=['POST'])
def cargar_consumo():
    """ Endpoint para recibir y procesar el XML de consumo. """
    if 'archivo' not in request.files:
        return jsonify({"status": "error", "message": "No se encontró el archivo"}), 400
    
    archivo = request.files['archivo']
    if archivo.filename == '':
        return jsonify({"status": "error", "message": "No se seleccionó ningún archivo"}), 400

    if archivo:
        xml_string = archivo.read().decode('utf-8')
        resultado = datalake.cargar_consumo_desde_xml_string(xml_string)
        if resultado["status"] == "error":
            return jsonify(resultado), 500
        return jsonify(resultado), 200

# Endpoint para crear un nuevo cliente (ejemplo de endpoint de creación)
@app.route('/crear-cliente', methods=['POST'])
def crear_cliente():
    from models import Cliente
    data = request.json
    
    if not all(k in data for k in ['nit', 'nombre', 'usuario', 'clave', 'direccion', 'correo']):
        return jsonify({"status": "error", "message": "Faltan datos para crear el cliente."}), 400

    if not validar_nit(data['nit']):
        return jsonify({"status": "error", "message": "El NIT proporcionado es inválido."}), 400
        
    if any(c.nit == data['nit'] for c in datalake.clientes):
        return jsonify({"status": "error", "message": "Ya existe un cliente con ese NIT."}), 400

    nuevo_cliente = Cliente(
        nit=data['nit'],
        nombre=data['nombre'],
        usuario=data['usuario'],
        clave=data['clave'],
        direccion=data['direccion'],
        correo=data['correo']
    )
    datalake.clientes.append(nuevo_cliente)
    
    return jsonify({"status": "success", "message": "Cliente creado exitosamente."}), 201


# NOTA: De manera similar, se crearían los endpoints /crearRecurso, /crearCategoria, etc.
# Por brevedad, solo se implementa /crear-cliente como ejemplo.


if __name__ == '__main__':
    app.run(debug=True, port=5000)