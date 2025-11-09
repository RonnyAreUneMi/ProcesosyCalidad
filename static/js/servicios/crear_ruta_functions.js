// ============================================
// VARIABLES GLOBALES
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

// Mapa de puntos de transporte por ID
let allPoints = [...transporteData.terminales_terrestres, ...transporteData.aeropuertos, ...transporteData.puertos_maritimos];
allPoints.forEach(p => {
    pointById[p.id] = p.nombre;
});

// ============================================
// FUNCIONES AUXILIARES
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
// INICIALIZACIÓN DEL MAPA
// ============================================
function initMap() {
    map = L.map('map', {
        center: [-1.8312, -78.1834],
        zoom: 7,
        zoomControl: true,
        preferCanvas: false
    });

    var tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
        minZoom: 3,
        crossOrigin: true
    });
    
    tileLayer.addTo(map);

    setTimeout(function() {
        map.invalidateSize(true);
        map.setView([-1.8312, -78.1834], 7);
    }, 100);

    L.Control.Locate = L.Control.extend({
        onAdd: function(map) {
            var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-locate');
            container.innerHTML = '<i class="fas fa-location-crosshairs" style="font-size: 16px; color: #0284c7;"></i>';
            container.title = 'Localizar mi posición';
            
            L.DomEvent.on(container, 'click', function(e) {
                L.DomEvent.stopPropagation(e);
                L.DomEvent.preventDefault(e);
                locateUser();
            });
            
            return container;
        }
    });
    
    var locateControl = new L.Control.Locate({ position: 'topleft' });
    map.addControl(locateControl);

    routingControl = L.Routing.control({
        waypoints: [],
        routeWhileDragging: false,
        show: false,
        addWaypoints: false,
        draggableWaypoints: false,
        fitSelectedRoutes: false,
        showAlternatives: false,
        lineOptions: {
            styles: [{color: '#ef4444', opacity: 0.8, weight: 5}],
            extendToWaypoints: true,
            missingRouteTolerance: 0
        },
        createMarker: function() { 
            return null;
        },
        router: L.Routing.osrmv1({
            serviceUrl: 'https://router.project-osrm.org/route/v1'
        })
    });

    routingControl.on('routingerror', function(e) {
        var waypoints = routingControl.getWaypoints();
        var coords = waypoints.map(function(wp) {
            return [wp.latLng.lat, wp.latLng.lng];
        });
        if (window.fallbackLine) {
            map.removeLayer(window.fallbackLine);
        }
        window.fallbackLine = L.polyline(coords, {
            color: '#0284c7',
            weight: 5,
            opacity: 0.8
        }).addTo(map);
        if (coords.length > 1) {
            map.fitBounds(L.latLngBounds(coords));
        }
    });

    map.on('locationfound', onLocationFound);
    map.on('locationerror', onLocationError);
    map.on('click', function() { map.invalidateSize(true); });
    map.on('zoomend', function() {
        setTimeout(function() { map.invalidateSize(true); }, 100);
    });
    map.on('moveend', function() {
        setTimeout(function() { map.invalidateSize(true); }, 100);
    });

    initDestinoMarkers();
}

// ============================================
// FUNCIONES DE LOCALIZACIÓN
// ============================================
function locateUser() {
    if (!navigator.geolocation) {
        alert('Tu navegador no soporta geolocalización');
        return;
    }
    map.locate({setView: true, maxZoom: 12});
}

