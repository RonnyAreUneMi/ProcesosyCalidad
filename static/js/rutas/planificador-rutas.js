// ============================================
// VARIABLES GLOBALES MAPBOX 3D
// ============================================
let map, userMarker, routingControl;
let selectedDestino = null;
let rutasDisponibles = [];
let rutaSeleccionada = null;
let userLocation = null;
let markers = {};
let pointById = {};
let transferMarkers = [];
let destinoMarker = null;
let customRouteLines = [];

// Usar configuración global
if (window.MapboxConfig) {
    mapboxgl.accessToken = window.MapboxConfig.accessToken;
}

// Mapa de puntos de transporte por ID
let allPoints = [...transporteData.terminales_terrestres, ...transporteData.aeropuertos, ...transporteData.puertos_maritimos];
allPoints.forEach(p => {
    pointById[p.id] = p.nombre;
});

// ============================================
// FUNCIONES AUXILIARES (mantener originales)
// ============================================
function obtenerPrecioParaDestino(destinoCiudad, services) {
    if (!services || services.length === 0) {
        return null;
    }
    
    var destinoNormalizado = normalizar(destinoCiudad);
    
    let matching = services.filter(s => {
        let destName = s.destino__nombre || '';
        let destCiudad = s.destino__ciudad || '';
        
        let destNameNorm = normalizar(destName);
        let destCiudadNorm = normalizar(destCiudad);
        
        if (destinoNormalizado === 'galapagos') {
            let isGalapagos = destNameNorm.includes('cristobal') || 
                             destNameNorm.includes('santa_cruz') || 
                             destNameNorm.includes('isabela') ||
                             destNameNorm.includes('san_cristobal') ||
                             destCiudadNorm.includes('baquerizo') ||
                             destCiudadNorm.includes('puerto_ayora') ||
                             destCiudadNorm.includes('moreno');
            
            if (isGalapagos) {
                return true;
            }
        }
        
        let match = destNameNorm === destinoNormalizado || 
                   destCiudadNorm === destinoNormalizado ||
                   destNameNorm.includes(destinoNormalizado) ||
                   destinoNormalizado.includes(destNameNorm) ||
                   destCiudadNorm.includes(destinoNormalizado) ||
                   destinoNormalizado.includes(destCiudadNorm);
        
        return match;
    });
    
    if (matching.length === 0) return null;
    
    let minService = matching.reduce((prev, current) => 
        parseFloat(prev.precio) < parseFloat(current.precio) ? prev : current
    );
    
    let result = {
        precio: parseFloat(minService.precio),
        nombre: minService.nombre
    };
    return result;
}

function actualizarPreciosConDB(rutas) {
    if (!transporteServices || transporteServices.length === 0) {
        return rutas;
    }
    
    let updatedRutas = rutas.map(ruta => {
        let tramos = ruta.tramos.map(tramo => {
            if (['terrestre', 'aereo', 'maritimo'].includes(tramo.medio_transporte)) {
                let priceInfo = obtenerPrecioParaDestino(tramo.hasta, transporteServices);
                if (priceInfo) {
                    let oldCosto = tramo.costo_aprox;
                    tramo.costo_aprox = priceInfo.precio;
                    tramo.nombre_servicio = priceInfo.nombre;
                    tramo.precio_disponible = true;
                } else {
                    tramo.precio_disponible = false;
                }
            } else {
                if (typeof tramo.precio_disponible === 'undefined') {
                    tramo.precio_disponible = true;
                }
            }
            return tramo;
        });
        
        let costoTotal = tramos.reduce((sum, t) => sum + parseFloat(t.costo_aprox || 0), 0);
        
        return {
            ...ruta,
            tramos: tramos,
            costo_total: costoTotal
        };
    });
    
    return updatedRutas;
}

