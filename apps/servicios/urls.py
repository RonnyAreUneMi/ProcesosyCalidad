from django.urls import path
from . import views

app_name = 'servicios'

urlpatterns = [
    # Listado y búsqueda
    path('', views.listar_servicios, name='listar_servicios'),
    path('<int:servicio_id>/', views.detalle_servicio, name='detalle_servicio'),
    path('tipo/<str:tipo>/', views.servicios_por_tipo, name='servicios_por_tipo'),
    
    # Gestión de servicios (Proveedores/Administradores)
    path('crear/', views.crear_servicio, name='crear_servicio'),
    path('<int:servicio_id>/editar/', views.editar_servicio, name='editar_servicio'),
    path('<int:servicio_id>/eliminar/', views.eliminar_servicio, name='eliminar_servicio'),
    path('mis-servicios/', views.mis_servicios, name='mis_servicios'),
    
    # Gestión de imágenes (AJAX)
    path('imagen/<int:imagen_id>/eliminar/', views.eliminar_imagen, name='eliminar_imagen'),
    path('imagen/<int:imagen_id>/principal/', views.marcar_imagen_principal, name='marcar_imagen_principal'),
    
    # APIs para búsqueda y chatbot (AJAX)
    path('api/buscar/', views.buscar_servicios_ajax, name='buscar_servicios_ajax'),
    path('api/estadisticas/', views.estadisticas_servicios_ajax, name='estadisticas_servicios_ajax'),
    path('api/comparar/', views.comparar_servicios_ajax, name='comparar_servicios_ajax'),
    path('api/recomendaciones/', views.recomendaciones_ajax, name='recomendaciones_ajax'),
]