function onLocationFound(e) {
    var radius = e.accuracy / 2;
    userLocation = e.latlng;
    
    if (userMarker) {
        map.removeLayer(userMarker);
    }
    
    var userIcon = L.divIcon({
        className: 'user-location-icon',
        html: '<div style="background: #0284c7; border: 3px solid white; border-radius: 50%; width: 20px; height: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.3);"></div>',
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });
    
    userMarker = L.marker(e.latlng, {icon: userIcon}).addTo(map)
        .bindPopup(`Tu ubicación (precisión: ${radius.toFixed(0)}m)`).openPopup();
    
    L.circle(e.latlng, radius, {
        color: '#0284c7',
        fillColor: '#38bdf8',
        fillOpacity: 0.2,
        weight: 2
    }).addTo(map);
    
    map.setView(e.latlng, 12);
    
    setTimeout(function() {
        map.invalidateSize(true);
    }, 100);
    
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
        var marker = L.marker([dest.latitud, dest.longitud])
            .bindPopup(`<b>${dest.nombre}</b><br>${dest.region_display}<br>${dest.provincia}`);
        
        markers[dest.id] = marker;
        
        marker.on('click', function() {
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
        map.removeLayer(destinoMarker);
    }
    
    var destinoIcon = L.divIcon({
        className: 'destino-marker-icon',
        html: '<div style="background: #dc2626; border: 3px solid white; border-radius: 50%; width: 24px; height: 24px; box-shadow: 0 2px 5px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;"><i class="fas fa-map-marker-alt" style="color: white; font-size: 12px;"></i></div>',
        iconSize: [24, 24],
        iconAnchor: [12, 24]
    });
    
    destinoMarker = L.marker([dest.latitud, dest.longitud], {icon: destinoIcon})
        .addTo(map)
        .bindPopup(`<b>${dest.nombre}</b><br>${dest.region_display}<br>${dest.provincia}`)
        .openPopup();
    
    var bounds = L.latLngBounds([
        [userLocation.lat, userLocation.lng],
        [dest.latitud, dest.longitud]
    ]);
    map.fitBounds(bounds, {padding: [80, 80]});
    
    buscarRutasDisponibles(dest);
    mostrarRutaPreliminar(dest);
    mostrarNotificación(`Destino seleccionado: ${dest.nombre}`, 'success');
}

function mostrarRutaPreliminar(destino) {
    if (!userLocation || !destino) return;
    
    if (routingControl) {
        map.removeControl(routingControl);
    }
    if (window.fallbackLine) {
        map.removeLayer(window.fallbackLine);
    }
    
    if (customRouteLines && customRouteLines.length > 0) {
        customRouteLines.forEach(function(line) {
            map.removeLayer(line);
        });
        customRouteLines = [];
    }
    
    if (transferMarkers) {
        transferMarkers.forEach(function(marker) {
            map.removeLayer(marker);
        });
        transferMarkers = [];
    }
    
    var waypoints = [
        L.latLng(userLocation.lat, userLocation.lng),
        L.latLng(destino.latitud, destino.longitud)
    ];
    
    routingControl.setWaypoints(waypoints);
    routingControl.addTo(map);
    map.fitBounds(L.latLngBounds(waypoints), {padding: [50, 50]});
    
    setTimeout(function() {
        map.invalidateSize(true);
    }, 200);
}

// ============================================
// FUNCIONES DE CÁLCULO
// ============================================
function determinarCiudadCercana(location) {
    var closest = null;
    var minDist = Infinity;
    var allLocations = [...destinos, ...transporteData.terminales_terrestres, ...transporteData.aeropuertos, ...transporteData.puertos_maritimos];
    allLocations.forEach(function(point) {
        if (point.latitud !== undefined && point.longitud !== undefined) {
            var dist = map.distance([location.lat, location.lng], [point.latitud, point.longitud]);
            if (dist < minDist) {
                minDist = dist;
                closest = point.ciudad || point.nombre;
            }
        }
    });
    return closest || 'Guayaquil';
}

function normalizar(nombre) {
    return nombre
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^a-z0-9]/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_|_$/g, '');
}

function encontrarPuntoTransporte(ciudad, transporteData, tipoPreferido = null) {
    const todosPuntos = [
        ...(transporteData.terminales_terrestres || []),
        ...(transporteData.aeropuertos || []),
        ...(transporteData.puertos_maritimos || [])
    ];
    
    let puntosFiltrados = tipoPreferido ? 
        todosPuntos.filter(p => p.tipo === tipoPreferido) : 
        todosPuntos;
    
    let punto = puntosFiltrados.find(p => 
        p.ciudad && normalizar(p.ciudad) === normalizar(ciudad)
    );
    
    if (!punto) {
        punto = puntosFiltrados.find(p => 
            normalizar(p.nombre).includes(normalizar(ciudad)) ||
            normalizar(ciudad).includes(normalizar(p.ciudad || ''))
        );
    }
    
    return punto;
}

function encontrarAeropuertoCercano(ciudadOrigen, transporteData) {
    if (!transporteData.aeropuertos) return null;
    
    let aeropuerto = transporteData.aeropuertos.find(a => 
        normalizar(a.ciudad) === normalizar(ciudadOrigen)
    );
    
    if (!aeropuerto) {
        const puntoOrigen = encontrarPuntoTransporte(ciudadOrigen, transporteData);
        if (puntoOrigen) {
            let distanciaMin = Infinity;
            transporteData.aeropuertos.forEach(a => {
                const dist = calcularDistancia(puntoOrigen, a);
                if (dist < distanciaMin) {
                    distanciaMin = dist;
                    aeropuerto = a;
                }
            });
        }
    }
    
    return aeropuerto;
}

