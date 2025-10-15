# Usaremos dataclasses para crear clases concisas que almacenan datos.
from dataclasses import dataclass, field
from typing import List

@dataclass
class Recurso:
    id: int
    nombre: str
    abreviatura: str
    metrica: str
    tipo: str
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
    fecha_inicio: str
    estado: str # 'Vigente' o 'Cancelada'
    fecha_final: str = None
    consumos: list = field(default_factory=list) # Guardará los consumos no facturados

@dataclass
class Cliente:
    nit: str
    nombre: str
    usuario: str
    clave: str
    direccion: str
    correo: str
    instancias: List[Instancia] = field(default_factory=list)