import os
import uuid # Para generar IDs únicos de factura
from datetime import datetime # Para la fecha de factura
from flask import Flask, request, jsonify
# CORRECCIÓN: Nombres de import actualizados
from database import datalake # Se importa la instancia ya inicializada
from models import (
    Recurso, Categoria, Configuracion, RecursoConfiguracion,
    Cliente, Instancia, Factura, DetalleInstanciaFactura, DetalleRecursoInstancia
)
from utils import validar_nit, extraer_fecha # Importado para Release 2

app = Flask(__name__)

# --- Endpoints Principales ---

@app.route('/reset', methods=['POST'])
def reset_sistema():
    """ Endpoint para borrar todos los datos en memoria y el archivo persistente. """
    try:
        datalake.reset_datos()
        print("Sistema reseteado y archivo persistente limpiado/eliminado.")
        return jsonify({"status": "success", "message": "Sistema inicializado. Todos los datos han sido borrados."})
    except Exception as e:
        print(f"Error durante el reset: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error al resetear el sistema: {e}"}), 500


@app.route('/cargar-configuracion', methods=['POST'])
def cargar_configuracion():
    """ Endpoint para recibir y procesar el XML de configuración. """
    if 'archivo' not in request.files:
        return jsonify({"status": "error", "message": "No se encontró el archivo"}), 400

    archivo = request.files['archivo']
    if archivo.filename == '':
        return jsonify({"status": "error", "message": "No se seleccionó ningún archivo"}), 400
    if not archivo.filename.lower().endswith('.xml'):
         return jsonify({"status": "error", "message": "El archivo debe ser de tipo .xml"}), 400


    if archivo:
        try:
            xml_string = archivo.read().decode('utf-8')
            resultado = datalake.cargar_desde_xml_string(xml_string) # Datalake ahora guarda automáticamente
            status_code = 200 if resultado["status"] == "success" else 500
            # No es necesario guardar aquí, cargar_desde_xml_string ya lo hace
            # if resultado["status"] == "success":
            #     datalake.guardar_a_xml()
            return jsonify(resultado), status_code
        except UnicodeDecodeError:
             return jsonify({"status": "error", "message": "Error de codificación. Asegúrese que el archivo sea UTF-8."}), 400
        except Exception as e:
            print(f"Error inesperado en /cargar-configuracion: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": f"Error inesperado al procesar el archivo: {e}"}), 500

@app.route('/cargar-consumo', methods=['POST'])
def cargar_consumo():
    """ Endpoint para recibir y procesar el XML de consumo. """
    if 'archivo' not in request.files:
        return jsonify({"status": "error", "message": "No se encontró el archivo"}), 400

    archivo = request.files['archivo']
    if archivo.filename == '':
        return jsonify({"status": "error", "message": "No se seleccionó ningún archivo"}), 400
    if not archivo.filename.lower().endswith('.xml'):
         return jsonify({"status": "error", "message": "El archivo debe ser de tipo .xml"}), 400

    if archivo:
        try:
            xml_string = archivo.read().decode('utf-8')
            resultado = datalake.cargar_consumo_desde_xml_string(xml_string) # Datalake ahora guarda automáticamente
            status_code = 200 if resultado["status"] == "success" else 500
            # No es necesario guardar aquí, cargar_consumo_desde_xml_string ya lo hace
            # if resultado["status"] == "success":
            #    datalake.guardar_a_xml()
            return jsonify(resultado), status_code
        except UnicodeDecodeError:
             return jsonify({"status": "error", "message": "Error de codificación. Asegúrese que el archivo sea UTF-8."}), 400
        except Exception as e:
            print(f"Error inesperado en /cargar-consumo: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": f"Error inesperado al procesar el archivo: {e}"}), 500

