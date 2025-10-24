import os
from flask import Flask, request, jsonify, send_from_directory
from database import datalake # Se importa la instancia ya inicializada
from utils import validar_nit
from datetime import datetime

app = Flask(__name__)

# --- Endpoints de Carga de Archivos ---

@app.route('/reset', methods=['POST'])
def reset_sistema():
    """ Endpoint para borrar todos los datos. """
    datalake.reset_datos()
    # guardar_a_xml() ya no es necesario aquí, reset_datos lo maneja
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
        try:
            xml_string = archivo.read().decode('utf-8')
            resultado = datalake.cargar_desde_xml_string(xml_string)
            if resultado["status"] == "error":
                return jsonify(resultado), 500
            
            # Si la carga es exitosa, guarda en el XML persistente
            datalake.guardar_a_xml()
            return jsonify(resultado), 200
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error al leer el archivo: {e}"}), 500

@app.route('/cargar-consumo', methods=['POST'])
def cargar_consumo():
    """ Endpoint para recibir y procesar el XML de consumo. """
    if 'archivo' not in request.files:
        return jsonify({"status": "error", "message": "No se encontró el archivo"}), 400
    
    archivo = request.files['archivo']
    if archivo.filename == '':
        return jsonify({"status": "error", "message": "No se seleccionó ningún archivo"}), 400

    if archivo:
        try:
            xml_string = archivo.read().decode('utf-8')
            resultado = datalake.cargar_consumo_desde_xml_string(xml_string)
            if resultado["status"] == "error":
                return jsonify(resultado), 500
            
            # Si la carga es exitosa, guarda los nuevos consumos
            datalake.guardar_a_xml()
            return jsonify(resultado), 200
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error al leer el archivo: {e}"}), 500

# --- Endpoint de Consulta ---

@app.route('/consultar-datos', methods=['GET'])
def consultar_datos():
    """ Endpoint para obtener un resumen de los datos actuales. """
    datos = datalake.get_datos_generales()
    return jsonify(datos)

# --- Endpoints de Creación de Datos (Formularios) ---

@app.route('/crear-cliente', methods=['POST'])
def crear_cliente():
    """ Endpoint para crear un nuevo cliente. """
    from models import Cliente
    data = request.json
    
    # Validación mejorada: verifica que el valor no sea None ni string vacío
    if not all(data.get(k) for k in ['nit', 'nombre', 'usuario', 'clave', 'direccion', 'correo']):
        return jsonify({"status": "error", "message": "Faltan datos para crear el cliente."}), 400

    nit = data['nit']
    if not validar_nit(nit):
        return jsonify({"status": "error", "message": "El NIT proporcionado es inválido."}), 400
        
    if any(c.nit == nit for c in datalake.clientes):
        return jsonify({"status": "error", "message": "Ya existe un cliente con ese NIT."}), 400

    nuevo_cliente = Cliente(
        nit=nit,
        nombre=data['nombre'],
        usuario=data['usuario'],
        clave=data['clave'],
        direccion=data['direccion'],
        correo=data['correo'],
        instancias=[]
    )
    datalake.clientes.append(nuevo_cliente)
    datalake.guardar_a_xml() # Persistir cambio
    
    return jsonify({"status": "success", "message": f"Cliente '{nuevo_cliente.nombre}' creado exitosamente."}), 201

@app.route('/crear-recurso', methods=['POST'])
def crear_recurso():
    """ Endpoint para crear un nuevo recurso. """
    from models import Recurso
    data = request.json
    
    # Validación mejorada
    required_keys = ['id', 'nombre', 'abreviatura', 'metrica', 'tipo', 'valor_x_hora']
    if not all(str(data.get(k)) for k in required_keys): # str() maneja 0 y 0.0
        return jsonify({"status": "error", "message": "Faltan datos para crear el recurso."}), 400

    try:
        nuevo_id = int(data['id'])
        nuevo_valor = float(data['valor_x_hora'])

        nuevo_recurso = Recurso(
            id=nuevo_id,
            nombre=data['nombre'],
            abreviatura=data['abreviatura'],
            metrica=data['metrica'],
            tipo=data['tipo'].upper(),
            valor_x_hora=nuevo_valor
        )
        
        if any(r.id == nuevo_recurso.id for r in datalake.recursos):
            return jsonify({"status": "error", "message": f"Ya existe un recurso con ID {nuevo_recurso.id}."}), 400

        datalake.recursos.append(nuevo_recurso)
        datalake.guardar_a_xml() # Persistir cambio
        return jsonify({"status": "success", "message": f"Recurso '{nuevo_recurso.nombre}' creado exitosamente."}), 201
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "El ID y el Valor por Hora deben ser números válidos."}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error inesperado: {e}"}), 500

