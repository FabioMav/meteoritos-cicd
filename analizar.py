"""
analizar.py
Lee datos/meteoritos.csv (incluido en el repositorio, no se descarga nada),
lo valida por completo y genera public/index.html con el informe.

Datos: muestra de 20.000 registros de "Meteorite Landings" (NASA / The
Meteoritical Society). Columnas obligatorias: id, name, recclass,
"mass (g)", fall, year, reclat, reclong.

Reglas de validacion, segun la consigna:
  - La cabecera debe tener las 8 columnas obligatorias.
  - Debe haber al menos un registro.
  - Cada fila debe tener el numero correcto de campos.
  - id: entero positivo, obligatorio y unico en todo el archivo.
  - name y recclass: texto obligatorio, no vacio despues de quitar espacios.
  - mass (g): numero finito >= 0, CUANDO ESTE DISPONIBLE (admite faltante).
  - fall: unicamente "Fell" o "Found" (obligatorio, sin faltantes).
  - year: CUANDO ESTE DISPONIBLE, entero entre 1 y 2026. El campo puede
    venir como un numero de ano suelto ("1880", o incluso de pocos digitos
    para caidas muy antiguas, p. ej. "301") o como una fecha completa
    exportada por el portal de NASA (p. ej. "1/1/1880 12:00:00 AM"). Este
    programa primero intenta interpretar el campo entero como un numero
    (para no romper anos antiguos de pocos digitos), y si no es puramente
    numerico busca los primeros 4 digitos consecutivos dentro del texto
    (el componente de ano de una fecha). Si no encuentra ninguna de las
    dos formas, lo marca como formato de fecha no reconocido.
  - reclat: numero finito entre -90 y 90, cuando este disponible.
  - reclong: numero finito entre -180 y 180, cuando este disponible.
  - Los datos faltantes (mass, year, reclat, reclong) NUNCA se convierten
    en 0: se reconocen como faltantes el campo vacio y, por si se escriben
    a mano durante las pruebas, tambien "NA", "N/A" y "#N/A".
  - Ante cualquier dato invalido, el programa junta TODOS los errores
    encontrados (cada uno con su fila y su columna), los imprime y termina
    con codigo de salida distinto de cero, sin escribir un informe nuevo
    (no corrige ni descarta filas en silencio).

Preparacion de la muestra (documentado tambien en el README/informe):
  La fuente oficial (data.nasa.gov) no fue alcanzable desde este entorno
  de preparacion; se uso como base un espejo de los mismos datos oficiales
  de NASA/Meteoritical Society (mismas 45.716 filas, mismos valores de id,
  name, recclass, mass, fall, year, reclat, reclong), publicado en GitHub
  por pylablanche/Kaggle_Meteorites a partir del dataset de Kaggle "NASA
  Meteorites Landings". Se tomaron las primeras 20.000 filas de ese
  archivo en su orden (que es alfabetico por "name", no por "id" como el
  export directo de NASA), se selecciono unicamente las 8 columnas
  pedidas, y se renombro "mass" a "mass (g)" para que coincida con el
  nombre oficial de la columna. Se audito el archivo completo (45.716
  filas) en busca de anomalias (year fuera de 1-2026, reclat/reclong
  fuera de rango, mass negativa) antes de fijar la version inicial: se
  encontraron exactamente 3 filas anomalas en todo el archivo (dos con
  year invalido por error de tipeo del dato original, 2101 y 2501, y una
  con reclong=354.47 -- el meteorito "Meridiani Planum", hallado por el
  rover Opportunity en Marte, cuya longitud original esta expresada en
  convencion 0-360 en vez de -180-180); ninguna de las tres cae dentro de
  las primeras 20.000 filas usadas aqui, asi que la muestra queda limpia
  sin necesidad de corregir nada a mano.
"""
import csv
import html
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

ARCHIVO_ENTRADA = "datos/meteoritos.csv"
DIRECTORIO_SALIDA = "public"
ARCHIVO_SALIDA = f"{DIRECTORIO_SALIDA}/index.html"

NOMBRE_ESTUDIANTE = "Fabio Mavric"
URL_FUENTE = "https://data.nasa.gov/dataset/meteorite-landings"
URL_CSV_ORIGINAL = "https://data.nasa.gov/docs/legacy/meteorite_landings/Meteorite_Landings.csv"

COLUMNAS_OBLIGATORIAS = ["id", "name", "recclass", "mass (g)", "fall", "year", "reclat", "reclong"]
MARCAS_FALTANTE = {"", "NA", "N/A", "#N/A"}
VALORES_FALL_VALIDOS = {"Fell", "Found"}

