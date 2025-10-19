# Generated migration file
# Ejecutar: python manage.py makemigrations
# Luego: python manage.py migrate

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('servicios', '0001_initial'),  # Ajusta según tu última migración
    ]

    operations = [
        # Agregar campos de geolocalización
        migrations.AddField(
            model_name='servicio',
            name='direccion',
            field=models.CharField(default='', help_text='Ej: Charles Darwin Ave., Puerto Ayora 200102 Ecuador', max_length=500, verbose_name='Dirección Completa'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='servicio',
            name='latitud',
            field=models.DecimalField(decimal_places=8, default=0, help_text='Coordenada latitud (-90 a 90)', max_digits=10, validators=[django.core.validators.MinValueValidator(-90), django.core.validators.MaxValueValidator(90)], verbose_name='Latitud'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='servicio',
            name='longitud',
            field=models.DecimalField(decimal_places=8, default=0, help_text='Coordenada longitud (-180 a 180)', max_digits=11, validators=[django.core.validators.MinValueValidator(-180), django.core.validators.MaxValueValidator(180)], verbose_name='Longitud'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='servicio',
            name='zona_referencia',
            field=models.CharField(blank=True, help_text='Ej: Cerca del muelle principal, Frente al parque central', max_length=200, null=True, verbose_name='Zona de Referencia'),
        ),
        
        # Agregar campos de contacto
        migrations.AddField(
            model_name='servicio',
            name='telefono',
            field=models.CharField(default='+593000000000', help_text='Formato: +593981234567', max_length=17, validators=[django.core.validators.RegexValidator(message="El número de teléfono debe estar en formato: '+593981234567' o '0981234567'", regex='^\\+?1?\\d{9,15}$')], verbose_name='Teléfono de Contacto'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='servicio',
            name='telefono_alternativo',
            field=models.CharField(blank=True, max_length=17, null=True, validators=[django.core.validators.RegexValidator(message="El número de teléfono debe estar en formato: '+593981234567' o '0981234567'", regex='^\\+?1?\\d{9,15}$')], verbose_name='Teléfono Alternativo'),
        ),
        migrations.AddField(
            model_name='servicio',
            name='email_contacto',
            field=models.EmailField(default='contacto@ejemplo.com', help_text='Email para consultas y reservas', max_length=254, verbose_name='Email de Contacto'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='servicio',
            name='sitio_web',
            field=models.URLField(blank=True, help_text='URL del sitio web (opcional)', null=True, verbose_name='Sitio Web'),
        ),
        migrations.AddField(
            model_name='servicio',
            name='whatsapp',
            field=models.CharField(blank=True, help_text='Número de WhatsApp (opcional)', max_length=17, null=True, validators=[django.core.validators.RegexValidator(message="El número de teléfono debe estar en formato: '+593981234567' o '0981234567'", regex='^\\+?1?\\d{9,15}$')], verbose_name='WhatsApp'),
        ),
        
        # Agregar descripción a imágenes
        migrations.AddField(
            model_name='imagenservicio',
            name='descripcion',
            field=models.TextField(blank=True, null=True, verbose_name='Descripción de la Imagen'),
        ),
        
        # Agregar índice para coordenadas
        migrations.AddIndex(
            model_name='servicio',
            index=models.Index(fields=['latitud', 'longitud'], name='servicios_latitud_longitud_idx'),
        ),
        
        # Crear modelo HorarioAtencion
        migrations.CreateModel(
            name='HorarioAtencion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_horario', models.CharField(choices=[('lunes_viernes', 'Lunes a Viernes'), ('sabado_domingo', 'Sábado y Domingo')], max_length=20, verbose_name='Tipo de Horario')),
                ('hora_apertura', models.TimeField(help_text='Formato 24 horas: 08:00', verbose_name='Hora de Apertura')),
                ('hora_cierre', models.TimeField(help_text='Formato 24 horas: 23:00', verbose_name='Hora de Cierre')),
                ('cerrado', models.BooleanField(default=False, help_text='Marcar si el servicio está cerrado en este horario', verbose_name='Cerrado')),
                ('notas', models.CharField(blank=True, help_text='Ej: Horario extendido en temporada alta', max_length=200, null=True, verbose_name='Notas')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('servicio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='horarios', to='servicios.servicio', verbose_name='Servicio')),
            ],
            options={
                'verbose_name': 'Horario de Atención',
                'verbose_name_plural': 'Horarios de Atención',
                'db_table': 'horarios_atencion',
                'ordering': ['tipo_horario', 'hora_apertura'],
                'unique_together': {('servicio', 'tipo_horario')},
            },
        ),
    ]