@app.route('/crear-categoria', methods=['POST'])
def crear_categoria():
    """ Endpoint para crear una nueva categoría. """
    from models import Categoria
    data = request.json

    if not all(data.get(k) for k in ['id', 'nombre', 'descripcion', 'carga_trabajo']):
        return jsonify({"status": "error", "message": "Faltan datos para crear la categoría."}), 400

    try:
        nuevo_id = int(data['id'])
        nueva_categoria = Categoria(
            id=nuevo_id,
            nombre=data['nombre'],
            descripcion=data['descripcion'],
            carga_trabajo=data['carga_trabajo'],
            configuraciones=[]
        )
        
        if any(c.id == nueva_categoria.id for c in datalake.categorias):
            return jsonify({"status": "error", "message": f"Ya existe una categoría con ID {nueva_categoria.id}."}), 400

        datalake.categorias.append(nueva_categoria)
        datalake.guardar_a_xml() # Persistir cambio
        return jsonify({"status": "success", "message": f"Categoría '{nueva_categoria.nombre}' creada exitosamente."}), 201
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "El ID debe ser un número válido."}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error inesperado: {e}"}), 500

# --- ENDPOINT CORREGIDO Y VALIDADO ---
@app.route('/crear-configuracion', methods=['POST'])
def crear_configuracion():
    """ Endpoint para crear una nueva configuración CON sus recursos. """
    from models import Configuracion, RecursoConfiguracion
    data = request.json

    # Validación campos básicos
    required_basic = ['id', 'nombre', 'descripcion', 'id_categoria']
    if not all(data.get(k) for k in required_basic):
        return jsonify({"status": "error", "message": f"Faltan datos básicos: {', '.join(required_basic)}"}), 400

    try:
        id_conf = int(data['id'])
        id_cat = int(data['id_categoria'])
        
        categoria = datalake.find_categoria(id_cat)
        if not categoria:
            return jsonify({"status": "error", "message": f"Categoría con ID {id_cat} no encontrada."}), 404
        
        # Verificar si ya existe config con ese ID en cualquier categoría
        if any(c.id == id_conf for cat in datalake.categorias for c in cat.configuraciones):
             return jsonify({"status": "error", "message": f"Ya existe una configuración con ID {id_conf} en el sistema."}), 400

        nueva_config = Configuracion(
            id=id_conf,
            nombre=data['nombre'],
            descripcion=data['descripcion'],
            recursos=[] # Lista para llenar
        )

        # Procesar recursos del payload
        recursos_payload = data.get('recursos', []) # Debe ser una lista [{'id_recurso': X, 'cantidad': Y}]
        if not isinstance(recursos_payload, list):
             return jsonify({"status": "error", "message": "El campo 'recursos' debe ser una lista."}), 400

        # Es válido crear una configuración sin recursos inicialmente
        # if not recursos_payload:
        #      return jsonify({"status": "error", "message": "Debe añadir al menos un recurso a la configuración."}), 400
        
        for rec_data in recursos_payload:
            if not isinstance(rec_data, dict) or not rec_data.get('id_recurso') or not str(rec_data.get('cantidad')): # str() para aceptar 0
                return jsonify({"status": "error", "message": "Cada recurso debe ser un objeto con 'id_recurso' y 'cantidad' no vacíos."}), 400
            
            try:
                id_rec = int(rec_data['id_recurso'])
                cantidad = float(rec_data['cantidad'])

                if not datalake.find_recurso(id_rec):
                    return jsonify({"status": "error", "message": f"El recurso con ID {id_rec} no existe."}), 404
                
                # Evitar duplicados del mismo recurso en la misma config
                if any(r.id_recurso == id_rec for r in nueva_config.recursos):
                    return jsonify({"status": "error", "message": f"El recurso con ID {id_rec} ya fue añadido a esta configuración."}), 400

                nueva_config.recursos.append(RecursoConfiguracion(id_recurso=id_rec, cantidad=cantidad))
            
            except (ValueError, TypeError):
                 return jsonify({"status": "error", "message": f"ID de recurso ('{rec_data.get('id_recurso')}') y cantidad ('{rec_data.get('cantidad')}') deben ser números válidos."}), 400
        
        # Añadir la nueva configuración a la categoría encontrada
        categoria.configuraciones.append(nueva_config)
        datalake.guardar_a_xml() # Persistir cambio
        return jsonify({"status": "success", "message": f"Configuración '{nueva_config.nombre}' (ID: {id_conf}) creada con {len(nueva_config.recursos)} recursos en '{categoria.nombre}'."}), 201
    
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "El ID de Configuración y el ID de Categoría deben ser números válidos."}), 400
    except Exception as e:
        app.logger.error(f"Error inesperado al crear configuración: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Error inesperado: {e}"}), 500
