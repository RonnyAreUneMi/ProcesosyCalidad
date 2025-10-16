from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.db.models import Sum, Count, Q, Avg
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from .models import Reserva, ItemCarrito
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


def solo_turistas(view_func):
    """
    Decorador específico para validar que solo turistas realicen ciertas acciones
    """
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Debes iniciar sesión.')
            return redirect('usuarios:login')
        
        if not hasattr(request.user, 'rol') or request.user.rol.nombre != 'turista':
            messages.error(request, 'Solo los turistas pueden realizar esta acción.')
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    return wrapper


# ============================================
# VISTAS DEL CARRITO DE COMPRAS
# ============================================

@login_required
@solo_turistas
def ver_carrito(request):
    """
    RF-003: Vista del carrito de compras
    Muestra todos los items del carrito con cálculo dinámico de totales
    """
    items = ItemCarrito.objects.filter(
        usuario=request.user
    ).select_related(
        'servicio', 
        'servicio__destino',
        'servicio__proveedor'
    ).prefetch_related(
        'servicio__imagenes',
        'servicio__calificaciones'
    )
    
    # Calcular estadísticas de calificaciones para cada item
    for item in items:
        servicio = item.servicio
        
        # Obtener conteo de calificaciones por puntuación
        stats = servicio.calificaciones.filter(
            activo=True
        ).values('puntuacion').annotate(
            count=Count('id')
        ).order_by('puntuacion')
        
        # Crear diccionario con las estadísticas (clave como string)
        stats_dict = {str(i): 0 for i in range(1, 6)}
        for stat in stats:
            stats_dict[str(stat['puntuacion'])] = stat['count']
        
        # Agregar stats al item para usarlo en la plantilla
        item.stats_calificaciones = stats_dict
    
    # Calcular totales
    subtotal = sum(item.get_subtotal() for item in items)
    impuestos = sum(item.get_impuestos() for item in items)
    total = sum(item.get_total() for item in items)
    
    # Verificar si hay items próximos a expirar (24 horas)
    hace_24_horas = timezone.now() - timedelta(hours=24)
    items_expirando = items.filter(fecha_agregado__lte=hace_24_horas)
    
    context = {
        'items': items,
        'subtotal': subtotal,
        'impuestos': impuestos,
        'total': total,
        'items_expirando': items_expirando.exists(),
        'cantidad_items': items.count(),
    }
    
    return render(request, 'reservas/carrito.html', context)

@login_required
@solo_turistas
@require_http_methods(["POST"])
def agregar_al_carrito(request, servicio_id):
    """
    RF-003: Agregar servicio al carrito
    Valida disponibilidad, capacidad y fechas
    MEJORADO: Soporta reserva rápida
    """
    servicio = get_object_or_404(Servicio, id=servicio_id, activo=True, disponible=True)
    
    try:
        # Obtener datos del formulario
        cantidad_personas = int(request.POST.get('cantidad_personas', 1))
        fecha_servicio_str = request.POST.get('fecha_servicio')
        reserva_rapida = request.POST.get('reserva_rapida') == '1'  # ← NUEVO
        
        # Validaciones
        if cantidad_personas < 1:
            messages.error(request, 'La cantidad de personas debe ser al menos 1.')
            return redirect('servicios:detalle_servicio', servicio_id=servicio_id)
        
        if not fecha_servicio_str:
            messages.error(request, 'Debes seleccionar una fecha para el servicio.')
            return redirect('servicios:detalle_servicio', servicio_id=servicio_id)
        
        # Convertir fecha
        fecha_servicio = datetime.strptime(fecha_servicio_str, '%Y-%m-%d').date()
        
        # Validar que la fecha sea futura
        if fecha_servicio <= timezone.now().date():
            messages.error(request, 'La fecha del servicio debe ser futura.')
            return redirect('servicios:detalle_servicio', servicio_id=servicio_id)
        
        # Validar capacidad máxima
        if cantidad_personas > servicio.capacidad_maxima:
            messages.error(
                request, 
                f'La capacidad máxima para este servicio es de {servicio.capacidad_maxima} personas.'
            )
            return redirect('servicios:detalle_servicio', servicio_id=servicio_id)
        
        # Verificar si ya existe en el carrito
        item_existente = ItemCarrito.objects.filter(
            usuario=request.user,
            servicio=servicio,
            fecha_servicio=fecha_servicio
        ).first()
        
        if item_existente:
            # Actualizar cantidad
            nueva_cantidad = item_existente.cantidad_personas + cantidad_personas
            
            if nueva_cantidad > servicio.capacidad_maxima:
                messages.warning(
                    request,
                    f'Ya tienes {item_existente.cantidad_personas} personas en el carrito para esta fecha. '
                    f'Capacidad máxima: {servicio.capacidad_maxima}.'
                )
                return redirect('reservas:ver_carrito')
            
            item_existente.cantidad_personas = nueva_cantidad
            item_existente.save()
            messages.success(request, 'Cantidad actualizada en el carrito.')
        else:
            # Crear nuevo item
            ItemCarrito.objects.create(
                usuario=request.user,
                servicio=servicio,
                cantidad_personas=cantidad_personas,
                fecha_servicio=fecha_servicio
            )
            messages.success(request, f'"{servicio.nombre}" agregado al carrito.')
        
        # ← NUEVO: Decidir redirección según tipo de acción
        if reserva_rapida:
            # Reserva rápida: ir directo a confirmar
            return redirect('reservas:confirmar_reserva')
        else:
            # Normal: volver al carrito
            return redirect('reservas:ver_carrito')
        
    except ValueError as e:
        messages.error(request, 'Datos inválidos. Por favor verifica la información.')
        return redirect('servicios:detalle_servicio', servicio_id=servicio_id)
    except Exception as e:
        messages.error(request, f'Error al agregar al carrito: {str(e)}')
        return redirect('servicios:detalle_servicio', servicio_id=servicio_id)


