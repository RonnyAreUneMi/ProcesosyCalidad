// ==================== VERIFICACIÓN DE DEPENDENCIAS ====================
(function() {
    'use strict';
    
    if (typeof Swal === 'undefined') {
        console.error('❌ SweetAlert2 no está cargado');
        return;
    }
    
    console.log('✅ SweetAlert2 detectado correctamente');
})();

// ==================== SISTEMA DE NOTIFICACIONES TOAST ====================
const Toast = Swal.mixin({
    toast: true,
    position: 'top-end',
    showConfirmButton: false,
    timer: 4000,
    timerProgressBar: true,
    didOpen: (toast) => {
        toast.addEventListener('mouseenter', Swal.stopTimer)
        toast.addEventListener('mouseleave', Swal.resumeTimer)
    },
    customClass: {
        popup: 'colored-toast'
    }
});

const Notificaciones = {
    mostrar(mensaje, tipo = 'info', duracion = 4000) {
        const iconos = {
            success: 'success',
            error: 'error',
            warning: 'warning',
            info: 'info'
        };
        
        Toast.fire({
            icon: iconos[tipo],
            title: mensaje,
            timer: duracion
        });
    }
};

// ==================== VALIDADOR DE COORDENADAS ====================
const ValidadorCoordenadas = {
    validar(input, tipo) {
        const value = input.value.trim();
        
        input.classList.remove('border-red-500', 'border-green-500');
        
        if (!value) {
            input.classList.add('border-red-500');
            return false;
        }
        
        const num = parseFloat(value);
        
        if (isNaN(num)) {
            input.classList.add('border-red-500');
            return false;
        }
        
        let valido = false;
        
        if (tipo === 'latitud') {
            valido = num >= -5 && num <= 2;
        } else {
            valido = num >= -92 && num <= -75;
        }
        
        if (valido) {
            input.classList.add('border-green-500');
        } else {
            input.classList.add('border-red-500');
        }
        
        return valido;
    },
    
    limpiarEstilos(input, tipo) {
        input.classList.remove('border-red-500', 'border-green-500');
    }
};

