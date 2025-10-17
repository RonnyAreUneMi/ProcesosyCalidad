# Script para agregar categorías de destinos turísticos
# Guardar como: scripts/agregar_categorias.py
# Ejecutar con: python manage.py shell < scripts/agregar_categorias.py

from apps.destinos.models import Categoria

def agregar_categorias():
    """
    Agrega categorías iniciales para destinos turísticos en Ecuador
    """
    categorias = [
        {
            'nombre': 'Playas',
            'descripcion': 'Hermosas playas y destinos costeros del Ecuador',
            'icono': 'fas fa-umbrella-beach',
        },
        {
            'nombre': 'Montañas',
            'descripcion': 'Destinos de montaña, volcanes y paisajes andinos',
            'icono': 'fas fa-mountain',
        },
        {
            'nombre': 'Sitios Históricos',
            'descripcion': 'Lugares con valor histórico y patrimonial',
            'icono': 'fas fa-landmark',
        },
        {
            'nombre': 'Parques Nacionales',
            'descripcion': 'Áreas naturales protegidas y reservas ecológicas',
            'icono': 'fas fa-tree',
        },
        {
            'nombre': 'Aventura',
            'descripcion': 'Destinos para deportes extremos y actividades de aventura',
            'icono': 'fas fa-hiking',
        },
        {
            'nombre': 'Cultura',
            'descripcion': 'Pueblos, tradiciones y expresiones culturales',
            'icono': 'fas fa-theater-masks',
        },
        {
            'nombre': 'Ecoturismo',
            'descripcion': 'Turismo sostenible en contacto con la naturaleza',
            'icono': 'fas fa-leaf',
        },
        {
            'nombre': 'Gastronomía',
            'descripcion': 'Destinos reconocidos por su oferta gastronómica',
            'icono': 'fas fa-utensils',
        },
        {
            'nombre': 'Termas y Balnearios',
            'descripcion': 'Aguas termales y centros de relajación',
            'icono': 'fas fa-hot-tub',
        },
        {
            'nombre': 'Lagos y Ríos',
            'descripcion': 'Destinos con lagos, lagunas y ríos',
            'icono': 'fas fa-water',
        },
        {
            'nombre': 'Islas',
            'descripcion': 'Destinos insulares y archipiélagos',
            'icono': 'fas fa-island-tropical',
        },
        {
            'nombre': 'Ciudades',
            'descripcion': 'Ciudades con atractivos turísticos urbanos',
            'icono': 'fas fa-city',
        },
    ]
    
    categorias_creadas = 0
    categorias_existentes = 0
    
    print("Iniciando creación de categorías...")
    print("-" * 50)
    
    for cat_data in categorias:
        categoria, created = Categoria.objects.get_or_create(
            nombre=cat_data['nombre'],
            defaults={
                'descripcion': cat_data['descripcion'],
                'icono': cat_data['icono'],
                'activo': True
            }
        )
        
        if created:
            categorias_creadas += 1
            print(f"✓ Creada: {categoria.nombre}")
        else:
            categorias_existentes += 1
            print(f"○ Ya existe: {categoria.nombre}")
    
    print("-" * 50)
    print(f"Proceso completado:")
    print(f"  - Categorías creadas: {categorias_creadas}")
    print(f"  - Categorías ya existentes: {categorias_existentes}")
    print(f"  - Total de categorías: {Categoria.objects.count()}")

# Ejecutar la función
if __name__ == '__main__':
    agregar_categorias()