function calcularDistancia(punto1, punto2) {
    const R = 6371;
    const lat1 = punto1.latitud * Math.PI / 180;
    const lat2 = punto2.latitud * Math.PI / 180;
    const deltaLat = (punto2.latitud - punto1.latitud) * Math.PI / 180;
    const deltaLng = (punto2.longitud - punto1.longitud) * Math.PI / 180;
    
    const a = Math.sin(deltaLat/2) * Math.sin(deltaLat/2) +
              Math.cos(lat1) * Math.cos(lat2) *
              Math.sin(deltaLng/2) * Math.sin(deltaLng/2);
    
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    
    return Math.round(R * c);
}

function estimarDuracion(punto1, punto2, medio) {
    const distancia = calcularDistancia(punto1, punto2);
    
    const velocidades = {
        'terrestre': 50,
        'aereo': 500,
        'maritimo': 30
    };
    
    const horas = distancia / velocidades[medio];
    const horasAjustadas = medio === 'aereo' ? horas + 2 : horas;
    
    if (horasAjustadas < 1) {
        return `${Math.round(horasAjustadas * 60)} minutos`;
    } else if (horasAjustadas < 24) {
        const horasRedondeadas = Math.round(horasAjustadas * 10) / 10;
        const horasEnteras = Math.floor(horasRedondeadas);
        const minutosDecimales = (horasRedondeadas - horasEnteras) * 60;
        
        if (minutosDecimales > 0) {
            return `${horasEnteras} hora${horasEnteras !== 1 ? 's' : ''} ${Math.round(minutosDecimales)} minutos`;
        } else {
            return `${horasEnteras} hora${horasEnteras !== 1 ? 's' : ''}`;
        }
    } else {
        const dias = Math.floor(horasAjustadas / 24);
        const horasRestantes = Math.round(horasAjustadas % 24);
        return `${dias} día${dias > 1 ? 's' : ''} ${horasRestantes} horas`;
    }
}

function estimarDuracionHoras(punto1, punto2, medio) {
    const distancia = calcularDistancia(punto1, punto2);
    
    const velocidades = {
        'terrestre': 50,
        'aereo': 500,
        'maritimo': 30
    };
    
    const horas = distancia / velocidades[medio];
    return medio === 'aereo' ? horas + 2 : horas;
}

function estimarCosto(punto1, punto2, medio) {
    const distancia = calcularDistancia(punto1, punto2);
    
    const tarifasPorKm = {
        'terrestre': 0.03,
        'aereo': 0.35,
        'maritimo': 0.15
    };
    
    const costoBase = {
        'terrestre': 2,
        'aereo': 50,
        'maritimo': 20
    };
    
    return Math.round(costoBase[medio] + (distancia * tarifasPorKm[medio]));
}

