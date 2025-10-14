from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
    # Autenticación
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # Perfil
    path('perfil/', views.perfil_view, name='perfil'),
    
    # Administración de usuarios (solo administradores)
    path('admin/usuarios/', views.listar_usuarios_view, name='listar_usuarios'),
    path('admin/usuarios/<int:usuario_id>/cambiar-rol/', views.cambiar_rol_view, name='cambiar_rol'),
    path('admin/usuarios/<int:usuario_id>/toggle-estado/', views.toggle_usuario_estado_view, name='toggle_estado'),
    path('admin/cambiar-rol/', views.cambiar_rol_view, name='cambiar_rol_form'),
]