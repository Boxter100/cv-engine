import json
from pathlib import Path

import pytest

from cv_engine.models import (
    CVBullet,
    CVContact,
    CVEducation,
    CVExperience,
    CVProject,
    CVSkillGroup,
    TargetedCV,
)
from cv_engine.profile import MasterProfile

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "data" / "profile"


@pytest.fixture
def master() -> MasterProfile:
    return MasterProfile.load(PROFILE_DIR)


@pytest.fixture
def clean_cv(master: MasterProfile) -> TargetedCV:
    """CV completamente fiel al CV maestro.

    Se construye desde `data/profile/`, no con datos inventados: si el perfil
    real cambia, el fixture sigue siendo fiel y los tests siguen significando
    algo.
    """
    profile = master.profile
    experience = master.experiences[0]
    project = master.projects[0]
    education = master.education[0]

    return TargetedCV(
        name=profile.name,
        title=profile.title,
        target_position="Frontend Developer",
        target_company="Example Company",
        summary="Desarrollo de aplicaciones web.",
        section_order=["perfil", "experiencia", "proyectos", "habilidades", "educacion"],
        contact=CVContact(
            location=profile.location,
            email=profile.email,
            phone=profile.phone,
            website=profile.website,
            github=profile.github,
            linkedin=profile.linkedin,
        ),
        experiences=[
            CVExperience(
                company=experience.company,
                role=experience.role,
                location=experience.location,
                start_date=experience.start_date,
                end_date=experience.end_date,
                bullets=[
                    CVBullet(
                        text=experience.achievements[0],
                        source_type="experience",
                        source_index=0,
                        keywords=["React"],
                    ),
                    CVBullet(
                        text=experience.achievements[1],
                        source_type="experience",
                        source_index=0,
                        keywords=["REST APIs"],
                    ),
                ],
                technologies=["TypeScript", "React"],
            )
        ],
        projects=[
            CVProject(
                name=project.name,
                type=project.type,
                bullets=[
                    CVBullet(
                        text=project.highlights[0],
                        source_type="project",
                        source_index=0,
                        keywords=["Astro"],
                    )
                ],
                technologies=project.technologies,
                url=project.url,
            )
        ],
        skill_groups=[
            CVSkillGroup(category="Lenguajes", items=["Python", "TypeScript"]),
            CVSkillGroup(category="Frontend", items=["React", "Astro"]),
        ],
        education=[
            CVEducation(
                institution=education.institution,
                degree=education.degree,
                start_date=education.start_date,
                end_date=education.end_date,
                description=education.description,
            )
        ],
    )


class FakeClient:
    """Cliente de llama-server falso para probar sin GPU."""

    def __init__(self, response: str | dict | Exception):
        self.response = response
        self.calls: list[dict] = []

    def chat(self, **kwargs) -> str:
        self.calls.append(kwargs)

        if isinstance(self.response, Exception):
            raise self.response

        if isinstance(self.response, str):
            return self.response

        return json.dumps(self.response)


def make_client(response: str | dict | Exception) -> FakeClient:
    return FakeClient(response)


@pytest.fixture
def fake_client():
    return make_client