@app.route('/consultar-datos', methods=['GET'])
def consultar_datos():
    """ Endpoint para obtener un resumen de los datos actuales del Datalake. """
    try:
        datos = datalake.get_datos_generales()
        return jsonify(datos)
    except Exception as e:
        print(f"Error en /consultar-datos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error al consultar datos: {e}"}), 500

# --- Endpoints de Creación de Datos ---

@app.route('/crear-recurso', methods=['POST'])
def crear_recurso():
    """ Endpoint para crear un nuevo recurso. """
    data = request.json
    campos_requeridos = ['id', 'nombre', 'abreviatura', 'metrica', 'tipo', 'valor_x_hora']

    # Validación de campos y valores no vacíos/nulos
    missing_or_empty = [k for k in campos_requeridos if data.get(k) is None or str(data.get(k)).strip() == ""]
    if missing_or_empty:
        return jsonify({"status": "error", "message": f"Faltan datos o hay campos vacíos para crear el recurso: {', '.join(missing_or_empty)}."}), 400

    try:
        nuevo_id = int(data['id'])
        valor_hora = float(data['valor_x_hora'])
        tipo_recurso = data['tipo'].strip().upper()
        if tipo_recurso not in ['HARDWARE', 'SOFTWARE']:
             return jsonify({"status": "error", "message": "El tipo de recurso debe ser 'HARDWARE' o 'SOFTWARE'."}), 400
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "El ID debe ser un número entero y el valor por hora debe ser numérico."}), 400

    if datalake.find_recurso(nuevo_id):
        return jsonify({"status": "error", "message": f"Ya existe un recurso con el ID {nuevo_id}."}), 400

    nuevo_recurso = Recurso(
        id=nuevo_id,
        nombre=str(data['nombre']).strip(),
        abreviatura=str(data['abreviatura']).strip(),
        metrica=str(data['metrica']).strip(),
        tipo=tipo_recurso,
        valor_x_hora=valor_hora
    )
    datalake.recursos.append(nuevo_recurso)
    datalake.guardar_a_xml() # Persistir cambio
    return jsonify({"status": "success", "message": "Recurso creado exitosamente."}), 201

@app.route('/crear-categoria', methods=['POST'])
def crear_categoria():
    """ Endpoint para crear una nueva categoría. """
    data = request.json
    campos_requeridos = ['id', 'nombre', 'descripcion', 'carga_trabajo']

    missing_or_empty = [k for k in campos_requeridos if data.get(k) is None or str(data.get(k)).strip() == ""]
    if missing_or_empty:
        return jsonify({"status": "error", "message": f"Faltan datos o hay campos vacíos para crear la categoría: {', '.join(missing_or_empty)}."}), 400

    try:
        nuevo_id = int(data['id'])
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "El ID de la categoría debe ser un número entero."}), 400

    if datalake.find_categoria(nuevo_id):
        return jsonify({"status": "error", "message": f"Ya existe una categoría con el ID {nuevo_id}."}), 400

    nueva_categoria = Categoria(
        id=nuevo_id,
        nombre=str(data['nombre']).strip(),
        descripcion=str(data['descripcion']).strip(),
        carga_trabajo=str(data['carga_trabajo']).strip(),
        configuraciones=[] # Nueva categoría inicia sin configuraciones
    )
    datalake.categorias.append(nueva_categoria)
    datalake.guardar_a_xml() # Persistir cambio
    return jsonify({"status": "success", "message": "Categoría creada exitosamente."}), 201

