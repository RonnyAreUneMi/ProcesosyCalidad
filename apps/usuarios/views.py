import json
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse

from apps.destinos.models import Destino
from .forms import LoginForm, RegisterForm, PerfilUsuarioForm
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


from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import models
from django.db.models import Q, Count
from .forms import LoginForm, RegisterForm, PerfilUsuarioForm
from .models import Usuario, Rol


def es_administrador(user):
    """
    Función helper para verificar si el usuario es administrador
    """
    return user.is_authenticated and user.es_administrador()


@login_required
@user_passes_test(es_administrador, login_url='home')
def listar_usuarios_view(request):
    """
    Vista para listar todos los usuarios con paginación
    Solo accesible por administradores
    RF-008: Panel de administración con cambio de rol directo
    """
    # Filtros opcionales
    rol_filtro = request.GET.get('rol', '')
    busqueda = request.GET.get('q', '')
    
    # Query base
    usuarios = Usuario.objects.select_related('rol').all().order_by('-fecha_registro')
    
    # Aplicar filtros
    if rol_filtro:
        usuarios = usuarios.filter(rol__nombre=rol_filtro)
    
    if busqueda:
        usuarios = usuarios.filter(
            Q(nombre__icontains=busqueda) | 
            Q(correo__icontains=busqueda)
        )
    
    # Paginación
    paginator = Paginator(usuarios, 10)  # 10 usuarios por página
    page = request.GET.get('page', 1)
    
    try:
        usuarios_paginados = paginator.page(page)
    except PageNotAnInteger:
        usuarios_paginados = paginator.page(1)
    except EmptyPage:
        usuarios_paginados = paginator.page(paginator.num_pages)
    
    # Estadísticas generales
    total_usuarios = Usuario.objects.count()
    
    # Contar usuarios por rol - SIEMPRE mostrar los 3 roles
    usuarios_por_rol = {
        'Turista': Usuario.objects.filter(rol__nombre=Rol.TURISTA).count(),
        'Proveedor': Usuario.objects.filter(rol__nombre=Rol.PROVEEDOR).count(),
        'Administrador': Usuario.objects.filter(rol__nombre=Rol.ADMINISTRADOR).count(),
    }
    
    # Estadísticas adicionales
    usuarios_activos = Usuario.objects.filter(is_active=True).count()
    usuarios_inactivos = Usuario.objects.filter(is_active=False).count()
    
    # Usuarios nuevos del mes actual
    from datetime import datetime
    inicio_mes = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usuarios_nuevos_mes = Usuario.objects.filter(
        fecha_registro__gte=inicio_mes
    ).count()
    
    # Obtener todos los roles disponibles para los selects
    roles_disponibles = Rol.objects.filter(activo=True)
    
    context = {
        'title': 'Gestión de Usuarios',
        'usuarios': usuarios_paginados,
        'roles': Rol.objects.filter(activo=True),
        'roles_disponibles': roles_disponibles,
        'total_usuarios': total_usuarios,
        'usuarios_por_rol': usuarios_por_rol,
        'usuarios_activos': usuarios_activos,
        'usuarios_inactivos': usuarios_inactivos,
        'usuarios_nuevos_mes': usuarios_nuevos_mes,
        'rol_filtro': rol_filtro,
        'busqueda': busqueda,
    }
    return render(request, 'usuarios/listar_usuarios.html', context)

