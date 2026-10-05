import re

from cv_engine.models import TargetedCV, ValidationIssue, ValidationReport
from cv_engine.profile import MasterProfile

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?%?")


def normalize(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\s%+./-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


class CVValidator:
    """Validación determinista en una sola pasada, sin IA.

    Verifica: identidad copiada del maestro, referencias válidas,
    tecnologías y cifras presentes en el maestro.
    """

    def __init__(self, master: MasterProfile):
        self.master = master
        corpus = master.corpus_text()
        self.corpus_normalized = normalize(corpus)
        self.corpus_numbers = set(NUMBER_RE.findall(corpus))
        self.tech_universe = {
            normalize(t) for t in master.all_technologies() if t
        }

    def _issue(self, issues, code, location, message, severity="error",
               evidence=None):
        issues.append(
            ValidationIssue(
                severity=severity, code=code, location=location,
                message=message, evidence=evidence,
            )
        )

    def validate(self, cv: TargetedCV) -> ValidationReport:
        issues: list[ValidationIssue] = []
        profile = self.master.profile

        if cv.name != profile.name:
            self._issue(issues, "name_mismatch", "name",
                        "El nombre no coincide con el CV maestro.")
        for field in ("location", "email", "phone", "website",
                      "github", "linkedin"):
            if (getattr(cv.contact, field) or None) != (
                getattr(profile, field) or None
            ):
                self._issue(issues, "contact_mismatch", f"contact.{field}",
                            f"El campo '{field}' fue alterado.")

        for pos, exp in enumerate(cv.experiences):
            found = next(
                (s for s in self.master.experiences
                 if s.company == exp.company and s.role == exp.role),
                None,
            )
            if found is None:
                self._issue(issues, "unknown_experience",
                            f"experiencias[{pos}]",
                            "No corresponde a ningún registro del maestro.")
                continue
            for field in ("company", "role", "start_date", "end_date"):
                if (getattr(exp, field) or None) != (
                    getattr(found, field) or None
                ):
                    self._issue(issues, "experience_field",
                                f"experiencias[{pos}].{field}",
                                f"El campo '{field}' no coincide con el maestro.")

        names = {p.name for p in self.master.projects}
        for pos, proj in enumerate(cv.projects):
            if proj.name not in names:
                self._issue(issues, "unknown_project",
                            f"proyectos[{pos}]",
                            "No corresponde a ningún proyecto del maestro.")

        # Tecnologías: deben existir en el maestro.
        def check_tech(value: str, location: str):
            if normalize(value) not in self.tech_universe:
                self._issue(issues, "invented_technology", location,
                            f"La tecnología '{value}' no está en el maestro.")

        for pos, g in enumerate(cv.skill_groups):
            for item in g.items:
                check_tech(item, f"habilidades[{pos}].{g.category}")
        for pos, exp in enumerate(cv.experiences):
            for tech in exp.technologies:
                check_tech(tech, f"experiencias[{pos}].technologies")
        for pos, proj in enumerate(cv.projects):
            for tech in proj.technologies:
                check_tech(tech, f"proyectos[{pos}].technologies")

        # Cifras: deben existir en el maestro.
        def check_numbers(text: str, location: str):
            for number in NUMBER_RE.findall(text or ""):
                if (number not in self.corpus_numbers
                        and number.rstrip("%") not in self.corpus_numbers):
                    self._issue(issues, "invented_number", location,
                                f"La cifra '{number}' no está en el maestro.")

        if cv.summary:
            check_numbers(cv.summary, "summary")
        for pos, exp in enumerate(cv.experiences):
            for i, b in enumerate(exp.bullets):
                if not 0 <= b.source_index < len(self.master.experiences):
                    self._issue(issues, "invalid_source",
                                f"experiencias[{pos}].bullets[{i}]",
                                "Apunta a un registro inexistente.")
                check_numbers(b.text, f"experiencias[{pos}].bullets[{i}]")
        for pos, proj in enumerate(cv.projects):
            for i, b in enumerate(proj.bullets):
                if not 0 <= b.source_index < len(self.master.projects):
                    self._issue(issues, "invalid_source",
                                f"proyectos[{pos}].bullets[{i}]",
                                "Apunta a un registro inexistente.")
                check_numbers(b.text, f"proyectos[{pos}].bullets[{i}]")

        return ValidationReport(
            ok=not [i for i in issues if i.severity == "error"],
            issues=issues,
        )
