from django.urls import path
from . import views

app_name = 'reservas'

urlpatterns = [
    # Carrito de compras
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/agregar/<int:servicio_id>/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('carrito/actualizar/<int:item_id>/', views.actualizar_item_carrito, name='actualizar_item_carrito'),
    path('carrito/eliminar/<int:item_id>/', views.eliminar_item_carrito, name='eliminar_item_carrito'),
    path('carrito/vaciar/', views.vaciar_carrito, name='vaciar_carrito'),
    path('carrito/count/', views.obtener_carrito_count, name='carrito_count'),
    path('proveedor/reservas/count/', views.obtener_reservas_pendientes_count, name='reservas_pendientes_count'),
    
    # Reservas - Turistas
    path('confirmar/', views.confirmar_reserva, name='confirmar_reserva'),
    path('mis-reservas/', views.mis_reservas, name='mis_reservas'),
    path('detalle/<int:reserva_id>/', views.detalle_reserva, name='detalle_reserva'),
    path('cancelar/<int:reserva_id>/', views.cancelar_reserva, name='cancelar_reserva'),
    
    # Reservas - Proveedores
    path('proveedor/reservas/', views.reservas_proveedor, name='reservas_proveedor'),
    path('proveedor/detalle/<int:reserva_id>/', views.detalle_reserva, name='detalle_reserva_proveedor'),  # ⬅️ AGREGAR ESTA LÍNEA
    path('proveedor/confirmar/<int:reserva_id>/', views.confirmar_reserva_proveedor, name='confirmar_reserva_proveedor'),
    path('proveedor/completar/<int:reserva_id>/', views.completar_reserva_proveedor, name='completar_reserva_proveedor'),
    path('estado/<int:reserva_id>/', views.verificar_estado_reserva, name='verificar_estado_reserva'),
    
    # APIs AJAX para estadísticas (Chatbot)
    path('api/estadisticas/', views.estadisticas_reservas_ajax, name='estadisticas_ajax'),
    path('api/mis-estadisticas/', views.mis_estadisticas_ajax, name='mis_estadisticas_ajax'),
]