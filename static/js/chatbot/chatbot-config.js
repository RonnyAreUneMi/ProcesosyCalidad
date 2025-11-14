/**
 * Chatbot Config - Ecuador Turismo
 * Configuración y constantes del chatbot
 */

const ChatbotConfig = {
    // Configuración de la API
    API_ENDPOINTS: {
        MESSAGE: '/chatbot/message/',
        CLEANUP: '/chatbot/limpiar/'
    },

    // Configuración del historial
    HISTORY: {
        MAX_MESSAGES: 30,
        STORAGE_KEY: 'ecuadorTurismoChatHistory'
    },

    // Configuración de UI
    UI: {
        TYPING_DELAY: 2000,
        BADGE_SHOW_DELAY: 15000,
        MESSAGE_HIDE_DELAY: 5000
    },

    // Patrones de detección de consultas
    QUERY_PATTERNS: {
        INSTANT: ['hola', 'buenos dias', 'buenas tardes', 'quien eres', 'que eres', 'como te llamas', 'adios', 'gracias', 'que puedes hacer'],
        SEARCH: ['buscar', 'recomendar', 'quiero', 'necesito', 'precio', 'costo', 'hotel', 'tour', 'destino', 'servicio']
    },

    // Mensajes del sistema
    MESSAGES: {
        WELCOME: `Hola, soy tu asistente de Ecuador Turismo.

Puedo ayudarte con:
• Buscar servicios turísticos
• Explorar destinos
• Comparar opciones
• Obtener recomendaciones

¿Qué te gustaría saber?`,
        
        ERROR_CSRF: 'Token de seguridad no disponible',
        ERROR_NETWORK: 'Error de conexión. Intenta nuevamente.',
        ERROR_UNKNOWN: 'Error desconocido'
    },

    // Configuración de indicadores de carga
    LOADING_INDICATORS: {
        INSTANT: 'Procesando...',
        SEARCH: 'Consultando base de datos...',
        SEARCH_ANALYZING: 'Analizando resultados...',
        GENERAL: 'Analizando tu consulta...',
        GENERAL_SEARCHING: 'Buscando información...'
    }
};

// Exportar configuración para uso global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChatbotConfig;
} else {
    window.ChatbotConfig = ChatbotConfig;
}