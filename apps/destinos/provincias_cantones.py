
PROVINCIAS_CANTONES = {
    'Azuay': [
        'Cuenca', 'Girón', 'Gualaceo', 'Nabón', 'Paute', 'Pucará', 
        'San Fernando', 'Santa Isabel', 'Sigsig', 'Oña', 'Chordeleg',
        'El Pan', 'Sevilla de Oro', 'Guachapala', 'Camilo Ponce Enríquez'
    ],
    'Bolívar': [
        'Guaranda', 'Chillanes', 'Chimbo', 'Echeandía', 'San Miguel',
        'Caluma', 'Las Naves'
    ],
    'Cañar': [
        'Azogues', 'Biblián', 'Cañar', 'La Troncal', 'El Tambo',
        'Déleg', 'Suscal'
    ],
    'Carchi': [
        'Tulcán', 'Bolívar', 'Espejo', 'Mira', 'Montúfar', 'San Pedro de Huaca'
    ],
    'Chimborazo': [
        'Riobamba', 'Alausí', 'Colta', 'Chambo', 'Chunchi', 'Guamote',
        'Guano', 'Pallatanga', 'Penipe', 'Cumandá'
    ],
    'Cotopaxi': [
        'Latacunga', 'La Maná', 'Pangua', 'Pujilí', 'Salcedo',
        'Saquisilí', 'Sigchos'
    ],
    'El Oro': [
        'Machala', 'Arenillas', 'Atahualpa', 'Balsas', 'Chilla', 'El Guabo',
        'Huaquillas', 'Marcabelí', 'Pasaje', 'Piñas', 'Portovelo',
        'Santa Rosa', 'Zaruma', 'Las Lajas'
    ],
    'Esmeraldas': [
        'Esmeraldas', 'Eloy Alfaro', 'Muisne', 'Quinindé', 'San Lorenzo',
        'Atacames', 'Rioverde', 'La Concordia'
    ],
    'Galápagos': [
        'Puerto Baquerizo Moreno', 'Puerto Ayora', 'Puerto Villamil'
    ],
    'Guayas': [
        'Guayaquil', 'Alfredo Baquerizo Moreno', 'Balao', 'Balzar', 'Colimes',
        'Daule', 'Durán', 'El Empalme', 'El Triunfo', 'Milagro', 'Naranjal',
        'Naranjito', 'Palestina', 'Pedro Carbo', 'Samborondón', 'Santa Lucía',
        'Salitre', 'San Jacinto de Yaguachi', 'Playas', 'Simón Bolívar',
        'Coronel Marcelino Maridueña', 'Lomas de Sargentillo', 'Nobol',
        'General Antonio Elizalde', 'Isidro Ayora'
    ],
    'Imbabura': [
        'Ibarra', 'Antonio Ante', 'Cotacachi', 'Otavalo', 'Pimampiro',
        'San Miguel de Urcuquí'
    ],
    'Loja': [
        'Loja', 'Calvas', 'Catamayo', 'Celica', 'Chaguarpamba', 'Espíndola',
        'Gonzanamá', 'Macará', 'Paltas', 'Puyango', 'Saraguro',
        'Sozoranga', 'Zapotillo', 'Pindal', 'Quilanga', 'Olmedo'
    ],
    'Los Ríos': [
        'Babahoyo', 'Baba', 'Montalvo', 'Puebloviejo', 'Quevedo', 'Urdaneta',
        'Ventanas', 'Vinces', 'Palenque', 'Buena Fe', 'Valencia', 'Mocache',
        'Quinsaloma'
    ],
    'Manabí': [
        'Portoviejo', 'Bolívar', 'Chone', 'El Carmen', 'Flavio Alfaro',
        'Jipijapa', 'Junín', 'Manta', 'Montecristi', 'Paján', 'Pichincha',
        'Rocafuerte', 'Santa Ana', 'Sucre', 'Tosagua', 'Veinticuatro de Mayo',
        'Pedernales', 'Olmedo', 'Puerto López', 'Jama', 'Jaramijó', 'San Vicente'
    ],
    'Morona Santiago': [
        'Macas', 'Gualaquiza', 'Limón Indanza', 'Palora', 'Santiago',
        'Sucúa', 'Huamboya', 'San Juan Bosco', 'Taisha', 'Logroño',
        'Pablo Sexto', 'Tiwintza'
    ],
    'Napo': [
        'Tena', 'Archidona', 'El Chaco', 'Quijos', 'Carlos Julio Arosemena Tola'
    ],
    'Orellana': [
        'Francisco de Orellana', 'Aguarico', 'La Joya de los Sachas', 'Loreto'
    ],
    'Pastaza': [
        'Puyo', 'Arajuno', 'Mera', 'Santa Clara'
    ],
    'Pichincha': [
        'Quito', 'Cayambe', 'Mejía', 'Pedro Moncayo', 'Rumiñahui',
        'San Miguel de los Bancos', 'Pedro Vicente Maldonado', 'Puerto Quito'
    ],
    'Santa Elena': [
        'Santa Elena', 'La Libertad', 'Salinas'
    ],
    'Santo Domingo de los Tsáchilas': [
        'Santo Domingo'
    ],
    'Sucumbíos': [
        'Nueva Loja', 'Gonzalo Pizarro', 'Putumayo', 'Shushufindi',
        'Sucumbíos', 'Cascales', 'Cuyabeno'
    ],
    'Tungurahua': [
        'Ambato', 'Baños de Agua Santa', 'Cevallos', 'Mocha', 'Patate',
        'Quero', 'Pelileo', 'Píllaro', 'Tisaleo'
    ],
    'Zamora Chinchipe': [
        'Zamora', 'Chinchipe', 'Nangaritza', 'Yacuambi', 'Yantzaza',
        'El Pangui', 'Centinela del Cóndor', 'Palanda', 'Paquisha'
    ]
}

def get_provincias():
    """Retorna lista de provincias ordenadas alfabéticamente"""
    return sorted(PROVINCIAS_CANTONES.keys())

def get_cantones(provincia):
    """Retorna lista de cantones para una provincia específica"""
    return sorted(PROVINCIAS_CANTONES.get(provincia, []))

def get_provincias_cantones_json():
    """Retorna el diccionario completo para usar en JavaScript"""
    import json
    return json.dumps(PROVINCIAS_CANTONES, ensure_ascii=False)