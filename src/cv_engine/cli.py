from pathlib import Path

import typer

from cv_engine.analysis.parser import parse_job_file
from cv_engine.ai.llama_server import LlamaServerClient
from cv_engine.generation.latex import (
    LatexError,
    build_pdf,
    compile_pdf,
    write_latex,
)
from cv_engine.models import TargetedCV
from cv_engine.pipeline import CVValidationFailure, run_pipeline
from cv_engine.profile import MasterProfile, validate_master_profile
from cv_engine.tracking import registrar_vacante
from cv_engine.validation.validator import CVValidator

app = typer.Typer(
    name="cv-engine",
    help="Motor local para generar CVs a medida de cada oferta.",
)

DEFAULT_OUT = Path("output")


@app.command()
def version():
    """Show the current version."""
    typer.echo("CV Engine v0.1.0")


@app.command()
def hello():
    """Check that CV Engine is working."""
    typer.echo("CV Engine is working.")


@app.command()
def validate():
    """Validate the CV master profile (los 5 JSON de data/profile)."""
    errors = validate_master_profile()

    if errors:
        typer.echo("El CV maestro tiene errores:")
        for error in errors:
            typer.echo(f"- {error}")
        raise typer.Exit(code=1)

    master = MasterProfile.load()
    typer.echo("El CV maestro es válido.")
    typer.echo(
        f"  {len(master.experiences)} experiencia(s), "
        f"{len(master.projects)} proyecto(s), "
        f"{len(master.education)} formación(es)."
    )


@app.command()
def analyze(job_file: str):
    """Muestra la oferta tal como la leerá la IA."""
    job = parse_job_file(job_file)
    typer.echo(f"Puesto: {job.position}")
    typer.echo(f"Origen: {job.source}")
    typer.echo("")
    typer.echo(job.description[:2000])


@app.command()
def generate(
    job_file: str = typer.Argument(..., help="Archivo con la oferta."),
    out: Path = typer.Option(
        None, "--out", "-o",
        help="Carpeta de salida. Por defecto output/<nombre-de-la-oferta>.",
    ),
    engine: str = typer.Option(
        "pdflatex", "--engine", help="Motor LaTeX: pdflatex, xelatex o lualatex."
    ),
):
    """Genera el CV: la IA lee el maestro + la oferta, luego compila a PDF."""
    job_path = Path(job_file)

    if not job_path.exists():
        typer.echo(f"No existe la oferta: {job_path}")
        raise typer.Exit(code=1)

    output_dir = out or DEFAULT_OUT / job_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(f"[1/3] Leyendo {job_path} y CV maestro...")
    typer.echo("[2/3] Generando CV con IA y validando...")

    try:
        result = run_pipeline(job_path, master=MasterProfile.load())
    except CVValidationFailure as failure:
        (output_dir / "cv.json").write_text(
            failure.cv.model_dump_json(indent=2), encoding="utf-8"
        )
        (output_dir / "validation.json").write_text(
            failure.report.model_dump_json(indent=2), encoding="utf-8"
        )
        registrar_vacante(
            DEFAULT_OUT / "vacantes.csv",
            puesto=failure.cv.target_position or job_path.stem,
            empresa=failure.cv.target_company,
            oferta_txt=job_path,
            descripcion_oferta=job_path.read_text(encoding="utf-8"),
            estado="fallo_validacion",
            validacion="; ".join(
                sorted({i.code for i in failure.report.errors()})
            ),
        )
        typer.echo("")
        typer.echo("[3/3] Validación fallida:")
        for issue in failure.report.issues:
            typer.echo(f"- [{issue.severity}] {issue.location}: {issue.message}")
        typer.echo(f"Se guardó el intento en {output_dir}. No se generó el PDF.")
        raise typer.Exit(code=1)

    (output_dir / "cv.json").write_text(
        result.cv.model_dump_json(indent=2), encoding="utf-8"
    )
    (output_dir / "validation.json").write_text(
        result.report.model_dump_json(indent=2), encoding="utf-8"
    )
    typer.echo("[3/3] Validación OK. Compilando LaTeX...")

    try:
        tex_path, compiled = build_pdf(
            result.cv, output_dir, stem="cv", engine=engine
        )
    except LatexError as error:
        typer.echo(str(error))
        raise typer.Exit(code=1)

    registrar_vacante(
        DEFAULT_OUT / "vacantes.csv",
        puesto=result.cv.target_position or result.job.position,
        empresa=result.cv.target_company,
        oferta_txt=job_path,
        descripcion_oferta=result.job.description,
        cv_pdf=compiled.pdf_path,
    )

    typer.echo(f"PDF: {compiled.pdf_path}")
    typer.echo(f"TEX: {tex_path}")


@app.command()
def render(
    cv_file: Path = typer.Argument(..., help="CV JSON generado previously."),
    out: Path = typer.Option(
        None, "--out", "-o", help="Carpeta de salida. Por defecto la del JSON."
    ),
    engine: str = typer.Option(
        "pdflatex", "--engine", help="Motor LaTeX: pdflatex, xelatex o lualatex."
    ),
    stem: str = typer.Option("cv", "--stem", help="Nombre de los archivos .tex/.pdf."),
):
    """Convierte un cv.json en LaTeX y PDF. No usa IA."""
    if not cv_file.exists():
        typer.echo(f"No existe el archivo: {cv_file}")
        raise typer.Exit(code=1)

    cv = TargetedCV.model_validate_json(cv_file.read_text(encoding="utf-8"))
    output_dir = out or cv_file.parent
    tex_path = write_latex(cv, output_dir / f"{stem}.tex")

    try:
        compiled = compile_pdf(tex_path, output_dir, engine=engine)
    except LatexError as error:
        typer.echo(str(error))
        raise typer.Exit(code=1)

    typer.echo(f"PDF: {compiled.pdf_path}")
    typer.echo(f"TEX: {tex_path}")


@app.command("validate-cv")
def validate_cv(cv_file: Path = typer.Argument(..., help="CV JSON a verificar.")):
    """Valida un cv.json contra el CV maestro."""
    if not cv_file.exists():
        typer.echo(f"No existe el archivo: {cv_file}")
        raise typer.Exit(code=1)

    cv = TargetedCV.model_validate_json(cv_file.read_text(encoding="utf-8"))
    report = CVValidator(MasterProfile.load()).validate(cv)
    (cv_file.parent / "validation.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    for issue in report.issues:
        typer.echo(f"[{issue.severity}] {issue.location}: {issue.message}")
    if report.ok:
        typer.echo("CV válido.")
        return
    typer.echo(f"CV inválido: {len(report.errors())} error(es).")
    raise typer.Exit(code=1)


@app.command()
def ask(prompt: str):
    """Send a prompt to the local llama-server."""
    client = LlamaServerClient()
    response = client.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=512,
    )
    typer.echo(response)


if __name__ == "__main__":
    app()
