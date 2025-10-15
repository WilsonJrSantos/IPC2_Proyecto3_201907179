import unittest
import requests

BASE_URL = "http://127.0.0.1:5000"  # Asegúrate que Flask esté corriendo en este puerto

class TestFlaskAPI(unittest.TestCase):

    def test_1_reset_sistema(self):
        """Probar el endpoint /reset"""
        response = requests.post(f"{BASE_URL}/reset")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print("\n/reset =>", data)
        self.assertEqual(data["status"], "success")

    def test_2_cargar_configuracion(self):
        """Probar el endpoint /cargar-configuracion con XML completo"""
        xml = """<?xml version="1.0"?>
<configuracion>
    <listaRecursos>
        <recurso id="1">
            <nombre>Servidor</nombre>
            <abreviatura>SRV</abreviatura>
            <metrica>GB</metrica>
            <tipo>Infraestructura</tipo>
            <valorXhora>5.0</valorXhora>
        </recurso>
    </listaRecursos>

    <listaCategorias>
        <categoria id="1">
            <nombre>Pequeña</nombre>
            <descripcion>Configuración básica</descripcion>
            <cargaTrabajo>Ligera</cargaTrabajo>
            <listaConfiguraciones>
                <configuracion id="101">
                    <nombre>Config A</nombre>
                    <descripcion>Servidor básico</descripcion>
                    <recursosConfiguracion>
                        <recurso id="1">2</recurso>
                    </recursosConfiguracion>
                </configuracion>
            </listaConfiguraciones>
        </categoria>
    </listaCategorias>

    <listaClientes>
        <cliente nit="1234567-8">
            <nombre>Juan Pérez</nombre>
            <usuario>juan</usuario>
            <clave>1234</clave>
            <direccion>Calle 10</direccion>
            <correoElectronico>juan@example.com</correoElectronico>
            <listaInstancias>
                <instancia id="1">
                    <idConfiguracion>101</idConfiguracion>
                    <nombre>MiServidor</nombre>
                    <fechaInicio>2025-10-15</fechaInicio>
                    <estado>Activa</estado>
                </instancia>
            </listaInstancias>
        </cliente>
    </listaClientes>
</configuracion>"""

        files = {'archivo': ('config_completo.xml', xml, 'text/xml')}
        response = requests.post(f"{BASE_URL}/cargar-configuracion", files=files)
        print("\n/cargar-configuracion =>", response.json())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_3_consultar_datos(self):
        """Probar el endpoint /consultar-datos"""
        response = requests.get(f"{BASE_URL}/consultar-datos")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print("\n/consultar-datos =>", data)

        # Ahora debería tener al menos 1 recurso, 1 categoría y 1 cliente
        self.assertGreaterEqual(len(data.get("recursos", [])), 1)
        self.assertGreaterEqual(len(data.get("categorias", [])), 1)
        self.assertGreaterEqual(len(data.get("clientes", [])), 1)

if __name__ == "__main__":
    unittest.main()