ANO_MINIMO = 1
ANO_MAXIMO = 2026


class DatosInvalidos(Exception):
    """Junta uno o mas errores de validacion (cada uno con fila y columna)."""

    def __init__(self, errores):
        self.errores = list(errores)
        super().__init__("\n".join(self.errores))


def leer_filas(ruta_csv):
    """Devuelve (fieldnames, filas_crudas) leyendo el CSV con DictReader.
    No valida contenido todavia; solo deja ver la cabecera y las filas tal
    cual estan en el archivo."""
    try:
        with open(ruta_csv, newline="", encoding="utf-8") as f:
            lector = csv.DictReader(f, restkey="__campos_de_mas__")
            fieldnames = lector.fieldnames or []
            filas = list(lector)
    except FileNotFoundError as exc:
        raise DatosInvalidos(
            [f"No se encontro {ruta_csv}. Debe estar en el repositorio (no se descarga)."]
        ) from exc
    return fieldnames, filas


def validar_estructura(fieldnames):
    """Valida la cabecera: deben estar las 8 columnas obligatorias."""
    faltantes = [c for c in COLUMNAS_OBLIGATORIAS if c not in fieldnames]
    if faltantes:
        raise DatosInvalidos(
            [f"cabecera, columna '{c}': falta la columna obligatoria" for c in faltantes]
        )


def _valor_numerico_opcional(valor, columna, numero_fila, errores, minimo=None, maximo=None):
    """Para mass/reclat/reclong: NA/N/A/#N/A/vacio -> None (faltante,
    nunca 0). Si hay valor, debe ser un numero finito; si se pasan
    'minimo'/'maximo', ademas debe caer en ese rango (incluyente). Si algo
    falla se agrega un error con fila y columna y se devuelve None."""
    texto = "" if valor is None else str(valor).strip()
    if texto in MARCAS_FALTANTE:
        return None
    try:
        numero = float(texto)
    except ValueError:
        errores.append(
            f"fila {numero_fila}, columna '{columna}': valor no numerico ({texto!r})"
        )
        return None
    if not math.isfinite(numero):
        errores.append(
            f"fila {numero_fila}, columna '{columna}': debe ser un numero finito "
            f"(se encontro {texto!r})"
        )
        return None
    if minimo is not None and numero < minimo:
        errores.append(
            f"fila {numero_fila}, columna '{columna}': debe ser >= {minimo} "
            f"(se encontro {texto!r})"
        )
        return None
    if maximo is not None and numero > maximo:
        errores.append(
            f"fila {numero_fila}, columna '{columna}': debe ser <= {maximo} "
            f"(se encontro {texto!r})"
        )
        return None
    return numero


_PATRON_SOLO_DIGITOS = re.compile(r"\d+")
_PATRON_CUATRO_DIGITOS = re.compile(r"\d{4}")


def extraer_year(texto):
    """Interpreta el campo 'year', que puede venir como un numero de ano
    suelto (incluso de pocos digitos, para caidas muy antiguas) o como una
    fecha completa exportada por el portal de NASA (p. ej.
    '1/1/1880 12:00:00 AM'). Devuelve un int, o None si no se pudo
    interpretar ninguna de las dos formas."""
    if _PATRON_SOLO_DIGITOS.fullmatch(texto):
        return int(texto)
    coincidencia = _PATRON_CUATRO_DIGITOS.search(texto)
    if coincidencia:
        return int(coincidencia.group(0))
    return None


