# apps/chatbot/views.py - VERSIÓN CON OPENAI GPT-4
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
import json
from django.test import RequestFactory
from datetime import datetime, timedelta
import hashlib


# SISTEMA DE APRENDIZAJE Y MEMORIA

class ChatbotMemory:
    """
    Sistema de memoria para que el chatbot aprenda de interacciones
    """
    
    @staticmethod
    def generar_hash_consulta(query):
        """Genera un hash único para una consulta"""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()
    
    @staticmethod
    def registrar_consulta_exitosa(query, funcion_usada, resultado):
        """
        Registra una consulta exitosa para aprendizaje futuro
        """
        hash_query = ChatbotMemory.generar_hash_consulta(query)
        cache_key = f"chatbot_success_{hash_query}"
        
        data = {
            'query': query,
            'funcion': funcion_usada,
            'timestamp': datetime.now().isoformat(),
            'resultado_type': type(resultado).__name__,
            'tuvo_resultados': bool(resultado.get('servicios') or resultado.get('destinos'))
        }
        
        cache.set(cache_key, data, timeout=86400 * 30)  # 30 días
        
        # Incrementar contador de éxito
        counter_key = f"chatbot_success_count_{funcion_usada}"
        count = cache.get(counter_key, 0)
        cache.set(counter_key, count + 1, timeout=86400 * 30)
    
    @staticmethod
    def registrar_error(query, error_msg):
        """
        Registra errores para análisis posterior
        """
        hash_query = ChatbotMemory.generar_hash_consulta(query)
        cache_key = f"chatbot_error_{hash_query}"
        
        data = {
            'query': query,
            'error': error_msg,
            'timestamp': datetime.now().isoformat(),
            'count': cache.get(cache_key, {}).get('count', 0) + 1
        }
        
        cache.set(cache_key, data, timeout=86400 * 7)  # 7 días
    
    @staticmethod
    def obtener_consultas_similares(query):
        """
        Busca consultas similares exitosas en el caché
        """
        # Buscar en caché las últimas 50 consultas exitosas
        pattern = "chatbot_success_*"
        keys = cache.keys(pattern)[:50] if hasattr(cache, 'keys') else []
        
        similares = []
        query_words = set(query.lower().split())
        
        for key in keys:
            data = cache.get(key)
            if data and data.get('tuvo_resultados'):
                stored_words = set(data['query'].lower().split())
                # Calcular similitud simple
                interseccion = len(query_words & stored_words)
                if interseccion >= 2:  # Al menos 2 palabras en común
                    similares.append({
                        'query': data['query'],
                        'funcion': data['funcion'],
                        'similitud': interseccion
                    })
        
        return sorted(similares, key=lambda x: x['similitud'], reverse=True)[:3]


# VALIDADOR DE CONTEXTO

