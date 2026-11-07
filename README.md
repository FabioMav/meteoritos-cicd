# meteoritos-cicd

Informe automatizado sobre caidas de meteoritos (dataset **Meteorite
Landings** de la NASA / The Meteoritical Society), con validacion y
publicacion continua usando **GitHub Actions** y **GitHub Pages**.

Trabajo practico de CI/CD — Fabio Mavric (UNIVALLE Cochabamba, Ingenieria
en Ciencia de Datos e Inteligencia de Negocios).

## Que hace este proyecto

`analizar.py` lee `datos/meteoritos.csv` (ya incluido en el repositorio:
**no se descarga nada** en ningun momento) y genera `public/index.html`,
un informe con: total de registros, cantidad Fell/Found, masa media
disponible, conteo de registros sin masa, un grafico con las diez
clasificaciones (`recclass`) mas frecuentes, un ranking de los diez
meteoritos de mayor masa y una tabla con los ultimos diez registros del
CSV (para comprobar las incorporaciones de las pruebas).

Cada `push` a `main` (o una ejecucion manual) dispara el workflow
`.github/workflows/meteoritos.yml`:

- **`ci` (CI — Verificacion):** prepara Python 3.12, corre
  `python -m unittest discover -v`, valida `datos/meteoritos.csv` por
  completo y genera el sitio con `python analizar.py`. Si el CSV tiene
  algun dato invalido, `analizar.py` termina con codigo de salida
  distinto de cero **y no genera un informe nuevo** — el job falla y no
  se sube nada a Pages.
- **`cd` (CD — Publicacion):** solo corre si `ci` termino bien
  (`needs: ci`), y publica `public/` en GitHub Pages.

## Preparacion de la muestra de datos