def validar_filas(fieldnames, filas):
    """Valida cada fila y devuelve la lista de meteoritos validos. Junta
    TODOS los errores que encuentre (no se detiene en el primero) y al
    final lanza DatosInvalidos con la lista completa si hay alguno."""
    errores = []
    meteoritos = []
    vistos = {}  # id -> primera fila donde aparecio

    if not filas:
        raise DatosInvalidos(["no hay ningun registro de datos (el CSV solo tiene cabecera)"])

    n_columnas_esperadas = len(fieldnames)

    for indice, fila in enumerate(filas):
        numero_fila = indice + 2  # fila 1 es la cabecera

        if "__campos_de_mas__" in fila:
            errores.append(
                f"fila {numero_fila}, estructura: tiene mas campos de los "
                f"{n_columnas_esperadas} esperados segun la cabecera"
            )
            continue
        if any(fila.get(c) is None for c in fieldnames):
            errores.append(
                f"fila {numero_fila}, estructura: tiene menos campos de los "
                f"{n_columnas_esperadas} esperados segun la cabecera"
            )
            continue

        id_texto = (fila.get("id") or "").strip()
        name_crudo = (fila.get("name") or "").strip()
        recclass_crudo = (fila.get("recclass") or "").strip()
        fall_crudo = (fila.get("fall") or "").strip()
        year_texto = (fila.get("year") or "").strip()

        id_valido = None
        if not id_texto:
            errores.append(f"fila {numero_fila}, columna 'id': identificador vacio")
        else:
            try:
                id_num = int(id_texto)
                if id_num <= 0:
                    errores.append(
                        f"fila {numero_fila}, columna 'id': debe ser un entero "
                        f"positivo (se encontro {id_texto!r})"
                    )
                else:
                    id_valido = id_num
                    if id_texto in vistos:
                        errores.append(
                            f"fila {numero_fila}, columna 'id': identificador duplicado "
                            f"{id_texto!r} (ya aparece en la fila {vistos[id_texto]})"
                        )
                    else:
                        vistos[id_texto] = numero_fila
            except ValueError:
                errores.append(
                    f"fila {numero_fila}, columna 'id': no es un entero valido "
                    f"(se encontro {id_texto!r})"
                )

        if not name_crudo:
            errores.append(f"fila {numero_fila}, columna 'name': nombre vacio")

        if not recclass_crudo:
            errores.append(f"fila {numero_fila}, columna 'recclass': clasificacion vacia")

        if fall_crudo not in VALORES_FALL_VALIDOS:
            errores.append(
                f"fila {numero_fila}, columna 'fall': debe ser 'Fell' o 'Found' "
                f"(se encontro {fall_crudo!r})"
            )

        year = None
        if year_texto and year_texto not in MARCAS_FALTANTE:
            year = extraer_year(year_texto)
            if year is None:
                errores.append(
                    f"fila {numero_fila}, columna 'year': formato de fecha no "
                    f"reconocido (se encontro {year_texto!r})"
                )
            elif not (ANO_MINIMO <= year <= ANO_MAXIMO):
                errores.append(
                    f"fila {numero_fila}, columna 'year': debe estar entre "
                    f"{ANO_MINIMO} y {ANO_MAXIMO} (se encontro {year_texto!r})"
                )
                year = None

        mass = _valor_numerico_opcional(fila.get("mass (g)"), "mass (g)", numero_fila, errores, minimo=0)
        reclat = _valor_numerico_opcional(fila.get("reclat"), "reclat", numero_fila, errores, minimo=-90, maximo=90)
        reclong = _valor_numerico_opcional(fila.get("reclong"), "reclong", numero_fila, errores, minimo=-180, maximo=180)

        if id_valido is not None and name_crudo and recclass_crudo and fall_crudo in VALORES_FALL_VALIDOS:
            meteoritos.append({
                "id": id_valido,
                "name": name_crudo,
                "recclass": recclass_crudo,
                "mass": mass,
                "fall": fall_crudo,
                "year": year,
                "reclat": reclat,
                "reclong": reclong,
                "orden_original": indice,
            })

    if errores:
        raise DatosInvalidos(errores)

    return meteoritos


def calcular(meteoritos):
    """Separado de la validacion: solo calcula, sobre datos ya validos."""
    total = len(meteoritos)
    fell = sum(1 for m in meteoritos if m["fall"] == "Fell")
    found = sum(1 for m in meteoritos if m["fall"] == "Found")

    con_masa = [m for m in meteoritos if m["mass"] is not None]
    masa_media = (sum(m["mass"] for m in con_masa) / len(con_masa)) if con_masa else None
    faltantes_masa = total - len(con_masa)

    conteo_clases = Counter(m["recclass"] for m in meteoritos)
    top10_clases = conteo_clases.most_common(10)

    top10_masa = sorted(con_masa, key=lambda m: m["mass"], reverse=True)[:10]

    por_orden = sorted(meteoritos, key=lambda m: m["orden_original"])
    ultimos10 = por_orden[-10:]

    return {
        "total": total,
        "fell": fell,
        "found": found,
        "masa_media": masa_media,
        "faltantes_masa": faltantes_masa,
        "top10_clases": top10_clases,
        "top10_masa": top10_masa,
        "ultimos10": ultimos10,
    }


