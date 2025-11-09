"""
Django settings for ecuador_turismo project.
"""

from pathlib import Path
from decouple import config
import os
import secrets

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================
# 🔒 SECURITY CONFIGURATION
# ============================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default=secrets.token_urlsafe(50))

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Apps del proyecto
    'apps.usuarios',
    'apps.destinos',
    'apps.servicios',
    'apps.rutas',
    'apps.reservas',
    'apps.calificaciones',
    'apps.chatbot',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'ecuador_turismo.middleware.SecurityHeadersMiddleware',
    'ecuador_turismo.middleware.URLEncryptionMiddleware',
    'ecuador_turismo.middleware.ConnectionHandlingMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ecuador_turismo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
            ],
        },
    },
]

WSGI_APPLICATION = 'ecuador_turismo.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# ============================================
# 🗄️ DATABASE ACID COMPLIANCE
# ============================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
        'OPTIONS': {
            'sslmode': 'require',
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000',
        },
        'CONN_MAX_AGE': 300,
        'CONN_HEALTH_CHECKS': True,
        'ATOMIC_REQUESTS': True,  # Garantiza transacciones ACID
    }
}

# Database Connection Pooling para ACID
DATABASE_POOL_ARGS = {
    'max_overflow': 10,
    'pool_pre_ping': True,
    'pool_recycle': 300,
}


# ============================================
# ✅ OPENAI CONFIGURATION (GPT-4)
# ============================================
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')

# ============================================
# ✅ GROQ CONFIGURATION (Alternativa GRATIS)
# ============================================
GROQ_API_KEY = config('GROQ_API_KEY', default='')

# Validar que al menos una key esté configurada
if not GROQ_API_KEY and not OPENAI_API_KEY and DEBUG:
    import warnings
    warnings.warn(
        "⚠️  Ni GROQ_API_KEY ni OPENAI_API_KEY están configuradas. El chatbot no funcionará.\n"
        "   Agrega tu API key en el archivo .env:\n"
        "   GROQ_API_KEY=gsk_... (GRATIS) o\n"
        "   OPENAI_API_KEY=sk-proj-...",
        RuntimeWarning
    )

# Configuración opcional de modelo (puedes cambiarlo aquí)
OPENAI_MODEL = config('OPENAI_MODEL', default='gpt-4-turbo-preview')
GROQ_MODEL = config('GROQ_MODEL', default='llama-3.3-70b-versatile')
# Opciones: 'gpt-4-turbo-preview', 'gpt-4o', 'gpt-4', 'gpt-3.5-turbo'

# ============================================
# ✅ GROQ CONFIGURATION (Alternativa a OpenAI)
# ============================================
GROQ_API_KEY = config('GROQ_API_KEY', default='')

# ============================================


# Supabase Configuration
SUPABASE_URL = config('SUPABASE_URL')
SUPABASE_ANON_KEY = config('SUPABASE_ANON_KEY')
SUPABASE_BUCKET_NAME = config('SUPABASE_BUCKET_NAME')
STORAGES = {
    "default": {
        "BACKEND": "storages.supabase_storage.SupabaseStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Custom User Model
# RF-001: Modelo de usuario personalizado
AUTH_USER_MODEL = 'usuarios.Usuario'


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

# ============================================
# 🔐 PASSWORD SECURITY
# ============================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12},  # Aumentado a 12 caracteres
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'es-ec'

TIME_ZONE = 'America/Guayaquil'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Authentication settings
LOGIN_URL = 'usuarios:login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'


# ============================================
# 🔒 SECURITY ENHANCEMENTS
# ============================================

# URL Encryption Key (para encriptar URLs sensibles)
URL_ENCRYPTION_KEY = config('URL_ENCRYPTION_KEY', default=secrets.token_urlsafe(32))

# Rate Limiting
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

# CSRF Protection
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False  # Permitir acceso desde JavaScript para AJAX
CSRF_COOKIE_SAMESITE = 'Lax'  # Cambiar a Lax para permitir AJAX
CSRF_USE_SESSIONS = False  # Usar cookies en lugar de sesiones
CSRF_COOKIE_AGE = 3600  # 1 hora
CSRF_COOKIE_NAME = 'csrftoken'
CSRF_HEADER_NAME = 'HTTP_X_CSRFTOKEN'

# Session Security
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_AGE = 3600  # 1 hora para mayor seguridad
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# SSL/HTTPS Security
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# Content Security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

# Frame Protection
X_FRAME_OPTIONS = 'DENY'

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")

# Permissions Policy
PERMISSIONS_POLICY = {
    "accelerometer": [],
    "camera": [],
    "geolocation": ["self"],
    "microphone": [],
    "payment": [],
}

# ============================================
# 🔐 CACHE SECURITY (Redis)
# ============================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 60,  # 1 minuto de caché
    }
}

# Cache para sesiones (ACID compliance)
SESSION_CACHE_ALIAS = 'default'

# Cache middleware settings
CACHE_MIDDLEWARE_SECONDS = 60  # 1 minuto de caché
CACHE_MIDDLEWARE_KEY_PREFIX = 'ecuador_turismo'
CACHE_MIDDLEWARE_ANONYMOUS_ONLY = True

# Connection handling settings
CONN_MAX_AGE = None  # Conexiones persistentes sin límite de tiempo
ATOMIC_REQUESTS = False  # Desactivar transacciones atómicas globales

# ============================================
# 📝 LOGGING SECURITY
# ============================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security_alerts.log',
            'maxBytes': 1024*1024*15,
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django.security': {
            'handlers': ['security_file', 'console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['file', 'console'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}


# Messages framework
from django.contrib.messages import constants as messages

MESSAGE_TAGS = {
    messages.DEBUG: 'debug',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'error',
}