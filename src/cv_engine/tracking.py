"""Registro de vacantes en CSV (output/vacantes.csv).

Cada `generate` agrega una fila, haya éxito o fallo. El CSV es el
historial: nunca se sobrescribe, solo se hace append.
"""

import csv
import re
from datetime import date
from pathlib import Path

URL_RE = re.compile(r"https?://[^\s)>\]]+")

COLUMNS = [
    "fecha",
    "puesto",
    "empresa",
    "link",
    "oferta_txt",
    "cv_pdf",
    "estado",
    "validacion",
]


def extraer_link(texto: str) -> str:
    """Primera URL del texto de la oferta, o vacío si no hay."""
    match = URL_RE.search(texto or "")
    if not match:
        return ""
    # Recorta puntuación final típica al pegar links ("...ver.", "...,").
    return match.group(0).rstrip(".,;:")


def registrar_vacante(
    csv_path: Path | str,
    puesto: str,
    empresa: str | None,
    oferta_txt: Path | str,
    descripcion_oferta: str = "",
    cv_pdf: Path | str | None = None,
    estado: str = "generado",
    validacion: str = "OK",
) -> Path:
    """Agrega una fila al CSV. Crea el archivo con header si no existe."""
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    existe = csv_path.exists()

    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if not existe:
            writer.writeheader()
        writer.writerow(
            {
                "fecha": date.today().isoformat(),
                "puesto": puesto or "",
                "empresa": empresa or "",
                "link": extraer_link(descripcion_oferta),
                "oferta_txt": str(oferta_txt),
                "cv_pdf": str(cv_pdf) if cv_pdf else "",
                "estado": estado,
                "validacion": validacion,
            }
        )

    return csv_path
