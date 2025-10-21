from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils.html import escape
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple, Any
import json
import logging

from .models import Destino, Categoria, ImagenDestino, AtraccionTuristica
from apps.destinos.provincias_cantones import get_provincias, get_cantones, get_provincias_cantones_json

logger = logging.getLogger(__name__)


"""
================================================================================
UTILIDADES Y VALIDADORES
================================================================================
"""

class InputValidator:
    """
    Validador centralizado para sanitización de inputs según ISO/IEC 27002.
    """
    
    @staticmethod
    def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
        if not value:
            return ''
        cleaned = escape(str(value).strip())
        return cleaned[:max_length] if max_length else cleaned
    
    @staticmethod
    def validate_numeric(value: str, min_val: float = 0, 
                        max_val: Optional[float] = None) -> Optional[float]:
        if not value:
            return None
        try:
            num = float(value.strip())
            if num < min_val or (max_val and num > max_val):
                return None
            return num
        except (ValueError, TypeError, InvalidOperation):
            return None
    
    @staticmethod
    def validate_coordinates(lat: str, lon: str) -> Tuple[Optional[float], Optional[float]]:
        try:
            lat_val = float(lat.strip())
            lon_val = float(lon.strip())
            if -90 <= lat_val <= 90 and -180 <= lon_val <= 180:
                return lat_val, lon_val
        except (ValueError, TypeError):
            pass
        return None, None
    
    @staticmethod
    def validate_price_range(min_price: str, max_price: str) -> Tuple[Optional[float], Optional[float]]:
        try:
            min_val = float(min_price.strip())
            max_val = float(max_price.strip())
            if min_val >= 0 and max_val >= 0 and min_val <= max_val:
                return min_val, max_val
        except (ValueError, TypeError):
            pass
        return None, None
    
    @staticmethod
    def validate_image(image_file) -> Tuple[bool, str]:
        if not image_file:
            return True, ''
        
        valid_formats = ['image/jpeg', 'image/png', 'image/webp']
        if image_file.content_type not in valid_formats:
            return False, 'Formato de imagen no válido. Usa JPG, PNG o WEBP'
        
        max_size = 5 * 1024 * 1024
        if image_file.size > max_size:
            return False, 'La imagen no puede exceder 5MB'
        
        return True, ''