// ==================== VALIDADOR DE IMÁGENES ====================
const ValidadorImagenes = {
    MAX_SIZE: 5 * 1024 * 1024,
    FORMATOS_VALIDOS: ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'],
    
    validar(file) {
        if (file.size > this.MAX_SIZE) {
            return { 
                valido: false, 
                error: `"${file.name}" excede 5MB (${(file.size / 1024 / 1024).toFixed(2)}MB)`,
                tipo: 'tamaño'
            };
        }
        
        if (!this.FORMATOS_VALIDOS.includes(file.type.toLowerCase())) {
            return { 
                valido: false, 
                error: `"${file.name}" no es un formato válido`,
                tipo: 'formato'
            };
        }
        
        return { valido: true };
    },
    
    async mostrarErrores(archivosInvalidos, input) {
        const erroresPorTipo = {
            tamaño: archivosInvalidos.filter(a => a.tipo === 'tamaño'),
            formato: archivosInvalidos.filter(a => a.tipo === 'formato')
        };
        
        let html = '<div class="text-left">';
        
        if (erroresPorTipo.tamaño.length > 0) {
            html += `
                <div class="mb-4">
                    <p class="font-semibold text-red-600 mb-2">
                        <i class="fas fa-weight-hanging mr-2"></i>
                        Archivos muy pesados (límite: 5MB):
                    </p>
                    <ul class="list-disc list-inside space-y-1 text-sm">
                        ${erroresPorTipo.tamaño.map(a => `
                            <li class="text-gray-700">
                                <span class="font-medium">${a.nombre}</span>
                                <span class="text-red-500"> (${a.tamaño})</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
            `;
        }
        
        if (erroresPorTipo.formato.length > 0) {
            html += `
                <div class="mb-4">
                    <p class="font-semibold text-orange-600 mb-2">
                        <i class="fas fa-file-image mr-2"></i>
                        Formatos no válidos (solo JPG, PNG, GIF, WEBP):
                    </p>
                    <ul class="list-disc list-inside space-y-1 text-sm">
                        ${erroresPorTipo.formato.map(a => `
                            <li class="text-gray-700">${a.nombre}</li>
                        `).join('')}
                    </ul>
                </div>
            `;
        }
        
        html += `
            <div class="bg-blue-50 border-l-4 border-blue-500 p-3 mt-4 rounded">
                <p class="text-sm text-blue-800">
                    <i class="fas fa-info-circle mr-2"></i>
                    <strong>¿Qué deseas hacer?</strong>
                </p>
            </div>
        `;
        html += '</div>';
        
        const result = await Swal.fire({
            title: '⚠️ Algunas imágenes no son válidas',
            html: html,
            icon: 'warning',
            showCancelButton: true,
            showDenyButton: true,
            confirmButtonText: '<i class="fas fa-trash-alt mr-2"></i> Eliminar todas',
            denyButtonText: '<i class="fas fa-check-circle mr-2"></i> Mantener válidas',
            cancelButtonText: '<i class="fas fa-edit mr-2"></i> Corregir',
            confirmButtonColor: '#dc2626',
            denyButtonColor: '#059669',
            cancelButtonColor: '#3b82f6',
            customClass: {
                popup: 'swal-wide',
                confirmButton: 'order-3',
                denyButton: 'order-2',
                cancelButton: 'order-1'
            },
            buttonsStyling: true,
            allowOutsideClick: false,
            width: '600px'
        });
        
        if (result.isConfirmed) {
            input.value = '';
            const preview = document.getElementById('imagenesPreview');
            if (preview) {
                preview.innerHTML = '';
                preview.classList.add('hidden');
            }
            Toast.fire({
                icon: 'info',
                title: 'Todas las imágenes fueron eliminadas'
            });
        } else if (result.isDenied) {
            this.filtrarArchivosValidos(input, archivosInvalidos);
        } else {
            input.value = '';
            const preview = document.getElementById('imagenesPreview');
            if (preview) {
                preview.innerHTML = '';
                preview.classList.add('hidden');
            }
            
            setTimeout(() => {
                input.click();
                Toast.fire({
                    icon: 'info',
                    title: 'Selecciona nuevamente las imágenes correctas',
                    timer: 3000
                });
            }, 300);
        }
    },
    
    filtrarArchivosValidos(input, archivosInvalidos) {
        const dt = new DataTransfer();
        const nombresInvalidos = archivosInvalidos.map(a => a.nombre);
        
        Array.from(input.files).forEach(file => {
            if (!nombresInvalidos.includes(file.name)) {
                dt.items.add(file);
            }
        });
        
        input.files = dt.files;
        GestorImagenes.previsualizar(input);
        
        const cantidadValidas = dt.files.length;
        const cantidadInvalidas = archivosInvalidos.length;
        
        Swal.fire({
            title: '¡Listo!',
            html: `
                <div class="text-center">
                    <p class="text-lg mb-2">
                        <i class="fas fa-check-circle text-green-500 text-3xl mb-3"></i>
                    </p>
                    <p class="text-gray-700">
                        Se mantuvieron <strong class="text-green-600">${cantidadValidas} imagen(es) válida(s)</strong>
                    </p>
                    <p class="text-gray-500 text-sm mt-2">
                        ${cantidadInvalidas} imagen(es) fueron descartadas
                    </p>
                </div>
            `,
            icon: 'success',
            timer: 3000,
            showConfirmButton: false
        });
    }
};

// ==================== GESTOR DE PREVIEW DE IMÁGENES ====================
const GestorImagenes = {
    async previsualizar(input) {
        const preview = document.getElementById('imagenesPreview');
        if (!preview) return;
        
        if (!input.files || input.files.length === 0) {
            preview.innerHTML = '';
            preview.classList.add('hidden');
            return;
        }
        
        const archivosInvalidos = [];
        const archivosValidos = [];
        
        Array.from(input.files).forEach(file => {
            const resultado = ValidadorImagenes.validar(file);
            if (!resultado.valido) {
                archivosInvalidos.push({
                    nombre: file.name,
                    tamaño: (file.size / 1024 / 1024).toFixed(2) + 'MB',
                    tipo: resultado.tipo
                });
            } else {
                archivosValidos.push(file);
            }
        });
        
        if (archivosInvalidos.length > 0) {
            await ValidadorImagenes.mostrarErrores(archivosInvalidos, input);
            return;
        }
        
        preview.innerHTML = '';
        preview.classList.remove('hidden');
        
        archivosValidos.forEach((file, idx) => {
            const reader = new FileReader();
            
            reader.onload = (e) => {
                const div = document.createElement('div');
                div.className = 'relative group animate-fadeIn';
                div.innerHTML = `
                    <div class="aspect-square rounded-xl overflow-hidden shadow-lg border-2 border-gray-200 hover:border-sky-400 transition-all bg-gray-100">
                        <img src="${e.target.result}" 
                             class="w-full h-full object-cover transition-transform group-hover:scale-110"
                             alt="Preview ${idx + 1}">
                    </div>
                    ${idx === 0 ? `
                        <div class="absolute bottom-2 left-2">
                            <span class="px-3 py-1.5 bg-yellow-400 text-yellow-900 rounded-full text-xs font-bold shadow-lg flex items-center">
                                <i class="fas fa-star mr-1"></i> Principal
                            </span>
                        </div>
                    ` : ''}
                    <div class="absolute top-2 right-2">
                        <span class="px-2.5 py-1 bg-gray-900 bg-opacity-80 text-white rounded-lg text-xs font-bold">
                            ${idx + 1}
                        </span>
                    </div>
                    <div class="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-10 transition-all rounded-xl"></div>
                `;
                preview.appendChild(div);
            };
            
            reader.onerror = () => {
                Toast.fire({
                    icon: 'error',
                    title: `Error al cargar "${file.name}"`
                });
            };
            
            reader.readAsDataURL(file);
        });
        
        if (archivosValidos.length > 0) {
            Toast.fire({
                icon: 'success',
                title: `${archivosValidos.length} imagen(es) lista(s) para subir`,
                timer: 2000
            });
        }
    }
};

// ==================== GESTOR DE HORARIOS ====================
const GestorHorarios = {
    toggle(tipo) {
        const checkbox = document.getElementById(`cerrado_${tipo}`);
        const fields = document.getElementById(`horario_${tipo}_fields`);
        const msg = document.getElementById(`cerrado_${tipo}_msg`);
        
        if (!checkbox || !fields || !msg) return;
        
        if (checkbox.checked) {
            fields.classList.add('hidden');
            msg.classList.remove('hidden');
            fields.querySelectorAll('input').forEach(input => {
                input.disabled = true;
                input.required = false;
            });
        } else {
            fields.classList.remove('hidden');
            msg.classList.add('hidden');
            fields.querySelectorAll('input').forEach(input => {
                input.disabled = false;
            });
        }
    }
};

// ==================== GESTOR DE ELIMINACIÓN DE IMÁGENES ====================
const GestorEliminacion = {
    async confirmar(imagenId) {
        const result = await Swal.fire({
            title: '¿Eliminar esta imagen?',
            html: `
                <div class="text-center">
                    <i class="fas fa-trash-alt text-5xl text-red-500 mb-4"></i>
                    <p class="text-gray-600">Esta acción no se puede deshacer.</p>
                    <p class="text-gray-600 font-semibold mt-2">¿Estás seguro de continuar?</p>
                </div>
            `,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: '<i class="fas fa-trash-alt mr-2"></i> Sí, eliminar',
            cancelButtonText: '<i class="fas fa-times mr-2"></i> Cancelar',
            confirmButtonColor: '#dc2626',
            cancelButtonColor: '#6b7280',
            reverseButtons: true,
            customClass: {
                confirmButton: 'font-semibold',
                cancelButton: 'font-semibold'
            }
        });
        
        if (result.isConfirmed) {
            this.ejecutar(imagenId);
        }
    },
    
    async ejecutar(imagenId) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        try {
            const response = await fetch(`/servicios/imagen/${imagenId}/eliminar/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json',
                },
            });
            
            const data = await response.json();
            
            if (data.success) {
                const elemento = document.getElementById(`imagen-${imagenId}`);
                if (elemento) {
                    elemento.style.transition = 'all 0.3s ease';
                    elemento.style.opacity = '0';
                    elemento.style.transform = 'scale(0.8)';
                    setTimeout(() => elemento.remove(), 300);
                }
                
                await Swal.fire({
                    title: '¡Eliminada!',
                    text: 'La imagen se eliminó correctamente',
                    icon: 'success',
                    timer: 2000,
                    showConfirmButton: false
                });
            } else {
                await Swal.fire({
                    title: 'Error',
                    text: data.error || 'No se pudo eliminar la imagen',
                    icon: 'error',
                    confirmButtonText: 'Entendido',
                    confirmButtonColor: '#3b82f6'
                });
            }
        } catch (error) {
            console.error('Error:', error);
            await Swal.fire({
                title: 'Error de conexión',
                text: 'No se pudo conectar con el servidor',
                icon: 'error',
                confirmButtonText: 'Entendido',
                confirmButtonColor: '#3b82f6'
            });
        }
    }
};