@app.route('/crear-configuracion', methods=['POST'])
def crear_configuracion():
    """ Endpoint para crear una nueva configuración dentro de una categoría existente. """
    data = request.json
    campos_requeridos = ['id_categoria', 'id', 'nombre', 'descripcion', 'recursos']

    missing_or_empty = [k for k in campos_requeridos if data.get(k) is None or (k != 'recursos' and str(data.get(k)).strip() == "")]
    # 'recursos' puede ser lista vacía, pero debe existir
    if 'recursos' not in data or not isinstance(data.get('recursos'), list):
         missing_or_empty.append('recursos (debe ser una lista, puede ser vacía)')

    if missing_or_empty:
        return jsonify({"status": "error", "message": f"Faltan datos, campos vacíos o formato incorrecto para crear la configuración: {', '.join(missing_or_empty)}."}), 400

    try:
        id_cat = int(data['id_categoria'])
        nuevo_id_conf = int(data['id'])
        recursos_data = data['recursos'] # [{ "id_recurso": X, "cantidad": Y }, ...]
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Los IDs de categoría y configuración deben ser números enteros."}), 400

    categoria = datalake.find_categoria(id_cat)
    if not categoria:
        return jsonify({"status": "error", "message": f"Categoría con ID {id_cat} no encontrada."}), 404

    if datalake.find_configuracion(nuevo_id_conf): # Busca globalmente
        return jsonify({"status": "error", "message": f"Ya existe una configuración con el ID {nuevo_id_conf} (globalmente)."}), 400

    recursos_config_obj = []
    # Validación detallada de los recursos
    for i, rec_data in enumerate(recursos_data):
        if not isinstance(rec_data, dict) or 'id_recurso' not in rec_data or 'cantidad' not in rec_data:
            return jsonify({"status": "error", "message": f"Formato inválido para el recurso en índice {i}. Debe ser un objeto con 'id_recurso' y 'cantidad'."}), 400
        try:
            id_rec = int(rec_data['id_recurso'])
            cantidad = float(rec_data['cantidad'])
            if cantidad <= 0:
                 return jsonify({"status": "error", "message": f"Recurso ID {id_rec}: la cantidad debe ser mayor que cero."}), 400
            if not datalake.find_recurso(id_rec):
                return jsonify({"status": "error", "message": f"Recurso con ID {id_rec} no encontrado."}), 404
             # Evitar duplicados del mismo recurso dentro de la config
            if any(rc.id_recurso == id_rec for rc in recursos_config_obj):
                 return jsonify({"status": "error", "message": f"Recurso ID {id_rec} añadido más de una vez a la configuración."}), 400

            recursos_config_obj.append(RecursoConfiguracion(id_recurso=id_rec, cantidad=cantidad))
        except (ValueError, TypeError):
             return jsonify({"status": "error", "message": f"Recurso en índice {i}: 'id_recurso' debe ser entero y 'cantidad' debe ser numérica."}), 400

    nueva_configuracion = Configuracion(
        id=nuevo_id_conf,
        nombre=str(data['nombre']).strip(),
        descripcion=str(data['descripcion']).strip(),
        recursos=recursos_config_obj
    )
    categoria.configuraciones.append(nueva_configuracion)
    datalake.guardar_a_xml() # Persistir cambio
    return jsonify({"status": "success", "message": "Configuración creada exitosamente."}), 201


@app.route('/crear-cliente', methods=['POST'])
def crear_cliente():
    """ Endpoint para crear un nuevo cliente. """
    data = request.json
    campos_requeridos = ['nit', 'nombre', 'usuario', 'clave', 'direccion', 'correo']

    missing_or_empty = [k for k in campos_requeridos if data.get(k) is None or str(data.get(k)).strip() == ""]
    if missing_or_empty:
        return jsonify({"status": "error", "message": f"Faltan datos o hay campos vacíos para crear el cliente: {', '.join(missing_or_empty)}."}), 400

    nit = str(data['nit']).strip()
    if not validar_nit(nit):
        return jsonify({"status": "error", "message": "El NIT proporcionado es inválido."}), 400

    if datalake.find_cliente(nit):
        return jsonify({"status": "error", "message": "Ya existe un cliente con ese NIT."}), 400

    nuevo_cliente = Cliente(
        nit=nit,
        nombre=str(data['nombre']).strip(),
        usuario=str(data['usuario']).strip(),
        clave=str(data['clave']), # Guardar clave como viene (¡inseguro!)
        direccion=str(data['direccion']).strip(),
        correo=str(data['correo']).strip(),
        instancias=[]
    )
    datalake.clientes.append(nuevo_cliente)
    datalake.guardar_a_xml() # Persistir cambio
    return jsonify({"status": "success", "message": "Cliente creado exitosamente."}), 201


