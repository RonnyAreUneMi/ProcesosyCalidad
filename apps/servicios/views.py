from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from .models import Servicio, ImagenServicio
from apps.destinos.models import Destino, Categoria
from apps.usuarios.models import Usuario
from datetime import date, timedelta


def rol_requerido(roles_permitidos):
    """
    Decorador local para verificar roles
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


def listar_servicios(request):
    """
    Vista para listar servicios con filtros y búsqueda mejorados
    RF-002: Búsqueda y Filtrado por Región
    """
    # Query base - ANTES de aplicar filtros para estadísticas
    servicios_base = Servicio.objects.filter(activo=True, disponible=True)
    
    # Calcular estadísticas por tipo ANTES de filtrar
    stats_por_tipo = {
        'alojamiento': servicios_base.filter(tipo='alojamiento').count(),
        'tour': servicios_base.filter(tipo='tour').count(),
        'actividad': servicios_base.filter(tipo='actividad').count(),
        'transporte': servicios_base.filter(tipo='transporte').count(),
        'gastronomia': servicios_base.filter(tipo='gastronomia').count(),
    }
    
    # Ahora aplicamos los filtros para la búsqueda
    servicios = servicios_base.select_related('destino', 'categoria', 'proveedor')
    
    # Obtener parámetros de filtro
    tipo = request.GET.get('tipo')
    destino_id = request.GET.get('destino')
    categoria_id = request.GET.get('categoria')
    region = request.GET.get('region')
    precio_min = request.GET.get('precio_min')
    precio_max = request.GET.get('precio_max')
    calificacion_min = request.GET.get('calificacion')
    busqueda = request.GET.get('q')
    
    # Contador de filtros aplicados
    filtros_activos = 0
    
    # Aplicar filtros de manera más flexible
    if tipo:
        servicios = servicios.filter(tipo=tipo)
        filtros_activos += 1
    
    if destino_id:
        servicios = servicios.filter(destino_id=destino_id)
        filtros_activos += 1
    
    if categoria_id:
        servicios = servicios.filter(categoria_id=categoria_id)
        filtros_activos += 1
    
    if region:
        servicios = servicios.filter(destino__region=region)
        filtros_activos += 1
    
    # Filtros de precio - permitir cualquier valor
    if precio_min:
        try:
            precio_min_val = float(precio_min)
            servicios = servicios.filter(precio__gte=precio_min_val)
            filtros_activos += 1
        except ValueError:
            messages.warning(request, 'Precio mínimo inválido')
            precio_min = None
    
    if precio_max:
        try:
            precio_max_val = float(precio_max)
            servicios = servicios.filter(precio__lte=precio_max_val)
            filtros_activos += 1
        except ValueError:
            messages.warning(request, 'Precio máximo inválido')
            precio_max = None
    
    if calificacion_min:
        try:
            cal_min = float(calificacion_min)
            servicios = servicios.filter(calificacion_promedio__gte=cal_min)
            filtros_activos += 1
        except ValueError:
            messages.warning(request, 'Calificación inválida')
            calificacion_min = None
    
    # Búsqueda por texto - MÁS FLEXIBLE
    if busqueda:
        servicios = servicios.filter(
            Q(nombre__icontains=busqueda) |
            Q(descripcion__icontains=busqueda) |
            Q(destino__nombre__icontains=busqueda) |
            Q(destino__descripcion__icontains=busqueda) |
            Q(categoria__nombre__icontains=busqueda)
        )
        filtros_activos += 1
    
    # Ordenamiento
    orden = request.GET.get('orden', 'calificacion')
    opciones_orden = {
        'precio_asc': 'precio',
        'precio_desc': '-precio',
        'calificacion': '-calificacion_promedio',
        'nombre': 'nombre',
        'recientes': '-fecha_creacion'
    }
    servicios = servicios.order_by(opciones_orden.get(orden, '-calificacion_promedio'))
    
    # Paginación
    paginator = Paginator(servicios, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Datos para filtros
    destinos = Destino.objects.filter(activo=True).order_by('nombre')
    categorias = Categoria.objects.filter(activo=True).order_by('nombre')
    
    # Regiones de Ecuador
    REGIONES = [
        ('costa', 'Costa'),
        ('sierra', 'Sierra'),
        ('oriente', 'Oriente (Amazonía)'),
        ('galapagos', 'Galápagos'),
    ]
    
    # Construir query string para paginación
    filtros_query = ''
    params = []
    if busqueda:
        params.append(f'q={busqueda}')
    if tipo:
        params.append(f'tipo={tipo}')
    if destino_id:
        params.append(f'destino={destino_id}')
    if categoria_id:
        params.append(f'categoria={categoria_id}')
    if region:
        params.append(f'region={region}')
    if precio_min:
        params.append(f'precio_min={precio_min}')
    if precio_max:
        params.append(f'precio_max={precio_max}')
    if calificacion_min:
        params.append(f'calificacion={calificacion_min}')
    if orden:
        params.append(f'orden={orden}')
    
    if params:
        filtros_query = '&' + '&'.join(params)
    
    context = {
        'page_obj': page_obj,
        'destinos': destinos,
        'categorias': categorias,
        'regiones': REGIONES,
        'tipos_servicio': Servicio.TIPO_SERVICIO_CHOICES,
        'total_resultados': servicios_base.count(),  # Total general
        'resultados_filtrados': page_obj.paginator.count,  # Resultados después de filtrar
        'stats_por_tipo': stats_por_tipo,  # Estadísticas por tipo
        'filtros_activos': filtros_activos,
        'filtros_query': filtros_query,
        'filtros_aplicados': {
            'tipo': tipo,
            'destino': destino_id,
            'categoria': categoria_id,
            'region': region,
            'precio_min': precio_min,
            'precio_max': precio_max,
            'calificacion': calificacion_min,
            'busqueda': busqueda,
            'orden': orden,
        }
    }
    
    return render(request, 'servicios/listar.html', context)

def detalle_servicio(request, servicio_id):
    """
    Vista para mostrar el detalle de un servicio
    Relacionado con RF-003: Sistema de Reservas y RF-006: Calificaciones
    VERSIÓN CORREGIDA con integración completa
    """
    servicio = get_object_or_404(
        Servicio.objects.select_related('destino', 'categoria', 'proveedor'),
        id=servicio_id,
        activo=True
    )
    
    # Obtener imágenes del servicio ordenadas
    imagenes = servicio.imagenes.all()
    imagen_principal = imagenes.filter(es_principal=True).first()
    imagenes_secundarias = imagenes.filter(es_principal=False)
    
    # Variables para calificaciones (valores por defecto)
    calificaciones_lista = []
    stats_calificaciones = {
        '5': 0,
        '4': 0,
        '3': 0,
        '2': 0,
        '1': 0,
    }
    puede_calificar = False
    ya_califico = False
    calificacion_usuario = None
    
    # Intentar obtener calificaciones solo si el modelo existe
    try:
        from apps.calificaciones.models import Calificacion
        
        # CORRECCIÓN: Obtener el QuerySet completo primero
        calificaciones_queryset = Calificacion.objects.filter(
            servicio=servicio,
            activo=True
        ).select_related('usuario').prefetch_related('respuesta')
        
        # Calcular estadísticas ANTES del slice (sobre el QuerySet completo)
        stats_calificaciones = {
            '5': calificaciones_queryset.filter(puntuacion=5).count(),
            '4': calificaciones_queryset.filter(puntuacion=4).count(),
            '3': calificaciones_queryset.filter(puntuacion=3).count(),
            '2': calificaciones_queryset.filter(puntuacion=2).count(),
            '1': calificaciones_queryset.filter(puntuacion=1).count(),
        }
        
        # AHORA sí aplicar slice para mostrar solo las últimas 10
        calificaciones_lista = list(calificaciones_queryset.order_by('-fecha_creacion')[:10])
        
        # Verificar permisos del usuario autenticado
        if request.user.is_authenticated:
            # Solo verificar si es turista
            if hasattr(request.user, 'rol') and request.user.rol.nombre == 'turista':
                # Verificar si tiene reservas completadas
                try:
                    from apps.reservas.models import Reserva
                    tiene_reserva_completada = Reserva.objects.filter(
                        usuario=request.user,
                        servicio=servicio,
                        estado='completada'
                    ).exists()
                except ImportError:
                    # Si no existe el modelo de reservas, no permitir calificar
                    tiene_reserva_completada = False
                
                if tiene_reserva_completada:
                    # Verificar si ya calificó
                    calificacion_usuario = Calificacion.objects.filter(
                        usuario=request.user,
                        servicio=servicio,
                        activo=True
                    ).first()
                    
                    ya_califico = calificacion_usuario is not None
                    puede_calificar = not ya_califico
                    
    except ImportError:
        # El modelo Calificacion aún no existe, usar valores por defecto
        pass
    
    # Servicios relacionados del mismo destino
    servicios_relacionados = Servicio.objects.filter(
        destino=servicio.destino,
        activo=True,
        disponible=True
    ).exclude(id=servicio.id).order_by('-calificacion_promedio')[:4]
    
    # Verificar si el servicio está en el carrito (si existe el modelo)
    en_carrito = False
    cantidad_en_carrito = 0
    if request.user.is_authenticated:
        try:
            from apps.reservas.models import ItemCarrito
            item_carrito = ItemCarrito.objects.filter(
                usuario=request.user,
                servicio=servicio
            ).first()
            
            if item_carrito:
                en_carrito = True
                cantidad_en_carrito = item_carrito.cantidad_personas
        except ImportError:
            pass
    fecha_minima = (date.today() + timedelta(days=1)).isoformat()
    context = {
        'servicio': servicio,
        'imagen_principal': imagen_principal,
        'imagenes_secundarias': imagenes_secundarias,
        'calificaciones': calificaciones_lista,
        'stats_calificaciones': stats_calificaciones,
        'total_calificaciones': sum(stats_calificaciones.values()),
        'servicios_relacionados': servicios_relacionados,
        'puede_calificar': puede_calificar,
        'ya_califico': ya_califico,
        'calificacion_usuario': calificacion_usuario,
        'en_carrito': en_carrito,
        'cantidad_en_carrito': cantidad_en_carrito,
        'fecha_minima': fecha_minima,
    }
    
    return render(request, 'servicios/detalle.html', context)


@login_required
@rol_requerido(['proveedor', 'administrador'])
def crear_servicio(request):
    """
    Vista para crear un nuevo servicio
    Solo para proveedores y administradores
    """
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Obtener datos del formulario
                nombre = request.POST.get('nombre')
                descripcion = request.POST.get('descripcion')
                tipo = request.POST.get('tipo')
                precio = request.POST.get('precio')
                destino_id = request.POST.get('destino')
                categoria_id = request.POST.get('categoria')
                capacidad_maxima = request.POST.get('capacidad_maxima', 1)
                disponible = request.POST.get('disponible') == 'on'
                
                # Validaciones básicas
                if not all([nombre, descripcion, tipo, precio, destino_id]):
                    messages.error(request, 'Todos los campos obligatorios deben ser completados')
                    return redirect('servicios:crear_servicio')
                
                # Obtener el destino
                destino = get_object_or_404(Destino, id=destino_id, activo=True)
                
                # Obtener la categoría si se proporcionó
                categoria = None
                if categoria_id:
                    categoria = get_object_or_404(Categoria, id=categoria_id, activo=True)
                
                # Determinar el proveedor
                if request.user.rol.nombre == 'proveedor':
                    proveedor = request.user
                else:
                    # Si es administrador, debe asignar a un proveedor específico
                    proveedor_id = request.POST.get('proveedor_id')
                    if proveedor_id:
                        proveedor = get_object_or_404(Usuario, id=proveedor_id, rol__nombre='proveedor')
                    else:
                        messages.error(request, 'Debe seleccionar un proveedor')
                        # Recargar el formulario con los datos
                        destinos = Destino.objects.filter(activo=True).order_by('nombre')
                        categorias = Categoria.objects.filter(activo=True).order_by('nombre')
                        proveedores = Usuario.objects.filter(rol__nombre='proveedor', is_active=True)
                        context = {
                            'destinos': destinos,
                            'categorias': categorias,
                            'tipos_servicio': Servicio.TIPO_SERVICIO_CHOICES,
                            'proveedores': proveedores,
                        }
                        return render(request, 'servicios/crear.html', context)
                
                # Crear el servicio
                servicio = Servicio.objects.create(
                    nombre=nombre,
                    descripcion=descripcion,
                    tipo=tipo,
                    precio=precio,
                    destino=destino,
                    categoria=categoria,
                    proveedor=proveedor,
                    capacidad_maxima=capacidad_maxima,
                    disponible=disponible
                )
                
                # Procesar imágenes si se subieron
                imagenes = request.FILES.getlist('imagenes')
                for idx, imagen in enumerate(imagenes):
                    ImagenServicio.objects.create(
                        servicio=servicio,
                        imagen=imagen,
                        es_principal=(idx == 0),
                        orden=idx
                    )
                
                messages.success(request, f'Servicio "{servicio.nombre}" creado exitosamente')
                return redirect('servicios:detalle_servicio', servicio_id=servicio.id)
            
        except Exception as e:
            messages.error(request, f'Error al crear el servicio: {str(e)}')
            return redirect('servicios:crear_servicio')
    
    # GET - Mostrar formulario
    destinos = Destino.objects.filter(activo=True).order_by('nombre')
    categorias = Categoria.objects.filter(activo=True).order_by('nombre')
    
    # Si es administrador, cargar lista de proveedores
    proveedores = None
    if request.user.rol.nombre == 'administrador':
        proveedores = Usuario.objects.filter(rol__nombre='proveedor', is_active=True).order_by('nombre')
    
    context = {
        'destinos': destinos,
        'categorias': categorias,
        'tipos_servicio': Servicio.TIPO_SERVICIO_CHOICES,
        'proveedores': proveedores,
    }
    
    return render(request, 'servicios/crear.html', context)


@login_required
@rol_requerido(['proveedor', 'administrador'])
def editar_servicio(request, servicio_id):
    """
    Vista para editar un servicio existente
    """
    servicio = get_object_or_404(Servicio, id=servicio_id)
    
    # Verificar permisos: proveedor solo edita sus servicios
    if request.user.rol.nombre == 'proveedor' and servicio.proveedor != request.user:
        messages.error(request, 'No tienes permiso para editar este servicio')
        return redirect('servicios:listar_servicios')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                servicio.nombre = request.POST.get('nombre')
                servicio.descripcion = request.POST.get('descripcion')
                servicio.tipo = request.POST.get('tipo')
                servicio.precio = request.POST.get('precio')
                servicio.capacidad_maxima = request.POST.get('capacidad_maxima', 1)
                servicio.disponible = request.POST.get('disponible') == 'on'
                
                destino_id = request.POST.get('destino')
                servicio.destino = get_object_or_404(Destino, id=destino_id, activo=True)
                
                categoria_id = request.POST.get('categoria')
                if categoria_id:
                    servicio.categoria = get_object_or_404(Categoria, id=categoria_id, activo=True)
                else:
                    servicio.categoria = None
                
                servicio.save()
                
                # Procesar nuevas imágenes
                imagenes = request.FILES.getlist('imagenes')
                if imagenes:
                    ultima_orden = servicio.imagenes.count()
                    for idx, imagen in enumerate(imagenes):
                        ImagenServicio.objects.create(
                            servicio=servicio,
                            imagen=imagen,
                            orden=ultima_orden + idx
                        )
                
                messages.success(request, 'Servicio actualizado exitosamente')
                return redirect('servicios:detalle_servicio', servicio_id=servicio.id)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar el servicio: {str(e)}')
    
    destinos = Destino.objects.filter(activo=True).order_by('nombre')
    categorias = Categoria.objects.filter(activo=True).order_by('nombre')
    
    context = {
        'servicio': servicio,
        'destinos': destinos,
        'categorias': categorias,
        'tipos_servicio': Servicio.TIPO_SERVICIO_CHOICES,
    }
    
    return render(request, 'servicios/editar.html', context)


@login_required
@rol_requerido(['proveedor', 'administrador'])
def eliminar_servicio(request, servicio_id):
    """
    Vista para eliminar (desactivar) un servicio
    """
    servicio = get_object_or_404(Servicio, id=servicio_id)
    
    # Verificar permisos
    if request.user.rol.nombre == 'proveedor' and servicio.proveedor != request.user:
        messages.error(request, 'No tienes permiso para eliminar este servicio')
        return redirect('servicios:listar_servicios')
    
    if request.method == 'POST':
        servicio.activo = False
        servicio.disponible = False
        servicio.save()
        messages.success(request, f'Servicio "{servicio.nombre}" eliminado exitosamente')
        return redirect('servicios:mis_servicios')
    
    return render(request, 'servicios/eliminar.html', {'servicio': servicio})


@login_required
@rol_requerido(['proveedor'])
def mis_servicios(request):
    """
    Vista para que los proveedores vean sus servicios
    """
    servicios = Servicio.objects.filter(
        proveedor=request.user
    ).select_related('destino', 'categoria').order_by('-fecha_creacion')
    
    # Estadísticas
    total_servicios = servicios.count()
    servicios_activos = servicios.filter(activo=True, disponible=True).count()
    promedio_calificacion = servicios.aggregate(
        promedio=Avg('calificacion_promedio')
    )['promedio'] or 0
    
    # Paginación
    paginator = Paginator(servicios, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_servicios': total_servicios,
        'servicios_activos': servicios_activos,
        'promedio_calificacion': round(promedio_calificacion, 2),
    }
    
    return render(request, 'servicios/mis_servicios.html', context)


@login_required
@require_http_methods(["POST"])
def eliminar_imagen(request, imagen_id):
    """
    Vista AJAX para eliminar una imagen de servicio
    """
    imagen = get_object_or_404(ImagenServicio, id=imagen_id)
    
    # Verificar permisos
    if request.user.rol.nombre == 'proveedor' and imagen.servicio.proveedor != request.user:
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)
    
    if not request.user.rol.nombre in ['proveedor', 'administrador']:
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)
    
    try:
        # Si es la imagen principal, asignar otra como principal
        if imagen.es_principal:
            otra_imagen = imagen.servicio.imagenes.exclude(id=imagen.id).first()
            if otra_imagen:
                otra_imagen.es_principal = True
                otra_imagen.save()
        
        imagen.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def marcar_imagen_principal(request, imagen_id):
    """
    Vista AJAX para marcar una imagen como principal
    """
    imagen = get_object_or_404(ImagenServicio, id=imagen_id)
    
    # Verificar permisos
    if request.user.rol.nombre == 'proveedor' and imagen.servicio.proveedor != request.user:
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)
    
    if not request.user.rol.nombre in ['proveedor', 'administrador']:
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)
    
    try:
        # Desmarcar todas las demás imágenes
        ImagenServicio.objects.filter(
            servicio=imagen.servicio
        ).update(es_principal=False)
        
        # Marcar esta como principal
        imagen.es_principal = True
        imagen.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def servicios_por_tipo(request, tipo):
    """
    Vista para listar servicios por tipo específico
    """
    # Validar que el tipo existe
    tipos_validos = dict(Servicio.TIPO_SERVICIO_CHOICES)
    if tipo not in tipos_validos:
        messages.error(request, 'Tipo de servicio no válido')
        return redirect('servicios:listar_servicios')
    
    servicios = Servicio.objects.filter(
        tipo=tipo,
        activo=True,
        disponible=True
    ).select_related('destino', 'categoria', 'proveedor').order_by('-calificacion_promedio')
    
    # Paginación
    paginator = Paginator(servicios, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'tipo': tipo,
        'tipo_nombre': tipos_validos[tipo],
        'total_servicios': servicios.count(),
    }
    
    return render(request, 'servicios/por_tipo.html', context)


@require_http_methods(["GET"])
def buscar_servicios_ajax(request):
    """
    Vista AJAX para búsqueda de servicios
    VERSIÓN CORREGIDA: Maneja parámetros opcionales correctamente
    Usado por el chatbot (RF-007) y búsqueda predictiva
    """
    # Obtener parámetros (todos opcionales)
    query = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    region = request.GET.get('region', '').strip()
    destino_id = request.GET.get('destino', '').strip()
    precio_max = request.GET.get('precio_max', '').strip()
    
    # Query base
    servicios = Servicio.objects.filter(
        activo=True,
        disponible=True
    ).select_related('destino', 'categoria', 'proveedor')
    
    # Aplicar filtros solo si tienen valor
    if query:
        servicios = servicios.filter(
            Q(nombre__icontains=query) | 
            Q(descripcion__icontains=query) |
            Q(destino__nombre__icontains=query)
        )
    
    if tipo:
        servicios = servicios.filter(tipo=tipo)
    
    if region:
        servicios = servicios.filter(destino__region=region)
    
    if destino_id:
        try:
            servicios = servicios.filter(destino_id=int(destino_id))
        except (ValueError, TypeError):
            pass
    
    if precio_max:
        try:
            servicios = servicios.filter(precio__lte=float(precio_max))
        except (ValueError, TypeError):
            pass
    
    # Ordenar por calificación y limitar
    servicios = servicios.order_by('-calificacion_promedio', '-total_calificaciones')[:15]
    
    # Construir respuesta
    resultados = [{
        'id': s.id,
        'nombre': s.nombre,
        'tipo': s.get_tipo_display(),
        'tipo_code': s.tipo,
        'precio': float(s.precio),
        'destino': s.destino.nombre,
        'region': s.destino.get_region_display(),
        'calificacion': float(s.calificacion_promedio),
        'total_calificaciones': s.total_calificaciones,
        'capacidad': s.capacidad_maxima,
        'descripcion_corta': s.descripcion[:150] + '...' if len(s.descripcion) > 150 else s.descripcion,
        'url': f'/servicios/{s.id}/',
        'imagen': s.get_imagen_principal() if hasattr(s, 'get_imagen_principal') else None
    } for s in servicios]
    
    return JsonResponse({
        'success': True,
        'servicios': resultados,
        'total_encontrados': len(resultados),
        'filtros_aplicados': {
            'query': query or None,
            'tipo': tipo or None,
            'region': region or None,
            'destino_id': destino_id or None,
            'precio_max': precio_max or None
        }
    })


@require_http_methods(["GET"])
def estadisticas_servicios_ajax(request):
    """
    Vista AJAX para obtener estadísticas de servicios
    Usado por el chatbot para análisis comparativo (RF-007)
    """
    try:
        # Estadísticas generales
        total_servicios = Servicio.objects.filter(activo=True, disponible=True).count()
        
        # Servicios por tipo
        servicios_por_tipo = {}
        for tipo_code, tipo_nombre in Servicio.TIPO_SERVICIO_CHOICES:
            count = Servicio.objects.filter(
                tipo=tipo_code,
                activo=True,
                disponible=True
            ).count()
            servicios_por_tipo[tipo_nombre] = count
        
        # Servicios por región
        servicios_por_region = {}
        regiones = ['costa', 'sierra', 'oriente', 'galapagos']
        for region in regiones:
            count = Servicio.objects.filter(
                destino__region=region,
                activo=True,
                disponible=True
            ).count()
            servicios_por_region[region.title()] = count
        
        # Precio promedio por tipo
        precio_promedio_tipo = {}
        for tipo_code, tipo_nombre in Servicio.TIPO_SERVICIO_CHOICES:
            promedio = Servicio.objects.filter(
                tipo=tipo_code,
                activo=True,
                disponible=True
            ).aggregate(promedio=Avg('precio'))['promedio']
            precio_promedio_tipo[tipo_nombre] = round(float(promedio or 0), 2)
        
        # Servicios mejor calificados
        mejor_calificados = Servicio.objects.filter(
            activo=True,
            disponible=True
        ).order_by('-calificacion_promedio')[:5]
        
        mejores = [{
            'id': s.id,
            'nombre': s.nombre,
            'tipo': s.get_tipo_display(),
            'calificacion': float(s.calificacion_promedio),
            'precio': float(s.precio),
            'destino': s.destino.nombre
        } for s in mejor_calificados]
        
        return JsonResponse({
            'success': True,
            'total_servicios': total_servicios,
            'servicios_por_tipo': servicios_por_tipo,
            'servicios_por_region': servicios_por_region,
            'precio_promedio_tipo': precio_promedio_tipo,
            'mejor_calificados': mejores
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def comparar_servicios_ajax(request):
    """
    Vista AJAX para comparar múltiples servicios
    Usado por el chatbot (RF-007) para análisis comparativo
    """
    servicios_ids = request.GET.get('ids', '').split(',')
    
    if not servicios_ids or servicios_ids == ['']:
        return JsonResponse({
            'success': False,
            'error': 'Debe proporcionar IDs de servicios'
        }, status=400)
    
    try:
        servicios = Servicio.objects.filter(
            id__in=servicios_ids,
            activo=True,
            disponible=True
        ).select_related('destino', 'categoria')
        
        comparacion = [{
            'id': s.id,
            'nombre': s.nombre,
            'tipo': s.get_tipo_display(),
            'precio': float(s.precio),
            'calificacion': float(s.calificacion_promedio),
            'total_calificaciones': s.total_calificaciones,
            'destino': s.destino.nombre,
            'region': s.destino.region,
            'capacidad': s.capacidad_maxima,
            'categoria': s.categoria.nombre if s.categoria else None,
            'url': f'/servicios/{s.id}/'
        } for s in servicios]
        
        # Calcular diferencias
        if len(comparacion) > 1:
            precios = [s['precio'] for s in comparacion]
            calificaciones = [s['calificacion'] for s in comparacion]
            
            analisis = {
                'precio_min': min(precios),
                'precio_max': max(precios),
                'precio_promedio': sum(precios) / len(precios),
                'diferencia_precio': max(precios) - min(precios),
                'mejor_calificado': max(comparacion, key=lambda x: x['calificacion']),
                'mas_economico': min(comparacion, key=lambda x: x['precio']),
                'mas_reseniado': max(comparacion, key=lambda x: x['total_calificaciones'])
            }
        else:
            analisis = None
        
        return JsonResponse({
            'success': True,
            'servicios': comparacion,
            'analisis': analisis
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def recomendaciones_ajax(request):
    """
    Vista AJAX para obtener recomendaciones de servicios
    Usado por el chatbot (RF-007) para recomendaciones personalizadas
    """
    presupuesto = request.GET.get('presupuesto')
    tipo = request.GET.get('tipo')
    region = request.GET.get('region')
    personas = request.GET.get('personas', 1)
    
    try:
        # Filtros base
        servicios = Servicio.objects.filter(
            activo=True,
            disponible=True
        ).select_related('destino', 'categoria')
        
        # Aplicar filtros
        if presupuesto:
            try:
                servicios = servicios.filter(precio__lte=float(presupuesto))
            except ValueError:
                pass
        
        if tipo:
            servicios = servicios.filter(tipo=tipo)
        
        if region:
            servicios = servicios.filter(destino__region=region)
        
        if personas:
            try:
                servicios = servicios.filter(capacidad_maxima__gte=int(personas))
            except ValueError:
                pass
        
        # Ordenar por calificación y limitar resultados
        servicios = servicios.order_by('-calificacion_promedio', '-total_calificaciones')[:8]
        
        recomendaciones = [{
            'id': s.id,
            'nombre': s.nombre,
            'tipo': s.get_tipo_display(),
            'precio': float(s.precio),
            'calificacion': float(s.calificacion_promedio),
            'destino': s.destino.nombre,
            'region': s.destino.region,
            'descripcion_corta': s.descripcion[:150] + '...' if len(s.descripcion) > 150 else s.descripcion,
            'url': f'/servicios/{s.id}/'
        } for s in servicios]
        
        return JsonResponse({
            'success': True,
            'recomendaciones': recomendaciones,
            'total_encontrados': len(recomendaciones),
            'filtros_aplicados': {
                'presupuesto': presupuesto,
                'tipo': tipo,
                'region': region,
                'personas': personas
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)