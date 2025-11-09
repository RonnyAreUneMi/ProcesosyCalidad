# Plataforma Inteligente de Turismo - Ecuador

Este proyecto es una aplicación web robusta y escalable desarrollada con Django, diseñada para ser el portal central de turismo en Ecuador. La plataforma conecta a turistas con proveedores de servicios, ofrece guías de destinos detalladas y cuenta con un asistente de IA conversacional para una experiencia de usuario interactiva.

## 📋 Tabla de Contenidos
1.  [Funcionalidades Clave](#-funcionalidades-clave)
2.  [Arquitectura y Tecnologías](#-arquitectura-y-tecnologías)
3.  [Instalación y Configuración](#-instalación-y-configuración)
4.  [Estructura del Proyecto](#-estructura-del-proyecto)
5.  [Análisis de Componentes Clave](#-análisis-de-componentes-clave)
6.  [Ejecución de la Aplicación](#-ejecución-de-la-aplicación)

---

## ✨ Funcionalidades Clave

*   **Gestión de Usuarios por Roles**: Sistema de autenticación con tres roles definidos:
    *   **Turista**: Puede buscar servicios, hacer reservas, gestionar su carrito y calificar servicios.
    *   **Proveedor**: Puede gestionar sus propios servicios (hoteles, tours, etc.), ver y administrar las reservas recibidas.
    *   **Administrador**: Tiene acceso total al sistema, incluyendo gestión de usuarios, roles, servicios, destinos y visualización de estadísticas.

*   **Módulo de Servicios y Destinos**:
    *   CRUD completo para servicios y destinos turísticos.
    *   Búsqueda avanzada con filtros por región, tipo, precio y palabras clave.
    *   Mapas interactivos (Leaflet.js) para visualización y selección de ubicaciones.

*   **Asistente de IA (Chatbot)**:
    *   Integración con modelos de lenguaje grandes (LLM) como GPT-4 (OpenAI) y Llama 3 (Groq).
    *   Capacidad de "Function Calling" para interactuar en tiempo real con la base de datos de la aplicación (buscar servicios, destinos, etc.).
    *   Procesamiento de lenguaje natural para corregir errores ortográficos y entender el contexto de la conversación.
    *   *Prompt Engineering* avanzado para guiar el comportamiento del modelo y asegurar respuestas precisas y seguras.

*   **Sistema de Reservas y Carrito de Compras**:
    *   Los turistas pueden agregar múltiples servicios a un carrito.
    *   Flujo de reserva completo, desde la selección hasta la confirmación.
    *   Los proveedores pueden confirmar o completar las reservas, lo que habilita la calificación por parte del turista.
    *   Uso de transacciones atómicas (`transaction.atomic`) para garantizar la integridad de los datos.

*   **Seguridad y Rendimiento**:
    *   Decoradores personalizados para control de acceso basado en roles.
    *   Protección contra ataques CSRF.
    *   Limitación de peticiones (Rate Limiting) para prevenir spam y abuso.
    *   Uso de caché de Django (con Redis) para mejorar el rendimiento en consultas frecuentes y estadísticas.

*   **Planificador de Rutas**:
    *   Herramienta interactiva para que los usuarios planifiquen rutas de viaje entre diferentes destinos de Ecuador.

---

## 🏗️ Arquitectura y Tecnologías

El proyecto sigue una arquitectura modular basada en aplicaciones de Django, lo que facilita la mantenibilidad y escalabilidad.

*   **Backend**:
    *   **Framework**: Django
    *   **Lenguaje**: Python
    *   **Base de Datos**: PostgreSQL (recomendado)
    *   **Caché**: Redis
    *   **IA / LLM**: Integración con API de OpenAI y Groq.

*   **Frontend**:
    *   **Motor de Plantillas**: Django Templates.
    *   **JavaScript**: JavaScript moderno (ES6+) organizado en módulos.
    *   **Estilos**: Tailwind CSS.
    *   **Librerías**: SweetAlert2 (notificaciones), Leaflet.js (mapas), Alpine.js (interactividad).

*   **Almacenamiento de Archivos**:
    *   Un backend de almacenamiento personalizado (`SupabaseStorage`) para gestionar la subida de archivos a Supabase Storage, desacoplando los medios del servidor de la aplicación.

---

## 🚀 Instalación y Configuración

Sigue estos pasos para configurar el entorno de desarrollo local.

### 1. Prerrequisitos
*   Python 3.9+
*   Pip (gestor de paquetes de Python)
*   Git
*   Una base de datos PostgreSQL
*   Un servidor Redis

### 2. Clonar el Repositorio
```bash
git clone <URL_DEL_REPOSITORIO>
cd <NOMBRE_DEL_PROYECTO>
```

### 3. Configurar Entorno Virtual
Es una buena práctica aislar las dependencias del proyecto.
```bash
# Crear entorno virtual
python -m venv venv

# Activar en Windows
venv\Scripts\activate

# Activar en macOS/Linux
source venv/bin/activate
```

### 4. Instalar Dependencias
Instala todas las dependencias listadas en `requirements.txt`.
```bash
pip install -r requirements.txt
```

### 5. Configurar Variables de Entorno
Crea un archivo `.env` en la raíz del proyecto. Usa el siguiente template como guía.

**`.env`**:
```ini
# Django Settings
SECRET_KEY='tu-django-secret-key-aqui'
DEBUG=True

# Database (Ejemplo para PostgreSQL)
DATABASE_URL='postgres://user:password@host:port/dbname'

# Redis Cache
REDIS_URL='redis://localhost:6379/1'

# Supabase Storage (para subida de imágenes)
SUPABASE_URL='https://tu-proyecto.supabase.co'
SUPABASE_ANON_KEY='tu-supabase-anon-key'
SUPABASE_BUCKET_NAME='nombre-del-bucket'

# LLM APIs (elige una o ambas)
OPENAI_API_KEY='tu-openai-api-key'
GROQ_API_KEY='tu-groq-api-key'
```

### 6. Migraciones de la Base de Datos
Aplica las migraciones para crear las tablas en la base de datos.
```bash
python manage.py migrate
```

### 7. Crear un Superusuario
Este usuario tendrá rol de Administrador y acceso al panel de Django.
```bash
python manage.py createsuperuser
```
Sigue las instrucciones en la terminal para crear tu cuenta de administrador.

---

## 📁 Estructura del Proyecto

El código está organizado en aplicaciones de Django, cada una con una responsabilidad clara.

```
.
├── apps/
│   ├── chatbot/        # Lógica del asistente de IA y function calling.
│   ├── destinos/       # Modelos, vistas y lógica para destinos turísticos.
│   ├── reservas/       # Gestión del carrito de compras y reservas.
│   ├── rutas/          # Lógica para el planificador de rutas.
│   ├── servicios/      # Gestión de servicios (hoteles, tours, etc.).
│   └── usuarios/       # Modelos de usuario, roles, autenticación y decoradores.
├── static/
│   ├── css/
│   └── js/             # Scripts JS modulares para el frontend.
├── storages/
│   └── supabase_storage.py # Backend de almacenamiento para Supabase.
├── templates/          # Plantillas HTML globales y de base.
├── manage.py           # Script de gestión de Django.
└── README.md           # Este archivo.
```

---

## 🔬 Análisis de Componentes Clave

### `apps/chatbot/views.py`
Este es el cerebro del asistente de IA.
*   **`TextProcessor`**: Una clase de utilidad para normalizar texto, corregir errores ortográficos comunes y extraer palabras clave.
*   **`SYSTEM_PROMPT`**: Un prompt de sistema muy detallado que define la personalidad, capacidades, reglas y prohibiciones del chatbot. Es fundamental para guiar al LLM.
*   **`ejecutar_funcion`**: Un despachador que invoca las vistas AJAX de la aplicación (ej. `buscar_servicios_ajax`) utilizando `RequestFactory`. Esto evita duplicar la lógica de negocio y mantiene el código DRY.
*   **`chatbot_message`**: La vista principal que orquesta el flujo: recibe el mensaje, llama al LLM, ejecuta las funciones que el modelo decide, y genera una respuesta final basada en los datos obtenidos.

### `apps/usuarios/decorators.py`
Centraliza la lógica de autorización y seguridad.
*   **`rol_requerido` / `rol_requerido_ajax`**: Decoradores flexibles para restringir el acceso a vistas según el rol del usuario, con soporte para respuestas HTML y JSON.
*   **`limite_peticiones`**: Un decorador crucial para la seguridad que implementa *rate limiting* por usuario o IP, previniendo ataques de fuerza bruta o spam en endpoints sensibles como el chatbot.

### `static/js/servicios/servicio-form.js`
Un ejemplo de JavaScript modular y robusto.
*   **Organización**: El código está dividido en objetos (`ValidadorCoordenadas`, `GestorImagenes`) con responsabilidades únicas.
*   **UX**: Utiliza `SweetAlert2` para ofrecer feedback visual claro y profesional al usuario, mejorando la experiencia en la validación de formularios.
*   **Robustez**: Incluye validaciones del lado del cliente para imágenes (tamaño, formato) y coordenadas geográficas, reduciendo la carga en el servidor.

---

## ▶️ Ejecución de la Aplicación

Una vez completada la configuración, inicia el servidor de desarrollo de Django.

```bash
python manage.py runserver
```

La aplicación estará disponible en `http://127.0.0.1:8000/`.