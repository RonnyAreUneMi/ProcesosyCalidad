from django.template import Library
from django.conf import settings

register = Library()

@register.simple_tag
def mapbox_token():
    """Retorna el token de Mapbox de forma segura"""
    return getattr(settings, 'MAPBOX_ACCESS_TOKEN', '')

@register.simple_tag
def mapbox_style():
    """Retorna el estilo de Mapbox configurado"""
    return getattr(settings, 'MAPBOX_STYLE', 'mapbox://styles/mapbox/streets-v12')