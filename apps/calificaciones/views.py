from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.core.paginator import Paginator
from .models import Calificacion, RespuestaCalificacion
from apps.servicios.models import Servicio
from apps.usuarios.models import Usuario


def rol_requerido(roles_permitidos):
    """
    Decorador para verificar roles de usuario
    """
    from functools import wraps
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, 'Debes iniciar sesión para acceder.')
                return redirect('usuarios:login')
            
            if not hasattr(request.user, 'rol') or request.user.rol is None:
                messages.error(request, 'Tu cuenta no tiene un rol asignado.')
                return redirect('home')
            
            if request.user.rol.nombre not in roles_permitidos:
                messages.error(request, 'No tienes permisos para acceder a esta página.')
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


@login_required
@require_http_methods(["POST"])
def crear_calificacion(request, servicio_id):
    """
    RF-006: Crear una calificación para un servicio
    Solo usuarios que hayan completado una reserva pueden calificar
    """
    servicio = get_object_or_404(Servicio, id=servicio_id, activo=True)
    
    # Verificar que el usuario tenga una reserva completada
    try:
        from apps.reservas.models import Reserva
        tiene_reserva_completada = Reserva.objects.filter(
            usuario=request.user,
            servicio=servicio,
            estado='completada'
        ).exists()
    except ImportError:
        # Si el módulo de reservas no existe, permitir calificar temporalmente
        tiene_reserva_completada = True
    
    if not tiene_reserva_completada:
        messages.error(request, 'Solo puedes calificar servicios que hayas utilizado.')
        return redirect('servicios:detalle_servicio', servicio_id=servicio_id)
    
    # Verificar que no haya calificado previamente
    calificacion_existente = Calificacion.objects.filter(
        usuario=request.user,
        servicio=servicio,
        activo=True
    ).first()
    
    if calificacion_existente:
        messages.warning(request, 'Ya has calificado este servicio. Puedes editarla.')
        return redirect('calificaciones:editar_calificacion', calificacion_id=calificacion_existente.id)
    
    try:
        # Obtener datos del formulario
        puntuacion = request.POST.get('puntuacion')
        comentario = request.POST.get('comentario', '').strip()
        
        # Validaciones
        if not puntuacion:
            messages.error(request, 'Debes seleccionar una puntuación.')
            return redirect('servicios:detalle_servicio', servicio_id=servicio_id)
        
        puntuacion = int(puntuacion)
        if puntuacion < 1 or puntuacion > 5:
            messages.error(request, 'La puntuación debe estar entre 1 y 5 estrellas.')
            return redirect('servicios:detalle_servicio', servicio_id=servicio_id)
        
        # Validar comentario (opcional pero con límites)
        if comentario and len(comentario) > 1000:
            messages.error(request, 'El comentario no puede exceder 1000 caracteres.')
            return redirect('servicios:detalle_servicio', servicio_id=servicio_id)
        
        # Detectar palabras ofensivas básicas (moderación simple)
        palabras_ofensivas = ['idiota', 'estupido', 'basura', 'horrible']  # Expandir según necesidad
        comentario_lower = comentario.lower()
        es_ofensivo = any(palabra in comentario_lower for palabra in palabras_ofensivas)
        
        # Crear la calificación
        with transaction.atomic():
            calificacion = Calificacion.objects.create(
                usuario=request.user,
                servicio=servicio,
                puntuacion=puntuacion,
                comentario=comentario if comentario else None,
                activo=not es_ofensivo,  # Desactivar si es ofensivo
                moderado=es_ofensivo
            )
            
            # El método save() del modelo ya actualiza el promedio del servicio
        
        if es_ofensivo:
            messages.warning(
                request, 
                'Tu calificación fue enviada pero está en revisión por contener contenido inapropiado.'
            )
        else:
            messages.success(request, '¡Gracias por tu calificación!')
        
        return redirect('servicios:detalle_servicio', servicio_id=servicio_id)
        
    except ValueError:
        messages.error(request, 'Puntuación inválida.')
        return redirect('servicios:detalle_servicio', servicio_id=servicio_id)
    except Exception as e:
        messages.error(request, f'Error al crear la calificación: {str(e)}')
        return redirect('servicios:detalle_servicio', servicio_id=servicio_id)


