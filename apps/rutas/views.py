from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib import messages
from .models import Ruta, DetalleRuta
from apps.destinos.models import Destino
from apps.servicios.models import Servicio
import json
import os
from django.conf import settings

@login_required
def crear_ruta(request):
    """
    Vista para consultar y planificar rutas (solo lectura)
    """
    # Verificar permisos: permitir administradores, proveedores y turistas
    if not request.user.rol or request.user.rol.nombre not in ['administrador', 'proveedor', 'turista']:
        messages.error(request, 'No tienes permisos para acceder a esta vista')
        return redirect('rutas:lista_rutas')
    
    # GET request
    destinos = Destino.objects.filter(activo=True).order_by('nombre')
    
    # Preparar datos JSON para JavaScript
    destinos_json = json.dumps([{
        'id': d.id,
        'nombre': d.nombre,
        'latitud': float(d.latitud),
        'longitud': float(d.longitud),
        'provincia': d.provincia,
        'ciudad': d.ciudad if d.ciudad else d.provincia,
        'region': d.region,
        'region_display': d.get_region_display(),
        'precio_promedio_minimo': float(d.precio_promedio_minimo),
        'precio_promedio_maximo': float(d.precio_promedio_maximo)
    } for d in destinos])
    
    # ← CORREGIDO + DEBUG: Cargar servicios de transporte desde DB
    servicios_qs = Servicio.objects.filter(
        tipo=Servicio.TRANSPORTE,
        activo=True,
        disponible=True
    ).select_related('destino').values(
        'nombre', 'precio', 'destino__nombre', 'destino__ciudad'  # Asegura todos los campos
    ).order_by('destino__nombre')

    transporte_services = [
        {
            'nombre': item['nombre'],
            'precio': float(item['precio']),
            'destino__nombre': item.get('destino__nombre', ''),  # ← SAFE: Si no existe, vacío
            'destino__ciudad': item['destino__ciudad']
        }
        for item in servicios_qs
    ]

    transporte_services_json = json.dumps(transporte_services)
    
    # Cargar datos de transporte (estructura de puntos/rutas, sin precios)
    transporte_json_path = os.path.join(settings.BASE_DIR, 'static', 'data', 'transporte_ecuador.json')
    try:
        with open(transporte_json_path, 'r', encoding='utf-8') as f:
            transporte_data = json.load(f)
            # ← CAMBIO: No usamos precios del JSON, solo estructura
            # Si quieres remover precios del JSON, edítalo manualmente
            transporte_json = json.dumps(transporte_data)
    except FileNotFoundError:
        transporte_json = json.dumps({})
        messages.warning(request, 'No se encontró el archivo de datos de transporte')
    
    context = {
        'destinos': destinos,
        'destinos_json': destinos_json,
        'transporte_json': transporte_json,
        # ← NUEVO: Pasar servicios de DB a JS
        'transporte_services_json': transporte_services_json,
        'titulo': 'Planificador de Rutas'
    }
    
    return render(request, 'rutas/crear_ruta.html', context)
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from apps.destinos.models import Destino
from apps.servicios.models import Servicio
import json
import os
from unicodedata import normalize
import re


def normalizar_texto(texto):
    """Normaliza texto para búsqueda flexible"""
    if not texto:
        return ""
    texto = texto.lower().strip()
    texto = normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    texto = re.sub(r'\s+', ' ', texto)
    return texto


