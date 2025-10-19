from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.usuarios.models import Usuario
from apps.servicios.models import Servicio


class Calificacion(models.Model):
    """
    Modelo para calificaciones y reseñas de servicios turísticos
    RF-006: Sistema de Calificaciones Dinámico
    """
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='calificaciones',
        verbose_name='Usuario'
    )
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name='calificaciones',
        verbose_name='Servicio'
    )
    puntuacion = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Puntuación',
        help_text='Calificación de 1 a 5 estrellas'
    )
    comentario = models.TextField(
        blank=True,
        null=True,
        verbose_name='Comentario'
    )
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
        verbose_name='Activo',
        help_text='Desactivar si el comentario es ofensivo'
    )
    moderado = models.BooleanField(
        default=False,
        verbose_name='Moderado',
        help_text='Indica si el comentario fue revisado por moderación'
    )
    
    class Meta:
        db_table = 'calificaciones'
        verbose_name = 'Calificación'
        verbose_name_plural = 'Calificaciones'
        ordering = ['-fecha_creacion']
        unique_together = [['usuario', 'servicio']]
        indexes = [
            models.Index(fields=['servicio', 'activo']),
            models.Index(fields=['puntuacion']),
        ]
    
    def __str__(self):
        return f"{self.usuario.nombre} - {self.servicio.nombre} ({self.puntuacion}★)"
    
    def save(self, *args, **kwargs):
        """
        Al guardar, actualizar las calificaciones del servicio y destino
        """
        super().save(*args, **kwargs)
        
        # Solo actualizar si no es una actualización parcial de campos específicos
        if 'update_fields' not in kwargs:
            self._actualizar_calificaciones()
    
    def delete(self, *args, **kwargs):
        """
        Al eliminar, actualizar las calificaciones del servicio y destino
        """
        servicio = self.servicio
        destino = servicio.destino if hasattr(servicio, 'destino') and servicio.destino else None
        
        super().delete(*args, **kwargs)
        
        # Actualizar después de eliminar
        if servicio:
            try:
                servicio.actualizar_calificacion()
            except Exception:
                pass
        
        if destino:
            try:
                destino.actualizar_calificacion()
            except Exception:
                pass
    
    def _actualizar_calificaciones(self):
        """
        Método auxiliar para actualizar servicio y destino en cascada
        """
        try:
            # Actualizar servicio
            self.servicio.actualizar_calificacion()
            
            # Actualizar destino si existe
            if hasattr(self.servicio, 'destino') and self.servicio.destino:
                self.servicio.destino.actualizar_calificacion()
        except Exception as e:
            # Log el error pero no fallar la transacción principal
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error actualizando calificaciones en cascada: {str(e)}")


class RespuestaCalificacion(models.Model):
    """
    Modelo para respuestas de proveedores a calificaciones
    """
    calificacion = models.OneToOneField(
        Calificacion,
        on_delete=models.CASCADE,
        related_name='respuesta',
        verbose_name='Calificación'
    )
    proveedor = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='respuestas_calificaciones',
        limit_choices_to={'rol__nombre': 'proveedor'},
        verbose_name='Proveedor'
    )
    respuesta = models.TextField(
        verbose_name='Respuesta'
    )
    fecha_respuesta = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Respuesta'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    
    class Meta:
        db_table = 'respuestas_calificacion'
        verbose_name = 'Respuesta a Calificación'
        verbose_name_plural = 'Respuestas a Calificaciones'
        ordering = ['-fecha_respuesta']
    
    def __str__(self):
        return f"Respuesta de {self.proveedor.nombre} a calificación #{self.calificacion.id}"