# 🛡️ Documentación de Seguridad - Ecuador Turismo

## 🔒 Middlewares de Seguridad Implementados

### 1. **InputSanitizationMiddleware**
- **Función**: Sanitiza automáticamente todas las entradas del usuario
- **Protege contra**: XSS, SQL Injection, Command Injection
- **Ubicación**: `ecuador_turismo/middleware.py`

### 2. **URLValidationMiddleware** 
- **Función**: Valida rutas y previene manipulación de URLs
- **Protege contra**: Path Traversal, acceso no autorizado
- **Rutas permitidas**: `/destinos/`, `/servicios/`, `/usuarios/`, etc.

### 3. **RateLimitMiddleware**
- **Función**: Limita requests por IP (100/minuto)
- **Protege contra**: Ataques de fuerza bruta, DDoS
- **Configuración**: `RATELIMIT_ENABLE = True`

### 4. **SecurityHeadersMiddleware**
- **Función**: Agrega headers de seguridad HTTP
- **Headers**: X-Frame-Options, X-XSS-Protection, CSP, etc.

### 5. **URLEncryptionMiddleware**
- **Función**: Encripta URLs sensibles con PBKDF2
- **Protege**: Rutas administrativas y sensibles
- **Configuración**: `URL_ENCRYPTION_KEY` en settings

### 6. **AuditMiddleware**
- **Función**: Registra accesos a rutas sensibles
- **Logs**: `logs/security_alerts.log`

## 🔐 Sanitizadores de Entrada

### InputSanitizer Class
```python
# Métodos disponibles:
InputSanitizer.sanitize_text(text)      # Texto general
InputSanitizer.sanitize_email(email)    # Emails
InputSanitizer.sanitize_phone(phone)    # Teléfonos
InputSanitizer.sanitize_url(url)        # URLs
InputSanitizer.sanitize_filename(file)  # Archivos
```

### Patrones Detectados
- `<script>` - XSS Scripts
- `javascript:` - JavaScript URLs
- `union select` - SQL Injection
- `../` - Path Traversal
- `exec()` - Command Injection

## 📝 Configuración de Seguridad

### Variables de Entorno Requeridas (.env)
```bash
# Seguridad
SECRET_KEY=tu-django-secret-key-muy-largo
URL_ENCRYPTION_KEY=clave-de-32-caracteres-minimo
RATELIMIT_ENABLE=True

# Base de datos
DB_NAME=ecuador_turismo
DB_USER=usuario
DB_PASSWORD=password-seguro
DB_HOST=localhost
DB_PORT=5432
```

### Settings de Seguridad Activados
- CSRF Protection
- Session Security
- HTTPS Redirect (producción)
- HSTS Headers
- Content Security Policy
- Permissions Policy

## 🚨 Logs de Seguridad

### Ubicación de Logs
- **General**: `logs/security.log`
- **Alertas**: `logs/security_alerts.log`

### Eventos Registrados
- Intentos de acceso malicioso
- Patrones peligrosos detectados
- Rate limiting activado
- URLs inválidas
- Errores de encriptación

## ⚠️ Archivos Protegidos (.gitignore)

### Nunca Subir a GitHub:
- `.env` - Variables de entorno
- `*.log` - Logs de seguridad
- `*.key` - Claves privadas
- `/media/` - Archivos subidos por usuarios
- `db.sqlite3` - Base de datos local
- Scripts de prueba de seguridad

## 🧪 Testing de Seguridad

### Comandos de Prueba (Solo Desarrollo)
```bash
# NO incluir estos archivos en producción
python attack_test.py           # Ataques básicos
python test_url_validation.py   # Validación URLs
python test_input_sanitization.py # Sanitización
```

## 🔧 Mantenimiento

### Revisar Regularmente:
1. **Logs de seguridad** - Buscar patrones de ataque
2. **Rate limiting** - Ajustar límites según tráfico
3. **Patrones maliciosos** - Actualizar detectores
4. **Certificados SSL** - Renovar antes del vencimiento

### Actualizaciones de Seguridad:
- Django y dependencias
- Patrones de sanitización
- Headers de seguridad
- Configuraciones CSP

## 📞 Contacto de Seguridad

En caso de vulnerabilidades encontradas:
1. No reportar públicamente
2. Contactar al equipo de desarrollo
3. Proporcionar detalles técnicos
4. Esperar confirmación antes de divulgar

---

**⚠️ IMPORTANTE**: Esta documentación contiene información sensible sobre la seguridad del sistema. Mantener confidencial y actualizar regularmente.