@login_required
@solo_turistas
@require_http_methods(["POST"])
def actualizar_item_carrito(request, item_id):
    """
    RF-003: Actualizar cantidad de personas en un item del carrito
    """
    item = get_object_or_404(ItemCarrito, id=item_id, usuario=request.user)
    
    try:
        cantidad_personas = int(request.POST.get('cantidad_personas', 1))
        
        if cantidad_personas < 1:
            messages.error(request, 'La cantidad debe ser al menos 1.')
            return redirect('reservas:ver_carrito')
        
        if cantidad_personas > item.servicio.capacidad_maxima:
            messages.error(
                request,
                f'La capacidad máxima es de {item.servicio.capacidad_maxima} personas.'
            )
            return redirect('reservas:ver_carrito')
        
        item.cantidad_personas = cantidad_personas
        item.save()
        
        messages.success(request, 'Cantidad actualizada.')
        return redirect('reservas:ver_carrito')
        
    except ValueError:
        messages.error(request, 'Cantidad inválida.')
        return redirect('reservas:ver_carrito')


@login_required
@solo_turistas
@require_http_methods(["POST"])
def eliminar_item_carrito(request, item_id):
    """
    RF-003: Eliminar item del carrito
    """
    item = get_object_or_404(ItemCarrito, id=item_id, usuario=request.user)
    
    try:
        nombre_servicio = item.servicio.nombre
        item.delete()
        messages.success(request, f'"{nombre_servicio}" eliminado del carrito.')
    except Exception as e:
        messages.error(request, f'Error al eliminar: {str(e)}')
    
    return redirect('reservas:ver_carrito')


@login_required
@solo_turistas
@require_http_methods(["POST"])
def vaciar_carrito(request):
    """
    RF-003: Vaciar todo el carrito
    """
    try:
        ItemCarrito.objects.filter(usuario=request.user).delete()
        messages.success(request, 'Carrito vaciado.')
    except Exception as e:
        messages.error(request, f'Error al vaciar carrito: {str(e)}')
    
    return redirect('reservas:ver_carrito')


# ============================================
# VISTAS DE RESERVAS
# ============================================

@login_required
@solo_turistas
def confirmar_reserva(request):
    """
    RF-003: Confirmación de reserva
    Muestra resumen y permite confirmar la reserva
    """
    items = ItemCarrito.objects.filter(
        usuario=request.user
    ).select_related('servicio', 'servicio__destino')
    
    if not items.exists():
        messages.warning(request, 'Tu carrito está vacío.')
        return redirect('servicios:listar_servicios')
    
    # Calcular totales
    subtotal = sum(item.get_subtotal() for item in items)
    impuestos = sum(item.get_impuestos() for item in items)
    total = sum(item.get_total() for item in items)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Crear reservas para cada item del carrito
                reservas_creadas = []
                
                for item in items:
                    # Verificar disponibilidad nuevamente
                    if not item.servicio.disponible or not item.servicio.activo:
                        raise Exception(f'El servicio "{item.servicio.nombre}" ya no está disponible.')
                    
                    # Crear reserva
                    reserva = Reserva.objects.create(
                        usuario=request.user,
                        servicio=item.servicio,
                        fecha_servicio=item.fecha_servicio,
                        cantidad_personas=item.cantidad_personas,
                        precio_unitario=item.servicio.precio,
                        subtotal=item.get_subtotal(),
                        impuestos=item.get_impuestos(),
                        costo_total=item.get_total(),
                        estado=Reserva.PENDIENTE
                    )
                    reservas_creadas.append(reserva)
                
                # Vaciar carrito
                items.delete()
                
                messages.success(
                    request,
                    f'¡Reserva confirmada! Se crearon {len(reservas_creadas)} reserva(s).'
                )
                return redirect('reservas:mis_reservas')
                
        except Exception as e:
            messages.error(request, f'Error al procesar la reserva: {str(e)}')
            return redirect('reservas:ver_carrito')
    
    context = {
        'items': items,
        'subtotal': subtotal,
        'impuestos': impuestos,
        'total': total,
    }
    
    return render(request, 'reservas/confirmar.html', context)