El dataset oficial es **Meteorite Landings**
(https://data.nasa.gov/dataset/meteorite-landings, datos de The
Meteoritical Society, CSV original en
https://data.nasa.gov/docs/legacy/meteorite_landings/Meteorite_Landings.csv).

Para preparar `datos/meteoritos.csv` (desde el entorno usado para armar
este proyecto, que no tenia acceso directo a `data.nasa.gov`) se uso como
base un espejo publico de los **mismos datos oficiales** (mismas 45.716
filas, mismos valores de `id`, `name`, `recclass`, `mass`, `fall`, `year`,
`reclat`, `reclong`), publicado en GitHub por
[pylablanche/Kaggle_Meteorites](https://github.com/pylablanche/Kaggle_Meteorites)
a partir del dataset "NASA Meteorites Landings" de Kaggle, que a su vez
proviene de la misma fuente de NASA/Meteoritical Society.

Pasos de preparacion:

1. Se tomaron las **primeras 20.000 filas de datos** de ese espejo, en su
   orden tal cual aparecen en el archivo (ese espejo esta ordenado
   alfabeticamente por `name`, no por `id` como el export directo de
   NASA — se documenta aqui por transparencia, ya que es una diferencia
   de orden respecto al archivo oficial, aunque no afecta a ninguna
   regla de validacion).
2. Se seleccionaron unicamente las 8 columnas pedidas: `id`, `name`,
   `recclass`, `mass (g)`, `fall`, `year`, `reclat`, `reclong`.
3. **Diferencia de nombre de columna:** el espejo trae la columna de masa
   como `mass` (sin unidad en el nombre); se renombro a `mass (g)` para
   coincidir con el nombre oficial de la consigna. Tambien se descartaron
   las columnas `nametype` y `GeoLocation` del espejo, que no estan entre
   las 8 pedidas.
4. **Faltantes:** en este archivo los campos de `mass (g)`, `year`,
   `reclat` y `reclong` faltantes vienen como **cadena vacia**. El
   programa tambien reconoce `NA`, `N/A` y `#N/A` como las mismas marcas
   de faltante, por si se escriben a mano al agregar registros de prueba.
   Nunca se convierten en 0 (una coordenada en 0 es un dato valido).
5. **Anomalias detectadas y su tratamiento:** antes de fijar la version
   inicial se audito el archivo completo (45.716 filas) buscando
   registros fuera de las reglas de validacion (year fuera de 1-2026,
   `reclat`/`reclong` fuera de rango, masa negativa). Se encontraron
   exactamente **3 filas anomalas en todo el archivo**:
   - Dos registros con `year` invalido por error de tipeo del dato
     original: `Northwest Africa 7701` (year=2101) y `Ur` (year=2501).
   - Un registro con `reclong`=354.47: **Meridiani Planum**, el
     meteorito hallado por el rover *Opportunity* **en Marte** en 2005,
     cuya longitud original esta expresada en convencion 0-360 en vez de
     -180 a 180 (una curiosidad real y bien documentada del dataset
     oficial de NASA).

   Ninguna de las tres cae dentro de las primeras 20.000 filas usadas en
   este proyecto, asi que la muestra queda limpia sin necesidad de
   corregir nada a mano para fijar la version inicial.
6. **El campo `year` puede venir como fecha completa:** el export directo
   de NASA expresa `year` como una fecha completa (p. ej.
   `1/1/1880 12:00:00 AM`), mientras que este espejo ya trae el ano
   extraido como numero simple (p. ej. `1880`). `analizar.py` esta
   preparado para **ambos formatos**: primero intenta leer el campo
   entero como numero (para no romper anos antiguos de pocos digitos,
   como `301`), y si no es puramente numerico busca los primeros 4
   digitos consecutivos dentro del texto (el componente de ano de una
   fecha). Ver la funcion `extraer_year()` en `analizar.py`, probada en
   `test_analizar.py` con ambos formatos.

## Columnas obligatorias y reglas de validacion

| Columna | Regla |
|---|---|
| Estructura | Deben estar las 8 columnas; cada fila con el numero correcto de campos. |
| `id` | Entero positivo, obligatorio, unico en todo el archivo. |
| `name`, `recclass` | Texto obligatorio, no vacio tras quitar espacios. |
| `mass (g)` | Numero finito >= 0, cuando este disponible (admite faltante). |
| `fall` | Unicamente `Fell` o `Found` (obligatorio). |
| `year` | Cuando este disponible: entero entre 1 y 2026 (admite fecha completa, ver arriba). |
| `reclat` | Numero finito entre -90 y 90, cuando este disponible. |
| `reclong` | Numero finito entre -180 y 180, cuando este disponible. |

Si hay cualquier dato invalido, `analizar.py` junta **todos** los errores
encontrados (cada uno con su fila y su columna), los imprime por `stderr`
y termina con `sys.exit(1)` sin escribir `public/index.html` — no corrige
ni descarta filas invalidas en silencio, ni siquiera las agregadas
durante las pruebas.

## Valores de referencia (CSV original, sin editar)

Con el `datos/meteoritos.csv` tal como viene preparado en este proyecto:

- Total de registros: **20000**
- Fell: **1107** &middot; Found: **18893**
- Masa media disponible: **21,876.97 g**
- Registros sin dato de masa: **70**
- Clasificacion mas frecuente: **L6** (4694 registros)
- Meteorito de mayor masa: **Hoba**, 60,000,000 g (60 toneladas — es,
  efectivamente, el meteorito mas masivo conocido en la Tierra; buena
  forma de confirmar que los datos son reales)
- Ultimo registro del CSV: id `13027`, *Lewis Cliff 86088*

Vas a usar estos numeros para comparar despues de agregar o editar
registros.

## Estructura del proyecto

```
datos/meteoritos.csv          # CSV fuente (20.000 filas), SI va al repositorio
analizar.py                   # validacion + calculo + generacion de public/index.html
test_analizar.py              # pruebas unittest, con datos propios (no el CSV real)
.github/workflows/meteoritos.yml  # workflow de CI (ci) y CD (cd)
.gitignore                    # public/, __pycache__/, .venv/
githooks/post-commit          # opcional: push automatico tras cada commit (ver mas abajo)
public/index.html             # se genera al ejecutar analizar.py (no se versiona)
```

No se usa ninguna biblioteca externa (solo la biblioteca estandar de
Python 3.12), asi que no hace falta `requirements.txt`.

## Como correrlo en tu computadora

Terminal de VS Code, en la raiz del proyecto:

```bash
python -m unittest discover -v
python analizar.py
```

(Si tu sistema usa otro comando, cambia `python` por `python3` o `py`.)

Despues abre `public/index.html` en el navegador y revisa que el total
inicial sea **20000 registros**.

## Push automatico al hacer commit (opcional, solo comodidad local)

El proyecto trae un git hook (`githooks/post-commit`) que hace el push a
`origin` automaticamente apenas termina cada commit en GitHub Desktop, en
vez de tener que apretar "Push origin" a mano. No es parte de la
consigna. Para activarlo, una sola vez, en la terminal de VS Code parado
en la raiz del proyecto:

```bash
git config core.hooksPath githooks
```

(En Mac/Linux tambien: `chmod +x githooks/post-commit`.) Si el push
automatico falla (sin conexion, o cambios remotos que no tenes
localmente), el commit se hace igual y GitHub Desktop sigue mostrando
"Push origin" disponible como aviso.

## Pasos para crear y publicar el proyecto

1. Crea en GitHub un repositorio **publico** llamado `meteoritos-cicd`.
   Clonalo con GitHub Desktop y abrelo en VS Code.
2. Copia todos los archivos de este proyecto dentro del repositorio
   clonado (incluye las carpetas ocultas `.github/` y `.gitignore`, y la
   carpeta `githooks/`).
3. En GitHub → **Settings → Pages → Build and deployment → Source →
   GitHub Actions**.
4. En GitHub Desktop: deberian verse como cambios `datos/meteoritos.csv`,
   `analizar.py`, `test_analizar.py`, `.gitignore`, `README.md`,
   `.github/workflows/meteoritos.yml` y `githooks/post-commit`. Commit
   (p. ej. "Primera version del informe de meteoritos") y Push origin.
5. En GitHub → **Actions**, abre "Meteoritos - CI y CD" y espera que `ci`
   y `cd` terminen en verde. En Settings → Pages, abre "Visit site"
   (normalmente `https://TU-USUARIO.github.io/meteoritos-cicd/`).
6. Anota los indicadores principales de esta primera version (los
   "Valores de referencia" de arriba) para tu informe.

## Paso 7 — demostrar una actualizacion valida

1. Agrega al final de `datos/meteoritos.csv` un meteorito ficticio con un
   `id` **nuevo** (que no exista ya), un `name` reconocible (p. ej. algo
   como "Meteorito Prueba Fabio") y datos validos en todas las columnas.
2. Corre `python -m unittest discover -v` y `python analizar.py`
   localmente; confirma que el total subio en 1 y que el nuevo registro
   aparece en la tabla de "ultimos diez registros".
3. Commit (p. ej. "Simular nuevo hallazgo de meteorito") y Push origin.
4. En Actions, espera que `ci` y `cd` terminen en verde para ese commit.
5. En GitHub Pages, confirma que el total aumento en 1, que el nuevo
   registro aparece en la tabla, y anota el identificador del commit.

## Paso 8 — demostrar que datos invalidos bloquean CD

Repeti esto **tres veces por separado** (una prueba a la vez, cada una
con su propio commit):

1. **Masa invalida:** agrega un registro con `mass (g)` negativo (p. ej.
   `-100`).
2. **Coordenada invalida:** agrega un registro con `reclat` o `reclong`
   fuera de rango (p. ej. `reclat=120`).
3. **Identificador duplicado:** agrega un registro cuyo `id` ya exista en
   el archivo (p. ej. repeti el `id` que usaste en el paso 7).

Para cada caso: corre `python analizar.py` localmente y confirma que
falla con un mensaje que indique la fila y la columna exactas; despues
Commit y Push **a proposito** para ver el mismo bloqueo en GitHub
Actions — el job `ci` debe fallar, `cd` debe aparecer omitido, y GitHub
Pages debe conservar la ultima version valida (la del paso 7). Despues
corregi el dato (o elimina esa fila de prueba) y volve a enviar el
cambio para dejar el repositorio en verde otra vez.

## Si el cambio no aparece

- Comprueba primero que el nuevo valor este en `datos/meteoritos.csv`
  dentro de GitHub, en `main` (que no haya quedado sin `commit` o sin
  `push`).
- Revisa la ejecucion de Actions asociada al ultimo commit: `cd` tambien
  debe haber terminado bien. Abre la URL del despliegue y recarga sin
  cache.
- No edites `public/index.html` directamente: Actions lo vuelve a
  generar en cada ejecucion. No descargues otra copia del CSV: el
  proyecto siempre lee `datos/meteoritos.csv` del repositorio.