// ==================== VALIDADOR DE FORMULARIO ====================
const ValidadorFormulario = {
    async validar(e) {
        const latInput = document.getElementById('latitud');
        const lngInput = document.getElementById('longitud');
        
        if (!latInput || !lngInput) {
            e.preventDefault();
            await Swal.fire({
                title: 'Error del sistema',
                text: 'No se encontraron los campos de coordenadas',
                icon: 'error',
                confirmButtonText: 'Entendido',
                confirmButtonColor: '#3b82f6'
            });
            return false;
        }
        
        const latValida = ValidadorCoordenadas.validar(latInput, 'latitud');
        const lngValida = ValidadorCoordenadas.validar(lngInput, 'longitud');
        
        if (!latValida || !lngValida) {
            e.preventDefault();
            
            let errores = [];
            if (!latValida) errores.push('• Latitud inválida (debe estar entre -5° y 2°)');
            if (!lngValida) errores.push('• Longitud inválida (debe estar entre -92° y -75°)');
            
            const result = await Swal.fire({
                title: '⚠️ Coordenadas incorrectas',
                html: `
                    <div class="text-left">
                        <p class="text-gray-700 mb-3">Se encontraron los siguientes errores:</p>
                        <div class="bg-red-50 border-l-4 border-red-500 p-4 mb-4 rounded">
                            ${errores.map(e => `<p class="text-red-700 text-sm mb-1">${e}</p>`).join('')}
                        </div>
                        <p class="text-sm text-gray-600">
                            <i class="fas fa-info-circle text-blue-500 mr-2"></i>
                            Las coordenadas deben corresponder a ubicaciones dentro de Ecuador
                        </p>
                    </div>
                `,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: '<i class="fas fa-edit mr-2"></i> Corregir ahora',
                cancelButtonText: '<i class="fas fa-times mr-2"></i> Cancelar',
                confirmButtonColor: '#3b82f6',
                cancelButtonColor: '#6b7280',
                reverseButtons: true,
                customClass: {
                    confirmButton: 'font-semibold',
                    cancelButton: 'font-semibold'
                }
            });
            
            if (result.isConfirmed) {
                if (!latValida) {
                    latInput.focus();
                    latInput.select();
                } else if (!lngValida) {
                    lngInput.focus();
                    lngInput.select();
                }
            }
            
            return false;
        }
        
        return true;
    }
};

