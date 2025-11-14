"""
Middleware de seguridad personalizado para Ecuador Turismo
"""

import hashlib
import hmac
import time
from urllib.parse import quote, unquote
from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseServerError
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from cryptography.fernet import Fernet
import base64
import logging

logger = logging.getLogger('django.security')


class URLEncryptionMiddleware(MiddlewareMixin):
    """Middleware para encriptar URLs sensibles"""

    def __init__(self, get_response):
        super().__init__(get_response)
        # Validar y generar clave de encriptación
        encryption_key = getattr(settings, 'URL_ENCRYPTION_KEY', None)
        if not encryption_key or len(encryption_key) < 32:
            raise ValueError("URL_ENCRYPTION_KEY debe tener al menos 32 caracteres")
        
        # Usar PBKDF2 para derivación segura de clave
        import os
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        
        salt = b'ecuador_turismo_salt'  # En producción usar salt aleatorio
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
        self.cipher = Fernet(key)

        # URLs que requieren encriptación
        self.sensitive_urls = [
            '/admin/',
            '/api/',
            '/usuarios/perfil/',
            '/reservas/',
            '/pagos/',
        ]
    
    def process_request(self, request):
        """Procesar request entrante"""
        path = request.path
        
        # Verificar si es una URL encriptada
        if path.startswith('/secure/'):
            try:
                encrypted_path = path.replace('/secure/', '')
                decrypted_path = self.decrypt_url(encrypted_path)
                request.path_info = decrypted_path
                request.path = decrypted_path
            except Exception:
                logger.warning("Intento de acceso con URL inválida")
                return HttpResponseForbidden("URL inválida")
        
        return None
    
    def encrypt_url(self, url):
        """Encriptar URL"""
        try:
            encrypted = self.cipher.encrypt(url.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error("Error en encriptación de URL")
            return url
    
    def decrypt_url(self, encrypted_url):
        """Desencriptar URL"""
        try:
            decoded = base64.urlsafe_b64decode(encrypted_url.encode())
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error("Error en desencriptación de URL")
            raise ValueError("URL no válida")


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Middleware para headers de seguridad adicionales"""
    
    def process_response(self, request, response):
        """Agregar headers de seguridad"""

        # Prevenir clickjacking
        response['X-Frame-Options'] = 'DENY'

        # Prevenir MIME sniffing
        response['X-Content-Type-Options'] = 'nosniff'

        # XSS Protection
        response['X-XSS-Protection'] = '1; mode=block'

        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Feature Policy
        response['Permissions-Policy'] = (
            'accelerometer=(), camera=(), geolocation=(self), '
            'microphone=(), payment=()'
        )

        return response


class RateLimitMiddleware(MiddlewareMixin):
    """Middleware para rate limiting"""

    def process_request(self, request):
        """Limitar requests por IP"""
        if not getattr(settings, 'RATELIMIT_ENABLE', True):
            return None

        try:
            ip = self.get_client_ip(request)
            cache_key = f"rate_limit_{ip}"

            # Obtener contador actual
            current_requests = cache.get(cache_key, 0)

            # Límite: 100 requests por minuto
            if current_requests >= 100:
                logger.warning("Rate limit excedido")
                return HttpResponseForbidden("Rate limit excedido. Intente nuevamente en un minuto.")

            # Incrementar contador
            cache.set(cache_key, current_requests + 1, 60)
        except Exception:
            # Si Redis no está disponible, continuar sin rate limiting
            logger.warning("Rate limiting deshabilitado")
            pass

        return None

    def get_client_ip(self, request):
        """Obtener IP real del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
            # Sanitizar IP
            import re
            if re.match(r'^[0-9.:]+$', ip):
                return ip
        return request.META.get('REMOTE_ADDR', '127.0.0.1')


class AuditMiddleware(MiddlewareMixin):
    """Middleware para auditoría de seguridad"""
    
    def process_request(self, request):
        """Registrar requests sensibles"""
        sensitive_paths = ['/admin/', '/api/', '/usuarios/', '/reservas/']
        
        if any(request.path.startswith(path) for path in sensitive_paths):
            logger.info(
                "Acceso a ruta sensible - "
                f"Method: {request.method} "
                f"User: {getattr(request.user, 'id', 'Anonymous')}"
            )
        
        return None
    
    def get_client_ip(self, request):
        """Obtener IP del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
            # Sanitizar IP
            import re
            if re.match(r'^[0-9.:]+$', ip):
                return ip
        return request.META.get('REMOTE_ADDR', '127.0.0.1')


class InputSanitizationMiddleware(MiddlewareMixin):
    """Middleware para sanitizar todas las entradas del usuario"""
    
    def process_request(self, request):
        """Sanitizar datos de entrada"""
        from ecuador_turismo.sanitizers import InputSanitizer
        
        # Sanitizar POST data
        if request.method == 'POST' and hasattr(request, 'POST'):
            sanitized_post = {}
            for key, value in request.POST.items():
                try:
                    if key in ['email', 'correo']:
                        sanitized_post[key] = InputSanitizer.sanitize_email(value)
                    elif key in ['telefono', 'phone']:
                        sanitized_post[key] = InputSanitizer.sanitize_phone(value)
                    elif key in ['url', 'website', 'sitio_web']:
                        sanitized_post[key] = InputSanitizer.sanitize_url(value)
                    else:
                        sanitized_post[key] = InputSanitizer.sanitize_text(value)
                except Exception as e:
                    logger.warning(f"Entrada rechazada en campo {key}")
                    return HttpResponseForbidden("Datos no válidos")
            
            # Reemplazar POST data
            request.POST = request.POST.copy()
            for key, value in sanitized_post.items():
                request.POST[key] = value
        
        # Sanitizar GET parameters
        if hasattr(request, 'GET'):
            sanitized_get = {}
            for key, value in request.GET.items():
                try:
                    sanitized_get[key] = InputSanitizer.sanitize_text(value)
                except Exception:
                    logger.warning(f"Parámetro GET rechazado: {key}")
                    return HttpResponseForbidden("Parámetros no válidos")
        
        return None


class URLValidationMiddleware(MiddlewareMixin):
    """Middleware para validar rutas y prevenir manipulación de URLs"""
    
    def __init__(self, get_response):
        super().__init__(get_response)
        # Rutas válidas permitidas
        self.valid_patterns = [
            r'^/$',  # Home
            r'^/destinos/$',
            r'^/destinos/\d+/$',
            r'^/servicios/$',
            r'^/servicios/\d+/$',
            r'^/usuarios/login/$',
            r'^/usuarios/registro/$',
            r'^/usuarios/perfil/$',
            r'^/reservas/$',
            r'^/reservas/\d+/$',
            r'^/chatbot/$',
            r'^/admin/',
            r'^/static/',
            r'^/media/',
        ]
        
        # Patrones sospechosos
        self.suspicious_patterns = [
            r'\.\./',  # Path traversal
            r'%2e%2e',  # Encoded path traversal
            r'<script',  # XSS
            r'javascript:',  # XSS
            r'union.*select',  # SQL injection
            r'drop.*table',  # SQL injection
            r'exec.*\(',  # Command injection (escapar paréntesis)
        ]
    
    def process_request(self, request):
        """Validar la URL del request"""
        path = request.path.lower()
        
        # Verificar patrones sospechosos
        import re
        for pattern in self.suspicious_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                logger.warning("Patrón sospechoso detectado en URL")
                return HttpResponseForbidden("Acceso denegado")
        
        # Verificar si la ruta es válida
        is_valid = False
        for pattern in self.valid_patterns:
            if re.match(pattern, request.path):
                is_valid = True
                break
        
        if not is_valid:
            logger.warning("Intento de acceso a ruta no válida")
            return HttpResponseForbidden("Ruta no encontrada")
        
        return None


class ConnectionHandlingMiddleware(MiddlewareMixin):
    """Middleware para manejar conexiones rotas"""
    
    def process_exception(self, request, exception):
        if isinstance(exception, (ConnectionError, TimeoutError)):
            logger.warning("Conexión perdida")
            return HttpResponseServerError("Error de conexión")