// ============================================
// INICIALIZACIÓN DEL MAPA MAPBOX 3D
// ============================================
function initMap() {
    map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/outdoors-v12',
        center: [-78.1834, -1.8312],
        zoom: 6,
        pitch: 45, // Vista 3D por defecto
        bearing: 0
    });

    // Agregar controles
    map.addControl(new mapboxgl.NavigationControl());
    map.addControl(new mapboxgl.FullscreenControl());
    
    // Control de geolocalización
    const geolocate = new mapboxgl.GeolocateControl({
        positionOptions: {
            enableHighAccuracy: true
        },
        trackUserLocation: true,
        showUserHeading: true
    });
    
    geolocate.on('geolocate', function(e) {
        userLocation = {
            lat: e.coords.latitude,
            lng: e.coords.longitude
        };
        onLocationFound(e);
    });
    
    map.addControl(geolocate);

    // Configurar terreno 3D
    map.on('style.load', () => {
        map.addSource('mapbox-dem', {
            'type': 'raster-dem',
            'url': 'mapbox://mapbox.mapbox-terrain-dem-v1',
            'tileSize': 512,
            'maxzoom': 14
        });
        map.setTerrain({ 'source': 'mapbox-dem', 'exaggeration': 2 });
        
        // Agregar capa de cielo para efecto 3D
        map.addLayer({
            'id': 'sky',
            'type': 'sky',
            'paint': {
                'sky-type': 'atmosphere',
                'sky-atmosphere-sun': [0.0, 0.0],
                'sky-atmosphere-sun-intensity': 15
            }
        });
        
        initDestinoMarkers();
    });
}

// ============================================
// FUNCIONES DE LOCALIZACIÓN
// ============================================
function locateUser() {
    if (!navigator.geolocation) {
        alert('Tu navegador no soporta geolocalización');
        return;
    }
    
    navigator.geolocation.getCurrentPosition(function(position) {
        userLocation = {
            lat: position.coords.latitude,
            lng: position.coords.longitude
        };
        
        map.flyTo({
            center: [userLocation.lng, userLocation.lat],
            zoom: 12,
            pitch: 60,
            duration: 2000
        });
        
        onLocationFound(position);
    }, function(error) {
        onLocationError(error);
    });
}

function onLocationFound(e) {
    const coords = e.coords || e;
    const lat = coords.latitude || coords.lat;
    const lng = coords.longitude || coords.lng;
    
    if (userMarker) {
        userMarker.remove();
    }
    
    // Crear marcador personalizado para usuario
    const el = document.createElement('div');
    el.className = 'user-marker';
    el.style.cssText = `
        background: #0284c7;
        border: 3px solid white;
        border-radius: 50%;
        width: 20px;
        height: 20px;
        box-shadow: 0 2px 10px rgba(2,132,199,0.5);
        cursor: pointer;
    `;
    
    userMarker = new mapboxgl.Marker(el)
        .setLngLat([lng, lat])
        .setPopup(new mapboxgl.Popup().setHTML('Tu ubicación'))
        .addTo(map);
    
    mostrarNotificación('Ubicación encontrada. Selecciona un destino para ver las opciones de rutas.', 'success');
}

function onLocationError(e) {
    alert('No se pudo obtener tu ubicación: ' + e.message);
}

// ============================================
// FUNCIONES DE DESTINOS
// ============================================
function initDestinoMarkers() {
    destinos.forEach(function(dest) {
        const lat = window.Utils ? window.Utils.parseCoordinate(dest.latitud) : parseFloat(dest.latitud);
        const lng = window.Utils ? window.Utils.parseCoordinate(dest.longitud) : parseFloat(dest.longitud);
        
        // Crear marcador personalizado
        const el = document.createElement('div');
        el.className = 'destino-marker';
        el.style.cssText = `
            background: #10b981;
            border: 2px solid white;
            border-radius: 50%;
            width: 14px;
            height: 14px;
            box-shadow: 0 2px 6px rgba(16,185,129,0.3);
            cursor: pointer;
        `;
        
        const marker = new mapboxgl.Marker(el)
            .setLngLat([lng, lat])
            .setPopup(new mapboxgl.Popup().setHTML(`<b>${dest.nombre}</b><br>${dest.region_display}<br>${dest.provincia}`))
            .addTo(map);
        
        markers[dest.id] = marker;
        
        el.addEventListener('click', function(e) {
            e.stopPropagation();
            seleccionarDestino(dest);
        });
    });
}

