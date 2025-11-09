from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.usuarios.views import home_view

urlpatterns = [
    # Admin de Django
    path('admin/', admin.site.urls),
    
    # Página principal (Home)
    path('', home_view, name='home'),
    
    # URLs de la app usuarios (login, register, etc.)
    path('usuarios/', include('apps.usuarios.urls')),
    
    # TODO: Agregar URLs de otras apps cuando estén listas
    path('destinos/', include('apps.destinos.urls')),
    path('servicios/', include('apps.servicios.urls')),

    path('rutas/', include('apps.rutas.urls')),
    path('reservas/', include('apps.reservas.urls')),
    path('calificaciones/', include('apps.calificaciones.urls')),
    path('chatbot/', include('apps.chatbot.urls')),
]

# Configuración para servir archivos media y static en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Personalizar títulos del admin
admin.site.site_header = "Ecuador Turismo - Administración"
admin.site.site_title = "Admin Ecuador Turismo"
admin.site.index_title = "Panel de Administración"