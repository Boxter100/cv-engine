import json

import pytest

from cv_engine.pipeline import CVValidationFailure, run_pipeline


BUENOS = {
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
    "projects": [],
}

MALO = {
    **BUENOS,
    "experiences": [
        {
            "source_index": 0,
            "bullets": [
                {
                    "text": "Aumenté los ingresos un 40%.",
                    "source_type": "experience",
                    "source_index": 0,
                    "keywords": [],
                }
            ],
        }
    ],
}


class SimpleClient:
    def __init__(self, payload: dict):
        self.payload = payload

    def chat(self, **kwargs) -> str:
        return json.dumps(self.payload)


def test_pipeline_pasa(master, tmp_path):
    oferta = tmp_path / "job.txt"
    oferta.write_text("Frontend Developer\nReact, TypeScript", encoding="utf-8")

    resultado = run_pipeline(oferta, master=master, client=SimpleClient(BUENOS))

    assert resultado.report.ok is True
    assert resultado.job.position == "Frontend Developer"
    assert resultado.cv.name == master.profile.name


def test_pipeline_falla_si_inventa(master, tmp_path):
    oferta = tmp_path / "job.txt"
    oferta.write_text("Frontend Developer\nReact", encoding="utf-8")

    with pytest.raises(CVValidationFailure) as error:
        run_pipeline(oferta, master=master, client=SimpleClient(MALO))

    assert "invented_number" in {i.code for i in error.value.report.issues}


def test_oferta_inexistente_falla(master, tmp_path):
    with pytest.raises(FileNotFoundError):
        run_pipeline(tmp_path / "no-existe.txt", master=master)
