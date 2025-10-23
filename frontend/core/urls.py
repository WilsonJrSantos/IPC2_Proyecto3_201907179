from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('reset/', views.reset_data, name='reset_data'),
]