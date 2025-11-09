from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from apps.usuarios.models import Usuario
from apps.servicios.models import Servicio


class Reserva(models.Model):
    """
    Modelo para reservas de servicios turísticos
    RF-003: Sistema de Reservas con Cálculo Dinámico
    """
    PENDIENTE = 'pendiente'
    CONFIRMADA = 'confirmada'
    CANCELADA = 'cancelada'
    COMPLETADA = 'completada'
    
    ESTADO_CHOICES = [
        (PENDIENTE, 'Pendiente'),
        (CONFIRMADA, 'Confirmada'),
        (CANCELADA, 'Cancelada'),
        (COMPLETADA, 'Completada'),
    ]
    
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='reservas',
        verbose_name='Usuario'
    )
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.PROTECT,
        related_name='reservas',
        verbose_name='Servicio'
    )
    fecha_reserva = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Reserva'
    )
    fecha_servicio = models.DateField(
        verbose_name='Fecha del Servicio',
        help_text='Fecha en que se prestará el servicio'
    )
    cantidad_personas = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Cantidad de Personas'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=PENDIENTE,
        verbose_name='Estado'
    )
    
    # Costos
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Precio Unitario (USD)',
        help_text='Precio del servicio al momento de la reserva'
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Subtotal (USD)'
    )
    impuestos = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Impuestos (USD)',
        help_text='12% IVA'
    )
    costo_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Costo Total (USD)'
    )
    
    # Información adicional
    notas = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas Adicionales'
    )
    codigo_reserva = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name='Código de Reserva'
    )
    
    # Metadatos
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    fecha_cancelacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Cancelación'
    )
    motivo_cancelacion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Motivo de Cancelación'
    )
    
    class Meta:
        db_table = 'reservas'
        verbose_name = 'Reserva'
        verbose_name_plural = 'Reservas'
        ordering = ['-fecha_reserva']
        indexes = [
            models.Index(fields=['usuario', 'estado']),
            models.Index(fields=['fecha_servicio']),
            models.Index(fields=['estado']),
            models.Index(fields=['codigo_reserva']),
        ]
    
    def __str__(self):
        return f"Reserva #{self.codigo_reserva} - {self.usuario.nombre}"
    
    def save(self, *args, **kwargs):
        """
        Genera código de reserva y calcula totales
        """
        # Generar código de reserva si no existe
        if not self.codigo_reserva:
            import random
            import string
            self.codigo_reserva = ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            )
        
        # Calcular totales usando Decimal con cuantización
        TASA_IVA = Decimal('0.12')  # 12% IVA
        self.precio_unitario = self.servicio.precio
        
        # Cuantizar cada operación para evitar pérdida de precisión
        self.subtotal = (self.precio_unitario * self.cantidad_personas).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        self.impuestos = (self.subtotal * TASA_IVA).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        self.costo_total = (self.subtotal + self.impuestos).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        super().save(*args, **kwargs)
    
    def confirmar(self):
        """Confirma la reserva"""
        from django.db import transaction
        
        if self.estado != self.PENDIENTE:
            raise ValueError("Solo se pueden confirmar reservas pendientes")
            
        with transaction.atomic():
            self.estado = self.CONFIRMADA
            self.fecha_actualizacion = timezone.now()
            self.save(update_fields=['estado', 'fecha_actualizacion'])
    
    def cancelar(self, motivo=''):
        """Cancela la reserva"""
        self.estado = self.CANCELADA
        self.fecha_cancelacion = timezone.now()
        self.motivo_cancelacion = motivo
        self.save(update_fields=['estado', 'fecha_cancelacion', 'motivo_cancelacion'])
    
    def completar(self):
        """Marca la reserva como completada"""
        self.estado = self.COMPLETADA
        self.save(update_fields=['estado'])
    
    def puede_calificar(self):
        """
        Verifica si la reserva puede ser calificada
        Solo reservas completadas pueden ser calificadas
        """
        return self.estado == self.COMPLETADA
    
    def esta_activa(self):
        """Verifica si la reserva está activa"""
        return self.estado in [self.PENDIENTE, self.CONFIRMADA]


class ItemCarrito(models.Model):
    """
    Modelo para items del carrito de compras (basado en sesión)
    RF-003: Sistema de Reservas con Cálculo Dinámico
    """
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='carrito',
        verbose_name='Usuario'
    )
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        verbose_name='Servicio'
    )
    cantidad_personas = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Cantidad de Personas'
    )
    fecha_servicio = models.DateField(
        verbose_name='Fecha del Servicio'
    )
    fecha_agregado = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha Agregado'
    )
    
    class Meta:
        db_table = 'items_carrito'
        verbose_name = 'Item de Carrito'
        verbose_name_plural = 'Items de Carrito'
        unique_together = [['usuario', 'servicio', 'fecha_servicio']]
        ordering = ['-fecha_agregado']
    
    def __str__(self):
        return f"{self.servicio.nombre} - {self.cantidad_personas} persona(s)"
    
    def get_subtotal(self):
        """Calcula el subtotal del item con precisión"""
        subtotal = self.servicio.precio * self.cantidad_personas
        return subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def get_impuestos(self):
        """Calcula los impuestos (12% IVA) con precisión"""
        TASA_IVA = Decimal('0.12')
        impuestos = self.get_subtotal() * TASA_IVA
        return impuestos.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def get_total(self):
        """Calcula el total del item con precisión"""
        total = self.get_subtotal() + self.get_impuestos()
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)