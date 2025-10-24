import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
# CORRECCIÓN: Nombres de import actualizados
from models import (
    Recurso, Categoria, Configuracion, RecursoConfiguracion,
    Cliente, Instancia, Factura, DetalleInstanciaFactura, DetalleRecursoInstancia
)
from utils import extraer_fecha, validar_nit

class Datalake:
    def __init__(self, db_filename="db_persistente.xml"):
        self.recursos = []
        self.categorias = []
        self.clientes = []
        self.facturas = []
        self.db_file = db_filename
        # CORRECCIÓN: Mover creación de directorio a guardar_a_xml
        # os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        self.cargar_desde_xml_persistente()

    def cargar_desde_xml_string(self, xml_string):
        """ Parsea el XML de configuración inicial y carga los datos en memoria, haciendo merge. """
        current_recursos = {r.id: r for r in self.recursos}
        current_categorias = {c.id: c for c in self.categorias}
        current_configs = {conf.id: conf for cat in self.categorias for conf in cat.configuraciones}
        current_clientes = {cli.nit: cli for cli in self.clientes}
        current_instancias = {(inst.id, cli.nit): inst for cli in self.clientes for inst in cli.instancias}

        # No limpiamos nada al inicio, hacemos merge
        nuevos = {'recursos': 0, 'categorias': 0, 'configuraciones': 0, 'clientes': 0, 'instancias': 0}
        actualizados = {'recursos': 0, 'categorias': 0, 'configuraciones': 0, 'clientes': 0, 'instancias': 0}
        errores = []
        ids_config_procesadas_en_este_xml = set()

        try:
            root = ET.fromstring(xml_string)

            # Cargar/Actualizar Recursos
            for rec_elem in root.findall('.//listaRecursos/recurso'):
                try:
                    rec_id = int(rec_elem.attrib['id'])
                    recurso_data = Recurso(
                        id=rec_id,
                        nombre=rec_elem.findtext('nombre'),
                        abreviatura=rec_elem.findtext('abreviatura'),
                        metrica=rec_elem.findtext('metrica'),
                        tipo=(rec_elem.findtext('tipo') or '').strip().upper(),
                        valor_x_hora=float(rec_elem.findtext('valorXhora'))
                    )
                    if rec_id in current_recursos:
                        # Actualiza el existente
                        existing = current_recursos[rec_id]
                        existing.nombre = recurso_data.nombre or existing.nombre
                        existing.abreviatura = recurso_data.abreviatura or existing.abreviatura
                        existing.metrica = recurso_data.metrica or existing.metrica
                        existing.tipo = recurso_data.tipo or existing.tipo
                        existing.valor_x_hora = recurso_data.valor_x_hora # Siempre actualiza valor
                        actualizados['recursos'] += 1
                    else:
                        # Añade nuevo
                        self.recursos.append(recurso_data)
                        current_recursos[rec_id] = recurso_data # Añade al dict temporal
                        nuevos['recursos'] += 1
                except (ValueError, KeyError, AttributeError, TypeError, ET.ParseError) as e:
                    errores.append(f"Error procesando recurso XML: {e} - {ET.tostring(rec_elem, encoding='unicode')[:100]}")


            # Cargar/Actualizar Categorías y Configuraciones
            for cat_elem in root.findall('.//listaCategorias/categoria'):
                try:
                    id_cat = int(cat_elem.attrib['id'])
                    categoria_existente = current_categorias.get(id_cat)

                    if categoria_existente:
                        categoria_actual = categoria_existente
                        categoria_actual.nombre = cat_elem.findtext('nombre') or categoria_actual.nombre
                        categoria_actual.descripcion = cat_elem.findtext('descripcion') or categoria_actual.descripcion
                        categoria_actual.carga_trabajo = cat_elem.findtext('cargaTrabajo') or categoria_actual.carga_trabajo
                        actualizados['categorias'] += 1
                    else:
                        categoria_actual = Categoria(
                            id=id_cat,
                            nombre=cat_elem.findtext('nombre'),
                            descripcion=cat_elem.findtext('descripcion'),
                            carga_trabajo=cat_elem.findtext('cargaTrabajo'),
                            configuraciones=[]
                        )
                        self.categorias.append(categoria_actual)
                        current_categorias[id_cat] = categoria_actual # Añade al dict temporal
                        nuevos['categorias'] += 1

                    for conf_elem in cat_elem.findall('.//listaConfiguraciones/configuracion'):
                        try:
                            id_conf = int(conf_elem.attrib['id'])

                            # Evitar procesar el mismo ID de config dos veces DESDE ESTE XML
                            if id_conf in ids_config_procesadas_en_este_xml:
                                errores.append(f"Configuración ID {id_conf} duplicada dentro del XML. Omitiendo segunda aparición.")
                                continue
                            ids_config_procesadas_en_este_xml.add(id_conf)

                            config_existente = current_configs.get(id_conf)
                            cat_de_existente = self.find_categoria_por_config(id_conf) if config_existente else None

                            # Lógica de validación: No puede existir en otra categoría
                            if config_existente and cat_de_existente and cat_de_existente.id != categoria_actual.id:
                                errores.append(f"Configuración ID {id_conf} ya existe en Categoría ID {cat_de_existente.id}. No se puede añadir/modificar en Cat ID {categoria_actual.id}.")
                                continue

                            recursos_de_config = []
                            for rec_conf_elem in conf_elem.findall('.//recursosConfiguracion/recurso'):
                                try:
                                    rec_id = int(rec_conf_elem.attrib['id'])
                                    cantidad = float(rec_conf_elem.text)
                                    if rec_id in current_recursos: # Validar contra recursos ya cargados/existentes
                                        # Evitar duplicados del mismo recurso dentro de la config
                                        if not any(rc.id_recurso == rec_id for rc in recursos_de_config):
                                            recursos_de_config.append(RecursoConfiguracion(id_recurso=rec_id, cantidad=cantidad))
                                        else:
                                            errores.append(f"Config ID {id_conf}: Recurso ID {rec_id} duplicado dentro de <recursosConfiguracion>. Omitiendo duplicado.")
                                    else:
                                         errores.append(f"Config ID {id_conf}: Recurso ID {rec_id} referenciado no existe en <listaRecursos>.")
                                except (ValueError, KeyError, AttributeError, TypeError, ET.ParseError) as e_rec:
                                    errores.append(f"Error proc. recurso en config ID {id_conf}: {e_rec}")


                            if config_existente:
                                # Actualiza la existente (asumiendo que está en la categoría correcta)
                                config_actual = config_existente
                                config_actual.nombre = conf_elem.findtext('nombre') or config_actual.nombre
                                config_actual.descripcion = conf_elem.findtext('descripcion') or config_actual.descripcion
                                config_actual.recursos = recursos_de_config # Sobrescribe recursos
                                actualizados['configuraciones'] += 1
                            else:
                                # Crea nueva configuración
                                config_actual = Configuracion(
                                    id=id_conf,
                                    nombre=conf_elem.findtext('nombre'),
                                    descripcion=conf_elem.findtext('descripcion'),
                                    recursos=recursos_de_config
                                )
                                categoria_actual.configuraciones.append(config_actual)
                                current_configs[id_conf] = config_actual # Añade al dict temporal
                                nuevos['configuraciones'] += 1

                        except (ValueError, KeyError, AttributeError, TypeError, ET.ParseError) as e_conf:
                            errores.append(f"Error proc. config en cat ID {categoria_actual.id}: {e_conf} - {ET.tostring(conf_elem, encoding='unicode')[:100]}")
                except (ValueError, KeyError, AttributeError, TypeError, ET.ParseError) as e_cat:
                    errores.append(f"Error procesando categoría: {e_cat} - {ET.tostring(cat_elem, encoding='unicode')[:100]}")

            # Cargar/Actualizar Clientes e Instancias
            for cli_elem in root.findall('.//listaClientes/cliente'):
                try:
                    nit = cli_elem.attrib['nit']
                    if not validar_nit(nit):
                        errores.append(f"NIT '{nit}' inválido. Saltando cliente.")
                        continue

                    cliente_existente = current_clientes.get(nit)
                    if cliente_existente:
                        cliente_actual = cliente_existente
                        cliente_actual.nombre = cli_elem.findtext('nombre') or cliente_actual.nombre
                        cliente_actual.usuario = cli_elem.findtext('usuario') or cliente_actual.usuario
                        cliente_actual.clave = cli_elem.findtext('clave') or cliente_actual.clave
                        cliente_actual.direccion = cli_elem.findtext('direccion') or cliente_actual.direccion
                        cliente_actual.correo = cli_elem.findtext('correoElectronico') or cliente_actual.correo
                        actualizados['clientes'] += 1
                    else:
                        cliente_actual = Cliente(
                            nit=nit,
                            nombre=cli_elem.findtext('nombre'),
                            usuario=cli_elem.findtext('usuario'),
                            clave=cli_elem.findtext('clave'),
                            direccion=cli_elem.findtext('direccion'),
                            correo=cli_elem.findtext('correoElectronico'),
                            instancias=[]
                        )
                        self.clientes.append(cliente_actual)
                        current_clientes[nit] = cliente_actual # Añade al dict temporal
                        nuevos['clientes'] += 1

                    for inst_elem in cli_elem.findall('.//listaInstancias/instancia'):
                        try:
                            id_inst = int(inst_elem.attrib['id'])
                            instancia_key = (id_inst, nit)
                            instancia_existente = current_instancias.get(instancia_key)

                            id_conf_str = inst_elem.findtext('idConfiguracion')
                            if not id_conf_str:
                                errores.append(f"Cliente NIT {nit}, Instancia ID {id_inst}: Falta <idConfiguracion>. Saltando.")
                                continue
                            id_conf = int(id_conf_str)

                            if id_conf not in current_configs:
                                errores.append(f"Cliente NIT {nit}, Instancia ID {id_inst}: Config ID {id_conf} referenciada no existe. Saltando instancia.")
                                continue

                            estado = (inst_elem.findtext('estado') or '').strip().upper()
                            fecha_inicio = extraer_fecha(inst_elem.findtext('fechaInicio'))
                            fecha_final = None
                            if estado == 'CANCELADA':
                                fecha_final = extraer_fecha(inst_elem.findtext('fechaFinal'))

                            if instancia_existente:
                                # Actualiza la instancia existente
                                instancia_actual = instancia_existente
                                instancia_actual.id_configuracion = id_conf
                                instancia_actual.nombre = inst_elem.findtext('nombre') or instancia_actual.nombre
                                instancia_actual.fecha_inicio = fecha_inicio if fecha_inicio else instancia_actual.fecha_inicio
                                instancia_actual.estado = 'Cancelada' if estado == 'CANCELADA' else 'Vigente'
                                instancia_actual.fecha_final = fecha_final if instancia_actual.estado == 'Cancelada' else None
                                # Los consumos NO se tocan al cargar configuración
                                actualizados['instancias'] += 1
                            else:
                                # Crea nueva instancia
                                instancia_actual = Instancia(
                                    id=id_inst,
                                    id_configuracion=id_conf,
                                    nombre=inst_elem.findtext('nombre'),
                                    fecha_inicio=fecha_inicio if fecha_inicio else "Fecha Inválida",
                                    estado='Cancelada' if estado == 'CANCELADA' else 'Vigente',
                                    fecha_final=fecha_final,
                                    consumos=[] # Nueva instancia sin consumos
                                )
                                cliente_actual.instancias.append(instancia_actual)
                                current_instancias[instancia_key] = instancia_actual # Añade al dict temporal
                                nuevos['instancias'] += 1
                        except (ValueError, KeyError, AttributeError, TypeError, ET.ParseError) as e_inst:
                            errores.append(f"Error proc. instancia para cliente NIT {nit}: {e_inst}")
                except (KeyError, AttributeError, TypeError, ET.ParseError) as e_cli:
                     errores.append(f"Error procesando cliente: {e_cli} - {ET.tostring(cli_elem, encoding='unicode')[:100]}")

            # Construir mensaje de resumen
            resumen_nuevos = [f"{v} {k}" for k, v in nuevos.items() if v > 0]
            resumen_actualizados = [f"{v} {k}" for k, v in actualizados.items() if v > 0]
            mensaje = "Carga de configuración completada. "
            if resumen_nuevos: mensaje += f"Nuevos: {', '.join(resumen_nuevos)}. "
            if resumen_actualizados: mensaje += f"Actualizados: {', '.join(resumen_actualizados)}. "
            if not resumen_nuevos and not resumen_actualizados: mensaje += "No se realizaron cambios (datos ya existentes o sin cambios)."

            if errores:
                mensaje += f" Se encontraron {len(errores)} advertencias/errores durante la carga. Revise los logs del backend."
                print("\n--- Errores/Advertencias Carga Config XML ---")
                for i, err in enumerate(errores): print(f"{i+1}. {err}")
                print("---------------------------------------------\n")

            return {"status": "success", "message": mensaje}

        except ET.ParseError as e:
            return {"status": "error", "message": f"Error fatal al parsear el XML de configuración: {e}"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": f"Error inesperado durante carga de configuración: {type(e).__name__} - {e}"}


    def cargar_consumo_desde_xml_string(self, xml_string):
        """ Parsea el XML de consumo y lo registra en la instancia correspondiente. """
        consumos_procesados = 0
        errores = []
        try:
            root = ET.fromstring(xml_string)

            for consumo_elem in root.findall('.//consumo'):
                try:
                    # Usar .get() para evitar KeyError si falta el atributo
                    nit_cliente = consumo_elem.attrib.get('nitCliente')
                    id_instancia_str = consumo_elem.attrib.get('idInstancia')
                    tiempo_str = consumo_elem.findtext('tiempo') # Más seguro que .find().text

                    # Validaciones básicas
                    if not nit_cliente or not id_instancia_str or tiempo_str is None:
                        errores.append(f"Consumo inválido (falta nitCliente, idInstancia o tiempo): {ET.tostring(consumo_elem, encoding='unicode')[:100]}")
                        continue

                    id_instancia = int(id_instancia_str)
                    tiempo = float(tiempo_str)

                    # Ignora fechaHora por ahora, según enunciado solo importa el tiempo

                    instancia_encontrada = self.find_instancia(nit_cliente, id_instancia)

                    if not instancia_encontrada:
                        errores.append(f"Instancia ID {id_instancia} para cliente NIT {nit_cliente} no encontrada.")
                        continue

                    if instancia_encontrada.estado != 'Vigente':
                         errores.append(f"Intento de añadir consumo a instancia ID {id_instancia} (NIT {nit_cliente}) que está '{instancia_encontrada.estado}'.")
                         continue

                    # Añadir el consumo a la lista de la instancia
                    instancia_encontrada.consumos.append(tiempo)
                    consumos_procesados += 1
                except (ValueError, TypeError) as e: # Captura errores de conversión int/float
                     errores.append(f"Error procesando valor en un consumo: {e} - {ET.tostring(consumo_elem, encoding='unicode')[:100]}")
                except Exception as e: # Captura otros errores inesperados por elemento
                     errores.append(f"Error inesperado procesando un consumo: {e} - {ET.tostring(consumo_elem, encoding='unicode')[:100]}")

            mensaje = f"{consumos_procesados} consumos procesados."
            if errores:
                 mensaje += f" Se encontraron {len(errores)} advertencias/errores. Revise logs del backend."
                 print("\n--- Errores/Advertencias Carga Consumo XML ---")
                 for i, err in enumerate(errores): print(f"{i+1}. {err}")
                 print("----------------------------------------------\n")


            return {"status": "success", "message": mensaje}

        except ET.ParseError as e:
            return {"status": "error", "message": f"Error fatal al parsear el XML de consumo: {e}"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": f"Error inesperado durante carga de consumo: {type(e).__name__} - {e}"}

    def reset_datos(self):
        """ Limpia todos los datos en memoria y el archivo XML persistente. """
        self.recursos.clear()
        self.categorias.clear()
        self.clientes.clear()
        self.facturas.clear()
        try:
            if os.path.exists(self.db_file):
                # Opcional: Escribir un archivo vacío en lugar de borrarlo
                # self.guardar_a_xml() # Guardará un estado vacío
                os.remove(self.db_file) # Borra el archivo
                print(f"Archivo {self.db_file} eliminado.")
            # Asegura que al reiniciar se cree el archivo vacío si no existe
            self.guardar_a_xml()
        except OSError as e:
            print(f"Error al manejar {self.db_file} en reset: {e}")
        except Exception as e:
             print(f"Error inesperado en reset_datos: {e}")


    def get_datos_generales(self):
        """ Devuelve un resumen de todos los datos cargados en formato serializable. """
        # Usa list comprehensions y asdict (si los modelos lo soportan) o .__dict__
        # Asegura que las listas internas también se serialicen
        return {
            "recursos": [r.__dict__ for r in self.recursos],
            "categorias": [
                {
                    "id": c.id, "nombre": c.nombre, "descripcion": c.descripcion,
                    "carga_trabajo": c.carga_trabajo,
                    "configuraciones": [
                        {
                            "id": conf.id, "nombre": conf.nombre, "descripcion": conf.descripcion,
                            "recursos": [rc.__dict__ for rc in conf.recursos]
                        } for conf in c.configuraciones
                    ]
                } for c in self.categorias
            ],
            "clientes": [
                {
                    "nit": cli.nit, "nombre": cli.nombre, "usuario": cli.usuario,
                    # No incluir clave en la consulta general por seguridad
                    "direccion": cli.direccion, "correo": cli.correo,
                    "instancias": [
                        {
                            "id": inst.id, "id_configuracion": inst.id_configuracion,
                            "nombre": inst.nombre, "fecha_inicio": inst.fecha_inicio,
                            "estado": inst.estado, "fecha_final": inst.fecha_final,
                            "consumos_pendientes_count": len(inst.consumos), # Devuelve la cantidad, no los valores
                            "consumos_pendientes_total_horas": sum(inst.consumos) # Devuelve el total de horas
                        } for inst in cli.instancias
                    ]
                } for cli in self.clientes
            ],
             "facturas": [f.to_dict() for f in self.facturas] # Asume que Factura tiene to_dict()
        }


    # --- Métodos de Búsqueda ---
    def find_cliente(self, nit):
        return next((c for c in self.clientes if c.nit == nit), None)

    def find_recurso(self, id_recurso):
        # Asegura comparación de enteros
        try: id_recurso_int = int(id_recurso)
        except (ValueError, TypeError): return None
        return next((r for r in self.recursos if r.id == id_recurso_int), None)

    def find_categoria(self, id_categoria):
        try: id_categoria_int = int(id_categoria)
        except (ValueError, TypeError): return None
        return next((c for c in self.categorias if c.id == id_categoria_int), None)

    def find_configuracion(self, id_configuracion):
        try: id_configuracion_int = int(id_configuracion)
        except (ValueError, TypeError): return None
        for cat in self.categorias:
            found = next((conf for conf in cat.configuraciones if conf.id == id_configuracion_int), None)
            if found: return found
        return None

    def find_instancia(self, nit_cliente, id_instancia):
        try: id_instancia_int = int(id_instancia)
        except (ValueError, TypeError): return None
        cliente = self.find_cliente(nit_cliente)
        if cliente:
            return next((i for i in cliente.instancias if i.id == id_instancia_int), None)
        return None

    def find_categoria_por_config(self, id_configuracion):
        try: id_configuracion_int = int(id_configuracion)
        except (ValueError, TypeError): return None
        for cat in self.categorias:
            if any(conf.id == id_configuracion_int for conf in cat.configuraciones):
                return cat
        return None

    def get_all_configuraciones(self):
        all_configs = []
        for cat in self.categorias:
            all_configs.extend(cat.configuraciones)
        return all_configs

    # --- Persistencia en XML ---
    def guardar_a_xml(self):
        """ Guarda el estado actual de los datos en el archivo XML persistente. """
        # CORRECCIÓN: Asegurar que el directorio exista ANTES de intentar escribir
        try:
            os.makedirs(os.path.dirname(self.db_file) or '.', exist_ok=True)
        except OSError as e:
            print(f"Advertencia: No se pudo crear el directorio para {self.db_file}: {e}")
            # Decide si continuar o no. Podríamos intentar guardar en el directorio actual.
            # self.db_file = os.path.basename(self.db_file) # Guarda solo el nombre del archivo

        root = ET.Element("sistemaTecnologiasChapinas")

        # Guardar Recursos
        lista_rec = ET.SubElement(root, "listaRecursos")
        for r in self.recursos:
            rec_elem = ET.SubElement(lista_rec, "recurso", id=str(r.id))
            ET.SubElement(rec_elem, "nombre").text = r.nombre
            ET.SubElement(rec_elem, "abreviatura").text = r.abreviatura
            ET.SubElement(rec_elem, "metrica").text = r.metrica
            ET.SubElement(rec_elem, "tipo").text = r.tipo
            ET.SubElement(rec_elem, "valorXhora").text = str(r.valor_x_hora)

        # Guardar Categorías y Configuraciones
        lista_cat = ET.SubElement(root, "listaCategorias")
        for c in self.categorias:
            cat_elem = ET.SubElement(lista_cat, "categoria", id=str(c.id))
            ET.SubElement(cat_elem, "nombre").text = c.nombre
            ET.SubElement(cat_elem, "descripcion").text = c.descripcion
            ET.SubElement(cat_elem, "cargaTrabajo").text = c.carga_trabajo
            lista_conf = ET.SubElement(cat_elem, "listaConfiguraciones")
            for conf in c.configuraciones:
                conf_elem = ET.SubElement(lista_conf, "configuracion", id=str(conf.id))
                ET.SubElement(conf_elem, "nombre").text = conf.nombre
                ET.SubElement(conf_elem, "descripcion").text = conf.descripcion
                rec_conf_lista = ET.SubElement(conf_elem, "recursosConfiguracion")
                for rc in conf.recursos:
                    rec_conf_elem = ET.SubElement(rec_conf_lista, "recurso", id=str(rc.id_recurso))
                    rec_conf_elem.text = str(rc.cantidad)

        # Guardar Clientes e Instancias (con consumos pendientes)
        lista_cli = ET.SubElement(root, "listaClientes")
        for cli in self.clientes:
            cli_elem = ET.SubElement(lista_cli, "cliente", nit=cli.nit)
            ET.SubElement(cli_elem, "nombre").text = cli.nombre
            ET.SubElement(cli_elem, "usuario").text = cli.usuario
            ET.SubElement(cli_elem, "clave").text = cli.clave # ¡Ojo con guardar claves en texto plano!
            ET.SubElement(cli_elem, "direccion").text = cli.direccion
            ET.SubElement(cli_elem, "correoElectronico").text = cli.correo
            lista_inst = ET.SubElement(cli_elem, "listaInstancias")
            for inst in cli.instancias:
                inst_elem = ET.SubElement(lista_inst, "instancia", id=str(inst.id))
                ET.SubElement(inst_elem, "idConfiguracion").text = str(inst.id_configuracion)
                ET.SubElement(inst_elem, "nombre").text = inst.nombre
                ET.SubElement(inst_elem, "fechaInicio").text = inst.fecha_inicio if inst.fecha_inicio else ""
                ET.SubElement(inst_elem, "estado").text = inst.estado
                ET.SubElement(inst_elem, "fechaFinal").text = inst.fecha_final if inst.fecha_final else ""
                cons_lista = ET.SubElement(inst_elem, "consumosPendientes")
                for cons in inst.consumos: # Guarda la lista de floats
                    ET.SubElement(cons_lista, "consumo").text = str(cons)

        # Guardar Facturas
        lista_fac = ET.SubElement(root, "listaFacturas")
        for f in self.facturas:
            fac_elem = ET.SubElement(lista_fac, "factura", id=str(f.id), nitCliente=f.nit_cliente)
            ET.SubElement(fac_elem, "nombreCliente").text = f.nombre_cliente
            ET.SubElement(fac_elem, "fechaFactura").text = f.fecha_factura
            ET.SubElement(fac_elem, "montoTotal").text = str(f.monto_total)
            detalles_inst_elem = ET.SubElement(fac_elem, "detallesInstancias")
            # CORRECCIÓN: Usar nombres correctos de clases/atributos
            for det_inst in f.detalles_instancias:
                det_inst_elem = ET.SubElement(detalles_inst_elem, "detalleInstancia", idInstancia=str(det_inst.id_instancia))
                ET.SubElement(det_inst_elem, "nombreInstancia").text = det_inst.nombre_instancia
                ET.SubElement(det_inst_elem, "idConfiguracion").text = str(det_inst.id_configuracion)
                ET.SubElement(det_inst_elem, "nombreConfiguracion").text = det_inst.nombre_configuracion
                ET.SubElement(det_inst_elem, "idCategoria").text = str(det_inst.id_categoria if det_inst.id_categoria is not None else "") # Manejar None
                ET.SubElement(det_inst_elem, "horasConsumidas").text = str(det_inst.horas_consumidas)
                ET.SubElement(det_inst_elem, "subtotalInstancia").text = str(det_inst.subtotal_instancia)
                detalles_rec_elem = ET.SubElement(det_inst_elem, "recursosCosto")
                for det_rec in det_inst.recursos_costo:
                    det_rec_elem = ET.SubElement(detalles_rec_elem, "detalleRecurso", idRecurso=str(det_rec.id_recurso))
                    ET.SubElement(det_rec_elem, "nombreRecurso").text = det_rec.nombre_recurso
                    ET.SubElement(det_rec_elem, "cantidad").text = str(det_rec.cantidad)
                    ET.SubElement(det_rec_elem, "metrica").text = det_rec.metrica
                    ET.SubElement(det_rec_elem, "valorXhora").text = str(det_rec.valor_x_hora)
                    ET.SubElement(det_rec_elem, "subtotal").text = str(det_rec.subtotal)

        # Escribir el archivo XML formateado
        try:
            xml_str_bytes = ET.tostring(root, encoding='utf-8', method='xml')
            dom = minidom.parseString(xml_str_bytes)
            pretty_xml_str_bytes = dom.toprettyxml(indent="  ", encoding='utf-8')

            with open(self.db_file, "wb") as f:
                f.write(pretty_xml_str_bytes)
            # Quitar el print de aquí para no saturar consola, se puede loguear si se quiere
            # print(f"Datos guardados exitosamente en {self.db_file}")
        except Exception as e:
            print(f"Error CRÍTICO al intentar guardar en {self.db_file}: {e}")
            # Considerar qué hacer aquí. ¿Lanzar excepción? ¿Intentar de nuevo?

    def cargar_desde_xml_persistente(self):
        """ Carga los datos desde el archivo XML persistente al iniciar. """
        if not os.path.exists(self.db_file):
            print(f"Archivo {self.db_file} no encontrado. Iniciando en blanco.")
            return

        try:
            # Añadir manejo de archivo vacío
            if os.path.getsize(self.db_file) == 0:
                print(f"Archivo {self.db_file} está vacío. Iniciando en blanco.")
                return

            tree = ET.parse(self.db_file)
            root = tree.getroot()

            # Cargar Recursos
            self.recursos = []
            for rec_elem in root.findall('.//listaRecursos/recurso'):
                try: self.recursos.append(Recurso(
                        id=int(rec_elem.attrib['id']), nombre=rec_elem.findtext('nombre', default=""),
                        abreviatura=rec_elem.findtext('abreviatura', default=""), metrica=rec_elem.findtext('metrica', default=""),
                        tipo=rec_elem.findtext('tipo', default="HARDWARE"), valor_x_hora=float(rec_elem.findtext('valorXhora', default=0.0))
                    ))
                except (ValueError, KeyError, AttributeError, TypeError): continue

            # Cargar Categorías y Configuraciones
            self.categorias = []
            for cat_elem in root.findall('.//listaCategorias/categoria'):
                try:
                    categoria = Categoria(
                        id=int(cat_elem.attrib['id']), nombre=cat_elem.findtext('nombre', default=""),
                        descripcion=cat_elem.findtext('descripcion', default=""), carga_trabajo=cat_elem.findtext('cargaTrabajo', default=""),
                        configuraciones=[] )
                    for conf_elem in cat_elem.findall('.//listaConfiguraciones/configuracion'):
                        try:
                            configuracion = Configuracion(
                                id=int(conf_elem.attrib['id']), nombre=conf_elem.findtext('nombre', default=""),
                                descripcion=conf_elem.findtext('descripcion', default=""), recursos=[] )
                            for rec_conf_elem in conf_elem.findall('.//recursosConfiguracion/recurso'):
                                try: configuracion.recursos.append(RecursoConfiguracion(
                                        id_recurso=int(rec_conf_elem.attrib['id']), cantidad=float(rec_conf_elem.text or 0.0) ))
                                except (ValueError, KeyError, AttributeError, TypeError): continue
                            categoria.configuraciones.append(configuracion)
                        except (ValueError, KeyError, AttributeError, TypeError): continue
                    self.categorias.append(categoria)
                except (ValueError, KeyError, AttributeError, TypeError): continue

            # Cargar Clientes e Instancias
            self.clientes = []
            for cli_elem in root.findall('.//listaClientes/cliente'):
                 try:
                    cliente = Cliente(
                        nit=cli_elem.attrib['nit'], nombre=cli_elem.findtext('nombre', default=""),
                        usuario=cli_elem.findtext('usuario', default=""), clave=cli_elem.findtext('clave', default=""),
                        direccion=cli_elem.findtext('direccion', default=""), correo=cli_elem.findtext('correoElectronico', default=""),
                        instancias=[] )
                    for inst_elem in cli_elem.findall('.//listaInstancias/instancia'):
                        try:
                            instancia = Instancia(
                                id=int(inst_elem.attrib['id']), id_configuracion=int(inst_elem.findtext('idConfiguracion', default=0)),
                                nombre=inst_elem.findtext('nombre', default=""), fecha_inicio=inst_elem.findtext('fechaInicio', default=""),
                                estado=inst_elem.findtext('estado', default="Vigente"), fecha_final=inst_elem.findtext('fechaFinal'), # None si no existe
                                consumos=[] )
                            for cons_elem in inst_elem.findall('.//consumosPendientes/consumo'):
                                try: instancia.consumos.append(float(cons_elem.text or 0.0))
                                except (ValueError, TypeError): continue
                            cliente.instancias.append(instancia)
                        except (ValueError, KeyError, AttributeError, TypeError): continue
                    self.clientes.append(cliente)
                 except (KeyError, AttributeError, TypeError): continue

            # Cargar Facturas
            self.facturas = []
            for fac_elem in root.findall('.//listaFacturas/factura'):
                try:
                    factura = Factura(
                        id=int(fac_elem.attrib['id']), nit_cliente=fac_elem.attrib['nitCliente'],
                        nombre_cliente=fac_elem.findtext('nombreCliente', default=""), fecha_factura=fac_elem.findtext('fechaFactura', default=""),
                        monto_total=float(fac_elem.findtext('montoTotal', default=0.0)), detalles_instancias=[] )
                    # CORRECCIÓN: Usar nombres correctos
                    for det_inst_elem in fac_elem.findall('.//detallesInstancias/detalleInstancia'):
                         try:
                            id_cat_text = det_inst_elem.findtext('idCategoria')
                            id_categoria = int(id_cat_text) if id_cat_text else None

                            detalle_inst = DetalleInstanciaFactura(
                                id_instancia=int(det_inst_elem.attrib['idInstancia']), nombre_instancia=det_inst_elem.findtext('nombreInstancia', default=""),
                                id_configuracion=int(det_inst_elem.findtext('idConfiguracion', default=0)), nombre_configuracion=det_inst_elem.findtext('nombreConfiguracion', default=""),
                                id_categoria=id_categoria, horas_consumidas=float(det_inst_elem.findtext('horasConsumidas', default=0.0)),
                                subtotal_instancia=float(det_inst_elem.findtext('subtotalInstancia', default=0.0)), recursos_costo=[] )
                            for det_rec_elem in det_inst_elem.findall('.//recursosCosto/detalleRecurso'):
                                try: detalle_inst.recursos_costo.append(DetalleRecursoInstancia(
                                        id_recurso=int(det_rec_elem.attrib['idRecurso']), nombre_recurso=det_rec_elem.findtext('nombreRecurso', default=""),
                                        cantidad=float(det_rec_elem.findtext('cantidad', default=0.0)), metrica=det_rec_elem.findtext('metrica', default=""),
                                        valor_x_hora=float(det_rec_elem.findtext('valorXhora', default=0.0)), subtotal=float(det_rec_elem.findtext('subtotal', default=0.0)) ))
                                except (ValueError, KeyError, AttributeError, TypeError): continue
                            factura.detalles_instancias.append(detalle_inst)
                         except (ValueError, KeyError, AttributeError, TypeError): continue
                    self.facturas.append(factura)
                except (ValueError, KeyError, AttributeError, TypeError): continue

            print(f"Datos cargados exitosamente desde {self.db_file}")

        except ET.ParseError as e:
            print(f"Error al parsear {self.db_file}: {e}. Archivo corrupto o vacío. Iniciando en blanco.")
            # Si el archivo está corrupto, lo mejor es empezar de cero
            self.recursos, self.categorias, self.clientes, self.facturas = [], [], [], []
            # Opcional: intentar borrar el archivo corrupto
            try: os.remove(self.db_file)
            except OSError: pass
        except FileNotFoundError:
             print(f"Archivo {self.db_file} no encontrado. Iniciando en blanco.")
        except Exception as e:
            print(f"Error INESPERADO al cargar XML persistente ({type(e).__name__}): {e}. Iniciando en blanco.")
            import traceback
            traceback.print_exc()
            self.recursos, self.categorias, self.clientes, self.facturas = [], [], [], []
            try: os.remove(self.db_file)
            except OSError: pass


# Instancia global del Datalake
# Se crea aquí para que esté disponible para importación en app.py
# La carga inicial se hace en el __init__
datalake = Datalake()

