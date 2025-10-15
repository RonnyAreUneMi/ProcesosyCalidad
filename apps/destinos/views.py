from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import Destino, Categoria, ImagenDestino, AtraccionTuristica
from apps.calificaciones.models import Calificacion
from django.contrib import messages



def lista_destinos(request):
    """
    RF-002: Vista principal con búsqueda y filtrado por regiones
    """
    destinos = Destino.objects.filter(activo=True).select_related('categoria')
    
    # Filtros
    region = request.GET.get('region')
    categoria_id = request.GET.get('categoria')
    precio_min = request.GET.get('precio_min')
    precio_max = request.GET.get('precio_max')
    calificacion_min = request.GET.get('calificacion_min')
    busqueda = request.GET.get('q')
    
    if region:
        destinos = destinos.filter(region=region)
    
    if categoria_id:
        destinos = destinos.filter(categoria_id=categoria_id)
    
    if precio_min:
        destinos = destinos.filter(precio_promedio_minimo__gte=precio_min)
    
    if precio_max:
        destinos = destinos.filter(precio_promedio_maximo__lte=precio_max)
    
    if calificacion_min:
        destinos = destinos.filter(calificacion_promedio__gte=calificacion_min)
    
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
    
    # ===== AGREGAR ESTO: Calcular destinos por región =====
    destinos_por_region = {
        'costa': Destino.objects.filter(region=Destino.COSTA, activo=True).count(),
        'sierra': Destino.objects.filter(region=Destino.SIERRA, activo=True).count(),
        'oriente': Destino.objects.filter(region=Destino.ORIENTE, activo=True).count(),
        'galapagos': Destino.objects.filter(region=Destino.GALAPAGOS, activo=True).count(),
    }
    # ===================================================
    
    # Contexto
    categorias = Categoria.objects.filter(activo=True)
    regiones = Destino.REGIONES_CHOICES
    
    context = {
        'page_obj': page_obj,
        'categorias': categorias,
        'regiones': regiones,
        'destinos_por_region': destinos_por_region,  # AGREGAR ESTA LÍNEA
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
    
    # ========================================
    # CALIFICACIONES Y ESTADÍSTICAS
    # ========================================
    calificaciones = []
    stats_calificaciones = {
        '5': 0,
        '4': 0,
        '3': 0,
        '2': 0,
        '1': 0,
    }
    total_calificaciones = 0
    
    try:
        from apps.calificaciones.models import Calificacion
        
        # Obtener calificaciones de servicios del destino
        calificaciones_queryset = Calificacion.objects.filter(
            servicio__destino=destino,
            activo=True
        ).select_related('usuario', 'servicio').order_by('-fecha_creacion')
        
        # Calcular estadísticas (antes del slice)
        total_calificaciones = calificaciones_queryset.count()
        for puntuacion in range(1, 6):
            stats_calificaciones[str(puntuacion)] = calificaciones_queryset.filter(
                puntuacion=puntuacion
            ).count()
        
        # Obtener las últimas 10 para mostrar
        calificaciones = calificaciones_queryset[:10]
        
    except ImportError:
        # La app de calificaciones aún no existe
        pass
    
    # ========================================
    # SERVICIOS DEL DESTINO
    # ========================================
    try:
        from apps.servicios.models import Servicio
        
        servicios_destino = Servicio.objects.filter(
            destino=destino,
            activo=True,
            disponible=True
        ).order_by('-calificacion_promedio')[:6]
        
    except ImportError:
        servicios_destino = []
    
    # ========================================
    # DESTINOS RELACIONADOS
    # ========================================
    destinos_relacionados = Destino.objects.filter(
        region=destino.region,
        activo=True
    ).exclude(id=destino.id).order_by('-calificacion_promedio')[:4]

    calificaciones_por_tipo = {}
    if total_calificaciones > 0:
        try:
            from apps.servicios.models import Servicio
            
            # Agrupar calificaciones por tipo de servicio
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
    # Validar que la región existe
    regiones_validas = dict(Destino.REGIONES_CHOICES)
    if region not in regiones_validas:
        return redirect('destinos:lista_destinos')
    
    destinos = Destino.objects.filter(
        region=region,
        activo=True
    ).order_by('-destacado', '-calificacion_promedio')
    
    # Paginación
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
    
    context = {
        'destinos': destinos,
    }
    
    return render(request, 'destinos/destinos_destacados.html', context)


def mapa_destinos(request):
    """
    RF-005: Vista de mapa interactivo con todos los destinos
    """
    destinos = Destino.objects.filter(activo=True).values(
        'id', 'nombre', 'slug', 'descripcion_corta', 
        'latitud', 'longitud', 'region', 'calificacion_promedio'
    )
    
    # Convertir a lista para JSON
    destinos_list = list(destinos)
    
    context = {
        'destinos_json': destinos_list,
    }
    
    return render(request, 'destinos/mapa_destinos.html', context)


@login_required
def agregar_favorito(request, destino_id):
    """
    Vista para agregar destino a favoritos (AJAX)
    """
    if request.method == 'POST':
        destino = get_object_or_404(Destino, id=destino_id, activo=True)
        
        # Aquí implementarías la lógica de favoritos
        # Por ahora retornamos respuesta básica
        
        return JsonResponse({
            'success': True,
            'message': f'{destino.nombre} agregado a favoritos'
        })
    
    return JsonResponse({'success': False}, status=400)


def busqueda_ajax(request):
    """
    Búsqueda con autocompletado para el buscador
    """
    termino = request.GET.get('q', '')
    
    if len(termino) < 3:
        return JsonResponse({'resultados': []})
    
    destinos = Destino.objects.filter(
        Q(nombre__icontains=termino) |
        Q(provincia__icontains=termino) |
        Q(ciudad__icontains=termino),
        activo=True
    )[:10]
    
    resultados = [{
        'id': d.id,
        'nombre': d.nombre,
        'provincia': d.provincia,
        'region': d.get_region_display(),
        'slug': d.slug,
        'imagen': d.get_imagen_principal()
    } for d in destinos]
    
    return JsonResponse({'resultados': resultados})


def estadisticas_destino(request, destino_id):
    """
    Obtener estadísticas de un destino (para dashboard)
    """
    destino = get_object_or_404(Destino, id=destino_id)
    
    stats = {
        'visitas': destino.visitas,
        'calificacion_promedio': float(destino.calificacion_promedio),
        'total_calificaciones': destino.total_calificaciones,
        'total_imagenes': destino.imagenes.count(),
        'total_atracciones': destino.atracciones.filter(activo=True).count(),
    }
    
    return JsonResponse(stats)
# Agrega estas funciones al final de tu archivo apps/destinos/views.py

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Destino, Categoria
from .provincias_cantones import get_provincias, get_cantones, get_provincias_cantones_json
import json

@login_required
def crear_destino(request):
    """
    Vista para crear un nuevo destino (solo administradores)
    RF-008: Panel de Administración
    """
    # Verificar que el usuario sea administrador
    if not request.user.es_administrador():
        messages.error(request, 'No tienes permisos para crear destinos')
        return redirect('destinos:lista_destinos')

    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            nombre = request.POST.get('nombre')
            region = request.POST.get('region')
            categoria_id = request.POST.get('categoria')
            provincia = request.POST.get('provincia')
            ciudad = request.POST.get('ciudad')
            descripcion = request.POST.get('descripcion')
            descripcion_corta = request.POST.get('descripcion_corta')
            latitud = request.POST.get('latitud')
            longitud = request.POST.get('longitud')
            altitud = request.POST.get('altitud')
            clima = request.POST.get('clima')
            mejor_epoca = request.POST.get('mejor_epoca')
            precio_min = request.POST.get('precio_promedio_minimo')
            precio_max = request.POST.get('precio_promedio_maximo')
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

            # Validar altitud (si se proporciona)
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

            # Validar categoría (si se proporciona)
            categoria = None
            if categoria_id:
                try:
                    categoria = Categoria.objects.get(id=categoria_id, activo=True)
                except Categoria.DoesNotExist:
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

            # Validar imagen (si se proporciona)
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
                activo=activo,
                # imagen_principal=imagen_principal
            )
            # Asignar imagen solo si se subió una (sino usa la por defecto del modelo)
            # Subir la imagen a Supabase si se proporcionó
            mensaje_imagen = ""
            if imagen_principal:
                try:
                    # Django automáticamente usará el SupabaseStorage configurado
                    destino.imagen_principal = imagen_principal
                    destino.save(update_fields=['imagen_principal'])
                    mensaje_imagen = " Imagen subida a Supabase exitosamente."
                except Exception as e:
                    # Si falla la subida, informar pero no cancelar la creación
                    mensaje_imagen = f" Advertencia: Error al subir imagen: {str(e)}"
                    print(f"Error subiendo imagen a Supabase: {str(e)}")
            else:
                mensaje_imagen = " Se usará la imagen por defecto."

            messages.success(request, f'Destino "{nombre}" creado exitosamente', f'{"Imagen personalizada subida." if imagen_principal else "Se usará la imagen por defecto."}')
            return redirect('destinos:lista_destinos')

        except Exception as e:
            messages.error(request, f'Error al crear2 el destino: {str(e)}')
            return redirect('destinos:crear_destino')

    # GET request: Renderizar formulario
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
    RF-008: Panel de Administración
    """
    # Verificar que el usuario sea administrador
    if not request.user.es_administrador():
        return JsonResponse({
            'success': False,
            'message': 'No tienes permisos para editar destinos'
        }, status=403)
    
    destino = get_object_or_404(Destino, id=destino_id)
    
    if request.method == 'POST':
        # Aquí irá la lógica para editar el destino
        return JsonResponse({
            'success': True,
            'message': 'Funcionalidad en desarrollo'
        })
    
    # Obtener datos necesarios para el formulario
    categorias = Categoria.objects.filter(activo=True)
    regiones = Destino.REGIONES_CHOICES
    imagenes = destino.imagenes.all()
    atracciones = destino.atracciones.all()
    
    context = {
        'destino': destino,
        'categorias': categorias,
        'regiones': regiones,
        'imagenes': imagenes,
        'atracciones': atracciones,
        'titulo': f'Editar {destino.nombre}'
    }
    
    return render(request, 'destinos/editar_destino.html', context)


@login_required
def eliminar_destino(request, destino_id):
    """
    Vista para eliminar (desactivar) un destino (solo administradores)
    RF-008: Panel de Administración
    """
    # Verificar que el usuario sea administrador
    if not request.user.es_administrador():
        messages.error(request, 'No tienes permisos para eliminar destinos')
        return redirect('destinos:lista_destinos')
    
    destino = get_object_or_404(Destino, id=destino_id)
    
    if request.method == 'POST':
        nombre_destino = destino.nombre
        
        # Desactivar el destino en lugar de eliminarlo
        destino.activo = False
        destino.save()
        
        # Mensaje de éxito
        messages.success(request, f'Destino "{nombre_destino}" eliminado exitosamente')
        
        # Redireccionar a la lista de destinos
        return redirect('destinos:lista_destinos')
    
    # GET request: mostrar confirmación
    context = {
        'destino': destino,
        'titulo': f'Eliminar {destino.nombre}'
    }
    
    return render(request, 'destinos/eliminar_destino.html', context)