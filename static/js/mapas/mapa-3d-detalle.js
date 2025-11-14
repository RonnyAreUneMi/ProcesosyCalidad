/**
 * Funcionalidades avanzadas para el mapa 3D de detalle de servicios
 * Mejora la experiencia de usuario con controles personalizados y animaciones
 */

class Mapa3DDetalle {
    constructor() {
        this.mapa = null;
        this.marcador = null;
        this.is3D = true;
        this.coordenadas = null;
        this.animacionActiva = false;
    }

    /**
     * Inicializa las funcionalidades avanzadas del mapa
     */
    init(mapa, coordenadas) {
        this.mapa = mapa;
        this.coordenadas = coordenadas;
        this.setupEventListeners();
        this.setupKeyboardControls();
        this.setupTouchGestures();
    }

    /**
     * Configura los event listeners para los controles
     */
    setupEventListeners() {
        // Animación de rotación automática
        this.setupAutoRotation();
        
        // Controles de zoom mejorados
        this.setupZoomControls();
        
        // Información de coordenadas en tiempo real
        this.setupCoordinateDisplay();
    }

    /**
     * Configura la rotación automática del mapa
     */
    setupAutoRotation() {
        let rotationActive = false;
        let rotationInterval;

        // Crear botón de rotación automática
        const rotateBtn = document.createElement('button');
        rotateBtn.id = 'autoRotate';
        rotateBtn.className = 'bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 p-2 rounded-lg shadow-md border border-gray-200 dark:border-gray-600 transition-all';
        rotateBtn.innerHTML = '<i class="fas fa-sync-alt text-sm"></i>';
        rotateBtn.title = 'Rotación automática';

        // Insertar en el contenedor de controles
        const controlsContainer = document.querySelector('#mapContainer .absolute.top-4.right-4');
        if (controlsContainer) {
            controlsContainer.appendChild(rotateBtn);
        } else {
            // Fallback: crear contenedor si no existe
            const mapContainer = document.getElementById('mapContainer');
            if (mapContainer) {
                const newContainer = document.createElement('div');
                newContainer.className = 'absolute top-4 right-4 z-10 flex flex-col gap-2';
                newContainer.appendChild(rotateBtn);
                mapContainer.appendChild(newContainer);
            }
        }

        rotateBtn.addEventListener('click', () => {
            if (!rotationActive) {
                this.startAutoRotation();
                rotateBtn.innerHTML = '<i class="fas fa-pause text-sm"></i>';
                rotateBtn.title = 'Pausar rotación';
                rotationActive = true;
            } else {
                this.stopAutoRotation();
                rotateBtn.innerHTML = '<i class="fas fa-sync-alt text-sm"></i>';
                rotateBtn.title = 'Rotación automática';
                rotationActive = false;
            }
        });
    }

    /**
     * Inicia la rotación automática
     */
    startAutoRotation() {
        if (this.animacionActiva) return;
        
        this.animacionActiva = true;
        const rotateCamera = (timestamp) => {
            if (!this.animacionActiva) return;
            
            this.mapa.rotateTo((this.mapa.getBearing() + 0.5) % 360, { duration: 0 });
            requestAnimationFrame(rotateCamera);
        };
        
        requestAnimationFrame(rotateCamera);
    }

    /**
     * Detiene la rotación automática
     */
    stopAutoRotation() {
        this.animacionActiva = false;
    }

    /**
     * Configura controles de zoom mejorados
     */
    setupZoomControls() {
        // Crear controles de zoom personalizados
        const zoomContainer = document.createElement('div');
        zoomContainer.className = 'absolute bottom-4 right-4 z-10 flex flex-col gap-1';
        
        const zoomIn = document.createElement('button');
        zoomIn.className = 'bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 p-2 rounded-t-lg shadow-md border border-gray-200 dark:border-gray-600 transition-all';
        zoomIn.innerHTML = '<i class="fas fa-plus text-sm"></i>';
        zoomIn.title = 'Acercar';
        
        const zoomOut = document.createElement('button');
        zoomOut.className = 'bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 p-2 rounded-b-lg shadow-md border border-gray-200 dark:border-gray-600 border-t-0 transition-all';
        zoomOut.innerHTML = '<i class="fas fa-minus text-sm"></i>';
        zoomOut.title = 'Alejar';
        
        zoomContainer.appendChild(zoomIn);
        zoomContainer.appendChild(zoomOut);
        
        const mapContainer = document.getElementById('mapContainer');
        if (mapContainer) {
            mapContainer.appendChild(zoomContainer);
        }

        // Event listeners para zoom
        zoomIn.addEventListener('click', () => {
            this.mapa.zoomTo(this.mapa.getZoom() + 1, { duration: 500 });
        });

        zoomOut.addEventListener('click', () => {
            this.mapa.zoomTo(this.mapa.getZoom() - 1, { duration: 500 });
        });
    }