class QueryHelper:
    """
    Helper para construcción de queries optimizadas.
    Centraliza lógica de consultas a la base de datos.
    """
    
    @staticmethod
    def get_active_destinations_query():
        return Destino.objects.filter(activo=True).select_related('categoria')
    
    @staticmethod
    def apply_search_filters(queryset, filters: Dict[str, str]):
        if filters.get('region'):
            queryset = queryset.filter(region=filters['region'])
        
        if filters.get('categoria_id'):
            categoria_id = InputValidator.validate_numeric(filters['categoria_id'], min_val=1)
            if categoria_id:
                queryset = queryset.filter(categoria_id=int(categoria_id))
        
        if filters.get('precio_min'):
            precio_min = InputValidator.validate_numeric(filters['precio_min'])
            if precio_min is not None:
                queryset = queryset.filter(precio_promedio_minimo__gte=precio_min)
        
        if filters.get('precio_max'):
            precio_max = InputValidator.validate_numeric(filters['precio_max'])
            if precio_max is not None:
                queryset = queryset.filter(precio_promedio_maximo__lte=precio_max)
        
        if filters.get('calificacion_min'):
            cal_min = InputValidator.validate_numeric(filters['calificacion_min'], min_val=0, max_val=5)
            if cal_min is not None:
                queryset = queryset.filter(calificacion_promedio__gte=cal_min)
        
        if filters.get('busqueda'):
            busqueda = InputValidator.sanitize_string(filters['busqueda'], max_length=200)
            if busqueda:
                queryset = queryset.filter(
                    Q(nombre__icontains=busqueda) |
                    Q(descripcion__icontains=busqueda) |
                    Q(provincia__icontains=busqueda) |
                    Q(ciudad__icontains=busqueda)
                )
        
        return queryset
    
    @staticmethod
    def get_destinations_by_region_stats() -> Dict[str, int]:
        """Calcula estadísticas de destinos por región"""
        stats = {}
        for region_code, _ in Destino.REGIONES_CHOICES:
            stats[region_code] = Destino.objects.filter(
                region=region_code, 
                activo=True
            ).count()
        return stats
    
    @staticmethod
    def get_destination_services(destino):
        result = {
            'servicios': [],
            'total': 0,
            'por_tipo': {},
            'tiene_abiertos': False
        }
        
        try:
            from apps.servicios.models import Servicio
            
            servicios_query = Servicio.objects.filter(
                destino=destino,
                activo=True,
                disponible=True
            ).select_related('proveedor', 'categoria').prefetch_related('imagenes', 'horarios')
            
            result['total'] = servicios_query.count()
            result['servicios'] = list(
                servicios_query.order_by('-calificacion_promedio', '-total_calificaciones')[:6]
            )
            
            for servicio in result['servicios']:
                if hasattr(servicio, 'esta_abierto_ahora') and servicio.esta_abierto_ahora():
                    result['tiene_abiertos'] = True
                    break
            
            if result['total'] > 6:
                for tipo_code, tipo_nombre in Servicio.TIPO_SERVICIO_CHOICES:
                    count = servicios_query.filter(tipo=tipo_code).count()
                    if count > 0:
                        result['por_tipo'][tipo_nombre] = {
                            'codigo': tipo_code,
                            'total': count
                        }
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f'Error al cargar servicios del destino {destino.id}: {str(e)}')
        
        return result
    
    @staticmethod
    def get_destination_ratings(destino):
        result = {
            'calificaciones': [],
            'stats': {'5': 0, '4': 0, '3': 0, '2': 0, '1': 0},
            'total': 0,
            'por_tipo': {}
        }
        
        try:
            from apps.calificaciones.models import Calificacion
            
            calificaciones_qs = Calificacion.objects.filter(
                servicio__destino=destino,
                activo=True
            ).select_related('usuario', 'servicio')
            
            result['total'] = calificaciones_qs.count()
            
            for puntuacion in range(1, 6):
                result['stats'][str(puntuacion)] = calificaciones_qs.filter(
                    puntuacion=puntuacion
                ).count()
            
            result['calificaciones'] = list(
                calificaciones_qs.order_by('-fecha_creacion')[:10]
            )
            
            if result['total'] > 0:
                try:
                    from apps.servicios.models import Servicio
                    
                    for tipo_code, tipo_nombre in Servicio.TIPO_SERVICIO_CHOICES:
                        tipo_cals = calificaciones_qs.filter(servicio__tipo=tipo_code)
                        count = tipo_cals.count()
                        if count > 0:
                            promedio = tipo_cals.aggregate(promedio=Avg('puntuacion'))['promedio']
                            result['por_tipo'][tipo_nombre] = {
                                'count': count,
                                'promedio': round(promedio, 1)
                            }
                except Exception:
                    pass
        except ImportError:
            pass
        
        return result