def cargar_datos_transporte():
    """Carga el JSON de transporte"""
    transporte_json_path = os.path.join(settings.BASE_DIR, 'static', 'data', 'transporte_ecuador.json')
    try:
        with open(transporte_json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


@require_http_methods(["GET"])
def buscar_rutas_ajax(request):
    """
    Busca rutas de transporte entre dos ciudades
    GET params: origen, destino
    """
    origen = request.GET.get('origen', '').strip()
    destino = request.GET.get('destino', '').strip()
    
    if not origen or not destino:
        return JsonResponse({
            'success': False,
            'error': 'Debe especificar origen y destino'
        }, status=400)
    
    datos_transporte = cargar_datos_transporte()
    origen_norm = normalizar_texto(origen)
    destino_norm = normalizar_texto(destino)
    
    rutas_recomendadas = datos_transporte.get('rutas_recomendadas', {})
    
    # 1. Buscar ruta directa
    variaciones = [
        f"{origen_norm}_{destino_norm}",
        f"{destino_norm}_{origen_norm}"
    ]
    
    for var in variaciones:
        if var in rutas_recomendadas:
            return JsonResponse({
                'success': True,
                'rutas': rutas_recomendadas[var],
                'origen': origen,
                'destino': destino,
                'tipo': 'directa'
            })
    
    # 2. Buscar ruta con conexión vía hubs principales
    ciudades_intermedias = ['guayaquil', 'quito']
    
    for intermedia in ciudades_intermedias:
        tramo1_key = f"{origen_norm}_{intermedia}"
        tramo2_key = f"{intermedia}_{destino_norm}"
        
        # Intentar también orden inverso
        if tramo1_key not in rutas_recomendadas:
            tramo1_key = f"{intermedia}_{origen_norm}"
        if tramo2_key not in rutas_recomendadas:
            tramo2_key = f"{destino_norm}_{intermedia}"
        
        if tramo1_key in rutas_recomendadas and tramo2_key in rutas_recomendadas:
            ruta_combinada = {
                "tipo": "conexion",
                "nombre": f"Ruta vía {intermedia.capitalize()}",
                "descripcion": f"Conexión en {intermedia.capitalize()}",
                "tramos": []
            }
            
            # Obtener tramos del primer segmento
            for ruta in rutas_recomendadas[tramo1_key]:
                if ruta.get('tipo') == 'recomendada':
                    ruta_combinada['tramos'].extend(ruta.get('tramos', []))
                    break
            
            # Obtener tramos del segundo segmento
            for ruta in rutas_recomendadas[tramo2_key]:
                if ruta.get('tipo') == 'recomendada':
                    tramos_segundo = ruta.get('tramos', [])
                    offset = len(ruta_combinada['tramos'])
                    for tramo in tramos_segundo:
                        tramo_copia = tramo.copy()
                        tramo_copia['orden'] = tramo['orden'] + offset
                        ruta_combinada['tramos'].append(tramo_copia)
                    break
            
            # Calcular totales
            duracion_total = 0
            for t in ruta_combinada['tramos']:
                duracion_str = t.get('duracion_aprox', '0')
                try:
                    duracion_total += float(duracion_str.split()[0])
                except (ValueError, IndexError):
                    pass
            
            costo_total = sum(t.get('costo_aprox', 0) for t in ruta_combinada['tramos'])
            
            ruta_combinada['duracion_total'] = f"{duracion_total} horas"
            ruta_combinada['costo_total'] = round(costo_total, 2)
            
            return JsonResponse({
                'success': True,
                'rutas': [ruta_combinada],
                'origen': origen,
                'destino': destino,
                'tipo': 'conexion',
                'ciudad_conexion': intermedia.capitalize()
            })
    
    # 3. No se encontró ruta
    ciudades_disponibles = set()
    for clave in rutas_recomendadas.keys():
        partes = clave.split('_')
        ciudades_disponibles.update([p.capitalize() for p in partes])
    
    return JsonResponse({
        'success': False,
        'error': f'No se encontró ruta de {origen} a {destino}',
        'sugerencia': f'Ciudades disponibles: {", ".join(sorted(ciudades_disponibles)[:15])}',
        'rutas': []
    })


@require_http_methods(["GET"])
def puntos_transporte_ajax(request):
    """
    Obtiene terminales, aeropuertos y puertos de una ciudad
    GET params: ciudad, tipo (opcional: terrestre, aereo, maritimo, todos)
    """
    ciudad = request.GET.get('ciudad', '').strip()
    tipo = request.GET.get('tipo', 'todos').lower()
    
    if not ciudad:
        return JsonResponse({
            'success': False,
            'error': 'Debe especificar una ciudad'
        }, status=400)
    
    datos_transporte = cargar_datos_transporte()
    ciudad_norm = normalizar_texto(ciudad)
    
    puntos_encontrados = {
        'terminales': [],
        'aeropuertos': [],
        'puertos': []
    }
    
    # Buscar terminales terrestres
    if tipo in ["terrestre", "todos"]:
        for terminal in datos_transporte.get('terminales_terrestres', []):
            ciudad_terminal = normalizar_texto(terminal.get('ciudad', ''))
            if ciudad_norm in ciudad_terminal or ciudad_terminal in ciudad_norm:
                puntos_encontrados['terminales'].append(terminal)
    
    # Buscar aeropuertos
    if tipo in ["aereo", "todos"]:
        for aero in datos_transporte.get('aeropuertos', []):
            ciudad_aero = normalizar_texto(aero.get('ciudad', ''))
            if ciudad_norm in ciudad_aero or ciudad_aero in ciudad_norm:
                puntos_encontrados['aeropuertos'].append(aero)
    
    # Buscar puertos marítimos
    if tipo in ["maritimo", "todos"]:
        for puerto in datos_transporte.get('puertos_maritimos', []):
            ciudad_puerto = normalizar_texto(puerto.get('ciudad', ''))
            if ciudad_norm in ciudad_puerto or ciudad_puerto in ciudad_norm:
                puntos_encontrados['puertos'].append(puerto)
    
    total_puntos = sum(len(v) for v in puntos_encontrados.values())
    
    return JsonResponse({
        'success': total_puntos > 0,
        'ciudad': ciudad,
        'puntos': puntos_encontrados,
        'total': total_puntos
    })


@require_http_methods(["GET"])
def datos_transporte_completos_ajax(request):
    """
    Retorna todos los datos de transporte (JSON completo)
    Para uso del planificador de rutas
    """
    datos_transporte = cargar_datos_transporte()
    
    return JsonResponse({
        'success': True,
        'datos': datos_transporte
    })


@require_http_methods(["GET"])
def servicios_transporte_ajax(request):
    """
    Retorna servicios de transporte desde la base de datos
    GET params: destino (opcional), precio_max (opcional)
    """
    servicios_qs = Servicio.objects.filter(
        tipo=Servicio.TRANSPORTE,
        activo=True,
        disponible=True
    ).select_related('destino')
    
    # Filtrar por destino si se especifica
    destino_nombre = request.GET.get('destino', '').strip()
    if destino_nombre:
        servicios_qs = servicios_qs.filter(
            Q(destino__nombre__icontains=destino_nombre) |
            Q(destino__ciudad__icontains=destino_nombre)
        )
    
    # Filtrar por precio máximo
    precio_max = request.GET.get('precio_max')
    if precio_max:
        try:
            servicios_qs = servicios_qs.filter(precio__lte=float(precio_max))
        except ValueError:
            pass
    
    # Serializar servicios
    servicios_data = []
    for servicio in servicios_qs[:50]:  # Limitar a 50 resultados
        servicios_data.append({
            'id': servicio.id,
            'nombre': servicio.nombre,
            'descripcion': servicio.descripcion,
            'precio': float(servicio.precio),
            'destino': {
                'id': servicio.destino.id if servicio.destino else None,
                'nombre': servicio.destino.nombre if servicio.destino else '',
                'ciudad': servicio.destino.ciudad if servicio.destino else ''
            },
            'disponibilidad': servicio.disponibilidad,
            'calificacion_promedio': float(servicio.calificacion_promedio) if servicio.calificacion_promedio else 0
        })
    
    return JsonResponse({
        'success': True,
        'servicios': servicios_data,
        'total': len(servicios_data)
    })


@require_http_methods(["GET"])
def destinos_con_coordenadas_ajax(request):
    """
    Retorna destinos activos con coordenadas para mapeo
    """
    destinos = Destino.objects.filter(activo=True).order_by('nombre')
    
    destinos_data = [{
        'id': d.id,
        'nombre': d.nombre,
        'slug': d.slug,
        'latitud': float(d.latitud),
        'longitud': float(d.longitud),
        'provincia': d.provincia,
        'ciudad': d.ciudad if d.ciudad else d.provincia,
        'region': d.region,
        'region_display': d.get_region_display(),
        'precio_promedio_minimo': float(d.precio_promedio_minimo),
        'precio_promedio_maximo': float(d.precio_promedio_maximo),
        'descripcion_corta': d.descripcion[:200] if d.descripcion else ''
    } for d in destinos]
    
    return JsonResponse({
        'success': True,
        'destinos': destinos_data,
        'total': len(destinos_data)
    })