def construir_svg_clases(top10_clases):
    """Barras con las 10 clasificaciones (recclass) mas frecuentes."""
    if not top10_clases:
        return "<p>No hay suficientes datos para el grafico.</p>"
    maximo = max(cant for _clase, cant in top10_clases)
    ancho_barra = 56
    espacio = 18
    alto_grafico = 220
    margen_inferior = 54
    ancho_svg = len(top10_clases) * (ancho_barra + espacio) + espacio
    alto_svg = alto_grafico + margen_inferior

    barras = []
    for i, (clase, cantidad) in enumerate(top10_clases):
        alto_barra = (cantidad / maximo) * (alto_grafico - 24) if maximo else 0
        x = espacio + i * (ancho_barra + espacio)
        y = alto_grafico - alto_barra
        barras.append(
            f'<rect x="{x}" y="{y:.1f}" width="{ancho_barra}" height="{alto_barra:.1f}" '
            f'fill="#2a78d6" rx="3"><title>{html.escape(clase)}: {cantidad}</title></rect>'
            f'<text x="{x + ancho_barra / 2}" y="{y - 6:.1f}" font-size="11" '
            f'text-anchor="middle" fill="#0b0b0b" class="valor-barra">{cantidad}</text>'
            f'<text x="{x + ancho_barra / 2}" y="{alto_grafico + 16}" font-size="10" '
            f'text-anchor="middle" fill="#52514e">{html.escape(clase)}</text>'
        )
    return (
        f'<svg viewBox="0 0 {ancho_svg} {alto_svg}" width="100%" '
        f'style="max-width:{ancho_svg}px; height:auto;" role="img" '
        f'aria-label="Diez clasificaciones mas frecuentes">' + "".join(barras) + "</svg>"
    )