class DestinationFormProcessor:
    
    @staticmethod
    def extract_form_data(request) -> Dict[str, Any]:
        return {
            'nombre': InputValidator.sanitize_string(request.POST.get('nombre', ''), max_length=200),
            'region': InputValidator.sanitize_string(request.POST.get('region', ''), max_length=20),
            'categoria_id': InputValidator.sanitize_string(request.POST.get('categoria', ''), max_length=10),
            'provincia': InputValidator.sanitize_string(request.POST.get('provincia', ''), max_length=100),
            'ciudad': InputValidator.sanitize_string(request.POST.get('ciudad', ''), max_length=100),
            'descripcion': InputValidator.sanitize_string(request.POST.get('descripcion', '')),
            'descripcion_corta': InputValidator.sanitize_string(request.POST.get('descripcion_corta', ''), max_length=300),
            'latitud': request.POST.get('latitud', '').strip(),
            'longitud': request.POST.get('longitud', '').strip(),
            'altitud': request.POST.get('altitud', '').strip(),
            'clima': InputValidator.sanitize_string(request.POST.get('clima', ''), max_length=100),
            'mejor_epoca': InputValidator.sanitize_string(request.POST.get('mejor_epoca', ''), max_length=200),
            'precio_min': request.POST.get('precio_promedio_minimo', '').strip(),
            'precio_max': request.POST.get('precio_promedio_maximo', '').strip(),
            'destacado': request.POST.get('destacado') == 'on',
            'activo': request.POST.get('activo') == 'on',
            'imagen_principal': request.FILES.get('imagen_principal')
        }
    
    @staticmethod
    def validate_form_data(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        
        required_fields = ['nombre', 'region', 'provincia', 'descripcion', 
                          'descripcion_corta', 'latitud', 'longitud', 
                          'precio_min', 'precio_max']
        
        for field in required_fields:
            if not data.get(field):
                errors.append(f'El campo {field.replace("_", " ")} es obligatorio')
        
        if errors:
            return False, errors
        
        lat, lon = InputValidator.validate_coordinates(data['latitud'], data['longitud'])
        if lat is None or lon is None:
            errors.append('Coordenadas geográficas inválidas')
        
        precio_min, precio_max = InputValidator.validate_price_range(data['precio_min'], data['precio_max'])
        if precio_min is None or precio_max is None:
            errors.append('Rango de precios inválido')
        
        if data.get('altitud'):
            altitud = InputValidator.validate_numeric(data['altitud'], min_val=0, max_val=10000)
            if altitud is None:
                errors.append('Altitud inválida (debe ser entre 0 y 10000 metros)')
        
        if len(data.get('descripcion_corta', '')) > 300:
            errors.append('La descripción corta no puede exceder 300 caracteres')
        
        if data.get('region') not in dict(Destino.REGIONES_CHOICES).keys():
            errors.append('La región seleccionada no es válida')
        
        provincias = get_provincias()
        if data.get('provincia') not in provincias:
            errors.append('La provincia seleccionada no es válida')
        
        if data.get('ciudad'):
            cantones = get_cantones(data['provincia'])
            if data['ciudad'] not in cantones:
                errors.append('La ciudad/cantón seleccionado no es válido')
        
        if data.get('categoria_id'):
            try:
                categoria = Categoria.objects.get(id=int(data['categoria_id']), activo=True)
            except (Categoria.DoesNotExist, ValueError):
                errors.append('La categoría seleccionada no es válida')
        
        if data.get('imagen_principal'):
            is_valid, error_msg = InputValidator.validate_image(data['imagen_principal'])
            if not is_valid:
                errors.append(error_msg)
        
        return len(errors) == 0, errors
    
    @staticmethod
    def create_destination(data: Dict[str, Any], user) -> Destino:
        lat, lon = InputValidator.validate_coordinates(data['latitud'], data['longitud'])
        precio_min, precio_max = InputValidator.validate_price_range(data['precio_min'], data['precio_max'])
        
        altitud = None
        if data.get('altitud'):
            altitud = InputValidator.validate_numeric(data['altitud'], min_val=0)
        
        categoria = None
        if data.get('categoria_id'):
            try:
                categoria = Categoria.objects.get(id=int(data['categoria_id']), activo=True)
            except (Categoria.DoesNotExist, ValueError):
                pass
        
        destino = Destino.objects.create(
            nombre=data['nombre'],
            region=data['region'],
            categoria=categoria,
            provincia=data['provincia'],
            ciudad=data['ciudad'] if data['ciudad'] else None,
            descripcion=data['descripcion'],
            descripcion_corta=data['descripcion_corta'],
            latitud=lat,
            longitud=lon,
            altitud=altitud,
            clima=data['clima'] if data['clima'] else None,
            mejor_epoca=data['mejor_epoca'] if data['mejor_epoca'] else None,
            precio_promedio_minimo=precio_min,
            precio_promedio_maximo=precio_max,
            destacado=data['destacado'],
            activo=data['activo'],
            creado_por=user
        )
        
        if data.get('imagen_principal'):
            try:
                destino.imagen_principal = data['imagen_principal']
                destino.save(update_fields=['imagen_principal'])
            except Exception as e:
                logger.warning(f'Error al guardar imagen: {str(e)}')
        
        return destino
    
    @staticmethod
    def update_destination(destino: Destino, data: Dict[str, Any]) -> Destino:
        lat, lon = InputValidator.validate_coordinates(data['latitud'], data['longitud'])
        precio_min, precio_max = InputValidator.validate_price_range(data['precio_min'], data['precio_max'])
        
        altitud = None
        if data.get('altitud'):
            altitud = InputValidator.validate_numeric(data['altitud'], min_val=0)
        
        categoria = None
        if data.get('categoria_id'):
            try:
                categoria = Categoria.objects.get(id=int(data['categoria_id']), activo=True)
            except (Categoria.DoesNotExist, ValueError):
                pass
        
        destino.nombre = data['nombre']
        destino.region = data['region']
        destino.categoria = categoria
        destino.provincia = data['provincia']
        destino.ciudad = data['ciudad'] if data['ciudad'] else None
        destino.descripcion = data['descripcion']
        destino.descripcion_corta = data['descripcion_corta']
        destino.latitud = lat
        destino.longitud = lon
        destino.altitud = altitud
        destino.clima = data['clima'] if data['clima'] else None
        destino.mejor_epoca = data['mejor_epoca'] if data['mejor_epoca'] else None
        destino.precio_promedio_minimo = precio_min
        destino.precio_promedio_maximo = precio_max
        destino.destacado = data['destacado']
        destino.activo = data['activo']
        
        if data.get('imagen_principal'):
            destino.imagen_principal = data['imagen_principal']
        
        destino.save()
        return destino


"""
================================================================================
VISTAS PÚBLICAS
================================================================================
"""

def lista_destinos(request):
    destinos = QueryHelper.get_active_destinations_query()
    
    filters = {
        'region': InputValidator.sanitize_string(request.GET.get('region', ''), max_length=20),
        'categoria_id': request.GET.get('categoria', '').strip(),
        'precio_min': request.GET.get('precio_min', '').strip(),
        'precio_max': request.GET.get('precio_max', '').strip(),
        'calificacion_min': request.GET.get('calificacion_min', '').strip(),
        'busqueda': request.GET.get('q', '').strip(),
    }
    
    destinos = QueryHelper.apply_search_filters(destinos, filters)
    
    orden = request.GET.get('orden', '-destacado')
    orden_permitido = ['-destacado', 'nombre', '-calificacion_promedio', '-visitas']
    if orden not in orden_permitido:
        orden = '-destacado'
    destinos = destinos.order_by(orden, '-calificacion_promedio')
    
    paginator = Paginator(destinos, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    destinos_por_region = QueryHelper.get_destinations_by_region_stats()
    
    categorias = Categoria.objects.filter(activo=True)
    regiones = Destino.REGIONES_CHOICES
    
    context = {
        'page_obj': page_obj,
        'categorias': categorias,
        'regiones': regiones,
        'destinos_por_region': destinos_por_region,
        'filtros_aplicados': {**filters, 'orden': orden}
    }
    
    return render(request, 'destinos/lista_destinos.html', context)


def detalle_destino(request, slug):
    slug_sanitized = InputValidator.sanitize_string(slug, max_length=200)
    
    destino = get_object_or_404(
        Destino.objects.select_related('categoria', 'creado_por'),
        slug=slug_sanitized,
        activo=True
    )
    
    destino.incrementar_visitas()
    
    imagenes = destino.imagenes.all().order_by('-es_principal', 'orden')
    atracciones = destino.atracciones.filter(activo=True)
    
    servicios_data = QueryHelper.get_destination_services(destino)
    ratings_data = QueryHelper.get_destination_ratings(destino)
    
    destinos_relacionados = Destino.objects.filter(
        region=destino.region,
        activo=True
    ).exclude(id=destino.id).order_by('-calificacion_promedio')[:4]
    
    context = {
        'destino': destino,
        'imagenes': imagenes,
        'atracciones': atracciones,
        'servicios_destino': servicios_data['servicios'],
        'servicios_por_tipo': servicios_data['por_tipo'],
        'total_servicios': servicios_data['total'],
        'calificaciones': ratings_data['calificaciones'],
        'stats_calificaciones': ratings_data['stats'],
        'total_calificaciones': ratings_data['total'],
        'calificaciones_por_tipo': ratings_data['por_tipo'],
        'destinos_relacionados': destinos_relacionados,
        'coordenadas': destino.get_coordenadas(),
    }
    
    return render(request, 'destinos/detalle_destino.html', context)


def destinos_por_region(request, region):
    """Vista filtrada por región específica"""
    region_sanitized = InputValidator.sanitize_string(region, max_length=20)
    regiones_validas = dict(Destino.REGIONES_CHOICES)
    
    if region_sanitized not in regiones_validas:
        return redirect('destinos:lista_destinos')
    
    destinos = Destino.objects.filter(
        region=region_sanitized,
        activo=True
    ).order_by('-destacado', '-calificacion_promedio')
    
    paginator = Paginator(destinos, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'region': region_sanitized,
        'region_nombre': regiones_validas[region_sanitized],
        'total_destinos': destinos.count(),
    }
    
    return render(request, 'destinos/destinos_por_region.html', context)


def destinos_destacados(request):
    """Vista de destinos destacados"""
    destinos = Destino.objects.filter(
        destacado=True,
        activo=True
    ).order_by('-calificacion_promedio')[:8]
    
    return render(request, 'destinos/destinos_destacados.html', {'destinos': destinos})


def mapa_destinos(request):
    """Vista de mapa interactivo con todos los destinos activos"""
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
    
    return render(request, 'destinos/mapa_destinos.html', {'destinos_json': destinos_json})


"""
================================================================================
VISTAS AJAX
================================================================================
"""

@require_http_methods(["GET"])
def busqueda_ajax(request):
    """Búsqueda de destinos para autocompletado y chatbot"""
    termino = InputValidator.sanitize_string(request.GET.get('q', ''), max_length=200)
    region = InputValidator.sanitize_string(request.GET.get('region', ''), max_length=20)
    
    if len(termino) < 2:
        return JsonResponse({
            'success': True,
            'resultados': [],
            'mensaje': 'Escribe al menos 2 caracteres para buscar'
        })
    
    destinos = Destino.objects.filter(activo=True)
    
    destinos = destinos.filter(
        Q(nombre__icontains=termino) |
        Q(provincia__icontains=termino) |
        Q(ciudad__icontains=termino) |
        Q(descripcion__icontains=termino)
    )
    
    if region:
        destinos = destinos.filter(region=region)
    
    destinos = destinos.order_by('-calificacion_promedio', '-destacado')[:15]
    
    resultados = []
    for d in destinos:
        resultados.append({
            'id': d.id,
            'nombre': d.nombre,
            'slug': d.slug,
            'provincia': d.provincia,
            'ciudad': d.ciudad or '',
            'region': d.region,
            'region_display': d.get_region_display(),
            'calificacion': float(d.calificacion_promedio),
            'total_calificaciones': d.total_calificaciones,
            'precio_min': float(d.precio_promedio_minimo) if d.precio_promedio_minimo else 0,
            'precio_max': float(d.precio_promedio_maximo) if d.precio_promedio_maximo else 0,
            'descripcion_corta': d.descripcion_corta,
            'imagen': d.get_imagen_principal(),
            'url': f'/destinos/{d.slug}/',
            'destacado': d.destacado
        })
    
    return JsonResponse({
        'success': True,
        'resultados': resultados,
        'total': len(resultados)
    })


@require_http_methods(["GET"])
def estadisticas_destinos_ajax(request):
    """Estadísticas generales de destinos para chatbot"""
    try:
        total_destinos = Destino.objects.filter(activo=True).count()
        
        destinos_por_region = {}
        for region_code, region_nombre in Destino.REGIONES_CHOICES:
            count = Destino.objects.filter(region=region_code, activo=True).count()
            destinos_por_region[region_nombre] = count
        
        precio_por_region = {}
        for region_code, region_nombre in Destino.REGIONES_CHOICES:
            destinos_region = Destino.objects.filter(region=region_code, activo=True)
            if destinos_region.exists():
                promedio_min = destinos_region.aggregate(
                    promedio=Avg('precio_promedio_minimo')
                )['promedio']
                promedio_max = destinos_region.aggregate(
                    promedio=Avg('precio_promedio_maximo')
                )['promedio']
                
                precio_por_region[region_nombre] = {
                    'minimo': round(float(promedio_min or 0), 2),
                    'maximo': round(float(promedio_max or 0), 2)
                }
        
        mejor_calificados = Destino.objects.filter(
            activo=True
        ).order_by('-calificacion_promedio', '-total_calificaciones')[:5]
        
        mejores = [{
            'id': d.id,
            'nombre': d.nombre,
            'region': d.get_region_display(),
            'calificacion': float(d.calificacion_promedio),
            'total_calificaciones': d.total_calificaciones,
            'provincia': d.provincia,
            'url': f'/destinos/{d.slug}/'
        } for d in mejor_calificados]
        
        mas_visitados = Destino.objects.filter(
            activo=True
        ).order_by('-visitas')[:5]
        
        visitados = [{
            'nombre': d.nombre,
            'visitas': d.visitas,
            'region': d.get_region_display()
        } for d in mas_visitados]
        
        return JsonResponse({
            'success': True,
            'total_destinos': total_destinos,
            'destinos_por_region': destinos_por_region,
            'precio_promedio_region': precio_por_region,
            'mejor_calificados': mejores,
            'mas_visitados': visitados
        })
        
    except Exception as e:
        logger.error(f'Error en estadisticas_destinos_ajax: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': 'Error al obtener estadísticas'
        }, status=500)


@require_http_methods(["GET"])
def destinos_por_region_ajax(request, region):
    """Obtener destinos de una región específica para chatbot"""
    region_sanitized = InputValidator.sanitize_string(region, max_length=20)
    regiones_validas = dict(Destino.REGIONES_CHOICES)
    
    if region_sanitized not in regiones_validas:
        return JsonResponse({
            'success': False,
            'error': f'Región "{region_sanitized}" no válida. Opciones: costa, sierra, oriente, galapagos'
        }, status=400)
    
    try:
        destinos = Destino.objects.filter(
            region=region_sanitized,
            activo=True
        ).order_by('-calificacion_promedio')[:10]
        
        resultados = [{
            'id': d.id,
            'nombre': d.nombre,
            'provincia': d.provincia,
            'ciudad': d.ciudad or '',
            'calificacion': float(d.calificacion_promedio),
            'precio_min': float(d.precio_promedio_minimo) if d.precio_promedio_minimo else 0,
            'precio_max': float(d.precio_promedio_maximo) if d.precio_promedio_maximo else 0,
            'descripcion_corta': d.descripcion_corta,
            'destacado': d.destacado,
            'url': f'/destinos/{d.slug}/'
        } for d in destinos]
        
        return JsonResponse({
            'success': True,
            'region': regiones_validas[region_sanitized],
            'total': len(resultados),
            'destinos': resultados
        })
        
    except Exception as e:
        logger.error(f'Error en destinos_por_region_ajax: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': 'Error al obtener destinos'
        }, status=500)


