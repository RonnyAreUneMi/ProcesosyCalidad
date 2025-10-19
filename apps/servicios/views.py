from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from decimal import Decimal, InvalidOperation
from .models import Servicio, ImagenServicio, HorarioAtencion
from apps.destinos.models import Destino, Categoria
from apps.usuarios.models import Usuario
from datetime import date, timedelta, datetime


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
    servicios_base = Servicio.objects.filter(activo=True, disponible=True)
    
    stats_por_tipo = {
        'alojamiento': servicios_base.filter(tipo='alojamiento').count(),
        'tour': servicios_base.filter(tipo='tour').count(),
        'actividad': servicios_base.filter(tipo='actividad').count(),
        'transporte': servicios_base.filter(tipo='transporte').count(),
        'restaurante': servicios_base.filter(tipo='restaurante').count(),
    }
    
    servicios = servicios_base.select_related('destino', 'categoria', 'proveedor').prefetch_related('horarios')
    
    tipo = request.GET.get('tipo')
    destino_id = request.GET.get('destino')
    categoria_id = request.GET.get('categoria')
    region = request.GET.get('region')
    precio_min = request.GET.get('precio_min')
    precio_max = request.GET.get('precio_max')
    calificacion_min = request.GET.get('calificacion')
    busqueda = request.GET.get('q')
    abierto_ahora = request.GET.get('abierto_ahora') == 'on'
    
    filtros_activos = 0
    
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
    
    if abierto_ahora:
        servicios_abiertos = []
        for s in servicios:
            if s.esta_abierto_ahora():
                servicios_abiertos.append(s.id)
        servicios = servicios.filter(id__in=servicios_abiertos)
        filtros_activos += 1
    
    if busqueda:
        servicios = servicios.filter(
            Q(nombre__icontains=busqueda) |
            Q(descripcion__icontains=busqueda) |
            Q(direccion__icontains=busqueda) |
            Q(zona_referencia__icontains=busqueda) |
            Q(destino__nombre__icontains=busqueda) |
            Q(destino__descripcion__icontains=busqueda) |
            Q(categoria__nombre__icontains=busqueda)
        )
        filtros_activos += 1
    
    orden = request.GET.get('orden', 'calificacion')
    opciones_orden = {
        'precio_asc': 'precio',
        'precio_desc': '-precio',
        'calificacion': '-calificacion_promedio',
        'nombre': 'nombre',
        'recientes': '-fecha_creacion'
    }
    servicios = servicios.order_by(opciones_orden.get(orden, '-calificacion_promedio'))
    
    paginator = Paginator(servicios, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    destinos = Destino.objects.filter(activo=True).order_by('nombre')
    categorias = Categoria.objects.filter(activo=True).order_by('nombre')
    
    REGIONES = [
        ('costa', 'Costa'),
        ('sierra', 'Sierra'),
        ('oriente', 'Oriente (Amazonía)'),
        ('galapagos', 'Galápagos'),
    ]
    
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
    if abierto_ahora:
        params.append('abierto_ahora=on')
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
        'total_resultados': servicios_base.count(),
        'resultados_filtrados': page_obj.paginator.count,
        'stats_por_tipo': stats_por_tipo,
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
            'abierto_ahora': abierto_ahora,
        }
    }
    
    return render(request, 'servicios/listar.html', context)


