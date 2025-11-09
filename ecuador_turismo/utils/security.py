"""
Utilidades de seguridad para Ecuador Turismo
"""

import hashlib
import hmac
import secrets
from django.conf import settings
from django.urls import reverse
from cryptography.fernet import Fernet
import base64
import logging

logger = logging.getLogger('django.security')


class URLSecurity:
    """Clase para manejar seguridad de URLs"""
    
    @staticmethod
    def encrypt_url(url):
        """Encriptar URL sensible"""
        try:
            key = settings.URL_ENCRYPTION_KEY.encode()
            key = base64.urlsafe_b64encode(key[:32].ljust(32, b'0'))
            cipher = Fernet(key)
            
            encrypted = cipher.encrypt(url.encode())
            return f"/secure/{base64.urlsafe_b64encode(encrypted).decode()}"
        except Exception as e:
            logger.error(f"Error al encriptar URL: {str(e)}")
            return url
    
    @staticmethod
    def generate_secure_token():
        """Generar token seguro"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def verify_csrf_token(request, token):
        """Verificar token CSRF personalizado"""
        try:
            expected = hmac.new(
                settings.SECRET_KEY.encode(),
                request.session.session_key.encode(),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, token)
        except Exception as e:
            logger.warning(f"Error al verificar token CSRF: {str(e)}")
            return False
    
    @staticmethod
    def generate_signed_url(url, expiry_seconds=3600):
        """Generar URL firmada con expiración"""
        import time
        timestamp = int(time.time()) + expiry_seconds
        message = f"{url}:{timestamp}"
        signature = hmac.new(
            settings.SECRET_KEY.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"{url}?signature={signature}&expires={timestamp}"
    
    @staticmethod
    def verify_signed_url(url, signature, expires):
        """Verificar URL firmada"""
        import time
        try:
            # Verificar expiración
            if int(expires) < int(time.time()):
                logger.warning("URL firmada expirada")
                return False
            
            # Verificar firma
            message = f"{url}:{expires}"
            expected = hmac.new(
                settings.SECRET_KEY.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected, signature)
        except Exception as e:
            logger.error(f"Error al verificar URL firmada: {str(e)}")
            return False


class DatabaseSecurity:
    """Utilidades para seguridad de base de datos (ACID)"""
    
    @staticmethod
    def execute_atomic_transaction(operations):
        """
        Ejecutar operaciones en transacción ACID
        
        Args:
            operations: Lista de funciones a ejecutar
            
        Returns:
            Lista de resultados de cada operación
            
        Raises:
            Exception: Si alguna operación falla
        """
        from django.db import transaction
        
        try:
            with transaction.atomic():
                results = []
                for operation in operations:
                    result = operation()
                    results.append(result)
                logger.info(f"Transacción ACID completada exitosamente: {len(operations)} operaciones")
                return results
        except Exception as e:
            logger.error(f"Error en transacción ACID: {str(e)}")
            raise
    
    @staticmethod
    def validate_input(data, allowed_fields):
        """
        Validar y sanitizar entrada de datos
        
        Args:
            data: Diccionario con datos a validar
            allowed_fields: Lista de campos permitidos
            
        Returns:
            Diccionario con datos sanitizados
        """
        cleaned_data = {}
        dangerous_patterns = [
            '<script', '</script>', 'javascript:', 'onerror=', 'onclick=',
            '<iframe', '</iframe>', 'eval(', 'expression(', 'vbscript:',
            'onload=', 'onmouseover=', '<object', '<embed'
        ]
        
        for field in allowed_fields:
            if field in data:
                # Sanitizar datos
                value = str(data[field]).strip()
                
                # Remover patrones peligrosos
                value_lower = value.lower()
                for pattern in dangerous_patterns:
                    if pattern in value_lower:
                        logger.warning(f"Patrón peligroso detectado en campo {field}: {pattern}")
                        value = value_lower.replace(pattern, '')
                
                cleaned_data[field] = value
        
        return cleaned_data
    
    @staticmethod
    def hash_sensitive_data(data):
        """
        Hash de datos sensibles usando SHA-256
        
        Args:
            data: Datos a hashear
            
        Returns:
            Hash hexadecimal
        """
        return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def encrypt_sensitive_data(data):
        """
        Encriptar datos sensibles
        
        Args:
            data: Datos a encriptar
            
        Returns:
            Datos encriptados en base64
        """
        try:
            key = settings.SECRET_KEY.encode()
            key = base64.urlsafe_b64encode(key[:32].ljust(32, b'0'))
            cipher = Fernet(key)
            
            encrypted = cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Error al encriptar datos: {str(e)}")
            raise
    
    @staticmethod
    def decrypt_sensitive_data(encrypted_data):
        """
        Desencriptar datos sensibles
        
        Args:
            encrypted_data: Datos encriptados en base64
            
        Returns:
            Datos desencriptados
        """
        try:
            key = settings.SECRET_KEY.encode()
            key = base64.urlsafe_b64encode(key[:32].ljust(32, b'0'))
            cipher = Fernet(key)
            
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Error al desencriptar datos: {str(e)}")
            raise


class AuditLogger:
    """Clase para logging de auditoría"""
    
    @staticmethod
    def log_user_action(user, action, resource, ip_address, success=True):
        """
        Registrar acción de usuario para auditoría
        
        Args:
            user: Usuario que realiza la acción
            action: Tipo de acción (CREATE, READ, UPDATE, DELETE)
            resource: Recurso afectado
            ip_address: Dirección IP del usuario
            success: Si la acción fue exitosa
        """
        status = "SUCCESS" if success else "FAILED"
        logger.info(
            f"AUDIT: User={user.username if user.is_authenticated else 'Anonymous'} "
            f"Action={action} Resource={resource} IP={ip_address} Status={status}"
        )
    
    @staticmethod
    def log_security_event(event_type, description, severity="WARNING"):
        """
        Registrar evento de seguridad
        
        Args:
            event_type: Tipo de evento (INTRUSION_ATTEMPT, INVALID_ACCESS, etc.)
            description: Descripción del evento
            severity: Nivel de severidad (INFO, WARNING, ERROR, CRITICAL)
        """
        log_method = getattr(logger, severity.lower(), logger.warning)
        log_method(f"SECURITY_EVENT: Type={event_type} Description={description}")

