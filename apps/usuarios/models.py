from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import EmailValidator
from django.utils import timezone


class Rol(models.Model):
    """
    Modelo para gestionar roles de usuarios en el sistema
    RF-001: Gestión de Usuarios con Roles
    """
    TURISTA = 'turista'
    PROVEEDOR = 'proveedor'
    ADMINISTRADOR = 'administrador'
    
    ROLES_CHOICES = [
        (TURISTA, 'Turista'),
        (PROVEEDOR, 'Proveedor de Servicios'),
        (ADMINISTRADOR, 'Administrador del Sistema'),
    ]
    
    nombre = models.CharField(
        max_length=50,
        unique=True,
        choices=ROLES_CHOICES,
        verbose_name='Nombre del Rol'
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descripción del Rol'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    
    class Meta:
        db_table = 'roles'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'
        ordering = ['nombre']
    
    def __str__(self):
        return self.get_nombre_display()


class UsuarioManager(BaseUserManager):
    """
    Manager personalizado para el modelo Usuario
    Gestiona la creación de usuarios y superusuarios
    """
    
    def create_user(self, correo, nombre, password=None, **extra_fields):
        """
        Crea y guarda un usuario con el correo y contraseña dados
        """
        if not correo:
            raise ValueError('El usuario debe tener un correo electrónico')
        if not nombre:
            raise ValueError('El usuario debe tener un nombre')
        
        correo = self.normalize_email(correo)
        user = self.model(correo=correo, nombre=nombre, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, correo, nombre, password=None, **extra_fields):
        """
        Crea y guarda un superusuario con permisos de administrador
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superusuario debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superusuario debe tener is_superuser=True.')
        
        # Asignar rol de administrador
        rol_admin, created = Rol.objects.get_or_create(
            nombre=Rol.ADMINISTRADOR,
            defaults={'descripcion': 'Administrador del sistema con acceso completo'}
        )
        extra_fields['rol'] = rol_admin
        
        return self.create_user(correo, nombre, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Modelo de Usuario personalizado
    RF-001: Registro de usuario con validación y roles
    """
    correo = models.EmailField(
        max_length=255,
        unique=True,
        validators=[EmailValidator()],
        verbose_name='Correo Electrónico',
        help_text='Correo electrónico único del usuario'
    )
    nombre = models.CharField(
        max_length=150,
        verbose_name='Nombre Completo',
        help_text='Nombre completo del usuario'
    )
    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        related_name='usuarios',
        verbose_name='Rol del Usuario',
        null=True,
        blank=True
    )
    telefono = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name='Teléfono'
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Registro'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name='Es Staff'
    )
    ultimo_acceso = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Último Acceso'
    )
    
    objects = UsuarioManager()
    
    USERNAME_FIELD = 'correo'
    REQUIRED_FIELDS = ['nombre']
    
    class Meta:
        db_table = 'usuarios'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['-fecha_registro']
        indexes = [
            models.Index(fields=['correo']),
            models.Index(fields=['rol']),
        ]
    
    def __str__(self):
        return f"{self.nombre} ({self.correo})"
    
    def save(self, *args, **kwargs):
        """
        Sobrescribe el método save para asignar rol por defecto
        RF-001: Asignación automática de rol "turista"
        """
        if not self.rol_id:
            rol_turista, created = Rol.objects.get_or_create(
                nombre=Rol.TURISTA,
                defaults={'descripcion': 'Usuario turista con permisos básicos'}
            )
            self.rol = rol_turista
        super().save(*args, **kwargs)
    
    def actualizar_ultimo_acceso(self):
        """
        Actualiza la fecha del último acceso del usuario
        """
        self.ultimo_acceso = timezone.now()
        self.save(update_fields=['ultimo_acceso'])
    
    def es_turista(self):
        """Verifica si el usuario tiene rol de turista"""
        return self.rol and self.rol.nombre == Rol.TURISTA
    
    def es_proveedor(self):
        """Verifica si el usuario tiene rol de proveedor"""
        return self.rol and self.rol.nombre == Rol.PROVEEDOR
    
    def es_administrador(self):
        """Verifica si el usuario tiene rol de administrador"""
        return self.rol and self.rol.nombre == Rol.ADMINISTRADOR or self.is_superuser
    
    def puede_cambiar_rol(self):
        """
        Determina si el usuario puede cambiar su rol
        Solo administradores pueden cambiar roles
        """
        return self.es_administrador()
    
    def get_permisos(self):
        """
        Retorna lista de permisos basados en el rol
        """
        permisos = {
            Rol.TURISTA: ['ver_destinos', 'hacer_reservas', 'calificar_servicios'],
            Rol.PROVEEDOR: ['gestionar_servicios', 'ver_reservas', 'responder_calificaciones'],
            Rol.ADMINISTRADOR: ['gestionar_todo', 'ver_reportes', 'gestionar_usuarios']
        }
        return permisos.get(self.rol.nombre if self.rol else Rol.TURISTA, [])


class PerfilUsuario(models.Model):
    """
    Modelo extendido para información adicional del perfil
    """
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name='perfil',
        verbose_name='Usuario'
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        verbose_name='Avatar'
    )
    biografia = models.TextField(
        blank=True,
        null=True,
        max_length=500,
        verbose_name='Biografía'
    )
    pais = models.CharField(
        max_length=100,
        default='Ecuador',
        verbose_name='País'
    )
    ciudad = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Ciudad'
    )
    preferencias_notificacion = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Preferencias de Notificación'
    )
    
    class Meta:
        db_table = 'perfiles_usuario'
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'
    
    def __str__(self):
        return f"Perfil de {self.usuario.nombre}"