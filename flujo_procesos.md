flowchart TD
    Start([Ingreso al Sistema]):::inicio
    Start --> AuthCheck{Usuario<br/>Autenticado}:::decision
    
    %% USUARIO ANÓNIMO
    AuthCheck -->|No| Anon[Usuario Anónimo]:::anon
    Anon --> AnonHome[Visualizar Página Principal<br/>y Destinos]:::anon
    Anon --> AnonSearch[Buscar Servicios<br/>y Destinos]:::anon
    AnonHome --> AnonDetail[Consultar Detalle<br/>de Servicio]:::anon
    AnonSearch --> AnonDetail
    AnonDetail --> AnonRequire[Validación de<br/>Autenticación Requerida]:::anon
    AnonRequire --> AnonRedirect([Redirección a<br/>Inicio de Sesión]):::anon
    
    %% VERIFICAR ROL
    AuthCheck -->|Sí| RoleCheck{Verificación<br/>de Rol}:::decision
    
    %% TURISTA
    RoleCheck -->|Turista| Tourist[ROL: TURISTA]:::turista
    Tourist --> TSearch[Búsqueda de Servicios]:::turista
    TSearch --> TDetail[Consulta de Detalle]:::turista
    TDetail --> TCart[Agregar a Carrito]:::turista
    TCart --> TViewCart[Gestión de Carrito]:::turista
    TViewCart --> TConfirm{Confirmar<br/>Reserva}:::turista
    TConfirm -->|Confirmar| TCreate[Crear Reserva<br/>Estado: Pendiente]:::turista
    TConfirm -->|Modificar| TViewCart
    TCreate --> TMyBookings[Historial de Reservas]:::turista
    TMyBookings --> TCompleted{Estado de<br/>Reserva}:::turista
    TCompleted -->|Completada| TRate[Calificar Servicio]:::turista
    TRate --> TCreateRating[Registrar Calificación]:::turista
    TCompleted -->|Pendiente/Confirmada| TWait[En Espera de<br/>Confirmación del Proveedor]:::turista
    Tourist --> TChatbot([Asistente Virtual]):::turista
    Tourist --> TProfile([Gestión de Perfil]):::turista
    
    %% PROVEEDOR
    RoleCheck -->|Proveedor| Prov[ROL: PROVEEDOR]:::proveedor
    Prov --> PPanel[Panel de Control<br/>del Proveedor]:::proveedor
    PPanel --> PServices[Gestión de Servicios<br/>Crear/Editar/Eliminar]:::proveedor
    PPanel --> PBookings[Administración<br/>de Reservas]:::proveedor
    PBookings --> PPending{Estado de<br/>Reserva}:::proveedor
    PPending -->|Pendiente| PConfirm[Confirmar Reserva]:::proveedor
    PConfirm --> PConfirmed[Estado: Confirmada]:::proveedor
    PPending -->|Confirmada| PComplete[Marcar como Completada]:::proveedor
    PComplete --> PCompleted[Estado: Completada]:::proveedor
    PPanel --> PRatings[Revisión de<br/>Calificaciones Recibidas]:::proveedor
    PRatings --> PNoResponse{Calificación<br/>sin Respuesta}:::proveedor
    PNoResponse -->|Sí| PRespond[Responder a Calificación]:::proveedor
    PPanel --> PStats([Análisis de Estadísticas<br/>e Ingresos]):::proveedor
    
    %% ADMINISTRADOR
    RoleCheck -->|Administrador| Admin[ROL: ADMINISTRADOR]:::admin
    Admin --> APanel[Panel de<br/>Administración General]:::admin
    APanel --> AUsers[Gestión de Usuarios<br/>del Sistema]:::admin
    AUsers --> ARoles[Asignación de Roles<br/>y Permisos]:::admin
    APanel --> AServices[Supervisión Global<br/>de Servicios]:::admin
    APanel --> AModerate[Moderación de<br/>Calificaciones]:::admin
    AModerate --> AOffensive{Evaluación de<br/>Contenido}:::admin
    AOffensive -->|Inapropiado| AReject[Rechazar Calificación]:::admin
    AOffensive -->|Apropiado| AApprove[Aprobar Calificación]:::admin
    APanel --> AStats([Dashboard de<br/>Estadísticas Globales]):::admin
    
    %% Privilegios de Administrador
    Admin -.->|Acceso Total| Prov
    Admin -.->|Acceso Total| Tourist
    
    %% ESTILOS
    classDef inicio fill:#2e7d32,stroke:#1b5e20,stroke-width:3px,color:#fff,font-weight:bold
    classDef decision fill:#f57c00,stroke:#e65100,stroke-width:2px,color:#fff,font-weight:bold
    classDef anon fill:#757575,stroke:#424242,stroke-width:2px,color:#fff
    classDef turista fill:#1976d2,stroke:#0d47a1,stroke-width:2px,color:#fff
    classDef proveedor fill:#fbc02d,stroke:#f57f17,stroke-width:2px,color:#000
    classDef admin fill:#c62828,stroke:#8e0000,stroke-width:2px,color:#fff,font-weight:bold