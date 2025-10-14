# storages/supabase_storage.py
import os
import requests
import mimetypes
from django.core.files.storage import Storage
from django.conf import settings
from django.utils.deconstruct import deconstructible
from django.core.files.base import ContentFile
import uuid


@deconstructible
class SupabaseStorage(Storage):
    """
    Custom storage backend para Supabase Storage
    """
    
    def __init__(self):
        self.supabase_url = settings.SUPABASE_URL.rstrip('/')
        self.supabase_key = settings.SUPABASE_ANON_KEY
        self.bucket_name = settings.SUPABASE_BUCKET_NAME
        self.base_url = f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}"
        self.upload_url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}"
        
    def _get_headers(self, content_type=None):
        """Retorna los headers necesarios para la API de Supabase"""
        headers = {
            'Authorization': f'Bearer {self.supabase_key}',
            'apikey': self.supabase_key,
        }
        if content_type:
            headers['Content-Type'] = content_type
        return headers
    
    def _normalize_name(self, name):
        """
        Normaliza el nombre del archivo para evitar conflictos
        Agrega un UUID para evitar sobrescrituras
        """
        # Obtener la extensión del archivo
        base_name, ext = os.path.splitext(name)
        
        # Limpiar el nombre base
        base_name = base_name.replace(' ', '_')
        base_name = ''.join(c for c in base_name if c.isalnum() or c in ['_', '-'])
        
        # Agregar UUID para unicidad
        unique_name = f"{base_name}_{uuid.uuid4().hex[:8]}{ext}"
        
        return unique_name
    
    def _save(self, name, content):
        """
        Guarda el archivo en Supabase Storage
        """
        try:
            # Leer el contenido del archivo
            content.seek(0)
            file_content = content.read()
            
            # Normalizar el nombre del archivo
            name = self._normalize_name(name)
            
            # Detectar el tipo MIME
            content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
            if hasattr(content, 'content_type') and content.content_type:
                content_type = content.content_type
            
            # Headers para la subida
            headers = self._get_headers(content_type)
            
            # URL para subir
            upload_url = f"{self.upload_url}/{name}"
            
            # Subir el archivo
            response = requests.post(
                upload_url,
                headers=headers,
                data=file_content,
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                raise Exception(f"Error al subir archivo a Supabase: {response.status_code} - {response.text}")
            
            return name
            
        except Exception as e:
            raise Exception(f"Error guardando archivo en Supabase: {str(e)}")
    
    def url(self, name):
        """
        Retorna la URL pública del archivo
        """
        if not name:
            return ''
        # Asegurar que el nombre no tenga barras iniciales
        name = name.lstrip('/')
        return f"{self.base_url}/{name}"
    
    def exists(self, name):
        """
        Verifica si un archivo existe en Supabase Storage
        """
        try:
            url = f"{self.base_url}/{name}"
            response = requests.head(url, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def delete(self, name):
        """
        Elimina un archivo de Supabase Storage
        """
        try:
            url = f"{self.upload_url}/{name}"
            headers = self._get_headers()
            
            response = requests.delete(url, headers=headers, timeout=10)
            if response.status_code not in [200, 204]:
                print(f"Advertencia: No se pudo eliminar {name}: {response.text}")
        except Exception as e:
            print(f"Error al eliminar archivo {name}: {str(e)}")
    
    def size(self, name):
        """
        Retorna el tamaño del archivo
        """
        try:
            url = f"{self.base_url}/{name}"
            response = requests.head(url, timeout=10)
            if response.status_code == 200:
                return int(response.headers.get('Content-Length', 0))
        except:
            pass
        return 0
    
    def get_available_name(self, name, max_length=None):
        """
        Retorna un nombre de archivo disponible
        Como usamos UUID, cada archivo es único
        """
        name = self._normalize_name(name)
        
        if max_length and len(name) > max_length:
            # Acortar el nombre si es necesario
            base, ext = os.path.splitext(name)
            base = base[:max_length - len(ext) - 10]
            name = f"{base}{ext}"
        
        return name
    
    def get_valid_name(self, name):
        """
        Retorna un nombre de archivo válido para el sistema de archivos
        """
        return self._normalize_name(name)
    
    def path(self, name):
        """
        Retorna la ruta del archivo (no aplicable para storage remoto)
        """
        raise NotImplementedError("Este backend no soporta rutas locales")