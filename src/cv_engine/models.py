from typing import Literal

from pydantic import BaseModel, Field


class Profile(BaseModel):
    name: str
    title: str
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    github: str | None = None
    linkedin: str | None = None


class Experience(BaseModel):
    company: str
    role: str
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class Project(BaseModel):
    name: str
    type: str
    description: str
    technologies: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    url: str | None = None


class Skills(BaseModel):
    languages: list[str] = Field(default_factory=list)
    frontend: list[str] = Field(default_factory=list)
    backend: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    systems_networking: list[str] = Field(default_factory=list)
    devops: list[str] = Field(default_factory=list)
    python_stack: list[str] = Field(default_factory=list)
    ai: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    web_scraping: list[str] = Field(default_factory=list)
    design_3d: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    languages_spoken: list[str] = Field(default_factory=list)
    other: list[str] = Field(default_factory=list)


class Education(BaseModel):
    institution: str
    degree: str
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class JobDescription(BaseModel):
    company: str | None = None
    position: str
    description: str
    source: str | None = None


SourceType = Literal["experience", "project", "education", "profile"]

# Secciones del CV en el orden por defecto. La IA puede reordenarlas.
SECTIONS = ("perfil", "experiencia", "proyectos", "habilidades", "educacion")


class CVBullet(BaseModel):
    text: str
    source_type: SourceType
    source_index: int
    keywords: list[str] = Field(default_factory=list)


class CVContact(BaseModel):
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    github: str | None = None
    linkedin: str | None = None


class CVExperience(BaseModel):
    company: str
    role: str
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[CVBullet] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class CVProject(BaseModel):
    name: str
    type: str | None = None
    bullets: list[CVBullet] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None


class CVSkillGroup(BaseModel):
    category: str
    items: list[str] = Field(default_factory=list)


class CVEducation(BaseModel):
    institution: str
    degree: str
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class TargetedCV(BaseModel):
    name: str
    title: str
    target_position: str | None = None
    target_company: str | None = None
    summary: str | None = None
    section_order: list[str] = Field(default_factory=lambda: list(SECTIONS))
    contact: CVContact = Field(default_factory=CVContact)
    experiences: list[CVExperience] = Field(default_factory=list)
    projects: list[CVProject] = Field(default_factory=list)
    skill_groups: list[CVSkillGroup] = Field(default_factory=list)
    education: list[CVEducation] = Field(default_factory=list)


Severity = Literal["error", "warning"]


class ValidationIssue(BaseModel):
    severity: Severity
    code: str
    location: str
    message: str
    evidence: str | None = None


class ValidationReport(BaseModel):
    ok: bool = True
    issues: list[ValidationIssue] = Field(default_factory=list)

    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]