function seleccionarDestino(dest) {
    if (!userLocation) {
        mostrarNotificación('Primero localiza tu posición en el mapa', 'warning');
        return;
    }

    selectedDestino = dest;
    actualizarListaDestinos();
    
    if (destinoMarker) {
        destinoMarker.remove();
    }
    
    const destLat = parseFloat(String(dest.latitud).replace(',', '.'));
    const destLng = parseFloat(String(dest.longitud).replace(',', '.'));
    
    // Crear marcador de destino seleccionado
    const el = document.createElement('div');
    el.className = 'destino-selected-marker';
    el.style.cssText = `
        background: #dc2626;
        border: 3px solid white;
        border-radius: 50%;
        width: 20px;
        height: 20px;
        box-shadow: 0 2px 10px rgba(220,38,38,0.5);
    `;
    
    destinoMarker = new mapboxgl.Marker(el)
        .setLngLat([destLng, destLat])
        .setPopup(new mapboxgl.Popup().setHTML(`<b>${dest.nombre}</b><br>${dest.region_display}<br>${dest.provincia}`))
        .addTo(map);
    
    // Volar a vista que incluya ambos puntos con efecto 3D
    const bounds = new mapboxgl.LngLatBounds()
        .extend([userLocation.lng, userLocation.lat])
        .extend([destLng, destLat]);
    
    map.fitBounds(bounds, {
        padding: 100,
        pitch: 60,
        bearing: -17.6,
        duration: 2000
    });
    
    buscarRutasDisponibles(dest);
    mostrarRutaPreliminar(dest);
    mostrarNotificación(`Destino seleccionado: ${dest.nombre}`, 'success');
}

function mostrarRutaPreliminar(destino) {
    if (!userLocation || !destino) return;
    
    limpiarRutas();
    
    const destLat = parseFloat(String(destino.latitud).replace(',', '.'));
    const destLng = parseFloat(String(destino.longitud).replace(',', '.'));
    
    // Obtener ruta usando Mapbox Directions API
    obtenerRutaMapbox(userLocation.lng, userLocation.lat, destLng, destLat);
}

function obtenerRutaMapbox(startLng, startLat, endLng, endLat) {
    const url = `https://api.mapbox.com/directions/v5/mapbox/driving/${startLng},${startLat};${endLng},${endLat}?geometries=geojson&access_token=${mapboxgl.accessToken}`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.routes && data.routes.length > 0) {
                const route = data.routes[0];
                
                // Agregar la ruta al mapa
                if (map.getSource('route')) {
                    map.removeLayer('route');
                    map.removeSource('route');
                }
                
                map.addSource('route', {
                    'type': 'geojson',
                    'data': {
                        'type': 'Feature',
                        'properties': {},
                        'geometry': route.geometry
                    }
                });
                
                map.addLayer({
                    'id': 'route',
                    'type': 'line',
                    'source': 'route',
                    'layout': {
                        'line-join': 'round',
                        'line-cap': 'round'
                    },
                    'paint': {
                        'line-color': '#ef4444',
                        'line-width': 6,
                        'line-opacity': 0.8
                    }
                });
                
                // Ajustar vista a la ruta con efecto 3D
                const coordinates = route.geometry.coordinates;
                const bounds = coordinates.reduce((bounds, coord) => {
                    return bounds.extend(coord);
                }, new mapboxgl.LngLatBounds(coordinates[0], coordinates[0]));
                
                map.fitBounds(bounds, {
                    padding: 80,
                    pitch: 60,
                    bearing: -17.6
                });
            } else {
                // Fallback a línea directa
                mostrarLineaDirecta(startLng, startLat, endLng, endLat);
            }
        })
        .catch(error => {
            console.error('Error obteniendo ruta:', error);
            mostrarLineaDirecta(startLng, startLat, endLng, endLat);
        });
}

function mostrarLineaDirecta(startLng, startLat, endLng, endLat) {
    if (map.getSource('route')) {
        map.removeLayer('route');
        map.removeSource('route');
    }
    
    map.addSource('route', {
        'type': 'geojson',
        'data': {
            'type': 'Feature',
            'properties': {},
            'geometry': {
                'type': 'LineString',
                'coordinates': [
                    [startLng, startLat],
                    [endLng, endLat]
                ]
            }
        }
    });
    
    map.addLayer({
        'id': 'route',
        'type': 'line',
        'source': 'route',
        'layout': {
            'line-join': 'round',
            'line-cap': 'round'
        },
        'paint': {
            'line-color': '#0284c7',
            'line-width': 4,
            'line-opacity': 0.6,
            'line-dasharray': [2, 2]
        }
    });
}

function limpiarRutas() {
    if (map.getLayer('route')) {
        map.removeLayer('route');
    }
    if (map.getSource('route')) {
        map.removeSource('route');
    }
    
    transferMarkers.forEach(marker => marker.remove());
    transferMarkers = [];
}