@app.route('/crear-instancia', methods=['POST'])
def crear_instancia():
    """ Endpoint para crear (aprovisionar) una nueva instancia para un cliente. """
    data = request.json
    campos_requeridos = ['nit_cliente', 'id_instancia', 'id_configuracion', 'nombre', 'fecha_inicio']

    missing_or_empty = [k for k in campos_requeridos if data.get(k) is None or str(data.get(k)).strip() == ""]
    if missing_or_empty:
        return jsonify({"status": "error", "message": f"Faltan datos o hay campos vacíos para crear la instancia: {', '.join(missing_or_empty)}."}), 400

    nit = str(data['nit_cliente']).strip()
    cliente = datalake.find_cliente(nit)
    if not cliente:
        return jsonify({"status": "error", "message": f"Cliente con NIT {nit} no encontrado."}), 404

    try:
        id_inst = int(data['id_instancia'])
        id_conf = int(data['id_configuracion'])
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Los IDs de instancia y configuración deben ser números enteros."}), 400

    # Validar fecha inicio usando la función de utils
    fecha_inicio_str = str(data['fecha_inicio']).strip()
    fecha_inicio_valida = extraer_fecha(fecha_inicio_str) # Devuelve dd/mm/yyyy o None
    if not fecha_inicio_valida:
        # Aunque el requisito dice extraer, para la creación manual es mejor ser estrictos
        return jsonify({"status": "error", "message": "Formato de fecha de inicio inválido. Use dd/mm/yyyy."}), 400

    if datalake.find_instancia(nit, id_inst):
        return jsonify({"status": "error", "message": f"Ya existe una instancia con ID {id_inst} para el cliente {nit}."}), 400

    configuracion = datalake.find_configuracion(id_conf)
    if not configuracion:
        return jsonify({"status": "error", "message": f"Configuración con ID {id_conf} no encontrada."}), 404

    nueva_instancia = Instancia(
        id=id_inst,
        id_configuracion=id_conf,
        nombre=str(data['nombre']).strip(),
        fecha_inicio=fecha_inicio_valida, # Guarda la fecha extraída/validada
        estado='Vigente', # Nueva instancia siempre inicia Vigente
        fecha_final=None,
        consumos=[]
    )
    cliente.instancias.append(nueva_instancia)
    datalake.guardar_a_xml() # Persistir cambio
    return jsonify({"status": "success", "message": "Instancia creada exitosamente."}), 201

@app.route('/cancelar-instancia', methods=['POST'])
def cancelar_instancia():
    """ Endpoint para cancelar una instancia existente. """
    data = request.json
    campos_requeridos = ['nit_cliente', 'id_instancia', 'fecha_final']

    missing_or_empty = [k for k in campos_requeridos if data.get(k) is None or str(data.get(k)).strip() == ""]
    if missing_or_empty:
        return jsonify({"status": "error", "message": f"Faltan datos o hay campos vacíos para cancelar la instancia: {', '.join(missing_or_empty)}."}), 400

    nit = str(data['nit_cliente']).strip()
    try:
        id_inst = int(data['id_instancia'])
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "El ID de instancia debe ser un número entero."}), 400

    # Validar fecha final
    fecha_final_str = str(data['fecha_final']).strip()
    fecha_final_valida = extraer_fecha(fecha_final_str)
    if not fecha_final_valida:
        return jsonify({"status": "error", "message": "Formato de fecha final inválido. Use dd/mm/yyyy."}), 400

    instancia = datalake.find_instancia(nit, id_inst)
    if not instancia:
        return jsonify({"status": "error", "message": f"Instancia con ID {id_inst} para el cliente {nit} no encontrada."}), 404

    if instancia.estado == 'Cancelada':
        return jsonify({"status": "warning", "message": f"La instancia ID {id_inst} ya estaba cancelada."}), 200 # O 400 si se prefiere error

    instancia.estado = 'Cancelada'
    instancia.fecha_final = fecha_final_valida
    # Los consumos pendientes NO se limpian aquí, se limpian al facturar.

    datalake.guardar_a_xml() # Persistir cambio
    return jsonify({"status": "success", "message": f"Instancia ID {id_inst} cancelada exitosamente."}), 200


