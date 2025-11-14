/**
 * Chatbot Utils - Ecuador Turismo
 * Utilidades y funciones auxiliares para el chatbot
 */

class ChatbotUtils {
    static actualizarContadorCarrito() {
        fetch('/reservas/carrito/')
            .then(res => res.text())
            .then(html => {
                const match = html.match(/Tienes (\d+) servicio/);
                if (match && match[1]) {
                    const cantidad = parseInt(match[1]);
                    const badge = document.getElementById('carritoCount');
                    if (badge) {
                        badge.textContent = cantidad;
                        badge.style.display = cantidad > 0 ? 'flex' : 'none';
                    }
                }
            })
            .catch(err => console.log('Carrito no disponible'));
    }

    static mostrarLoader() {
        const loader = document.getElementById('loaderOverlay');
        if (loader) {
            loader.classList.add('active');
        }
    }

    static ocultarLoader() {
        const loader = document.getElementById('loaderOverlay');
        if (loader) {
            loader.classList.remove('active');
        }
    }

    static toggleDarkMode() {
        const html = document.documentElement;
        const isDark = html.classList.contains('dark');
        if (isDark) {
            html.classList.remove('dark');
            localStorage.setItem('theme', 'light');
        } else {
            html.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        }
    }

    static toggleMobileMenu() {
        const mobileMenu = document.getElementById('mobileMenu');
        if (mobileMenu) {
            mobileMenu.classList.toggle('hidden');
        }
    }

    static initTheme() {
        const theme = localStorage.getItem('theme') || 'light';
        if (theme === 'dark') {
            document.documentElement.classList.add('dark');
        }
    }

    static initAOS() {
        if (typeof AOS !== 'undefined') {
            AOS.init({ 
                duration: 600, 
                once: true, 
                offset: 80, 
                easing: 'ease-out' 
            });
        }
    }

    static setupSmoothScrolling() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({ 
                        behavior: 'smooth', 
                        block: 'start' 
                    });
                }
            });
        });
    }

    static hideMessages() {
        setTimeout(() => {
            document.querySelectorAll('[class*="message-"]').forEach(msg => {
                msg.style.transition = 'opacity 0.4s ease';
                msg.style.opacity = '0';
                setTimeout(() => msg.remove(), 400);
            });
        }, 5000);
    }
}

// Funciones globales para compatibilidad
function toggleDarkMode() {
    ChatbotUtils.toggleDarkMode();
}

function toggleMobileMenu() {
    ChatbotUtils.toggleMobileMenu();
}

function mostrarLoader() {
    ChatbotUtils.mostrarLoader();
}

function ocultarLoader() {
    ChatbotUtils.ocultarLoader();
}

function actualizarContadorCarrito() {
    ChatbotUtils.actualizarContadorCarrito();
}

// Inicialización automática
document.addEventListener('DOMContentLoaded', function() {
    ChatbotUtils.initTheme();
    ChatbotUtils.initAOS();
    ChatbotUtils.setupSmoothScrolling();
    ChatbotUtils.hideMessages();
    ChatbotUtils.actualizarContadorCarrito();
});

// Event listeners globales
window.addEventListener('beforeunload', function() { 
    ChatbotUtils.mostrarLoader(); 
});

window.addEventListener('load', function() {
    setTimeout(ChatbotUtils.ocultarLoader, 300);
});

window.addEventListener('pageshow', function(event) {
    if (event.persisted) {
        ChatbotUtils.ocultarLoader();
    }
});

// Auto-hide loader después de 10 segundos
setTimeout(function() {
    const loader = document.getElementById('loaderOverlay');
    if (loader && loader.classList.contains('active')) {
        ChatbotUtils.ocultarLoader();
    }
}, 10000);

// Actualizar contador de carrito cada 30 segundos
setInterval(ChatbotUtils.actualizarContadorCarrito, 30000);