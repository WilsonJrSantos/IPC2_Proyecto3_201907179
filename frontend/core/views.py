import json # Para pasar datos a JS
import requests
from datetime import datetime # Para convertir fechas
from django.shortcuts import render, redirect # Añadir redirect
from django.http import HttpResponse, JsonResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

API_URL = "http://127.0.0.1:5000" # URL de nuestro backend Flask

def format_date_to_api(date_str_iso):
    """Convierte YYYY-MM-DD a dd/mm/yyyy para enviar al API."""
    if not date_str_iso: return ""
    try:
        return datetime.strptime(date_str_iso, '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        return "" # Devuelve vacío si el formato es incorrecto

def get_api_data():
    """ Función auxiliar para obtener los datos del API. """
    try:
        response = requests.get(f"{API_URL}/consultar-datos", timeout=5) # Añadir timeout
        response.raise_for_status() # Lanza excepción si hay error HTTP
        # Asegurarnos que la respuesta es JSON antes de decodificar
        if 'application/json' in response.headers.get('Content-Type', ''):
            return response.json()
        else:
            print(f"Respuesta inesperada del API (no es JSON): {response.text[:200]}")
            return None
    except requests.exceptions.Timeout:
        print("Error: Timeout conectando al API.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error conectando al API: {e}")
        return None # Devuelve None si falla la conexión o hay error
    except json.JSONDecodeError as e:
        print(f"Error decodificando JSON del API: {e}")
        return None

# --- Vistas Principales ---

def home(request):
    """ Vista principal para cargar archivos y ver datos. """
    context = {}
    # Usar sessions para mostrar mensajes después de redireccionar
    if 'message' in request.session:
        context['message'] = request.session.pop('message')

    api_data = get_api_data() # Obtener datos frescos en cada carga GET

    if request.method == 'POST':
        message_text = ''
        message_type = 'error' # Tipo por defecto

        try:
            # Lógica para enviar archivos XML al backend
            if 'config_file' in request.FILES:
                archivo = request.FILES['config_file']
                if not archivo.name.lower().endswith('.xml'):
                     raise ValueError("El archivo de configuración debe ser .xml")
                files = {'archivo': archivo}
                response = requests.post(f"{API_URL}/cargar-configuracion", files=files, timeout=10) # Timeout
                response.raise_for_status()
                message_text = response.json().get('message', 'Archivo de configuración enviado.')
                message_type = response.json().get('status', 'success') # 'success', 'error', 'warning'

            elif 'consumo_file' in request.FILES:
                archivo = request.FILES['consumo_file']
                if not archivo.name.lower().endswith('.xml'):
                     raise ValueError("El archivo de consumo debe ser .xml")
                files = {'archivo': archivo}
                response = requests.post(f"{API_URL}/cargar-consumo", files=files, timeout=10) # Timeout
                response.raise_for_status()
                message_text = response.json().get('message', 'Archivo de consumo enviado.')
                message_type = response.json().get('status', 'success')

            # Guardar mensaje en sesión y redireccionar para evitar reenvío de form
            request.session['message'] = (message_text, message_type)
            return redirect('home') # Redirecciona a la misma vista (método GET)

        except ValueError as ve: # Capturar error de validación de archivo local
             message_text = str(ve)
        except requests.exceptions.Timeout:
            message_text = "Error: Timeout al enviar archivo al API."
        except requests.exceptions.HTTPError as http_err:
             # Errores específicos devueltos por el API (4xx, 5xx)
             try:
                 error_data = http_err.response.json()
                 message_text = f"Error del API ({http_err.response.status_code}): {error_data.get('message', http_err.response.text)}"
             except json.JSONDecodeError:
                 message_text = f"Error HTTP {http_err.response.status_code} del API: {http_err.response.text}"
        except requests.exceptions.RequestException as e:
            # Captura errores de conexión o HTTP del API
            message_text = f"Error de conexión o del API: {e}"
        except Exception as e:
             # Captura otros errores inesperados
             message_text = f"Error inesperado procesando la petición: {e}"

        context['message'] = (message_text, message_type) # Mostrar error si falla antes de redirect


    # Pasar datos del API (si se obtuvieron) al contexto para el GET
    context['api_data'] = api_data
    # Pasar los datos como JSON para la pestaña RAW
    context['api_data_json'] = json.dumps(api_data, indent=2, ensure_ascii=False) if api_data else "{}"

    return render(request, 'core/home.html', context)

def reset_data_view(request):
    """ Vista para llamar al endpoint de reset del backend. """
    context = {'message': None}
    if request.method == 'POST':
        message_text = ''
        message_type = 'error'
        try:
            response = requests.post(f"{API_URL}/reset", timeout=5)
            response.raise_for_status()
            message_text = response.json().get('message', 'Sistema reseteado exitosamente.')
            message_type = 'success'
        except requests.exceptions.Timeout:
            message_text = "Error: Timeout conectando al API para resetear."
        except requests.exceptions.RequestException as e:
            message_text = f"Error al conectar con el API para resetear: {e}"
        except Exception as e:
            message_text = f"Error inesperado: {e}"

        context['message'] = (message_text, message_type)

    return render(request, 'core/reset.html', context)


# --- Vistas de Creación de Datos ---

def creacion_datos_view(request):
    """ Vista para manejar los formularios de creación de nuevos datos. """
    context = {'message': None, 'api_data': None, 'api_data_json': '{}'}
    api_data = get_api_data() # Obtener datos para los dropdowns

    if api_data:
        context['api_data'] = api_data
        # Convertir datos a JSON para usar en JavaScript
        context['api_data_json'] = json.dumps(api_data, ensure_ascii=False)
        # Pasar listas directamente para los <select> del template
        context['clientes'] = api_data.get('clientes', [])
        context['categorias'] = api_data.get('categorias', [])
        # Recolectar todas las configuraciones de todas las categorías
        all_configs = []
        for cat in api_data.get('categorias', []):
           all_configs.extend(cat.get('configuraciones', []))
        context['configuraciones'] = all_configs
        context['recursos'] = api_data.get('recursos', [])


    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        payload = {}
        endpoint = ''
        message_text = ''
        message_type = 'error'

        try:
            # Determinar qué formulario se envió y construir el payload
            if form_type == 'crear_cliente':
                endpoint = '/crear-cliente'
                payload = {
                    'nit': request.POST.get('nit'),
                    'nombre': request.POST.get('nombre'),
                    'usuario': request.POST.get('usuario'),
                    'clave': request.POST.get('clave'),
                    'direccion': request.POST.get('direccion'),
                    'correo': request.POST.get('correo'),
                }
            elif form_type == 'crear_recurso':
                 endpoint = '/crear-recurso'
                 payload = {
                    'id': request.POST.get('rec_id'),
                    'nombre': request.POST.get('rec_nombre'),
                    'abreviatura': request.POST.get('rec_abreviatura'),
                    'metrica': request.POST.get('rec_metrica'),
                    'tipo': request.POST.get('rec_tipo'),
                    'valor_x_hora': request.POST.get('rec_valor'),
                 }
            elif form_type == 'crear_categoria':
                 endpoint = '/crear-categoria'
                 payload = {
                     'id': request.POST.get('cat_id'),
                     'nombre': request.POST.get('cat_nombre'),
                     'descripcion': request.POST.get('cat_descripcion'),
                     'carga_trabajo': request.POST.get('cat_carga'),
                 }
            elif form_type == 'crear_configuracion':
                endpoint = '/crear-configuracion'
                recursos_list = []
                # Recolectar recursos añadidos dinámicamente
                rec_ids = request.POST.getlist('conf_rec_id[]')
                rec_cants = request.POST.getlist('conf_rec_cant[]')
                # print(f"Recursos recibidos: IDs={rec_ids}, Cants={rec_cants}") # Debug
                for rec_id, rec_cant in zip(rec_ids, rec_cants):
                     if rec_id and rec_cant: # Asegurar que ambos tengan valor
                        recursos_list.append({'id_recurso': rec_id, 'cantidad': rec_cant})

                payload = {
                    'id_categoria': request.POST.get('conf_cat_id'),
                    'id': request.POST.get('conf_id'),
                    'nombre': request.POST.get('conf_nombre'),
                    'descripcion': request.POST.get('conf_descripcion'),
                    'recursos': recursos_list
                }
                # print(f"Payload Crear Config: {payload}") # Debug
            elif form_type == 'crear_instancia':
                endpoint = '/crear-instancia'
                # Convertir fecha YYYY-MM-DD a dd/mm/yyyy
                fecha_inicio_api = format_date_to_api(request.POST.get('inst_fecha_inicio'))
                if not fecha_inicio_api and request.POST.get('inst_fecha_inicio'): # Si había fecha pero el formato falló
                     raise ValueError("Formato de fecha de inicio inválido. Use el calendario.")

                payload = {
                    'nit_cliente': request.POST.get('inst_nit_cliente'),
                    'id_instancia': request.POST.get('inst_id'),
                    'id_configuracion': request.POST.get('inst_conf_id'),
                    'nombre': request.POST.get('inst_nombre'),
                    'fecha_inicio': fecha_inicio_api,
                }
            elif form_type == 'cancelar_instancia':
                endpoint = '/cancelar-instancia'
                # Convertir fecha YYYY-MM-DD a dd/mm/yyyy
                fecha_final_api = format_date_to_api(request.POST.get('cancel_fecha_final'))
                if not fecha_final_api and request.POST.get('cancel_fecha_final'):
                     raise ValueError("Formato de fecha final inválido. Use el calendario.")

                payload = {
                     'nit_cliente': request.POST.get('cancel_nit_cliente'),
                     'id_instancia': request.POST.get('cancel_inst_id'),
                     'fecha_final': fecha_final_api,
                }

            # Enviar petición al backend
            if endpoint:
                # print(f"Enviando a {endpoint} payload: {payload}") # Debug
                response = requests.post(f"{API_URL}{endpoint}", json=payload, timeout=10) # Timeout
                # print(f"Respuesta API: Status={response.status_code}, Body={response.text}") # Debug
                response.raise_for_status() # Lanza excepción si hay error HTTP
                message_text = response.json().get('message', 'Operación realizada.')
                # Usar status del API si existe, sino 'success' por defecto
                message_type = response.json().get('status', 'success')
                # Recargar datos frescos del API después de la operación exitosa
                api_data = get_api_data()
                if api_data:
                    context['api_data'] = api_data
                    context['api_data_json'] = json.dumps(api_data, ensure_ascii=False)
                    # Actualizar listas para dropdowns
                    context['clientes'] = api_data.get('clientes', [])
                    context['categorias'] = api_data.get('categorias', [])
                    all_configs = []
                    for cat in api_data.get('categorias', []):
                       all_configs.extend(cat.get('configuraciones', []))
                    context['configuraciones'] = all_configs
                    context['recursos'] = api_data.get('recursos', [])

            else:
                message_text = "Tipo de formulario no reconocido."
                message_type = 'error' # Asegurar que sea error si no se reconoce

        except ValueError as ve: # Capturar errores de conversión de fecha/número locales
             message_text = f"Error en los datos del formulario: {ve}"
             message_type = 'error'
        except requests.exceptions.Timeout:
            message_text = f"Error: Timeout conectando al API ({endpoint})."
            message_type = 'error'
        except requests.exceptions.HTTPError as http_err:
             # Errores específicos devueltos por el API (4xx, 5xx)
             try:
                 error_data = http_err.response.json()
                 message_text = f"Error del API ({http_err.response.status_code}): {error_data.get('message', http_err.response.text)}"
             except json.JSONDecodeError:
                 message_text = f"Error HTTP {http_err.response.status_code} del API: {http_err.response.text}"
             message_type = 'error'
        except requests.exceptions.RequestException as req_err:
             # Errores de conexión
             message_text = f"Error de conexión con el API: {req_err}"
             message_type = 'error'
        except Exception as e:
             # Otros errores inesperados
             message_text = f"Error inesperado: {type(e).__name__} - {e}"
             message_type = 'error'
             import traceback
             traceback.print_exc() # Imprimir traceback completo en consola Django

        context['message'] = (message_text, message_type)


    return render(request, 'core/creacion_datos.html', context)


# --- Vistas de Facturación y Reportes ---

def facturacion_view(request):
    """ Vista para el proceso de facturación y generación de PDF (simplificado). """
    context = {'message': None}
    api_data = get_api_data()
    context['clientes'] = api_data.get('clientes', []) if api_data else []

    if request.method == 'POST':
        nit = request.POST.get('nit')
        # --- CORRECCIÓN: Solo enviar el NIT ---
        payload = {'nit': nit}
        message_text = ''
        message_type = 'error'

        try:
            # 1. Generar la factura en el backend
            response_factura = requests.post(f"{API_URL}/generar-factura", json=payload, timeout=10) # Timeout
            response_factura.raise_for_status()
            factura_data_full = response_factura.json() # Contiene 'status', 'message', 'factura'

            if factura_data_full.get('status') == 'success' and 'factura' in factura_data_full:
                factura_data = factura_data_full['factura'] # Extraer solo los datos de la factura

                # 2. Generar el PDF
                response_pdf = HttpResponse(content_type='application/pdf')
                # Nombre de archivo más descriptivo
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                # Usar ID numérico si existe, sino timestamp
                factura_id_str = str(factura_data.get('id', timestamp))
                filename = f"factura_{factura_data.get('nit_cliente', 'NIT')}_{factura_id_str}.pdf"
                response_pdf['Content-Disposition'] = f'attachment; filename="{filename}"'

                p = canvas.Canvas(response_pdf, pagesize=letter)
                width, height = letter # Ancho y alto de la página

                # --- Estilos Mejorados para PDF ---
                p.setFont("Helvetica-Bold", 16)
                p.drawCentredString(width / 2.0, height - inch, "Factura - Tecnologías Chapinas, S.A.")

                p.setFont("Helvetica", 11)
                margin = inch
                text_y = height - 1.5 * inch

                # Datos del Cliente y Factura
                p.drawString(margin, text_y, f"Factura No: {factura_data.get('id', 'N/A')}")
                text_y -= 20
                p.drawString(margin, text_y, f"Fecha de Emisión: {factura_data.get('fecha_factura', 'N/A')}")
                text_y -= 20
                p.drawString(margin, text_y, f"Cliente: {factura_data.get('nombre_cliente', 'N/A')}")
                text_y -= 20
                p.drawString(margin, text_y, f"NIT: {factura_data.get('nit_cliente', 'N/A')}")

                text_y -= 40 # Espacio antes del detalle

                # Encabezado Detalle
                p.setFont("Helvetica-Bold", 12)
                p.drawString(margin, text_y, "Detalle de Consumos por Instancia")
                text_y -= 15
                p.line(margin, text_y, width - margin, text_y) # Línea separadora
                text_y -= 25

                # Detalle por Instancia
                p.setFont("Helvetica", 10)
                for detalle_inst in factura_data.get('detalles_instancias', []):
                    # Control de Salto de Página
                    needed_height = 60 + len(detalle_inst.get('recursos_costo', [])) * 24 # Altura aprox.
                    if text_y < margin + needed_height:
                         p.showPage()
                         p.setFont("Helvetica", 10)
                         text_y = height - margin # Reiniciar Y en nueva página

                    p.setFont("Helvetica-Bold", 10)
                    p.drawString(margin, text_y, f"Instancia: {detalle_inst.get('nombre_instancia', 'N/A')} (ID: {detalle_inst.get('id_instancia', 'N/A')})")
                    text_y -= 15
                    p.setFont("Helvetica", 9)
                    p.drawString(margin + 15, text_y, f"Configuración: {detalle_inst.get('nombre_configuracion', 'N/A')} (ID: {detalle_inst.get('id_configuracion', 'N/A')})")
                    text_y -= 15
                    p.drawString(margin + 15, text_y, f"Horas Totales Consumidas: {detalle_inst.get('horas_consumidas', 0):.2f} hrs")
                    text_y -= 15

                    # Detalle de Recursos para esta Instancia
                    p.setFont("Helvetica-Oblique", 9)
                    p.drawString(margin + 30, text_y, "Recursos y Costo:")
                    text_y -= 12
                    p.setFont("Helvetica", 8) # Letra más pequeña para detalle recurso
                    for det_rec in detalle_inst.get('recursos_costo', []):
                         linea = (f"- {det_rec.get('nombre_recurso', 'N/A')}: "
                                  f"{det_rec.get('cantidad', 0)} {det_rec.get('metrica', '')} x "
                                  f"{detalle_inst.get('horas_consumidas', 0):.2f} hrs x "
                                  f"Q{det_rec.get('valor_x_hora', 0):.2f}/hr = Q{det_rec.get('subtotal', 0):.2f}")
                         p.drawString(margin + 45, text_y, linea)
                         text_y -= 12
                         if text_y < margin * 0.75: # Salto si ya no cabe (ajustado margen inferior)
                              p.showPage()
                              p.setFont("Helvetica", 8)
                              text_y = height - margin * 0.75

                    p.setFont("Helvetica-Bold", 10)
                    p.drawString(margin + 15, text_y, f"Subtotal Instancia: Q{detalle_inst.get('subtotal_instancia', 0):.2f}")
                    text_y -= 25 # Espacio entre instancias

                # Línea antes del total (solo si hubo detalles)
                detalles_instancias_list = factura_data.get('detalles_instancias', []) # Re-obtener la lista
                if detalles_instancias_list: # Comprobar si la lista no está vacía
                    if text_y < margin * 1.5: # Salto si no cabe el total
                        p.showPage(); text_y = height - margin * 1.5
                    text_y -= 10
                    p.line(margin, text_y, width - margin, text_y)
                    text_y -= 25

                # Total General
                p.setFont("Helvetica-Bold", 14)
                total_str = f"MONTO TOTAL: Q{factura_data.get('monto_total', 0):,.2f}" # Con separador de miles
                p.drawRightString(width - margin, text_y, total_str)

                # Guardar PDF
                p.showPage()
                p.save()
                return response_pdf

            elif factura_data_full.get('status') == 'info':
                # Caso donde no hay consumos pendientes
                message_text = factura_data_full.get('message', 'No hay consumos para facturar.')
                message_type = 'info'
            else:
                 # Otro tipo de respuesta del API que no es 'success' con factura
                 message_text = factura_data_full.get('message', 'Respuesta inesperada del API.')
                 message_type = factura_data_full.get('status', 'warning') # Usar status si existe

        except requests.exceptions.Timeout:
            message_text = "Error: Timeout al generar factura en el API."
            message_type = 'error'
        except requests.exceptions.HTTPError as http_err:
            try:
                error_data = http_err.response.json()
                message_text = f"Error del API ({http_err.response.status_code}): {error_data.get('message', http_err.response.text)}"
            except json.JSONDecodeError:
                message_text = f"Error HTTP {http_err.response.status_code} del API: {http_err.response.text}"
            message_type = 'error'
        except requests.exceptions.RequestException as req_err:
            message_text = f"Error de conexión con el API: {req_err}"
            message_type = 'error'
        except Exception as e:
            message_text = f"Error inesperado al generar PDF: {type(e).__name__} - {e}"
            message_type = 'error'
            import traceback
            traceback.print_exc() # Imprimir traceback completo en consola Django


        context['message'] = (message_text, message_type)


    return render(request, 'core/facturacion.html', context)


def reportes_view(request):
    """ Vista para generar y mostrar reportes de ventas. """
    context = {'message': None, 'reporte_data': None, 'reporte_titulo': '', 'form_data': {}, 'total_general': 0.0}
    endpoint_map = {
        'recursos': '/reporte/ventas-recurso',
        'categorias': '/reporte/ventas-categoria',
    }

    if request.method == 'POST': # Cambiado a POST para recibir datos del form
        report_type = request.POST.get('report_type')
        fecha_inicio_iso = request.POST.get('fecha_inicio') # YYYY-MM-DD
        fecha_fin_iso = request.POST.get('fecha_fin')       # YYYY-MM-DD

        context['form_data'] = {'report_type': report_type, 'fecha_inicio': fecha_inicio_iso, 'fecha_fin': fecha_fin_iso} # Guardar para rellenar form

        endpoint = endpoint_map.get(report_type)
        message_text = ''
        message_type = 'error'

        if not endpoint:
            message_text = "Tipo de reporte no válido."
        elif not fecha_inicio_iso or not fecha_fin_iso:
             message_text = "Debe seleccionar fecha de inicio y fin."
        else:
            try:
                # Enviar fechas como parámetros GET al API
                params = {'fecha_inicio': fecha_inicio_iso, 'fecha_fin': fecha_fin_iso}
                response = requests.get(f"{API_URL}{endpoint}", params=params, timeout=10) # Usar GET y Timeout
                response.raise_for_status()
                report_json = response.json()

                if report_json.get('status') == 'success':
                    # --- CORRECCIÓN: Usar 'data' en lugar de 'reporte' ---
                    reporte_data_dict = report_json.get('data', {})
                    # ---------------------------------------------------
                    # Ordenar los datos por valor descendente para mostrarlos
                    # Convertir a lista de tuplas (nombre, valor) para ordenar y pasar al template
                    context['reporte_data'] = sorted(reporte_data_dict.items(), key=lambda item: item[1], reverse=True)

                    # Crear título más descriptivo
                    tipo_titulo = report_json.get('tipo_reporte', 'Desconocido')
                    context['reporte_titulo'] = f"Ingresos por {tipo_titulo} ({report_json.get('fecha_inicio', '?')} - {report_json.get('fecha_fin', '?')})"

                    # Calcular total general
                    total_general = sum(reporte_data_dict.values())
                    context['total_general'] = round(total_general, 2)

                    message_text = "Reporte generado exitosamente."
                    message_type = 'success'
                else:
                    message_text = report_json.get('message', 'Error desconocido del API al generar reporte.')
                    message_type = report_json.get('status', 'error')

            except requests.exceptions.Timeout:
                message_text = f"Error: Timeout conectando al API ({endpoint})."
                message_type = 'error'
            except requests.exceptions.HTTPError as http_err:
                try:
                    error_data = http_err.response.json()
                    message_text = f"Error del API ({http_err.response.status_code}): {error_data.get('message', http_err.response.text)}"
                except json.JSONDecodeError:
                    message_text = f"Error HTTP {http_err.response.status_code} del API: {http_err.response.text}"
                message_type = 'error'
            except requests.exceptions.RequestException as req_err:
                 message_text = f"Error de conexión con el API: {req_err}"
                 message_type = 'error'
            except Exception as e:
                 message_text = f"Error inesperado: {type(e).__name__} - {e}"
                 message_type = 'error'
                 import traceback
                 traceback.print_exc()

        context['message'] = (message_text, message_type)

    # Si es GET, solo renderiza el formulario vacío
    return render(request, 'core/reportes.html', context)


def ayuda_view(request):
    """ Vista para la página de Ayuda. """
    context = {
        'student_name': "Tu Nombre Completo Aquí", # Reemplaza con tus datos
        'student_id': "Tu Carnet Aquí"           # Reemplaza con tus datos
    }
    return render(request, 'core/ayuda.html', context)

