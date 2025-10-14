from django.db import models
from django.core.validators import MinValueValidator
from apps.destinos.models import Destino


class Ruta(models.Model):
    """
    Modelo para rutas turísticas entre destinos
    RF-004: Comparación de Rutas Multimodales
    """
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre de la Ruta'
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descripción'
    )
    distancia_total_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Distancia Total (km)'
    )
    duracion_total_horas = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Duración Total (horas)'
    )
    precio_promedio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Precio Promedio (USD)'
    )
    activa = models.BooleanField(
        default=True,
        verbose_name='Activa'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    
    class Meta:
        db_table = 'rutas'
        verbose_name = 'Ruta'
        verbose_name_plural = 'Rutas'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre
    
    def calcular_totales(self):
        """
        Recalcula los totales de la ruta basándose en sus detalles
        """
        detalles = self.detalles.all()
        
        self.distancia_total_km = sum(d.distancia_tramo_km for d in detalles)
        self.duracion_total_horas = sum(d.duracion_tramo_horas for d in detalles)
        self.precio_promedio = sum(d.precio for d in detalles)
        
        self.save(update_fields=[
            'distancia_total_km',
            'duracion_total_horas',
            'precio_promedio'
        ])


class DetalleRuta(models.Model):
    """
    Modelo para detalles de tramos de una ruta
    RF-004: Comparación de Rutas Multimodales
    Cada tramo representa un segmento de la ruta con medio de transporte específico
    """
    BUS = 'bus'
    AVION = 'avion'
    BARCO = 'barco'
    AUTO = 'auto'
    
    MEDIO_TRANSPORTE_CHOICES = [
        (BUS, 'Bus'),
        (AVION, 'Avión'),
        (BARCO, 'Barco'),
        (AUTO, 'Auto'),
    ]
    
    ruta = models.ForeignKey(
        Ruta,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='Ruta'
    )
    origen = models.ForeignKey(
        Destino,
        on_delete=models.PROTECT,
        related_name='tramos_origen',
        verbose_name='Origen'
    )
    destino = models.ForeignKey(
        Destino,
        on_delete=models.PROTECT,
        related_name='tramos_destino',
        verbose_name='Destino'
    )
    orden_tramo = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Orden del Tramo',
        help_text='Orden secuencial del tramo en la ruta'
    )
    medio_transporte = models.CharField(
        max_length=20,
        choices=MEDIO_TRANSPORTE_CHOICES,
        verbose_name='Medio de Transporte'
    )
    distancia_tramo_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Distancia del Tramo (km)'
    )
    duracion_tramo_horas = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Duración del Tramo (horas)'
    )
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Precio del Tramo (USD)'
    )
    
    # Información adicional
    empresa_transporte = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Empresa de Transporte'
    )
    horarios_disponibles = models.TextField(
        blank=True,
        null=True,
        verbose_name='Horarios Disponibles',
        help_text='Horarios de salida disponibles'
    )
    notas = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas Adicionales'
    )
    
    class Meta:
        db_table = 'detalles_ruta'
        verbose_name = 'Detalle de Ruta'
        verbose_name_plural = 'Detalles de Ruta'
        ordering = ['ruta', 'orden_tramo']
        unique_together = [['ruta', 'orden_tramo']]
        indexes = [
            models.Index(fields=['ruta', 'orden_tramo']),
            models.Index(fields=['medio_transporte']),
        ]
    
    def __str__(self):
        return f"{self.origen.nombre} → {self.destino.nombre} ({self.get_medio_transporte_display()})"
    
    def save(self, *args, **kwargs):
        """
        Al guardar, recalcula los totales de la ruta padre
        """
        super().save(*args, **kwargs)
        self.ruta.calcular_totales()