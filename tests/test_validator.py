from cv_engine.models import CVSkillGroup
from cv_engine.validation.validator import CVValidator


def codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_cv_fiel_al_maestro_pasa(master, clean_cv):
    report = CVValidator(master).validate(clean_cv)
    assert report.ok is True
    assert report.issues == []


def test_detecta_cifra_inventada(master, clean_cv):
    clean_cv.experiences[0].bullets[0].text = "Aumenté el rendimiento un 40%."
    report = CVValidator(master).validate(clean_cv)
    assert report.ok is False
    assert "invented_number" in codes(report)


def test_detecta_tecnologia_inventada(master, clean_cv):
    clean_cv.skill_groups.append(
        CVSkillGroup(category="Otros", items=["Kubernetes"])
    )
    report = CVValidator(master).validate(clean_cv)
    assert report.ok is False
    assert "invented_technology" in codes(report)


def test_detecta_empresa_inventada(master, clean_cv):
    clean_cv.experiences[0].company = "Google"
    report = CVValidator(master).validate(clean_cv)
    assert report.ok is False
    assert "unknown_experience" in codes(report)


def test_detecta_fecha_alterada(master, clean_cv):
    clean_cv.experiences[0].start_date = "2015-01"
    report = CVValidator(master).validate(clean_cv)
    assert "experience_field" in codes(report)


def test_detecta_contacto_alterado(master, clean_cv):
    clean_cv.contact.email = "otro@example.com"
    report = CVValidator(master).validate(clean_cv)
    assert report.ok is False
    assert "contact_mismatch" in codes(report)


def test_detecta_nombre_alterado(master, clean_cv):
    clean_cv.name = "Nombre Inventado"
    report = CVValidator(master).validate(clean_cv)
    assert "name_mismatch" in codes(report)


def test_detecta_fuente_inexistente(master, clean_cv):
    clean_cv.experiences[0].bullets[0].source_index = 99
    report = CVValidator(master).validate(clean_cv)
    assert report.ok is False
    assert "invalid_source" in codes(report)


def test_detecta_proyecto_inventado(master, clean_cv):
    clean_cv.projects[0].name = "Proyecto Inventado"
    report = CVValidator(master).validate(clean_cv)
    assert "unknown_project" in codes(report)