@login_required
def editar_calificacion(request, calificacion_id):
    """
    RF-006: Editar una calificación existente
    """
    calificacion = get_object_or_404(
        Calificacion, 
        id=calificacion_id, 
        usuario=request.user,
        activo=True
    )
    
    if request.method == 'POST':
        try:
            puntuacion = int(request.POST.get('puntuacion'))
            comentario = request.POST.get('comentario', '').strip()
            
            # Validaciones
            if puntuacion < 1 or puntuacion > 5:
                messages.error(request, 'La puntuación debe estar entre 1 y 5 estrellas.')
                return redirect('calificaciones:editar_calificacion', calificacion_id=calificacion_id)
            
            if comentario and len(comentario) > 1000:
                messages.error(request, 'El comentario no puede exceder 1000 caracteres.')
                return redirect('calificaciones:editar_calificacion', calificacion_id=calificacion_id)
            
            # Detectar contenido ofensivo
            palabras_ofensivas = ['idiota', 'estupido', 'basura', 'horrible']
            comentario_lower = comentario.lower()
            es_ofensivo = any(palabra in comentario_lower for palabra in palabras_ofensivas)
            
            with transaction.atomic():
                calificacion.puntuacion = puntuacion
                calificacion.comentario = comentario if comentario else None
                
                if es_ofensivo:
                    calificacion.activo = False
                    calificacion.moderado = True
                
                calificacion.save()
            
            if es_ofensivo:
                messages.warning(request, 'Tu calificación está en revisión por contener contenido inapropiado.')
            else:
                messages.success(request, 'Calificación actualizada exitosamente.')
            
            return redirect('servicios:detalle_servicio', servicio_id=calificacion.servicio.id)
            
        except ValueError:
            messages.error(request, 'Puntuación inválida.')
        except Exception as e:
            messages.error(request, f'Error al actualizar la calificación: {str(e)}')
    
    context = {
        'calificacion': calificacion,
    }
    
    return render(request, 'calificaciones/editar.html', context)


@login_required
@require_http_methods(["POST"])
def eliminar_calificacion(request, calificacion_id):
    """
    RF-006: Eliminar (desactivar) una calificación
    """
    calificacion = get_object_or_404(
        Calificacion, 
        id=calificacion_id, 
        usuario=request.user
    )
    
    servicio_id = calificacion.servicio.id
    
    try:
        with transaction.atomic():
            # Desactivar en lugar de eliminar (soft delete)
            calificacion.activo = False
            calificacion.save()
            
            # El método save() ya actualiza el promedio del servicio
        
        messages.success(request, 'Calificación eliminada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al eliminar la calificación: {str(e)}')
    
    return redirect('servicios:detalle_servicio', servicio_id=servicio_id)


@login_required
def mis_calificaciones(request):
    """
    Vista para que el usuario vea todas sus calificaciones
    """
    calificaciones = Calificacion.objects.filter(
        usuario=request.user
    ).select_related('servicio', 'servicio__destino').order_by('-fecha_creacion')
    
    # Estadísticas del usuario
    total_calificaciones = calificaciones.count()
    promedio_calificaciones = calificaciones.aggregate(
        promedio=Avg('puntuacion')
    )['promedio'] or 0
    
    # Distribución de puntuaciones
    distribucion = {
        '5': calificaciones.filter(puntuacion=5).count(),
        '4': calificaciones.filter(puntuacion=4).count(),
        '3': calificaciones.filter(puntuacion=3).count(),
        '2': calificaciones.filter(puntuacion=2).count(),
        '1': calificaciones.filter(puntuacion=1).count(),
    }
    
    # Paginación
    paginator = Paginator(calificaciones, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_calificaciones': total_calificaciones,
        'promedio_calificaciones': round(promedio_calificaciones, 2),
        'distribucion': distribucion,
    }
    
    return render(request, 'calificaciones/mis_calificaciones.html', context)


