from django.shortcuts import render
import requests

API_URL = "http://127.0.0.1:5000" # URL de nuestro backend Flask

def home(request):
    """ Vista principal para cargar archivos y ver datos. """
    context = {}
    
    if request.method == 'POST':
        # Lógica para enviar archivos al backend
        if 'config_file' in request.FILES:
            files = {'archivo': request.FILES['config_file']}
            try:
                response = requests.post(f"{API_URL}/cargar-configuracion", files=files)
                response.raise_for_status()
                context['config_message'] = response.json().get('message', 'Éxito')
            except requests.exceptions.RequestException as e:
                context['config_message'] = f"Error de conexión: {e}"

        elif 'consumo_file' in request.FILES:
            files = {'archivo': request.FILES['consumo_file']}
            try:
                response = requests.post(f"{API_URL}/cargar-consumo", files=files)
                response.raise_for_status()
                context['consumo_message'] = response.json().get('message', 'Éxito')
            except requests.exceptions.RequestException as e:
                context['consumo_message'] = f"Error de conexión: {e}"

    # Lógica para consultar datos
    try:
        response = requests.get(f"{API_URL}/consultar-datos")
        response.raise_for_status()
        context['datos'] = response.json()
    except requests.exceptions.RequestException as e:
        context['datos_error'] = f"No se pudieron cargar los datos del API: {e}"

    return render(request, 'core/home.html', context)

def reset_data(request):
    """ Vista para llamar al endpoint de reset del backend. """
    message = ''
    if request.method == 'POST':
        try:
            response = requests.post(f"{API_URL}/reset")
            response.raise_for_status()
            message = response.json().get('message', 'Sistema reseteado.')
        except requests.exceptions.RequestException as e:
            message = f"Error al resetear: {e}"
    
    return render(request, 'core/reset.html', {'message': message})