// ============================================
// GENERACIÓN DE RUTAS
// ============================================
function generarRutasDinamicas(origen, destino, transporteData) {
    const rutas = [];
    
    const puntoOrigenTerrestre = encontrarPuntoTransporte(origen, transporteData, 'terrestre');
    const puntoDestinoTerrestre = encontrarPuntoTransporte(destino, transporteData, 'terrestre');
    
    if (!puntoOrigenTerrestre || !puntoDestinoTerrestre) {
        return [{
            tipo: 'recomendada',
            nombre: `Ruta directa a ${destino}`,
            descripcion: 'Ruta básica (requiere verificación)',
            tramos: [{
                orden: 1,
                desde: origen,
                hasta: destino,
                medio_transporte: 'terrestre',
                duracion_aprox: 'Por determinar',
                distancia_km: 0,
                costo_aprox: 0
            }],
            duracion_total: 'Por determinar',
            costo_total: 0
        }];
    }
    
    const duracionTerrestre = estimarDuracion(puntoOrigenTerrestre, puntoDestinoTerrestre, 'terrestre');
    const costoTerrestre = estimarCosto(puntoOrigenTerrestre, puntoDestinoTerrestre, 'terrestre');
    const duracionTerrestreHoras = estimarDuracionHoras(puntoOrigenTerrestre, puntoDestinoTerrestre, 'terrestre');
    
    rutas.push({
        tipo: 'recomendada',
        nombre: 'Ruta Terrestre Directa',
        descripcion: 'Viaje por carretera en bus interprovincial',
        tramos: [{
            orden: 1,
            desde: puntoOrigenTerrestre.ciudad,
            hasta: puntoDestinoTerrestre.ciudad,
            medio_transporte: 'terrestre',
            punto_partida: puntoOrigenTerrestre.id,
            punto_llegada: puntoDestinoTerrestre.id,
            duracion_aprox: duracionTerrestre,
            distancia_km: calcularDistancia(puntoOrigenTerrestre, puntoDestinoTerrestre),
            costo_aprox: costoTerrestre
        }],
        duracion_total: duracionTerrestre,
        duracion_horas: duracionTerrestreHoras,
        costo_total: costoTerrestre
    });
    
    const aeropuertoOrigen = encontrarAeropuertoCercano(origen, transporteData);
    const aeropuertoDestino = encontrarAeropuertoCercano(destino, transporteData);
    
    if (aeropuertoOrigen && aeropuertoDestino) {
        if (aeropuertoOrigen.id === aeropuertoDestino.id) {
            return rutas;
        }
        
        const tieneAeropuertoOrigen = transporteData.aeropuertos.some(a => 
            normalizar(a.ciudad) === normalizar(origen)
        );
        
        if (!tieneAeropuertoOrigen) {
            return rutas;
        }
        
        const tramosAereos = [];
        let orden = 1;
        let duracionTotalAerea = 0;
        let costoTotalAereo = 0;
        
        const distanciaAlAeropuerto = calcularDistancia(puntoOrigenTerrestre, aeropuertoOrigen);
        if (distanciaAlAeropuerto > 10) {
            const duracionTraslado = estimarDuracionHoras(puntoOrigenTerrestre, aeropuertoOrigen, 'terrestre');
            duracionTotalAerea += duracionTraslado;
            costoTotalAereo += 5;
            
            tramosAereos.push({
                orden: orden++,
                desde: puntoOrigenTerrestre.ciudad,
                hasta: aeropuertoOrigen.ciudad,
                medio_transporte: 'terrestre',
                punto_partida: puntoOrigenTerrestre.id,
                punto_llegada: aeropuertoOrigen.id,
                duracion_aprox: estimarDuracion(puntoOrigenTerrestre, aeropuertoOrigen, 'terrestre'),
                distancia_km: Math.round(distanciaAlAeropuerto),
                costo_aprox: 5
            });
        }
        
        const duracionVuelo = estimarDuracionHoras(aeropuertoOrigen, aeropuertoDestino, 'aereo');
        const costoVuelo = estimarCosto(aeropuertoOrigen, aeropuertoDestino, 'aereo');
        duracionTotalAerea += duracionVuelo;
        costoTotalAereo += costoVuelo;
        
        tramosAereos.push({
            orden: orden++,
            desde: aeropuertoOrigen.ciudad,
            hasta: aeropuertoDestino.ciudad,
            medio_transporte: 'aereo',
            punto_partida: aeropuertoOrigen.id,
            punto_llegada: aeropuertoDestino.id,
            duracion_aprox: estimarDuracion(aeropuertoOrigen, aeropuertoDestino, 'aereo'),
            distancia_km: calcularDistancia(aeropuertoOrigen, aeropuertoDestino),
            costo_aprox: costoVuelo
        });
        
        const distanciaDelAeropuerto = calcularDistancia(aeropuertoDestino, puntoDestinoTerrestre);
        if (distanciaDelAeropuerto > 10) {
            const duracionTraslado = estimarDuracionHoras(aeropuertoDestino, puntoDestinoTerrestre, 'terrestre');
            duracionTotalAerea += duracionTraslado;
            costoTotalAereo += 5;
            
            tramosAereos.push({
                orden: orden++,
                desde: aeropuertoDestino.ciudad,
                hasta: puntoDestinoTerrestre.ciudad,
                medio_transporte: 'terrestre',
                punto_partida: aeropuertoDestino.id,
                punto_llegada: puntoDestinoTerrestre.id,
                duracion_aprox: estimarDuracion(aeropuertoDestino, puntoDestinoTerrestre, 'terrestre'),
                distancia_km: Math.round(distanciaDelAeropuerto),
                costo_aprox: 5
            });
        }
        
        if (duracionTotalAerea < (duracionTerrestreHoras - 3)) {
            const duracionTotalAereaTexto = duracionTotalAerea < 24 ? 
                `${Math.round(duracionTotalAerea * 10) / 10} horas` : 
                `${Math.floor(duracionTotalAerea / 24)} día(s) ${Math.round(duracionTotalAerea % 24)} horas`;
            
            rutas.push({
                tipo: 'alternativa',
                nombre: 'Ruta Aérea Rápida',
                descripcion: 'Más rápida pero más costosa, combinando vuelo y transporte terrestre',
                tramos: tramosAereos,
                duracion_total: duracionTotalAereaTexto,
                duracion_horas: duracionTotalAerea,
                costo_total: costoTotalAereo
            });
        }
    }
    
    return rutas;
}