class ContextValidator:
    """
    Valida y mejora el contexto de las consultas
    """
    
    KEYWORDS_SERVICIOS = [
        'hotel', 'alojamiento', 'hospedaje', 'tour', 'excursión',
        'actividad', 'transporte', 'restaurante', 'comida', 'gastronomía',
        'reservar', 'precio', 'costo', 'cuánto cuesta', 'disponibilidad'
    ]
    
    KEYWORDS_DESTINOS = [
        'destino', 'lugar', 'ciudad', 'provincia', 'visitar',
        'conocer', 'lugares turísticos', 'atractivos', 'dónde ir',
        'qué ver', 'región', 'zona'
    ]
    
    KEYWORDS_RESERVAS = [
        'reserva', 'reservas', 'mis reservas', 'mis viajes',
        'confirmación', 'cancelar', 'estado', 'historial'
    ]
    
    @staticmethod
    def identificar_intencion(mensaje):
        """
        Identifica la intención principal del mensaje
        Returns: dict con tipo e indicadores de confianza
        """
        msg_lower = mensaje.lower()
        
        scores = {
            'servicios': sum(1 for kw in ContextValidator.KEYWORDS_SERVICIOS if kw in msg_lower),
            'destinos': sum(1 for kw in ContextValidator.KEYWORDS_DESTINOS if kw in msg_lower),
            'reservas': sum(1 for kw in ContextValidator.KEYWORDS_RESERVAS if kw in msg_lower)
        }
        
        tipo_principal = max(scores, key=scores.get)
        confianza = scores[tipo_principal]
        
        return {
            'tipo': tipo_principal if confianza > 0 else 'general',
            'confianza': confianza,
            'scores': scores,
            'necesita_aclaracion': confianza == 0 or (scores['servicios'] == scores['destinos'] and scores['servicios'] > 0)
        }
    
    @staticmethod
    def extraer_parametros(mensaje):
        """
        Extrae parámetros clave del mensaje
        """
        msg_lower = mensaje.lower()
        params = {}
        
        # Detectar región
        regiones = {
            'costa': ['costa', 'playa', 'guayaquil', 'manta', 'salinas'],
            'sierra': ['sierra', 'quito', 'cuenca', 'montaña', 'andes'],
            'oriente': ['oriente', 'amazonía', 'amazonia', 'selva'],
            'galapagos': ['galápagos', 'galapagos', 'islas']
        }
        
        for region, keywords in regiones.items():
            if any(kw in msg_lower for kw in keywords):
                params['region'] = region
                break
        
        # Detectar tipo de servicio
        tipos = {
            'alojamiento': ['hotel', 'alojamiento', 'hospedaje', 'hostal'],
            'tour': ['tour', 'excursión', 'recorrido'],
            'actividad': ['actividad', 'aventura', 'deportes'],
            'transporte': ['transporte', 'traslado', 'taxi', 'bus'],
            'gastronomia': ['restaurante', 'comida', 'gastronomía', 'comer']
        }
        
        for tipo, keywords in tipos.items():
            if any(kw in msg_lower for kw in keywords):
                params['tipo'] = tipo
                break
        
        # Detectar presupuesto
        import re
        precio_match = re.search(r'\$?\s*(\d+)\s*(?:dólares|dolares|usd)?', msg_lower)
        if precio_match:
            params['precio_max'] = int(precio_match.group(1))
        
        return params


# INICIALIZACIÓN Y HERRAMIENTAS

def get_openai_client():
    """Inicializa el cliente de OpenAI de forma lazy"""
    from openai import OpenAI
    
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError(
            "❌ OPENAI_API_KEY no configurada. "
            "Verifica tu archivo .env"
        )
    
    return OpenAI(api_key=api_key)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_servicios",
            "description": "Busca servicios turísticos (hoteles, tours, actividades, transporte, restaurantes). USAR PARA: reservas, precios, disponibilidad de servicios.",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "Término de búsqueda general"
                    },
                    "tipo": {
                        "type": "string",
                        "enum": ["alojamiento", "tour", "actividad", "transporte", "gastronomia"],
                        "description": "Tipo específico de servicio"
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
            "description": "Busca destinos turísticos (ciudades, lugares, atractivos). USAR PARA: información de lugares, qué visitar, dónde ir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "Nombre del destino, ciudad o provincia"
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
            "description": "Obtiene los mejores destinos de una región. USAR PARA: explorar una región completa.",
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
            "description": "Estadísticas de servicios disponibles",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_estadisticas_destinos",
            "description": "Estadísticas de destinos turísticos",
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
                        "description": "IDs separados por comas (ejemplo: '1,2,3')"
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
            "description": "Recomendaciones personalizadas según criterios",
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
            "description": "Obtiene estadísticas generales de reservas del sistema",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_mis_estadisticas",
            "description": "Obtiene estadísticas personales del usuario autenticado (solo si está logueado)",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]


