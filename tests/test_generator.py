import pytest

from cv_engine.generation.generator import (
    CVGenerationError,
    CVGenerator,
    extract_json,
)
from cv_engine.models import JobDescription, SECTIONS


def job(position="Frontend Developer", description="React, TypeScript"):
    return JobDescription(position=position, description=description)


GENERATED = {
    "summary": "Desarrollo de aplicaciones web.",
    "experiences": [
        {
            "source_index": 0,
            "bullets": [
                {
                    "text": "Construcción de componentes web reutilizables.",
                    "source_type": "experience",
                    "source_index": 0,
                    "keywords": ["React"],
                }
            ],
        }
    ],
    "projects": [
        {
            "source_index": 0,
            "bullets": [
                {
                    "text": "Implementación de componentes reutilizables.",
                    "source_type": "project",
                    "source_index": 0,
                    "keywords": [],
                }
            ],
        }
    ],
}


def test_extract_json_plano():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_con_markdown():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_sin_json_falla():
    with pytest.raises(CVGenerationError):
        extract_json("no devuelvo nada")


def test_genera_cv_con_trazabilidad(master, fake_client):
    cv = CVGenerator(fake_client(GENERATED)).generate(master, job())

    assert cv.name == master.profile.name
    assert cv.contact.email == master.profile.email
    bullet = cv.experiences[0].bullets[0]
    assert bullet.source_type == "experience"
    assert bullet.source_index == 0
    assert bullet.keywords == ["React"]
    assert cv.projects[0].bullets[0].source_type == "project"


def test_empresa_rol_y_fechas_vienen_del_maestro(master, fake_client):
    cv = CVGenerator(fake_client(GENERATED)).generate(master, job())

    exp = cv.experiences[0]
    assert exp.company == master.experiences[0].company
    assert exp.role == master.experiences[0].role
    assert exp.start_date == master.experiences[0].start_date


def test_ignora_source_index_fuera_de_rango(master, fake_client):
    cliente = fake_client(
        {"summary": "s", "experiences": [{"source_index": 42, "bullets": [
            {"text": "x", "source_type": "experience",
             "source_index": 42}]}],
         "projects": []}
    )
    cv = CVGenerator(cliente).generate(master, job())
    assert cv.experiences == [] and cv.projects == []


def test_temperatura_cero(master, fake_client):
    cliente = fake_client({"summary": "s", "experiences": [], "projects": []})
    CVGenerator(cliente).generate(master, job())
    assert cliente.calls[0]["temperature"] == 0.0


def test_habilidades_solo_del_maestro(master, fake_client):
    cliente = fake_client(
        {"summary": "s", "experiences": GENERATED["experiences"],
         "projects": [],
         "skill_groups": [
             {"category": "Python", "items": ["Pydantic", "Kubernetes"]},
             {"category": "Inventada", "items": ["Docker"]},
         ]}
    )
    cv = CVGenerator(cliente).generate(master, job())
    grupos = {g.category: g.items for g in cv.skill_groups}
    assert grupos.get("Python") == ["Pydantic"]
    assert "Inventada" not in grupos


def test_la_ia_elige_secciones_y_orden(master, fake_client):
    cliente = fake_client(
        {"summary": "s",
         "section_order": ["habilidades", "perfil", "educacion"],
         "experiences": GENERATED["experiences"],
         "projects": GENERATED["projects"]}
    )
    cv = CVGenerator(cliente).generate(master, job())
    assert cv.section_order[:3] == ["habilidades", "perfil", "educacion"]
    assert set(cv.section_order) == set(SECTIONS)


def test_prompt_incluye_maestro_y_oferta(master, fake_client):
    cliente = fake_client({"summary": "s", "experiences": [], "projects": []})
    CVGenerator(cliente).generate(master, job("Dev", "oferta especial"))
    prompt = cliente.calls[0]["messages"][1]["content"]
    assert "CV MAESTRO" in prompt
    assert "oferta especial" in prompt
    assert master.experiences[0].company in prompt
