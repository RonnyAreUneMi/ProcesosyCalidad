/**
 * Chatbot Core - Ecuador Turismo
 * Funcionalidad principal del asistente virtual
 */

class ChatbotCore {
    constructor() {
        this.CHAT_HISTORY_KEY = 'ecuadorTurismoChatHistory';
        this.isProcessing = false;
        this.init();
    }

    init() {
        this.cargarHistorialChat();
        this.configurarLimpiezaAlCerrarSesion();
        this.mostrarBadgeInicial();
    }

    cargarHistorialChat() {
        const historial = this.obtenerHistorialChat();
        const container = document.getElementById('chatbotMessages');
        container.innerHTML = '';
        
        if (historial.length === 0) {
            this.addChatMessage(
                'Hola, soy tu asistente de Ecuador Turismo.\n\n' +
                'Puedo ayudarte con:\n' +
                '• Buscar servicios turísticos\n' +
                '• Explorar destinos\n' +
                '• Comparar opciones\n' +
                '• Obtener recomendaciones\n\n' +
                '¿Qué te gustaría saber?',
                'bot', false
            );
        } else {
            historial.forEach(msg => this.addChatMessage(msg.content, msg.role === 'user' ? 'user' : 'bot', false));
        }
    }

    obtenerHistorialChat() {
        const stored = sessionStorage.getItem(this.CHAT_HISTORY_KEY);
        return stored ? JSON.parse(stored) : [];
    }

    guardarMensajeHistorial(content, role) {
        const historial = this.obtenerHistorialChat();
        historial.push({ content, role, timestamp: Date.now() });
        if (historial.length > 30) historial.splice(0, historial.length - 30);
        sessionStorage.setItem(this.CHAT_HISTORY_KEY, JSON.stringify(historial));
    }

    toggleChatbot() {
        const chatbotWindow = document.getElementById('chatbotWindow');
        const chatbotBadge = document.getElementById('chatbotBadge');
        chatbotWindow.classList.toggle('active');
        
        if (chatbotWindow.classList.contains('active')) {
            chatbotBadge.style.display = 'none';
            document.getElementById('chatbotInput').focus();
        }
    }