    /**
     * Configura controles de teclado
     */
    setupKeyboardControls() {
        document.addEventListener('keydown', (e) => {
            if (!this.mapa) return;
            
            const mapContainer = document.getElementById('mapContainer');
            if (!mapContainer || !mapContainer.contains(document.activeElement)) return;

            switch(e.key) {
                case 'r':
                case 'R':
                    e.preventDefault();
                    this.resetView();
                    break;
                case '3':
                    e.preventDefault();
                    this.toggle3DView();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    this.mapa.setBearing(this.mapa.getBearing() - 10);
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    this.mapa.setBearing(this.mapa.getBearing() + 10);
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    this.mapa.setPitch(Math.min(this.mapa.getPitch() + 10, 60));
                    break;
                case 'ArrowDown':
                    e.preventDefault();
                    this.mapa.setPitch(Math.max(this.mapa.getPitch() - 10, 0));
                    break;
            }
        });
    }

    /**
     * Configura gestos táctiles mejorados
     */
    setupTouchGestures() {
        const mapElement = document.getElementById('map');
        if (!mapElement) return;

        let touchStartTime = 0;
        let touchCount = 0;

        mapElement.addEventListener('touchstart', (e) => {
            touchStartTime = Date.now();
            touchCount = e.touches.length;
        });

        mapElement.addEventListener('touchend', (e) => {
            const touchDuration = Date.now() - touchStartTime;
            
            // Doble tap para centrar
            if (touchCount === 1 && touchDuration < 300) {
                setTimeout(() => {
                    if (touchCount === 1) {
                        this.resetView();
                    }
                }, 300);
            }
        });
    }

    /**
     * Configura display de coordenadas en tiempo real
     */
    setupCoordinateDisplay() {
        // Crear display de coordenadas
        const coordDisplay = document.createElement('div');
        coordDisplay.id = 'coordDisplay';
        coordDisplay.className = 'absolute bottom-4 left-4 z-10 bg-white dark:bg-gray-800 rounded-lg shadow-md border border-gray-200 dark:border-gray-600 px-3 py-2 text-xs font-mono text-gray-700 dark:text-gray-300';
        coordDisplay.style.display = 'none';
        
        const mapContainer = document.getElementById('mapContainer');
        if (mapContainer) {
            mapContainer.appendChild(coordDisplay);
        }

        // Mostrar coordenadas al mover el mouse
        this.mapa.on('mousemove', (e) => {
            const { lng, lat } = e.lngLat;
            coordDisplay.innerHTML = `
                <div class="flex space-x-4">
                    <span>Lat: ${lat.toFixed(6)}</span>
                    <span>Lng: ${lng.toFixed(6)}</span>
                </div>
            `;
            coordDisplay.style.display = 'block';
        });

        this.mapa.on('mouseleave', () => {
            coordDisplay.style.display = 'none';
        });
    }

    /**
     * Resetea la vista del mapa
     */
    resetView() {
        if (!this.coordenadas) return;
        
        this.mapa.flyTo({
            center: [this.coordenadas.lng, this.coordenadas.lat],
            zoom: 15,
            pitch: 60,
            bearing: -17.6,
            duration: 2000
        });
    }

    /**
     * Alterna entre vista 2D y 3D
     */
    toggle3DView() {
        const toggle3D = document.getElementById('toggle3D');
        if (!toggle3D) return;

        if (this.is3D) {
            this.mapa.easeTo({
                pitch: 0,
                bearing: 0,
                duration: 1000
            });
            toggle3D.innerHTML = '<i class="fas fa-mountain text-sm"></i>';
            toggle3D.title = 'Vista 3D';
        } else {
            this.mapa.easeTo({
                pitch: 60,
                bearing: -17.6,
                duration: 1000
            });
            toggle3D.innerHTML = '<i class="fas fa-cube text-sm"></i>';
            toggle3D.title = 'Vista 2D';
        }
        this.is3D = !this.is3D;
    }

    /**
     * Añade efectos de clima (experimental)
     */
    addWeatherEffects() {
        // Efecto de lluvia (simplificado)
        this.mapa.addLayer({
            'id': 'rain-effect',
            'type': 'raster',
            'source': {
                'type': 'raster',
                'tiles': ['https://tile.openweathermap.org/map/precipitation_new/{z}/{x}/{y}.png?appid=YOUR_API_KEY'],
                'tileSize': 256
            },
            'paint': {
                'raster-opacity': 0.3
            }
        });
    }

    /**
     * Limpia recursos al destruir la instancia
     */
    destroy() {
        this.stopAutoRotation();
        this.mapa = null;
        this.marcador = null;
        this.coordenadas = null;
    }
}

// Instancia global
window.mapa3DDetalle = new Mapa3DDetalle();

// Auto-inicialización cuando el mapa esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Esperar a que el mapa se inicialice
    const checkMapReady = setInterval(() => {
        if (typeof window.mapaDetalle !== 'undefined' && window.mapaDetalle && window.mapaDetalle.loaded()) {
            const dataElement = document.querySelector('[data-lat][data-lng]');
            if (dataElement) {
                const lat = parseFloat(dataElement.dataset.lat || '0');
                const lng = parseFloat(dataElement.dataset.lng || '0');
                
                if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
                    window.mapa3DDetalle.init(window.mapaDetalle, { lat, lng });
                    clearInterval(checkMapReady);
                    console.log('✅ Mapa 3D avanzado inicializado correctamente');
                }
            }
        }
    }, 200);
    
    // Timeout de seguridad
    setTimeout(() => {
        clearInterval(checkMapReady);
        console.log('⚠️ Timeout alcanzado para inicialización del mapa 3D avanzado');
    }, 8000);
});