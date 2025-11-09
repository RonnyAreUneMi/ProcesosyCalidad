# apps/chatbot/views.py - VERSIÓN PROFESIONAL OPTIMIZADA
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.test import RequestFactory
import json
import hashlib
import re
from datetime import datetime
from unicodedata import normalize


# ============================================
# UTILIDADES DE TEXTO
# ============================================

class TextProcessor:
    """Procesador inteligente de texto con normalización avanzada"""
    
    STOPWORDS = {
        'hotel', 'restaurante', 'tour', 'el', 'la', 'los', 'las', 'de', 'del', 
        'en', 'un', 'una', 'para', 'por', 'con', 'sin'
    }
    
    CORRECCIONES_COMUNES = {
        'kito': 'quito',
        'guayakil': 'guayaquil',
        'cuenka': 'cuenca',
        'galapagos': 'galápagos',
        'guayakil': 'guayaquil',
        'resturante': 'restaurante',
        'hospedage': 'hospedaje',
        'hoteles': 'hotel',
        'restaurantes': 'restaurante'
    }
    
    @classmethod
    def normalizar(cls, texto):
        """Normalización completa: corrección ortográfica, minúsculas, stopwords"""
        if not texto:
            return ""
        
        # Minúsculas
        texto = texto.lower().strip()
        
        # Remover acentos
        texto = normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
        
        # Remover caracteres especiales excepto espacios y guiones
        texto = re.sub(r'[^\w\s-]', '', texto)
        
        # Normalizar espacios
        texto = re.sub(r'\s+', ' ', texto)
        
        # Aplicar correcciones ortográficas
        palabras = texto.split()
        palabras_corregidas = [cls.CORRECCIONES_COMUNES.get(p, p) for p in palabras]
        
        return ' '.join(palabras_corregidas)
    
    @classmethod
    def extraer_keywords(cls, texto):
        """Extrae palabras clave eliminando stopwords"""
        texto_norm = cls.normalizar(texto)
        palabras = texto_norm.split()
        
        # Filtrar stopwords
        keywords = [p for p in palabras if p not in cls.STOPWORDS and len(p) > 2]
        
        return ' '.join(keywords) if keywords else texto_norm
    
    @classmethod
    def detectar_region(cls, texto):
        """Detecta región mencionada en el texto"""
        texto_norm = cls.normalizar(texto)
        
        regiones = {
            'costa': ['costa', 'guayaquil', 'manta', 'esmeraldas', 'salinas', 'playas'],
            'sierra': ['sierra', 'quito', 'cuenca', 'riobamba', 'ambato', 'loja', 'andes'],
            'oriente': ['oriente', 'amazonia', 'tena', 'puyo', 'macas', 'coca', 'selva'],
            'galapagos': ['galapagos', 'isabela', 'santa cruz', 'san cristobal']
        }
        
        for region, keywords in regiones.items():
            if any(kw in texto_norm for kw in keywords):
                return region
        
        return None
    
    @classmethod
    def detectar_tipo_servicio(cls, texto):
        """Detecta tipo de servicio mencionado"""
        texto_norm = cls.normalizar(texto)
        
        tipos = {
            'alojamiento': ['hotel', 'hospedaje', 'hostal', 'resort', 'lodge', 'cabaña', 'dormir'],
            'gastronomia': ['restaurante', 'comida', 'comer', 'gastronomia', 'cocina'],
            'tour': ['tour', 'excursion', 'visita', 'recorrido', 'paseo'],
            'actividad': ['actividad', 'aventura', 'deporte', 'diving', 'buceo', 'rafting'],
            'transporte': ['transporte', 'bus', 'taxi', 'transfer', 'traslado']
        }
        
        for tipo, keywords in tipos.items():
            if any(kw in texto_norm for kw in keywords):
                return tipo
        
        return None


# ============================================
# SISTEMA DE CONTEXTO Y MEMORIA
# ============================================