@require_http_methods(["GET"])
def estadisticas_destino(request, destino_id):
    """Obtener estadísticas de un destino específico"""
    destino_id_val = InputValidator.validate_numeric(str(destino_id), min_val=1)
    if not destino_id_val:
        return JsonResponse({'error': 'ID inválido'}, status=400)
    
    destino = get_object_or_404(Destino, id=int(destino_id_val))
    
    servicios_count = 0
    try:
        from apps.servicios.models import Servicio
        servicios_count = Servicio.objects.filter(
            destino=destino,
            activo=True
        ).count()
    except ImportError:
        pass
    
    stats = {
        'visitas': destino.visitas,
        'calificacion_promedio': float(destino.calificacion_promedio),
        'total_calificaciones': destino.total_calificaciones,
        'total_imagenes': destino.imagenes.count(),
        'total_atracciones': destino.atracciones.filter(activo=True).count(),
        'total_servicios': servicios_count
    }
    
    return JsonResponse(stats)


"""
================================================================================
VISTAS DE ADMINISTRACIÓN
================================================================================
"""

@login_required
def crear_destino(request):
    """
    Vista para crear un nuevo destino.
    Acceso restringido a administradores.
    """
    if not request.user.es_administrador():
        messages.error(request, 'No tienes permisos para crear destinos')
        return redirect('destinos:lista_destinos')

    if request.method == 'POST':
        data = DestinationFormProcessor.extract_form_data(request)
        is_valid, errors = DestinationFormProcessor.validate_form_data(data)
        
        if not is_valid:
            for error in errors:
                messages.error(request, error)
            return redirect('destinos:crear_destino')
        
        try:
            destino = DestinationFormProcessor.create_destination(data, request.user)
            
            if data.get('imagen_principal'):
                messages.success(request, f'Destino "{destino.nombre}" creado exitosamente con imagen')
            else:
                messages.success(request, f'Destino "{destino.nombre}" creado exitosamente')
            
            return redirect('destinos:detalle_destino', slug=destino.slug)
            
        except Exception as e:
            logger.error(f'Error al crear destino: {str(e)}')
            messages.error(request, 'Error al crear el destino. Intenta nuevamente')
            return redirect('destinos:crear_destino')

    categorias = Categoria.objects.filter(activo=True)
    regiones = Destino.REGIONES_CHOICES
    provincias = get_provincias()
    provincias_cantones_json = get_provincias_cantones_json()

    context = {
        'categorias': categorias,
        'regiones': regiones,
        'provincias': provincias,
        'provincias_cantones_json': provincias_cantones_json,
        'titulo': 'Crear Nuevo Destino'
    }

    return render(request, 'destinos/crear_destino.html', context)


