from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from apps.usuarios.models import Usuario


class Categoria(models.Model):
    """
    Modelo para categorías de destinos turísticos
    Ejemplo: Playas, Montañas, Sitios Históricos, Parques Nacionales
    """
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Nombre de la Categoría'
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descripción'
    )
    icono = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Icono CSS',
        help_text='Clase de icono para representar la categoría'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    
    class Meta:
        db_table = 'categorias'
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class Destino(models.Model):
    """
    Modelo para destinos turísticos en Ecuador
    RF-002: Búsqueda y filtrado por regiones
    RF-005: Mapas y rutas interactivas
    """
    # Regiones de Ecuador
    COSTA = 'costa'
    SIERRA = 'sierra'
    ORIENTE = 'oriente'
    GALAPAGOS = 'galapagos'
    
    REGIONES_CHOICES = [
        (COSTA, 'Costa'),
        (SIERRA, 'Sierra'),
        (ORIENTE, 'Oriente/Amazonía'),
        (GALAPAGOS, 'Galápagos'),
    ]
    
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre del Destino'
    )
    slug = models.SlugField(
        max_length=250,
        unique=True,
        blank=True,
        verbose_name='Slug'
    )
    descripcion = models.TextField(
        verbose_name='Descripción'
    )
    descripcion_corta = models.CharField(
        max_length=300,
        verbose_name='Descripción Corta',
        help_text='Resumen breve para listados'
    )
    provincia = models.CharField(
        max_length=100,
        verbose_name='Provincia'
    )
    ciudad = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Ciudad'
    )
    region = models.CharField(
        max_length=20,
        choices=REGIONES_CHOICES,
        verbose_name='Región'
    )
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name='destinos',
        verbose_name='Categoría',
        null=True,
        blank=True
    )
    
    # Coordenadas geográficas para Google Maps
    latitud = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        verbose_name='Latitud',
        help_text='Coordenada geográfica en formato decimal'
    )
    longitud = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        verbose_name='Longitud',
        help_text='Coordenada geográfica en formato decimal'
    )
    
    # Información adicional
    clima = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Clima',
        help_text='Descripción del clima del destino'
    )
    altitud = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='Altitud (msnm)',
        help_text='Altitud sobre el nivel del mar en metros'
    )
    mejor_epoca = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Mejor Época para Visitar'
    )
    
    # Precios de referencia
    precio_promedio_minimo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Precio Promedio Mínimo (USD)',
        help_text='Costo promedio mínimo por persona por día'
    )
    precio_promedio_maximo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Precio Promedio Máximo (USD)',
        help_text='Costo promedio máximo por persona por día'
    )
    
    # Calificación
    calificacion_promedio = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name='Calificación Promedio'
    )
    total_calificaciones = models.IntegerField(
        default=0,
        verbose_name='Total de Calificaciones'
    )
    
    # Popularidad y visibilidad
    visitas = models.IntegerField(
        default=0,
        verbose_name='Número de Visitas'
    )
    destacado = models.BooleanField(
        default=False,
        verbose_name='Destino Destacado'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
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
    creado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='destinos_creados',
        verbose_name='Creado Por'
    )
    
    class Meta:
        db_table = 'destinos'
        verbose_name = 'Destino'
        verbose_name_plural = 'Destinos'
        ordering = ['-destacado', '-calificacion_promedio', 'nombre']
        indexes = [
            models.Index(fields=['region']),
            models.Index(fields=['provincia']),
            models.Index(fields=['calificacion_promedio']),
            models.Index(fields=['destacado']),
        ]
    
    def __str__(self):
        return f"{self.nombre} - {self.get_region_display()}"
    
    def save(self, *args, **kwargs):
        """Generar slug automáticamente si no existe"""
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)
    
    def incrementar_visitas(self):
        """Incrementar el contador de visitas"""
        self.visitas += 1
        self.save(update_fields=['visitas'])
    
# Reemplaza el método actualizar_calificacion en tu modelo Destino con este:

def actualizar_calificacion(self):
    """
    Actualizar la calificación promedio basada en las calificaciones de servicios asociados
    """
    from django.db.models import Avg, Count
    from apps.calificaciones.models import Calificacion
    
    stats = Calificacion.objects.filter(
        servicio__destino=self,
        activo=True
    ).aggregate(
        promedio=Avg('puntuacion'),
        total=Count('id')
    )
    
    self.calificacion_promedio = round(stats['promedio'] or 0, 2)
    self.total_calificaciones = stats['total'] or 0
    self.save(update_fields=['calificacion_promedio', 'total_calificaciones'])
    
    def get_rango_precio(self):
        """Retorna el rango de precio formateado"""
        if self.precio_promedio_minimo and self.precio_promedio_maximo:
            return f"${self.precio_promedio_minimo:.0f} - ${self.precio_promedio_maximo:.0f}"
        return "Precio no disponible"
    
    def get_coordenadas(self):
        """Retorna las coordenadas como tupla para Google Maps"""
        return (float(self.latitud), float(self.longitud))


class ImagenDestino(models.Model):
    """
    Modelo para gestionar múltiples imágenes por destino
    """
    destino = models.ForeignKey(
        Destino,
        on_delete=models.CASCADE,
        related_name='imagenes',
        verbose_name='Destino'
    )
    imagen = models.ImageField(
        upload_to='destinos/%Y/%m/',
        verbose_name='Imagen'
    )
    titulo = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Título de la Imagen'
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descripción'
    )
    es_principal = models.BooleanField(
        default=False,
        verbose_name='Imagen Principal'
    )
    orden = models.IntegerField(
        default=0,
        verbose_name='Orden de Visualización'
    )
    fecha_subida = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Subida'
    )
    
    class Meta:
        db_table = 'imagenes_destino'
        verbose_name = 'Imagen de Destino'
        verbose_name_plural = 'Imágenes de Destinos'
        ordering = ['orden', '-es_principal']
    
    def __str__(self):
        return f"Imagen de {self.destino.nombre}"
    
    def save(self, *args, **kwargs):
        """Si se marca como principal, desmarcar otras imágenes principales del mismo destino"""
        if self.es_principal:
            ImagenDestino.objects.filter(
                destino=self.destino,
                es_principal=True
            ).exclude(pk=self.pk).update(es_principal=False)
        super().save(*args, **kwargs)


class AtraccionTuristica(models.Model):
    """
    Modelo para atracciones turísticas específicas dentro de un destino
    """
    destino = models.ForeignKey(
        Destino,
        on_delete=models.CASCADE,
        related_name='atracciones',
        verbose_name='Destino'
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre de la Atracción'
    )
    descripcion = models.TextField(
        verbose_name='Descripción'
    )
    tipo = models.CharField(
        max_length=100,
        verbose_name='Tipo de Atracción',
        help_text='Ej: Museo, Parque, Mirador, Playa, etc.'
    )
    precio_entrada = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Precio de Entrada (USD)'
    )
    horario = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Horario de Atención'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    
    class Meta:
        db_table = 'atracciones_turisticas'
        verbose_name = 'Atracción Turística'
        verbose_name_plural = 'Atracciones Turísticas'
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} - {self.destino.nombre}"