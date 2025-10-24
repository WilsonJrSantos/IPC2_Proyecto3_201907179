from dataclasses import dataclass, field, asdict
from typing import List

# --- Modelos de Configuración ---
@dataclass
class Recurso:
    id: int
    nombre: str
    abreviatura: str
    metrica: str
    tipo: str # HARDWARE | SOFTWARE
    valor_x_hora: float

@dataclass
class RecursoConfiguracion:
    id_recurso: int
    cantidad: float

@dataclass
class Configuracion:
    id: int
    nombre: str
    descripcion: str
    recursos: List[RecursoConfiguracion] = field(default_factory=list)

@dataclass
class Categoria:
    id: int
    nombre: str
    descripcion: str
    carga_trabajo: str
    configuraciones: List[Configuracion] = field(default_factory=list)

@dataclass
class Instancia:
    id: int
    id_configuracion: int
    nombre: str
    fecha_inicio: str # dd/mm/yyyy
    estado: str # Vigente | Cancelada
    fecha_final: str = None # dd/mm/yyyy
    consumos: List[float] = field(default_factory=list) # Consumos pendientes en horas

@dataclass
class Cliente:
    nit: str
    nombre: str
    usuario: str
    clave: str
    direccion: str
    correo: str
    instancias: List[Instancia] = field(default_factory=list)

# --- Modelos de Facturación ---
@dataclass
class DetalleRecursoInstancia:
    id_recurso: int
    nombre_recurso: str
    cantidad: float
    metrica: str
    valor_x_hora: float
    subtotal: float

    def to_dict(self):
       return asdict(self)


@dataclass
class DetalleInstanciaFactura:
    # --- CORRECCIÓN: Reordenar campos ---
    # Campos sin valor por defecto primero
    id_instancia: int
    nombre_instancia: str
    id_configuracion: int
    nombre_configuracion: str
    horas_consumidas: float
    subtotal_instancia: float
    # Campos con valor por defecto después
    id_categoria: int = None
    recursos_costo: List[DetalleRecursoInstancia] = field(default_factory=list)
    # --- FIN CORRECCIÓN ---

    def to_dict(self):
        d = asdict(self)
        # Asegurarse de que los objetos anidados también se conviertan
        d['recursos_costo'] = [rc.to_dict() for rc in self.recursos_costo]
        return d

@dataclass
class Factura:
    id: int
    nit_cliente: str
    nombre_cliente: str
    fecha_factura: str # dd/mm/yyyy
    monto_total: float
    detalles_instancias: List[DetalleInstanciaFactura] = field(default_factory=list)

    def to_dict(self):
       d = asdict(self)
       # Asegurarse de que los objetos anidados también se conviertan
       d['detalles_instancias'] = [di.to_dict() for di in self.detalles_instancias]
       return d

