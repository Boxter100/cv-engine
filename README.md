# CV Engine

Motor local para generar CVs personalizados a partir de una oferta laboral.
Todo el procesamiento ocurre en tu máquina: un `llama-server` de llama.cpp y
LaTeX. No sale ningún dato a servicios externos.

## Cómo funciona

```
oferta (.txt) + CV maestro (data/profile/*.json)
   │
   ├─ generate   →  la IA lee el maestro y la oferta, hace match y crea el cv.json
   ├─ validate   →  chequeo determinista en una pasada (sin IA)
   └─ render     →  LaTeX → PDF
```

La idea central: **la IA lee, hace match y redacta; el maestro manda.** La IA
elige qué incluir, en qué orden, cómo reenfocar cada hecho y cómo resumir; el
CV maestro sigue siendo la única fuente de verdad. Cada bullet lleva el
registro del que salió (`source_type` + `source_index`) y la validación
bloquea lo que se desvíe: nombre, contacto, empresas, cargos, fechas,
tecnologías y cifras. Si la validación falla, **no se genera el PDF**.

## Requisitos

- Python 3.12+ (gestionado con `uv`)
- `llama-server` de llama.cpp escuchando en `http://127.0.0.1:8080/v1`
- Una distribución de LaTeX: `pdflatex` o `latexmk`, más los paquetes
  `geometry`, `titlesec`, `enumitem`, `fontawesome5`, `microtype`, `xcolor`,
  `lmodern`, `babel`, `ragged2e`, `hyperref`.

En Fedora:

```bash
sudo dnf install texlive-latex texlive-fonts-extra texlive-sansfonts latexmk poppler-utils
```

## Instalación

```bash
uv sync
```

## El CV maestro

La única fuente de verdad. Vive en `data/profile/` y son cinco archivos
(datos personales: **no se versionan en git**, ver `.gitignore`):

| Archivo | Contenido |
|---|---|
| `profile.json` | nombre, título, contacto, enlaces |
| `experience.json` | lista de empleos con logros y tecnologías |
| `projects.json` | proyectos personales o de cliente |
| `skills.json` | habilidades agrupadas por categoría |
| `education.json` | formación académica |

```bash
uv run cv-engine validate   # revisa que los JSON cumplan el esquema
```

Cuanto más concreto sea `achievements` y `highlights` en el texto libre, mejor
será el CV final. Escribe resultados, no tareas: "redujo el tiempo de carga de
3s a 900ms" funciona mucho mejor que "mejoró el rendimiento".

> Si clonas este repo en otra máquina, recrea `data/profile/` con tus 5 JSON.
> `data/jobs/*.txt` sí se versiona (son las ofertas de ejemplo).

## Uso

```bash
# Pipeline completo: cv.json, validation.json, cv.tex, cv.pdf + fila en vacantes.csv
uv run cv-engine generate data/jobs/mi-vacante.txt

# Solo convertir un cv.json existente a PDF (no usa IA, es determinista)
uv run cv-engine render output/mi-vacante/cv.json

# Volver a validar un cv.json editado a mano
uv run cv-engine validate-cv output/mi-vacante/cv.json

# Ver la oferta tal como la leerá la IA
uv run cv-engine analyze data/jobs/mi-vacante.txt
```

Opciones útiles de `generate`:

- `--out RUTA` — carpeta de salida (por defecto `output/<nombre-de-la-oferta>/`)
- `--engine xelatex` — motor alternativo de LaTeX

## Qué decide la IA y qué decide el motor

| Decisión | Quién |
|---|---|
| Qué experiencias y proyectos incluir, y en qué orden | IA |
| Cuántos bullets por registro y cuáles | IA |
| Cómo reenfocar cada hecho hacia el lenguaje de la vacante | IA |
| `summary` adaptado a la vacante (el título no se toca) | IA |
| `section_order` | IA, de entre las cinco secciones existentes |
| Qué grupos de habilidades mostrar | IA, solo con habilidades del maestro |
| Nombre, contacto, empresas, cargos, fechas | motor (copiados del maestro) |
| Habilidades o cifras que no estén en el maestro | motor las rechaza, no hay PDF |

Lo que la vacante pide y no tienes simplemente se omite: mejor un CV corto
y cierto que uno largo y falso.

## Validación

Una sola pasada determinista, sin IA:

- nombre y datos de contacto idénticos al CV maestro
- empresas, cargos y fechas copiados del maestro, nunca del modelo
- ninguna cifra o porcentaje que no exista en el CV maestro
- ninguna tecnología fuera del CV maestro
- referencias válidas a los registros de origen (`source_type` + `source_index`)

## Salidas

| Archivo | Qué es |
|---|---|
| `cv.json` | el CV adaptado, con la trazabilidad de cada bullet |
| `validation.json` | veredicto y lista de problemas |
| `cv.tex` | LaTeX generado |
| `cv.pdf` | resultado final |

`cv.json` es editable y puedes re-renderizar sin volver a llamar a la IA:

```bash
uv run cv-engine render output/mi-vacante/cv.json
```

## Registro de vacantes

Cada `generate` agrega una fila a `output/vacantes.csv` (éxito o fallo):

| Columna | Qué es |
|---|---|
| `fecha`, `puesto`, `empresa` | cuándo y para qué se generó |
| `link` | primera URL del `.txt`, o vacío (editable a mano en Excel) |
| `oferta_txt`, `cv_pdf` | rutas a la oferta y al PDF |
| `estado` | `generado` o `fallo_validacion` |
| `validacion` | `OK` o códigos de error |

## Personalizar el diseño

La plantilla está en
`src/cv_engine/generation/templates/cv.tex.j2`. Es un `article` pelado con
`geometry`, `titlesec`, `enumitem`, `fontawesome5` y `lmodern` — sin clases de CV
opinionadas, para que controles el diseño sin pelearte con la clase.

Una regla a tener en cuenta al editarla: las llaves de LaTeX no pueden tocar los
delimitadores de Jinja. Abre con `{ {{ valor }}` (espacio de por medio) y cierra
con `{{ valor }}}` (pegado). Mezclar los dos estilos rompe el parseo de Jinja.

## Variables de entorno

| Variable | Por defecto | Para qué |
|---|---|---|
| `LLAMA_SERVER_URL` | `http://127.0.0.1:8080/v1` | dirección del servidor |
| `LLAMA_MODEL` | el primero disponible | forzar un modelo concreto |
| `LLAMA_TIMEOUT` | `1800` | segundos por petición |
| `LLAMA_THINKING` | `false` | activa el modo razonamiento del modelo |

Sobre `LLAMA_THINKING`: los modelos de razonamiento pueden ser más cuidadosos,
pero gastan mucho más tiempo (~15s normal vs ~75s con razonamiento).

## Desarrollo

```bash
uv run pytest              # 34 tests, ninguno necesita GPU ni LaTeX
uv run pytest -k latex     # solo los que compilan PDF de verdad
```

La suite no toca la red: el cliente de llama-server se inyecta como dependencia
en `CVGenerator` (ver `tests/conftest.py`, clase `FakeClient`).

## Privacidad

`.gitignore` excluye todo lo que contiene datos personales:

- `output/` — PDFs, CVs generados y `vacantes.csv`
- `data/profile/` — tu nombre, email, teléfono e historial
- `.env`, `.env.*` — configuración local
