"""
Sanitizadores de entrada para prevenir ataques de inyección
"""

import re
import html
import logging
from django.utils.html import strip_tags
from django.core.exceptions import ValidationError

logger = logging.getLogger('django.security')

class InputSanitizer:
    """Clase para sanitizar todas las entradas del usuario"""
    
    # Patrones peligrosos
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # XSS scripts
        r'javascript:',  # JavaScript URLs
        r'on\w+\s*=',  # Event handlers
        r'<iframe[^>]*>.*?</iframe>',  # Iframes
        r'<object[^>]*>.*?</object>',  # Objects
        r'<embed[^>]*>.*?</embed>',  # Embeds
        r'union.*select',  # SQL injection
        r'drop.*table',  # SQL injection
        r'insert.*into',  # SQL injection
        r'delete.*from',  # SQL injection
        r'exec\s*\(',  # Command injection
        r'system\s*\(',  # Command injection
        r'\.\./',  # Path traversal
        r'%2e%2e',  # Encoded path traversal
    ]
    
    @classmethod
    def sanitize_text(cls, text):
        """Sanitizar texto general"""
        if not text:
            return text
            
        # Convertir a string si no lo es
        text = str(text)
        
        # Detectar patrones peligrosos
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Patrón peligroso detectado en entrada: {pattern}")
                raise ValidationError("Entrada contiene contenido no permitido")
        
        # Escapar HTML
        text = html.escape(text)
        
        # Remover tags HTML restantes
        text = strip_tags(text)
        
        # Limpiar caracteres de control
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        return text.strip()
    
    @classmethod
    def sanitize_email(cls, email):
        """Sanitizar email"""
        if not email:
            return email
            
        email = str(email).strip().lower()
        
        # Validar formato básico
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValidationError("Formato de email inválido")
            
        return email
    
    @classmethod
    def sanitize_phone(cls, phone):
        """Sanitizar teléfono"""
        if not phone:
            return phone
            
        # Remover todo excepto números, +, -, (), espacios
        phone = re.sub(r'[^\d\+\-\(\)\s]', '', str(phone))
        
        return phone.strip()
    
    @classmethod
    def sanitize_url(cls, url):
        """Sanitizar URL"""
        if not url:
            return url
            
        url = str(url).strip()
        
        # Verificar protocolo seguro
        if not url.startswith(('http://', 'https://', '/')):
            raise ValidationError("URL debe comenzar con http://, https:// o /")
            
        # Detectar patrones peligrosos
        dangerous_url_patterns = [
            r'javascript:',
            r'data:',
            r'vbscript:',
            r'file:',
            r'ftp:',
        ]
        
        for pattern in dangerous_url_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                raise ValidationError("URL contiene protocolo no permitido")
                
        return url
    
    @classmethod
    def sanitize_filename(cls, filename):
        """Sanitizar nombre de archivo"""
        if not filename:
            return filename
            
        filename = str(filename).strip()
        
        # Remover caracteres peligrosos
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # Remover path traversal
        filename = re.sub(r'\.\.', '', filename)
        
        # Limitar longitud
        if len(filename) > 255:
            filename = filename[:255]
            
        return filename