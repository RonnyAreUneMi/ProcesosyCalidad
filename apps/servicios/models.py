from django.db import models
from django.core.validators import MinValueValidator
from apps.destinos.models import Destino, Categoria
from apps.usuarios.models import Usuario


class Servicio(models.Model):
    """
    Modelo para servicios turísticos (alojamiento, tours, actividades)
    RF-003: Sistema de Reservas con Cálculo Dinámico
    """
    ALOJAMIENTO = 'alojamiento'
    TOUR = 'tour'
    ACTIVIDAD = 'actividad'
    TRANSPORTE = 'transporte'
    RESTAURANTE = 'restaurante'
    
    TIPO_SERVICIO_CHOICES = [
        (ALOJAMIENTO, 'Alojamiento'),
        (TOUR, 'Tour'),
        (ACTIVIDAD, 'Actividad'),
        (TRANSPORTE, 'Transporte'),
        (RESTAURANTE, 'Restaurante'),
    ]
    
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre del Servicio'
    )
    descripcion = models.TextField(
        verbose_name='Descripción'
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_SERVICIO_CHOICES,
        verbose_name='Tipo de Servicio'
    )
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Precio (USD)',
        help_text='Precio base del servicio'
    )
    destino = models.ForeignKey(
        Destino,
        on_delete=models.CASCADE,
        related_name='servicios',
        verbose_name='Destino'
    )
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name='servicios',
        verbose_name='Categoría',
        null=True,
        blank=True
    )
    proveedor = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='servicios_proveedor',
        limit_choices_to={'rol__nombre': 'proveedor'},
        verbose_name='Proveedor'
    )
    
    # Disponibilidad
    disponible = models.BooleanField(
        default=True,
        verbose_name='Disponible'
    )
    capacidad_maxima = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Capacidad Máxima',
        help_text='Número máximo de personas por reserva'
    )
    
    # Calificación
    calificacion_promedio = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        verbose_name='Calificación Promedio'
    )
    total_calificaciones = models.IntegerField(
        default=0,
        verbose_name='Total de Calificaciones'
    )
    
    # Metadatos
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    
    class Meta:
        db_table = 'servicios'
        verbose_name = 'Servicio'
        verbose_name_plural = 'Servicios'
        ordering = ['-calificacion_promedio', 'nombre']
        indexes = [
            models.Index(fields=['tipo']),
            models.Index(fields=['destino']),
            models.Index(fields=['disponible']),
        ]
    
    def __str__(self):
        return f"{self.nombre} - {self.get_tipo_display()}"
    
    def actualizar_calificacion(self):
        """
        Actualizar la calificación promedio del servicio
        """
        from django.db.models import Avg, Count
        from apps.calificaciones.models import Calificacion
        
        stats = Calificacion.objects.filter(
            servicio=self,
            activo=True
        ).aggregate(
            promedio=Avg('puntuacion'),
            total=Count('id')
        )
        
        self.calificacion_promedio = round(stats['promedio'] or 0, 2)
        self.total_calificaciones = stats['total'] or 0
        self.save(update_fields=['calificacion_promedio', 'total_calificaciones'])


class ImagenServicio(models.Model):
    """
    Modelo para imágenes de servicios
    """
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name='imagenes',
        verbose_name='Servicio'
    )
    imagen = models.ImageField(
        upload_to='servicios/%Y/%m/',
        verbose_name='Imagen'
    )
    titulo = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Título'
    )
    es_principal = models.BooleanField(
        default=False,
        verbose_name='Imagen Principal'
    )
    orden = models.IntegerField(
        default=0,
        verbose_name='Orden'
    )
    fecha_subida = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Subida'
    )
    
    class Meta:
        db_table = 'imagenes_servicio'
        verbose_name = 'Imagen de Servicio'
        verbose_name_plural = 'Imágenes de Servicios'
        ordering = ['orden', '-es_principal']
    
    def __str__(self):
        return f"Imagen de {self.servicio.nombre}"
    
    def save(self, *args, **kwargs):
        """Si se marca como principal, desmarcar otras imágenes principales"""
        if self.es_principal:
            ImagenServicio.objects.filter(
                servicio=self.servicio,
                es_principal=True
            ).exclude(pk=self.pk).update(es_principal=False)
        super().save(*args, **kwargs)