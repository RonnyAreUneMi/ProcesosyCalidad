from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from .models import Servicio, ImagenServicio, HorarioAtencion
from apps.destinos.models import Destino, Categoria
from apps.usuarios.models import Usuario
from datetime import date, timedelta, datetime
import logging
from functools import wraps

logger = logging.getLogger(__name__)

# ==================== CONSTANTES ====================
class ServicioConstants:
    """Constantes centralizadas para evitar magic numbers"""
    ITEMS_PER_PAGE = 12
    ITEMS_PER_PAGE_MIS_SERVICIOS = 10
    MAX_RESULTADOS_AJAX = 10
    MAX_RESULTADOS_CERCANOS = 20
    MAX_RECOMENDACIONES = 8
    RADIO_BUSQUEDA_DEFAULT_KM = 10
    MAX_SERVICIOS_RELACIONADOS = 4
    MAX_CALIFICACIONES_MOSTRADAS = 10
    
    # Validación de coordenadas Ecuador
    LATITUD_MIN = Decimal('-5')
    LATITUD_MAX = Decimal('2')
    LONGITUD_MIN = Decimal('-92')
    LONGITUD_MAX = Decimal('-75')
    
    REGIONES = [
        ('costa', 'Costa'),
        ('sierra', 'Sierra'),
        ('oriente', 'Oriente (Amazonía)'),
        ('galapagos', 'Galápagos'),
    ]
    
    OPCIONES_ORDEN = {
        'precio_asc': 'precio',
        'precio_desc': '-precio',
        'calificacion': '-calificacion_promedio',
        'nombre': 'nombre',
        'recientes': '-fecha_creacion'
    }
    
    HORARIO_SEMANA = 'lunes_viernes'
    HORARIO_FIN_SEMANA = 'sabado_domingo'