@login_required
@user_passes_test(es_administrador, login_url='home')
@require_http_methods(["POST"])
def cambiar_rol_view(request, usuario_id):
    """
    Vista para cambiar el rol de un usuario directamente desde la tabla
    Solo accesible por administradores
    RF-001: Validación para cambiar rol
    """
    try:
        usuario = Usuario.objects.get(pk=usuario_id)
        nuevo_rol_id = request.POST.get('rol_id')
        
        if not nuevo_rol_id:
            messages.error(request, 'Debe seleccionar un rol.')
            return redirect('usuarios:listar_usuarios')
        
        nuevo_rol = Rol.objects.get(pk=nuevo_rol_id)
        
        # Evitar cambiar el rol del administrador actual
        if usuario == request.user and nuevo_rol.nombre != Rol.ADMINISTRADOR:
            messages.warning(
                request,
                'No puedes cambiar tu propio rol de administrador.'
            )
            return redirect('usuarios:listar_usuarios')
        
        with transaction.atomic():
            # Guardar rol anterior para el mensaje
            rol_anterior = usuario.rol.get_nombre_display() if usuario.rol else 'Sin rol'
            
            # Cambiar rol
            usuario.rol = nuevo_rol
            usuario.save()
            
            messages.success(
                request,
                f'Rol de {usuario.nombre} cambiado de {rol_anterior} a {nuevo_rol.get_nombre_display()}.'
            )
        
    except Usuario.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
    except Rol.DoesNotExist:
        messages.error(request, 'Rol no encontrado.')
    except Exception as e:
        messages.error(request, f'Error al cambiar el rol: {str(e)}')
    
    return redirect('usuarios:listar_usuarios')


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
    from apps.reservas.models import Reserva

    destinos = Destino.objects.filter(activo=True).values(
        'id', 'nombre', 'slug', 'descripcion_corta',
        'latitud', 'longitud', 'region', 'calificacion_promedio'
    )
    
    destinos_list = []
    for destino in destinos:
        destinos_list.append({
            'id': destino['id'],
            'nombre': destino['nombre'],
            'slug': destino['slug'],
            'descripcion_corta': destino['descripcion_corta'] or '',
            'latitud': float(destino['latitud']) if destino['latitud'] else None,
            'longitud': float(destino['longitud']) if destino['longitud'] else None,
            'region': destino['region'],
            'calificacion_promedio': float(destino['calificacion_promedio']) if destino['calificacion_promedio'] else 0.0
        })
    
    destinos_json = json.dumps(destinos_list)
    
    # Inicializar estadísticas
    estadisticas_usuario = None

    # Si el usuario está autenticado, calcular sus estadísticas
    if request.user.is_authenticated and hasattr(request.user, 'rol') and request.user.rol:
        if request.user.rol.nombre == 'turista':
            mis_reservas = Reserva.objects.filter(usuario=request.user)
            gasto_total = mis_reservas.filter(
                estado__in=[Reserva.CONFIRMADA, Reserva.COMPLETADA]
            ).aggregate(total=models.Sum('costo_total'))['total'] or 0
            
            estadisticas_usuario = {
                'rol': 'turista',
                'total_reservas': mis_reservas.count(),
                'destinos_visitados': mis_reservas.filter(estado=Reserva.COMPLETADA).values('servicio__destino').distinct().count(),
                'gasto_total': float(gasto_total)
            }
        elif request.user.rol.nombre == 'proveedor':
            from apps.servicios.models import Servicio
            servicios_ids = Servicio.objects.filter(proveedor=request.user).values_list('id', flat=True)
            reservas_servicios = Reserva.objects.filter(servicio_id__in=servicios_ids)
            ingresos = reservas_servicios.filter(
                estado__in=[Reserva.CONFIRMADA, Reserva.COMPLETADA]
            ).aggregate(total=models.Sum('costo_total'))['total'] or 0

            estadisticas_usuario = {
                'rol': 'proveedor',
                'total_reservas_recibidas': reservas_servicios.count(),
                'reservas_pendientes': reservas_servicios.filter(estado=Reserva.PENDIENTE).count(),
                'ingresos_totales': float(ingresos)
            }

    context = {
        'title': 'Ecuador Turismo - Descubre lo Extraordinario',
        'destinos_json': destinos_json,
        'estadisticas_usuario': estadisticas_usuario,
    }
    return render(request, 'home.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def perfil_view(request):
    from apps.reservas.models import Reserva
    from apps.calificaciones.models import Calificacion

    # Inicializar estadísticas
    estadisticas_usuario = {
        'total_reservas': 0,
        'destinos_visitados': 0,
        'total_calificaciones': 0,
        'puntos': 0,  # Placeholder
    }

    # Calcular estadísticas si el usuario es turista
    if request.user.is_authenticated and hasattr(request.user, 'rol') and request.user.rol and request.user.rol.nombre == 'turista':
        mis_reservas = Reserva.objects.filter(usuario=request.user)
        
        estadisticas_usuario['total_reservas'] = mis_reservas.count()
        
        estadisticas_usuario['destinos_visitados'] = mis_reservas.filter(
            estado=Reserva.COMPLETADA
        ).values('servicio__destino').distinct().count()
        
        estadisticas_usuario['total_calificaciones'] = Calificacion.objects.filter(
            usuario=request.user,
            activo=True
        ).count()

    if request.method == 'POST':
        form = PerfilUsuarioForm(request.POST, instance=request.user)
        
        # Validar contraseña actual si se intenta cambiar
        password_actual = request.POST.get('password_actual')
        password1 = request.POST.get('password1')
        
        # Validar contraseña actual si se intenta cambiar
        password_actual = request.POST.get('password_actual')
        password1 = request.POST.get('password1')
        
        if password1 and password_actual:
            if not request.user.check_password(password_actual):
                messages.error(request, 'La contraseña actual es incorrecta.')
                form = PerfilUsuarioForm(request.POST, instance=request.user)
                context = {
                    'form': form,
                    'title': 'Mi Perfil',
                    'user': request.user,
                    'permisos': request.user.get_permisos(),
                    'estadisticas_usuario': estadisticas_usuario,
                }
                return render(request, 'usuarios/perfil.html', context)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil actualizado exitosamente.')
            
            # Si se cambió la contraseña, re-autenticar
            if password1:
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, request.user)
                messages.info(request, 'Tu contraseña ha sido actualizada.')
            
            return redirect('usuarios:perfil')
        else:
            messages.error(request, 'Error al actualizar el perfil. Verifica los datos.')
    else:
        form = PerfilUsuarioForm(instance=request.user)
    
    context = {
        'form': form,
        'title': 'Mi Perfil',
        'user': request.user,
        'permisos': request.user.get_permisos(),
        'estadisticas_usuario': estadisticas_usuario,
    }
    return render(request, 'usuarios/profile.html', context)