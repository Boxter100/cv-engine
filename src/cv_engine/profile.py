import json
from pathlib import Path

from pydantic import ValidationError

from cv_engine.models import (
    Education,
    Experience,
    Profile,
    Project,
    Skills,
)

PROFILE_DIR = Path("data/profile")

FILES = {
    "profile": "profile.json",
    "experience": "experience.json",
    "projects": "projects.json",
    "skills": "skills.json",
    "education": "education.json",
}


def load_json(filename: str):
    path = PROFILE_DIR / filename

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


class MasterProfile:
    def __init__(
        self,
        profile: Profile,
        experiences: list[Experience],
        projects: list[Project],
        skills: Skills,
        education: list[Education],
    ):
        self.profile = profile
        self.experiences = experiences
        self.projects = projects
        self.skills = skills
        self.education = education

    @classmethod
    def load(cls, directory: Path | str | None = None) -> "MasterProfile":
        root = Path(directory) if directory else PROFILE_DIR

        def read(key: str):
            path = root / FILES[key]

            with path.open("r", encoding="utf-8") as file:
                return json.load(file)

        return cls(
            profile=Profile.model_validate(read("profile")),
            experiences=[
                Experience.model_validate(item) for item in read("experience")
            ],
            projects=[Project.model_validate(item) for item in read("projects")],
            skills=Skills.model_validate(read("skills")),
            education=[Education.model_validate(item) for item in read("education")],
        )

    def all_technologies(self) -> list[str]:
        result: list[str] = [
            item
            for group in self.skills.model_dump().values()
            for item in group
        ]

        for experience in self.experiences:
            result.extend(experience.technologies)

        for project in self.projects:
            result.extend(project.technologies)

        return [item for item in result if item]

    def corpus_text(self) -> str:
        parts: list[str] = [
            self.profile.name,
            self.profile.title,
            self.profile.location or "",
            self.skills.model_dump_json(),
        ]

        for experience in self.experiences:
            parts.extend(
                [
                    experience.company,
                    experience.role,
                    experience.location or "",
                    experience.start_date or "",
                    experience.end_date or "",
                    experience.description,
                    *experience.achievements,
                    *experience.technologies,
                ]
            )

        for project in self.projects:
            parts.extend(
                [
                    project.name,
                    project.type,
                    project.description,
                    *project.highlights,
                    *project.technologies,
                    project.url or "",
                ]
            )

        for item in self.education:
            parts.extend(
                [
                    item.institution,
                    item.degree,
                    item.start_date or "",
                    item.end_date or "",
                    item.description or "",
                ]
            )

        return "\n".join(part for part in parts if part)


def validate_master_profile(
    directory: Path | str | None = None,
) -> list[str]:
    root = Path(directory) if directory else PROFILE_DIR

    try:
        MasterProfile.load(root)
    except FileNotFoundError as error:
        return [f"Falta el archivo {error.filename}."]
    except json.JSONDecodeError as error:
        return [f"JSON inválido: {error}"]
    except ValidationError as error:
        messages = [
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        ]

        return messages

    return []
