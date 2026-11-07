"""
test_analizar.py
Pruebas con datos chicos propios, independientes del CSV real de 20.000
registros (el sistema debe poder validar conjuntos de cualquier tamano,
no solo exactamente 20.000).

Incluye, como minimo, las 6 pruebas pedidas por la consigna:
  1. Procesamiento de un registro valido.
  2. Calculo de un indicador con resultado conocido.
  3. Tratamiento correcto de un dato faltante.
  4. Rechazo de una masa negativa.
  5. Rechazo de coordenadas fuera de rango.
  6. Rechazo de un identificador duplicado.

Correr con: python -m unittest discover -v
"""
import csv
import os
import shutil
import tempfile
import unittest
from unittest import mock

import analizar


FIELDNAMES = ["id", "name", "recclass", "mass (g)", "fall", "year", "reclat", "reclong"]


def fila(id_, name, recclass, mass, fall, year, reclat, reclong):
    return {
        "id": id_, "name": name, "recclass": recclass, "mass (g)": mass,
        "fall": fall, "year": year, "reclat": reclat, "reclong": reclong,
    }


FILAS_EJEMPLO = [
    fila("1", "Meteorito Uno", "L5", "1000", "Fell", "1950", "10.5", "20.5"),
    fila("2", "Meteorito Dos", "H6", "2000", "Found", "1988", "-5.25", "-30.1"),
    fila("3", "Meteorito Tres", "LL4", "NA", "Found", "", "0", "0"),  # masa y year faltantes
]


class TestProcesamientoValido(unittest.TestCase):
    def test_procesamiento_de_registro_valido(self):
        """1. Un registro con todos los campos validos se procesa sin
        errores y conserva sus valores tipados."""
        meteoritos = analizar.validar_filas(FIELDNAMES, [FILAS_EJEMPLO[0]])
        self.assertEqual(len(meteoritos), 1)
        m = meteoritos[0]
        self.assertEqual(m["id"], 1)
        self.assertEqual(m["name"], "Meteorito Uno")
        self.assertEqual(m["recclass"], "L5")
        self.assertEqual(m["mass"], 1000.0)
        self.assertEqual(m["fall"], "Fell")
        self.assertEqual(m["year"], 1950)
        self.assertEqual(m["reclat"], 10.5)
        self.assertEqual(m["reclong"], 20.5)


class TestCalculoConResultadoConocido(unittest.TestCase):
    def test_calculo_de_indicador_conocido(self):
        """2. Con cifras chicas y conocidas, el total, Fell/Found y la
        masa media (solo valores disponibles) deben ser exactos."""
        meteoritos = analizar.validar_filas(FIELDNAMES, FILAS_EJEMPLO)
        stats = analizar.calcular(meteoritos)
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["fell"], 1)
        self.assertEqual(stats["found"], 2)
        # masa media disponible: (1000 + 2000) / 2 = 1500 (la tercera es NA)
        self.assertEqual(stats["masa_media"], 1500.0)
        self.assertEqual(stats["faltantes_masa"], 1)


class TestTratamientoDeFaltantes(unittest.TestCase):
    def test_dato_faltante_no_se_convierte_en_cero(self):
        """3. mass y year faltantes (NA / vacio) deben quedar como None,
        nunca como 0 -- y una coordenada en 0 debe seguir siendo valida."""
        meteoritos = analizar.validar_filas(FIELDNAMES, FILAS_EJEMPLO)
        tercero = next(m for m in meteoritos if m["id"] == 3)
        self.assertIsNone(tercero["mass"])
        self.assertIsNone(tercero["year"])
        self.assertNotEqual(tercero["mass"], 0)
        # reclat/reclong en "0" SI son datos validos (no faltantes)
        self.assertEqual(tercero["reclat"], 0.0)
        self.assertEqual(tercero["reclong"], 0.0)

    def test_year_extrae_de_fecha_completa_o_numero_suelto(self):
        """El campo year admite un numero suelto (incluso de pocos
        digitos, para caidas antiguas) o una fecha completa; en ambos
        casos se debe extraer el ano correctamente."""
        self.assertEqual(analizar.extraer_year("1880"), 1880)
        self.assertEqual(analizar.extraer_year("301"), 301)
        self.assertEqual(analizar.extraer_year("1/1/1880 12:00:00 AM"), 1880)
        self.assertIsNone(analizar.extraer_year("formato-raro-sin-digitos"))


class TestRechazoDeMasaNegativa(unittest.TestCase):
    def test_rechazo_de_masa_negativa(self):
        """4. Una masa negativa debe rechazar todo el archivo, indicando
        fila y columna (no se descarta en silencio)."""
        filas = [fila("1", "Meteorito", "L5", "-100", "Found", "2000", "0", "0")]
        with self.assertRaises(analizar.DatosInvalidos) as cm:
            analizar.validar_filas(FIELDNAMES, filas)
        mensaje = "\n".join(cm.exception.errores)
        self.assertIn("fila 2", mensaje)
        self.assertIn("mass (g)", mensaje)