def generar_html(stats, hora_generacion_utc, commit_sha):
    total = stats["total"]
    fell = stats["fell"]
    found = stats["found"]
    masa_media = stats["masa_media"]
    faltantes_masa = stats["faltantes_masa"]
    top10_clases = stats["top10_clases"]
    top10_masa = stats["top10_masa"]
    ultimos10 = stats["ultimos10"]

    svg_grafico = construir_svg_clases(top10_clases)

    def celda_masa(valor):
        return f"{valor:,.1f} g" if valor is not None else "sin dato"

    def celda_coord(valor):
        return f"{valor:.5f}" if valor is not None else "sin dato"

    def celda_year(valor):
        return str(valor) if valor is not None else "sin dato"

    filas_ranking_masa = "\n".join(
        f"<tr><td>{i + 1}</td><td>{html.escape(m['name'])}</td>"
        f"<td>{html.escape(m['recclass'])}</td><td>{celda_masa(m['mass'])}</td></tr>"
        for i, m in enumerate(top10_masa)
    )

    filas_ultimos10 = "\n".join(
        f"<tr><td>{m['id']}</td><td>{html.escape(m['name'])}</td>"
        f"<td>{html.escape(m['recclass'])}</td><td>{celda_masa(m['mass'])}</td>"
        f"<td>{html.escape(m['fall'])}</td><td>{celda_year(m['year'])}</td>"
        f"<td>{celda_coord(m['reclat'])}</td><td>{celda_coord(m['reclong'])}</td></tr>"
        for m in ultimos10
    )

    masa_media_texto = f"{masa_media:,.2f} g" if masa_media is not None else "sin dato"

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe de meteoritos (Meteorite Landings, NASA)</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, sans-serif; max-width: 920px; margin: 2rem auto; padding: 0 1rem;
          line-height: 1.5; color: #0b0b0b; background: #fcfcfb; }}
  svg .valor-barra {{ fill: #0b0b0b; }}
  @media (prefers-color-scheme: dark) {{
    body {{ color: #f0efec; background: #1a1a19; }}
    td, th {{ border-color: #3a3a38 !important; }}
    .aviso {{ background: rgba(230,160,40,0.14) !important; }}
    svg .valor-barra {{ fill: #f0efec; }}
  }}
  h1 {{ margin-bottom: 0.2rem; font-size: 1.5rem; }}
  .subtitulo {{ color: #52514e; margin-top: 0; }}
  .aviso {{ background: rgba(230,160,40,0.12); border-left: 4px solid #d98c1a; border-radius: 6px;
            padding: 0.8rem 1rem; margin: 1rem 0; font-size: 0.92rem; }}
  .indicadores {{ display: flex; gap: 1.2rem; flex-wrap: wrap; margin: 1.5rem 0; }}
  .indicador {{ background: rgba(42,120,214,0.08); border-radius: 10px; padding: 0.8rem 1.1rem; min-width: 160px; }}
  .indicador .valor {{ font-size: 1.4rem; font-weight: 700; }}
  .indicador .etiqueta {{ font-size: 0.82rem; color: #52514e; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: 0.85rem; }}
  th, td {{ border: 1px solid #d8d6d0; padding: 0.35rem 0.5rem; text-align: left; }}
  th {{ background: rgba(42,120,214,0.08); }}
  .tabla-scroll {{ overflow-x: auto; }}
  footer {{ margin-top: 2rem; font-size: 0.85rem; color: #52514e; }}
  a {{ color: #2a78d6; }}
  code {{ font-size: 0.85em; }}
</style>
</head>
<body>
  <h1>Informe de meteoritos (Meteorite Landings, NASA)</h1>
  <p class="subtitulo">{html.escape(NOMBRE_ESTUDIANTE)} &middot;
    Fuente: <a href="{URL_FUENTE}">NASA Open Data &ndash; Meteorite Landings</a>
    (datos de The Meteoritical Society; CSV original:
    <a href="{URL_CSV_ORIGINAL}">Meteorite_Landings.csv</a>)</p>

  <p class="aviso"><strong>Copia educativa: contiene modificaciones simuladas.</strong>
    Los registros agregados o alterados durante esta practica de CI/CD son simulaciones
    para demostrar el flujo de validacion y publicacion; no representan correcciones ni
    aportes a la base de datos original de The Meteoritical Society / NASA.</p>

  <p>Generado: <strong>{hora_generacion_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC</strong><br>
     Commit: <code>{html.escape(commit_sha)}</code></p>

  <div class="indicadores">
    <div class="indicador"><div class="valor">{total}</div><div class="etiqueta">Registros totales</div></div>
    <div class="indicador"><div class="valor">{fell}</div><div class="etiqueta">Fell (caida observada)</div></div>
    <div class="indicador"><div class="valor">{found}</div><div class="etiqueta">Found (hallazgo posterior)</div></div>
    <div class="indicador"><div class="valor">{masa_media_texto}</div><div class="etiqueta">Masa media (solo valores disponibles)</div></div>
    <div class="indicador"><div class="valor">{faltantes_masa}</div><div class="etiqueta">Registros sin dato de masa</div></div>
  </div>

  <h2>Diez clasificaciones (recclass) mas frecuentes</h2>
  {svg_grafico}

  <h2>Ranking: diez meteoritos de mayor masa</h2>
  <div class="tabla-scroll">
  <table>
    <thead><tr><th>#</th><th>name</th><th>recclass</th><th>mass (g)</th></tr></thead>
    <tbody>
    {filas_ranking_masa}
    </tbody>
  </table>
  </div>

  <h2>Ultimos diez registros del CSV</h2>
  <p>En el orden del archivo (no por masa), para poder comprobar las incorporaciones
    agregadas al final durante la practica.</p>
  <div class="tabla-scroll">
  <table>
    <thead><tr><th>id</th><th>name</th><th>recclass</th><th>mass (g)</th>
      <th>fall</th><th>year</th><th>reclat</th><th>reclong</th></tr></thead>
    <tbody>
    {filas_ultimos10}
    </tbody>
  </table>
  </div>

  <footer>
    <p>Datos: <a href="{URL_FUENTE}">NASA Open Data &ndash; Meteorite Landings</a>,
      con datos de The Meteoritical Society. "mass (g)" es la masa del meteorito en
      gramos; los campos de masa, year, reclat y reclong pueden faltar en el
      registro original (no se completan con 0).</p>
    <p>Generado automaticamente por GitHub Actions a partir de datos/meteoritos.csv
      del repositorio.</p>
  </footer>
</body>
</html>
"""


def main():
    try:
        fieldnames, filas = leer_filas(ARCHIVO_ENTRADA)
        validar_estructura(fieldnames)
        meteoritos = validar_filas(fieldnames, filas)
    except DatosInvalidos as exc:
        print("ERROR: se encontraron datos invalidos en "
              f"{ARCHIVO_ENTRADA}; no se genera un informe nuevo.", file=sys.stderr)
        for mensaje in exc.errores:
            print(f"  - {mensaje}", file=sys.stderr)
        sys.exit(1)

    stats = calcular(meteoritos)
    os.makedirs(DIRECTORIO_SALIDA, exist_ok=True)

    hora_generacion_utc = datetime.now(timezone.utc)
    commit_sha = os.environ.get("GITHUB_SHA") or "local"
    contenido = generar_html(stats, hora_generacion_utc, commit_sha)
    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
        f.write(contenido)

    print(f"OK: {ARCHIVO_SALIDA} generado con {stats['total']} meteoritos validos.")


if __name__ == "__main__":
    main()
