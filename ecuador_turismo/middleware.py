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
        self.get_response = get_response
        # Generar clave de encriptación
        key = settings.URL_ENCRYPTION_KEY.encode()
        key = base64.urlsafe_b64encode(key[:32].ljust(32, b'0'))
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
            except Exception as e:
                logger.warning(f"Intento de acceso con URL inválida: {path}")
                return HttpResponseForbidden("URL inválida")
        
        return None
    
    def encrypt_url(self, url):
        """Encriptar URL"""
        try:
            encrypted = self.cipher.encrypt(url.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception:
            return url
    
    def decrypt_url(self, encrypted_url):
        """Desencriptar URL"""
        try:
            decoded = base64.urlsafe_b64decode(encrypted_url.encode())
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception:
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
                logger.warning(f"Rate limit excedido para IP: {ip}")
                return HttpResponseForbidden("Rate limit excedido. Intente nuevamente en un minuto.")

            # Incrementar contador
            cache.set(cache_key, current_requests + 1, 60)
        except Exception as e:
            # Si Redis no está disponible, continuar sin rate limiting
            logger.warning(f"Rate limiting deshabilitado: {e}")
            pass

        return None

    def get_client_ip(self, request):
        """Obtener IP real del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class AuditMiddleware(MiddlewareMixin):
    """Middleware para auditoría de seguridad"""
    
    def process_request(self, request):
        """Registrar requests sensibles"""
        sensitive_paths = ['/admin/', '/api/', '/usuarios/', '/reservas/']
        
        if any(request.path.startswith(path) for path in sensitive_paths):
            logger.info(
                f"Acceso a ruta sensible: {request.path} "
                f"IP: {self.get_client_ip(request)} "
                f"User: {getattr(request.user, 'username', 'Anonymous')} "
                f"Method: {request.method}"
            )
        
        return None
    
    def get_client_ip(self, request):
        """Obtener IP del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ConnectionHandlingMiddleware(MiddlewareMixin):
    """Middleware para manejar conexiones rotas"""
    
    def process_exception(self, request, exception):
        if isinstance(exception, (ConnectionError, TimeoutError)):
            logger.warning(f"Conexión perdida: {request.path}")
            return HttpResponseServerError("Error de conexión")