# --- Endpoint de Facturación ---

@app.route('/generar-factura', methods=['POST'])
def generar_factura():
    """
    Genera una factura para un cliente, procesando TODOS los consumos pendientes
    de sus instancias VIGENTES. Usa la fecha actual como fecha de emisión.
    Limpia los consumos procesados de esas instancias.
    """
    data = request.json
    nit_cliente = data.get('nit') # Espera solo 'nit'

    # --- CORRECCIÓN: Eliminar la validación de 'fecha_factura' ---
    if not nit_cliente:
        return jsonify({"status": "error", "message": "Falta NIT del cliente."}), 400

    # --- CORRECCIÓN: Generar fecha_factura aquí ---
    fecha_factura_dt = datetime.now()
    fecha_factura_str = fecha_factura_dt.strftime('%d/%m/%Y') # Formato dd/mm/yyyy

    cliente = datalake.find_cliente(nit_cliente)
    if not cliente:
        return jsonify({"status": "error", "message": f"Cliente con NIT {nit_cliente} no encontrado"}), 404

    total_factura_general = 0.0
    detalles_instancias_facturadas = []
    instancias_procesadas_ids = [] # Para saber qué instancias limpiar

    for instancia in cliente.instancias:
        # Solo procesa instancias VIGENTES y con consumos pendientes
        if instancia.estado != 'Vigente' or not instancia.consumos:
            continue

        configuracion = datalake.find_configuracion(instancia.id_configuracion)
        if not configuracion:
            print(f"Advertencia (Factura): Configuración ID {instancia.id_configuracion} para Instancia ID {instancia.id} (NIT {nit_cliente}) no encontrada. Omitiendo instancia.")
            continue # Salta esta instancia si su config no existe

        categoria = datalake.find_categoria_por_config(instancia.id_configuracion) # Necesario para reportes

        horas_consumidas_instancia = sum(instancia.consumos)
        costo_instancia_actual = 0.0
        detalles_recursos_facturados = []

        for rec_conf in configuracion.recursos:
            recurso = datalake.find_recurso(rec_conf.id_recurso)
            if not recurso:
                 print(f"Advertencia (Factura): Recurso ID {rec_conf.id_recurso} de Config ID {configuracion.id} no encontrado. Omitiendo costo de este recurso.")
                 continue # Salta este recurso si no existe globalmente

            costo_recurso_en_instancia = rec_conf.cantidad * recurso.valor_x_hora * horas_consumidas_instancia
            costo_instancia_actual += costo_recurso_en_instancia

            # Usar nombres correctos de models.py
            detalles_recursos_facturados.append(DetalleRecursoInstancia(
                id_recurso=recurso.id,
                nombre_recurso=recurso.nombre,
                cantidad=rec_conf.cantidad,
                metrica=recurso.metrica,
                valor_x_hora=recurso.valor_x_hora,
                subtotal=round(costo_recurso_en_instancia, 2)
            ))

        total_factura_general += costo_instancia_actual
        instancias_procesadas_ids.append(instancia.id) # Marcar para limpiar consumos

        # Usar nombres correctos de models.py
        detalles_instancias_facturadas.append(DetalleInstanciaFactura(
            id_instancia=instancia.id,
            nombre_instancia=instancia.nombre,
            id_configuracion=configuracion.id,
            nombre_configuracion=configuracion.nombre,
            horas_consumidas=round(horas_consumidas_instancia, 2),
            subtotal_instancia=round(costo_instancia_actual, 2),
            id_categoria=categoria.id if categoria else None, # Añadir ID categoría
            recursos_costo=detalles_recursos_facturados
        ))

    if not detalles_instancias_facturadas:
        return jsonify({
            "status": "info", # Cambiado a 'info' para indicar que no hubo error pero no se hizo nada
            "message": "No se encontraron consumos pendientes para facturar en instancias vigentes de este cliente."
        }), 200

    # Generar número único de factura
    num_factura_actual = len(datalake.facturas) + 1
    # Genera un ID más robusto para evitar colisiones simples
    id_factura_unico = f"F-{fecha_factura_dt.strftime('%Y%m%d')}-{num_factura_actual}"

    nueva_factura = Factura(
        id=id_factura_unico, # Usar ID único
        nit_cliente=nit_cliente,
        nombre_cliente=cliente.nombre, # Añadir nombre para conveniencia
        fecha_factura=fecha_factura_str, # Fecha de hoy (dd/mm/yyyy)
        monto_total=round(total_factura_general, 2),
        detalles_instancias=detalles_instancias_facturadas
    )
    datalake.facturas.append(nueva_factura)

    # Limpiar consumos de las instancias procesadas
    for inst_id in instancias_procesadas_ids:
        instancia = datalake.find_instancia(nit_cliente, inst_id)
        if instancia:
            instancia.consumos.clear()

    datalake.guardar_a_xml() # Persistir la nueva factura y la limpieza de consumos

    # Devolver la factura generada como JSON
    return jsonify({
        "status": "success",
        "message": f"Factura {id_factura_unico} generada exitosamente.",
        "factura": nueva_factura.to_dict() # Asume que Factura tiene to_dict()
    }), 201 # 201 Created