@login_required
@rol_requerido(['proveedor'])
def calificaciones_proveedor(request):
    """
    Vista para que los proveedores vean las calificaciones de sus servicios
    """
    # Obtener servicios del proveedor
    servicios_ids = Servicio.objects.filter(
        proveedor=request.user,
        activo=True
    ).values_list('id', flat=True)
    
    # Obtener calificaciones de esos servicios
    calificaciones = Calificacion.objects.filter(
        servicio_id__in=servicios_ids,
        activo=True
    ).select_related('usuario', 'servicio').order_by('-fecha_creacion')
    
    # Estadísticas
    total_calificaciones = calificaciones.count()
    promedio_general = calificaciones.aggregate(
        promedio=Avg('puntuacion')
    )['promedio'] or 0
    
    # Distribución
    distribucion = {
        '5': calificaciones.filter(puntuacion=5).count(),
        '4': calificaciones.filter(puntuacion=4).count(),
        '3': calificaciones.filter(puntuacion=3).count(),
        '2': calificaciones.filter(puntuacion=2).count(),
        '1': calificaciones.filter(puntuacion=1).count(),
    }
    
    # Calificaciones sin respuesta
    sin_respuesta = calificaciones.filter(respuesta__isnull=True).count()
    
    # Filtros
    servicio_id = request.GET.get('servicio')
    puntuacion = request.GET.get('puntuacion')
    
    if servicio_id:
        calificaciones = calificaciones.filter(servicio_id=servicio_id)
    
    if puntuacion:
        calificaciones = calificaciones.filter(puntuacion=int(puntuacion))
    
    # Paginación
    paginator = Paginator(calificaciones, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Servicios para el filtro
    servicios = Servicio.objects.filter(
        proveedor=request.user,
        activo=True
    ).order_by('nombre')
    
    context = {
        'page_obj': page_obj,
        'servicios': servicios,
        'total_calificaciones': total_calificaciones,
        'promedio_general': round(promedio_general, 2),
        'distribucion': distribucion,
        'sin_respuesta': sin_respuesta,
        'filtros': {
            'servicio': servicio_id,
            'puntuacion': puntuacion,
        }
    }
    
    return render(request, 'calificaciones/proveedor.html', context)


@login_required
@rol_requerido(['proveedor'])
@require_http_methods(["POST"])
def responder_calificacion(request, calificacion_id):
    """
    Vista para que los proveedores respondan a calificaciones
    """
    calificacion = get_object_or_404(Calificacion, id=calificacion_id, activo=True)
    
    # Verificar que el proveedor es dueño del servicio
    if calificacion.servicio.proveedor != request.user:
        return JsonResponse({
            'success': False,
            'error': 'No tienes permiso para responder esta calificación'
        }, status=403)
    
    # Verificar que no haya respondido ya
    if hasattr(calificacion, 'respuesta'):
        return JsonResponse({
            'success': False,
            'error': 'Ya has respondido a esta calificación'
        }, status=400)
    
    respuesta_texto = request.POST.get('respuesta', '').strip()
    
    if not respuesta_texto:
        return JsonResponse({
            'success': False,
            'error': 'La respuesta no puede estar vacía'
        }, status=400)
    
    if len(respuesta_texto) > 500:
        return JsonResponse({
            'success': False,
            'error': 'La respuesta no puede exceder 500 caracteres'
        }, status=400)
    
    try:
        respuesta = RespuestaCalificacion.objects.create(
            calificacion=calificacion,
            proveedor=request.user,
            respuesta=respuesta_texto
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Respuesta enviada exitosamente',
            'respuesta': {
                'id': respuesta.id,
                'texto': respuesta.respuesta,
                'fecha': respuesta.fecha_respuesta.strftime('%d/%m/%Y %H:%M')
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@rol_requerido(['proveedor'])
@require_http_methods(["POST"])
def editar_respuesta(request, respuesta_id):
    """
    Vista para editar una respuesta a calificación
    """
    respuesta = get_object_or_404(
        RespuestaCalificacion, 
        id=respuesta_id, 
        proveedor=request.user
    )
    
    nuevo_texto = request.POST.get('respuesta', '').strip()
    
    if not nuevo_texto:
        return JsonResponse({
            'success': False,
            'error': 'La respuesta no puede estar vacía'
        }, status=400)
    
    if len(nuevo_texto) > 500:
        return JsonResponse({
            'success': False,
            'error': 'La respuesta no puede exceder 500 caracteres'
        }, status=400)
    
    try:
        respuesta.respuesta = nuevo_texto
        respuesta.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Respuesta actualizada exitosamente',
            'respuesta': {
                'texto': respuesta.respuesta,
                'fecha': respuesta.fecha_actualizacion.strftime('%d/%m/%Y %H:%M')
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@rol_requerido(['administrador'])
def moderar_calificaciones(request):
    """
    RF-006: Panel de moderación para administradores
    """
    # Calificaciones pendientes de moderación o reportadas
    calificaciones = Calificacion.objects.filter(
        Q(moderado=True) | Q(activo=False)
    ).select_related('usuario', 'servicio').order_by('-fecha_creacion')
    
    # Filtros
    estado = request.GET.get('estado')
    if estado == 'pendiente':
        calificaciones = calificaciones.filter(moderado=True, activo=False)
    elif estado == 'aprobada':
        calificaciones = calificaciones.filter(moderado=True, activo=True)
    
    # Paginación
    paginator = Paginator(calificaciones, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_pendientes': Calificacion.objects.filter(moderado=True, activo=False).count(),
    }
    
    return render(request, 'calificaciones/moderar.html', context)


@login_required
@rol_requerido(['administrador'])
@require_http_methods(["POST"])
def aprobar_calificacion(request, calificacion_id):
    """
    Vista para aprobar una calificación moderada
    """
    calificacion = get_object_or_404(Calificacion, id=calificacion_id)
    
    try:
        with transaction.atomic():
            calificacion.activo = True
            calificacion.moderado = True
            calificacion.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Calificación aprobada'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@rol_requerido(['administrador'])
@require_http_methods(["POST"])
def rechazar_calificacion(request, calificacion_id):
    """
    Vista para rechazar una calificación
    """
    calificacion = get_object_or_404(Calificacion, id=calificacion_id)
    
    try:
        with transaction.atomic():
            calificacion.activo = False
            calificacion.moderado = True
            calificacion.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Calificación rechazada'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================
# VISTAS AJAX PARA EL CHATBOT (RF-007)
# ============================================

@require_http_methods(["GET"])
def estadisticas_calificaciones_ajax(request):
    """
    Vista AJAX para obtener estadísticas de calificaciones
    Usado por el chatbot (RF-007)
    """
    try:
        total = Calificacion.objects.filter(activo=True).count()
        promedio_general = Calificacion.objects.filter(activo=True).aggregate(
            promedio=Avg('puntuacion')
        )['promedio'] or 0
        
        # Distribución por puntuación
        distribucion = {}
        for i in range(1, 6):
            distribucion[str(i)] = Calificacion.objects.filter(
                puntuacion=i, 
                activo=True
            ).count()
        
        # Servicios mejor y peor calificados
        mejor_calificados = Servicio.objects.filter(
            activo=True,
            disponible=True
        ).order_by('-calificacion_promedio')[:5]
        
        peor_calificados = Servicio.objects.filter(
            activo=True,
            disponible=True,
            total_calificaciones__gte=3  # Al menos 3 calificaciones
        ).order_by('calificacion_promedio')[:5]
        
        mejores = [{
            'nombre': s.nombre,
            'calificacion': float(s.calificacion_promedio),
            'total': s.total_calificaciones
        } for s in mejor_calificados]
        
        peores = [{
            'nombre': s.nombre,
            'calificacion': float(s.calificacion_promedio),
            'total': s.total_calificaciones
        } for s in peor_calificados]
        
        return JsonResponse({
            'success': True,
            'total_calificaciones': total,
            'promedio_general': round(promedio_general, 2),
            'distribucion': distribucion,
            'mejor_calificados': mejores,
            'peor_calificados': peores
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def calificaciones_por_servicio_ajax(request, servicio_id):
    """
    Vista AJAX para obtener todas las calificaciones de un servicio
    Usado por el chatbot y vistas públicas (RF-007)
    """
    servicio = get_object_or_404(Servicio, id=servicio_id, activo=True)
    
    calificaciones = Calificacion.objects.filter(
        servicio=servicio,
        activo=True
    ).select_related('usuario').order_by('-fecha_creacion')
    
    # Estadísticas
    stats = {
        'total': calificaciones.count(),
        'promedio': float(servicio.calificacion_promedio),
        'distribucion': {
            '5': calificaciones.filter(puntuacion=5).count(),
            '4': calificaciones.filter(puntuacion=4).count(),
            '3': calificaciones.filter(puntuacion=3).count(),
            '2': calificaciones.filter(puntuacion=2).count(),
            '1': calificaciones.filter(puntuacion=1).count(),
        }
    }
    
    # Últimas calificaciones
    ultimas = calificaciones[:10]
    calificaciones_data = [{
        'usuario': c.usuario.nombre,
        'puntuacion': c.puntuacion,
        'comentario': c.comentario,
        'fecha': c.fecha_creacion.strftime('%d/%m/%Y')
    } for c in ultimas]
    
    return JsonResponse({
        'success': True,
        'servicio': servicio.nombre,
        'estadisticas': stats,
        'calificaciones': calificaciones_data
    })