class ContextManager:
    """Gestiona el contexto de la conversación"""
    
    @staticmethod
    def construir_contexto(mensaje, historial):
        """Construye contexto inteligente desde el historial"""
        contexto = {
            'mensaje_actual': mensaje,
            'ultima_busqueda': None,
            'tema_conversacion': None,
            'region_mencionada': TextProcessor.detectar_region(mensaje),
            'tipo_servicio': TextProcessor.detectar_tipo_servicio(mensaje)
        }
        
        # Analizar últimos 3 mensajes para contexto
        for msg in historial[-3:]:
            if msg.get('role') == 'user':
                content = msg.get('content', '')
                
                # Detectar contexto previo
                if not contexto['region_mencionada']:
                    contexto['region_mencionada'] = TextProcessor.detectar_region(content)
                
                if not contexto['tipo_servicio']:
                    contexto['tipo_servicio'] = TextProcessor.detectar_tipo_servicio(content)
        
        return contexto
    
    @staticmethod
    def registrar_interaccion(mensaje, funcion, resultado, exitoso):
        """Registra interacciones para aprendizaje"""
        cache_key = f"chatbot_interaction_{timezone.now().strftime('%Y%m%d')}"
        
        interacciones = cache.get(cache_key, [])
        interacciones.append({
            'timestamp': timezone.now().isoformat(),
            'mensaje': mensaje[:100],  # Primeros 100 chars
            'funcion': funcion,
            'exitoso': exitoso,
            'tuvo_resultados': bool(resultado.get('servicios') or resultado.get('destinos'))
        })
        
        # Mantener últimas 100 interacciones
        cache.set(cache_key, interacciones[-100:], timeout=86400 * 7)


# ============================================
# CLIENTE OPENAI
# ============================================

def get_openai_client():
    """Inicializa cliente OpenAI/Groq con validación"""
    from openai import OpenAI

    # Intentar usar Groq primero (es gratis)
    groq_key = getattr(settings, 'GROQ_API_KEY', None)
    if groq_key:
        return OpenAI(
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1"
        )

    # Si no hay Groq, usar OpenAI
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("Ni GROQ_API_KEY ni OPENAI_API_KEY están configuradas")

    return OpenAI(api_key=api_key)


