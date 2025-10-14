from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import Rol, Usuario, PerfilUsuario


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    """
    Administración de Roles en Django Admin
    RF-001: Gestión de roles
    """
    list_display = ('nombre', 'descripcion_corta', 'cantidad_usuarios', 'activo', 'fecha_creacion')
    list_filter = ('activo', 'fecha_creacion')
    search_fields = ('nombre', 'descripcion')
    readonly_fields = ('fecha_creacion',)
    ordering = ('nombre',)
    
    fieldsets = (
        ('Información del Rol', {
            'fields': ('nombre', 'descripcion', 'activo')
        }),
        ('Auditoría', {
            'fields': ('fecha_creacion',),
            'classes': ('collapse',)
        }),
    )
    
    def descripcion_corta(self, obj):
        """Muestra descripción truncada"""
        if obj.descripcion:
            return obj.descripcion[:50] + '...' if len(obj.descripcion) > 50 else obj.descripcion
        return '-'
    descripcion_corta.short_description = 'Descripción'
    
    def cantidad_usuarios(self, obj):
        """Cuenta usuarios con este rol"""
        count = obj.usuarios.count()
        return format_html(
            '<span style="background: #3b82f6; color: white; padding: 3px 10px; border-radius: 12px; font-weight: bold;">{}</span>',
            count
        )
    cantidad_usuarios.short_description = 'Usuarios'


class PerfilUsuarioInline(admin.StackedInline):
    """
    Inline para mostrar perfil de usuario en admin
    """
    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Perfil Extendido'
    fk_name = 'usuario'
    fields = ('biografia', 'pais', 'ciudad', 'avatar')


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    """
    Administración personalizada de Usuarios en Django Admin
    RF-001: Gestión completa de usuarios
    RF-008: Panel de administración
    """
    list_display = (
        'correo',
        'nombre',
        'rol_badge',
        'telefono',
        'estado_badge',
        'ultimo_acceso_formateado',
        'fecha_registro'
    )
    list_filter = (
        'is_active',
        'is_staff',
        'rol',
        'fecha_registro',
        'ultimo_acceso'
    )
    search_fields = ('correo', 'nombre', 'telefono')
    readonly_fields = ('fecha_registro', 'fecha_actualizacion', 'ultimo_acceso', 'password')
    ordering = ('-fecha_registro',)
    
    # Inlines
    inlines = [PerfilUsuarioInline]
    
    # Fieldsets para agregar/editar
    fieldsets = (
        ('Credenciales', {
            'fields': ('correo', 'password')
        }),
        ('Información Personal', {
            'fields': ('nombre', 'telefono')
        }),
        ('Permisos y Rol', {
            'fields': ('rol', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Fechas Importantes', {
            'fields': ('fecha_registro', 'fecha_actualizacion', 'ultimo_acceso'),
            'classes': ('collapse',)
        }),
    )
    
    # Fieldsets para crear usuario
    add_fieldsets = (
        ('Credenciales', {
            'classes': ('wide',),
            'fields': ('correo', 'password1', 'password2'),
        }),
        ('Información Personal', {
            'fields': ('nombre', 'telefono')
        }),
        ('Permisos', {
            'fields': ('rol', 'is_active', 'is_staff', 'is_superuser')
        }),
    )
    
    def rol_badge(self, obj):
        """Muestra el rol con badge colorido"""
        if obj.rol:
            colores = {
                'turista': '#10b981',      # Verde
                'proveedor': '#f59e0b',    # Naranja
                'administrador': '#3b82f6' # Azul
            }
            color = colores.get(obj.rol.nombre, '#6b7280')
            return format_html(
                '<span style="background: {}; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 11px;">{}</span>',
                color,
                obj.rol.get_nombre_display().upper()
            )
        return format_html('<span style="color: #6b7280;">Sin rol</span>')
    rol_badge.short_description = 'Rol'
    
    def estado_badge(self, obj):
        """Muestra el estado del usuario con badge"""
        if obj.is_active:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 11px;">✓ ACTIVO</span>'
            )
        else:
            return format_html(
                '<span style="background: #ef4444; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 11px;">✗ INACTIVO</span>'
            )
    estado_badge.short_description = 'Estado'
    
    def ultimo_acceso_formateado(self, obj):
        """Formatea la fecha de último acceso"""
        if obj.ultimo_acceso:
            return obj.ultimo_acceso.strftime('%d/%m/%Y %H:%M')
        return format_html('<span style="color: #9ca3af;">Nunca</span>')
    ultimo_acceso_formateado.short_description = 'Último Acceso'
    
    # Acciones personalizadas
    actions = ['activar_usuarios', 'desactivar_usuarios', 'asignar_rol_turista']
    
    def activar_usuarios(self, request, queryset):
        """Acción para activar usuarios seleccionados"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f'{updated} usuario(s) activado(s) exitosamente.'
        )
    activar_usuarios.short_description = '✓ Activar usuarios seleccionados'
    
    def desactivar_usuarios(self, request, queryset):
        """Acción para desactivar usuarios seleccionados"""
        # Evitar desactivar superusuarios
        queryset = queryset.exclude(is_superuser=True)
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{updated} usuario(s) desactivado(s) exitosamente.'
        )
    desactivar_usuarios.short_description = '✗ Desactivar usuarios seleccionados'
    
    def asignar_rol_turista(self, request, queryset):
        """Acción para asignar rol de turista"""
        rol_turista = Rol.objects.get(nombre=Rol.TURISTA)
        updated = queryset.update(rol=rol_turista)
        self.message_user(
            request,
            f'{updated} usuario(s) ahora tienen rol de Turista.'
        )
    asignar_rol_turista.short_description = '👤 Asignar rol de Turista'


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    """
    Administración de Perfiles de Usuario
    """
    list_display = ('usuario', 'pais', 'ciudad', 'tiene_avatar')
    list_filter = ('pais',)
    search_fields = ('usuario__nombre', 'usuario__correo', 'ciudad')
    
    fieldsets = (
        ('Usuario', {
            'fields': ('usuario',)
        }),
        ('Información Adicional', {
            'fields': ('avatar', 'biografia', 'pais', 'ciudad')
        }),
        ('Configuración', {
            'fields': ('preferencias_notificacion',),
            'classes': ('collapse',)
        }),
    )
    
    def tiene_avatar(self, obj):
        """Indica si el usuario tiene avatar"""
        if obj.avatar:
            return format_html('<span style="color: #10b981;">✓ Sí</span>')
        return format_html('<span style="color: #6b7280;">✗ No</span>')
    tiene_avatar.short_description = 'Avatar'