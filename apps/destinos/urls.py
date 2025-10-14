from django.urls import path
from . import views

app_name = 'destinos'

urlpatterns = [
    # ===========================
    # Rutas públicas
    # ===========================
    path('', views.lista_destinos, name='lista_destinos'),
    path('region/<str:region>/', views.destinos_por_region, name='destinos_por_region'),
    path('destacados/', views.destinos_destacados, name='destinos_destacados'),
    path('mapa/', views.mapa_destinos, name='mapa_destinos'),
    path('detalle/<slug:slug>/', views.detalle_destino, name='detalle_destino'),

    # ===========================
    # Funcionalidades AJAX
    # ===========================
    path('busqueda-ajax/', views.busqueda_ajax, name='busqueda_ajax'),
    path('agregar-favorito/<int:destino_id>/', views.agregar_favorito, name='agregar_favorito'),
    path('estadisticas/<int:destino_id>/', views.estadisticas_destino, name='estadisticas_destino'),

    # ===========================
    # Admin Routes (solo administradores)
    # ===========================
    path('crear/', views.crear_destino, name='crear_destino'),
    path('editar/<int:destino_id>/', views.editar_destino, name='editar_destino'),
    path('eliminar/<int:destino_id>/', views.eliminar_destino, name='eliminar_destino'),
]