@login_required
@solo_turistas
def mis_reservas(request):
    """
    Vista para que los turistas vean sus reservas
    Incluye estadísticas y filtros
    """
    reservas = Reserva.objects.filter(
        usuario=request.user
    ).select_related('servicio', 'servicio__destino').order_by('-fecha_reserva')
    
    # Filtros
    estado = request.GET.get('estado')
    if estado:
        reservas = reservas.filter(estado=estado)
    
    # Estadísticas
    total_reservas = Reserva.objects.filter(usuario=request.user).count()
    reservas_pendientes = Reserva.objects.filter(
        usuario=request.user,
        estado=Reserva.PENDIENTE
    ).count()
    reservas_completadas = Reserva.objects.filter(
        usuario=request.user,
        estado=Reserva.COMPLETADA
    ).count()
    
    # Calcular gasto total
    gasto_total = Reserva.objects.filter(
        usuario=request.user,
        estado__in=[Reserva.CONFIRMADA, Reserva.COMPLETADA]
    ).aggregate(total=Sum('costo_total'))['total'] or 0
    
    # Paginación
    paginator = Paginator(reservas, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_reservas': total_reservas,
        'reservas_pendientes': reservas_pendientes,
        'reservas_completadas': reservas_completadas,
        'gasto_total': gasto_total,
        'filtro_estado': estado,
    }
    
    return render(request, 'reservas/mis_reservas.html', context)


@login_required
@solo_turistas
def detalle_reserva(request, reserva_id):
    """
    Vista de detalle de una reserva
    Muestra información completa y opciones disponibles
    """
    reserva = get_object_or_404(
        Reserva.objects.select_related('servicio', 'servicio__destino', 'servicio__proveedor'),
        id=reserva_id,
        usuario=request.user
    )
    
    # Verificar si puede calificar
    puede_calificar = False
    ya_califico = False
    
    if reserva.estado == Reserva.COMPLETADA:
        try:
            from apps.calificaciones.models import Calificacion
            ya_califico = Calificacion.objects.filter(
                usuario=request.user,
                servicio=reserva.servicio,
                activo=True
            ).exists()
            puede_calificar = not ya_califico
        except ImportError:
            puede_calificar = True
    
    context = {
        'reserva': reserva,
        'puede_calificar': puede_calificar,
        'ya_califico': ya_califico,
    }
    
    return render(request, 'reservas/detalle.html', context)


@login_required
@solo_turistas
@require_http_methods(["POST"])
def cancelar_reserva(request, reserva_id):
    """
    Cancelar una reserva
    Solo se pueden cancelar reservas pendientes o confirmadas
    """
    reserva = get_object_or_404(Reserva, id=reserva_id, usuario=request.user)
    
    if reserva.estado not in [Reserva.PENDIENTE, Reserva.CONFIRMADA]:
        messages.error(request, 'Esta reserva no puede ser cancelada.')
        return redirect('reservas:detalle_reserva', reserva_id=reserva_id)
    
    # Verificar si la fecha del servicio ya pasó
    if reserva.fecha_servicio <= timezone.now().date():
        messages.error(request, 'No puedes cancelar una reserva cuya fecha ya pasó.')
        return redirect('reservas:detalle_reserva', reserva_id=reserva_id)
    
    motivo = request.POST.get('motivo', 'Sin motivo especificado')
    
    try:
        reserva.cancelar(motivo=motivo)
        messages.success(request, f'Reserva #{reserva.codigo_reserva} cancelada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al cancelar la reserva: {str(e)}')
    
    return redirect('reservas:mis_reservas')


