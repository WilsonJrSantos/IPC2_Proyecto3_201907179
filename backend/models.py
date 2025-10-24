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
# CORRECCIÓN: Nombres actualizados para coincidir con el uso
@dataclass
class DetalleRecursoInstancia: # Anteriormente DetalleRecursoFacturado
    id_recurso: int # Añadido ID para referencia
    nombre_recurso: str
    cantidad: float
    metrica: str # Añadido para mostrar en factura
    valor_x_hora: float
    # horas_consumidas: float # Se obtiene del DetalleInstanciaFactura
    subtotal: float # Aporte al total de la instancia

    def to_dict(self):
       return asdict(self)


@dataclass
class DetalleInstanciaFactura: # Anteriormente DetalleInstanciaFacturada
    id_instancia: int
    nombre_instancia: str
    id_configuracion: int
    nombre_configuracion: str # Añadido para mostrar en factura
    id_categoria: int = None # Puede que no se encuentre si la config fue borrada?
    horas_consumidas: float # Total de horas para esta instancia en la factura
    subtotal_instancia: float
    recursos_costo: List[DetalleRecursoInstancia] = field(default_factory=list) # CORRECCIÓN: Usar nombre corregido

    def to_dict(self):
        d = asdict(self)
        d['recursos_costo'] = [rc.to_dict() for rc in self.recursos_costo]
        return d

@dataclass
class Factura:
    id: int # Cambiado de numero a id para consistencia
    nit_cliente: str
    nombre_cliente: str
    fecha_factura: str # Fecha fin del rango (dd/mm/yyyy)
    monto_total: float
    detalles_instancias: List[DetalleInstanciaFactura] = field(default_factory=list) # CORRECCIÓN: Usar nombre corregido

    def to_dict(self):
       d = asdict(self)
       d['detalles_instancias'] = [di.to_dict() for di in self.detalles_instancias]
       return d