# ============================================
# DEFINICIÓN DE TOOLS (FUNCIONES)
# ============================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_servicios",
            "description": """Busca servicios turísticos (hoteles, tours, restaurantes) usando PALABRAS CLAVE.
            
            IMPORTANTE: 
            - Usa solo palabras distintivas, NO nombres completos
            - Elimina palabras genéricas (hotel, restaurante, tour)
            - Ejemplos: 'Hilton Colon Quito' → q='hilton colon', 'Oro Verde' → q='oro verde'
            - La búsqueda es flexible y encuentra coincidencias parciales""",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "Palabras clave distintivas (NO nombre completo). Ejemplos: 'hilton', 'oro verde', 'casa cangrejo'"
                    },
                    "tipo": {
                        "type": "string",
                        "enum": ["alojamiento", "tour", "actividad", "transporte", "gastronomia"],
                        "description": "Tipo de servicio específico"
                    },
                    "region": {
                        "type": "string",
                        "enum": ["costa", "sierra", "oriente", "galapagos"],
                        "description": "Región geográfica (minúsculas, sin artículos)"
                    },
                    "precio_max": {
                        "type": "number",
                        "description": "Precio máximo en USD"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_destinos",
            "description": """Busca destinos turísticos (ciudades, provincias, lugares) usando palabras clave.
            
            CRÍTICO: Usa solo para LUGARES QUE SE VISITAN, no para servicios/negocios.
            Ejemplos: 'Quito', 'Galápagos', 'Baños de Agua Santa'""",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "Nombre del destino (ciudad, provincia, atractivo). Normaliza errores: 'Kito'→'quito'"
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
            "description": "Obtiene los mejores destinos de una región completa",
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
            "name": "obtener_recomendaciones",
            "description": "Genera recomendaciones personalizadas según preferencias del usuario",
            "parameters": {
                "type": "object",
                "properties": {
                    "presupuesto": {"type": "number", "description": "Presupuesto en USD"},
                    "tipo": {
                        "type": "string",
                        "enum": ["alojamiento", "tour", "actividad", "transporte", "gastronomia"]
                    },
                    "region": {
                        "type": "string",
                        "enum": ["costa", "sierra", "oriente", "galapagos"]
                    },
                    "personas": {"type": "integer", "description": "Número de personas"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "comparar_servicios",
            "description": "Compara múltiples servicios por precio, calificación y características",
            "parameters": {
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "string",
                        "description": "IDs de servicios separados por comas (ej: '1,2,3')"
                    }
                },
                "required": ["ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_estadisticas_servicios",
            "description": "Estadísticas generales: total servicios, por tipo, por región, precios promedio",
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
    }
]


# ============================================
# SYSTEM PROMPT PROFESIONAL
# ============================================

SYSTEM_PROMPT = """Eres **Guía Ecuador** 🇪🇨, el asistente turístico inteligente especializado en Ecuador.

## 🎯 MISIÓN PRINCIPAL
Ayudar a turistas con información **REAL y VERIFICADA** exclusivamente de tu base de datos. NUNCA inventes información.

## 🧠 CAPACIDADES INTELIGENTES

### 1️⃣ ANÁLISIS Y CORRECCIÓN AUTOMÁTICA
- Corriges errores ortográficos automáticamente: "kito"→"quito", "guayakil"→"guayaquil"
- Normalizas consultas: "hoteles en la costa" → buscar servicios tipo=alojamiento, region=costa
- Extraes contexto: "quiero algo económico cerca de la playa" → presupuesto bajo + region=costa

### 2️⃣ BÚSQUEDA INTELIGENTE CON PALABRAS CLAVE
**REGLA DE ORO**: Usa SOLO palabras distintivas, NO nombres completos

✅ CORRECTO:
- Usuario: "Hotel Hilton Colon Quito" → buscar_servicios(q="hilton colon", tipo="alojamiento")
- Usuario: "Oro Verde Guayaquil" → buscar_servicios(q="oro verde", region="costa")
- Usuario: "tour galápagos" → buscar_servicios(q="galapagos", tipo="tour")

❌ INCORRECTO:
- q="Hotel Hilton Colon Quito" (muy específico)
- q="hotel oro verde" (incluye palabra genérica "hotel")

### 3️⃣ ESTRATEGIA DE BÚSQUEDA INCREMENTAL
Si no encuentras resultados:
1. **Primer intento**: Palabras clave + filtros → buscar_servicios(q="hilton colon", tipo="alojamiento")
2. **Segundo intento**: Menos palabras → buscar_servicios(q="hilton")
3. **Tercer intento**: Sin filtros → buscar_servicios(q="hilton")
4. Si aún no hay resultados → Informa honestamente y sugiere alternativas

### 4️⃣ DIFERENCIACIÓN CRÍTICA
🏨 **SERVICIOS** (usar buscar_servicios):
- Negocios que se RESERVAN: hoteles, tours, restaurantes, transporte
- Tienen precios, calificaciones, se pueden reservar
- Ejemplos: "Hilton Colon", "Tour Galápagos", "Restaurante El Coral"

🏞️ **DESTINOS** (usar buscar_destinos):
- Lugares que se VISITAN: ciudades, provincias, atractivos naturales
- NO se reservan, solo se visitan
- Ejemplos: "Quito", "Cuenca", "Parque Cotopaxi", "Baños de Agua Santa"

### 5️⃣ MANEJO DE URLs
- **SERVICIOS**: Usa `/servicios/<id>/` (ej: `/servicios/42/`)
- **DESTINOS**: Usa `/destinos/<slug>/` donde slug es el nombre normalizado
  - Ejemplos: `/destinos/quito/`, `/destinos/galapagos/`, `/destinos/banos-de-agua-santa/`
- NUNCA inventes URLs, usa SOLO las que devuelven las funciones

### 6️⃣ PERSONALIDAD Y TONO
- **Cálido y profesional**, pero NO robótico
- **Conversacional**: Responde saludos naturalmente ("¡Hola! 👋 ¿En qué puedo ayudarte?")
- **Conciso**: Máximo 200 palabras por respuesta
- **Emojis moderados**: 2-4 por mensaje, solo cuando sea apropiado
- **Proactivo**: Siempre termina con pregunta o sugerencia relevante

### 7️⃣ CUÁNDO NO LLAMAR FUNCIONES
**NO llames funciones si el usuario:**
- Solo saluda: "hola", "buenos días", "hey"
- Hace preguntas generales: "¿qué puedes hacer?", "¿cómo funciona?"
- Agradece: "gracias", "perfecto", "ok"
- Responde con confirmación: "sí", "no", "tal vez"
- **Pregunta por recetas o cómo preparar**: "cómo hacer chaulafan", "receta de ceviche", "ingredientes del encebollado"
- **Pregunta fuera de turismo**: "clima", "historia", "política", "economía"
- **Pregunta solo por un plato sin contexto de restaurante**: "chaulafan", "ceviche", "encebollado" (sin mencionar "restaurante" o "dónde comer")

**SÍ llama funciones si el usuario:**
- Busca restaurantes específicamente: "restaurantes en Quito", "dónde comer en Guayaquil"
- Busca hoteles/tours: "hoteles en Quito", "tours Galápagos"
- Pregunta por un lugar: "qué visitar en Cuenca"
- Busca restaurante que sirva un plato: "restaurante de chaulafan", "dónde comer ceviche"

### 8️⃣ LÍMITES DE TU CONOCIMIENTO
**SOLO ayudas con servicios turísticos:**
- ✅ Hoteles, hostales, alojamiento
- ✅ Tours, actividades, excursiones
- ✅ Restaurantes (el lugar, NO recetas ni menús específicos)
- ✅ Transporte turístico
- ✅ Destinos turísticos

**IMPORTANTE SOBRE RESTAURANTES:**
- ✅ Puedes recomendar restaurantes por ubicación
- ❌ NO tienes información de menús o platos específicos
- ❌ NO puedes filtrar por plato ("restaurante de ceviche")
- ✅ Si preguntan por un plato, pregunta en qué ciudad y recomienda restaurantes de esa ciudad

**NO ayudas con:**
- ❌ Recetas de comida
- ❌ Cómo preparar platos
- ❌ Ingredientes o técnicas culinarias
- ❌ Menús específicos de restaurantes
- ❌ Información no turística (clima, historia detallada, política)
- ❌ Temas fuera de turismo

**Si te preguntan algo fuera de tu alcance, responde:**
"Lo siento, solo puedo ayudarte con servicios turísticos en Ecuador 🇪🇨 (hoteles, tours, restaurantes, destinos). Para [tema solicitado], te recomiendo consultar otras fuentes especializadas. ¿Puedo ayudarte con algo relacionado al turismo en Ecuador? 🗺️"

## 🚫 PROHIBICIONES ABSOLUTAS
1. ❌ Inventar datos, precios, lugares o servicios que no están en los resultados
2. ❌ Mencionar servicios/destinos que no aparecen en las respuestas de funciones
3. ❌ Usar nombres completos en parámetro 'q' (solo keywords)
4. ❌ Ignorar errores ortográficos (SIEMPRE normaliza primero)
5. ❌ Responder sin consultar funciones cuando se necesita información específica
6. ❌ Crear URLs inventadas (usa solo las del sistema)
7. ❌ Ser excesivamente formal en saludos ("estimado usuario")
8. ❌ Llamar funciones para saludos simples o preguntas generales
9. ❌ Responder preguntas sobre recetas, ingredientes o cómo preparar comida
10. ❌ Dar información detallada sobre temas no turísticos (clima, historia, política)
11. ❌ Gastar tokens en preguntas fuera de tu alcance (rechaza educadamente)

## ✅ FLUJO DE TRABAJO CORRECTO
1. **Recibir mensaje** (puede tener errores, ser informal)
2. **Analizar contexto**: ¿Busca servicio o destino? ¿Qué región? ¿Qué tipo?
3. **Normalizar**: Corregir ortografía, extraer keywords
4. **Llamar función** con parámetros optimizados
5. **Si no hay resultados**: Intentar con menos filtros o variaciones
6. **Responder**: Basándose SOLO en datos reales, tono natural
7. **Cerrar**: Pregunta de seguimiento o sugerencia relevante

## 📋 EJEMPLOS DE INTERACCIONES CORRECTAS

### Ejemplo 1: Saludo (SIN llamar funciones)
Usuario: "hola"
Tú: NO llames ninguna función, solo responde:
"¡Hola! 👋 Soy tu Guía Ecuador. ¿Qué te gustaría explorar hoy? Puedo ayudarte con hoteles, tours, restaurantes o destinos turísticos 🗺️"

### Ejemplo 2: Búsqueda con errores
Usuario: "hoteles en kito baratos"
Tú piensas: "Corregir 'kito'→'quito', tipo=alojamiento, region=sierra, presupuesto bajo"
Tú llamas: buscar_servicios(q="quito", tipo="alojamiento", precio_max=80, region="sierra")
Tú respondes: "¡Encontré opciones económicas en Quito! 🏨..."

### Ejemplo 3: Búsqueda de servicio específico
Usuario: "necesito el hotel oro verde"
Tú piensas: "Quiere hotel específico, extraer keywords: 'oro verde'"
Tú llamas: buscar_servicios(q="oro verde", tipo="alojamiento")
BD retorna: Oro Verde Manta ($120), Oro Verde Guayaquil ($150)
Tú respondes: "¡Perfecto! Tengo 2 ubicaciones del Oro Verde 🏨:
1. **Oro Verde Manta** - $120/noche ⭐4.5 [Ver más](/servicios/23/)
2. **Oro Verde Guayaquil** - $150/noche ⭐4.8 [Ver más](/servicios/45/)
¿Cuál ubicación te interesa más?"

### Ejemplo 4: Búsqueda sin resultados
Usuario: "hotel atlantis"
Tú llamas: buscar_servicios(q="atlantis", tipo="alojamiento")
BD retorna: []
Tú respondes: "No encontré un hotel con ese nombre en mi base de datos 😔 
¿Quizás buscas algo similar? Tengo excelentes opciones de hoteles en [región]. ¿Me dices en qué zona te gustaría hospedarte?"

### Ejemplo 5: Destino turístico
Usuario: "qué visitar en cuenca"
Tú piensas: "Busca destino, no servicio"
Tú llamas: buscar_destinos(q="cuenca")
BD retorna: Cuenca (slug: cuenca)
Tú respondes: "¡Cuenca es hermosa! 🏛️ Es Patrimonio de la Humanidad con arquitectura colonial impresionante.
[Descubre Cuenca](/destinos/cuenca/)
¿Te gustaría que te recomiende tours o dónde hospedarte en Cuenca?"

### Ejemplo 6: Pregunta sobre receta (NO llamar funciones)
Usuario: "cómo hacer chaulafan"
Tú: NO llames funciones, responde directamente:
"Lo siento, solo puedo ayudarte con servicios turísticos en Ecuador 🇪🇨 (hoteles, tours, restaurantes, destinos). Para recetas de comida, te recomiendo consultar sitios especializados en gastronomía. ¿Puedo ayudarte a encontrar restaurantes donde sirvan chaulafan? 🍴"

### Ejemplo 7: Pregunta solo por plato (NO llamar funciones)
Usuario: "chaulafan"
Tú: NO llames funciones, responde directamente:
"¿Te refieres a buscar restaurantes que sirvan chaulafan? 🍴 Si es así, dime en qué ciudad te gustaría comer y te ayudo a encontrar opciones. O si buscas otra cosa relacionada al turismo en Ecuador, con gusto te ayudo 🗺️"

### Ejemplo 8: Pregunta sobre restaurante (SÍ llamar funciones)
Usuario: "restaurantes en Quito"
Tú piensas: "Busca servicios de restaurantes"
Tú llamas: buscar_servicios(q="quito", tipo="restaurante")
Tú respondes: Con los resultados de restaurantes disponibles

### Ejemplo 9: Buscar restaurante con plato específico (SÍ llamar funciones)
Usuario: "dónde comer ceviche en Guayaquil"
Tú piensas: "Busca restaurantes en Guayaquil"
Tú llamas: buscar_servicios(q="guayaquil", tipo="restaurante")
Tú respondes: Con restaurantes en Guayaquil (NO filtres por "ceviche" porque no tienes menús)

## 🎓 REGLAS DE CALIDAD ISO
- Código limpio y mantenible
- Sin hardcodear datos (usa solo funciones)
- Manejo robusto de errores
- Logging apropiado para debugging
- Validación de parámetros
- Caché inteligente
- Respuestas consistentes

## 💡 RECORDATORIOS FINALES
- Siempre normaliza ANTES de buscar
- Extrae keywords, elimina palabras genéricas
- Si no hay resultados, intenta variaciones
- Usa SOLO datos de funciones
- Tono natural, no robótico
- URLs correctas según tipo (servicio vs destino)
- Termina con pregunta/sugerencia relevante

¡Estás listo para ser el mejor asistente turístico de Ecuador! 🇪🇨"""


# ============================================
# EJECUTOR DE FUNCIONES
# ============================================

def ejecutar_funcion(nombre_funcion, parametros, request=None):
    """Ejecuta funciones AJAX con validación robusta"""
    
    # Importaciones locales
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
    
    # Limpiar parámetros (remover None, strings vacíos, ceros)
    parametros_limpios = {
        k: v for k, v in parametros.items()
        if v is not None and v != "" and str(v).strip() != ""
    }
    
    factory = RequestFactory()
    
    try:
        # ========================================
        # SERVICIOS
        # ========================================
        if nombre_funcion == "buscar_servicios":
            # Normalizar query si existe
            if 'q' in parametros_limpios:
                parametros_limpios['q'] = TextProcessor.extraer_keywords(parametros_limpios['q'])
            
            req = factory.get('/ajax/buscar-servicios/', parametros_limpios)
            req.user = request.user if request else None
            response = buscar_servicios_ajax(req)
            data = json.loads(response.content)
            
            # Agregar URLs correctas a servicios
            if data.get('success') and data.get('servicios'):
                for servicio in data['servicios']:
                    servicio['url'] = f"/servicios/{servicio['id']}/"
            
            return data
        
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
            req.user = request.user if request else None
            response = recomendaciones_ajax(req)
            data = json.loads(response.content)
            
            # Agregar URLs
            if data.get('success') and data.get('recomendaciones'):
                for rec in data['recomendaciones']:
                    rec['url'] = f"/servicios/{rec['id']}/"
            
            return data
        
        # ========================================
        # DESTINOS
        # ========================================
        elif nombre_funcion == "buscar_destinos":
            # Normalizar query
            if 'q' in parametros_limpios:
                parametros_limpios['q'] = TextProcessor.normalizar(parametros_limpios['q'])
            
            req = factory.get('/destinos/ajax/busqueda/', parametros_limpios)
            response = busqueda_ajax(req)
            data = json.loads(response.content)
            
            # Agregar URLs correctas con slug
            if data.get('success') and data.get('destinos'):
                for destino in data['destinos']:
                    # Generar slug desde el nombre
                    slug = re.sub(r'[^\w\s-]', '', destino.get('nombre', '')).strip().lower()
                    slug = re.sub(r'[-\s]+', '-', slug)
                    destino['url'] = f"/destinos/{slug}/"
            
            return data
        
        elif nombre_funcion == "obtener_destinos_por_region":
            region = parametros_limpios.get('region', '')
            if not region:
                return {"error": "Región requerida", "success": False}
            
            req = factory.get(f'/destinos/ajax/region/{region}/')
            response = destinos_por_region_ajax(req, region)
            data = json.loads(response.content)
            
            # Agregar URLs
            if data.get('success') and data.get('destinos'):
                for destino in data['destinos']:
                    slug = re.sub(r'[^\w\s-]', '', destino.get('nombre', '')).strip().lower()
                    slug = re.sub(r'[-\s]+', '-', slug)
                    destino['url'] = f"/destinos/{slug}/"
            
            return data
        
        elif nombre_funcion == "obtener_estadisticas_destinos":
            req = factory.get('/destinos/ajax/estadisticas/')
            response = estadisticas_destinos_ajax(req)
            return json.loads(response.content)
        
        # Función no encontrada
        return {
            "error": f"Función '{nombre_funcion}' no existe",
            "success": False
        }
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        
        print(f"❌ Error ejecutando {nombre_funcion}: {str(e)}")
        print(error_trace)
        
        return {
            "error": f"Error interno: {str(e)}",
            "success": False,
            "traceback": error_trace[:300] if settings.DEBUG else None
        }


# ============================================
# ENDPOINT PRINCIPAL
# ============================================

@require_http_methods(["POST"])
def chatbot_message(request):
    """
    Endpoint principal del chatbot con GPT-4
    
    Maneja:
    - Normalización inteligente de consultas
    - Contexto conversacional
    - Múltiples llamadas a funciones
    - Respuestas basadas SOLO en datos reales
    """
    
    try:
        # Parsear request
        data = json.loads(request.body)
        mensaje_usuario = data.get('message', '').strip()
        historial = data.get('history', [])
        
        if not mensaje_usuario:
            return JsonResponse({
                'success': False,
                'error': 'El mensaje está vacío'
            }, status=400)
        
        # Construir contexto inteligente
        contexto = ContextManager.construir_contexto(mensaje_usuario, historial)
        
        # ========================================
        # CONSTRUIR MENSAJES PARA GPT-4
        # ========================================
        mensajes = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Incluir historial reciente (últimos 8 mensajes)
        for msg in historial[-8:]:
            if msg.get('role') in ['user', 'assistant']:
                mensajes.append({
                    "role": msg['role'],
                    "content": msg.get('content', '')
                })
        
        # Agregar mensaje actual con contexto
        mensajes.append({
            "role": "user",
            "content": mensaje_usuario
        })
        
        # ========================================
        # PRIMERA LLAMADA: GPT-4 DECIDE FUNCIONES
        # ========================================
        client = get_openai_client()
        
        # Determinar modelo según el cliente
        modelo = "llama-3.3-70b-versatile" if hasattr(settings, 'GROQ_API_KEY') and settings.GROQ_API_KEY else "gpt-4-turbo-preview"

        respuesta_inicial = client.chat.completions.create(
            model=modelo,
            messages=mensajes,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.6,  # Balance creatividad/precisión
            max_tokens=800
        )
        
        mensaje_asistente = respuesta_inicial.choices[0].message
        
        # ========================================
        # EJECUTAR FUNCIONES SI ES NECESARIO
        # ========================================
        if mensaje_asistente.tool_calls:
            resultados_funciones = []
            
            for tool_call in mensaje_asistente.tool_calls:
                nombre_funcion = tool_call.function.name
                
                # Parsear argumentos
                try:
                    argumentos = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as e:
                    print(f"⚠️ Error parseando argumentos de {nombre_funcion}: {e}")
                    argumentos = {}
                
                # Ejecutar función
                print(f"🔧 Ejecutando: {nombre_funcion}({argumentos})")
                resultado = ejecutar_funcion(nombre_funcion, argumentos, request)
                
                exitoso = resultado.get('success', False)
                
                # Registrar interacción
                ContextManager.registrar_interaccion(
                    mensaje_usuario,
                    nombre_funcion,
                    resultado,
                    exitoso
                )
                
                if not exitoso:
                    print(f"⚠️ {nombre_funcion} retornó error: {resultado.get('error')}")
                
                resultados_funciones.append({
                    "tool_call_id": tool_call.id,
                    "nombre": nombre_funcion,
                    "argumentos": argumentos,
                    "resultado": resultado,
                    "exitoso": exitoso
                })
            
            # ========================================
            # SEGUNDA LLAMADA: GENERAR RESPUESTA FINAL
            # ========================================
            
            # Construir mensajes con resultados
            mensajes_con_resultados = mensajes + [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": mensaje_asistente.tool_calls
                }
            ]
            
            # Agregar resultado de cada función
            for res in resultados_funciones:
                mensajes_con_resultados.append({
                    "role": "tool",
                    "tool_call_id": res["tool_call_id"],
                    "name": res["nombre"],
                    "content": json.dumps(res["resultado"], ensure_ascii=False)
                })
            
            # Instrucciones finales para respuesta
            instrucciones_finales = """
RESULTADOS OBTENIDOS. Ahora genera tu respuesta final:

🎯 REGLAS CRÍTICAS:
1. **SOLO usa datos de los resultados anteriores** - NUNCA inventes
2. Si 'servicios' o 'destinos' está vacío → di claramente "No encontré..."
3. **Máximo 200 palabras** - sé conciso y directo
4. **URLs correctas**:
   - Servicios: /servicios/{id}/
   - Destinos: /destinos/{slug}/ (usa el slug del resultado)
5. Termina con pregunta/sugerencia relevante
6. Tono natural y conversacional (no robótico)

📋 FORMATO DE RESPUESTA:
- Lista servicios/destinos con detalles relevantes (precio, calificación)
- Usa emojis moderadamente (2-4 máximo)
- Incluye enlaces clickeables si hay resultados
- Si múltiples opciones, menciona las TOP 3

✅ EJEMPLO CORRECTO:
Si encontraste 2 hoteles "Oro Verde":
"¡Encontré 2 opciones del Oro Verde! 🏨

1. **Oro Verde Manta** - $120/noche ⭐4.5
   [Ver detalles](/servicios/23/)

2. **Oro Verde Guayaquil** - $150/noche ⭐4.8
   [Ver detalles](/servicios/45/)

¿Cuál ubicación prefieres? También puedo sugerirte tours en esa zona 🗺️"

❌ EJEMPLO INCORRECTO:
"Encontré el Hotel Oro Verde. Es muy bueno y está en varios lugares."
(Falta especificidad, enlaces, precios)

🚫 NUNCA:
- Menciones servicios/destinos que no están en los resultados
- Inventes precios, calificaciones o datos
- Uses URLs incorrectas o inventadas
- Seas excesivamente formal ("estimado usuario")

Genera ahora tu respuesta basándote SOLO en los datos reales."""
            
            mensajes_con_resultados.append({
                "role": "user",
                "content": instrucciones_finales
            })
            
            # Generar respuesta final
            respuesta_final = client.chat.completions.create(
                model=modelo,
                messages=mensajes_con_resultados,
                temperature=0.7,
                max_tokens=600
            )
            
            respuesta_texto = respuesta_final.choices[0].message.content
            
            # Debug info
            debug_info = {
                'funciones_ejecutadas': [r['nombre'] for r in resultados_funciones],
                'argumentos_usados': [r['argumentos'] for r in resultados_funciones],
                'exitosos': sum(1 for r in resultados_funciones if r['exitoso']),
                'fallidos': sum(1 for r in resultados_funciones if not r['exitoso']),
                'contexto': contexto
            }
        else:
            # No se necesitaron funciones (ej: saludos, preguntas generales)
            respuesta_texto = mensaje_asistente.content or "Lo siento, no pude generar una respuesta."
            debug_info = {
                'funciones_ejecutadas': [],
                'tipo': 'respuesta_directa',
                'mensaje': 'No se requirieron llamadas a funciones'
            }
        
        return JsonResponse({
            'success': True,
            'response': respuesta_texto,
            'debug': debug_info if settings.DEBUG else None
        })
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        
        print(f"❌ ERROR EN CHATBOT: {error_msg}")
        print(error_trace)
        
        # Respuesta amigable al usuario
        return JsonResponse({
            'success': False,
            'error': 'Lo siento, ocurrió un error al procesar tu mensaje. Por favor intenta de nuevo en unos momentos.',
            'debug': {
                'error': error_msg,
                'trace': error_trace[:500]
            } if settings.DEBUG else None
        }, status=500)


# ============================================
# ENDPOINTS ADICIONALES
# ============================================

@require_http_methods(["POST"])
def limpiar_historial(request):
    """Limpia el historial del chat"""
    return JsonResponse({
        'success': True,
        'message': 'Historial limpiado correctamente'
    })


@require_http_methods(["GET"])
def estadisticas_chatbot(request):
    """
    Obtiene estadísticas de uso del chatbot
    Solo accesible para administradores
    """
    
    # Validar permisos
    if not request.user.is_authenticated:
        return JsonResponse({
            'error': 'Debes iniciar sesión'
        }, status=401)
    
    if request.user.rol.nombre != 'administrador':
        return JsonResponse({
            'error': 'No tienes permisos para ver estas estadísticas'
        }, status=403)
    
    try:
        # Obtener interacciones del día actual
        hoy = timezone.now().strftime('%Y%m%d')
        interacciones_hoy = cache.get(f"chatbot_interaction_{hoy}", [])
        
        # Contadores por función
        funciones_count = {}
        funciones_exitosas = {}
        
        for interaccion in interacciones_hoy:
            funcion = interaccion.get('funcion')
            exitoso = interaccion.get('exitoso', False)
            
            funciones_count[funcion] = funciones_count.get(funcion, 0) + 1
            
            if exitoso:
                funciones_exitosas[funcion] = funciones_exitosas.get(funcion, 0) + 1
        
        # Calcular tasas de éxito
        tasas_exito = {
            func: round((funciones_exitosas.get(func, 0) / count) * 100, 1)
            for func, count in funciones_count.items()
        }
        
        estadisticas = {
            'total_interacciones_hoy': len(interacciones_hoy),
            'funciones_mas_usadas': dict(sorted(
                funciones_count.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),
            'tasas_exito': tasas_exito,
            'ultimas_consultas': [
                {
                    'timestamp': i.get('timestamp'),
                    'mensaje': i.get('mensaje'),
                    'funcion': i.get('funcion'),
                    'exitoso': i.get('exitoso')
                }
                for i in interacciones_hoy[-20:]  # Últimas 20
            ]
        }
        
        return JsonResponse({
            'success': True,
            'estadisticas': estadisticas
        })
        
    except Exception as e:
        import traceback
        print(f"❌ Error obteniendo estadísticas: {str(e)}")
        print(traceback.format_exc())
        
        return JsonResponse({
            'success': False,
            'error': 'Error al obtener estadísticas'
        }, status=500)


@require_http_methods(["POST"])
def test_normalizacion(request):
    """
    Endpoint de testing para probar normalización de texto
    Solo en DEBUG mode
    """
    
    if not settings.DEBUG:
        return JsonResponse({
            'error': 'Endpoint solo disponible en modo DEBUG'
        }, status=403)
    
    try:
        data = json.loads(request.body)
        texto = data.get('texto', '')
        
        resultado = {
            'original': texto,
            'normalizado': TextProcessor.normalizar(texto),
            'keywords': TextProcessor.extraer_keywords(texto),
            'region_detectada': TextProcessor.detectar_region(texto),
            'tipo_servicio_detectado': TextProcessor.detectar_tipo_servicio(texto)
        }
        
        return JsonResponse({
            'success': True,
            'resultado': resultado
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================
# VALIDACIÓN DE CONFIGURACIÓN
# ============================================

def validar_configuracion():
    """
    Valida que todo esté configurado correctamente
    Llamar al inicio de la aplicación
    """
    
    errores = []
    
    # Validar API Key de OpenAI
    if not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
        errores.append("OPENAI_API_KEY no configurada en settings.py")
    
    # Validar que las apps necesarias estén instaladas
    required_apps = ['apps.servicios', 'apps.destinos', 'apps.chatbot']
    for app in required_apps:
        if app not in settings.INSTALLED_APPS:
            errores.append(f"App '{app}' no está en INSTALLED_APPS")
    
    # Validar caché
    if not hasattr(settings, 'CACHES'):
        errores.append("CACHES no configurado en settings.py")
    
    if errores:
        print("⚠️ ERRORES DE CONFIGURACIÓN DEL CHATBOT:")
        for error in errores:
            print(f"  - {error}")
        return False
    
    print("✅ Configuración del chatbot validada correctamente")
    return True


# ============================================
# UTILIDADES DE MANTENIMIENTO
# ============================================

def limpiar_cache_antiguo():
    """
    Limpia interacciones antiguas del caché
    Ejecutar periódicamente (ej: tarea cron diaria)
    """
    
    from datetime import timedelta
    
    # Limpiar interacciones de más de 7 días
    fecha_limite = timezone.now() - timedelta(days=7)
    
    claves_eliminadas = 0
    
    for dia in range(8):  # Últimos 8 días
        fecha = (timezone.now() - timedelta(days=dia)).strftime('%Y%m%d')
        cache_key = f"chatbot_interaction_{fecha}"
        
        if cache.get(cache_key):
            if dia > 7:  # Más de 7 días
                cache.delete(cache_key)
                claves_eliminadas += 1
    
    print(f"🧹 Limpieza de caché: {claves_eliminadas} claves eliminadas")
    
    return claves_eliminadas