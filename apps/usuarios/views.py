from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from .forms import LoginForm, RegisterForm, CambioRolForm, PerfilUsuarioForm
from .models import Usuario, Rol


def es_administrador(user):
    """
    Función helper para verificar si el usuario es administrador
    """
    return user.is_authenticated and user.es_administrador()


@csrf_protect
@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    Vista de inicio de sesión
    RF-001: Autenticación de usuarios
    """
    # Redirigir si ya está autenticado
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            correo = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            # Autenticar usuario
            user = authenticate(request, username=correo, password=password)
            
            if user is not None:
                if user.is_active:
                    login(request, user)
                    
                    # Actualizar último acceso
                    user.actualizar_ultimo_acceso()
                    
                    # Mensaje de bienvenida personalizado según rol
                    rol_display = user.rol.get_nombre_display() if user.rol else 'Usuario'
                    messages.success(
                        request,
                        f'Bienvenido/a {user.nombre}. '
                        f'Has iniciado sesión como {rol_display}.'
                    )
                    
                    # Redirigir según el parámetro 'next' o a home
                    next_page = request.GET.get('next', 'home')
                    return redirect(next_page)
                else:
                    messages.error(
                        request,
                        'Tu cuenta ha sido desactivada. '
                        'Contacta al administrador.'
                    )
            else:
                messages.error(
                    request,
                    'Correo o contraseña incorrectos. '
                    'Por favor, inténtalo de nuevo.'
                )
        else:
            messages.error(
                request,
                'Por favor, corrige los errores en el formulario.'
            )
    else:
        form = LoginForm()
    
    context = {
        'form': form,
        'title': 'Iniciar Sesión - Ecuador Turismo'
    }
    return render(request, 'usuarios/login.html', context)


@csrf_protect
@require_http_methods(["GET", "POST"])
def register_view(request):
    """
    Vista de registro de nuevos usuarios
    RF-001: Registro de usuario con validación y asignación de roles
    """
    # Redirigir si ya está autenticado
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Crear usuario
                    user = form.save()
                    
                    # Autenticar y loguear automáticamente
                    login(request, user)
                    
                    # Mensaje de éxito
                    rol_display = user.rol.get_nombre_display() if user.rol else 'Turista'
                    messages.success(
                        request,
                        f'Cuenta creada exitosamente. '
                        f'Bienvenido/a {user.nombre}. '
                        f'Tu cuenta ha sido registrada como {rol_display}.'
                    )
                    
                    return redirect('home')
                    
            except Exception as e:
                messages.error(
                    request,
                    f'Error al crear la cuenta: {str(e)}. '
                    'Por favor, inténtalo de nuevo.'
                )
        else:
            # Mostrar errores específicos del formulario
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        form = RegisterForm()
    
    context = {
        'form': form,
        'title': 'Crear Cuenta - Ecuador Turismo',
        'roles_disponibles': Rol.objects.filter(activo=True).exclude(
            nombre=Rol.ADMINISTRADOR
        )
    }
    return render(request, 'usuarios/register.html', context)


@login_required
def logout_view(request):
    """
    Vista de cierre de sesión
    """
    nombre_usuario = request.user.nombre
    logout(request)
    messages.info(
        request,
        f'Hasta pronto, {nombre_usuario}. Has cerrado sesión exitosamente.'
    )
    return redirect('home')


@login_required
@require_http_methods(["GET", "POST"])
def perfil_view(request):
    """
    Vista de perfil de usuario
    Permite editar información personal
    """
    if request.method == 'POST':
        form = PerfilUsuarioForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Perfil actualizado exitosamente.'
            )
            return redirect('usuarios:perfil')
        else:
            messages.error(
                request,
                'Error al actualizar el perfil. Verifica los datos.'
            )
    else:
        form = PerfilUsuarioForm(instance=request.user)
    
    context = {
        'form': form,
        'title': 'Mi Perfil',
        'user': request.user,
        'permisos': request.user.get_permisos()
    }
    return render(request, 'usuarios/perfil.html', context)


@login_required
@user_passes_test(es_administrador, login_url='home')
@require_http_methods(["GET", "POST"])
def cambiar_rol_view(request, usuario_id=None):
    """
    Vista para cambiar el rol de un usuario
    Solo accesible por administradores
    RF-001: Validación para cambiar rol
    """
    if request.method == 'POST':
        form = CambioRolForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    usuario = form.cleaned_data['usuario']
                    nuevo_rol = form.cleaned_data['nuevo_rol']
                    motivo = form.cleaned_data.get('motivo', '')
                    
                    # Guardar rol anterior para registro
                    rol_anterior = usuario.rol
                    
                    # Cambiar rol
                    usuario.rol = nuevo_rol
                    usuario.save()
                    
                    # Registrar cambio (opcional: crear modelo de auditoría)
                    messages.success(
                        request,
                        f'Rol cambiado exitosamente. '
                        f'{usuario.nombre} ahora es {nuevo_rol.get_nombre_display()}.'
                    )
                    
                    return redirect('usuarios:listar_usuarios')
                    
            except Exception as e:
                messages.error(
                    request,
                    f'Error al cambiar el rol: {str(e)}'
                )
        else:
            messages.error(
                request,
                'Error en el formulario. Verifica los datos.'
            )
    else:
        initial = {}
        if usuario_id:
            try:
                usuario = Usuario.objects.get(pk=usuario_id)
                initial['usuario'] = usuario
            except Usuario.DoesNotExist:
                messages.error(request, 'Usuario no encontrado.')
                return redirect('usuarios:listar_usuarios')
        
        form = CambioRolForm(initial=initial)
    
    context = {
        'form': form,
        'title': 'Cambiar Rol de Usuario',
    }
    return render(request, 'usuarios/cambiar_rol.html', context)


@login_required
@user_passes_test(es_administrador, login_url='home')
def listar_usuarios_view(request):
    """
    Vista para listar todos los usuarios
    Solo accesible por administradores
    RF-008: Panel de administración
    """
    # Filtros opcionales
    rol_filtro = request.GET.get('rol', '')
    busqueda = request.GET.get('q', '')
    
    usuarios = Usuario.objects.select_related('rol').all()
    
    if rol_filtro:
        usuarios = usuarios.filter(rol__nombre=rol_filtro)
    
    if busqueda:
        usuarios = usuarios.filter(
            nombre__icontains=busqueda
        ) | usuarios.filter(
            correo__icontains=busqueda
        )
    
    # Estadísticas
    total_usuarios = Usuario.objects.count()
    usuarios_por_rol = {}
    for rol in Rol.objects.all():
        usuarios_por_rol[rol.get_nombre_display()] = Usuario.objects.filter(
            rol=rol
        ).count()
    
    context = {
        'title': 'Gestión de Usuarios',
        'usuarios': usuarios,
        'roles': Rol.objects.filter(activo=True),
        'total_usuarios': total_usuarios,
        'usuarios_por_rol': usuarios_por_rol,
        'rol_filtro': rol_filtro,
        'busqueda': busqueda,
    }
    return render(request, 'usuarios/listar_usuarios.html', context)


@login_required
@user_passes_test(es_administrador, login_url='home')
@require_http_methods(["POST"])
def toggle_usuario_estado_view(request, usuario_id):
    """
    Vista para activar/desactivar un usuario
    Solo accesible por administradores
    """
    try:
        usuario = Usuario.objects.get(pk=usuario_id)
        
        # Evitar que el admin se desactive a sí mismo
        if usuario == request.user:
            messages.warning(
                request,
                'No puedes desactivar tu propia cuenta.'
            )
            return redirect('usuarios:listar_usuarios')
        
        # Cambiar estado
        usuario.is_active = not usuario.is_active
        usuario.save()
        
        estado = "activado" if usuario.is_active else "desactivado"
        messages.success(
            request,
            f'Usuario {usuario.nombre} {estado} exitosamente.'
        )
        
    except Usuario.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('usuarios:listar_usuarios')


def home_view(request):
    """
    Vista de página principal
    Redirige según el estado de autenticación
    """
    context = {
        'title': 'Ecuador Turismo - Descubre lo Extraordinario'
    }
    return render(request, 'home.html', context)