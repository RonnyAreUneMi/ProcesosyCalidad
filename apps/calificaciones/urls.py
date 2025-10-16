from django.urls import path
from . import views

app_name = 'calificaciones'

urlpatterns = [
    # Crear, editar, eliminar calificaciones (usuarios)
    path('crear/<int:servicio_id>/', views.crear_calificacion, name='crear_calificacion'),
    path('editar/<int:calificacion_id>/', views.editar_calificacion, name='editar_calificacion'),
    path('eliminar/<int:calificacion_id>/', views.eliminar_calificacion, name='eliminar_calificacion'),
    
    # Vista personal del usuario
    path('mis-calificaciones/', views.mis_calificaciones, name='mis_calificaciones'),
    
    # Panel del proveedor
    path('proveedor/', views.calificaciones_proveedor, name='calificaciones_proveedor'),
    path('responder/<int:calificacion_id>/', views.responder_calificacion, name='responder_calificacion'),
    path('respuesta/editar/<int:respuesta_id>/', views.editar_respuesta, name='editar_respuesta'),
    
    # Panel de moderación (administrador)
    path('moderar/', views.moderar_calificaciones, name='moderar_calificaciones'),
    path('moderar/aprobar/<int:calificacion_id>/', views.aprobar_calificacion, name='aprobar_calificacion'),
    path('moderar/rechazar/<int:calificacion_id>/', views.rechazar_calificacion, name='rechazar_calificacion'),
    
    # APIs AJAX para chatbot y estadísticas
    path('api/estadisticas/', views.estadisticas_calificaciones_ajax, name='estadisticas_calificaciones_ajax'),
    path('api/servicio/<int:servicio_id>/', views.calificaciones_por_servicio_ajax, name='calificaciones_por_servicio_ajax'),
]