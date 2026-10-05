import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from cv_engine.models import TargetedCV

TEMPLATE_DIR = Path(__file__).parent / "templates"
DEFAULT_TEMPLATE = "cv.tex.j2"

LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "<": r"\textless{}",
    ">": r"\textgreater{}",
    "|": r"\textbar{}",
}

MONTHS = {
    "01": "ene",
    "02": "feb",
    "03": "mar",
    "04": "abr",
    "05": "may",
    "06": "jun",
    "07": "jul",
    "08": "ago",
    "09": "sep",
    "10": "oct",
    "11": "nov",
    "12": "dic",
}

PAGES_RE = re.compile(r"Output written on .*?\(\d+ pages?")


class LatexError(RuntimeError):
    pass


@dataclass
class CompileResult:
    pdf_path: Path
    pages: int | None
    engine: str
    log: str


def tex_escape(value) -> str:
    if value is None:
        return ""

    text = str(value)

    return "".join(LATEX_ESCAPES.get(char, char) for char in text)


def format_date(value: str | None) -> str:
    if not value:
        return ""

    text = str(value).strip()

    if re.fullmatch(r"\d{4}-\d{2}", text):
        year, month = text.split("-")

        return f"{MONTHS.get(month, month)} {year}"

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        year, month, _day = text.split("-")

        return f"{MONTHS.get(month, month)} {year}"

    return text


def format_period(value: str | None) -> str:
    return format_date(value) if value else "Presente"


def build_environment(template_dir: Path | str | None = None) -> Environment:
    root = Path(template_dir) if template_dir else TEMPLATE_DIR

    environment = Environment(
        loader=FileSystemLoader(str(root)),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        # LaTeX usa {#1} y {#2} en las definiciones de macros, que Jinja
        # interpretaria como el inicio de un comentario. Se cambia el delimitador
        # de comentarios por algo que no aparece en una plantilla LaTeX.
        comment_start_string="<%--",
        comment_end_string="--%>",
    )

    environment.filters["tex"] = tex_escape
    environment.filters["date"] = format_date
    environment.filters["period"] = format_period

    return environment


def render_latex(
    cv: TargetedCV,
    template_dir: Path | str | None = None,
    template: str = DEFAULT_TEMPLATE,
) -> str:
    environment = build_environment(template_dir)

    return environment.get_template(template).render(cv=cv)


def _log_errors(log: str) -> list[str]:
    errors: list[str] = []

    for line in log.splitlines():
        if line.startswith("!") or re.match(r"^.+?:\d+: ", line):
            message = line.strip()

            if message and message not in errors:
                errors.append(message)

    return errors


def _compile_with_latexmk(
    tex_path: Path,
    output_dir: Path,
    passes: int,
) -> tuple[int, str] | None:
    if not shutil.which("latexmk"):
        return None

    command = [
        "latexmk",
        "-pdf",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "-no-shell-escape",
        "-silent",
        f"-outdir={output_dir.resolve()}",
        f"passes={passes}",
        tex_path.name,
    ]

    process = subprocess.run(
        command,
        cwd=tex_path.parent,
        capture_output=True,
        text=True,
    )

    return process.returncode, (process.stdout or "") + (process.stderr or "")


def _compile_with_engine(
    tex_path: Path,
    output_dir: Path,
    engine: str,
    runs: int,
) -> tuple[int, str]:
    command = [
        engine,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "-no-shell-escape",
        f"-output-directory={output_dir.resolve()}",
        tex_path.name,
    ]

    output: list[str] = []

    for _ in range(runs):
        process = subprocess.run(
            command,
            cwd=tex_path.parent,
            capture_output=True,
            text=True,
        )
        output.append(process.stdout or "")
        output.append(process.stderr or "")

        if process.returncode != 0:
            break

    return process.returncode, "\n".join(output)


AUX_EXTENSIONS = (
    ".aux",
    ".log",
    ".out",
    ".fls",
    ".fdb_latexmk",
    ".toc",
    ".synctex.gz",
    ".nav",
    ".snm",
    ".vrb",
)


def _pages_from_log(log: str) -> int | None:
    match = PAGES_RE.search(log)

    if not match:
        return None

    found = re.search(r"(\d+)", match.group(0))

    return int(found.group(1)) if found else None


def _pages_from_pdfinfo(pdf_path: Path) -> int | None:
    if not shutil.which("pdfinfo"):
        return None

    process = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True,
        text=True,
    )

    if process.returncode != 0:
        return None

    match = re.search(r"^Pages:\s+(\d+)", process.stdout, re.MULTILINE)

    return int(match.group(1)) if match else None


def _cleanup_aux(output_dir: Path, stem: str) -> None:
    for extension in AUX_EXTENSIONS:
        aux = output_dir / f"{stem}{extension}"

        if aux.exists():
            aux.unlink()


def compile_pdf(
    tex_path: Path | str,
    output_dir: Path | str,
    engine: str = "pdflatex",
    passes: int = 2,
) -> CompileResult:
    tex_path = Path(tex_path)
    output_dir = Path(output_dir)

    if not tex_path.exists():
        raise LatexError(f"No existe el archivo .tex: {tex_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    result = _compile_with_latexmk(tex_path, output_dir, passes)
    used_engine = "latexmk"

    if result is None or result[0] != 0:
        returncode, log = _compile_with_engine(
            tex_path, output_dir, engine, passes
        )
        used_engine = engine
    else:
        returncode, log = result

    log_path = output_dir / f"{tex_path.stem}.log"
    if log_path.exists():
        log = log_path.read_text(encoding="utf-8", errors="replace")

    pdf_path = output_dir / f"{tex_path.stem}.pdf"

    if returncode != 0 or not pdf_path.exists():
        errors = _log_errors(log)[:20]

        detail = "\n".join(errors) if errors else log[-2000:]

        raise LatexError(
            f"LaTeX no pudo compilar {tex_path.name} "
            f"(exit {returncode}, motor {used_engine}):\n{detail}"
        )

    pages = _pages_from_log(log) or _pages_from_pdfinfo(pdf_path)

    _cleanup_aux(output_dir, tex_path.stem)

    return CompileResult(
        pdf_path=pdf_path,
        pages=pages,
        engine=used_engine,
        log=log,
    )


def write_latex(
    cv: TargetedCV,
    output_path: Path | str,
    template_dir: Path | str | None = None,
) -> Path:
    output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_latex(cv, template_dir), encoding="utf-8")

    return output_path


def build_pdf(
    cv: TargetedCV,
    output_dir: Path | str,
    stem: str = "cv",
    template_dir: Path | str | None = None,
    engine: str = "pdflatex",
) -> tuple[Path, CompileResult]:
    output_dir = Path(output_dir)

    tex_path = write_latex(
        cv,
        output_dir / f"{stem}.tex",
        template_dir,
    )

    return tex_path, compile_pdf(tex_path, output_dir, engine=engine)