function buscarRutasDisponibles(destino) {
    rutasDisponibles = [];
    
    var ciudadOrigen = determinarCiudadCercana(userLocation);
    var ciudadDestino = destino.ciudad || destino.nombre;
    
    if (destino.region === "galapagos") {
        ciudadDestino = "galapagos";
    }
    
    var claveRuta = `${normalizar(ciudadOrigen)}_${normalizar(ciudadDestino)}`;
    var claveInvertida = `${normalizar(ciudadDestino)}_${normalizar(ciudadOrigen)}`;
    
    if (transporteData.rutas_recomendadas && transporteData.rutas_recomendadas[claveRuta]) {
        rutasDisponibles = transporteData.rutas_recomendadas[claveRuta];
    } else if (transporteData.rutas_recomendadas && transporteData.rutas_recomendadas[claveInvertida]) {
        rutasDisponibles = transporteData.rutas_recomendadas[claveInvertida].map(ruta => ({
            ...ruta,
            tramos: ruta.tramos.reverse().map((t, i) => ({...t, orden: ruta.tramos.length - i}))
        }));
    } else {
        rutasDisponibles = generarRutasDinamicas(ciudadOrigen, ciudadDestino, transporteData);
    }

    if (destino.region === "galapagos") {
        rutasDisponibles = rutasDisponibles.filter(function(ruta) {
            return ruta.tramos.some(function(tramo) {
                return tramo.medio_transporte === "aereo";
            });
        });
        
        if (rutasDisponibles.length > 0) {
            rutasDisponibles[0].tipo = 'recomendada';
            for (let i = 1; i < rutasDisponibles.length; i++) {
                rutasDisponibles[i].tipo = 'alternativa';
            }
        }
    } else {
        if (rutasDisponibles.length > 0) {
            rutasDisponibles.sort(function(a, b) {
                if (a.tipo === 'recomendada' && b.tipo !== 'recomendada') return -1;
                if (a.tipo !== 'recomendada' && b.tipo === 'recomendada') return 1;
                return 0;
            });
        }
    }
    
    rutasDisponibles = actualizarPreciosConDB(rutasDisponibles);
    
    mostrarOpcionesRutas();
}

// ============================================
// MOSTRAR Y SELECCIONAR RUTAS
// ============================================
function mostrarOpcionesRutas() {
    var container = document.getElementById('rutas-opciones');
    var lista = document.getElementById('lista-rutas');
    
    container.style.display = 'block';
    lista.innerHTML = '';
    
    if (!selectedDestino) return;
    
    var destMin = selectedDestino.precio_promedio_minimo || 0;
    var destMax = selectedDestino.precio_promedio_maximo || 0;
    var destName = selectedDestino.nombre;
    
    rutasDisponibles.forEach(function(ruta, index) {
        var costoTransporte = ruta.costo_total;
        var totalMin = costoTransporte + destMin;
        var totalMax = costoTransporte + destMax;
        
        var tramoDest = {
            orden: ruta.tramos.length + 1,
            desde: ruta.tramos[ruta.tramos.length - 1]?.hasta || 'Llegada',
            hasta: destName,
            medio_transporte: 'alojamiento',
            punto_partida: null,
            punto_llegada: null,
            duracion_aprox: 'Estadía variable',
            costo_aprox: `${destMin.toFixed(1)} - ${destMax.toFixed(1)}`,
            precio_disponible: true
        };
        var tramosConDest = [...ruta.tramos, tramoDest];
        var duracionTotalConDest = `${ruta.duracion_total} + estadía`;
        
        var div = document.createElement('div');
        div.className = 'ruta-option p-4 rounded-lg border-2 border-gray-200 bg-white';
        div.style.cursor = 'pointer';
        
        div.addEventListener('click', function() {
            seleccionarRuta(index);
        });
        
        var tipoColor = ruta.tipo === 'recomendada' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800';
        var tipoTexto = ruta.tipo === 'recomendada' ? '⭐ Recomendada' : 'Alternativa';
        
        var rutaConDest = `${ruta.nombre} a ${destName}`;
        
        var tramosHTML = '';
        tramosConDest.forEach(function(tramo) {
            var iconoMedio = {
                'terrestre': 'fa-bus',
                'aereo': 'fa-plane',
                'maritimo': 'fa-ship',
                'alojamiento': 'fa-bed'
            };
            
            var partidaName = pointById[tramo.punto_partida] || tramo.desde;
            var llegadaName = pointById[tramo.punto_llegada] || tramo.hasta;
            
            var costoDisplay;
            if (tramo.medio_transporte === 'alojamiento') {
                costoDisplay = tramo.costo_aprox;
            } else {
                if (typeof tramo.precio_disponible !== 'undefined' && !tramo.precio_disponible) {
                    costoDisplay = 'Próximamente Disponible';
                } else {
                    let precioStr = typeof tramo.costo_aprox === 'number' ? 
                        `${tramo.costo_aprox.toFixed(1)} USD` : `${tramo.costo_aprox} USD`;
                    let nombreStr = tramo.nombre_servicio ? ` (${tramo.nombre_servicio})` : '';
                    costoDisplay = `${precioStr}${nombreStr}`;
                }
            }
            
            tramosHTML += `
                <div class="flex items-center space-x-2 text-sm text-gray-600 mb-1">
                    <i class="fas ${iconoMedio[tramo.medio_transporte] || 'fa-route'} text-sky-600"></i>
                    <span><strong>${tramo.desde}</strong> → <strong>${tramo.hasta}</strong></span>
                    ${partidaName !== tramo.desde || llegadaName !== tramo.hasta ? 
                        `<span class="text-xs text-gray-500">(${partidaName} → ${llegadaName})</span>` : ''}
                    <span class="text-xs text-gray-700">${tramo.duracion_aprox}, ${costoDisplay}</span>
                </div>
            `;
        });
        
        div.innerHTML = `
            <div class="flex items-start justify-between">
                <div class="flex-1">
                    <div class="flex items-center space-x-2 mb-2">
                        <span class="px-2 py-1 text-xs font-semibold rounded ${tipoColor}">${tipoTexto}</span>
                        <h3 class="font-bold text-gray-900">${rutaConDest}</h3>
                    </div>
                    <p class="text-sm text-gray-600 mb-3">${ruta.descripcion}</p>
                    <div class="space-y-1 mb-3">
                        ${tramosHTML}
                    </div>
                    <div class="flex items-center space-x-4 text-sm">
                        <span class="flex items-center text-gray-700">
                            <i class="fas fa-clock mr-1"></i>
                            <strong>${duracionTotalConDest}</strong>
                        </span>
                        <span class="flex items-center text-green-700 font-semibold">
                            <i class="fas fa-dollar-sign mr-1"></i>
                            <strong>${totalMin.toFixed(1)} - ${totalMax.toFixed(1)}</strong>
                        </span>
                    </div>
                </div>
            </div>
        `;
        
        lista.appendChild(div);
    });

    rutaSeleccionada = null;
}

