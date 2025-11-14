/**
 * Utilidades comunes para el proyecto
 */
window.Utils = {
    // Normalizar texto para comparaciones
    normalizar: function(nombre) {
        return nombre
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/[^a-z0-9]/g, '_')
            .replace(/_+/g, '_')
            .replace(/^_|_$/g, '');
    },

    // Convertir coordenadas con comas a puntos
    parseCoordinate: function(coord) {
        return parseFloat(String(coord).replace(',', '.'));
    },

    // Calcular distancia entre dos puntos
    calcularDistancia: function(lat1, lng1, lat2, lng2) {
        const R = 6371;
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLng = (lng2 - lng1) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLng/2) * Math.sin(dLng/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    },

    // Mostrar notificaciones
    mostrarNotificacion: function(mensaje, tipo = 'info') {
        const colores = {
            'success': 'bg-green-500',
            'info': 'bg-blue-500',
            'warning': 'bg-yellow-500',
            'error': 'bg-red-500'
        };
        
        const notificacion = document.createElement('div');
        notificacion.className = `fixed top-20 right-4 ${colores[tipo]} text-white px-6 py-3 rounded-lg shadow-lg z-50`;
        notificacion.innerHTML = `
            <div class="flex items-center space-x-2">
                <i class="fas fa-info-circle"></i>
                <span>${mensaje}</span>
            </div>
        `;
        
        document.body.appendChild(notificacion);
        
        setTimeout(() => {
            notificacion.style.opacity = '0';
            notificacion.style.transition = 'opacity 0.3s';
            setTimeout(() => {
                if (notificacion.parentNode) {
                    document.body.removeChild(notificacion);
                }
            }, 300);
        }, 3000);
    }
};