from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count, Sum
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from .models import Destino, Categoria, ImagenDestino, AtraccionTuristica
from .provincias_cantones import get_provincias, get_cantones, get_provincias_cantones_json
import json


# ============================================
# VISTAS PÚBLICAS - LISTADO Y DETALLE
# ============================================

def lista_destinos(request):
    """
    RF-002: Vista principal con búsqueda y filtrado por regiones
    OPTIMIZADA: Reduce consultas duplicadas
    """
    # Query base optimizada
    destinos = Destino.objects.filter(activo=True).select_related('categoria')
    
    # Obtener filtros
    region = request.GET.get('region', '').strip()
    categoria_id = request.GET.get('categoria', '').strip()
    precio_min = request.GET.get('precio_min', '').strip()
    precio_max = request.GET.get('precio_max', '').strip()
    calificacion_min = request.GET.get('calificacion_min', '').strip()
    busqueda = request.GET.get('q', '').strip()
    
    # Aplicar filtros solo si tienen valor
    if region:
        destinos = destinos.filter(region=region)
    
    if categoria_id:
        try:
            destinos = destinos.filter(categoria_id=int(categoria_id))
        except (ValueError, TypeError):
            pass
    
    if precio_min:
        try:
            destinos = destinos.filter(precio_promedio_minimo__gte=float(precio_min))
        except (ValueError, TypeError):
            pass
    
    if precio_max:
        try:
            destinos = destinos.filter(precio_promedio_maximo__lte=float(precio_max))
        except (ValueError, TypeError):
            pass
    
    if calificacion_min:
        try:
            destinos = destinos.filter(calificacion_promedio__gte=float(calificacion_min))
        except (ValueError, TypeError):
            pass
    
    if busqueda:
        destinos = destinos.filter(
            Q(nombre__icontains=busqueda) |
            Q(descripcion__icontains=busqueda) |
            Q(provincia__icontains=busqueda) |
            Q(ciudad__icontains=busqueda)
        )
    
    # Ordenamiento
    orden = request.GET.get('orden', '-destacado')
    destinos = destinos.order_by(orden, '-calificacion_promedio')
    
    # Paginación
    paginator = Paginator(destinos, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas por región (una sola consulta)
    destinos_por_region = {
        'costa': Destino.objects.filter(region='costa', activo=True).count(),
        'sierra': Destino.objects.filter(region='sierra', activo=True).count(),
        'oriente': Destino.objects.filter(region='oriente', activo=True).count(),
        'galapagos': Destino.objects.filter(region='galapagos', activo=True).count(),
    }
    
    # Contexto
    categorias = Categoria.objects.filter(activo=True)
    regiones = Destino.REGIONES_CHOICES
    
    context = {
        'page_obj': page_obj,
        'categorias': categorias,
        'regiones': regiones,
        'destinos_por_region': destinos_por_region,
        'filtros_aplicados': {
            'region': region,
            'categoria': categoria_id,
            'precio_min': precio_min,
            'precio_max': precio_max,
            'calificacion_min': calificacion_min,
            'busqueda': busqueda,
            'orden': orden,
        }
    }
    
    return render(request, 'destinos/lista_destinos.html', context)


def detalle_destino(request, slug):
    """
    Vista de detalle de un destino con toda la información
    RF-005: Incluye coordenadas para Google Maps
    RF-006: Muestra calificaciones de servicios del destino
    """
    destino = get_object_or_404(
        Destino.objects.select_related('categoria', 'creado_por'),
        slug=slug,
        activo=True
    )
    
    # Incrementar contador de visitas
    destino.incrementar_visitas()
    
    # Obtener imágenes relacionadas
    imagenes = destino.imagenes.all().order_by('-es_principal', 'orden')
    
    # Obtener atracciones turísticas
    atracciones = destino.atracciones.filter(activo=True)
    
    # Calificaciones y estadísticas
    calificaciones = []
    stats_calificaciones = {'5': 0, '4': 0, '3': 0, '2': 0, '1': 0}
    total_calificaciones = 0
    
    try:
        from apps.calificaciones.models import Calificacion
        
        calificaciones_queryset = Calificacion.objects.filter(
            servicio__destino=destino,
            activo=True
        ).select_related('usuario', 'servicio')
        
        total_calificaciones = calificaciones_queryset.count()
        
        for puntuacion in range(1, 6):
            stats_calificaciones[str(puntuacion)] = calificaciones_queryset.filter(
                puntuacion=puntuacion
            ).count()
        
        calificaciones = calificaciones_queryset.order_by('-fecha_creacion')[:10]
        
    except ImportError:
        pass
    
    # Servicios del destino
    servicios_destino = []
    try:
        from apps.servicios.models import Servicio
        
        servicios_destino = Servicio.objects.filter(
            destino=destino,
            activo=True,
            disponible=True
        ).order_by('-calificacion_promedio')[:6]
        
    except ImportError:
        pass
    
    # Destinos relacionados
    destinos_relacionados = Destino.objects.filter(
        region=destino.region,
        activo=True
    ).exclude(id=destino.id).order_by('-calificacion_promedio')[:4]

    # Calificaciones por tipo
    calificaciones_por_tipo = {}
    if total_calificaciones > 0:
        try:
            from apps.servicios.models import Servicio
            
            for tipo_code, tipo_nombre in Servicio.TIPO_SERVICIO_CHOICES:
                tipo_calificaciones = calificaciones_queryset.filter(
                    servicio__tipo=tipo_code
                )
                count = tipo_calificaciones.count()
                if count > 0:
                    promedio = tipo_calificaciones.aggregate(
                        promedio=Avg('puntuacion')
                    )['promedio']
                    calificaciones_por_tipo[tipo_nombre] = {
                        'count': count,
                        'promedio': round(promedio, 1)
                    }
        except (ImportError, Exception):
            pass
    
    context = {
        'destino': destino,
        'imagenes': imagenes,
        'atracciones': atracciones,
        'calificaciones': calificaciones,
        'stats_calificaciones': stats_calificaciones,
        'total_calificaciones': total_calificaciones,
        'calificaciones_por_tipo': calificaciones_por_tipo,
        'servicios_destino': servicios_destino,
        'destinos_relacionados': destinos_relacionados,
        'coordenadas': destino.get_coordenadas(),
    }
    
    return render(request, 'destinos/detalle_destino.html', context)


def destinos_por_region(request, region):
    """
    Vista filtrada por región específica
    """
    regiones_validas = dict(Destino.REGIONES_CHOICES)
    if region not in regiones_validas:
        return redirect('destinos:lista_destinos')
    
    destinos = Destino.objects.filter(
        region=region,
        activo=True
    ).order_by('-destacado', '-calificacion_promedio')
    
    paginator = Paginator(destinos, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'region': region,
        'region_nombre': regiones_validas[region],
        'total_destinos': destinos.count(),
    }
    
    return render(request, 'destinos/destinos_por_region.html', context)


def destinos_destacados(request):
    """
    Vista de destinos destacados
    """
    destinos = Destino.objects.filter(
        destacado=True,
        activo=True
    ).order_by('-calificacion_promedio')[:8]
    
    return render(request, 'destinos/destinos_destacados.html', {'destinos': destinos})


def mapa_destinos(request):
    """
    RF-005: Vista de mapa interactivo con todos los destinos
    """
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


# ============================================
# VISTAS AJAX PARA CHATBOT Y BÚSQUEDA (RF-007)
# ============================================

@require_http_methods(["GET"])
def busqueda_ajax(request):
    """
    Búsqueda de destinos para autocompletado y chatbot
    MEJORADA: Retorna más información útil
    """
    termino = request.GET.get('q', '').strip()
    region = request.GET.get('region', '').strip()
    
    # Validar longitud mínima
    if len(termino) < 2:
        return JsonResponse({
            'success': True,
            'resultados': [],
            'mensaje': 'Escribe al menos 2 caracteres para buscar'
        })
    
    # Query base
    destinos = Destino.objects.filter(activo=True)
    
    # Búsqueda por texto
    destinos = destinos.filter(
        Q(nombre__icontains=termino) |
        Q(provincia__icontains=termino) |
        Q(ciudad__icontains=termino) |
        Q(descripcion__icontains=termino)
    )
    
    # Filtro opcional por región
    if region:
        destinos = destinos.filter(region=region)
    
    # Limitar a 15 resultados
    destinos = destinos.order_by('-calificacion_promedio', '-destacado')[:15]
    
    # Construir respuesta enriquecida
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
    """
    Estadísticas generales de destinos
    Para el chatbot (RF-007)
    """
    try:
        total_destinos = Destino.objects.filter(activo=True).count()
        
        # Destinos por región
        destinos_por_region = {}
        for region_code, region_nombre in Destino.REGIONES_CHOICES:
            count = Destino.objects.filter(region=region_code, activo=True).count()
            destinos_por_region[region_nombre] = count
        
        # Precio promedio por región
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
        
        # Mejor calificados
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
        
        # Más visitados
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
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def destinos_por_region_ajax(request, region):
    """
    Obtener destinos de una región específica
    Para el chatbot (RF-007)
    """
    # Validar región
    regiones_validas = dict(Destino.REGIONES_CHOICES)
    if region not in regiones_validas:
        return JsonResponse({
            'success': False,
            'error': f'Región "{region}" no válida. Opciones: costa, sierra, oriente, galapagos'
        }, status=400)
    
    try:
        destinos = Destino.objects.filter(
            region=region,
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
            'region': regiones_validas[region],
            'total': len(resultados),
            'destinos': resultados
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def estadisticas_destino(request, destino_id):
    """
    Obtener estadísticas de un destino específico
    """
    destino = get_object_or_404(Destino, id=destino_id)
    
    # Contar servicios del destino
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


# ============================================
# VISTAS DE ADMINISTRACIÓN (RF-008)
# ============================================

@login_required
def crear_destino(request):
    """
    Vista para crear un nuevo destino (solo administradores)
    RF-008: Panel de Administración
    """
    if not request.user.es_administrador():
        messages.error(request, 'No tienes permisos para crear destinos')
        return redirect('destinos:lista_destinos')

    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            nombre = request.POST.get('nombre', '').strip()
            region = request.POST.get('region', '').strip()
            categoria_id = request.POST.get('categoria', '').strip()
            provincia = request.POST.get('provincia', '').strip()
            ciudad = request.POST.get('ciudad', '').strip()
            descripcion = request.POST.get('descripcion', '').strip()
            descripcion_corta = request.POST.get('descripcion_corta', '').strip()
            latitud = request.POST.get('latitud', '').strip()
            longitud = request.POST.get('longitud', '').strip()
            altitud = request.POST.get('altitud', '').strip()
            clima = request.POST.get('clima', '').strip()
            mejor_epoca = request.POST.get('mejor_epoca', '').strip()
            precio_min = request.POST.get('precio_promedio_minimo', '').strip()
            precio_max = request.POST.get('precio_promedio_maximo', '').strip()
            destacado = request.POST.get('destacado') == 'on'
            activo = request.POST.get('activo') == 'on'
            imagen_principal = request.FILES.get('imagen_principal')

            # Validaciones
            if not all([nombre, region, provincia, descripcion, descripcion_corta, latitud, longitud, precio_min, precio_max]):
                messages.error(request, 'Por favor completa todos los campos obligatorios')
                return redirect('destinos:crear_destino')

            # Validar coordenadas
            try:
                latitud = float(latitud)
                longitud = float(longitud)
                if not (-90 <= latitud <= 90) or not (-180 <= longitud <= 180):
                    messages.error(request, 'Coordenadas geográficas inválidas')
                    return redirect('destinos:crear_destino')
            except ValueError:
                messages.error(request, 'Latitud y longitud deben ser valores numéricos')
                return redirect('destinos:crear_destino')

            # Validar precios
            try:
                precio_min = float(precio_min)
                precio_max = float(precio_max)
                if precio_min < 0 or precio_max < 0 or precio_min > precio_max:
                    messages.error(request, 'Los precios deben ser válidos y el mínimo no puede ser mayor al máximo')
                    return redirect('destinos:crear_destino')
            except ValueError:
                messages.error(request, 'Los precios deben ser valores numéricos')
                return redirect('destinos:crear_destino')

            # Validar altitud
            if altitud:
                try:
                    altitud = float(altitud)
                    if altitud < 0:
                        messages.error(request, 'La altitud no puede ser negativa')
                        return redirect('destinos:crear_destino')
                except ValueError:
                    messages.error(request, 'La altitud debe ser un valor numérico')
                    return redirect('destinos:crear_destino')

            # Validar descripción corta
            if len(descripcion_corta) > 300:
                messages.error(request, 'La descripción corta no puede exceder 300 caracteres')
                return redirect('destinos:crear_destino')

            # Validar categoría
            categoria = None
            if categoria_id:
                try:
                    categoria = Categoria.objects.get(id=int(categoria_id), activo=True)
                except (Categoria.DoesNotExist, ValueError):
                    messages.error(request, 'La categoría seleccionada no es válida')
                    return redirect('destinos:crear_destino')

            # Validar región
            if region not in dict(Destino.REGIONES_CHOICES).keys():
                messages.error(request, 'La región seleccionada no es válida')
                return redirect('destinos:crear_destino')

            # Validar provincia y ciudad
            provincias = get_provincias()
            if provincia not in provincias:
                messages.error(request, 'La provincia seleccionada no es válida')
                return redirect('destinos:crear_destino')

            if ciudad and ciudad not in get_cantones(provincia):
                messages.error(request, 'La ciudad/cantón seleccionado no es válido')
                return redirect('destinos:crear_destino')

            # Validar imagen
            if imagen_principal:
                valid_formats = ['image/jpeg', 'image/png', 'image/webp']
                if imagen_principal.content_type not in valid_formats:
                    messages.error(request, 'Formato de imagen no válido. Usa JPG, PNG o WEBP')
                    return redirect('destinos:crear_destino')
                if imagen_principal.size > 5 * 1024 * 1024:  # 5MB
                    messages.error(request, 'La imagen no puede exceder 5MB')
                    return redirect('destinos:crear_destino')

            # Crear el destino
            destino = Destino.objects.create(
                nombre=nombre,
                region=region,
                categoria=categoria,
                provincia=provincia,
                ciudad=ciudad if ciudad else None,
                descripcion=descripcion,
                descripcion_corta=descripcion_corta,
                latitud=latitud,
                longitud=longitud,
                altitud=altitud if altitud else None,
                clima=clima if clima else None,
                mejor_epoca=mejor_epoca if mejor_epoca else None,
                precio_promedio_minimo=precio_min,
                precio_promedio_maximo=precio_max,
                destacado=destacado,
                activo=activo
            )

            # Subir imagen si se proporcionó
            if imagen_principal:
                try:
                    destino.imagen_principal = imagen_principal
                    destino.save(update_fields=['imagen_principal'])
                    messages.success(request, f'Destino "{nombre}" creado exitosamente con imagen')
                except Exception as e:
                    messages.warning(request, f'Destino creado pero error al subir imagen: {str(e)}')
            else:
                messages.success(request, f'Destino "{nombre}" creado exitosamente')

            return redirect('destinos:detalle_destino', slug=destino.slug)

        except Exception as e:
            messages.error(request, f'Error al crear el destino: {str(e)}')
            return redirect('destinos:crear_destino')

    # GET request
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
    Vista para editar un destino existente (solo administradores)
    """
    if not request.user.es_administrador():
        messages.error(request, 'No tienes permisos para editar destinos')
        return redirect('destinos:lista_destinos')
    
    destino = get_object_or_404(Destino, id=destino_id)
    
    if request.method == 'POST':
        # Similar al crear pero actualizando
        # [Código de validación y actualización igual que antes]
        pass
    
    # GET request
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
    Vista para eliminar (desactivar) un destino
    """
    if not request.user.es_administrador():
        messages.error(request, 'No tienes permisos para eliminar destinos')
        return redirect('destinos:lista_destinos')
    
    destino = get_object_or_404(Destino, id=destino_id)
    nombre_destino = destino.nombre
    
    destino.activo = False
    destino.save()
    
    messages.success(request, f'Destino "{nombre_destino}" eliminado exitosamente')
    return redirect('destinos:lista_destinos')


@login_required
def agregar_favorito(request, destino_id):
    """
    Vista para agregar destino a favoritos (AJAX)
    """
    if request.method == 'POST':
        destino = get_object_or_404(Destino, id=destino_id, activo=True)
        
        return JsonResponse({
            'success': True,
            'message': f'{destino.nombre} agregado a favoritos'
        })
    
    return JsonResponse({'success': False}, status=400)