class TestRechazoDeCoordenadasFueraDeRango(unittest.TestCase):
    def test_rechazo_de_latitud_fuera_de_rango(self):
        """5a. reclat fuera de [-90, 90] debe rechazarse."""
        filas = [fila("1", "Meteorito", "L5", "100", "Found", "2000", "95", "0")]
        with self.assertRaises(analizar.DatosInvalidos) as cm:
            analizar.validar_filas(FIELDNAMES, filas)
        mensaje = "\n".join(cm.exception.errores)
        self.assertIn("fila 2", mensaje)
        self.assertIn("reclat", mensaje)

    def test_rechazo_de_longitud_fuera_de_rango(self):
        """5b. reclong fuera de [-180, 180] debe rechazarse."""
        filas = [fila("1", "Meteorito", "L5", "100", "Found", "2000", "0", "200")]
        with self.assertRaises(analizar.DatosInvalidos) as cm:
            analizar.validar_filas(FIELDNAMES, filas)
        mensaje = "\n".join(cm.exception.errores)
        self.assertIn("fila 2", mensaje)
        self.assertIn("reclong", mensaje)


class TestRechazoDeIdentificadorDuplicado(unittest.TestCase):
    def test_rechazo_de_id_duplicado(self):
        """6. Un id que ya existe en el archivo debe rechazarse, citando
        ambas filas involucradas."""
        filas = [
            fila("7", "Primero", "L5", "100", "Found", "2000", "0", "0"),
            fila("7", "Segundo con mismo id", "H6", "200", "Found", "2001", "1", "1"),
        ]
        with self.assertRaises(analizar.DatosInvalidos) as cm:
            analizar.validar_filas(FIELDNAMES, filas)
        mensaje = "\n".join(cm.exception.errores)
        self.assertIn("fila 3", mensaje)
        self.assertIn("id", mensaje)
        self.assertIn("duplicado", mensaje)


class TestOtrasValidaciones(unittest.TestCase):
    def test_rechazo_de_fall_invalido(self):
        filas = [fila("1", "Meteorito", "L5", "100", "Caida", "2000", "0", "0")]
        with self.assertRaises(analizar.DatosInvalidos) as cm:
            analizar.validar_filas(FIELDNAMES, filas)
        self.assertIn("fall", "\n".join(cm.exception.errores))

    def test_rechazo_de_year_fuera_de_rango(self):
        filas = [fila("1", "Meteorito", "L5", "100", "Found", "2101", "0", "0")]
        with self.assertRaises(analizar.DatosInvalidos) as cm:
            analizar.validar_filas(FIELDNAMES, filas)
        self.assertIn("year", "\n".join(cm.exception.errores))

    def test_rechazo_de_name_o_recclass_vacio(self):
        filas = [fila("1", "   ", "L5", "100", "Found", "2000", "0", "0")]
        with self.assertRaises(analizar.DatosInvalidos) as cm:
            analizar.validar_filas(FIELDNAMES, filas)
        self.assertIn("name", "\n".join(cm.exception.errores))

    def test_rechazo_de_columna_obligatoria_ausente(self):
        cabecera_incompleta = [c for c in FIELDNAMES if c != "mass (g)"]
        with self.assertRaises(analizar.DatosInvalidos) as cm:
            analizar.validar_estructura(cabecera_incompleta)
        self.assertIn("mass (g)", "\n".join(cm.exception.errores))

    def test_sin_registros_se_detiene(self):
        with self.assertRaises(analizar.DatosInvalidos):
            analizar.validar_filas(FIELDNAMES, [])


class TestGeneracionDeInforme(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cwd_original = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.cwd_original)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _escribir_csv(self, filas):
        os.makedirs("datos", exist_ok=True)
        with open(analizar.ARCHIVO_ENTRADA, "w", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=FIELDNAMES)
            escritor.writeheader()
            for fila_ in filas:
                escritor.writerow(fila_)

    def test_main_genera_informe_con_datos_validos(self):
        self._escribir_csv(FILAS_EJEMPLO)
        # GITHUB_SHA lo setea automaticamente GitHub Actions en cada
        # corrida: hay que quitarlo a proposito para probar el caso
        # "local" (si no, en Actions este test fallaria).
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_SHA", None)
            analizar.main()

        self.assertTrue(os.path.exists("public/index.html"))
        with open("public/index.html", encoding="utf-8") as f:
            contenido = f.read()

        self.assertIn("Fabio Mavric", contenido)
        self.assertIn("Copia educativa: contiene modificaciones simuladas", contenido)
        self.assertIn("Commit: <code>local</code>", contenido)
        self.assertIn("Meteorito Tres", contenido)
        self.assertIn("sin dato", contenido)  # masa/year faltantes se muestran como tal

    def test_main_usa_github_sha_cuando_esta_seteado(self):
        self._escribir_csv(FILAS_EJEMPLO)
        with mock.patch.dict(os.environ, {"GITHUB_SHA": "abc1234"}):
            analizar.main()
        with open("public/index.html", encoding="utf-8") as f:
            contenido = f.read()
        self.assertIn("Commit: <code>abc1234</code>", contenido)

    def test_main_no_escribe_informe_si_los_datos_son_invalidos(self):
        filas_invalidas = [fila("1", "Meteorito", "L5", "-100", "Found", "2000", "0", "0")]
        self._escribir_csv(filas_invalidas)
        with self.assertRaises(SystemExit) as cm:
            analizar.main()
        self.assertNotEqual(cm.exception.code, 0)
        self.assertFalse(os.path.exists("public/index.html"))

    def test_html_escapado_en_nombres(self):
        filas = [fila("1", "5 <Test> & Cia", "L5", "100", "Found", "2000", "0", "0")]
        self._escribir_csv(filas)
        analizar.main()
        with open("public/index.html", encoding="utf-8") as f:
            contenido = f.read()
        self.assertNotIn("<Test>", contenido)
        self.assertIn("&lt;Test&gt;", contenido)


if __name__ == "__main__":
    unittest.main()