# --- Endpoints de Reportes ---

def parse_date_range(args):
    """ Parsea y valida fechas de inicio/fin desde los argumentos GET (YYYY-MM-DD). """
    fecha_inicio_str = args.get('fecha_inicio') # YYYY-MM-DD
    fecha_fin_str = args.get('fecha_fin')       # YYYY-MM-DD
    if not fecha_inicio_str or not fecha_fin_str:
        raise ValueError("Faltan fechas de inicio o fin.")

    try:
        # Convertir a objetos datetime para comparación
        fecha_inicio_dt = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        fecha_fin_dt = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        if fecha_inicio_dt > fecha_fin_dt:
            raise ValueError("La fecha de inicio no puede ser posterior a la fecha fin.")
    except ValueError:
        raise ValueError("Formato de fecha inválido. Use YYYY-MM-DD.")

    # Devolver objetos datetime
    return fecha_inicio_dt, fecha_fin_dt

def filter_facturas_by_date(fecha_inicio_dt, fecha_fin_dt):
    """ Filtra las facturas del datalake por rango de fechas (objetos datetime). """
    facturas_filtradas = []
    for f in datalake.facturas:
        try:
            # Convertir fecha de factura (dd/mm/yyyy) a datetime
            fecha_factura_dt = datetime.strptime(f.fecha_factura, '%d/%m/%Y')
            # Comparar fechas completas (sin hora)
            if fecha_inicio_dt.date() <= fecha_factura_dt.date() <= fecha_fin_dt.date():
                facturas_filtradas.append(f)
        except (ValueError, TypeError):
            print(f"Advertencia: Ignorando factura ID {f.id} con fecha inválida '{f.fecha_factura}'")
            continue # Ignora facturas con fecha inválida
    return facturas_filtradas

