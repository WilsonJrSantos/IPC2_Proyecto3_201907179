from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    # --- CORRECCIÓN: Usar el nombre de función correcto de views.py ---
    path('reset/', views.reset_data_view, name='reset_data'),
    path('creacion-datos/', views.creacion_datos_view, name='creacion_datos'),
    path('facturacion/', views.facturacion_view, name='facturacion'),
    path('reportes/', views.reportes_view, name='reportes'),
    path('ayuda/', views.ayuda_view, name='ayuda'),
]