# --- FIN ENDPOINT CORREGIDO ---


@app.route('/crear-instancia', methods=['POST'])
def crear_instancia():
    """ Endpoint para crear una nueva instancia. """
    from models import Instancia
    data = request.json

    if not all(data.get(k) for k in ['id', 'nombre', 'nit', 'id_configuracion', 'fecha_inicio']):
        return jsonify({"status": "error", "message": "Faltan datos para crear la instancia."}), 400

    try:
        nit_cliente = data['nit']
        id_inst = int(data['id'])
        id_conf = int(data['id_configuracion'])

        cliente = datalake.find_cliente(nit_cliente)
        if not cliente:
            return jsonify({"status": "error", "message": f"Cliente con NIT {nit_cliente} no encontrado."}), 404

        config = datalake.find_configuracion(id_conf)
        if not config:
            return jsonify({"status": "error", "message": f"Configuración con ID {id_conf} no encontrada."}), 404
        
        if any(i.id == id_inst for i in cliente.instancias):
             return jsonify({"status": "error", "message": f"Ya existe una instancia con ID {id_inst} para este cliente."}), 400
        
        nueva_instancia = Instancia(
            id=id_inst,
            id_configuracion=id_conf,
            nombre=data['nombre'],
            fecha_inicio=data['fecha_inicio'], # Ya viene en formato dd/mm/yyyy
            estado='Vigente',
            fecha_final=None,
            consumos=[]
        )
        cliente.instancias.append(nueva_instancia)
        datalake.guardar_a_xml()
        return jsonify({"status": "success", "message": f"Instancia '{nueva_instancia.nombre}' creada para el cliente {cliente.nombre}."}), 201
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "El ID de Instancia y el ID de Configuración deben ser números válidos."}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error inesperado: {e}"}), 500

@app.route('/cancelar-instancia', methods=['POST'])
def cancelar_instancia():
    """ Endpoint para cancelar una instancia existente. """
    data = request.json
    
    if not all(data.get(k) for k in ['nit', 'id_instancia', 'fecha_final']):
        return jsonify({"status": "error", "message": "Faltan datos para cancelar la instancia."}), 400
    
    try:
        nit_cliente = data['nit']
        id_instancia = int(data['id_instancia'])
        fecha_final = data['fecha_final'] # Ya viene en dd/mm/yyyy

        cliente = datalake.find_cliente(nit_cliente)
        if not cliente:
            return jsonify({"status": "error", "message": f"Cliente con NIT {nit_cliente} no encontrado."}), 404
        
        instancia = datalake.find_instancia(nit_cliente, id_instancia)
        if not instancia:
            return jsonify({"status": "error", "message": f"Instancia con ID {id_instancia} no encontrada."}), 404
        
        if instancia.estado == 'Cancelada':
            return jsonify({"status": "error", "message": f"La instancia '{instancia.nombre}' ya estaba cancelada."}), 400
        
        instancia.estado = 'Cancelada'
        instancia.fecha_final = fecha_final
        datalake.guardar_a_xml() # Persistir cambio
        return jsonify({"status": "success", "message": f"Instancia '{instancia.nombre}' (ID: {id_instancia}) ha sido cancelada."}), 200

    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "El ID de Instancia debe ser un número válido."}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error inesperado: {e}"}), 500


