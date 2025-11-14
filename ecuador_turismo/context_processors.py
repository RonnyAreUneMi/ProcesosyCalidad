from django.conf import settings

def mapbox_context(request):
    """Context processor para variables de Mapbox"""
    return {
        'MAPBOX_ACCESS_TOKEN': getattr(settings, 'MAPBOX_ACCESS_TOKEN', ''),
        'MAPBOX_STYLE': getattr(settings, 'MAPBOX_STYLE', 'mapbox://styles/mapbox/streets-v12'),
    }