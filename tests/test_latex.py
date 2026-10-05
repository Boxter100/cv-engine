import shutil

import pytest

from cv_engine.generation.latex import (
    LatexError,
    compile_pdf,
    format_date,
    format_period,
    render_latex,
    tex_escape,
    write_latex,
)

HAS_LATEX = bool(shutil.which("pdflatex") or shutil.which("latexmk"))


def test_escapa_caracteres_especiales():
    assert tex_escape("100% & más") == r"100\% \& más"
    assert tex_escape("a_b") == r"a\_b"
    assert tex_escape("#1 $2") == r"\#1 \$2"
    assert tex_escape("C:\\path") == r"C:\textbackslash{}path"


def test_escape_no_toca_acentos_ni_guiones():
    assert tex_escape("Diseño ñandú -- guiones") == "Diseño ñandú -- guiones"


def test_escape_de_none():
    assert tex_escape(None) == ""


def test_formato_de_fechas():
    assert format_date("2024-01") == "ene 2024"
    assert format_date("2024") == "2024"
    assert format_date("2024-12-05") == "dic 2024"
    assert format_period(None) == "Presente"


def test_render_incluye_contenido(clean_cv):
    tex = render_latex(clean_cv)

    assert clean_cv.name in tex
    assert clean_cv.experiences[0].role in tex
    assert clean_cv.experiences[0].bullets[0].text in tex
    assert clean_cv.projects[0].name in tex
    assert r"\begin{document}" in tex


def test_render_respeta_el_orden_de_la_ia(clean_cv):
    clean_cv.section_order = ["educacion", "experiencia", "perfil"]

    tex = render_latex(clean_cv)

    assert tex.index("EDUCACIÓN") < tex.index("EXPERIENCIA") < tex.index("PERFIL")


def test_render_escapa_contenido(clean_cv):
    clean_cv.experiences[0].bullets[0].text = "Mejoré el SEO un 100% & más"

    tex = render_latex(clean_cv)

    assert r"100\% \& más" in tex


def test_render_omite_secciones_vacias(clean_cv):
    clean_cv.projects = []
    clean_cv.summary = None

    tex = render_latex(clean_cv)

    assert "PROYECTOS" not in tex
    assert "PERFIL" not in tex
    assert "EXPERIENCIA" in tex


def test_render_no_puede_inyectar_latex(master, clean_cv):
    clean_cv.experiences[0].bullets[0].text = (
        r"\end{itemize}\section{HACK} \input{/etc/passwd}"
    )

    tex = render_latex(clean_cv)

    assert r"\section{HACK}" not in tex
    assert r"\input{/etc/passwd}" not in tex
    assert r"\textbackslash{}end\{itemize\}" in tex


@pytest.mark.skipif(not HAS_LATEX, reason="pdflatex no disponible")
def test_compila_pdf_de_una_pagina(clean_cv, tmp_path):
    tex_path = write_latex(clean_cv, tmp_path / "cv.tex")

    result = compile_pdf(tex_path, tmp_path)

    assert result.pdf_path.exists()
    assert result.pages == 1


@pytest.mark.skipif(not HAS_LATEX, reason="pdflatex no disponible")
def test_limpia_archivos_auxiliares(clean_cv, tmp_path):
    tex_path = write_latex(clean_cv, tmp_path / "cv.tex")

    compile_pdf(tex_path, tmp_path)

    assert not (tmp_path / "cv.aux").exists()
    assert not (tmp_path / "cv.log").exists()
    assert (tmp_path / "cv.pdf").exists()


def test_error_de_latex_reporta_linea(tmp_path):
    roto = tmp_path / "roto.tex"
    roto.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\undefinedcommand\n"
        "\\end{document}\n",
        encoding="utf-8",
    )

    with pytest.raises(LatexError):
        compile_pdf(roto, tmp_path, engine="pdflatex", passes=1)