@app.route('/reporte/ventas-recurso', methods=['GET']) # Cambiado a GET para reportes
def reporte_ventas_recurso():
    """ Reporte: Recursos que más ingresos generan en un rango de fechas. """
    try:
        fecha_inicio_dt, fecha_fin_dt = parse_date_range(request.args)
        facturas_filtradas = filter_facturas_by_date(fecha_inicio_dt, fecha_fin_dt)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    ingresos_por_recurso = {} # {id_recurso: total_generado}

    for factura in facturas_filtradas:
        for detalle_inst in factura.detalles_instancias:
            for detalle_rec in detalle_inst.recursos_costo:
                id_rec = detalle_rec.id_recurso
                subtotal_rec = detalle_rec.subtotal
                ingresos_por_recurso[id_rec] = ingresos_por_recurso.get(id_rec, 0.0) + subtotal_rec

    # Mapear IDs a nombres y ordenar
    resultado = {}
    for id_rec, total in ingresos_por_recurso.items():
        recurso = datalake.find_recurso(id_rec)
        nombre = f"{recurso.nombre} (ID: {id_rec})" if recurso else f"Recurso Desconocido (ID: {id_rec})"
        resultado[nombre] = round(total, 2)

    # Ordenar por valor descendente
    resultado_ordenado = dict(sorted(resultado.items(), key=lambda item: item[1], reverse=True))

    return jsonify({
        "status": "success",
        "tipo_reporte": "Recursos",
        "fecha_inicio": fecha_inicio_dt.strftime('%d/%m/%Y'), # Devolver en formato dd/mm/yyyy
        "fecha_fin": fecha_fin_dt.strftime('%d/%m/%Y'),       # Devolver en formato dd/mm/yyyy
        "data": resultado_ordenado
    })


@app.route('/reporte/ventas-categoria', methods=['GET']) # Cambiado a GET para reportes
def reporte_ventas_categoria():
    """ Reporte: Categorías/Configuraciones que más ingresos generan en un rango de fechas. """
    try:
        fecha_inicio_dt, fecha_fin_dt = parse_date_range(request.args)
        facturas_filtradas = filter_facturas_by_date(fecha_inicio_dt, fecha_fin_dt)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    # Cambiamos a ingresos por configuración, ya que la categoría se deriva
    ingresos_por_config = {} # {id_config: total_generado}

    for factura in facturas_filtradas:
        for detalle_inst in factura.detalles_instancias:
            id_conf = detalle_inst.id_configuracion
            subtotal_inst = detalle_inst.subtotal_instancia
            ingresos_por_config[id_conf] = ingresos_por_config.get(id_conf, 0.0) + subtotal_inst

    # Mapear IDs a nombres (Config y Cat) y ordenar
    resultado = {}
    for id_conf, total in ingresos_por_config.items():
        config = datalake.find_configuracion(id_conf)
        cat = datalake.find_categoria_por_config(id_conf)
        nombre = "Configuración Desconocida"
        if config and cat:
            nombre = f"Cat: '{cat.nombre}' (ID:{cat.id}) / Conf: '{config.nombre}' (ID:{id_conf})"
        elif config:
            nombre = f"Cat: Desconocida / Conf: '{config.nombre}' (ID:{id_conf})"
        elif cat:
             nombre = f"Cat: '{cat.nombre}' (ID:{cat.id}) / Conf: Desconocida (ID:{id_conf})"
        else:
             nombre = f"Cat/Conf Desconocidas (ID Config: {id_conf})"

        resultado[nombre] = round(total, 2)

     # Ordenar por valor descendente
    resultado_ordenado = dict(sorted(resultado.items(), key=lambda item: item[1], reverse=True))

    return jsonify({
        "status": "success",
        "tipo_reporte": "Categorías/Configuraciones",
        "fecha_inicio": fecha_inicio_dt.strftime('%d/%m/%Y'), # Devolver en formato dd/mm/yyyy
        "fecha_fin": fecha_fin_dt.strftime('%d/%m/%Y'),       # Devolver en formato dd/mm/yyyy
        "data": resultado_ordenado
    })


# --- Inicio de la Aplicación ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)

