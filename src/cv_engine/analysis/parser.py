from pathlib import Path

from cv_engine.models import JobDescription


def _es_url(linea: str) -> bool:
    return linea.strip().lower().startswith(("http://", "https://"))


def parse_job_file(path: str | Path) -> JobDescription:
    path = Path(path)

    text = path.read_text(encoding="utf-8").strip()

    if not text:
        raise ValueError("Job description is empty.")

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # El link de la vacante suele ir en la primera línea: no es el puesto.
    reales = [line for line in lines if not _es_url(line)]

    position = reales[0] if reales else path.stem

    return JobDescription(
        position=position,
        description=text,
        source=str(path),
    )
