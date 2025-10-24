from django.shortcuts import render, redirect
import requests
import json
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from datetime import datetime

API_URL = "http://127.0.0.1:5000"

def format_date_to_xml(date_str_iso):
    """Convierte yyyy-mm-dd (de input type=date) a dd/mm/yyyy (para el API/XML)"""
    if not date_str_iso: return ""
    try:
        return datetime.strptime(date_str_iso, '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError: return date_str_iso

def home(request):
    """ Vista principal para cargar archivos y ver datos. """
    context = {}
    message = None
    
    if request.method == 'POST':
        try:
            if 'config_file' in request.FILES:
                files = {'archivo': request.FILES['config_file']}
                response = requests.post(f"{API_URL}/cargar-configuracion", files=files)
                response.raise_for_status()
                message_text = response.json().get('message', 'Éxito')
                message = (message_text, 'success')
            elif 'consumo_file' in request.FILES:
                files = {'archivo': request.FILES['consumo_file']}
                response = requests.post(f"{API_URL}/cargar-consumo", files=files)
                response.raise_for_status()
                message_text = response.json().get('message', 'Éxito')
                message = (message_text, 'success')
        except requests.exceptions.RequestException as e:
            try:
                error_data = e.response.json()
                message_text = error_data.get('message', str(e))
            except: message_text = f"Error de conexión: {e}"
            message = (message_text, 'error')
        
        if message: request.session['message'] = message
        return redirect('home')

    if 'message' in request.session: context['message'] = request.session.pop('message')

    try:
        response = requests.get(f"{API_URL}/consultar-datos")
        response.raise_for_status()
        context['datos'] = response.json()
    except requests.exceptions.RequestException as e:
        context['datos_error'] = f"No se pudieron cargar los datos del API: {e}"

    return render(request, 'core/home.html', context)

def reset_data(request):
    """ Vista para llamar al endpoint de reset del backend. """
    message = None
    if request.method == 'POST':
        try:
            response = requests.post(f"{API_URL}/reset")
            response.raise_for_status()
            message_text = response.json().get('message', 'Sistema reseteado.')
            message = (message_text, 'success')
        except requests.exceptions.RequestException as e:
            message_text = f"Error al resetear: {e}"
            message = (message_text, 'error')
    
    return render(request, 'core/reset.html', {'message': message})

# --- INICIO VISTA MODIFICADA ---
def creacion_datos_view(request):
    """ Vista para manejar todos los formularios de creación de datos. """
    context = {}

    def get_dropdown_data():
        """Obtiene datos del API para poblar los <select>"""
        try:
            response = requests.get(f"{API_URL}/consultar-datos")
            response.raise_for_status()
            data = response.json()
            context['full_data_json'] = json.dumps(data) 
            context['clientes'] = data.get('clientes', [])
            context['categorias'] = data.get('categorias', [])
            
            all_configs = []
            for cat in data.get('categorias', []):
                all_configs.extend(cat.get('configuraciones', []))
            context['configuraciones'] = all_configs
            
            # --- NUEVO: Pasar recursos disponibles ---
            context['recursos'] = data.get('recursos', [])
            # --- FIN NUEVO ---

        except requests.exceptions.RequestException as e:
            context['message'] = (f"Error cargando datos para los selectores: {e}", 'error')
            context['clientes'], context['categorias'], context['configuraciones'], context['recursos'] = [], [], [], []
            context['full_data_json'] = "{}"

    get_dropdown_data() # Cargar datos para los dropdowns

    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        payload = {key: val for key, val in request.POST.items() if key not in ['csrfmiddlewaretoken', 'form_type'] and val and not key.startswith('recurso_id_') and not key.startswith('recurso_cantidad_')}
        endpoint = ''

        if form_type == 'crear_cliente': endpoint = '/crear-cliente'
        elif form_type == 'crear_recurso': endpoint = '/crear-recurso'
        elif form_type == 'crear_categoria': endpoint = '/crear-categoria'
        
        # --- NUEVO: Lógica para recolectar recursos dinámicos ---
        elif form_type == 'crear_configuracion':
            endpoint = '/crear-configuracion'
            recursos_list = []
            # Busca campos que empiecen con 'recurso_id_'
            recurso_keys = [key for key in request.POST if key.startswith('recurso_id_')]
            for key in recurso_keys:
                index = key.split('_')[-1] # Obtiene el índice (ej: '0', '1')
                id_recurso = request.POST.get(f'recurso_id_{index}')
                cantidad = request.POST.get(f'recurso_cantidad_{index}')
                if id_recurso and cantidad:
                    recursos_list.append({'id_recurso': id_recurso, 'cantidad': cantidad})
            payload['recursos'] = recursos_list # Añade la lista al payload
        # --- FIN NUEVO ---
        
        elif form_type == 'crear_instancia':
            endpoint = '/crear-instancia'
            payload['fecha_inicio'] = format_date_to_xml(payload.get('fecha_inicio'))
        
        elif form_type == 'cancelar_instancia':
            endpoint = '/cancelar-instancia'
            payload['fecha_final'] = format_date_to_xml(payload.get('fecha_final'))

        if not endpoint:
            context['message'] = ("Tipo de formulario desconocido.", 'error')
            get_dropdown_data()
            return render(request, 'core/creacion_datos.html', context)

        try:
            response = requests.post(f"{API_URL}{endpoint}", json=payload)
            response.raise_for_status()
            message_text = response.json().get('message', 'Operación exitosa.')
            context['message'] = (message_text, 'success')
        except requests.exceptions.RequestException as e:
            try:
                error_data = e.response.json()
                message_text = error_data.get('message', str(e))
            except: message_text = f"Error en la operación: {e}"
            context['message'] = (message_text, 'error')

        get_dropdown_data() # Recargar datos para los dropdowns
        return render(request, 'core/creacion_datos.html', context)

    return render(request, 'core/creacion_datos.html', context)
# --- FIN VISTA MODIFICADA ---


def facturacion_view(request):
    """ Vista para el proceso de facturación y generación de PDF. """
    context = {}
    try:
        response = requests.get(f"{API_URL}/consultar-datos")
        response.raise_for_status()
        context['clientes'] = response.json().get('clientes', [])
    except requests.exceptions.RequestException as e:
        context['message'] = (f"Error cargando clientes: {e}", 'error')
        context['clientes'] = []

    if request.method == 'POST':
        nit = request.POST.get('nit')
        fecha_inicio_iso = request.POST.get('fecha_inicio')
        fecha_fin_iso = request.POST.get('fecha_fin')
        fecha_inicio = format_date_to_xml(fecha_inicio_iso)
        fecha_fin = format_date_to_xml(fecha_fin_iso)

        try:
            payload = {'nit': nit, 'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin}
            response_factura = requests.post(f"{API_URL}/generar-factura", json=payload)
            response_factura.raise_for_status()
            factura_data = response_factura.json()

            if factura_data.get('status') == 'success':
                # --- Generación PDF Detallada ---
                response_pdf = HttpResponse(content_type='application/pdf')
                response_pdf['Content-Disposition'] = f'attachment; filename="factura_{nit}_{factura_data.get("id", "000")}.pdf"'
                p = canvas.Canvas(response_pdf, pagesize=letter)
                width, height = letter
                
                p.setFont("Helvetica-Bold", 16)
                p.drawCentredString(width / 2.0, height - 50, "Factura - Tecnologías Chapinas, S.A.")
                
                p.setFont("Helvetica", 10)
                p.drawString(inch, height - 90, f"Cliente NIT: {factura_data.get('nit_cliente')}")
                p.drawString(inch, height - 105, f"Cliente Nombre: {factura_data.get('nombre_cliente', 'N/A')}")
                p.drawRightString(width - inch, height - 90, f"No. Factura: {factura_data.get('id', 'N/A')}")
                p.drawRightString(width - inch, height - 105, f"Fecha Emisión: {factura_data.get('fecha_factura', 'N/A')}")
                
                p.setFont("Helvetica-Bold", 12)
                p.drawRightString(width - inch, height - 135, f"Monto Total: Q{factura_data.get('monto_total', 0.0):.2f}")
                p.line(inch, height - 150, width - inch, height - 150)
                
                y = height - 175
                p.setFont("Helvetica-Bold", 11)
                p.drawString(inch, y, "Detalle de Consumos por Instancia")
                y -= 25
                p.setFont("Helvetica", 9)
                
                for inst_detalle in factura_data.get('detalles_instancias', []):
                    if y < inch * 1.5: # Salto de página preventivo
                        p.showPage(); y = height - 50; p.setFont("Helvetica", 9)

                    p.setFont("Helvetica-Bold", 10)
                    p.drawString(inch, y, f"Instancia: {inst_detalle.get('nombre_instancia')} (ID: {inst_detalle.get('id_instancia')})")
                    p.drawRightString(width - inch, y, f"Subtotal Instancia: Q{inst_detalle.get('subtotal_instancia', 0.0):.2f}")
                    y -= 15
                    
                    p.setFont("Helvetica", 9)
                    p.drawString(inch + 20, y, f"Total Horas Consumidas: {inst_detalle.get('horas_consumidas', 0.0):.2f}h")
                    p.drawString(inch + 200, y, f"Configuración: {inst_detalle.get('nombre_configuracion')} (ID: {inst_detalle.get('id_configuracion')})")
                    y -= 15
                    
                    p.setFont("Helvetica-Oblique", 9)
                    p.drawString(inch + 20, y, "Recursos Utilizados y Cálculo:")
                    y -= 12

                    for rec_detalle in inst_detalle.get('recursos_costo', []):
                        if y < inch: p.showPage(); y = height - 50; p.setFont("Helvetica", 9) # Salto si no cabe el recurso
                        linea1 = f"- {rec_detalle.get('nombre_recurso')} (ID:{rec_detalle.get('id_recurso')})"
                        linea2 = f"  ({rec_detalle.get('cantidad')} {rec_detalle.get('metrica')} x Q{rec_detalle.get('valor_x_hora'):.2f}/h x {inst_detalle.get('horas_consumidas', 0.0):.2f}h)"
                        p.drawString(inch + 35, y, linea1)
                        p.drawRightString(width - inch, y, f"= Q{rec_detalle.get('subtotal', 0.0):.2f}")
                        y -= 12
                        p.drawString(inch + 35, y, linea2)
                        y -= 12
                    
                    y -= 10 # Espacio entre instancias

                p.showPage(); p.save()
                return response_pdf
                # --- Fin Generación PDF ---
            else:
                context['message'] = (factura_data.get('message', 'Error'), 'error' if factura_data.get('status') == 'error' else 'success')

        except requests.exceptions.RequestException as e:
            try: error_data = e.response.json(); message_text = error_data.get('message', str(e))
            except: message_text = f"Error al generar factura: {e}"
            context['message'] = (message_text, 'error')

    return render(request, 'core/facturacion.html', context)

def reportes_view(request):
    """ Vista para generar reportes de ventas. """
    context = {}
    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        fecha_inicio_iso = request.POST.get('fecha_inicio')
        fecha_fin_iso = request.POST.get('fecha_fin')
        fecha_inicio = format_date_to_xml(fecha_inicio_iso)
        fecha_fin = format_date_to_xml(fecha_fin_iso)

        context['form_data'] = {'report_type': report_type, 'fecha_inicio': fecha_inicio_iso, 'fecha_fin': fecha_fin_iso}

        endpoint, titulo = ('', '')
        if report_type == 'recursos':
            endpoint, titulo = ('/reporte/ventas-recurso', "Ingresos por Recurso")
        elif report_type == 'categorias':
            endpoint, titulo = ('/reporte/ventas-categoria', "Ingresos por Categoría/Configuración")
        context['reporte_titulo'] = titulo
        
        if endpoint:
            try:
                payload = {'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin}
                response = requests.post(f"{API_URL}{endpoint}", json=payload)
                response.raise_for_status()
                reporte_data_raw = response.json().get('reporte', {})
                sorted_data = sorted(reporte_data_raw.items(), key=lambda item: item[1], reverse=True)
                total_general = sum(reporte_data_raw.values())
                context['reporte_data'] = sorted_data
                context['total_general'] = total_general
            except requests.exceptions.RequestException as e:
                try: error_data = e.response.json(); message_text = error_data.get('message', str(e))
                except: message_text = f"Error al generar reporte: {e}"
                context['message'] = (message_text, 'error')

    return render(request, 'core/reportes.html', context)

def ayuda_view(request):
    """ Vista para la página de Ayuda. """
    # Puedes cambiar estos datos directamente o leerlos de un archivo/configuración
    context = {
        'student_name': 'Wilson Javier Antonio Juarez', # Reemplaza
        'student_id': '201907179' # Reemplaza
    }
    return render(request, 'core/ayuda.html', context)

