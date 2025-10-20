# apps/chatbot/views.py - VERSIÓN OPTIMIZADA CON GPT-4
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
import json
from django.test import RequestFactory
from datetime import datetime, timedelta
import hashlib
import re
from unicodedata import normalize


# ============================================
# UTILIDADES BÁSICAS (SIN HARDCODEAR DATOS)
# ============================================

class TextNormalizer:
    """
    Normalización básica de texto - El resto lo hace GPT-4
    """
    
    @staticmethod
    def normalizar_basico(texto):
        """
        Normalización básica: minúsculas, espacios, etc.
        NO corrige ortografía (eso lo hace GPT-4)
        """
        if not texto:
            return ""
        
        texto = texto.lower().strip()
        texto = normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
        texto = re.sub(r'\s+', ' ', texto)
        
        return texto


# ============================================
# SISTEMA DE MEMORIA (SIMPLIFICADO)
# ============================================

class ChatbotMemory:
    """
    Sistema de memoria optimizado - GPT-4 hace el análisis semántico
    """
    
    @staticmethod
    def generar_hash_consulta(query):
        """Genera hash para caché"""
        query_norm = TextNormalizer.normalizar_basico(query)
        return hashlib.md5(query_norm.encode()).hexdigest()
    
    @staticmethod
    def registrar_consulta_exitosa(query, funcion_usada, resultado):
        """Registra consultas exitosas"""
        hash_query = ChatbotMemory.generar_hash_consulta(query)
        cache_key = f"chatbot_success_{hash_query}"
        
        data = {
            'query': query,
            'funcion': funcion_usada,
            'timestamp': datetime.now().isoformat(),
            'tuvo_resultados': bool(resultado.get('servicios') or resultado.get('destinos') or resultado.get('data'))
        }
        
        cache.set(cache_key, data, timeout=86400 * 30)
        
        counter_key = f"chatbot_success_count_{funcion_usada}"
        count = cache.get(counter_key, 0)
        cache.set(counter_key, count + 1, timeout=86400 * 30)
    
    @staticmethod
    def registrar_error(query, error_msg):
        """Registra errores"""
        hash_query = ChatbotMemory.generar_hash_consulta(query)
        cache_key = f"chatbot_error_{hash_query}"
        
        data = {
            'query': query,
            'error': error_msg,
            'timestamp': datetime.now().isoformat(),
            'count': cache.get(cache_key, {}).get('count', 0) + 1
        }
        
        cache.set(cache_key, data, timeout=86400 * 7)


# ============================================
# CLIENTE OPENAI
# ============================================

def get_openai_client():
    """Inicializa el cliente de OpenAI"""
    from openai import OpenAI
    
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY no configurada")
    
    return OpenAI(api_key=api_key)


