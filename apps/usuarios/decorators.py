from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, JsonResponse


def rol_requerido(roles_permitidos):
    """
    Decorador para verificar que el usuario tenga uno de los roles especificados.
    
    Uso:
        @rol_requerido(['administrador'])
        @rol_requerido(['proveedor', 'administrador'])
        @rol_requerido(['turista'])
    
    Args:
        roles_permitidos: Lista de nombres de roles permitidos
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Verificar que el usuario esté autenticado
            if not request.user.is_authenticated:
                messages.warning(request, 'Debes iniciar sesión para acceder a esta página.')
                return redirect('usuarios:login')
            
            # Verificar que el usuario tenga rol asignado
            if not hasattr(request.user, 'rol') or request.user.rol is None:
                messages.error(request, 'Tu cuenta no tiene un rol asignado. Contacta al administrador.')
                return redirect('home')
            
            # Verificar que el rol esté en la lista de roles permitidos
            if request.user.rol.nombre not in roles_permitidos:
                messages.error(
                    request, 
                    f'No tienes permisos para acceder a esta página. '
                    f'Se requiere rol: {", ".join(roles_permitidos)}'
                )
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def solo_administrador(view_func):
    """
    Decorador simplificado para vistas que solo pueden acceder administradores.
    
    Uso:
        @solo_administrador
        def mi_vista_admin(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Debes iniciar sesión como administrador.')
            return redirect('usuarios:login')
        
        if not hasattr(request.user, 'rol') or request.user.rol is None:
            messages.error(request, 'Tu cuenta no tiene un rol asignado.')
            return redirect('home')
        
        if not request.user.es_administrador():
            messages.error(request, 'Solo los administradores pueden acceder a esta página.')
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def solo_proveedor(view_func):
    """
    Decorador simplificado para vistas que solo pueden acceder proveedores.
    
    Uso:
        @solo_proveedor
        def mi_vista_proveedor(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Debes iniciar sesión como proveedor.')
            return redirect('usuarios:login')
        
        if not hasattr(request.user, 'rol') or request.user.rol is None:
            messages.error(request, 'Tu cuenta no tiene un rol asignado.')
            return redirect('home')
        
        if not request.user.es_proveedor():
            messages.error(request, 'Solo los proveedores pueden acceder a esta página.')
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def rol_requerido_ajax(roles_permitidos):
    """
    Decorador para verificar roles en peticiones AJAX.
    Retorna JSON en lugar de redireccionar.
    
    Uso:
        @rol_requerido_ajax(['administrador', 'proveedor'])
        def mi_vista_ajax(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': 'Debes iniciar sesión'
                }, status=401)
            
            if not hasattr(request.user, 'rol') or request.user.rol is None:
                return JsonResponse({
                    'success': False,
                    'error': 'Tu cuenta no tiene un rol asignado'
                }, status=403)
            
            if request.user.rol.nombre not in roles_permitidos:
                return JsonResponse({
                    'success': False,
                    'error': 'No tienes permisos para realizar esta acción'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def usuario_activo_requerido(view_func):
    """
    Decorador para verificar que el usuario esté activo.
    
    Uso:
        @usuario_activo_requerido
        def mi_vista(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Debes iniciar sesión.')
            return redirect('usuarios:login')
        
        if not request.user.is_active:
            messages.error(request, 'Tu cuenta ha sido desactivada. Contacta al administrador.')
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def verificar_propietario_o_admin(obtener_objeto_func):
    """
    Decorador para verificar que el usuario sea el propietario del objeto o administrador.
    
    Uso:
        def obtener_servicio(request, servicio_id):
            return get_object_or_404(Servicio, id=servicio_id)
        
        @verificar_propietario_o_admin(obtener_servicio)
        def editar_servicio(request, servicio_id):
            ...
    
    Args:
        obtener_objeto_func: Función que retorna el objeto a verificar.
                            Debe aceptar (request, *args, **kwargs)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, 'Debes iniciar sesión.')
                return redirect('usuarios:login')
            
            # Obtener el objeto
            objeto = obtener_objeto_func(request, *args, **kwargs)
            
            # Verificar si es administrador
            if request.user.es_administrador():
                return view_func(request, *args, **kwargs)
            
            # Verificar si es el propietario (si el objeto tiene atributo 'proveedor' o 'usuario')
            if hasattr(objeto, 'proveedor') and objeto.proveedor == request.user:
                return view_func(request, *args, **kwargs)
            
            if hasattr(objeto, 'usuario') and objeto.usuario == request.user:
                return view_func(request, *args, **kwargs)
            
            # Si no cumple ninguna condición, denegar acceso
            messages.error(request, 'No tienes permisos para realizar esta acción.')
            return redirect('home')
        
        return wrapper
    return decorator


def requiere_confirmacion_reserva(view_func):
    """
    Decorador específico para verificar que el usuario tenga una reserva completada
    antes de poder calificar un servicio.
    
    Uso:
        @requiere_confirmacion_reserva
        def calificar_servicio(request, servicio_id):
            ...
    """
    @wraps(view_func)
    def wrapper(request, servicio_id, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Debes iniciar sesión para calificar.')
            return redirect('usuarios:login')
        
        from apps.servicios.models import Servicio
        from apps.reservas.models import Reserva
        from django.shortcuts import get_object_or_404
        
        servicio = get_object_or_404(Servicio, id=servicio_id)
        
        # Verificar si tiene reserva completada
        tiene_reserva = Reserva.objects.filter(
            usuario=request.user,
            servicio=servicio,
            estado='completada'
        ).exists()
        
        if not tiene_reserva:
            messages.error(
                request,
                'Solo puedes calificar servicios que hayas utilizado.'
            )
            return redirect('servicios:detalle_servicio', servicio_id=servicio_id)
        
        return view_func(request, servicio_id, *args, **kwargs)
    return wrapper


def limite_peticiones(max_peticiones=10, ventana_segundos=60):
    """
    Decorador para limitar el número de peticiones por usuario en un periodo de tiempo.
    Útil para prevenir spam en el chatbot o formularios.
    
    Uso:
        @limite_peticiones(max_peticiones=5, ventana_segundos=60)
        def chatbot_query(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.core.cache import cache
            from django.utils import timezone
            
            # Obtener identificador único del usuario
            if request.user.is_authenticated:
                identificador = f'rate_limit_user_{request.user.id}'
            else:
                # Para usuarios no autenticados, usar IP
                identificador = f'rate_limit_ip_{request.META.get("REMOTE_ADDR")}'
            
            # Obtener contador de peticiones
            cache_key = f'{identificador}_{view_func.__name__}'
            peticiones = cache.get(cache_key, [])
            
            # Limpiar peticiones antiguas
            ahora = timezone.now().timestamp()
            peticiones = [t for t in peticiones if ahora - t < ventana_segundos]
            
            # Verificar límite
            if len(peticiones) >= max_peticiones:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'Has excedido el límite de {max_peticiones} peticiones por {ventana_segundos} segundos.'
                    }, status=429)
                else:
                    messages.error(
                        request,
                        f'Has excedido el límite de peticiones. '
                        f'Por favor, espera unos segundos.'
                    )
                    return redirect('home')
            
            # Agregar petición actual
            peticiones.append(ahora)
            cache.set(cache_key, peticiones, ventana_segundos)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator