# apps/destinos/urls.py
from django.urls import path
from . import views

app_name = 'destinos'

urlpatterns = [
    # Vistas públicas
    path('', views.lista_destinos, name='lista_destinos'),
    path('destacados/', views.destinos_destacados, name='destinos_destacados'),
    path('mapa/', views.mapa_destinos, name='mapa_destinos'),
    path('region/<str:region>/', views.destinos_por_region, name='destinos_por_region'),
    path('<slug:slug>/', views.detalle_destino, name='detalle_destino'),
    
    # Vistas de administración
    path('admin/crear/', views.crear_destino, name='crear_destino'),
    path('admin/<int:destino_id>/editar/', views.editar_destino, name='editar_destino'),
    path('admin/<int:destino_id>/eliminar/', views.eliminar_destino, name='eliminar_destino'),
    
    # Vistas AJAX para chatbot y búsqueda
    path('ajax/busqueda/', views.busqueda_ajax, name='busqueda_ajax'),
    path('ajax/estadisticas/', views.estadisticas_destinos_ajax, name='estadisticas_destinos_ajax'),
    path('ajax/region/<str:region>/', views.destinos_por_region_ajax, name='destinos_por_region_ajax'),
    path('ajax/estadisticas/<int:destino_id>/', views.estadisticas_destino, name='estadisticas_destino'),
    
    # Favoritos
    path('<int:destino_id>/favorito/', views.agregar_favorito, name='agregar_favorito'),
]