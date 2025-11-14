/**
 * 🎮 Controles UI para mapas de Ecuador
 * Botones y controles reutilizables para la interfaz de mapas
 */

class MapControls {
    constructor(mapInstance, options = {}) {
        this.map = mapInstance;
        this.options = {
            showRegionFilters: options.showRegionFilters !== false,
            show3DControls: options.show3DControls !== false,
            showCounter: options.showCounter !== false,
            ...options
        };
        this.currentRegion = 'todos';
        this.destinosData = [];
    }

    // Crear panel de controles completo
    createControlPanel(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = `
            <div class="bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-xl shadow-lg border border-slate-200/80 dark:border-gray-700/80 p-4 transition-all">
                <div class="flex flex-wrap items-center justify-between gap-3">
                    ${this.options.showRegionFilters ? this.createRegionFilters() : ''}
                    <div class="flex items-center gap-3">
                        ${this.options.show3DControls ? this.create3DControls() : ''}
                        ${this.options.showCounter ? this.createCounter() : ''}
                    </div>
                </div>
            </div>
        `;

        this.attachEventListeners();
    }

    // Crear filtros de región
    createRegionFilters() {
        return `
            <div class="flex flex-wrap items-center gap-3">
                <button onclick="mapControls.filterByRegion('todos')"
                        class="region-filter-btn active flex items-center px-5 py-2.5 rounded-lg font-medium text-sm transition-all bg-blue-500 text-white hover:bg-blue-600"
                        data-region="todos">
                    <i class="fas fa-globe-americas mr-2"></i>
                    Todos
                </button>
                <button onclick="mapControls.filterByRegion('costa')"
                        class="region-filter-btn flex items-center px-5 py-2.5 rounded-lg font-medium text-sm transition-all bg-cyan-50 dark:bg-gray-700 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-100 dark:hover:bg-gray-600 border border-cyan-200 dark:border-cyan-500/30"
                        data-region="costa">
                    <i class="fas fa-umbrella-beach mr-2"></i>
                    Costa
                </button>
                <button onclick="mapControls.filterByRegion('sierra')"
                        class="region-filter-btn flex items-center px-5 py-2.5 rounded-lg font-medium text-sm transition-all bg-emerald-50 dark:bg-gray-700 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-gray-600 border border-emerald-200 dark:border-emerald-500/30"
                        data-region="sierra">
                    <i class="fas fa-mountain mr-2"></i>
                    Sierra
                </button>
                <button onclick="mapControls.filterByRegion('oriente')"
                        class="region-filter-btn flex items-center px-5 py-2.5 rounded-lg font-medium text-sm transition-all bg-green-50 dark:bg-gray-700 text-green-600 dark:text-green-400 hover:bg-green-100 dark:hover:bg-gray-600 border border-green-200 dark:border-green-500/30"
                        data-region="oriente">
                    <i class="fas fa-tree mr-2"></i>
                    Oriente
                </button>
                <button onclick="mapControls.filterByRegion('galapagos')"
                        class="region-filter-btn flex items-center px-5 py-2.5 rounded-lg font-medium text-sm transition-all bg-amber-50 dark:bg-gray-700 text-amber-600 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-gray-600 border border-amber-200 dark:border-amber-500/30"
                        data-region="galapagos">
                    <i class="fas fa-fish mr-2"></i>
                    Galápagos
                </button>
            </div>
        `;
    }

    // Crear controles 3D
    create3DControls() {
        return `
            <button id="toggle3D" onclick="mapControls.toggle3D()"
                    class="flex items-center px-4 py-2.5 rounded-lg font-medium text-sm transition-all bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600 shadow-lg">
                <i class="fas fa-cube mr-2"></i>
                <span id="toggle3DText">Vista 3D</span>
            </button>
            
            <button id="flyToEcuador" onclick="mapControls.flyToEcuador()"
                    class="flex items-center px-4 py-2.5 rounded-lg font-medium text-sm transition-all bg-gradient-to-r from-green-500 to-teal-500 text-white hover:from-green-600 hover:to-teal-600 shadow-lg">
                <i class="fas fa-home mr-2"></i>
                Centrar
            </button>
        `;
    }

    // Crear contador de destinos
    createCounter() {
        return `
            <div class="flex items-center gap-2 px-4 py-2.5 bg-white dark:bg-gray-700 rounded-lg border border-slate-200 dark:border-gray-600 transition-colors">
                <i class="fas fa-map-marker-alt text-blue-500 dark:text-blue-400"></i>
                <span class="text-sm font-medium text-slate-700 dark:text-gray-300">
                    <span id="destinosCount" class="text-blue-600 dark:text-blue-400">0</span> destinos
                </span>
            </div>
        `;
    }

    // Filtrar por región
    filterByRegion(region) {
        this.currentRegion = region;
        
        // Actualizar botones
        document.querySelectorAll('.region-filter-btn').forEach(btn => {
            btn.classList.remove('active', 'bg-blue-500', 'text-white');
            btn.classList.add('bg-gray-50', 'dark:bg-gray-700', 'text-gray-600', 'dark:text-gray-400');
        });
        
        const activeBtn = document.querySelector(`[data-region="${region}"]`);
        if (activeBtn) {
            activeBtn.classList.remove('bg-gray-50', 'dark:bg-gray-700', 'text-gray-600', 'dark:text-gray-400');
            activeBtn.classList.add('active', 'bg-blue-500', 'text-white');
        }

        // Actualizar marcadores
        const count = this.map.createMarkersFromData(this.destinosData, region);
        this.updateCounter(count);
    }

    // Alternar vista 3D
    toggle3D() {
        const is3D = this.map.toggle3D();
        const button = document.getElementById('toggle3D');
        const text = document.getElementById('toggle3DText');
        
        if (is3D) {
            text.textContent = 'Vista 2D';
            button.innerHTML = '<i class="fas fa-map mr-2"></i><span>Vista 2D</span>';
        } else {
            text.textContent = 'Vista 3D';
            button.innerHTML = '<i class="fas fa-cube mr-2"></i><span>Vista 3D</span>';
        }
    }

    // Centrar en Ecuador
    flyToEcuador() {
        this.map.flyToEcuador();
    }

    // Actualizar contador
    updateCounter(count) {
        const counter = document.getElementById('destinosCount');
        if (counter) {
            counter.textContent = count;
        }
    }

    // Cargar datos de destinos
    loadDestinos(destinosData) {
        this.destinosData = destinosData;
        const count = this.map.createMarkersFromData(destinosData, this.currentRegion);
        this.updateCounter(count);
    }

    // Adjuntar event listeners
    attachEventListeners() {
        // Los event listeners se manejan via onclick en el HTML generado
        // para mayor simplicidad y compatibilidad
    }
}

// CSS para los controles
const controlsCSS = `
<style>
.region-filter-btn {
    transform: translateY(0);
    transition: all 0.3s ease;
}

.region-filter-btn:hover {
    transform: translateY(-1px);
}

#toggle3D, #flyToEcuador {
    transform: translateY(0);
    transition: all 0.3s ease;
}

#toggle3D:hover, #flyToEcuador:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2);
}

#toggle3D:active, #flyToEcuador:active {
    transform: translateY(0);
}
</style>
`;

// Inyectar CSS
document.head.insertAdjacentHTML('beforeend', controlsCSS);

// Exportar para uso global
window.MapControls = MapControls;