# --- Endpoints de Facturación y Reportes ---

@app.route('/generar-factura', methods=['POST'])
def generar_factura():
    """ 
    Genera una factura para un cliente en un rango de fechas.
    Calcula el total, limpia los consumos y guarda la factura.
    """
    from models import Factura, DetalleFactura, DetalleRecursoFactura
    data = request.json
    
    if not all(data.get(k) for k in ['nit', 'fecha_inicio', 'fecha_fin']):
        return jsonify({"status": "error", "message": "Faltan datos (NIT, fecha inicio, fecha fin) para generar la factura."}), 400
    
    nit_cliente = data['nit']
    fecha_inicio_str = data['fecha_inicio']
    fecha_fin_str = data['fecha_fin']

    cliente = datalake.find_cliente(nit_cliente)
    if not cliente:
        return jsonify({"status": "error", "message": "Cliente no encontrado"}), 404
    
    try:
        # Validación de fechas (aunque el frontend ya las formatea)
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%d/%m/%Y').date() # Compara solo fechas
        fecha_fin = datetime.strptime(fecha_fin_str, '%d/%m/%Y').date()
    except ValueError:
        return jsonify({"status": "error", "message": "Formato de fecha inválido. Usar dd/mm/yyyy."}), 400
    
    total_factura = 0.0
    detalles_factura_obj = [] # Lista de objetos DetalleFactura
    consumos_procesados_en_esta_factura = False

    for instancia in cliente.instancias:
        if not instancia.consumos: continue # Si no hay consumos, salta

        config = datalake.find_configuracion(instancia.id_configuracion)
        if not config: continue 

        # IMPORTANTE: Aquí debería ir la lógica para filtrar consumos por fecha
        # Si el XML de consumo tuviera fechas por cada entrada, se filtraría aquí.
        # Como no las tiene, se procesan *todos* los consumos pendientes de la instancia.
        horas_consumidas_total = sum(instancia.consumos)
        if horas_consumidas_total == 0: continue

        costo_instancia = 0.0
        recursos_costo_obj = []
        categoria = datalake.find_categoria_por_config(config.id)
        id_categoria_actual = categoria.id if categoria else None

        for rec_conf in config.recursos:
            recurso = datalake.find_recurso(rec_conf.id_recurso)
            if recurso:
                costo_recurso = rec_conf.cantidad * recurso.valor_x_hora * horas_consumidas_total
                costo_instancia += costo_recurso
                recursos_costo_obj.append(DetalleRecursoFactura(
                    id_recurso=recurso.id, nombre_recurso=recurso.nombre, cantidad=rec_conf.cantidad,
                    metrica=recurso.metrica, valor_x_hora=recurso.valor_x_hora, subtotal=costo_recurso
                ))
        
        if costo_instancia > 0:
            total_factura += costo_instancia
            detalles_factura_obj.append(DetalleFactura(
                id_instancia=instancia.id, nombre_instancia=instancia.nombre, id_configuracion=config.id,
                nombre_configuracion=config.nombre, id_categoria=id_categoria_actual, 
                horas_consumidas=horas_consumidas_total, subtotal_instancia=costo_instancia,
                recursos_costo=recursos_costo_obj
            ))
            # Marcar que sí se procesaron consumos
            consumos_procesados_en_esta_factura = True
            # Limpiar consumos *solo* si se generó detalle para esta instancia
            instancia.consumos.clear() 

    if not consumos_procesados_en_esta_factura:
        return jsonify({
            "status": "info", 
            "message": f"No se encontraron consumos pendientes para el cliente {nit_cliente}."
        }), 200 # OK, pero sin factura

    # Crear y guardar la factura
    nueva_factura = Factura(
        id=len(datalake.facturas) + 1, nit_cliente=nit_cliente, nombre_cliente=cliente.nombre,
        fecha_factura=fecha_fin_str, # Usa fecha fin como fecha de corte
        monto_total=total_factura, detalles_instancias=detalles_factura_obj
    )
    datalake.facturas.append(nueva_factura)
    # Guardar cambios (consumos limpiados y nueva factura)
    datalake.guardar_a_xml() 

    return jsonify({
        "status": "success",
        "message": f"Factura {nueva_factura.id} generada exitosamente para {cliente.nombre}.",
        **nueva_factura.to_dict() # Devuelve los datos de la factura creada
    })