// ==================== CONTADOR DE CARACTERES ====================
const ContadorCaracteres = {
    init() {
        const descripcion = document.getElementById('descripcion');
        const charCount = document.getElementById('charCount');
        
        if (descripcion && charCount) {
            descripcion.addEventListener('input', function() {
                const length = this.value.length;
                charCount.textContent = length;
                
                if (length > 900) {
                    charCount.className = 'text-xs text-red-600 font-bold';
                } else if (length > 700) {
                    charCount.className = 'text-xs text-yellow-600 font-semibold';
                } else {
                    charCount.className = 'text-xs text-gray-500';
                }
            });
        }
    }
};

// ==================== DRAG AND DROP ====================
const DragAndDrop = {
    init() {
        const dropZone = document.querySelector('.border-dashed');
        const inputImagenes = document.getElementById('imagenes');
        
        if (!dropZone || !inputImagenes) return;
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.add('border-sky-500', 'bg-sky-50');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.remove('border-sky-500', 'bg-sky-50');
            });
        });

        dropZone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            inputImagenes.files = files;
            GestorImagenes.previsualizar(inputImagenes);
        });
    }
};

// ==================== FUNCIONES GLOBALES ====================
function eliminarImagen(imagenId) {
    GestorEliminacion.confirmar(imagenId);
}