    async sendChatMessage() {
        if (this.isProcessing) return;
        
        const input = document.getElementById('chatbotInput');
        const message = input.value.trim();
        if (!message) return;
        
        this.isProcessing = true;
        input.disabled = true;
        
        this.addChatMessage(message, 'user', true);
        this.guardarMensajeHistorial(message, 'user');
        input.value = '';
        
        const tipoConsulta = this.detectarTipoConsulta(message);
        const typingId = this.mostrarIndicadorEscritura(tipoConsulta);
        
        try {
            const historial = this.obtenerHistorialChat();
            const csrfToken = this.getCSRFToken();

            if (!csrfToken) {
                throw new Error('Token de seguridad no disponible');
            }

            const response = await fetch('/chatbot/message/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ message: message, history: historial })
            });
            
            this.removerIndicadorEscritura(typingId);
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            if (data.success) {
                this.addChatMessage(data.response, 'bot', true);
                this.guardarMensajeHistorial(data.response, 'assistant');
            } else {
                this.addChatMessage('Error: ' + (data.error || 'Desconocido'), 'bot', true);
            }
            
        } catch (error) {
            this.removerIndicadorEscritura(typingId);
            this.addChatMessage(`Error: ${error.message}`, 'bot', true);
        } finally {
            this.isProcessing = false;
            input.disabled = false;
            input.focus();
        }
    }

    detectarTipoConsulta(mensaje) {
        const mensajeLower = mensaje.toLowerCase();
        const patternsSaludos = ['hola', 'buenos dias', 'buenas tardes', 'quien eres', 'que eres', 'como te llamas', 'adios', 'gracias', 'que puedes hacer'];
        if (patternsSaludos.some(p => mensajeLower.includes(p))) return 'instantanea';
        const patternsConsulta = ['buscar', 'recomendar', 'quiero', 'necesito', 'precio', 'costo', 'hotel', 'tour', 'destino', 'servicio'];
        if (patternsConsulta.some(p => mensajeLower.includes(p))) return 'consulta';
        return 'general';
    }

    addChatMessage(text, sender, animate = true) {
        const container = document.getElementById('chatbotMessages');
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${sender}${animate ? ' slide-in-right' : ''}`;
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'chat-avatar';
        
        if (sender === 'bot') {
            const img = document.createElement('img');
            img.src = '/media/bot.png';
            img.alt = 'Bot';
            img.className = 'w-full h-full rounded-full object-cover';
            img.onerror = function() {
                this.style.display = 'none';
                this.parentElement.innerHTML = '<i class="fas fa-robot"></i>';
            };
            avatarDiv.appendChild(img);
        } else {
            avatarDiv.textContent = (window.chatbotUserInitial || 'U').toUpperCase();
        }
        
        const contentDiv = document.createElement('div');
        if (sender === 'bot') {
            contentDiv.className = 'chat-content';
            if (animate) {
                this.typeWriterEffect(contentDiv, text);
            } else {
                contentDiv.innerHTML = this.convertirMarkdownAHTML(text);
                this.aplicarColoresCorrectos(contentDiv);
            }
        } else {
            contentDiv.className = 'chat-bubble';
            contentDiv.innerHTML = this.convertirMarkdownAHTML(text);
        }
        
        msgDiv.appendChild(avatarDiv);
        msgDiv.appendChild(contentDiv);
        container.appendChild(msgDiv);
        container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    }

    typeWriterEffect(element, text) {
        const cleanText = this.convertirMarkdownAHTML(text);
        
        element.className = 'typewriter-text';
        element.innerHTML = '';
        
        // Mostrar directamente con formato HTML
        element.innerHTML = cleanText;
        
        // Simular cursor parpadeante por un momento
        setTimeout(() => {
            element.className = 'typewriter-text complete';
            this.aplicarColoresCorrectos(element);
            
            const container = document.getElementById('chatbotMessages');
            container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
        }, 300);
    }

    aplicarColoresCorrectos(element) {
        const isDark = document.documentElement.classList.contains('dark');
        const color = isDark ? '#d1d5db' : '#374151';
        
        element.style.color = color;
        
        const allElements = element.querySelectorAll('*');
        allElements.forEach(el => {
            if (!el.style.color || el.style.color === 'inherit') {
                el.style.color = color;
            }
        });
    }

    convertirMarkdownAHTML(text) {
        let html = text.replace(/\n/g, '<br>');
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        
        // Resaltar frases específicas
        html = html.replace(/(ver detalles|más información|consultar|reservar|disponible)/gi, '<span class="highlight">$1</span>');
        
        html = html.replace(/• /g, '<span class="text-blue-600 dark:text-blue-400">•</span> ');
        return html;
    }

    mostrarIndicadorEscritura(tipoConsulta) {
        const container = document.getElementById('chatbotMessages');
        const typingDiv = document.createElement('div');
        typingDiv.className = 'chat-message bot slide-in-right';
        typingDiv.id = 'typing-indicator-' + Date.now();
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'chat-avatar';
        const img = document.createElement('img');
        img.src = '/media/bot.png';
        img.alt = 'Bot';
        img.className = 'w-full h-full rounded-full object-cover';
        img.onerror = function() {
            this.style.display = 'none';
            this.parentElement.innerHTML = '<i class="fas fa-robot"></i>';
        };
        avatarDiv.appendChild(img);
        
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'chat-loading';
        
        if (tipoConsulta === 'instantanea') {
            loadingDiv.innerHTML = this.crearIndicadorCarga('Procesando...');
        } else if (tipoConsulta === 'consulta') {
            loadingDiv.innerHTML = this.crearIndicadorCarga('Consultando base de datos...');
            setTimeout(() => {
                if (typingDiv.parentElement) {
                    loadingDiv.innerHTML = this.crearIndicadorCarga('Analizando resultados...');
                }
            }, 2000);
        } else {
            loadingDiv.innerHTML = this.crearIndicadorCarga('Analizando tu consulta...');
            setTimeout(() => {
                if (typingDiv.parentElement) {
                    loadingDiv.innerHTML = this.crearIndicadorCarga('Buscando información...');
                }
            }, 2000);
        }
        
        typingDiv.appendChild(avatarDiv);
        typingDiv.appendChild(loadingDiv);
        container.appendChild(typingDiv);
        container.scrollTop = container.scrollHeight;
        
        return typingDiv.id;
    }

    crearIndicadorCarga(texto) {
        return `
            <div class="flex items-center space-x-3">
                <div class="flex space-x-1">
                    <div class="w-2 h-2 bg-blue-500 dark:bg-blue-400 rounded-full animate-bounce"></div>
                    <div class="w-2 h-2 bg-blue-500 dark:bg-blue-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
                    <div class="w-2 h-2 bg-blue-500 dark:bg-blue-400 rounded-full animate-bounce" style="animation-delay: 0.4s"></div>
                </div>
                <span class="loading-indicator">${texto}</span>
            </div>
        `;
    }

    removerIndicadorEscritura(id) {
        const indicator = document.getElementById(id);
        if (indicator) indicator.remove();
    }

    handleChatKeyPress(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendChatMessage();
        }
    }

    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    getCSRFToken() {
        if (window.CSRF_TOKEN) {
            return window.CSRF_TOKEN;
        }

        let token = this.getCookie('csrftoken');
        if (token) {
            return token;
        }

        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            token = metaTag.getAttribute('content');
            if (token) return token;
        }

        const inputTag = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (inputTag && inputTag.value) {
            return inputTag.value;
        }

        console.error('CSRF token no encontrado');
        return null;
    }

    configurarLimpiezaAlCerrarSesion() {
        if (window.isAuthenticated) {
            document.querySelectorAll('a[href*="logout"]').forEach(link => {
                link.addEventListener('click', () => {
                    sessionStorage.removeItem(this.CHAT_HISTORY_KEY);
                    const csrfToken = this.getCSRFToken();
                    if (csrfToken) {
                        fetch('/chatbot/limpiar/', {
                            method: 'POST',
                            headers: { 'X-CSRFToken': csrfToken }
                        }).catch(err => console.log('Limpieza fallida'));
                    }
                });
            });
        }
    }

    mostrarBadgeInicial() {
        setTimeout(() => {
            const chatbotWindow = document.getElementById('chatbotWindow');
            const chatbotBadge = document.getElementById('chatbotBadge');
            if (!chatbotWindow.classList.contains('active')) chatbotBadge.style.display = 'flex';
        }, 15000);
    }
}

// Instancia global del chatbot
let chatbot;

// Funciones globales para compatibilidad
function toggleChatbot() {
    chatbot.toggleChatbot();
}

function sendChatMessage() {
    chatbot.sendChatMessage();
}

function handleChatKeyPress(event) {
    chatbot.handleChatKeyPress(event);
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    chatbot = new ChatbotCore();
});