@login_required
def editar_destino(request, destino_id):
    """
    Vista para editar un destino existente.
    Acceso restringido a administradores.
    """
    if not request.user.es_administrador():
        messages.error(request, 'No tienes permisos para editar destinos')
        return redirect('destinos:lista_destinos')
    
    destino_id_val = InputValidator.validate_numeric(str(destino_id), min_val=1)
    if not destino_id_val:
        messages.error(request, 'ID de destino inválido')
        return redirect('destinos:lista_destinos')
    
    destino = get_object_or_404(Destino, id=int(destino_id_val))
    
    if request.method == 'POST':
        data = DestinationFormProcessor.extract_form_data(request)
        is_valid, errors = DestinationFormProcessor.validate_form_data(data)
        
        if not is_valid:
            for error in errors:
                messages.error(request, error)
            return redirect('destinos:editar_destino', destino_id=destino.id)
        
        try:
            destino = DestinationFormProcessor.update_destination(destino, data)
            messages.success(request, f'Destino "{destino.nombre}" actualizado exitosamente')
            return redirect('destinos:detalle_destino', slug=destino.slug)
            
        except Exception as e:
            logger.error(f'Error al actualizar destino: {str(e)}')
            messages.error(request, 'Error al actualizar el destino. Intenta nuevamente')
            return redirect('destinos:editar_destino', destino_id=destino.id)
    
    categorias = Categoria.objects.filter(activo=True)
    regiones = Destino.REGIONES_CHOICES
    provincias = get_provincias()
    provincias_cantones_json = get_provincias_cantones_json()
    
    valores_numericos = {
        'latitud': str(destino.latitud) if destino.latitud is not None else '',
        'longitud': str(destino.longitud) if destino.longitud is not None else '',
        'altitud': str(destino.altitud) if destino.altitud is not None else '',
        'precio_min': str(destino.precio_promedio_minimo) if destino.precio_promedio_minimo is not None else '',
        'precio_max': str(destino.precio_promedio_maximo) if destino.precio_promedio_maximo is not None else '',
    }
    
    context = {
        'destino': destino,
        'categorias': categorias,
        'regiones': regiones,
        'provincias': provincias,
        'provincias_cantones_json': provincias_cantones_json,
        'valores_numericos': valores_numericos,
        'titulo': f'Editar {destino.nombre}'
    }
    
    return render(request, 'destinos/editar_destino.html', context)


