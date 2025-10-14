# urls.py (app usuarios)
from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('listar/', views.listar_usuarios_view, name='listar_usuarios'),
    path('cambiar-rol/<int:usuario_id>/', views.cambiar_rol_view, name='cambiar_rol'),
    path('toggle-estado/<int:usuario_id>/', views.toggle_usuario_estado_view, name='toggle_estado'),
]