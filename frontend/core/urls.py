from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('creacion-datos/', views.creacion_datos_view, name='creacion_datos'),
    path('reset/', views.reset_data, name='reset_data'),
    # --- LÍNEA CORREGIDA ---
    # El nombre de la vista es 'facturacion_view', no 'facturacion'
    path('facturacion/', views.facturacion_view, name='facturacion'),
    # --- FIN DE LA CORRECCIÓN ---
    path('reportes/', views.reportes_view, name='reportes'),
    path('ayuda/', views.ayuda_view, name='ayuda'),
]