@login_required
@require_http_methods(["POST"])
def eliminar_destino(request, destino_id):
    """
    Vista para desactivar un destino.
    Acceso restringido a administradores.
    """
    if not request.user.es_administrador():
        messages.error(request, 'No tienes permisos para eliminar destinos')
        return redirect('destinos:lista_destinos')
    
    destino_id_val = InputValidator.validate_numeric(str(destino_id), min_val=1)
    if not destino_id_val:
        messages.error(request, 'ID de destino inválido')
        return redirect('destinos:lista_destinos')
    
    destino = get_object_or_404(Destino, id=int(destino_id_val))
    nombre_destino = destino.nombre
    
    destino.activo = False
    destino.save()
    
    messages.success(request, f'Destino "{nombre_destino}" eliminado exitosamente')
    return redirect('destinos:lista_destinos')


@login_required
def agregar_favorito(request, destino_id):
    """Vista para agregar destino a favoritos"""
    if request.method == 'POST':
        destino_id_val = InputValidator.validate_numeric(str(destino_id), min_val=1)
        if not destino_id_val:
            return JsonResponse({'success': False, 'error': 'ID inválido'}, status=400)
        
        destino = get_object_or_404(Destino, id=int(destino_id_val), activo=True)
        
        return JsonResponse({
            'success': True,
            'message': f'{destino.nombre} agregado a favoritos'
        })
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=400)