window.seleccionarRuta = function(index) {
    rutaSeleccionada = rutasDisponibles[index];
    
    var opciones = document.querySelectorAll('.ruta-option');
    opciones.forEach(function(op, i) {
        if (i === index) {
            op.classList.add('selected');
            op.style.borderColor = '#0284c7';
            op.style.backgroundColor = '#eff6ff';
        } else {
            op.classList.remove('selected');
            op.style.borderColor = '#e5e7eb';
            op.style.backgroundColor = '#ffffff';
        }
    });
    
    actualizarRutaMapa();
    mostrarNotificación(`Ruta "${rutaSeleccionada.nombre}" seleccionada`, 'success');
};

// ============================================
// ACTUALIZAR RUTA EN EL MAPA
// ============================================
function actualizarRutaMapa() {
    if (!userLocation || !selectedDestino || !rutaSeleccionada) return;
    
    if (customRouteLines && customRouteLines.length > 0) {
        customRouteLines.forEach(function(line) {
            map.removeLayer(line);
        });
        customRouteLines = [];
    }
    
    if (transferMarkers) {
        transferMarkers.forEach(function(marker) {
            map.removeLayer(marker);
        });
        transferMarkers = [];
    }
    
    var tieneTramoAereo = rutaSeleccionada.tramos.some(function(tramo) {
        return tramo.medio_transporte === 'aereo';
    });
    
    var finalLat = selectedDestino.latitud;
    var finalLng = selectedDestino.longitud;
    
    if (tieneTramoAereo) {
        if (routingControl) {
            map.removeControl(routingControl);
        }
        if (window.fallbackLine) {
            map.removeLayer(window.fallbackLine);
        }
        
        var waypoints = [L.latLng(userLocation.lat, userLocation.lng)];
        var transferPoints = [];
        
        var puntoAnterior = {
            latitud: userLocation.lat,
            longitud: userLocation.lng
        };
        
        rutaSeleccionada.tramos.forEach(function(tramo, tramoIndex) {
            var startPoint = allPoints.find(function(p) { return p.id === tramo.punto_partida; });
            var endPoint = allPoints.find(function(p) { return p.id === tramo.punto_llegada; });
            
            if (startPoint && (Math.abs(puntoAnterior.latitud - startPoint.latitud) > 0.001 || Math.abs(puntoAnterior.longitud - startPoint.longitud) > 0.001)) {
                var lineToStart = L.polyline([
                    [puntoAnterior.latitud, puntoAnterior.longitud],
                    [startPoint.latitud, startPoint.longitud]
                ], {
                    color: '#0284c7',
                    weight: 4,
                    opacity: 0.7
                }).addTo(map);
                
                customRouteLines.push(lineToStart);
                
                waypoints.push(L.latLng(startPoint.latitud, startPoint.longitud));
                transferPoints.push({
                    name: startPoint.nombre,
                    type: 'Salida',
                    lat: startPoint.latitud,
                    lng: startPoint.longitud
                });
                
                puntoAnterior = startPoint;
            }
            
            if (endPoint) {
                var lineStyle = {
                    color: tramo.medio_transporte === 'aereo' ? '#3b82f6' : '#0284c7',
                    weight: 5,
                    opacity: 0.8,
                    zIndex: 1000
                };
                
                if (tramo.medio_transporte === 'aereo') {
                    lineStyle.dashArray = '15, 10';
                    lineStyle.weight = 6;
                }
                
                var line = L.polyline([
                    [puntoAnterior.latitud, puntoAnterior.longitud],
                    [endPoint.latitud, endPoint.longitud]
                ], lineStyle).addTo(map);
                
                customRouteLines.push(line);
                
                waypoints.push(L.latLng(endPoint.latitud, endPoint.longitud));
                transferPoints.push({
                    name: endPoint.nombre,
                    type: 'Llegada',
                    lat: endPoint.latitud,
                    lng: endPoint.longitud
                });
                
                puntoAnterior = endPoint;
            }
        });
        
        if (Math.abs(puntoAnterior.latitud - finalLat) > 0.001 || Math.abs(puntoAnterior.longitud - finalLng) > 0.001) {
            var finalLine = L.polyline([
                [puntoAnterior.latitud, puntoAnterior.longitud],
                [finalLat, finalLng]
            ], {
                color: '#0284c7',
                weight: 4,
                opacity: 0.7
            }).addTo(map);
            
            customRouteLines.push(finalLine);
        }
        
        waypoints.push(L.latLng(finalLat, finalLng));
        
        transferPoints.forEach(function(point) {
            if ((Math.abs(point.lat - userLocation.lat) > 0.001 || Math.abs(point.lng - userLocation.lng) > 0.001) &&
                (Math.abs(point.lat - finalLat) > 0.001 || Math.abs(point.lng - finalLng) > 0.001)) {
                var color = point.type === 'Salida' ? '#f59e0b' : '#10b981';
                var icon = L.divIcon({
                    className: 'transfer-icon',
                    html: `<div style="background: ${color}; border: 2px solid white; border-radius: 50%; width: 16px; height: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.3);"></div>`,
                    iconSize: [16, 16],
                    iconAnchor: [8, 8]
                });
                var marker = L.marker([point.lat, point.lng], {icon: icon}).addTo(map)
                    .bindPopup(`<b>${point.name}</b><br>Trasbordo: ${point.type}`);
                transferMarkers.push(marker);
            }
        });
        
        if (waypoints.length > 1) {
            map.fitBounds(L.latLngBounds(waypoints), {padding: [80, 80]});
        }
        
    } else {
        if (routingControl) {
            map.removeControl(routingControl);
        }
        if (window.fallbackLine) {
            map.removeLayer(window.fallbackLine);
        }
        
        var waypoints = [L.latLng(userLocation.lat, userLocation.lng)];
        var transferPoints = [];
        
        rutaSeleccionada.tramos.forEach(function(tramo) {
            var startPoint = allPoints.find(function(p) { return p.id === tramo.punto_partida; });
            var endPoint = allPoints.find(function(p) { return p.id === tramo.punto_llegada; });
            
            if (startPoint && !waypoints.some(function(w) { 
                return Math.abs(w.lat - startPoint.latitud) < 0.001 && Math.abs(w.lng - startPoint.longitud) < 0.001; 
            })) {
                waypoints.push(L.latLng(startPoint.latitud, startPoint.longitud));
                transferPoints.push({
                    name: startPoint.nombre,
                    type: 'Salida',
                    lat: startPoint.latitud,
                    lng: startPoint.longitud
                });
            }
            
            if (endPoint && !waypoints.some(function(w) { 
                return Math.abs(w.lat - endPoint.latitud) < 0.001 && Math.abs(w.lng - endPoint.longitud) < 0.001; 
            })) {
                waypoints.push(L.latLng(endPoint.latitud, endPoint.longitud));
                transferPoints.push({
                    name: endPoint.nombre,
                    type: 'Llegada',
                    lat: endPoint.latitud,
                    lng: endPoint.longitud
                });
            }
        });
        
        if (!waypoints.some(function(w) { 
            return Math.abs(w.lat - finalLat) < 0.001 && Math.abs(w.lng - finalLng) < 0.001; 
        })) {
            waypoints.push(L.latLng(finalLat, finalLng));
        }
        
        routingControl.setWaypoints(waypoints);
        
        routingControl.on('routesfound', function(e) {
        });
        
        routingControl.addTo(map);
        
        transferPoints.forEach(function(point) {
            if ((Math.abs(point.lat - userLocation.lat) > 0.001 || Math.abs(point.lng - userLocation.lng) > 0.001) &&
                (Math.abs(point.lat - finalLat) > 0.001 || Math.abs(point.lng - finalLng) > 0.001)) {
                var color = point.type === 'Salida' ? '#f59e0b' : '#10b981';
                var icon = L.divIcon({
                    className: 'transfer-icon',
                    html: `<div style="background: ${color}; border: 2px solid white; border-radius: 50%; width: 16px; height: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.3);"></div>`,
                    iconSize: [16, 16],
                    iconAnchor: [8, 8]
                });
                var marker = L.marker([point.lat, point.lng], {icon: icon}).addTo(map)
                    .bindPopup(`<b>${point.name}</b><br>Trasbordo: ${point.type}`);
                transferMarkers.push(marker);
            }
        });
        
        if (waypoints.length > 1) {
            map.fitBounds(L.latLngBounds(waypoints), {padding: [80, 80]});
        }
    }
    
    if (destinoMarker) {
        map.removeLayer(destinoMarker);
    }
    
    var destinoIconHtml;
    if (tieneTramoAereo) {
        destinoIconHtml = '<div style="background: #3b82f6; border: 3px solid white; border-radius: 50%; width: 36px; height: 36px; box-shadow: 0 3px 10px rgba(59,130,246,0.5); display: flex; align-items: center; justify-content: center;"><i class="fas fa-plane" style="color: white; font-size: 18px; transform: rotate(45deg);"></i></div>';
    } else {
        destinoIconHtml = '<div style="background: #dc2626; border: 3px solid white; border-radius: 50%; width: 28px; height: 28px; box-shadow: 0 2px 5px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;"><i class="fas fa-map-marker-alt" style="color: white; font-size: 14px;"></i></div>';
    }
    
    var destinoIcon = L.divIcon({
        className: 'destino-marker-icon',
        html: destinoIconHtml,
        iconSize: tieneTramoAereo ? [36, 36] : [28, 28],
        iconAnchor: tieneTramoAereo ? [18, 18] : [14, 28]
    });
    
    destinoMarker = L.marker([finalLat, finalLng], {icon: destinoIcon})
        .addTo(map)
        .bindPopup(`<b>${selectedDestino.nombre}</b><br>${selectedDestino.region_display}<br>
            ${tieneTramoAereo ? '<i class="fas fa-plane mr-1"></i>Ruta con vuelo' : '<i class="fas fa-bus mr-1"></i>Ruta terrestre'}`);
    
    setTimeout(function() {
        map.invalidateSize(true);
    }, 300);
}