# ============================================
# HERRAMIENTAS (FUNCIONES)
# ============================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_servicios",
            "description": "Busca servicios turísticos por PALABRAS CLAVE (no nombres exactos). La búsqueda es flexible y encuentra coincidencias parciales. Ejemplos: 'oro verde' encuentra 'Oro Verde Manta', 'hilton' encuentra 'Hilton Colon Quito'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "PALABRAS CLAVE del servicio (NO nombre completo). Ejemplos: 'oro verde' (no 'Hotel Oro Verde'), 'hilton' (no 'Hotel Hilton Colon'), 'casa cangrejo' (no 'Restaurante La Casa del Cangrejo'). Elimina palabras genéricas como 'hotel', 'restaurante', 'tour'."
                    },
                    "tipo": {
                        "type": "string",
                        "enum": ["alojamiento", "tour", "actividad", "transporte", "gastronomia"],
                        "description": "Tipo de servicio"
                    },
                    "region": {
                        "type": "string",
                        "enum": ["costa", "sierra", "oriente", "galapagos"],
                        "description": "Región de Ecuador"
                    },
                    "precio_max": {
                        "type": "number",
                        "description": "Precio máximo en dólares"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_destinos",
            "description": "Busca destinos turísticos por PALABRAS CLAVE (ciudades, lugares, atractivos). Búsqueda flexible que encuentra coincidencias parciales.",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "PALABRAS CLAVE del destino (ciudad, provincia, lugar). Usa palabras distintivas. Ejemplos: 'quito', 'cuenca', 'galapagos'. Normaliza nombres (ej: 'Kito' → 'quito', 'Guayakil' → 'guayaquil')"
                    },
                    "region": {
                        "type": "string",
                        "enum": ["costa", "sierra", "oriente", "galapagos"],
                        "description": "Región específica"
                    }
                },
                "required": ["q"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_destinos_por_region",
            "description": "Obtiene los mejores destinos de una región completa.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "enum": ["costa", "sierra", "oriente", "galapagos"]
                    }
                },
                "required": ["region"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_estadisticas_servicios",
            "description": "Estadísticas generales de servicios disponibles",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_estadisticas_destinos",
            "description": "Estadísticas generales de destinos turísticos",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "comparar_servicios",
            "description": "Compara múltiples servicios por precio y calificación",
            "parameters": {
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "string",
                        "description": "IDs separados por comas (ej: '1,2,3')"
                    }
                },
                "required": ["ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_recomendaciones",
            "description": "Recomendaciones personalizadas según criterios del usuario",
            "parameters": {
                "type": "object",
                "properties": {
                    "presupuesto": {"type": "number"},
                    "tipo": {
                        "type": "string",
                        "enum": ["alojamiento", "tour", "actividad", "transporte", "gastronomia"]
                    },
                    "region": {
                        "type": "string",
                        "enum": ["costa", "sierra", "oriente", "galapagos"]
                    },
                    "personas": {"type": "integer"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_estadisticas_reservas",
            "description": "Estadísticas generales de reservas del sistema",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_mis_estadisticas",
            "description": "Estadísticas personales del usuario autenticado",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]


# ============================================
# SYSTEM PROMPT OPTIMIZADO
# ============================================

SYSTEM_PROMPT = """Eres "Guía Ecuador" 🇪🇨, el asistente turístico inteligente de Ecuador.

🎯 **TU MISIÓN:**
Ayudar a turistas con información REAL y VERIFICADA de nuestra base de datos.

🧠 **CAPACIDADES ESPECIALES:**
1. **CORRECCIÓN ORTOGRÁFICA AUTOMÁTICA:**
   - El usuario puede escribir con errores: "hoteles en kito" → interpretas "Quito"
   - Nombres mal escritos: "Guayakil" → "Guayaquil", "Cuenka" → "Cuenca"
   - Palabras en español: "resturante" → "restaurante", "hospedage" → "hospedaje"
   - SIEMPRE normaliza y corrige ANTES de llamar funciones

2. **BÚSQUEDA FLEXIBLE Y POR PALABRAS CLAVE:**
   - Usuario dice "Hotel Oro Verde" → busca q="oro verde" (palabras clave principales)
   - Usuario dice "restaurante El Coral" → busca q="coral" o q="el coral"
   - Si el nombre tiene ubicación, sepárala: "Oro Verde Manta" → busca "oro verde" con filtros
   - **REGLA DE ORO**: Usa las palabras más distintivas del nombre, NO el nombre completo
   
   Ejemplos:
   ✅ "Hotel Oro Verde" → buscar_servicios(q="oro verde", tipo="alojamiento")
   ✅ "Hilton Colon Quito" → buscar_servicios(q="hilton colon", tipo="alojamiento")
   ✅ "tour galapagos" → buscar_servicios(q="galapagos", tipo="tour")
   ❌ NO uses el nombre exacto completo si no hay resultados

3. **ESTRATEGIA DE BÚSQUEDA INCREMENTAL:**
   - Primer intento: busca con palabras clave principales
   - Si no hay resultados: prueba con menos palabras o variaciones
   - Ejemplos:
     * "Hotel Oro Verde Guayaquil" → primero "oro verde", luego "oro verde" + region
     * "Restaurante La Casa del Cangrejo" → primero "casa cangrejo", luego "cangrejo"

4. **DIFERENCIACIÓN CLARA:**
   - 🏨 SERVICIOS = Cosas que se RESERVAN (hoteles, tours, restaurantes, transporte)
   - 🏞️ DESTINOS = Lugares que se VISITAN (ciudades, provincias, atractivos)
   
   Ejemplos:
   - "hoteles en Quito" → buscar_servicios(q="quito", tipo="alojamiento")
   - "qué visitar en Quito" → buscar_destinos(q="quito")
   - "restaurantes en la sierra" → buscar_servicios(tipo="gastronomia", region="sierra")
   - "Hotel Oro Verde" → buscar_servicios(q="oro verde", tipo="alojamiento")

4. **PARÁMETROS INTELIGENTES:**
   - Regiones válidas: costa, sierra, oriente, galapagos (MINÚSCULAS, sin artículos)
   - Si el usuario dice "en la costa" → usa region="costa"
   - Combina múltiples filtros cuando sea apropiado
   - **IMPORTANTE**: El parámetro 'q' debe contener solo palabras clave distintivas

🚫 **PROHIBIDO:**
- Usar nombres completos en el parámetro 'q' (ej: ❌ "Hotel Oro Verde Manta", ✅ "oro verde")
- Inventar datos que no están en los resultados
- Mencionar lugares/servicios que no aparecen en la respuesta de las funciones
- Ignorar errores ortográficos del usuario (SIEMPRE normaliza primero)
- Responder sin consultar las funciones cuando se necesita información específica
- Incluir palabras genéricas en búsquedas: ❌ "hotel oro verde" → ✅ "oro verde"

✅ **FLUJO DE TRABAJO:**
1. Usuario envía mensaje (puede tener errores, puede ser nombre completo)
2. TÚ extraes las palabras CLAVE distintivas (elimina "hotel", "restaurante", ubicaciones obvias)
3. Llamas a la función con palabras clave + filtros (tipo, región)
4. Si NO hay resultados, prueba con menos palabras o sin filtros
5. Respondes basándote SOLO en los resultados reales
6. Si aún no hay resultados, lo dices claramente y ofreces alternativas

📏 **ESTILO:**
- Conciso: máximo 150 palabras
- Amigable y profesional
- Usa emojis moderadamente (2-3 por mensaje)
- Siempre termina con pregunta de seguimiento
- Si corriges ortografía del usuario, hazlo de forma natural sin señalarlo

**EJEMPLO DE BÚSQUEDA CORRECTA:**
Usuario: "buscame hotel oro verde"
TÚ piensas: "Quiere el hotel Oro Verde, pero debo buscar por palabras clave"
TÚ llamas: buscar_servicios(q="oro verde", tipo="alojamiento")
Base de datos tiene: "Oro Verde Manta", "Oro Verde Guayaquil"
TÚ respondes: "¡Encontré 2 opciones del Oro Verde! 🏨
1. **Oro Verde Manta**...
2. **Oro Verde Guayaquil**...
¿Cuál te interesa?"

**EJEMPLO DE BÚSQUEDA INCREMENTAL:**
Usuario: "Hotel Hilton Colon Quito"
Intento 1: buscar_servicios(q="hilton colon", tipo="alojamiento") → ✅ encuentra
Si no encuentra:
Intento 2: buscar_servicios(q="hilton", tipo="alojamiento") → buscar alternativa

**NUNCA DIGAS:** "No encontré 'Hotel Oro Verde' exacto" 
**SÍ DI:** "No encontré hoteles con ese nombre" (después de intentar variaciones)"""


# ============================================
# EJECUTOR DE FUNCIONES
# ============================================

def ejecutar_funcion(nombre_funcion, parametros, request=None):
    """
    Ejecuta funciones AJAX con validación
    """
    from apps.servicios.views import (
        buscar_servicios_ajax,
        estadisticas_servicios_ajax,
        comparar_servicios_ajax,
        recomendaciones_ajax
    )
    from apps.destinos.views import (
        busqueda_ajax,
        estadisticas_destinos_ajax,
        destinos_por_region_ajax
    )
    from apps.reservas.views import (
        estadisticas_reservas_ajax,
        mis_estadisticas_ajax
    )
    
    # Limpiar parámetros (remover vacíos y None)
    parametros_limpios = {
        k: v for k, v in parametros.items()
        if v is not None and v != "" and v != 0
    }
    
    factory = RequestFactory()
    
    try:
        # SERVICIOS
        if nombre_funcion == "buscar_servicios":
            req = factory.get('/ajax/buscar-servicios/', parametros_limpios)
            response = buscar_servicios_ajax(req)
            return json.loads(response.content)
        
        elif nombre_funcion == "obtener_estadisticas_servicios":
            req = factory.get('/ajax/estadisticas-servicios/')
            response = estadisticas_servicios_ajax(req)
            return json.loads(response.content)
        
        elif nombre_funcion == "comparar_servicios":
            req = factory.get('/ajax/comparar-servicios/', parametros_limpios)
            response = comparar_servicios_ajax(req)
            return json.loads(response.content)
        
        elif nombre_funcion == "obtener_recomendaciones":
            req = factory.get('/ajax/recomendaciones/', parametros_limpios)
            response = recomendaciones_ajax(req)
            return json.loads(response.content)
        
        # DESTINOS
        elif nombre_funcion == "buscar_destinos":
            req = factory.get('/destinos/ajax/busqueda/', parametros_limpios)
            response = busqueda_ajax(req)
            return json.loads(response.content)
        
        elif nombre_funcion == "obtener_destinos_por_region":
            region = parametros_limpios.get('region', '')
            if not region:
                return {"error": "Debe especificar una región", "success": False}
            req = factory.get(f'/destinos/ajax/region/{region}/')
            response = destinos_por_region_ajax(req, region)
            return json.loads(response.content)
        
        elif nombre_funcion == "obtener_estadisticas_destinos":
            req = factory.get('/destinos/ajax/estadisticas/')
            response = estadisticas_destinos_ajax(req)
            return json.loads(response.content)
        
        # RESERVAS
        elif nombre_funcion == "obtener_estadisticas_reservas":
            req = factory.get('/ajax/estadisticas-reservas/')
            response = estadisticas_reservas_ajax(req)
            return json.loads(response.content)
        
        elif nombre_funcion == "obtener_mis_estadisticas":
            if not request or not request.user.is_authenticated:
                return {
                    "error": "Debes iniciar sesión para ver tus estadísticas",
                    "success": False
                }
            req = factory.get('/ajax/mis-estadisticas/')
            req.user = request.user
            response = mis_estadisticas_ajax(req)
            return json.loads(response.content)
        
        return {"error": f"Función {nombre_funcion} no encontrada", "success": False}
    
    except Exception as e:
        import traceback
        print(f"❌ Error ejecutando {nombre_funcion}: {str(e)}")
        print(traceback.format_exc())
        return {"error": str(e), "success": False, "traceback": traceback.format_exc()[:500]}


# ============================================
# VISTA PRINCIPAL DEL CHATBOT
# ============================================

@require_http_methods(["POST"])
def chatbot_message(request):
    """
    Procesa mensajes del chatbot con GPT-4 (maneja errores ortográficos automáticamente)
    """
    try:
        data = json.loads(request.body)
        mensaje_usuario = data.get('message', '').strip()
        historial = data.get('history', [])
        
        if not mensaje_usuario:
            return JsonResponse({
                'success': False,
                'error': 'Mensaje vacío'
            }, status=400)
        
        # Construir mensajes para GPT-4
        mensajes = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Incluir historial reciente (últimos 10 mensajes)
        for msg in historial[-10:]:
            if msg.get('role') in ['user', 'assistant']:
                mensajes.append({
                    "role": msg['role'],
                    "content": msg.get('content', '')
                })
        
        # Agregar mensaje actual
        mensajes.append({
            "role": "user",
            "content": mensaje_usuario
        })
        
        # ========================================
        # PRIMERA LLAMADA A GPT-4
        # ========================================
        client = get_openai_client()
        
        respuesta_inicial = client.chat.completions.create(
            model="gpt-4-turbo-preview",  # Cambiar a "gpt-4o" si tienes acceso
            messages=mensajes,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=600
        )
        
        mensaje_asistente = respuesta_inicial.choices[0].message
        
        # ========================================
        # PROCESAR LLAMADAS A FUNCIONES
        # ========================================
        if mensaje_asistente.tool_calls:
            resultados_funciones = []
            
            for tool_call in mensaje_asistente.tool_calls:
                nombre_funcion = tool_call.function.name
                
                try:
                    argumentos = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as e:
                    print(f"⚠️ Error parseando argumentos: {e}")
                    argumentos = {}
                
                # Ejecutar función
                print(f"🔧 Ejecutando: {nombre_funcion}({argumentos})")
                resultado = ejecutar_funcion(nombre_funcion, argumentos, request)
                
                # Registrar en memoria
                if resultado.get('success'):
                    ChatbotMemory.registrar_consulta_exitosa(
                        mensaje_usuario,
                        nombre_funcion,
                        resultado
                    )
                else:
                    print(f"⚠️ Función retornó error: {resultado.get('error')}")
                
                resultados_funciones.append({
                    "tool_call_id": tool_call.id,
                    "nombre": nombre_funcion,
                    "argumentos": argumentos,
                    "resultado": resultado,
                    "exitoso": resultado.get('success', False)
                })
            
            # ========================================
            # SEGUNDA LLAMADA CON RESULTADOS
            # ========================================
            
            # Construir mensajes con resultados de funciones
            mensajes_con_resultados = mensajes + [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": mensaje_asistente.tool_calls
                }
            ]
            
            # Agregar resultados de cada función
            for res in resultados_funciones:
                mensajes_con_resultados.append({
                    "role": "tool",
                    "tool_call_id": res["tool_call_id"],
                    "name": res["nombre"],
                    "content": json.dumps(res["resultado"], ensure_ascii=False)
                })
            
            # Agregar instrucciones finales
            instrucciones_finales = """
RESULTADOS OBTENIDOS. Ahora responde al usuario:

🎯 REGLAS CRÍTICAS:
1. Usa SOLO los datos de los resultados anteriores
2. Si 'servicios' o 'destinos' está vacío → di "No encontré..."
3. Sé conciso (máximo 150 palabras)
4. Incluye enlaces solo si hay IDs reales
5. Termina con pregunta de seguimiento
6. Si encontraste múltiples opciones del mismo nombre en diferentes ubicaciones, menciónalas todas

EJEMPLOS DE RESPUESTAS CORRECTAS:
✅ Usuario buscó "Hotel Oro Verde" y encontraste 2:
"¡Encontré 2 opciones del Oro Verde! 🏨
1. **Oro Verde Manta** - $120/noche ⭐4.5
2. **Oro Verde Guayaquil** - $150/noche ⭐4.8
¿Cuál ubicación prefieres?"

✅ Usuario buscó "Hilton" y encontraste 1:
"¡Perfecto! Encontré el **Hilton Colon Quito** 🏨..."

❌ NO digas: "No encontré 'Hotel Oro Verde' exactamente" (si lo encontraste con búsqueda flexible)

NO inventes datos. NO menciones lugares que no aparecen en los resultados."""
            
            mensajes_con_resultados.append({
                "role": "user",
                "content": instrucciones_finales
            })
            
            # Generar respuesta final
            respuesta_final = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=mensajes_con_resultados,
                temperature=0.7,
                max_tokens=500
            )
            
            respuesta_texto = respuesta_final.choices[0].message.content
            
            debug_info = {
                'funciones_usadas': [r['nombre'] for r in resultados_funciones],
                'argumentos': [r['argumentos'] for r in resultados_funciones],
                'resultados_exitosos': [r['exitoso'] for r in resultados_funciones]
            }
        else:
            # No se necesitaron funciones
            respuesta_texto = mensaje_asistente.content or "Lo siento, no pude generar una respuesta."
            debug_info = {'funciones_usadas': [], 'mensaje': 'Respuesta directa sin funciones'}
        
        return JsonResponse({
            'success': True,
            'response': respuesta_texto,
            'debug': debug_info if settings.DEBUG else None
        })
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        
        print(f"❌ Error en chatbot: {error_msg}")
        print(error_trace)
        
        # Registrar error
        if 'mensaje_usuario' in locals():
            ChatbotMemory.registrar_error(mensaje_usuario, error_msg)
        
        # Respuesta amigable al usuario
        return JsonResponse({
            'success': False,
            'error': 'Lo siento, ocurrió un error al procesar tu mensaje. Por favor intenta de nuevo.',
            'debug': {'error': error_msg, 'trace': error_trace[:500]} if settings.DEBUG else None
        }, status=500)


@require_http_methods(["POST"])
def limpiar_historial(request):
    """Limpia el historial del chat"""
    return JsonResponse({'success': True, 'message': 'Historial limpiado'})


@require_http_methods(["GET"])
def estadisticas_chatbot(request):
    """
    Obtiene estadísticas de uso del chatbot (solo para admins)
    """
    if not request.user.is_authenticated or request.user.rol.nombre != 'administrador':
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    try:
        stats = {
            'funciones_mas_usadas': {},
            'total_consultas': 0
        }
        
        # Obtener contadores de funciones
        funciones = [
            'buscar_servicios', 'buscar_destinos', 'obtener_estadisticas_servicios',
            'obtener_estadisticas_destinos', 'comparar_servicios', 'obtener_recomendaciones',
            'obtener_destinos_por_region', 'obtener_estadisticas_reservas', 'obtener_mis_estadisticas'
        ]
        
        for func in funciones:
            count = cache.get(f"chatbot_success_count_{func}", 0)
            if count > 0:
                stats['funciones_mas_usadas'][func] = count
                stats['total_consultas'] += count
        
        return JsonResponse({
            'success': True,
            'estadisticas': stats
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)