// ============================================
// FUNCIONES DE CÁLCULO (mantener originales)
// ============================================
function determinarCiudadCercana(location) {
    var closest = null;
    var minDist = Infinity;
    var allLocations = [...destinos, ...transporteData.terminales_terrestres, ...transporteData.aeropuertos, ...transporteData.puertos_maritimos];
    allLocations.forEach(function(point) {
        if (point.latitud !== undefined && point.longitud !== undefined) {
            const lat1 = parseFloat(String(point.latitud).replace(',', '.'));
            const lng1 = parseFloat(String(point.longitud).replace(',', '.'));
            var dist = calcularDistanciaSimple(location.lat, location.lng, lat1, lng1);
            if (dist < minDist) {
                minDist = dist;
                closest = point.ciudad || point.nombre;
            }
        }
    });
    return closest || 'Guayaquil';
}

function normalizar(nombre) {
    return window.Utils ? window.Utils.normalizar(nombre) : nombre;
}

function calcularDistanciaSimple(lat1, lng1, lat2, lng2) {
    return window.Utils ? window.Utils.calcularDistancia(lat1, lng1, lat2, lng2) : 0;
}

// ============================================
// FUNCIONES DE RUTAS (simplificadas para Mapbox)
// ============================================
function buscarRutasDisponibles(destino) {
    const destLat = parseFloat(String(destino.latitud).replace(',', '.'));
    const destLng = parseFloat(String(destino.longitud).replace(',', '.'));
    
    // Obtener información de ruta real
    const url = `https://api.mapbox.com/directions/v5/mapbox/driving/${userLocation.lng},${userLocation.lat};${destLng},${destLat}?geometries=geojson&access_token=${mapboxgl.accessToken}`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.routes && data.routes.length > 0) {
                const route = data.routes[0];
                const distanciaKm = (route.distance / 1000).toFixed(1);
                const duracionHoras = (route.duration / 3600).toFixed(1);
                
                rutasDisponibles = [{
                    tipo: 'recomendada',
                    nombre: `Ruta por carretera a ${destino.nombre}`,
                    descripcion: `Ruta óptima siguiendo las carreteras principales`,
                    tramos: [{
                        orden: 1,
                        desde: 'Tu ubicación',
                        hasta: destino.nombre,
                        medio_transporte: 'terrestre',
                        duracion_aprox: `${duracionHoras} horas`,
                        distancia_km: distanciaKm,
                        costo_aprox: Math.round(parseFloat(distanciaKm) * 0.15)
                    }],
                    duracion_total: `${duracionHoras} horas`,
                    distancia_total: `${distanciaKm} km`,
                    costo_total: Math.round(parseFloat(distanciaKm) * 0.15)
                }];
            } else {
                rutasDisponibles = [{
                    tipo: 'recomendada',
                    nombre: `Ruta a ${destino.nombre}`,
                    descripcion: 'Ruta directa (verificar disponibilidad)',
                    tramos: [{
                        orden: 1,
                        desde: 'Tu ubicación',
                        hasta: destino.nombre,
                        medio_transporte: 'terrestre',
                        duracion_aprox: 'Por determinar',
                        costo_aprox: 'Por determinar'
                    }],
                    duracion_total: 'Por determinar',
                    costo_total: 0
                }];
            }
            
            mostrarOpcionesRutas();
        })
        .catch(error => {
            console.error('Error obteniendo datos de ruta:', error);
            rutasDisponibles = [{
                tipo: 'recomendada',
                nombre: `Ruta a ${destino.nombre}`,
                descripcion: 'Ruta básica',
                tramos: [{
                    orden: 1,
                    desde: 'Tu ubicación',
                    hasta: destino.nombre,
                    medio_transporte: 'terrestre',
                    duracion_aprox: 'Por determinar',
                    costo_aprox: 'Por determinar'
                }],
                duracion_total: 'Por determinar',
                costo_total: 0
            }];
            
            mostrarOpcionesRutas();
        });
}

// ============================================
// FUNCIONES DE UI (mantener originales)
// ============================================
function mostrarNotificación(mensaje, tipo) {
    if (window.Utils) {
        window.Utils.mostrarNotificacion(mensaje, tipo);
    }
}

