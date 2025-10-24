import os
import uuid # Para generar IDs de factura únicos
from datetime import datetime
from flask import Flask, request, jsonify
from database import datalake # Se importa la instancia ya inicializada
# CORRECCIÓN: Nombres de import actualizados para coincidir con models.py
from models import Cliente, Recurso, Categoria, Configuracion, RecursoConfiguracion, Instancia, Factura, DetalleInstanciaFactura, DetalleRecursoInstancia
from utils import validar_nit, extraer_fecha

app = Flask(__name__)

# --- Endpoints Principales (Carga XML y Reset) ---

@app.route('/reset', methods=['POST'])
def reset_sistema():
    """ Endpoint para borrar todos los datos en memoria y el archivo persistente. """
    try:
        datalake.reset_datos()
        return jsonify({"status": "success", "message": "Sistema inicializado. Todos los datos han sido borrados."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error durante el reseteo: {e}"}), 500

@app.route('/cargar-configuracion', methods=['POST'])
def cargar_configuracion():
    """ Endpoint para recibir y procesar el XML de configuración. """
    if 'archivo' not in request.files:
        return jsonify({"status": "error", "message": "No se encontró el archivo"}), 400

    archivo = request.files['archivo']
    if archivo.filename == '':
        return jsonify({"status": "error", "message": "No se seleccionó ningún archivo"}), 400

    if archivo and archivo.filename.lower().endswith('.xml'):
        try:
            xml_string = archivo.read().decode('utf-8')
            resultado = datalake.cargar_desde_xml_string(xml_string)
            if resultado["status"] == "success":
                datalake.guardar_a_xml() # Guardar después de cargar exitosamente
                return jsonify(resultado), 200
            else:
                # No guardar si hubo error en la carga lógica
                return jsonify(resultado), 400 # Usar 400 para errores de datos
        except UnicodeDecodeError:
             return jsonify({"status": "error", "message": "Error de codificación. Asegúrese que el archivo sea UTF-8."}), 400
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": f"Error inesperado al procesar archivo: {e}"}), 500
    else:
        return jsonify({"status": "error", "message": "Archivo inválido. Debe ser un .xml"}), 400


@app.route('/cargar-consumo', methods=['POST'])
def cargar_consumo():
    """ Endpoint para recibir y procesar el XML de consumo. """
    if 'archivo' not in request.files:
        return jsonify({"status": "error", "message": "No se encontró el archivo"}), 400

    archivo = request.files['archivo']
    if archivo.filename == '':
        return jsonify({"status": "error", "message": "No se seleccionó ningún archivo"}), 400

    if archivo and archivo.filename.lower().endswith('.xml'):
        try:
            xml_string = archivo.read().decode('utf-8')
            resultado = datalake.cargar_consumo_desde_xml_string(xml_string)
            if resultado["status"] == "success":
                datalake.guardar_a_xml() # Guardar después de cargar exitosamente
                return jsonify(resultado), 200
            else:
                 # No guardar si hubo error en la carga lógica
                return jsonify(resultado), 400 # Usar 400 para errores de datos
        except UnicodeDecodeError:
             return jsonify({"status": "error", "message": "Error de codificación. Asegúrese que el archivo sea UTF-8."}), 400
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": f"Error inesperado al procesar archivo: {e}"}), 500
    else:
        return jsonify({"status": "error", "message": "Archivo inválido. Debe ser un .xml"}), 400


@app.route('/consultar-datos', methods=['GET'])
def consultar_datos():
    """ Endpoint para obtener un resumen de los datos actuales del sistema. """
    try:
        datos = datalake.get_datos_generales()
        return jsonify(datos)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al consultar datos: {e}"}), 500

# --- Endpoints de Creación de Datos (Formularios Frontend) ---

@app.route('/crear-cliente', methods=['POST'])
def crear_cliente():
    """ Endpoint para crear un nuevo cliente desde el formulario. """
    data = request.json
    required_fields = ['nit', 'nombre', 'usuario', 'clave', 'direccion', 'correo']

    # Validación robusta de campos no vacíos
    missing_or_empty = [k for k in required_fields if not data.get(k)]
    if missing_or_empty:
        return jsonify({"status": "error", "message": f"Faltan datos o están vacíos: {', '.join(missing_or_empty)}."}), 400

    nit = data['nit']
    if not validar_nit(nit):
        return jsonify({"status": "error", "message": "El NIT proporcionado es inválido."}), 400

    if datalake.find_cliente(nit):
        return jsonify({"status": "error", "message": f"Ya existe un cliente con el NIT {nit}."}), 400

    try:
        nuevo_cliente = Cliente(
            nit=nit, nombre=data['nombre'], usuario=data['usuario'], clave=data['clave'],
            direccion=data['direccion'], correo=data['correo'], instancias=[] # Inicia sin instancias
        )
        datalake.clientes.append(nuevo_cliente)
        datalake.guardar_a_xml() # Guardar persistencia
        return jsonify({"status": "success", "message": f"Cliente '{data['nombre']}' (NIT: {nit}) creado exitosamente."}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al crear cliente: {e}"}), 500


@app.route('/crear-recurso', methods=['POST'])
def crear_recurso():
    """ Endpoint para crear un nuevo recurso. """
    data = request.json
    required_fields = ['id', 'nombre', 'abreviatura', 'metrica', 'tipo', 'valor_x_hora']

    missing_or_empty = [k for k in required_fields if data.get(k) is None or data.get(k) == '']
    if missing_or_empty:
        return jsonify({"status": "error", "message": f"Faltan datos o están vacíos: {', '.join(missing_or_empty)}."}), 400

    try:
        rec_id = int(data['id'])
        valor_hora = float(data['valor_x_hora'])
        tipo = data['tipo'].strip().upper()
        if tipo not in ["HARDWARE", "SOFTWARE"]:
             return jsonify({"status": "error", "message": "Tipo de recurso inválido. Debe ser 'HARDWARE' o 'SOFTWARE'."}), 400

    except ValueError:
        return jsonify({"status": "error", "message": "ID y Valor por Hora deben ser números válidos."}), 400

    if datalake.find_recurso(rec_id):
        return jsonify({"status": "error", "message": f"Ya existe un recurso con el ID {rec_id}."}), 400

    try:
        nuevo_recurso = Recurso(
            id=rec_id, nombre=data['nombre'], abreviatura=data['abreviatura'], metrica=data['metrica'],
            tipo=tipo, valor_x_hora=valor_hora
        )
        datalake.recursos.append(nuevo_recurso)
        datalake.guardar_a_xml()
        return jsonify({"status": "success", "message": f"Recurso '{data['nombre']}' (ID: {rec_id}) creado exitosamente."}), 201
    except Exception as e:
         return jsonify({"status": "error", "message": f"Error al crear recurso: {e}"}), 500

@app.route('/crear-categoria', methods=['POST'])
def crear_categoria():
    """ Endpoint para crear una nueva categoría. """
    data = request.json
    required_fields = ['id', 'nombre', 'descripcion', 'carga_trabajo']

    missing_or_empty = [k for k in required_fields if not data.get(k)]
    if missing_or_empty:
         return jsonify({"status": "error", "message": f"Faltan datos o están vacíos: {', '.join(missing_or_empty)}."}), 400

    try:
        cat_id = int(data['id'])
    except ValueError:
        return jsonify({"status": "error", "message": "El ID de la categoría debe ser un número entero."}), 400

    if datalake.find_categoria(cat_id):
        return jsonify({"status": "error", "message": f"Ya existe una categoría con el ID {cat_id}."}), 400

    try:
        nueva_categoria = Categoria(
            id=cat_id, nombre=data['nombre'], descripcion=data['descripcion'],
            carga_trabajo=data['carga_trabajo'], configuraciones=[] # Inicia vacía
        )
        datalake.categorias.append(nueva_categoria)
        datalake.guardar_a_xml()
        return jsonify({"status": "success", "message": f"Categoría '{data['nombre']}' (ID: {cat_id}) creada exitosamente."}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al crear categoría: {e}"}), 500


@app.route('/crear-configuracion', methods=['POST'])
def crear_configuracion():
    """ Endpoint para crear una nueva configuración dentro de una categoría. """
    data = request.json
    required_fields = ['id_categoria', 'id', 'nombre', 'descripcion'] # 'recursos' es opcional aquí

    missing_or_empty = [k for k in required_fields if data.get(k) is None or data.get(k) == '']
    if missing_or_empty:
         return jsonify({"status": "error", "message": f"Faltan datos o están vacíos: {', '.join(missing_or_empty)}."}), 400

    try:
        cat_id = int(data['id_categoria'])
        conf_id = int(data['id'])
    except ValueError:
        return jsonify({"status": "error", "message": "ID de Categoría y ID de Configuración deben ser números enteros."}), 400

    categoria = datalake.find_categoria(cat_id)
    if not categoria:
        return jsonify({"status": "error", "message": f"Categoría con ID {cat_id} no encontrada."}), 404 # 404 Not Found

    if datalake.find_configuracion(conf_id):
         # Verifica si ya existe en OTRA categoría (error) o en esta (permitiría actualizar, pero la UI no lo soporta aún)
         cat_existente = datalake.find_categoria_por_config(conf_id)
         if cat_existente and cat_existente.id != cat_id:
              return jsonify({"status": "error", "message": f"Ya existe una configuración con ID {conf_id} en la Categoría ID {cat_existente.id}."}), 400
         elif cat_existente and cat_existente.id == cat_id:
              # Podríamos implementar lógica de actualización aquí si quisiéramos
              return jsonify({"status": "error", "message": f"Ya existe una configuración con ID {conf_id} en esta categoría. Use XML para actualizar por ahora."}), 400
         else: # Caso raro, config existe pero no tiene categoría?
              return jsonify({"status": "error", "message": f"Ya existe una configuración con ID {conf_id}."}), 400


    recursos_config_list = []
    # Procesar recursos si vienen en la petición
    recursos_data = data.get('recursos', []) # Espera una lista de {'id_recurso': X, 'cantidad': Y}
    if not isinstance(recursos_data, list):
         return jsonify({"status": "error", "message": "El campo 'recursos' debe ser una lista."}), 400

    for i, rec_data in enumerate(recursos_data):
        if not isinstance(rec_data, dict) or 'id_recurso' not in rec_data or 'cantidad' not in rec_data:
            return jsonify({"status": "error", "message": f"Formato inválido para recurso en índice {i}. Debe ser {{'id_recurso': X, 'cantidad': Y}}."}), 400
        try:
            rec_id = int(rec_data['id_recurso'])
            cantidad = float(rec_data['cantidad'])
            if cantidad <= 0:
                 return jsonify({"status": "error", "message": f"Recurso ID {rec_id}: la cantidad debe ser mayor que cero."}), 400
        except ValueError:
            return jsonify({"status": "error", "message": f"ID de recurso y cantidad deben ser números válidos (índice {i})."}), 400

        recurso_global = datalake.find_recurso(rec_id)
        if not recurso_global:
            return jsonify({"status": "error", "message": f"El recurso con ID {rec_id} no existe globalmente."}), 404

        # Evitar duplicados del mismo recurso dentro de esta configuración
        if any(rc.id_recurso == rec_id for rc in recursos_config_list):
            return jsonify({"status": "error", "message": f"El recurso ID {rec_id} está duplicado en la configuración."}), 400

        recursos_config_list.append(RecursoConfiguracion(id_recurso=rec_id, cantidad=cantidad))

    try:
        nueva_configuracion = Configuracion(
            id=conf_id, nombre=data['nombre'], descripcion=data['descripcion'],
            recursos=recursos_config_list
        )
        categoria.configuraciones.append(nueva_configuracion)
        datalake.guardar_a_xml()
        return jsonify({"status": "success", "message": f"Configuración '{data['nombre']}' (ID: {conf_id}) creada en Categoría '{categoria.nombre}'."}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al crear configuración: {e}"}), 500

@app.route('/crear-instancia', methods=['POST'])
def crear_instancia():
    """ Endpoint para crear una nueva instancia para un cliente. """
    data = request.json
    required_fields = ['nit_cliente', 'id_instancia', 'id_configuracion', 'nombre', 'fecha_inicio']

    missing_or_empty = [k for k in required_fields if not data.get(k)]
    if missing_or_empty:
        return jsonify({"status": "error", "message": f"Faltan datos o están vacíos: {', '.join(missing_or_empty)}."}), 400

    nit = data['nit_cliente']
    cliente = datalake.find_cliente(nit)
    if not cliente:
        return jsonify({"status": "error", "message": f"Cliente con NIT {nit} no encontrado."}), 404

    try:
        inst_id = int(data['id_instancia'])
        conf_id = int(data['id_configuracion'])
    except ValueError:
         return jsonify({"status": "error", "message": "ID de Instancia y ID de Configuración deben ser números enteros."}), 400

    configuracion = datalake.find_configuracion(conf_id)
    if not configuracion:
        return jsonify({"status": "error", "message": f"Configuración con ID {conf_id} no encontrada."}), 404

    if datalake.find_instancia(nit, inst_id):
        return jsonify({"status": "error", "message": f"Ya existe una instancia con ID {inst_id} para el cliente NIT {nit}."}), 400

    # Validar formato de fecha dd/mm/yyyy (si no, guardar lo que vino)
    fecha_inicio_str = data['fecha_inicio']
    fecha_valida = extraer_fecha(fecha_inicio_str) # Usa la misma función que el XML

    try:
        nueva_instancia = Instancia(
            id=inst_id, id_configuracion=conf_id, nombre=data['nombre'],
            fecha_inicio=fecha_valida if fecha_valida else fecha_inicio_str, # Guarda fecha extraída o el string original
            estado='Vigente', # Nueva instancia siempre Vigente
            fecha_final=None,
            consumos=[]
        )
        cliente.instancias.append(nueva_instancia)
        datalake.guardar_a_xml()
        return jsonify({"status": "success", "message": f"Instancia '{data['nombre']}' (ID: {inst_id}) creada para cliente NIT {nit}."}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al crear instancia: {e}"}), 500


@app.route('/cancelar-instancia', methods=['POST'])
def cancelar_instancia():
    """ Endpoint para cancelar una instancia existente. """
    data = request.json
    required_fields = ['nit_cliente', 'id_instancia', 'fecha_final']

    missing_or_empty = [k for k in required_fields if not data.get(k)]
    if missing_or_empty:
         return jsonify({"status": "error", "message": f"Faltan datos o están vacíos: {', '.join(missing_or_empty)}."}), 400

    nit = data['nit_cliente']
    try:
        inst_id = int(data['id_instancia'])
    except ValueError:
        return jsonify({"status": "error", "message": "ID de Instancia debe ser un número entero."}), 400

    instancia = datalake.find_instancia(nit, inst_id)
    if not instancia:
        return jsonify({"status": "error", "message": f"No se encontró instancia con ID {inst_id} para el cliente NIT {nit}."}), 404

    if instancia.estado == 'Cancelada':
         return jsonify({"status": "warning", "message": f"La instancia ID {inst_id} ya estaba cancelada."}), 200 # O 400 si se prefiere error

    # Validar formato de fecha dd/mm/yyyy
    fecha_final_str = data['fecha_final']
    fecha_valida = extraer_fecha(fecha_final_str)
    if not fecha_valida:
         # Considerar si permitir cancelar sin fecha válida o requerirla
         # return jsonify({"status": "error", "message": "Formato de fecha final inválido. Use dd/mm/yyyy."}), 400
         fecha_a_usar = fecha_final_str # Guardar el string si no es válido
    else:
        fecha_a_usar = fecha_valida

    try:
        instancia.estado = 'Cancelada'
        instancia.fecha_final = fecha_a_usar
        datalake.guardar_a_xml()
        return jsonify({"status": "success", "message": f"Instancia ID {inst_id} (NIT: {nit}) cancelada exitosamente con fecha {fecha_a_usar}."}), 200
    except Exception as e:
        # Revertir cambios en memoria si falla el guardado? Podría ser...
        # instancia.estado = 'Vigente'
        # instancia.fecha_final = None
        return jsonify({"status": "error", "message": f"Error al cancelar instancia: {e}"}), 500


# --- Endpoint de Facturación ---

@app.route('/generar-factura', methods=['POST'])
def generar_factura():
    """
    Genera una factura para UN cliente específico basado en NIT,
    considerando todos sus consumos pendientes HASTA UNA FECHA DADA.
    Limpia los consumos de las instancias facturadas.
    """
    data = request.json
    nit_cliente = data.get('nit_cliente')
    fecha_fin_rango_str = data.get('fecha_factura') # Espera dd/mm/yyyy

    if not nit_cliente or not fecha_fin_rango_str:
        return jsonify({"status": "error", "message": "Faltan NIT del cliente o fecha de factura (dd/mm/yyyy)."}), 400

    # Validar fecha (aunque no se use para filtrar consumos, sí para la factura)
    fecha_factura = extraer_fecha(fecha_fin_rango_str)
    if not fecha_factura:
         return jsonify({"status": "error", "message": "Formato de fecha de factura inválido. Use dd/mm/yyyy."}), 400

    cliente = datalake.find_cliente(nit_cliente)
    if not cliente:
        return jsonify({"status": "error", "message": f"Cliente con NIT {nit_cliente} no encontrado"}), 404

    total_factura_general = 0.0
    detalles_instancias_factura = []
    instancias_con_consumo = False

    for instancia in cliente.instancias:
        if not instancia.consumos:
            continue # Saltar instancias sin consumos pendientes

        instancias_con_consumo = True
        horas_consumidas_instancia = sum(instancia.consumos)
        costo_total_instancia = 0.0
        detalles_recursos_instancia = [] # Para esta instancia específica

        config = datalake.find_configuracion(instancia.id_configuracion)
        if not config:
            # ¿Qué hacer si la config ya no existe? ¿Facturar a 0? ¿Error?
            # Por ahora, facturamos a 0 y logueamos advertencia.
            print(f"ADVERTENCIA: Configuración ID {instancia.id_configuracion} para Instancia ID {instancia.id} (NIT {nit_cliente}) no encontrada al facturar. Costo será 0.")
            continue # O podríamos añadir un detalle con costo 0

        categoria_contenedora = datalake.find_categoria_por_config(config.id)

        for rec_conf in config.recursos:
            recurso = datalake.find_recurso(rec_conf.id_recurso)
            if recurso:
                costo_recurso_en_instancia = rec_conf.cantidad * recurso.valor_x_hora * horas_consumidas_instancia
                costo_total_instancia += costo_recurso_en_instancia

                # CORRECCIÓN: Usar nombre de clase correcto
                detalles_recursos_instancia.append(DetalleRecursoInstancia(
                    id_recurso=recurso.id,
                    nombre_recurso=recurso.nombre,
                    cantidad=rec_conf.cantidad,
                    metrica=recurso.metrica,
                    valor_x_hora=recurso.valor_x_hora,
                    subtotal=costo_recurso_en_instancia
                ))
            else:
                 # Recurso de la config ya no existe globalmente? Loguear y continuar.
                 print(f"ADVERTENCIA: Recurso ID {rec_conf.id_recurso} (parte de Config ID {config.id}) no encontrado al facturar Instancia ID {instancia.id}. No se cobrará por él.")


        total_factura_general += costo_total_instancia

        # CORRECCIÓN: Usar nombre de clase correcto
        detalles_instancias_factura.append(DetalleInstanciaFactura(
            id_instancia=instancia.id,
            nombre_instancia=instancia.nombre,
            id_configuracion=config.id,
            nombre_configuracion=config.nombre,
            id_categoria=categoria_contenedora.id if categoria_contenedora else None,
            horas_consumidas=horas_consumidas_instancia,
            subtotal_instancia=costo_total_instancia,
            recursos_costo=detalles_recursos_instancia
        ))

        # Limpiar consumos SÓLO de esta instancia que se acaba de facturar
        instancia.consumos.clear()

    if not instancias_con_consumo:
        return jsonify({"status": "info", "message": f"El cliente NIT {nit_cliente} no tiene consumos pendientes para facturar."}), 200 # O 404 si prefieres


    # Generar ID único para la factura y guardar
    # Simplificado: usamos timestamp + parte de UUID. Mejor usar secuencia de BD real.
    # CORRECCIÓN: Usar timestamp como entero + parte UUID para ID numérico
    nuevo_id_factura = int(datetime.now().timestamp()) # Usa timestamp como ID numérico simple
    while any(f.id == nuevo_id_factura for f in datalake.facturas): # Evitar colisiones (poco probable)
        nuevo_id_factura += 1


    # CORRECCIÓN: Usar nombre de clase correcto
    nueva_factura = Factura(
        id=nuevo_id_factura,
        nit_cliente=cliente.nit,
        nombre_cliente=cliente.nombre,
        fecha_factura=fecha_factura, # Usar la fecha del rango
        monto_total=total_factura_general,
        detalles_instancias=detalles_instancias_factura
    )
    datalake.facturas.append(nueva_factura)
    datalake.guardar_a_xml() # Guardar todo, incluyendo consumos limpiados y nueva factura

    # Devolver la factura generada como JSON
    return jsonify({
        "status": "success",
        "message": f"Factura ID {nueva_factura.id} generada exitosamente para cliente NIT {cliente.nit}.",
        "factura": nueva_factura.to_dict() # Devuelve el objeto factura completo
    }), 201


# --- Endpoints de Reportes ---

@app.route('/reporte/ventas-recurso', methods=['POST'])
def reporte_ventas_recurso():
    """ Analiza las facturas en un rango de fechas y agrupa ingresos por recurso. """
    data = request.json
    fecha_inicio_str = data.get('fecha_inicio') # dd/mm/yyyy
    fecha_fin_str = data.get('fecha_fin')       # dd/mm/yyyy

    if not fecha_inicio_str or not fecha_fin_str:
        return jsonify({"status": "error", "message": "Faltan fecha de inicio o fecha de fin (dd/mm/yyyy)."}), 400

    # Convertir fechas para comparación (simplificado, asume formato correcto)
    # Una librería como `datetime.strptime` sería más robusta
    try:
        f_inicio = datetime.strptime(fecha_inicio_str, "%d/%m/%Y").date()
        f_fin = datetime.strptime(fecha_fin_str, "%d/%m/%Y").date()
    except ValueError:
        return jsonify({"status": "error", "message": "Formato de fecha inválido. Use dd/mm/yyyy."}), 400

    ingresos_por_recurso = {} # {id_recurso: total_generado}

    for factura in datalake.facturas:
        try:
            f_factura = datetime.strptime(factura.fecha_factura, "%d/%m/%Y").date()
            if f_inicio <= f_factura <= f_fin:
                # CORRECCIÓN: Usar nombres correctos
                for det_inst in factura.detalles_instancias:
                    for det_rec in det_inst.recursos_costo:
                        rec_id = det_rec.id_recurso
                        ingresos_por_recurso[rec_id] = ingresos_por_recurso.get(rec_id, 0.0) + det_rec.subtotal
        except ValueError:
            continue # Ignorar facturas con fecha inválida

    # Convertir IDs a nombres para el reporte
    resultado = {}
    for rec_id, total in ingresos_por_recurso.items():
        recurso = datalake.find_recurso(rec_id)
        nombre = recurso.nombre if recurso else f"Recurso ID {rec_id} (Eliminado?)"
        resultado[nombre] = round(total, 2)

    # Ordenar por valor descendente
    resultado_ordenado = dict(sorted(resultado.items(), key=lambda item: item[1], reverse=True))

    return jsonify({"status": "success", "reporte_data": resultado_ordenado})


@app.route('/reporte/ventas-categoria', methods=['POST'])
def reporte_ventas_categoria():
    """ Analiza las facturas en un rango de fechas y agrupa ingresos por categoría. """
    data = request.json
    fecha_inicio_str = data.get('fecha_inicio') # dd/mm/yyyy
    fecha_fin_str = data.get('fecha_fin')       # dd/mm/yyyy

    if not fecha_inicio_str or not fecha_fin_str:
         return jsonify({"status": "error", "message": "Faltan fecha de inicio o fecha de fin (dd/mm/yyyy)."}), 400

    try:
        f_inicio = datetime.strptime(fecha_inicio_str, "%d/%m/%Y").date()
        f_fin = datetime.strptime(fecha_fin_str, "%d/%m/%Y").date()
    except ValueError:
        return jsonify({"status": "error", "message": "Formato de fecha inválido. Use dd/mm/yyyy."}), 400

    ingresos_por_categoria = {} # {id_categoria: total_generado}

    for factura in datalake.facturas:
        try:
            f_factura = datetime.strptime(factura.fecha_factura, "%d/%m/%Y").date()
            if f_inicio <= f_factura <= f_fin:
                 # CORRECCIÓN: Usar nombres correctos
                for det_inst in factura.detalles_instancias:
                    cat_id = det_inst.id_categoria # Puede ser None
                    if cat_id is not None:
                         ingresos_por_categoria[cat_id] = ingresos_por_categoria.get(cat_id, 0.0) + det_inst.subtotal_instancia
                    # else: Podríamos agruparlos en "Sin Categoría" si quisiéramos
        except ValueError:
            continue

    # Convertir IDs a nombres
    resultado = {}
    for cat_id, total in ingresos_por_categoria.items():
        categoria = datalake.find_categoria(cat_id)
        nombre = categoria.nombre if categoria else f"Categoría ID {cat_id} (Eliminada?)"
        # Podríamos añadir el nombre de la config si quisiéramos más detalle
        resultado[nombre] = round(total, 2)

    # Ordenar por valor descendente
    resultado_ordenado = dict(sorted(resultado.items(), key=lambda item: item[1], reverse=True))

    return jsonify({"status": "success", "reporte_data": resultado_ordenado})


# --- Punto de Entrada ---
if __name__ == '__main__':
    # CORRECCIÓN: Quitar la creación de directorio de aquí
    # os.makedirs(os.path.dirname(datalake.db_file), exist_ok=True) # Movido a guardar_a_xml
    app.run(debug=True, port=5000)