SYSTEM_PROMPT = """Eres "Guía Ecuador" 🇪🇨, el asistente turístico inteligente de Ecuador.

🎯 **TU MISIÓN:**
Ayudar a turistas con información REAL y VERIFICADA de nuestra base de datos.

🧠 **REGLAS DE ORO - NUNCA LAS ROMPAS:**

1. **DIFERENCIA CLARAMENTE:**
   - 🏨 SERVICIOS = Hoteles, tours, actividades, restaurantes, transporte (cosas que se RESERVAN)
   - 🏞️ DESTINOS = Ciudades, lugares, provincias, atractivos (lugares que se VISITAN)
   
2. **USA LA HERRAMIENTA CORRECTA:**
   - Usuario pregunta por hoteles/tours/restaurantes/comedores → `buscar_servicios` con tipo='gastronomia'
   - Usuario pregunta por ciudades/lugares/qué visitar → `buscar_destinos`
   - Usuario menciona una REGIÓN (costa/sierra/oriente/galapagos) → SIEMPRE usa el parámetro `region`
   - Ejemplo: "restaurantes en la sierra" → buscar_servicios(tipo='gastronomia', region='sierra')

3. **BÚSQUEDA POR REGIÓN:**
   - Las regiones válidas son SOLO: costa, sierra, oriente, galapagos (en MINÚSCULAS)
   - Si el usuario dice "la sierra", "en la costa", etc. → usa 'sierra', 'costa' sin artículos
   - SIEMPRE combina región con tipo cuando el usuario lo especifica

4. **NUNCA INVENTES DATOS:**
   - Solo habla de lo que retornan las herramientas
   - Si no hay resultados, di claramente "No encontré..."
   - NO menciones lugares/servicios que no aparecen en los resultados

5. **SIEMPRE USA HERRAMIENTAS ANTES DE RESPONDER:**
   - Consulta específica → Buscar primero, responder después
   - Duda entre opciones → Mejor usar 2 herramientas que adivinar

6. **FORMATO DE RESPUESTA:**
   ```
   ✅ CON RESULTADOS:
   "¡Encontré [N] opciones!
   
   1. **[Nombre]** - $[Precio] ⭐[Rating]
      📍 [Ubicación] • [Tipo]
      [Ver más](/servicios/[ID]/)
   
   ¿Quieres más detalles de alguno?"
   
   ❌ SIN RESULTADOS:
   "No encontré [búsqueda específica]. 😔
   
   ¿Te interesaría ver [alternativa real]?"
   ```

7. **MANEJO DE AMBIGÜEDAD:**
   - Si no estás seguro → Pregunta al usuario
   - "¿Buscas hoteles EN Quito o información SOBRE Quito?"

🚫 **PROHIBIDO:**
- Mencionar destinos sin buscarlos primero
- Inventar precios o datos
- Confundir servicios con destinos
- Responder sin usar herramientas
- Ignorar el parámetro region cuando el usuario lo menciona

✅ **PERMITIDO:**
- Usar 2+ herramientas si es necesario
- Decir "no sé" cuando no hay datos
- Pedir aclaración al usuario

📏 **ESTILO:**
- Conciso: máximo 150 palabras
- Amigable pero profesional
- Usa emojis moderadamente (2-3 por mensaje)
- Siempre termina con pregunta de seguimiento"""


# EJECUTOR DE FUNCIONES MEJORADO

