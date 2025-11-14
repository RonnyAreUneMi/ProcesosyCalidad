/**
 * 🗺️ EcuadorMapbox - Sistema de mapas reutilizable con Mapbox GL JS
 * Configurado específicamente para Ecuador con funcionalidades 3D
 */

class EcuadorMapbox {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.map = null;
        this.markers = [];
        this.is3D = false;
        
        // Configuración por defecto para Ecuador
        this.config = {
            accessToken: 'pk.eyJ1IjoiaW5ncG9sbGl0byIsImEiOiJjbWh4cmVwcHYwNDF2MnJvcGc5N3VocDliIn0.FDbD09-VTzE7H-HAfee0yg',
            style: options.style || 'mapbox://styles/mapbox/outdoors-v12',
            center: options.center || [-78.1834, -1.8312], // Centro de Ecuador
            zoom: options.zoom || 6,
            pitch: options.pitch || 0,
            bearing: options.bearing || 0,
            enable3D: options.enable3D !== false,
            ...options
        };

        // Colores por región
        this.regionColors = {
            costa: '#0ea5e9',
            sierra: '#10b981', 
            oriente: '#f59e0b',
            galapagos: '#ef4444'
        };
    }

    async init() {
        if (!window.mapboxgl) {
            throw new Error('Mapbox GL JS no está cargado');
        }

        mapboxgl.accessToken = this.config.accessToken;

        this.map = new mapboxgl.Map({
            container: this.containerId,
            style: this.config.style,
            center: this.config.center,
            zoom: this.config.zoom,
            pitch: this.config.pitch,
            bearing: this.config.bearing
        });

        // Agregar controles básicos
        this.map.addControl(new mapboxgl.NavigationControl());
        this.map.addControl(new mapboxgl.FullscreenControl());

        // Configurar terreno 3D si está habilitado
        if (this.config.enable3D) {
            this.map.on('style.load', () => {
                this.map.addSource('mapbox-dem', {
                    'type': 'raster-dem',
                    'url': 'mapbox://mapbox.mapbox-terrain-dem-v1',
                    'tileSize': 512,
                    'maxzoom': 14
                });
                this.map.setTerrain({ 'source': 'mapbox-dem', 'exaggeration': 1.5 });
            });
        }

        return new Promise((resolve) => {
            this.map.on('load', () => resolve(this.map));
        });
    }

    // Agregar marcador con popup
    addMarker(lng, lat, options = {}) {
        const color = options.color || this.regionColors[options.region] || this.regionColors.costa;
        
        const marker = new mapboxgl.Marker({ color })
            .setLngLat([lng, lat])
            .addTo(this.map);

        if (options.popup) {
            const popup = new mapboxgl.Popup({ offset: 25 })
                .setHTML(options.popup);
            marker.setPopup(popup);
        }

        this.markers.push(marker);
        return marker;
    }

    // Crear marcadores desde datos de destinos
    createMarkersFromData(destinosData, regionFilter = 'todos') {
        this.clearMarkers();
        
        const destinosFiltrados = regionFilter === 'todos' 
            ? destinosData 
            : destinosData.filter(d => d.region === regionFilter);

        const bounds = new mapboxgl.LngLatBounds();

        destinosFiltrados.forEach(destino => {
            const lat = parseFloat(destino.latitud);
            const lng = parseFloat(destino.longitud);
            if (isNaN(lat) || isNaN(lng)) return;

            const isDark = document.documentElement.classList.contains('dark');
            const color = this.regionColors[destino.region] || this.regionColors.costa;
            
            const popupContent = `
            <div style="padding: 16px; background-color: ${isDark ? '#1e293b' : '#ffffff'}; min-width: 280px;">
                <div style="margin-bottom: 12px;">
                    <img src="${destino.get_imagen_principal || '/static/images/destinos/destino_defecto.jpg'}"
                         alt="${destino.nombre}"
                         style="width: 100%; height: 160px; object-fit: cover; border-radius: 8px;"/>
                </div>
                <h4 style="font-weight: 600; font-size: 18px; margin-bottom: 8px; color: ${isDark ? '#f1f5f9' : '#0f172a'};">
                    ${destino.nombre}
                </h4>
                <p style="font-size: 13px; color: ${isDark ? '#94a3b8' : '#64748b'}; margin-bottom: 10px; line-height: 1.5;">
                    ${destino.descripcion_corta || 'Sin descripción'}
                </p>
                <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 12px;">
                    <span style="color: #f59e0b; font-size: 14px;">
                        ${'★'.repeat(Math.round(destino.calificacion_promedio || 0))}${'☆'.repeat(5 - Math.round(destino.calificacion_promedio || 0))}
                    </span>
                    <span style="font-size: 12px; color: ${isDark ? '#94a3b8' : '#64748b'};">
                        ${(destino.calificacion_promedio || 0).toFixed(1)}
                    </span>
                </div>
                <a href="/destinos/${destino.slug}/"
                   style="display: block; background: ${color}; color: white;
                          padding: 10px; text-align: center; text-decoration: none;
                          font-size: 13px; font-weight: 500; border-radius: 6px;">
                    Ver detalles
                </a>
            </div>
            `;

            this.addMarker(lng, lat, {
                region: destino.region,
                popup: popupContent
            });

            bounds.extend([lng, lat]);
        });

        if (!bounds.isEmpty()) {
            this.map.fitBounds(bounds, { padding: 50, maxZoom: 10 });
        }

        return destinosFiltrados.length;
    }

    // Alternar vista 3D
    toggle3D() {
        if (this.is3D) {
            this.map.easeTo({
                pitch: 0,
                bearing: 0,
                duration: 1000
            });
            this.is3D = false;
        } else {
            this.map.easeTo({
                pitch: 60,
                bearing: -17.6,
                duration: 1000
            });
            this.is3D = true;
        }
        return this.is3D;
    }

    // Volar a Ecuador (centrar)
    flyToEcuador() {
        this.map.flyTo({
            center: this.config.center,
            zoom: this.config.zoom,
            pitch: this.is3D ? 60 : 0,
            bearing: this.is3D ? -17.6 : 0,
            duration: 2000
        });
    }

    // Volar a ubicación específica
    flyTo(lng, lat, zoom = 14) {
        this.map.flyTo({
            center: [lng, lat],
            zoom: zoom,
            pitch: this.is3D ? 60 : 0,
            bearing: this.is3D ? -17.6 : 0,
            duration: 1500
        });
    }

    // Limpiar marcadores
    clearMarkers() {
        this.markers.forEach(marker => marker.remove());
        this.markers = [];
    }

    // Redimensionar mapa
    resize() {
        if (this.map) {
            this.map.resize();
        }
    }

    // Destruir mapa
    destroy() {
        if (this.map) {
            this.map.remove();
            this.map = null;
        }
        this.markers = [];
    }
}

// Exportar para uso global
window.EcuadorMapbox = EcuadorMapbox;