@app.route('/reporte/ventas-recurso', methods=['POST'])
def reporte_ventas_recurso():
    """ Analiza los recursos que más ingresos generan en un rango de fechas. """
    data = request.json
    fecha_inicio_str = data.get('fecha_inicio')
    fecha_fin_str = data.get('fecha_fin')
    
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%d/%m/%Y').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%d/%m/%Y').date()
        if fecha_inicio > fecha_fin:
             return jsonify({"status": "error", "message": "La fecha de inicio no puede ser posterior a la fecha fin."}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Formato de fecha inválido. Usar dd/mm/yyyy."}), 400

    reporte = {} # { "Nombre Recurso": total_generado }
    
    for factura in datalake.facturas:
        try:
            fecha_factura = datetime.strptime(factura.fecha_factura, '%d/%m/%Y').date()
            if not (fecha_inicio <= fecha_factura <= fecha_fin): continue
        except ValueError: continue

        for detalle_inst in factura.detalles_instancias:
            for detalle_rec in detalle_inst.recursos_costo:
                nombre_rec = f"{detalle_rec.nombre_recurso} (ID: {detalle_rec.id_recurso})" # Incluir ID para diferenciar
                reporte[nombre_rec] = reporte.get(nombre_rec, 0) + detalle_rec.subtotal

    return jsonify({"status": "success", "reporte": reporte})


@app.route('/reporte/ventas-categoria', methods=['POST'])
def reporte_ventas_categoria():
    """ Analiza las categorías/configuraciones que más ingresos generan. """
    data = request.json
    fecha_inicio_str = data.get('fecha_inicio')
    fecha_fin_str = data.get('fecha_fin')
    
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%d/%m/%Y').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%d/%m/%Y').date()
        if fecha_inicio > fecha_fin:
             return jsonify({"status": "error", "message": "La fecha de inicio no puede ser posterior a la fecha fin."}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Formato de fecha inválido. Usar dd/mm/yyyy."}), 400

    reporte = {} # { "Categoria > Configuracion": total_generado }

    for factura in datalake.facturas:
        try:
            fecha_factura = datetime.strptime(factura.fecha_factura, '%d/%m/%Y').date()
            if not (fecha_inicio <= fecha_factura <= fecha_fin): continue
        except ValueError: continue

        for detalle_inst in factura.detalles_instancias:
            categoria = datalake.find_categoria(detalle_inst.id_categoria)
            nombre_cat = categoria.nombre if categoria else f"Cat ID: {detalle_inst.id_categoria}"
            llave_reporte = f"{nombre_cat} (ID: {detalle_inst.id_categoria}) > {detalle_inst.nombre_configuracion} (ID: {detalle_inst.id_configuracion})" # Más específico
            reporte[llave_reporte] = reporte.get(llave_reporte, 0) + detalle_inst.subtotal_instancia

    return jsonify({"status": "success", "reporte": reporte})


if __name__ == '__main__':
    # Asegura que la carpeta del backend exista para el db_persistente.xml
    # La instancia datalake ya se crea globalmente y llama a cargar_desde_xml_persistente()
    # No es necesario llamar a os.makedirs aquí si Datalake lo maneja o asume que existe
    app.run(debug=True, port=5000)

