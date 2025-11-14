# Estructura de JavaScript - Proyecto Procesos y Calidad de Software

## 📁 Organización de Archivos

### `/core/` - Núcleo del Sistema
- **`mapbox-config.js`** - Configuración centralizada de Mapbox GL JS
- **`utils.js`** - Utilidades comunes reutilizables

### `/mapas/` - Funcionalidades de Mapas
- **`ecuador-mapbox.js`** - Clase principal para mapas de Ecuador con Mapbox 3D
- **`map-controls.js`** - Controles UI para mapas (filtros, botones 3D)

### `/rutas/` - Sistema de Rutas
- **`planificador-rutas.js`** - Planificador de rutas con Mapbox 3D y Directions API

### `/servicios/` - Gestión de Servicios
- **`servicio-form.js`** - Formularios de servicios turísticos

### `/chatbot/` - Asistente Virtual
- **`chatbot-core.js`** - Funcionalidad principal del chatbot con IA
- **`chatbot-utils.js`** - Utilidades y funciones auxiliares

## 🔧 Dependencias

### Orden de Carga Recomendado:
1. `core/mapbox-config.js` (configuración global)
2. `core/utils.js` (utilidades)
3. Archivos específicos según funcionalidad

### APIs Externas:
- **Mapbox GL JS v3.0.1** - Mapas 3D y routing
- **FontAwesome** - Iconografía

## 📋 Estándares de Calidad

### Principios Aplicados:
- **DRY (Don't Repeat Yourself)** - Código reutilizable en `/core/`
- **Separación de Responsabilidades** - Cada carpeta tiene una función específica
- **Configuración Centralizada** - Un solo punto de configuración para Mapbox
- **Modularidad** - Archivos independientes y reutilizables

### Buenas Prácticas:
- Nombres descriptivos de archivos y funciones
- Comentarios JSDoc para funciones principales
- Manejo de errores consistente
- Código limpio y mantenible

## 🚀 Uso

```html
<!-- Carga básica para mapas -->
<script src="{% static 'js/core/mapbox-config.js' %}"></script>
<script src="{% static 'js/core/utils.js' %}"></script>
<script src="{% static 'js/mapas/ecuador-mapbox.js' %}"></script>

<!-- Para rutas -->
<script src="{% static 'js/rutas/planificador-rutas.js' %}"></script>

<!-- Para chatbot (ya incluido en base.html) -->
<script src="{% static 'js/chatbot/chatbot-utils.js' %}"></script>
<script src="{% static 'js/chatbot/chatbot-core.js' %}"></script>
```