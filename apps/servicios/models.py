from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from apps.destinos.models import Destino, Categoria
from apps.usuarios.models import Usuario


class Servicio(models.Model):
    """
    Modelo para servicios turísticos (alojamiento, tours, actividades)
    RF-003: Sistema de Reservas con Cálculo Dinámico
    Incluye geolocalización y horarios de atención
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
    
    # Información básica
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
    
    # === GEOLOCALIZACIÓN ===
    direccion = models.CharField(
        max_length=500,
        verbose_name='Dirección Completa',
        help_text='Ej: Charles Darwin Ave., Puerto Ayora 200102 Ecuador'
    )
    

    latitud = models.DecimalField(
        max_digits=10,  
        decimal_places=8,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90)
        ],
        verbose_name='Latitud',
        help_text='Coordenada latitud (-90 a 90)',
        null=False,
        blank=False
    )

    longitud = models.DecimalField(
        max_digits=11,  
        decimal_places=8,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180)
        ],
        verbose_name='Longitud',
        help_text='Coordenada longitud (-180 a 180)',
        null=False,
        blank=False
    )
    zona_referencia = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Zona de Referencia',
        help_text='Ej: Cerca del muelle principal, Frente al parque central'
    )
        
    # === INFORMACIÓN DE CONTACTO ===
    telefono_validator = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="El número de teléfono debe estar en formato: '+593981234567' o '0981234567'"
    )
    telefono = models.CharField(
        validators=[telefono_validator],
        max_length=17,
        verbose_name='Teléfono de Contacto',
        help_text='Formato: +593981234567'
    )
    telefono_alternativo = models.CharField(
        validators=[telefono_validator],
        max_length=17,
        blank=True,
        null=True,
        verbose_name='Teléfono Alternativo'
    )
    email_contacto = models.EmailField(
        verbose_name='Email de Contacto',
        help_text='Email para consultas y reservas'
    )
    sitio_web = models.URLField(
        blank=True,
        null=True,
        verbose_name='Sitio Web',
        help_text='URL del sitio web (opcional)'
    )
    whatsapp = models.CharField(
        validators=[telefono_validator],
        max_length=17,
        blank=True,
        null=True,
        verbose_name='WhatsApp',
        help_text='Número de WhatsApp (opcional)'
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
            models.Index(fields=['latitud', 'longitud']),
        ]
    
    def __str__(self):
        return f"{self.nombre} - {self.get_tipo_display()}"
    
    def clean(self):
        """Validación personalizada"""
        super().clean()
        
        # Validar que latitud y longitud sean válidas para Ecuador
        if self.latitud:
            if not (-5 <= self.latitud <= 2):
                raise ValidationError({
                    'latitud': 'La latitud debe estar dentro del rango de Ecuador (-5° a 2°)'
                })
        
        if self.longitud:
            if not (-92 <= self.longitud <= -75):
                raise ValidationError({
                    'longitud': 'La longitud debe estar dentro del rango de Ecuador (-92° a -75°)'
                })
    
    def actualizar_calificacion(self):
        """Actualizar la calificación promedio del servicio"""
        from django.db.models import Avg, Count
        from apps.calificaciones.models import Calificacion
        from decimal import Decimal, ROUND_HALF_UP
        
        stats = Calificacion.objects.filter(
            servicio=self,
            activo=True
        ).aggregate(
            promedio=Avg('puntuacion'),
            total=Count('id')
        )
        
        # Usar Decimal para mantener precisión y evitar redondeo incorrecto
        promedio = stats['promedio']
        if promedio is not None:
            # Convertir a Decimal y redondear correctamente a 2 decimales
            self.calificacion_promedio = Decimal(str(promedio)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        else:
            self.calificacion_promedio = Decimal('0.00')
            
        self.total_calificaciones = stats['total'] or 0
        self.save(update_fields=['calificacion_promedio', 'total_calificaciones'])
    
    def get_coordenadas(self):
        """Retorna las coordenadas como diccionario"""
        return {
            'lat': float(self.latitud) if self.latitud else 0.0,
            'lng': float(self.longitud) if self.longitud else 0.0
        }
    
    def get_url_google_maps(self):
        """Genera URL de Google Maps"""
        return f"https://www.google.com/maps?q={self.latitud},{self.longitud}"
    
    def esta_abierto_ahora(self):
        """Verifica si el servicio está abierto en este momento"""
        from datetime import datetime
        ahora = datetime.now()
        dia_semana = ahora.weekday()  # 0=Lunes, 6=Domingo
        hora_actual = ahora.time()
        
        # Determinar si es fin de semana (sábado=5, domingo=6)
        es_fin_de_semana = dia_semana >= 5
        
        # Obtener el horario correspondiente según el día
        if es_fin_de_semana:
            horario = self.horarios.filter(activo=True, tipo_horario='sabado_domingo').first()
        else:
            horario = self.horarios.filter(activo=True, tipo_horario='lunes_viernes').first()
        
        # Si no hay horario definido, considerar cerrado
        if not horario:
            return False
        
        # Si está marcado como cerrado
        if horario.cerrado:
            return False
        
        # Verificar si la hora actual está dentro del rango
        return horario.hora_apertura <= hora_actual <= horario.hora_cierre


class HorarioAtencion(models.Model):
    """
    Modelo para horarios de atención del servicio
    Separado en días laborables (L-V) y fines de semana (S-D)
    """
    LUNES_VIERNES = 'lunes_viernes'
    SABADO_DOMINGO = 'sabado_domingo'
    
    TIPO_HORARIO_CHOICES = [
        (LUNES_VIERNES, 'Lunes a Viernes'),
        (SABADO_DOMINGO, 'Sábado y Domingo'),
    ]
    
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name='horarios',
        verbose_name='Servicio'
    )
    tipo_horario = models.CharField(
        max_length=20,
        choices=TIPO_HORARIO_CHOICES,
        verbose_name='Tipo de Horario'
    )
    hora_apertura = models.TimeField(
        verbose_name='Hora de Apertura',
        help_text='Formato 24 horas: 08:00'
    )
    hora_cierre = models.TimeField(
        verbose_name='Hora de Cierre',
        help_text='Formato 24 horas: 23:00'
    )
    cerrado = models.BooleanField(
        default=False,
        verbose_name='Cerrado',
        help_text='Marcar si el servicio está cerrado en este horario'
    )
    notas = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Notas',
        help_text='Ej: Horario extendido en temporada alta'
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
        db_table = 'horarios_atencion'
        verbose_name = 'Horario de Atención'
        verbose_name_plural = 'Horarios de Atención'
        ordering = ['tipo_horario', 'hora_apertura']
        unique_together = ['servicio', 'tipo_horario']
    
    def __str__(self):
        if self.cerrado:
            return f"{self.servicio.nombre} - {self.get_tipo_horario_display()}: CERRADO"
        return f"{self.servicio.nombre} - {self.get_tipo_horario_display()}: {self.hora_apertura.strftime('%H:%M')} - {self.hora_cierre.strftime('%H:%M')}"
    
    def clean(self):
        """Validación personalizada"""
        super().clean()
        
        if not self.cerrado and self.hora_apertura >= self.hora_cierre:
            raise ValidationError({
                'hora_cierre': 'La hora de cierre debe ser posterior a la hora de apertura'
            })
    
    def get_horario_formateado(self):
        """Retorna el horario en formato legible"""
        if self.cerrado:
            return "Cerrado"
        return f"{self.hora_apertura.strftime('%H:%M')} - {self.hora_cierre.strftime('%H:%M')}"


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
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descripción de la Imagen'
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