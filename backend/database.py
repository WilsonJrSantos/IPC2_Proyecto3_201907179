from xml.etree import ElementTree as ET
from models import Recurso, Categoria, Configuracion, RecursoConfiguracion, Cliente, Instancia
from utils import extraer_fecha, validar_nit

class Datalake:
    def __init__(self):
        self.recursos = []
        self.categorias = []
        self.clientes = []

    def cargar_desde_xml_string(self, xml_string):
        """ Parsea el XML de configuración y carga los datos en memoria. """
        try:
            root = ET.fromstring(xml_string)
            
            # Cargar Recursos
            for rec_elem in root.findall('.//listaRecursos/recurso'):
                recurso = Recurso(
                    id=int(rec_elem.attrib['id']),
                    nombre=rec_elem.find('nombre').text,
                    abreviatura=rec_elem.find('abreviatura').text,
                    metrica=rec_elem.find('metrica').text,
                    tipo=rec_elem.find('tipo').text.strip(),
                    valor_x_hora=float(rec_elem.find('valorXhora').text)
                )
                self.recursos.append(recurso)

            # Cargar Categorías y sus Configuraciones
            for cat_elem in root.findall('.//listaCategorias/categoria'):
                categoria = Categoria(
                    id=int(cat_elem.attrib['id']),
                    nombre=cat_elem.find('nombre').text,
                    descripcion=cat_elem.find('descripcion').text,
                    carga_trabajo=cat_elem.find('cargaTrabajo').text
                )
                for conf_elem in cat_elem.findall('.//listaConfiguraciones/configuracion'):
                    configuracion = Configuracion(
                        id=int(conf_elem.attrib['id']),
                        nombre=conf_elem.find('nombre').text,
                        descripcion=conf_elem.find('descripcion').text
                    )
                    for rec_conf_elem in conf_elem.findall('.//recursosConfiguracion/recurso'):
                        rec_config = RecursoConfiguracion(
                            id_recurso=int(rec_conf_elem.attrib['id']),
                            cantidad=float(rec_conf_elem.text)
                        )
                        configuracion.recursos.append(rec_config)
                    categoria.configuraciones.append(configuracion)
                self.categorias.append(categoria)
            
            # Cargar Clientes y sus Instancias
            for cli_elem in root.findall('.//listaClientes/cliente'):
                nit = cli_elem.attrib['nit']
                if not validar_nit(nit):
                    print(f"Advertencia: NIT '{nit}' inválido. Saltando cliente.")
                    continue
                
                cliente = Cliente(
                    nit=nit,
                    nombre=cli_elem.find('nombre').text,
                    usuario=cli_elem.find('usuario').text,
                    clave=cli_elem.find('clave').text,
                    direccion=cli_elem.find('direccion').text,
                    correo=cli_elem.find('correoElectronico').text
                )
                for inst_elem in cli_elem.findall('.//listaInstancias/instancia'):
                    instancia = Instancia(
                        id=int(inst_elem.attrib['id']),
                        id_configuracion=int(inst_elem.find('idConfiguracion').text),
                        nombre=inst_elem.find('nombre').text,
                        fecha_inicio=extraer_fecha(inst_elem.find('fechaInicio').text),
                        estado=inst_elem.find('estado').text.strip()
                    )
                    if instancia.estado == 'Cancelada':
                        instancia.fecha_final = extraer_fecha(inst_elem.find('fechaFinal').text)
                    cliente.instancias.append(instancia)
                self.clientes.append(cliente)

            return {"status": "success", "message": "Datos cargados correctamente."}
        except Exception as e:
            return {"status": "error", "message": f"Error al procesar el XML: {e}"}

    def cargar_consumo_desde_xml_string(self, xml_string):
        """ Parsea el XML de consumo y lo registra en la instancia correspondiente. (Release 2) """
        try:
            root = ET.fromstring(xml_string)
            consumos_procesados = 0
            
            for consumo_elem in root.findall('.//consumo'):
                nit_cliente = consumo_elem.attrib['nitCliente']
                id_instancia = int(consumo_elem.attrib['idInstancia'])
                tiempo = float(consumo_elem.find('tiempo').text)
                
                # Buscar el cliente y la instancia
                cliente_encontrado = next((c for c in self.clientes if c.nit == nit_cliente), None)
                if not cliente_encontrado:
                    print(f"Advertencia: Cliente con NIT {nit_cliente} no encontrado.")
                    continue

                instancia_encontrada = next((i for i in cliente_encontrado.instancias if i.id == id_instancia), None)
                if not instancia_encontrada:
                    print(f"Advertencia: Instancia con ID {id_instancia} no encontrada para el cliente {nit_cliente}.")
                    continue
                
                # Añadir el consumo a la lista de la instancia
                instancia_encontrada.consumos.append(tiempo)
                consumos_procesados += 1
            
            return {"status": "success", "message": f"{consumos_procesados} consumos procesados."}
        except Exception as e:
            return {"status": "error", "message": f"Error al procesar el XML de consumo: {e}"}

    def reset_datos(self):
        """ Limpia todos los datos en memoria. """
        self.recursos.clear()
        self.categorias.clear()
        self.clientes.clear()

    def get_datos_generales(self):
        """ Devuelve un resumen de todos los datos cargados. """
        return {
            "recursos": [rec.__dict__ for rec in self.recursos],
            "categorias": [cat.__dict__ for cat in self.categorias],
            "clientes": [cli.__dict__ for cli in self.clientes]
        }

# Instancia global para actuar como nuestra base de datos en memoria
datalake = Datalake()