# ============================================
# VISTAS PARA PROVEEDORES
# ============================================

@login_required
@rol_requerido(['proveedor'])
def reservas_proveedor(request):
    """
    Vista para que los proveedores vean las reservas de sus servicios
    """
    # Obtener servicios del proveedor
    servicios_ids = Servicio.objects.filter(
        proveedor=request.user,
        activo=True
    ).values_list('id', flat=True)
    
    # Obtener reservas de esos servicios
    reservas = Reserva.objects.filter(
        servicio_id__in=servicios_ids
    ).select_related('usuario', 'servicio').order_by('-fecha_reserva')
    
    # Filtros
    estado = request.GET.get('estado')
    servicio_id = request.GET.get('servicio')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if estado:
        reservas = reservas.filter(estado=estado)
    
    if servicio_id:
        reservas = reservas.filter(servicio_id=servicio_id)
    
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            reservas = reservas.filter(fecha_servicio__gte=fecha_desde_obj)
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            reservas = reservas.filter(fecha_servicio__lte=fecha_hasta_obj)
        except ValueError:
            pass
    
    # Estadísticas
    total_reservas = Reserva.objects.filter(servicio_id__in=servicios_ids).count()
    pendientes = Reserva.objects.filter(
        servicio_id__in=servicios_ids,
        estado=Reserva.PENDIENTE
    ).count()
    confirmadas = Reserva.objects.filter(
        servicio_id__in=servicios_ids,
        estado=Reserva.CONFIRMADA
    ).count()
    
    # Ingresos totales
    ingresos = Reserva.objects.filter(
        servicio_id__in=servicios_ids,
        estado__in=[Reserva.CONFIRMADA, Reserva.COMPLETADA]
    ).aggregate(total=Sum('costo_total'))['total'] or 0
    
    # Paginación
    paginator = Paginator(reservas, 15)
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
        'total_reservas': total_reservas,
        'pendientes': pendientes,
        'confirmadas': confirmadas,
        'ingresos': ingresos,
        'filtros': {
            'estado': estado,
            'servicio': servicio_id,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
        }
    }
    
    return render(request, 'reservas/proveedor.html', context)