def detalle_servicio(request, servicio_id):
    """
    Vista para mostrar el detalle completo de un servicio
    Incluye: ubicación, horarios, contacto, calificaciones
    RF-003: Sistema de Reservas y RF-006: Calificaciones
    """
    servicio = get_object_or_404(
        Servicio.objects.select_related('destino', 'categoria', 'proveedor'),
        id=servicio_id,
        activo=True
    )
    
    imagenes = servicio.imagenes.all()
    imagen_principal = imagenes.filter(es_principal=True).first()
    imagenes_secundarias = imagenes.filter(es_principal=False)
    
    horarios = servicio.horarios.filter(activo=True).order_by('tipo_horario')
    horario_semana = horarios.filter(tipo_horario='lunes_viernes').first()
    horario_fin_semana = horarios.filter(tipo_horario='sabado_domingo').first()
    
    esta_abierto = servicio.esta_abierto_ahora()
    
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
    
    try:
        from apps.calificaciones.models import Calificacion
        
        calificaciones_queryset = Calificacion.objects.filter(
            servicio=servicio,
            activo=True
        ).select_related('usuario').prefetch_related('respuesta')
        
        stats_calificaciones = {
            '5': calificaciones_queryset.filter(puntuacion=5).count(),
            '4': calificaciones_queryset.filter(puntuacion=4).count(),
            '3': calificaciones_queryset.filter(puntuacion=3).count(),
            '2': calificaciones_queryset.filter(puntuacion=2).count(),
            '1': calificaciones_queryset.filter(puntuacion=1).count(),
        }
        
        calificaciones_lista = list(calificaciones_queryset.order_by('-fecha_creacion')[:10])
        
        if request.user.is_authenticated:
            if hasattr(request.user, 'rol') and request.user.rol.nombre == 'turista':
                try:
                    from apps.reservas.models import Reserva
                    tiene_reserva_completada = Reserva.objects.filter(
                        usuario=request.user,
                        servicio=servicio,
                        estado='completada'
                    ).exists()
                except ImportError:
                    tiene_reserva_completada = False
                
                if tiene_reserva_completada:
                    calificacion_usuario = Calificacion.objects.filter(
                        usuario=request.user,
                        servicio=servicio,
                        activo=True
                    ).first()
                    
                    ya_califico = calificacion_usuario is not None
                    puede_calificar = not ya_califico
                    
    except ImportError:
        pass
    
    servicios_relacionados = Servicio.objects.filter(
        destino=servicio.destino,
        activo=True,
        disponible=True
    ).exclude(id=servicio.id).order_by('-calificacion_promedio')[:4]
    
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
        'horario_semana': horario_semana,
        'horario_fin_semana': horario_fin_semana,
        'esta_abierto': esta_abierto,
        'coordenadas': servicio.get_coordenadas(),
        'url_google_maps': servicio.get_url_google_maps(),
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
    Incluye: ubicación geográfica, horarios, contacto
    Solo para proveedores y administradores
    """
    if request.method == 'POST':
        try:
            # ========== DATOS DE UBICACIÓN ==========
            direccion = request.POST.get('direccion')
            latitud_str = request.POST.get('latitud')
            longitud_str = request.POST.get('longitud')
            zona_referencia = request.POST.get('zona_referencia', '')
            
            # Validar que las coordenadas no estén vacías
            if not latitud_str or not longitud_str:
                messages.error(request, 'Las coordenadas son obligatorias. Por favor, selecciona la ubicación en el mapa.')
                return redirect('servicios:crear_servicio')
            
            # Convertir y validar coordenadas
            try:
                lat = Decimal(str(latitud_str))
                lng = Decimal(str(longitud_str))
                
                # Validar rangos de Ecuador
                if not (Decimal('-5') <= lat <= Decimal('2')):
                    messages.error(request, f'La latitud debe estar entre -5° y 2° (rango de Ecuador). Valor recibido: {lat}')
                    return redirect('servicios:crear_servicio')
                    
                if not (Decimal('-92') <= lng <= Decimal('-75')):
                    messages.error(request, f'La longitud debe estar entre -92° y -75° (rango de Ecuador). Valor recibido: {lng}')
                    return redirect('servicios:crear_servicio')
                    
            except (ValueError, TypeError, InvalidOperation) as e:
                messages.error(request, f'Coordenadas inválidas: {latitud_str}, {longitud_str}')
                return redirect('servicios:crear_servicio')
            
            with transaction.atomic():
                # ========== DATOS BÁSICOS ==========
                nombre = request.POST.get('nombre')
                descripcion = request.POST.get('descripcion')
                tipo = request.POST.get('tipo')
                precio = request.POST.get('precio')
                destino_id = request.POST.get('destino')
                categoria_id = request.POST.get('categoria')
                capacidad_maxima = request.POST.get('capacidad_maxima', 1)
                disponible = request.POST.get('disponible') == 'on'
                
                # ========== CONTACTO ==========
                telefono = request.POST.get('telefono')
                telefono_alternativo = request.POST.get('telefono_alternativo', '')
                email_contacto = request.POST.get('email_contacto')
                sitio_web = request.POST.get('sitio_web', '')
                whatsapp = request.POST.get('whatsapp', '')
                
                # ========== HORARIOS ==========
                hora_apertura_semana = request.POST.get('hora_apertura_semana')
                hora_cierre_semana = request.POST.get('hora_cierre_semana')
                cerrado_semana = request.POST.get('cerrado_semana') == 'on'
                notas_semana = request.POST.get('notas_semana', '')
                
                hora_apertura_finde = request.POST.get('hora_apertura_finde')
                hora_cierre_finde = request.POST.get('hora_cierre_finde')
                cerrado_finde = request.POST.get('cerrado_finde') == 'on'
                notas_finde = request.POST.get('notas_finde', '')
                
                # Validaciones básicas
                campos_obligatorios = [
                    nombre, descripcion, tipo, precio, destino_id,
                    direccion, telefono, email_contacto
                ]
                
                if not all(campos_obligatorios):
                    messages.error(request, 'Todos los campos obligatorios deben ser completados')
                    return redirect('servicios:crear_servicio')
                
                # Obtener relaciones
                destino = get_object_or_404(Destino, id=destino_id, activo=True)
                
                categoria = None
                if categoria_id:
                    categoria = get_object_or_404(Categoria, id=categoria_id, activo=True)
                
                # Determinar el proveedor
                if request.user.rol.nombre == 'proveedor':
                    proveedor = request.user
                else:
                    proveedor_id = request.POST.get('proveedor_id')
                    if proveedor_id:
                        proveedor = get_object_or_404(Usuario, id=proveedor_id, rol__nombre='proveedor')
                    else:
                        messages.error(request, 'Debe seleccionar un proveedor')
                        return redirect('servicios:crear_servicio')
                
                # ========== CREAR EL SERVICIO ==========
                servicio = Servicio.objects.create(
                    nombre=nombre,
                    descripcion=descripcion,
                    tipo=tipo,
                    precio=precio,
                    destino=destino,
                    categoria=categoria,
                    proveedor=proveedor,
                    capacidad_maxima=capacidad_maxima,
                    disponible=disponible,
                    direccion=direccion,
                    latitud=lat,
                    longitud=lng,
                    zona_referencia=zona_referencia if zona_referencia else None,
                    telefono=telefono,
                    telefono_alternativo=telefono_alternativo if telefono_alternativo else None,
                    email_contacto=email_contacto,
                    sitio_web=sitio_web if sitio_web else None,
                    whatsapp=whatsapp if whatsapp else None,
                )
                
                # ========== CREAR HORARIOS ==========
                if not cerrado_semana and hora_apertura_semana and hora_cierre_semana:
                    HorarioAtencion.objects.create(
                        servicio=servicio,
                        tipo_horario='lunes_viernes',
                        hora_apertura=hora_apertura_semana,
                        hora_cierre=hora_cierre_semana,
                        cerrado=False,
                        notas=notas_semana if notas_semana else None
                    )
                elif cerrado_semana:
                    HorarioAtencion.objects.create(
                        servicio=servicio,
                        tipo_horario='lunes_viernes',
                        hora_apertura='00:00',
                        hora_cierre='00:00',
                        cerrado=True,
                        notas=notas_semana if notas_semana else None
                    )
                
                if not cerrado_finde and hora_apertura_finde and hora_cierre_finde:
                    HorarioAtencion.objects.create(
                        servicio=servicio,
                        tipo_horario='sabado_domingo',
                        hora_apertura=hora_apertura_finde,
                        hora_cierre=hora_cierre_finde,
                        cerrado=False,
                        notas=notas_finde if notas_finde else None
                    )
                elif cerrado_finde:
                    HorarioAtencion.objects.create(
                        servicio=servicio,
                        tipo_horario='sabado_domingo',
                        hora_apertura='00:00',
                        hora_cierre='00:00',
                        cerrado=True,
                        notas=notas_finde if notas_finde else None
                    )
                
                # ========== PROCESAR IMÁGENES ==========
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
    ✅ CORREGIDO: Muestra correctamente precio y coordenadas en el formulario
    """
    servicio = get_object_or_404(Servicio, id=servicio_id)
    
    if request.user.rol.nombre == 'proveedor' and servicio.proveedor != request.user:
        messages.error(request, 'No tienes permiso para editar este servicio')
        return redirect('servicios:listar_servicios')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Actualizar datos básicos
                servicio.nombre = request.POST.get('nombre')
                servicio.descripcion = request.POST.get('descripcion')
                servicio.tipo = request.POST.get('tipo')
                servicio.precio = request.POST.get('precio')
                servicio.capacidad_maxima = request.POST.get('capacidad_maxima', 1)
                servicio.disponible = request.POST.get('disponible') == 'on'
                
                # Actualizar ubicación y contacto
                servicio.direccion = request.POST.get('direccion')
                servicio.zona_referencia = request.POST.get('zona_referencia', '') or None
                servicio.telefono = request.POST.get('telefono')
                servicio.telefono_alternativo = request.POST.get('telefono_alternativo', '') or None
                servicio.email_contacto = request.POST.get('email_contacto')
                servicio.sitio_web = request.POST.get('sitio_web', '') or None
                servicio.whatsapp = request.POST.get('whatsapp', '') or None
                
                # ✅ CORREGIDO: Actualizar coordenadas con validación
                latitud_str = request.POST.get('latitud')
                longitud_str = request.POST.get('longitud')
                
                if latitud_str and longitud_str:
                    try:
                        # Convertir a string primero para evitar problemas de precisión
                        lat = Decimal(str(latitud_str).strip())
                        lng = Decimal(str(longitud_str).strip())
                        
                        # Validar rangos
                        if not (Decimal('-5') <= lat <= Decimal('2')):
                            messages.error(request, f'La latitud debe estar entre -5° y 2° (Ecuador). Valor: {lat}')
                            return redirect('servicios:editar_servicio', servicio_id=servicio.id)
                            
                        if not (Decimal('-92') <= lng <= Decimal('-75')):
                            messages.error(request, f'La longitud debe estar entre -92° y -75° (Ecuador). Valor: {lng}')
                            return redirect('servicios:editar_servicio', servicio_id=servicio.id)
                        
                        # ✅ Asignar coordenadas (Django las guardará con 8 decimales)
                        servicio.latitud = lat
                        servicio.longitud = lng
                        
                    except (ValueError, InvalidOperation) as e:
                        messages.error(request, f'Coordenadas inválidas: {latitud_str}, {longitud_str}')
                        return redirect('servicios:editar_servicio', servicio_id=servicio.id)
                else:
                    messages.error(request, 'Las coordenadas son obligatorias')
                    return redirect('servicios:editar_servicio', servicio_id=servicio.id)
                
                # Actualizar destino y categoría
                destino_id = request.POST.get('destino')
                servicio.destino = get_object_or_404(Destino, id=destino_id, activo=True)
                
                categoria_id = request.POST.get('categoria')
                if categoria_id:
                    servicio.categoria = get_object_or_404(Categoria, id=categoria_id, activo=True)
                else:
                    servicio.categoria = None
                
                servicio.save()
                
                # Actualizar horarios
                HorarioAtencion.objects.filter(servicio=servicio).delete()
                
                hora_apertura_semana = request.POST.get('hora_apertura_semana')
                hora_cierre_semana = request.POST.get('hora_cierre_semana')
                cerrado_semana = request.POST.get('cerrado_semana') == 'on'
                notas_semana = request.POST.get('notas_semana', '')
                
                if not cerrado_semana and hora_apertura_semana and hora_cierre_semana:
                    HorarioAtencion.objects.create(
                        servicio=servicio,
                        tipo_horario='lunes_viernes',
                        hora_apertura=hora_apertura_semana,
                        hora_cierre=hora_cierre_semana,
                        cerrado=False,
                        notas=notas_semana if notas_semana else None
                    )
                elif cerrado_semana:
                    HorarioAtencion.objects.create(
                        servicio=servicio,
                        tipo_horario='lunes_viernes',
                        hora_apertura='00:00',
                        hora_cierre='00:00',
                        cerrado=True,
                        notas=notas_semana if notas_semana else None
                    )
                
                hora_apertura_finde = request.POST.get('hora_apertura_finde')
                hora_cierre_finde = request.POST.get('hora_cierre_finde')
                cerrado_finde = request.POST.get('cerrado_finde') == 'on'
                notas_finde = request.POST.get('notas_finde', '')
                
                if not cerrado_finde and hora_apertura_finde and hora_cierre_finde:
                    HorarioAtencion.objects.create(
                        servicio=servicio,
                        tipo_horario='sabado_domingo',
                        hora_apertura=hora_apertura_finde,
                        hora_cierre=hora_cierre_finde,
                        cerrado=False,
                        notas=notas_finde if notas_finde else None
                    )
                elif cerrado_finde:
                    HorarioAtencion.objects.create(
                        servicio=servicio,
                        tipo_horario='sabado_domingo',
                        hora_apertura='00:00',
                        hora_cierre='00:00',
                        cerrado=True,
                        notas=notas_finde if notas_finde else None
                    )
                
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
                
                messages.success(request, '✅ Servicio actualizado exitosamente')
                return redirect('servicios:detalle_servicio', servicio_id=servicio.id)
            
        except Exception as e:
            messages.error(request, f'❌ Error al actualizar el servicio: {str(e)}')
            import traceback
            print(traceback.format_exc())
    
    # ✅ GET - Mostrar formulario con datos (CORREGIDO)
    destinos = Destino.objects.filter(activo=True).order_by('nombre')
    categorias = Categoria.objects.filter(activo=True).order_by('nombre')
    
    horarios = servicio.horarios.filter(activo=True)
    horario_semana = horarios.filter(tipo_horario='lunes_viernes').first()
    horario_fin_semana = horarios.filter(tipo_horario='sabado_domingo').first()
    
    # ✅ CRÍTICO: Convertir coordenadas a float para el template
    coordenadas = {
        'lat': float(servicio.latitud),
        'lng': float(servicio.longitud)
    }
    
    # ✅ Datos completos para el formulario
    context = {
        'servicio': servicio,
        'destinos': destinos,
        'categorias': categorias,
        'tipos_servicio': Servicio.TIPO_SERVICIO_CHOICES,
        'horario_semana': horario_semana,
        'horario_fin_semana': horario_fin_semana,
        'coordenadas': coordenadas,
        # ✅ NUEVO: Valores individuales para los inputs
        'latitud_valor': str(servicio.latitud),  # String para mantener precisión
        'longitud_valor': str(servicio.longitud),
        'precio_valor': str(servicio.precio),
    }
    
    return render(request, 'servicios/editar.html', context)