function renderizarListaDestinos(destinosFiltrados) {
    var lista = document.getElementById('lista-destinos');
    lista.innerHTML = '';
    
    if (destinosFiltrados.length === 0) {
        lista.innerHTML = '<p class="text-sm text-gray-500 dark:text-gray-400 text-center py-4">No se encontraron destinos</p>';
        return;
    }
    
    destinosFiltrados.forEach(function(dest) {
        var isSelected = selectedDestino && selectedDestino.id === dest.id;
        var div = document.createElement('div');
        div.className = `destino-item p-4 rounded-xl border cursor-pointer transition-all duration-300 ${isSelected ? 'selected border-sky-400 dark:border-sky-500 bg-sky-50 dark:bg-sky-900/30 shadow-lg' : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 hover:border-sky-300 dark:hover:border-sky-600 hover:shadow-md hover:bg-gray-50 dark:hover:bg-gray-700/60'}`;
        div.innerHTML = `
            <div class="flex items-start justify-between">
                <div class="flex-1">
                    <h4 class="text-sm font-semibold text-gray-900 dark:text-white">${dest.nombre}</h4>
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        <i class="fas fa-map-marker-alt mr-1"></i>${dest.region_display}
                    </p>
                    <p class="text-xs text-gray-500 dark:text-gray-400">
                        <i class="fas fa-map-pin mr-1"></i>${dest.provincia}
                    </p>
                    ${dest.precio_promedio_minimo && dest.precio_promedio_maximo ? 
                      `<p class="text-xs text-green-600 dark:text-green-400 mt-1"><i class="fas fa-dollar-sign mr-1"></i>${dest.precio_promedio_minimo.toFixed(1)} - ${dest.precio_promedio_maximo.toFixed(1)}</p>` : ''}
                </div>
                <div>
                    ${isSelected ? 
                        '<span class="inline-block bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-400 text-xs px-2 py-1 rounded-full font-semibold"><i class="fas fa-check"></i></span>' : 
                        ''
                    }
                </div>
            </div>
        `;
        
        if (!isSelected) {
            div.onclick = function() {
                seleccionarDestino(dest);
            };
        }
        
        lista.appendChild(div);
    });
}

function actualizarListaDestinos() {
    var busqueda = document.getElementById('buscar-destino').value.toLowerCase();
    var region = document.getElementById('filtro-region').value.toLowerCase();
    
    var destinosFiltrados = destinos.filter(function(dest) {
        var matchBusqueda = dest.nombre.toLowerCase().includes(busqueda) || 
                           dest.provincia.toLowerCase().includes(busqueda);
        var matchRegion = !region || dest.region.toLowerCase() === region;
        return matchBusqueda && matchRegion;
    });
    
    renderizarListaDestinos(destinosFiltrados);
}