# ==================== DECORADORES ====================
def rol_requerido(roles_permitidos):
    """
    Decorador mejorado para verificar roles con logging
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                logger.warning(f'Intento de acceso no autenticado a {view_func.__name__}')
                messages.warning(request, 'Debes iniciar sesión para acceder.')
                return redirect('usuarios:login')
            
            if not hasattr(request.user, 'rol') or request.user.rol is None:
                logger.error(f'Usuario {request.user.id} sin rol asignado')
                messages.error(request, 'Tu cuenta no tiene un rol asignado.')
                return redirect('home')
            
            if request.user.rol.nombre not in roles_permitidos:
                logger.warning(f'Usuario {request.user.id} sin permisos para {view_func.__name__}')
                messages.error(request, 'No tienes permisos para acceder a esta página.')
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ==================== SERVICIOS DE VALIDACIÓN ====================
class CoordenadasValidator:
    """Validador de coordenadas geográficas"""
    
    @staticmethod
    def validar_coordenadas(latitud_str, longitud_str):
        """
        Valida y convierte coordenadas a Decimal
        Returns: (lat, lng, error_message)
        """
        if not latitud_str or not longitud_str:
            return None, None, 'Las coordenadas son obligatorias. Selecciona la ubicación en el mapa.'
        
        try:
            lat = Decimal(str(latitud_str).strip())
            lng = Decimal(str(longitud_str).strip())
            
            if not (ServicioConstants.LATITUD_MIN <= lat <= ServicioConstants.LATITUD_MAX):
                return None, None, f'La latitud debe estar entre -5° y 2° (Ecuador). Valor: {lat}'
            
            if not (ServicioConstants.LONGITUD_MIN <= lng <= ServicioConstants.LONGITUD_MAX):
                return None, None, f'La longitud debe estar entre -92° y -75° (Ecuador). Valor: {lng}'
            
            return lat, lng, None
            
        except (ValueError, TypeError, InvalidOperation):
            return None, None, f'Coordenadas inválidas: {latitud_str}, {longitud_str}'


class PermisoServicioValidator:
    """Validador de permisos sobre servicios"""
    
    @staticmethod
    def puede_editar(usuario, servicio):
        """Verifica si un usuario puede editar un servicio"""
        if usuario.rol.nombre == 'administrador':
            return True
        if usuario.rol.nombre == 'proveedor' and servicio.proveedor == usuario:
            return True
        return False
    
    @staticmethod
    def validar_permiso_edicion(request, servicio, redirect_url='servicios:listar_servicios'):
        """
        Valida permiso y redirige si no tiene acceso
        Returns: None si tiene permiso, HttpResponse si no lo tiene
        """
        if not PermisoServicioValidator.puede_editar(request.user, servicio):
            logger.warning(
                f'Usuario {request.user.id} intentó editar servicio {servicio.id} sin permisos'
            )
            messages.error(request, 'No tienes permiso para editar este servicio')
            return redirect(redirect_url)
        return None


# ==================== SERVICIOS DE DATOS ====================
class ServicioQueryService:
    """Servicio para consultas optimizadas de servicios"""
    
    @staticmethod
    def get_servicios_base():
        """Query base optimizado para listado de servicios"""
        return Servicio.objects.filter(
            activo=True, 
            disponible=True
        ).select_related(
            'destino', 'categoria', 'proveedor'
        ).prefetch_related('horarios')
    
    @staticmethod
    def get_stats_por_tipo(servicios_base):
        """Calcula estadísticas por tipo de servicio"""
        stats = {}
        for tipo_code, _ in Servicio.TIPO_SERVICIO_CHOICES:
            stats[tipo_code] = servicios_base.filter(tipo=tipo_code).count()
        return stats
    
    @staticmethod
    def aplicar_filtros(servicios, filtros_dict):
        """
        Aplica filtros a un queryset de servicios
        Returns: (servicios_filtrados, filtros_activos_count)
        """
        filtros_activos = 0
        
        # Filtro por tipo
        if filtros_dict.get('tipo'):
            servicios = servicios.filter(tipo=filtros_dict['tipo'])
            filtros_activos += 1
        
        # Filtro por destino
        if filtros_dict.get('destino_id'):
            servicios = servicios.filter(destino_id=filtros_dict['destino_id'])
            filtros_activos += 1
        
        # Filtro por categoría
        if filtros_dict.get('categoria_id'):
            servicios = servicios.filter(categoria_id=filtros_dict['categoria_id'])
            filtros_activos += 1
        
        # Filtro por región
        if filtros_dict.get('region'):
            servicios = servicios.filter(destino__region=filtros_dict['region'])
            filtros_activos += 1
        
        # Filtro por precio mínimo
        if filtros_dict.get('precio_min'):
            try:
                precio_min_val = float(filtros_dict['precio_min'])
                servicios = servicios.filter(precio__gte=precio_min_val)
                filtros_activos += 1
            except (ValueError, TypeError):
                logger.warning(f"Precio mínimo inválido: {filtros_dict['precio_min']}")
        
        # Filtro por precio máximo
        if filtros_dict.get('precio_max'):
            try:
                precio_max_val = float(filtros_dict['precio_max'])
                servicios = servicios.filter(precio__lte=precio_max_val)
                filtros_activos += 1
            except (ValueError, TypeError):
                logger.warning(f"Precio máximo inválido: {filtros_dict['precio_max']}")
        
        # Filtro por calificación
        if filtros_dict.get('calificacion_min'):
            try:
                cal_min = float(filtros_dict['calificacion_min'])
                servicios = servicios.filter(calificacion_promedio__gte=cal_min)
                filtros_activos += 1
            except (ValueError, TypeError):
                logger.warning(f"Calificación inválida: {filtros_dict['calificacion_min']}")
        
        # Filtro abierto ahora
        if filtros_dict.get('abierto_ahora'):
            servicios_abiertos = [s.id for s in servicios if s.esta_abierto_ahora()]
            servicios = servicios.filter(id__in=servicios_abiertos)
            filtros_activos += 1
        
        # Búsqueda
        if filtros_dict.get('busqueda'):
            servicios = servicios.filter(
                Q(nombre__icontains=filtros_dict['busqueda']) |
                Q(descripcion__icontains=filtros_dict['busqueda']) |
                Q(direccion__icontains=filtros_dict['busqueda']) |
                Q(zona_referencia__icontains=filtros_dict['busqueda']) |
                Q(destino__nombre__icontains=filtros_dict['busqueda']) |
                Q(destino__descripcion__icontains=filtros_dict['busqueda']) |
                Q(categoria__nombre__icontains=filtros_dict['busqueda'])
            )
            filtros_activos += 1
        
        return servicios, filtros_activos


class HorarioService:
    """Servicio para manejo de horarios"""
    
    @staticmethod
    def crear_horario(servicio, tipo_horario, hora_apertura, hora_cierre, cerrado, notas=''):
        """Crea un horario de atención"""
        if cerrado:
            return HorarioAtencion.objects.create(
                servicio=servicio,
                tipo_horario=tipo_horario,
                hora_apertura='00:00',
                hora_cierre='00:00',
                cerrado=True,
                notas=notas or None
            )
        
        if hora_apertura and hora_cierre:
            return HorarioAtencion.objects.create(
                servicio=servicio,
                tipo_horario=tipo_horario,
                hora_apertura=hora_apertura,
                hora_cierre=hora_cierre,
                cerrado=False,
                notas=notas or None
            )
        return None
    
    @staticmethod
    def actualizar_horarios(servicio, datos_horarios):
        """Actualiza todos los horarios de un servicio"""
        HorarioAtencion.objects.filter(servicio=servicio).delete()
        
        # Horario entre semana
        HorarioService.crear_horario(
            servicio,
            ServicioConstants.HORARIO_SEMANA,
            datos_horarios.get('hora_apertura_semana'),
            datos_horarios.get('hora_cierre_semana'),
            datos_horarios.get('cerrado_semana', False),
            datos_horarios.get('notas_semana', '')
        )
        
        # Horario fin de semana
        HorarioService.crear_horario(
            servicio,
            ServicioConstants.HORARIO_FIN_SEMANA,
            datos_horarios.get('hora_apertura_finde'),
            datos_horarios.get('hora_cierre_finde'),
            datos_horarios.get('cerrado_finde', False),
            datos_horarios.get('notas_finde', '')
        )


class ImagenService:
    """Servicio para manejo de imágenes"""
    
    @staticmethod
    def procesar_imagenes(servicio, archivos_imagenes, orden_inicial=0):
        """Procesa y guarda múltiples imágenes"""
        imagenes_creadas = []
        for idx, imagen in enumerate(archivos_imagenes):
            img = ImagenServicio.objects.create(
                servicio=servicio,
                imagen=imagen,
                es_principal=(idx == 0 and orden_inicial == 0),
                orden=orden_inicial + idx
            )
            imagenes_creadas.append(img)
        return imagenes_creadas


class CalificacionService:
    """Servicio para manejo de calificaciones"""
    
    @staticmethod
    def get_datos_calificaciones(servicio, usuario=None):
        """
        Obtiene datos completos de calificaciones
        Returns: dict con calificaciones, stats, permisos
        """
        datos = {
            'calificaciones_lista': [],
            'stats_calificaciones': {'5': 0, '4': 0, '3': 0, '2': 0, '1': 0},
            'puede_calificar': False,
            'ya_califico': False,
            'calificacion_usuario': None,
        }
        
        try:
            from apps.calificaciones.models import Calificacion
            
            calificaciones_queryset = Calificacion.objects.filter(
                servicio=servicio,
                activo=True
            ).select_related('usuario').prefetch_related('respuesta')
            
            # Estadísticas
            for puntuacion in range(1, 6):
                datos['stats_calificaciones'][str(puntuacion)] = \
                    calificaciones_queryset.filter(puntuacion=puntuacion).count()
            
            # Lista de calificaciones
            datos['calificaciones_lista'] = list(
                calificaciones_queryset.order_by('-fecha_creacion')[:ServicioConstants.MAX_CALIFICACIONES_MOSTRADAS]
            )
            
            # Permisos de calificación
            if usuario and usuario.is_authenticated:
                if hasattr(usuario, 'rol') and usuario.rol.nombre == 'turista':
                    try:
                        from apps.reservas.models import Reserva
                        tiene_reserva_completada = Reserva.objects.filter(
                            usuario=usuario,
                            servicio=servicio,
                            estado='completada'
                        ).exists()
                    except ImportError:
                        tiene_reserva_completada = False
                    
                    if tiene_reserva_completada:
                        datos['calificacion_usuario'] = Calificacion.objects.filter(
                            usuario=usuario,
                            servicio=servicio,
                            activo=True
                        ).first()
                        
                        datos['ya_califico'] = datos['calificacion_usuario'] is not None
                        datos['puede_calificar'] = not datos['ya_califico']
        
        except ImportError:
            logger.warning('Módulo de calificaciones no disponible')
        
        return datos


class CarritoService:
    """Servicio para verificar items en carrito"""
    
    @staticmethod
    def get_info_carrito(usuario, servicio):
        """
        Obtiene información del carrito para un servicio
        Returns: dict con en_carrito y cantidad
        """
        info = {
            'en_carrito': False,
            'cantidad_en_carrito': 0
        }
        
        if not usuario or not usuario.is_authenticated:
            return info
        
        try:
            from apps.reservas.models import ItemCarrito
            item_carrito = ItemCarrito.objects.filter(
                usuario=usuario,
                servicio=servicio
            ).first()
            
            if item_carrito:
                info['en_carrito'] = True
                info['cantidad_en_carrito'] = item_carrito.cantidad_personas
        
        except ImportError:
            logger.warning('Módulo de reservas no disponible')
        
        return info


class ProveedorService:
    """Servicio para manejo de proveedores"""
    
    @staticmethod
    def determinar_proveedor(request, proveedor_id=None):
        """
        Determina el proveedor según el rol del usuario
        Returns: (proveedor, error_message)
        """
        if request.user.rol.nombre == 'proveedor':
            return request.user, None
        
        if request.user.rol.nombre == 'administrador':
            if proveedor_id:
                try:
                    proveedor = Usuario.objects.get(
                        id=proveedor_id,
                        rol__nombre='proveedor',
                        is_active=True
                    )
                    return proveedor, None
                except Usuario.DoesNotExist:
                    return None, 'Proveedor no encontrado'
            return None, 'Debe seleccionar un proveedor'
        
        return None, 'Rol no autorizado'


# ==================== UTILIDADES ====================
def construir_query_string_filtros(filtros_dict):
    """Construye query string para paginación con filtros"""
    params = []
    mapeo = {
        'busqueda': 'q',
        'tipo': 'tipo',
        'destino_id': 'destino',
        'categoria_id': 'categoria',
        'region': 'region',
        'precio_min': 'precio_min',
        'precio_max': 'precio_max',
        'calificacion_min': 'calificacion',
        'orden': 'orden',
    }
    
    for key, param_name in mapeo.items():
        if filtros_dict.get(key):
            params.append(f'{param_name}={filtros_dict[key]}')
    
    if filtros_dict.get('abierto_ahora'):
        params.append('abierto_ahora=on')
    
    return '&' + '&'.join(params) if params else ''


def calcular_distancia_haversine(lat1, lon1, lat2, lon2):
    """Calcula distancia entre dos puntos en km usando fórmula de Haversine"""
    from math import radians, cos, sin, asin, sqrt
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c


# ==================== VISTAS PRINCIPALES ====================
def listar_servicios(request):
    """
    Vista para listar servicios con filtros y búsqueda mejorados
    RF-002: Búsqueda y Filtrado por Región
    """
    servicios_base = ServicioQueryService.get_servicios_base()
    stats_por_tipo = ServicioQueryService.get_stats_por_tipo(servicios_base)
    
    # Extraer filtros del request
    filtros = {
        'tipo': request.GET.get('tipo'),
        'destino_id': request.GET.get('destino'),
        'categoria_id': request.GET.get('categoria'),
        'region': request.GET.get('region'),
        'precio_min': request.GET.get('precio_min'),
        'precio_max': request.GET.get('precio_max'),
        'calificacion_min': request.GET.get('calificacion'),
        'busqueda': request.GET.get('q'),
        'abierto_ahora': request.GET.get('abierto_ahora') == 'on',
        'orden': request.GET.get('orden', 'calificacion'),
    }
    
    # Aplicar filtros
    servicios, filtros_activos = ServicioQueryService.aplicar_filtros(
        servicios_base, filtros
    )
    
    # Ordenamiento
    orden_campo = ServicioConstants.OPCIONES_ORDEN.get(
        filtros['orden'], 
        '-calificacion_promedio'
    )
    servicios = servicios.order_by(orden_campo)
    
    # Paginación
    paginator = Paginator(servicios, ServicioConstants.ITEMS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    # Datos para el template
    destinos = Destino.objects.filter(activo=True).order_by('nombre')
    categorias = Categoria.objects.filter(activo=True).order_by('nombre')
    
    context = {
        'page_obj': page_obj,
        'destinos': destinos,
        'categorias': categorias,
        'regiones': ServicioConstants.REGIONES,
        'tipos_servicio': Servicio.TIPO_SERVICIO_CHOICES,
        'total_resultados': servicios_base.count(),
        'resultados_filtrados': page_obj.paginator.count,
        'stats_por_tipo': stats_por_tipo,
        'filtros_activos': filtros_activos,
        'filtros_query': construir_query_string_filtros(filtros),
        'filtros_aplicados': filtros,
    }
    
    return render(request, 'servicios/listar.html', context)


def detalle_servicio(request, servicio_id):
    """
    Vista para mostrar el detalle completo de un servicio
    RF-003: Sistema de Reservas y RF-006: Calificaciones
    """
    servicio = get_object_or_404(
        Servicio.objects.select_related('destino', 'categoria', 'proveedor'),
        id=servicio_id,
        activo=True
    )
    
    # Imágenes
    imagenes = servicio.imagenes.all()
    imagen_principal = imagenes.filter(es_principal=True).first()
    imagenes_secundarias = imagenes.filter(es_principal=False)
    
    # Horarios
    horarios = servicio.horarios.filter(activo=True).order_by('tipo_horario')
    horario_semana = horarios.filter(tipo_horario=ServicioConstants.HORARIO_SEMANA).first()
    horario_fin_semana = horarios.filter(tipo_horario=ServicioConstants.HORARIO_FIN_SEMANA).first()
    
    # Calificaciones
    datos_calificaciones = CalificacionService.get_datos_calificaciones(
        servicio, 
        request.user if request.user.is_authenticated else None
    )
    
    # Servicios relacionados
    servicios_relacionados = Servicio.objects.filter(
        destino=servicio.destino,
        activo=True,
        disponible=True
    ).exclude(
        id=servicio.id
    ).order_by('-calificacion_promedio')[:ServicioConstants.MAX_SERVICIOS_RELACIONADOS]
    
    # Info del carrito
    info_carrito = CarritoService.get_info_carrito(request.user, servicio)
    
    # Fecha mínima para reservas
    fecha_minima = (date.today() + timedelta(days=1)).isoformat()
    
    context = {
        'servicio': servicio,
        'imagen_principal': imagen_principal,
        'imagenes_secundarias': imagenes_secundarias,
        'horario_semana': horario_semana,
        'horario_fin_semana': horario_fin_semana,
        'esta_abierto': servicio.esta_abierto_ahora(),
        'coordenadas': servicio.get_coordenadas(),
        'url_google_maps': servicio.get_url_google_maps(),
        'calificaciones': datos_calificaciones['calificaciones_lista'],
        'stats_calificaciones': datos_calificaciones['stats_calificaciones'],
        'total_calificaciones': sum(datos_calificaciones['stats_calificaciones'].values()),
        'servicios_relacionados': servicios_relacionados,
        'puede_calificar': datos_calificaciones['puede_calificar'],
        'ya_califico': datos_calificaciones['ya_califico'],
        'calificacion_usuario': datos_calificaciones['calificacion_usuario'],
        'en_carrito': info_carrito['en_carrito'],
        'cantidad_en_carrito': info_carrito['cantidad_en_carrito'],
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
            # Validar coordenadas
            lat, lng, error = CoordenadasValidator.validar_coordenadas(
                request.POST.get('latitud'),
                request.POST.get('longitud')
            )
            if error:
                messages.error(request, error)
                return redirect('servicios:crear_servicio')
            
            # Determinar proveedor
            proveedor, error = ProveedorService.determinar_proveedor(
                request,
                request.POST.get('proveedor_id')
            )
            if error:
                messages.error(request, error)
                return redirect('servicios:crear_servicio')
            
            with transaction.atomic():
                # Obtener relaciones
                destino = get_object_or_404(
                    Destino,
                    id=request.POST.get('destino'),
                    activo=True
                )
                
                categoria = None
                if request.POST.get('categoria'):
                    categoria = get_object_or_404(
                        Categoria,
                        id=request.POST.get('categoria'),
                        activo=True
                    )
                
                # Crear servicio
                servicio = Servicio.objects.create(
                    nombre=request.POST.get('nombre'),
                    descripcion=request.POST.get('descripcion'),
                    tipo=request.POST.get('tipo'),
                    precio=request.POST.get('precio'),
                    destino=destino,
                    categoria=categoria,
                    proveedor=proveedor,
                    capacidad_maxima=request.POST.get('capacidad_maxima', 1),
                    disponible=request.POST.get('disponible') == 'on',
                    direccion=request.POST.get('direccion'),
                    latitud=lat,
                    longitud=lng,
                    zona_referencia=request.POST.get('zona_referencia') or None,
                    telefono=request.POST.get('telefono'),
                    telefono_alternativo=request.POST.get('telefono_alternativo') or None,
                    email_contacto=request.POST.get('email_contacto'),
                    sitio_web=request.POST.get('sitio_web') or None,
                    whatsapp=request.POST.get('whatsapp') or None,
                )
                
                # Crear horarios
                datos_horarios = {
                    'hora_apertura_semana': request.POST.get('hora_apertura_semana'),
                    'hora_cierre_semana': request.POST.get('hora_cierre_semana'),
                    'cerrado_semana': request.POST.get('cerrado_semana') == 'on',
                    'notas_semana': request.POST.get('notas_semana', ''),
                    'hora_apertura_finde': request.POST.get('hora_apertura_finde'),
                    'hora_cierre_finde': request.POST.get('hora_cierre_finde'),
                    'cerrado_finde': request.POST.get('cerrado_finde') == 'on',
                    'notas_finde': request.POST.get('notas_finde', ''),
                }
                HorarioService.actualizar_horarios(servicio, datos_horarios)
                
                # Procesar imágenes
                imagenes = request.FILES.getlist('imagenes')
                if imagenes:
                    ImagenService.procesar_imagenes(servicio, imagenes)
                
                logger.info(f'Servicio {servicio.id} creado por usuario {request.user.id}')
                messages.success(request, f'Servicio "{servicio.nombre}" creado exitosamente')
                return redirect('servicios:detalle_servicio', servicio_id=servicio.id)
            
        except Exception as e:
            logger.error(f'Error creando servicio: {str(e)}', exc_info=True)
            messages.error(request, f'Error al crear el servicio: {str(e)}')
            return redirect('servicios:crear_servicio')
    
    # GET - Mostrar formulario
    destinos = Destino.objects.filter(activo=True).order_by('nombre')
    categorias = Categoria.objects.filter(activo=True).order_by('nombre')
    
    proveedores = None
    if request.user.rol.nombre == 'administrador':
        proveedores = Usuario.objects.filter(
            rol__nombre='proveedor',
            is_active=True
        ).order_by('nombre')
    
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
    
    # Validar permisos
    permiso_error = PermisoServicioValidator.validar_permiso_edicion(request, servicio)
    if permiso_error:
        return permiso_error
    
    if request.method == 'POST':
        try:
            # Validar coordenadas
            lat, lng, error = CoordenadasValidator.validar_coordenadas(
                request.POST.get('latitud'),
                request.POST.get('longitud')
            )
            if error:
                messages.error(request, error)
                return redirect('servicios:editar_servicio', servicio_id=servicio.id)
            
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
                servicio.zona_referencia = request.POST.get('zona_referencia') or None
                servicio.telefono = request.POST.get('telefono')
                servicio.telefono_alternativo = request.POST.get('telefono_alternativo') or None
                servicio.email_contacto = request.POST.get('email_contacto')
                servicio.sitio_web = request.POST.get('sitio_web') or None
                servicio.whatsapp = request.POST.get('whatsapp') or None
                servicio.latitud = lat
                servicio.longitud = lng
                
                # Actualizar destino y categoría
                servicio.destino = get_object_or_404(
                    Destino,
                    id=request.POST.get('destino'),
                    activo=True
                )
                
                categoria_id = request.POST.get('categoria')
                if categoria_id:
                    servicio.categoria = get_object_or_404(
                        Categoria,
                        id=categoria_id,
                        activo=True
                    )
                else:
                    servicio.categoria = None
                
                servicio.save()
                
                # Actualizar horarios
                datos_horarios = {
                    'hora_apertura_semana': request.POST.get('hora_apertura_semana'),
                    'hora_cierre_semana': request.POST.get('hora_cierre_semana'),
                    'cerrado_semana': request.POST.get('cerrado_semana') == 'on',
                    'notas_semana': request.POST.get('notas_semana', ''),
                    'hora_apertura_finde': request.POST.get('hora_apertura_finde'),
                    'hora_cierre_finde': request.POST.get('hora_cierre_finde'),
                    'cerrado_finde': request.POST.get('cerrado_finde') == 'on',
                    'notas_finde': request.POST.get('notas_finde', ''),
                }
                HorarioService.actualizar_horarios(servicio, datos_horarios)
                
                # Procesar nuevas imágenes
                imagenes = request.FILES.getlist('imagenes')
                if imagenes:
                    orden_inicial = servicio.imagenes.count()
                    ImagenService.procesar_imagenes(servicio, imagenes, orden_inicial)
                
                logger.info(f'Servicio {servicio.id} actualizado por usuario {request.user.id}')
                messages.success(request, '✅ Servicio actualizado exitosamente')
                return redirect('servicios:detalle_servicio', servicio_id=servicio.id)
            
        except Exception as e:
            logger.error(f'Error actualizando servicio {servicio_id}: {str(e)}', exc_info=True)
            messages.error(request, f'❌ Error al actualizar el servicio: {str(e)}')
    
    # GET - Mostrar formulario
    destinos = Destino.objects.filter(activo=True).order_by('nombre')
    categorias = Categoria.objects.filter(activo=True).order_by('nombre')
    
    horarios = servicio.horarios.filter(activo=True)
    horario_semana = horarios.filter(tipo_horario=ServicioConstants.HORARIO_SEMANA).first()
    horario_fin_semana = horarios.filter(tipo_horario=ServicioConstants.HORARIO_FIN_SEMANA).first()
    
    # Coordenadas para el mapa
    coordenadas = {
        'lat': float(servicio.latitud),
        'lng': float(servicio.longitud)
    }
    
    context = {
        'servicio': servicio,
        'destinos': destinos,
        'categorias': categorias,
        'tipos_servicio': Servicio.TIPO_SERVICIO_CHOICES,
        'horario_semana': horario_semana,
        'horario_fin_semana': horario_fin_semana,
        'coordenadas': coordenadas,
        'latitud_valor': str(servicio.latitud),
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
    
    # Validar permisos
    permiso_error = PermisoServicioValidator.validar_permiso_edicion(
        request, 
        servicio, 
        'servicios:mis_servicios'
    )
    if permiso_error:
        return permiso_error
    
    if request.method == 'POST':
        servicio.activo = False
        servicio.disponible = False
        servicio.save()
        
        logger.info(f'Servicio {servicio.id} eliminado por usuario {request.user.id}')
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
    ).select_related(
        'destino', 'categoria'
    ).prefetch_related('horarios').order_by('-fecha_creacion')
    
    # Estadísticas
    total_servicios = servicios.count()
    servicios_activos = servicios.filter(activo=True, disponible=True).count()
    promedio_calificacion = servicios.aggregate(
        promedio=Avg('calificacion_promedio')
    )['promedio'] or 0
    
    # Paginación
    paginator = Paginator(servicios, ServicioConstants.ITEMS_PER_PAGE_MIS_SERVICIOS)
    page_obj = paginator.get_page(request.GET.get('page'))
    
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
    if not PermisoServicioValidator.puede_editar(request.user, imagen.servicio):
        logger.warning(
            f'Usuario {request.user.id} intentó eliminar imagen {imagen_id} sin permisos'
        )
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)
    
    try:
        # Si es la imagen principal, asignar otra como principal
        if imagen.es_principal:
            otra_imagen = imagen.servicio.imagenes.exclude(id=imagen.id).first()
            if otra_imagen:
                otra_imagen.es_principal = True
                otra_imagen.save()
        
        imagen.delete()
        logger.info(f'Imagen {imagen_id} eliminada por usuario {request.user.id}')
        return JsonResponse({'success': True})
    
    except Exception as e:
        logger.error(f'Error eliminando imagen {imagen_id}: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def marcar_imagen_principal(request, imagen_id):
    """
    Vista AJAX para marcar una imagen como principal
    """
    imagen = get_object_or_404(ImagenServicio, id=imagen_id)
    
    # Verificar permisos
    if not PermisoServicioValidator.puede_editar(request.user, imagen.servicio):
        logger.warning(
            f'Usuario {request.user.id} intentó marcar imagen {imagen_id} sin permisos'
        )
        return JsonResponse({'success': False, 'error': 'Sin permisos'}, status=403)
    
    try:
        # Desmarcar todas las demás imágenes
        ImagenServicio.objects.filter(servicio=imagen.servicio).update(es_principal=False)
        
        # Marcar esta como principal
        imagen.es_principal = True
        imagen.save()
        
        logger.info(f'Imagen {imagen_id} marcada como principal por usuario {request.user.id}')
        return JsonResponse({'success': True})
    
    except Exception as e:
        logger.error(f'Error marcando imagen principal {imagen_id}: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def servicios_por_tipo(request, tipo):
    """
    Vista para listar servicios por tipo específico
    """
    # Validar tipo
    tipos_validos = dict(Servicio.TIPO_SERVICIO_CHOICES)
    if tipo not in tipos_validos:
        logger.warning(f'Tipo de servicio inválido solicitado: {tipo}')
        messages.error(request, 'Tipo de servicio no válido')
        return redirect('servicios:listar_servicios')
    
    servicios = Servicio.objects.filter(
        tipo=tipo,
        activo=True,
        disponible=True
    ).select_related(
        'destino', 'categoria', 'proveedor'
    ).prefetch_related('horarios').order_by('-calificacion_promedio')
    
    # Paginación
    paginator = Paginator(servicios, ServicioConstants.ITEMS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'tipo': tipo,
        'tipo_nombre': tipos_validos[tipo],
        'total_servicios': servicios.count(),
    }
    
    return render(request, 'servicios/por_tipo.html', context)


# ==================== VISTAS AJAX ====================
@require_http_methods(["GET"])
def buscar_servicios_ajax(request):
    """
    Vista AJAX para buscar servicios
    """
    try:
        # Extraer parámetros
        filtros = {
            'busqueda': request.GET.get('q', ''),
            'tipo': request.GET.get('tipo', ''),
            'region': request.GET.get('region', ''),
            'precio_max': request.GET.get('precio_max'),
            'abierto_ahora': request.GET.get('abierto_ahora') == 'true',
        }
        
        servicios = ServicioQueryService.get_servicios_base()
        servicios, _ = ServicioQueryService.aplicar_filtros(servicios, filtros)
        servicios = servicios.order_by('-calificacion_promedio')[:ServicioConstants.MAX_RESULTADOS_AJAX]
        
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
        logger.error(f'Error en buscar_servicios_ajax: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def estadisticas_servicios_ajax(request):
    """
    Vista AJAX para obtener estadísticas de servicios
    Usado por el chatbot para análisis comparativo (RF-007)
    """
    try:
        servicios_activos = Servicio.objects.filter(activo=True, disponible=True)
        total_servicios = servicios_activos.count()
        
        # Servicios por tipo
        servicios_por_tipo = {}
        for tipo_code, tipo_nombre in Servicio.TIPO_SERVICIO_CHOICES:
            count = servicios_activos.filter(tipo=tipo_code).count()
            servicios_por_tipo[tipo_nombre] = count
        
        # Servicios por región
        servicios_por_region = {}
        for region_code, region_nombre in ServicioConstants.REGIONES:
            count = servicios_activos.filter(destino__region=region_code).count()
            servicios_por_region[region_nombre] = count
        
        # Precio promedio por tipo
        precio_promedio_tipo = {}
        for tipo_code, tipo_nombre in Servicio.TIPO_SERVICIO_CHOICES:
            promedio = servicios_activos.filter(tipo=tipo_code).aggregate(
                promedio=Avg('precio')
            )['promedio']
            precio_promedio_tipo[tipo_nombre] = round(float(promedio or 0), 2)
        
        # Servicios mejor calificados
        mejor_calificados = servicios_activos.order_by('-calificacion_promedio')[:5]
        
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
        logger.error(f'Error en estadisticas_servicios_ajax: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def comparar_servicios_ajax(request):
    """
    Vista AJAX para comparar múltiples servicios
    Usado por el chatbot (RF-007)
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
        
        # Calcular análisis comparativo
        analisis = None
        if len(comparacion) > 1:
            precios = [s['precio'] for s in comparacion]
            
            analisis = {
                'precio_min': min(precios),
                'precio_max': max(precios),
                'precio_promedio': sum(precios) / len(precios),
                'diferencia_precio': max(precios) - min(precios),
                'mejor_calificado': max(comparacion, key=lambda x: x['calificacion']),
                'mas_economico': min(comparacion, key=lambda x: x['precio']),
                'mas_reseniado': max(comparacion, key=lambda x: x['total_calificaciones'])
            }
        
        return JsonResponse({
            'success': True,
            'servicios': comparacion,
            'analisis': analisis
        })
        
    except Exception as e:
        logger.error(f'Error en comparar_servicios_ajax: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def recomendaciones_ajax(request):
    """
    Vista AJAX para obtener recomendaciones de servicios
    Usado por el chatbot (RF-007)
    """
    try:
        # Extraer filtros
        filtros = {
            'tipo': request.GET.get('tipo'),
            'region': request.GET.get('region'),
            'precio_max': request.GET.get('presupuesto'),
            'abierto_ahora': request.GET.get('abierto_ahora') == 'true',
        }
        
        personas = request.GET.get('personas', 1)
        
        servicios = ServicioQueryService.get_servicios_base()
        servicios, _ = ServicioQueryService.aplicar_filtros(servicios, filtros)
        
        # Filtro por capacidad
        if personas:
            try:
                servicios = servicios.filter(capacidad_maxima__gte=int(personas))
            except (ValueError, TypeError):
                logger.warning(f'Valor de personas inválido: {personas}')
        
        # Ordenar y limitar
        servicios = servicios.order_by(
            '-calificacion_promedio', 
            '-total_calificaciones'
        )[:ServicioConstants.MAX_RECOMENDACIONES]
        
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
            'whatsapp': s.whatsapp,
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
                'presupuesto': request.GET.get('presupuesto'),
                'tipo': request.GET.get('tipo'),
                'region': request.GET.get('region'),
                'personas': personas,
                'abierto_ahora': filtros['abierto_ahora'],
            }
        })
        
    except Exception as e:
        logger.error(f'Error en recomendaciones_ajax: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def servicios_cercanos_ajax(request):
    """
    Vista AJAX para obtener servicios cercanos a una ubicación
    """
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    radio_km = request.GET.get('radio', ServicioConstants.RADIO_BUSQUEDA_DEFAULT_KM)
    tipo = request.GET.get('tipo', '')
    
    if not lat or not lng:
        return JsonResponse({
            'success': False,
            'error': 'Se requieren coordenadas (lat, lng)'
        }, status=400)
    
    try:
        lat_usuario = float(lat)
        lng_usuario = float(lng)
        radio = float(radio_km)
        
        servicios = ServicioQueryService.get_servicios_base()
        
        if tipo:
            servicios = servicios.filter(tipo=tipo)
        
        # Filtrar por distancia
        servicios_cercanos = []
        for s in servicios:
            distancia = calcular_distancia_haversine(
                lat_usuario, 
                lng_usuario, 
                float(s.latitud), 
                float(s.longitud)
            )
            
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
        servicios_cercanos.sort(key=lambda x: x['distancia_km'])
        
        return JsonResponse({
            'success': True,
            'servicios': servicios_cercanos[:ServicioConstants.MAX_RESULTADOS_CERCANOS],
            'total': len(servicios_cercanos),
            'radio_km': radio
        })
        
    except Exception as e:
        logger.error(f'Error en servicios_cercanos_ajax: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)