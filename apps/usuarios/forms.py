from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from .models import Usuario, Rol


class LoginForm(AuthenticationForm):
    """
    Formulario de inicio de sesión personalizado
    RF-001: Autenticación de usuarios
    """
    username = forms.EmailField(
        label='Correo Electrónico',
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition',
            'placeholder': 'tu@email.com',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition',
            'placeholder': '••••••••',
        })
    )
    
    error_messages = {
        'invalid_login': 'Correo o contraseña incorrectos. Por favor, inténtalo de nuevo.',
        'inactive': 'Esta cuenta ha sido desactivada.',
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remover labels por defecto si se desea
        # self.fields['username'].label = ''
        # self.fields['password'].label = ''


class RegisterForm(UserCreationForm):
    """
    Formulario de registro de nuevos usuarios
    RF-001: Registro de usuario con validación
    """
    nombre = forms.CharField(
        max_length=150,
        required=True,
        label='Nombre Completo',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition',
            'placeholder': 'Tu nombre completo',
        })
    )
    correo = forms.EmailField(
        max_length=255,
        required=True,
        label='Correo Electrónico',
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition',
            'placeholder': 'tu@email.com',
        })
    )
    telefono = forms.CharField(
        max_length=15,
        required=False,
        label='Teléfono (Opcional)',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition',
            'placeholder': '0999999999',
        })
    )
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition',
            'placeholder': 'Mínimo 8 caracteres',
        }),
        help_text='La contraseña debe tener al menos 8 caracteres y no puede ser completamente numérica.'
    )
    password2 = forms.CharField(
        label='Confirmar Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition',
            'placeholder': 'Repite tu contraseña',
        })
    )
    
    # Campo opcional para seleccionar rol (solo visible para admins o en casos específicos)
    rol = forms.ModelChoiceField(
        queryset=Rol.objects.filter(activo=True),
        required=False,
        label='Tipo de Cuenta',
        empty_label='Turista (por defecto)',
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition',
        }),
        help_text='Selecciona "Proveedor" si deseas registrar servicios turísticos'
    )
    
    class Meta:
        model = Usuario
        fields = ('nombre', 'correo', 'telefono', 'rol', 'password1', 'password2')
    
    def clean_correo(self):
        """
        Valida que el correo no esté registrado
        RF-001: Validación de email único
        """
        correo = self.cleaned_data.get('correo')
        if Usuario.objects.filter(correo=correo).exists():
            raise ValidationError(
                'Este correo electrónico ya está registrado. '
                'Por favor, usa otro o inicia sesión.'
            )
        return correo.lower()
    
    def clean_password2(self):
        """
        Valida que ambas contraseñas coincidan
        """
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError('Las contraseñas no coinciden.')
        
        return password2
    
    def clean_telefono(self):
        """
        Valida formato básico de teléfono ecuatoriano
        """
        telefono = self.cleaned_data.get('telefono')
        if telefono:
            # Remover espacios y guiones
            telefono = telefono.replace(' ', '').replace('-', '')
            # Validar que solo contenga números
            if not telefono.isdigit():
                raise ValidationError('El teléfono debe contener solo números.')
            # Validar longitud (celular Ecuador: 10 dígitos)
            if len(telefono) not in [9, 10]:
                raise ValidationError('El teléfono debe tener 9 o 10 dígitos.')
        return telefono
    
    def save(self, commit=True):
        """
        Guarda el usuario con el rol asignado
        RF-001: Asignación automática de rol "turista"
        """
        user = super().save(commit=False)
        user.correo = self.cleaned_data['correo']
        user.nombre = self.cleaned_data['nombre']
        user.telefono = self.cleaned_data.get('telefono', '')
        
        # Asignar rol seleccionado o turista por defecto
        if self.cleaned_data.get('rol'):
            user.rol = self.cleaned_data['rol']
        else:
            # Asignar rol turista por defecto
            rol_turista, created = Rol.objects.get_or_create(
                nombre=Rol.TURISTA,
                defaults={'descripcion': 'Usuario turista con permisos básicos'}
            )
            user.rol = rol_turista
        
        if commit:
            user.save()
        return user


class CambioRolForm(forms.Form):
    """
    Formulario para cambiar el rol de un usuario
    Solo accesible por administradores
    """
    usuario = forms.ModelChoiceField(
        queryset=Usuario.objects.all(),
        required=True,
        label='Usuario',
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 outline-none transition',
        })
    )
    nuevo_rol = forms.ModelChoiceField(
        queryset=Rol.objects.filter(activo=True),
        required=True,
        label='Nuevo Rol',
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 outline-none transition',
        })
    )
    motivo = forms.CharField(
        required=False,
        label='Motivo del Cambio (Opcional)',
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 outline-none transition resize-none',
            'rows': 3,
            'placeholder': 'Describe brevemente el motivo del cambio de rol...'
        })
    )
    
    def clean(self):
        """
        Validaciones adicionales del formulario
        """
        cleaned_data = super().clean()
        usuario = cleaned_data.get('usuario')
        nuevo_rol = cleaned_data.get('nuevo_rol')
        
        if usuario and nuevo_rol:
            if usuario.rol == nuevo_rol:
                raise ValidationError(
                    f'El usuario ya tiene el rol de {nuevo_rol.get_nombre_display()}.'
                )
        
        return cleaned_data


class PerfilUsuarioForm(forms.ModelForm):
    """
    Formulario para editar perfil de usuario
    """
    class Meta:
        model = Usuario
        fields = ['nombre', 'telefono']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 outline-none transition',
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 outline-none transition',
            }),
        }
# usuarios/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Usuario, Rol
class PerfilUsuarioForm(forms.ModelForm):
    """
    Formulario para editar el perfil del usuario
    """
    password_actual = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña actual'
        }),
        label='Contraseña Actual'
    )
    password1 = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nueva contraseña'
        }),
        label='Nueva Contraseña'
    )
    password2 = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmar contraseña'
        }),
        label='Confirmar Contraseña'
    )
    
    class Meta:
        model = Usuario
        fields = ['nombre', 'correo', 'telefono']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre completo'
            }),
            'correo': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'correo@ejemplo.com'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+593 99 123 4567'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        password_actual = cleaned_data.get('password_actual')
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        # Si se quiere cambiar la contraseña
        if password1 or password2:
            if not password_actual:
                raise forms.ValidationError(
                    'Debes ingresar tu contraseña actual para cambiarla.'
                )
            
            if password1 != password2:
                raise forms.ValidationError(
                    'Las contraseñas no coinciden.'
                )
            
            if len(password1) < 8:
                raise forms.ValidationError(
                    'La contraseña debe tener al menos 8 caracteres.'
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        password1 = self.cleaned_data.get('password1')
        
        # Cambiar contraseña si se proporcionó una nueva
        if password1:
            user.set_password(password1)
        
        if commit:
            user.save()
        return user