@login_required
@rol_requerido(['proveedor'])
@require_http_methods(["POST"])
def confirmar_reserva_proveedor(request, reserva_id):
    """
    Permite al proveedor confirmar una reserva pendiente
    """
    reserva = get_object_or_404(Reserva, id=reserva_id)
    
    # Verificar que el proveedor es dueño del servicio
    if reserva.servicio.proveedor != request.user:
        return JsonResponse({
            'success': False,
            'error': 'No tienes permiso para modificar esta reserva'
        }, status=403)
    
    if reserva.estado != Reserva.PENDIENTE:
        return JsonResponse({
            'success': False,
            'error': 'Solo se pueden confirmar reservas pendientes'
        }, status=400)
    
    try:
        reserva.confirmar()
        return JsonResponse({
            'success': True,
            'message': 'Reserva confirmada exitosamente',
            'nuevo_estado': 'Confirmada'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@rol_requerido(['proveedor'])
@require_http_methods(["POST"])
def completar_reserva_proveedor(request, reserva_id):
    """
    Permite al proveedor marcar una reserva como completada
    Esto habilita la posibilidad de calificar para el turista
    """
    reserva = get_object_or_404(Reserva, id=reserva_id)
    
    # Verificar que el proveedor es dueño del servicio
    if reserva.servicio.proveedor != request.user:
        return JsonResponse({
            'success': False,
            'error': 'No tienes permiso para modificar esta reserva'
        }, status=403)
    
    if reserva.estado != Reserva.CONFIRMADA:
        return JsonResponse({
            'success': False,
            'error': 'Solo se pueden completar reservas confirmadas'
        }, status=400)
    
    try:
        reserva.completar()
        return JsonResponse({
            'success': True,
            'message': 'Reserva marcada como completada',
            'nuevo_estado': 'Completada'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================
# VISTAS AJAX PARA ESTADÍSTICAS (CHATBOT)
# ============================================

@require_http_methods(["GET"])
def estadisticas_reservas_ajax(request):
    """
    Vista AJAX para obtener estadísticas de reservas
    Usado por el chatbot (RF-007)
    """
    try:
        total_reservas = Reserva.objects.count()
        
        # Reservas por estado
        por_estado = {}
        for estado_code, estado_nombre in Reserva.ESTADO_CHOICES:
            count = Reserva.objects.filter(estado=estado_code).count()
            por_estado[estado_nombre] = count
        
        # Ingresos totales
        ingresos_totales = Reserva.objects.filter(
            estado__in=[Reserva.CONFIRMADA, Reserva.COMPLETADA]
        ).aggregate(total=Sum('costo_total'))['total'] or 0
        
        # Servicios más reservados
        mas_reservados = Servicio.objects.annotate(
            num_reservas=Count('reservas')
        ).filter(num_reservas__gt=0).order_by('-num_reservas')[:5]
        
        servicios_populares = [{
            'nombre': s.nombre,
            'reservas': s.num_reservas,
            'destino': s.destino.nombre,
            'tipo': s.get_tipo_display()
        } for s in mas_reservados]
        
        # Reservas por mes (últimos 6 meses)
        from django.utils import timezone
        from datetime import timedelta
        
        hace_6_meses = timezone.now() - timedelta(days=180)
        reservas_recientes = Reserva.objects.filter(
            fecha_creacion__gte=hace_6_meses
        ).count()
        
        return JsonResponse({
            'success': True,
            'total_reservas': total_reservas,
            'reservas_recientes': reservas_recientes,
            'por_estado': por_estado,
            'ingresos_totales': float(ingresos_totales),
            'servicios_populares': servicios_populares
        })
        
    except Exception as e:
        import traceback
        print(f"Error en estadisticas_reservas_ajax: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def mis_estadisticas_ajax(request):
    """
    Vista AJAX para estadísticas personales del usuario
    Diferencia entre turistas y proveedores
    """
    try:
        if request.user.rol.nombre == 'turista':
            # Estadísticas para turistas
            mis_reservas = Reserva.objects.filter(usuario=request.user)
            
            total_reservas = mis_reservas.count()
            
            gasto_total = mis_reservas.filter(
                estado__in=[Reserva.CONFIRMADA, Reserva.COMPLETADA]
            ).aggregate(total=Sum('costo_total'))['total'] or 0
            
            # Destinos únicos visitados
            destinos_visitados = mis_reservas.filter(
                estado=Reserva.COMPLETADA
            ).values('servicio__destino__nombre').distinct().count()
            
            # Próximas reservas
            from django.utils import timezone
            proximas = mis_reservas.filter(
                fecha_inicio__gte=timezone.now(),
                estado__in=[Reserva.PENDIENTE, Reserva.CONFIRMADA]
            ).count()
            
            # Reservas por tipo de servicio
            por_tipo = {}
            for tipo_code, tipo_nombre in Servicio.TIPO_CHOICES:
                count = mis_reservas.filter(servicio__tipo=tipo_code).count()
                if count > 0:
                    por_tipo[tipo_nombre] = count
            
            return JsonResponse({
                'success': True,
                'rol': 'turista',
                'total_reservas': total_reservas,
                'gasto_total': float(gasto_total),
                'destinos_visitados': destinos_visitados,
                'proximas_reservas': proximas,
                'por_tipo_servicio': por_tipo
            })
            
        elif request.user.rol.nombre == 'proveedor':
            # Estadísticas para proveedores
            servicios_ids = Servicio.objects.filter(
                proveedor=request.user
            ).values_list('id', flat=True)
            
            reservas_servicios = Reserva.objects.filter(
                servicio_id__in=servicios_ids
            )
            
            total_reservas = reservas_servicios.count()
            
            ingresos = reservas_servicios.filter(
                estado__in=[Reserva.CONFIRMADA, Reserva.COMPLETADA]
            ).aggregate(total=Sum('costo_total'))['total'] or 0
            
            # Reservas pendientes de confirmar
            pendientes = reservas_servicios.filter(
                estado=Reserva.PENDIENTE
            ).count()
            
            # Servicio más reservado
            servicio_popular = Servicio.objects.filter(
                proveedor=request.user
            ).annotate(
                num_reservas=Count('reservas')
            ).order_by('-num_reservas').first()
            
            servicio_top = None
            if servicio_popular:
                servicio_top = {
                    'nombre': servicio_popular.nombre,
                    'reservas': servicio_popular.num_reservas
                }
            
            return JsonResponse({
                'success': True,
                'rol': 'proveedor',
                'total_reservas': total_reservas,
                'ingresos_totales': float(ingresos),
                'pendientes': pendientes,
                'servicio_mas_reservado': servicio_top
            })
        
        else:
            return JsonResponse({
                'success': False,
                'error': 'Rol no soportado para estadísticas'
            }, status=400)
            
    except Exception as e:
        import traceback
        print(f"Error en mis_estadisticas_ajax: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)