function mostrarOpcionesRutas() {
    var container = document.getElementById('rutas-opciones');
    var lista = document.getElementById('lista-rutas');
    
    container.style.display = 'block';
    lista.innerHTML = '';
    
    if (!selectedDestino) return;
    
    rutasDisponibles.forEach(function(ruta, index) {
        var div = document.createElement('div');
        div.className = 'ruta-option p-6 rounded-xl border-2 border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 cursor-pointer hover:border-sky-300 dark:hover:border-sky-500 hover:shadow-lg transition-all duration-300';
        
        div.addEventListener('click', function() {
            seleccionarRuta(index);
        });
        
        var tipoColor = ruta.tipo === 'recomendada' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800';
        var tipoTexto = ruta.tipo === 'recomendada' ? 'Recomendada' : 'Alternativa';
        var tipoIcon = ruta.tipo === 'recomendada' ? 'fas fa-star' : 'fas fa-route';
        
        div.innerHTML = `
            <div class="flex items-start justify-between">
                <div class="flex-1">
                    <div class="flex items-center space-x-2 mb-3">
                        <span class="inline-flex items-center px-3 py-1.5 text-xs font-semibold rounded-full ${tipoColor}">
                            <i class="${tipoIcon} mr-1.5"></i>
                            ${tipoTexto}
                        </span>
                        <h3 class="font-bold text-gray-900 dark:text-white text-lg">${ruta.nombre}</h3>
                    </div>
                    <p class="text-sm text-gray-600 dark:text-gray-300 mb-4">${ruta.descripcion}</p>
                    
                    ${ruta.tramos.map(tramo => `
                        <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg mb-2">
                            <div class="flex items-center space-x-3">
                                <div class="w-8 h-8 bg-sky-100 dark:bg-sky-900/50 rounded-full flex items-center justify-center">
                                    <i class="fas fa-route text-sky-600 dark:text-sky-400 text-sm"></i>
                                </div>
                                <div>
                                    <div class="font-medium text-gray-900 dark:text-white text-sm">
                                        ${tramo.desde} <i class="fas fa-arrow-right text-gray-400 mx-2"></i> ${tramo.hasta}
                                    </div>
                                    <div class="text-xs text-gray-500 dark:text-gray-400">
                                        ${tramo.duracion_aprox}${tramo.distancia_km ? ` • ${tramo.distancia_km} km` : ''}
                                    </div>
                                </div>
                            </div>
                            ${tramo.costo_aprox ? `
                                <div class="text-right">
                                    <div class="font-semibold text-green-600 dark:text-green-400">$${tramo.costo_aprox}</div>
                                    <div class="text-xs text-gray-500 dark:text-gray-400">USD</div>
                                </div>
                            ` : ''}
                        </div>
                    `).join('')}
                    
                    <div class="flex items-center justify-between mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                        <div class="flex items-center space-x-4 text-sm">
                            ${ruta.duracion_total ? `
                                <div class="flex items-center text-gray-700 dark:text-gray-300">
                                    <div class="w-6 h-6 bg-blue-100 dark:bg-blue-900/50 rounded-full flex items-center justify-center mr-2">
                                        <i class="fas fa-clock text-blue-600 dark:text-blue-400 text-xs"></i>
                                    </div>
                                    <span class="font-medium">${ruta.duracion_total}</span>
                                </div>
                            ` : ''}
                            ${ruta.distancia_total ? `
                                <div class="flex items-center text-gray-700 dark:text-gray-300">
                                    <div class="w-6 h-6 bg-indigo-100 dark:bg-indigo-900/50 rounded-full flex items-center justify-center mr-2">
                                        <i class="fas fa-road text-indigo-600 dark:text-indigo-400 text-xs"></i>
                                    </div>
                                    <span class="font-medium">${ruta.distancia_total}</span>
                                </div>
                            ` : ''}
                        </div>
                        ${ruta.costo_total ? `
                            <div class="text-right">
                                <div class="text-2xl font-bold text-green-600 dark:text-green-400">$${ruta.costo_total}</div>
                                <div class="text-xs text-gray-500 dark:text-gray-400">Total USD</div>
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
        
        lista.appendChild(div);
    });
}

window.seleccionarRuta = function(index) {
    rutaSeleccionada = rutasDisponibles[index];
    
    var opciones = document.querySelectorAll('.ruta-option');
    opciones.forEach(function(op, i) {
        if (i === index) {
            op.classList.add('selected');
            op.classList.remove('border-gray-200', 'dark:border-gray-700');
            op.classList.add('border-sky-500', 'dark:border-sky-400', 'bg-sky-50', 'dark:bg-sky-900/20', 'shadow-lg');
        } else {
            op.classList.remove('selected', 'border-sky-500', 'dark:border-sky-400', 'bg-sky-50', 'dark:bg-sky-900/20', 'shadow-lg');
            op.classList.add('border-gray-200', 'dark:border-gray-700');
        }
    });
    
    mostrarNotificación(`Ruta "${rutaSeleccionada.nombre}" seleccionada`, 'success');
};

window.recargarMapa = function() {
    map.resize();
    mostrarNotificación('Mapa recargado', 'success');
};

// Variable para controlar el estado 3D
let is3DView = true;

window.toggle3DView = function() {
    const toggleBtn = document.getElementById('toggle3DBtn');
    const toggleText = document.getElementById('toggle3DText');
    
    if (is3DView) {
        // Cambiar a vista 2D
        map.easeTo({
            pitch: 0,
            bearing: 0,
            duration: 1000
        });
        toggleText.textContent = 'Vista 3D';
        toggleBtn.querySelector('i').className = 'fas fa-mountain mr-2';
        is3DView = false;
        mostrarNotificación('Vista 2D activada', 'info');
    } else {
        // Cambiar a vista 3D
        map.easeTo({
            pitch: 45,
            bearing: 0,
            duration: 1000
        });
        toggleText.textContent = 'Vista 2D';
        toggleBtn.querySelector('i').className = 'fas fa-cube mr-2';
        is3DView = true;
        mostrarNotificación('Vista 3D activada', 'info');
    }
};

// ============================================
// INICIALIZACIÓN
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    actualizarListaDestinos();
    
    document.getElementById('buscar-destino').addEventListener('input', actualizarListaDestinos);
    document.getElementById('filtro-region').addEventListener('change', actualizarListaDestinos);
    
    window.addEventListener('resize', function() {
        map.resize();
    });
});