// ============================================
// FUNCIONES DE UI
// ============================================
function mostrarNotificación(mensaje, tipo) {
    var colores = {
        'success': 'bg-green-500',
        'info': 'bg-blue-500',
        'warning': 'bg-yellow-500',
        'error': 'bg-red-500'
    };
    
    var notificación = document.createElement('div');
    notificación.className = `fixed top-20 right-4 ${colores[tipo] || 'bg-blue-500'} text-white px-6 py-3 rounded-lg shadow-lg z-50 animate-slide-in`;
    notificación.innerHTML = `
        <div class="flex items-center space-x-2">
            <i class="fas fa-info-circle"></i>
            <span>${mensaje}</span>
        </div>
    `;
    
    document.body.appendChild(notificación);
    
    setTimeout(function() {
        notificación.style.opacity = '0';
        notificación.style.transition = 'opacity 0.3s';
        setTimeout(function() {
            document.body.removeChild(notificación);
        }, 300);
    }, 3000);
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
        div.className = `destino-item p-3 rounded-lg border ${isSelected ? 'selected border-sky-300 dark:border-sky-500 dark:bg-gray-800/60' : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/40 hover:dark:bg-gray-800/60'}`;
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

window.recargarMapa = function() {
    map.invalidateSize(true);
    setTimeout(function() {
        map.invalidateSize(true);
    }, 100);
    mostrarNotificación('Mapa recargado', 'success');
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
        map.invalidateSize(true);
    });

    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            setTimeout(function() {
                map.invalidateSize(true);
            }, 100);
        }
    });
});