def ejecutar_funcion(nombre_funcion, parametros, request=None):
    """
    Ejecuta funciones AJAX con validación y logging mejorado
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
    
    # Limpiar parámetros
    parametros_limpios = {
        k: v for k, v in parametros.items()
        if v and v != "" and v != 0
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
        print(f"Error ejecutando {nombre_funcion}: {str(e)}")
        print(traceback.format_exc())
        return {"error": str(e), "success": False}


# VISTA PRINCIPAL DEL CHATBOT

@require_http_methods(["POST"])
def chatbot_message(request):
    """
    Procesa mensajes del chatbot con sistema de aprendizaje usando OpenAI GPT-4
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
        
        # ========================================
        # ANÁLISIS PREVIO DEL CONTEXTO
        # ========================================
        intencion = ContextValidator.identificar_intencion(mensaje_usuario)
        params_detectados = ContextValidator.extraer_parametros(mensaje_usuario)
        consultas_similares = ChatbotMemory.obtener_consultas_similares(mensaje_usuario)
        
        # Construir contexto mejorado
        contexto_extra = f"\n\n**ANÁLISIS DE CONTEXTO:**\n"
        contexto_extra += f"- Intención detectada: {intencion['tipo']} (confianza: {intencion['confianza']})\n"
        
        if params_detectados:
            contexto_extra += f"- Parámetros detectados: {json.dumps(params_detectados, ensure_ascii=False)}\n"
        
        if consultas_similares:
            contexto_extra += f"- Consultas similares exitosas: {len(consultas_similares)}\n"
            for sim in consultas_similares[:2]:
                contexto_extra += f"  · '{sim['query']}' → {sim['funcion']}\n"
        
        if intencion['necesita_aclaracion']:
            contexto_extra += "⚠️ AMBIGÜEDAD DETECTADA: Considera preguntar si busca SERVICIOS o DESTINOS\n"
        
        # Construir mensajes para LLM
        mensajes = [{"role": "system", "content": SYSTEM_PROMPT + contexto_extra}]
        
        # Incluir historial (últimos 8 mensajes)
        for msg in historial[-8:]:
            if msg.get('role') in ['user', 'assistant']:
                mensajes.append({
                    "role": msg['role'],
                    "content": msg.get('content', '')
                })
        
        mensajes.append({
            "role": "user",
            "content": mensaje_usuario
        })
    
        # PRIMERA LLAMADA A OPENAI
        client = get_openai_client()
        
        respuesta_openai = client.chat.completions.create(
            model="gpt-4-turbo-preview",  # Cambia a gpt-4o si tienes acceso
            messages=mensajes,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.6,
            max_tokens=500
        )
        
        mensaje_asistente = respuesta_openai.choices[0].message
        
        # PROCESAR HERRAMIENTAS
        resultados_herramientas = []
        
        if mensaje_asistente.tool_calls:
            for tool_call in mensaje_asistente.tool_calls:
                nombre_funcion = tool_call.function.name
                
                try:
                    argumentos = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    argumentos = {}
                
                # Ejecutar función
                resultado = ejecutar_funcion(nombre_funcion, argumentos, request)
                
                # Registrar en memoria
                if resultado.get('success'):
                    ChatbotMemory.registrar_consulta_exitosa(
                        mensaje_usuario,
                        nombre_funcion,
                        resultado
                    )
                
                resultados_herramientas.append({
                    "nombre": nombre_funcion,
                    "argumentos": argumentos,
                    "resultado": resultado,
                    "exitoso": resultado.get('success', False)
                })

            # SEGUNDA LLAMADA CON RESULTADOS
            contexto_herramientas = "\n\n**RESULTADOS DE CONSULTAS:**\n"
            
            for res in resultados_herramientas:
                estado = "✅ ÉXITO" if res['exitoso'] else "❌ ERROR"
                contexto_herramientas += f"\n**{res['nombre']}** {estado}:\n"
                contexto_herramientas += f"```json\n{json.dumps(res['resultado'], ensure_ascii=False, indent=2)}\n```\n"
            
            # Agregar recordatorios críticos
            contexto_herramientas += "\n🚨 **RECORDATORIOS:**\n"
            contexto_herramientas += "1. Solo menciona datos que aparecen en los resultados\n"
            contexto_herramientas += "2. Si 'servicios' o 'destinos' está vacío, di 'No encontré'\n"
            contexto_herramientas += "3. Diferencia claramente SERVICIOS de DESTINOS\n"
            
            mensajes_con_resultados = [
                {"role": "system", "content": SYSTEM_PROMPT + contexto_extra},
                {"role": "user", "content": mensaje_usuario},
                {"role": "assistant", "content": "Entendido, consultaré la información."},
                {"role": "user", "content": f"{contexto_herramientas}\n\nAhora responde de forma clara, concisa y BASADA ÚNICAMENTE EN LOS DATOS ANTERIORES."}
            ]
            
            respuesta_final = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=mensajes_con_resultados,
                temperature=0.7,
                max_tokens=500
            )
            
            respuesta_texto = respuesta_final.choices[0].message.content
        else:
            respuesta_texto = mensaje_asistente.content or "Lo siento, no pude generar una respuesta."
        
        return JsonResponse({
            'success': True,
            'response': respuesta_texto,
            'debug': {
                'intencion': intencion,
                'params_detectados': params_detectados,
                'funciones_usadas': [r['nombre'] for r in resultados_herramientas] if mensaje_asistente.tool_calls else []
            } if settings.DEBUG else None
        })
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"Error en chatbot: {error_msg}")
        print(traceback.format_exc())
        
        # Registrar error
        if 'mensaje_usuario' in locals():
            ChatbotMemory.registrar_error(mensaje_usuario, error_msg)
        
        return JsonResponse({
            'success': False,
            'error': 'Ocurrió un error al procesar tu mensaje. Por favor intenta de nuevo.'
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
            'errores_recientes': [],
            'total_consultas': 0
        }
        
        # Obtener contadores de funciones
        funciones = [
            'buscar_servicios', 'buscar_destinos', 'obtener_estadisticas_servicios',
            'obtener_estadisticas_destinos', 'comparar_servicios', 'obtener_recomendaciones'
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