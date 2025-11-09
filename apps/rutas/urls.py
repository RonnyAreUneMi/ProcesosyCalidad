from django.urls import path
from . import views

app_name = 'rutas'

urlpatterns = [
    # Vista principal
    path('crear/', views.crear_ruta, name='crear_ruta'),
    
    # AJAX endpoints
    path('ajax/buscar/', views.buscar_rutas_ajax, name='buscar_rutas_ajax'),
    path('ajax/puntos/', views.puntos_transporte_ajax, name='puntos_transporte_ajax'),
    path('ajax/datos-completos/', views.datos_transporte_completos_ajax, name='datos_transporte_ajax'),
    path('ajax/servicios/', views.servicios_transporte_ajax, name='servicios_transporte_ajax'),
    path('ajax/destinos-coordenadas/', views.destinos_con_coordenadas_ajax, name='destinos_coordenadas_ajax'),
]