function toggleHorarioSemana() {
    GestorHorarios.toggle('semana');
}

function toggleHorarioFinde() {
    GestorHorarios.toggle('finde');
}

function previsualizarImagenes(input) {
    GestorImagenes.previsualizar(input);
}

function validarFormulario(e) {
    return ValidadorFormulario.validar(e);
}

function mostrarNotificacion(mensaje, tipo, duracion) {
    Notificaciones.mostrar(mensaje, tipo, duracion);
}

// ==================== INICIALIZACIÓN ====================
document.addEventListener('DOMContentLoaded', function() {
    if (typeof Swal === 'undefined') {
        console.error('❌ SweetAlert2 no está cargado. Por favor incluye el CDN de SweetAlert2');
        alert('Error: SweetAlert2 no está cargado. Revisa la consola para más detalles.');
        return;
    }
    
    ContadorCaracteres.init();
    
    const latInput = document.getElementById('latitud');
    const lngInput = document.getElementById('longitud');
    
    if (latInput) {
        latInput.addEventListener('blur', () => ValidadorCoordenadas.validar(latInput, 'latitud'));
        latInput.addEventListener('input', () => ValidadorCoordenadas.limpiarEstilos(latInput, 'latitud'));
    }
    
    if (lngInput) {
        lngInput.addEventListener('blur', () => ValidadorCoordenadas.validar(lngInput, 'longitud'));
        lngInput.addEventListener('input', () => ValidadorCoordenadas.limpiarEstilos(lngInput, 'longitud'));
    }
    
    const cerradoSemana = document.getElementById('cerrado_semana');
    const cerradoFinde = document.getElementById('cerrado_finde');
    
    if (cerradoSemana) {
        cerradoSemana.addEventListener('change', toggleHorarioSemana);
        toggleHorarioSemana();
    }
    
    if (cerradoFinde) {
        cerradoFinde.addEventListener('change', toggleHorarioFinde);
        toggleHorarioFinde();
    }
    
    const inputImagenes = document.getElementById('imagenes');
    if (inputImagenes) {
        inputImagenes.addEventListener('change', function() {
            previsualizarImagenes(this);
        });
    }
    
    const form = document.getElementById('servicioForm');
    if (form) {
        form.addEventListener('submit', validarFormulario);
    }
    
    DragAndDrop.init();
    
    console.log('%c✨ Sistema Inicializado', 'color: #3b82f6; font-size: 14px; font-weight: bold');
});