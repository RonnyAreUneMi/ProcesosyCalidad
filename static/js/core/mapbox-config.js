/**
 * Configuración global de Mapbox para el proyecto
 */
window.MapboxConfig = {
    accessToken: 'pk.eyJ1IjoiaW5ncG9sbGl0byIsImEiOiJjbWh4cmVwcHYwNDF2MnJvcGc5N3VocDliIn0.FDbD09-VTzE7H-HAfee0yg',
    styles: {
        streets: 'mapbox://styles/mapbox/streets-v12',
        outdoors: 'mapbox://styles/mapbox/outdoors-v12',
        satellite: 'mapbox://styles/mapbox/satellite-v9'
    },
    ecuador: {
        center: [-78.1834, -1.8312],
        zoom: 6,
        bounds: [[-92, -5], [-75, 2]]
    }
};

// Configurar token globalmente
if (typeof mapboxgl !== 'undefined') {
    mapboxgl.accessToken = window.MapboxConfig.accessToken;
}