@login_required
@rol_requerido(['proveedor', 'administrador'])
def eliminar_servicio(request, servicio_id):
    """
    Vista para eliminar (desactivar) un servicio
    """
    servicio = get_object_or_404(Servicio, id=servicio_id)
    
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
    ).select_related('destino', 'categoria').prefetch_related('horarios').order_by('-fecha_creacion')
    
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
    ).select_related('destino', 'categoria', 'proveedor').prefetch_related('horarios').order_by('-calificacion_promedio')
    
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
    Vista AJAX para buscar servicios
    Incluye búsqueda por ubicación y horarios
    """
    q = request.GET.get('q', '')
    tipo = request.GET.get('tipo', '')
    region = request.GET.get('region', '')
    precio_max = request.GET.get('precio_max')
    abierto_ahora = request.GET.get('abierto_ahora') == 'true'
    
    try:
        servicios = Servicio.objects.filter(
            activo=True,
            disponible=True
        ).select_related('destino', 'categoria').prefetch_related('horarios')
        
        # Búsqueda general (incluye ubicación)
        if q:
            servicios = servicios.filter(
                Q(nombre__icontains=q) |
                Q(descripcion__icontains=q) |
                Q(direccion__icontains=q) |
                Q(zona_referencia__icontains=q) |
                Q(destino__nombre__icontains=q) |
                Q(destino__provincia__icontains=q)
            )
        
        # Filtro por tipo
        if tipo:
            servicios = servicios.filter(tipo=tipo)
        
        # Filtro por región
        if region:
            servicios = servicios.filter(destino__region__iexact=region)
        
        # Filtro por precio
        if precio_max:
            try:
                servicios = servicios.filter(precio__lte=float(precio_max))
            except ValueError:
                pass
        
        # Filtro de abierto ahora
        if abierto_ahora:
            servicios_abiertos = []
            for s in servicios:
                if s.esta_abierto_ahora():
                    servicios_abiertos.append(s.id)
            servicios = servicios.filter(id__in=servicios_abiertos)
        
        # Ordenar y limitar
        servicios = servicios.order_by('-calificacion_promedio')[:10]
        
        # Serializar resultados
        resultados = [{
            'id': s.id,
            'nombre': s.nombre,
            'tipo': s.get_tipo_display(),
            'precio': float(s.precio),
            'calificacion': float(s.calificacion_promedio),
            'destino': s.destino.nombre,
            'region': s.destino.region,
            'direccion': s.direccion,
            'telefono': s.telefono,
            'latitud': float(s.latitud),
            'longitud': float(s.longitud),
            'esta_abierto': s.esta_abierto_ahora(),
            'url': f'/servicios/{s.id}/',
            'url_google_maps': s.get_url_google_maps(),
        } for s in servicios]
        
        return JsonResponse({
            'success': True,
            'servicios': resultados,
            'total': len(resultados)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


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
            'destino': s.destino.nombre,
            'direccion': s.direccion,
            'telefono': s.telefono,
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
    Incluye comparación de ubicación y contacto
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
        ).select_related('destino', 'categoria').prefetch_related('horarios')
        
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
            'direccion': s.direccion,
            'telefono': s.telefono,
            'email': s.email_contacto,
            'latitud': float(s.latitud),
            'longitud': float(s.longitud),
            'esta_abierto': s.esta_abierto_ahora(),
            'url': f'/servicios/{s.id}/',
            'url_google_maps': s.get_url_google_maps(),
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
    abierto_ahora = request.GET.get('abierto_ahora') == 'true'
    
    try:
        # Filtros base
        servicios = Servicio.objects.filter(
            activo=True,
            disponible=True
        ).select_related('destino', 'categoria').prefetch_related('horarios')
        
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
        
        # Filtro de abierto ahora
        if abierto_ahora:
            servicios_abiertos = []
            for s in servicios:
                if s.esta_abierto_ahora():
                    servicios_abiertos.append(s.id)
            servicios = servicios.filter(id__in=servicios_abiertos)
        
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
            'direccion': s.direccion,
            'telefono': s.telefono,
            'whatsapp': s.whatsapp if s.whatsapp else None,
            'latitud': float(s.latitud),
            'longitud': float(s.longitud),
            'esta_abierto': s.esta_abierto_ahora(),
            'url': f'/servicios/{s.id}/',
            'url_google_maps': s.get_url_google_maps(),
        } for s in servicios]
        
        return JsonResponse({
            'success': True,
            'recomendaciones': recomendaciones,
            'total_encontrados': len(recomendaciones),
            'filtros_aplicados': {
                'presupuesto': presupuesto,
                'tipo': tipo,
                'region': region,
                'personas': personas,
                'abierto_ahora': abierto_ahora,
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def servicios_cercanos_ajax(request):
    """
    Vista AJAX para obtener servicios cercanos a una ubicación
    Usado por el chatbot y búsqueda por mapa
    """
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    radio_km = request.GET.get('radio', 10)  # Radio por defecto 10km
    tipo = request.GET.get('tipo', '')
    
    if not lat or not lng:
        return JsonResponse({
            'success': False,
            'error': 'Se requieren coordenadas (lat, lng)'
        }, status=400)
    
    try:
        from math import radians, cos, sin, asin, sqrt
        
        def haversine(lat1, lon1, lat2, lon2):
            """Calcular distancia entre dos puntos en km"""
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            km = 6371 * c
            return km
        
        lat_usuario = float(lat)
        lng_usuario = float(lng)
        radio = float(radio_km)
        
        servicios = Servicio.objects.filter(
            activo=True,
            disponible=True
        ).select_related('destino', 'categoria').prefetch_related('horarios')
        
        if tipo:
            servicios = servicios.filter(tipo=tipo)
        
        # Filtrar por distancia
        servicios_cercanos = []
        for s in servicios:
            distancia = haversine(lat_usuario, lng_usuario, float(s.latitud), float(s.longitud))
            if distancia <= radio:
                servicios_cercanos.append({
                    'id': s.id,
                    'nombre': s.nombre,
                    'tipo': s.get_tipo_display(),
                    'precio': float(s.precio),
                    'calificacion': float(s.calificacion_promedio),
                    'direccion': s.direccion,
                    'telefono': s.telefono,
                    'latitud': float(s.latitud),
                    'longitud': float(s.longitud),
                    'distancia_km': round(distancia, 2),
                    'esta_abierto': s.esta_abierto_ahora(),
                    'url': f'/servicios/{s.id}/',
                    'url_google_maps': s.get_url_google_maps(),
                })
        
        # Ordenar por distancia
        servicios_cercanos.sort(key=lambda x: x['distancia_km'])
        
        return JsonResponse({
            'success': True,
            'servicios': servicios_cercanos[:20],  # Limitar a 20 resultados
            'total': len(servicios_cercanos),
            'radio_km': radio
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)