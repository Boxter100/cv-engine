import json
import re

from cv_engine.ai.llama_server import LlamaServerClient
from cv_engine.models import (
    SECTIONS,
    CVBullet,
    CVContact,
    CVEducation,
    CVExperience,
    CVProject,
    CVSkillGroup,
    JobDescription,
    TargetedCV,
)
from cv_engine.profile import MasterProfile


class CVGenerationError(RuntimeError):
    pass


def extract_json(response: str) -> dict:
    text = response.strip()

    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise CVGenerationError(
            f"El modelo no devolvió un objeto JSON:\n{response}"
        )

    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as error:
        raise CVGenerationError(
            f"El modelo no devolvió JSON válido:\n{response}"
        ) from error


class CVGenerator:
    """Genera el CV con una sola llamada a la IA.

    La IA lee el CV maestro completo y la oferta, y decide
    estructura, orden, selección y redacción. El motor solo
    re-ancla los hechos al maestro en `_assemble`.
    """

    def __init__(self, client: LlamaServerClient | None = None):
        self.client = client or LlamaServerClient()

    def _build_prompt(self, master: MasterProfile, job: JobDescription) -> str:
        master_json = json.dumps(
            {
                "profile": master.profile.model_dump(),
                "experiences": [
                    e.model_dump() for e in master.experiences
                ],
                "projects": [p.model_dump() for p in master.projects],
                "skills": master.skills.model_dump(),
                "education": [e.model_dump() for e in master.education],
            },
            ensure_ascii=False,
            indent=2,
        )

        return f"""Eres un generador de CVs. Recibes el CV maestro (única fuente de verdad) y una oferta laboral.

=== CV MAESTRO ===
{master_json}

=== OFERTA ===
Puesto: {job.position}
Empresa: {job.company or 'no indicada'}
Descripción:
{job.description}

Reglas obligatorias:
- Cada bullet debe derivarse de un registro concreto del maestro e indicar su origen con `source_type` ("experience", "project", "education" o "profile") y `source_index`.
- No inventes empresas, cargos, fechas, tecnologías, cifras, porcentajes, resultados ni certificaciones. Nada que no esté en el CV maestro.
- Puedes traducir, condensar y reenfocar cada hecho hacia el lenguaje de la oferta. No puedes crear hechos nuevos.
- Si un requisito de la oferta no tiene respaldo en el maestro, no lo menciones. Mejor un CV corto y cierto que uno largo y falso.
- Escribe en español, frases cortas empezando con verbo.
- `summary`: 2-3 líneas posicionando al candidato para ESTA oferta.
- `section_order`: orden de secciones, solo con estos valores: {list(SECTIONS)}.
- `skill_groups`: elige qué grupos mostrar, solo con habilidades que existan en el maestro.

Devuelve únicamente JSON válido con esta estructura:
{{
  "summary": "string",
  "section_order": ["perfil", "experiencia"],
  "experiences": [{{"source_index": 0, "bullets": [{{"text": "string", "source_type": "experience", "source_index": 0, "keywords": []}}]}}],
  "projects": [{{"source_index": 0, "bullets": [{{"text": "string", "source_type": "project", "source_index": 0, "keywords": []}}]}}],
  "skill_groups": [{{"category": "string", "items": ["string"]}}]
}}

No incluyas empresas, roles ni fechas: se toman del CV maestro. No uses Markdown. No expliques tu respuesta.
"""

    def _assemble(
        self, master: MasterProfile, job: JobDescription, data: dict
    ) -> TargetedCV:
        experiences: list[CVExperience] = []
        for item in data.get("experiences") or []:
            try:
                index = int(item.get("source_index", -1))
            except (TypeError, ValueError):
                continue
            if not 0 <= index < len(master.experiences):
                continue
            source = master.experiences[index]
            bullets = [
                CVBullet(
                    text=str(b.get("text", "")).strip(),
                    source_type="experience",
                    source_index=index,
                    keywords=[str(w) for w in b.get("keywords") or []],
                )
                for b in item.get("bullets") or []
                if str(b.get("text", "")).strip()
            ]
            if not bullets:
                continue
            experiences.append(
                CVExperience(
                    company=source.company,
                    role=source.role,
                    location=source.location,
                    start_date=source.start_date,
                    end_date=source.end_date,
                    bullets=bullets,
                    technologies=list(source.technologies),
                )
            )

        projects: list[CVProject] = []
        for item in data.get("projects") or []:
            try:
                index = int(item.get("source_index", -1))
            except (TypeError, ValueError):
                continue
            if not 0 <= index < len(master.projects):
                continue
            source = master.projects[index]
            bullets = [
                CVBullet(
                    text=str(b.get("text", "")).strip(),
                    source_type="project",
                    source_index=index,
                    keywords=[str(w) for w in b.get("keywords") or []],
                )
                for b in item.get("bullets") or []
                if str(b.get("text", "")).strip()
            ]
            if not bullets:
                continue
            projects.append(
                CVProject(
                    name=source.name,
                    type=source.type,
                    bullets=bullets,
                    technologies=list(source.technologies),
                    url=source.url,
                )
            )

        # Habilidades: solo lo que existe en el maestro, sin filtrado por match.
        universe = {
            item
            for group in master.skills.model_dump().values()
            for item in group
        }
        skill_groups: list[CVSkillGroup] = []
        groups = data.get("skill_groups")
        if isinstance(groups, list):
            for group in groups:
                if not isinstance(group, dict):
                    continue
                category = str(group.get("category") or "").strip()
                items = [
                    str(i).strip()
                    for i in group.get("items") or []
                    if str(i).strip() in universe
                ]
                if category and items:
                    skill_groups.append(
                        CVSkillGroup(category=category, items=items)
                    )
        if not skill_groups:
            for field, items in master.skills.model_dump().items():
                if items:
                    skill_groups.append(
                        CVSkillGroup(category=field, items=list(items))
                    )

        sections = data.get("section_order")
        order: list[str] = []
        if isinstance(sections, list):
            for name in sections:
                name = str(name or "").strip().lower()
                if name in SECTIONS and name not in order:
                    order.append(name)
        order += [n for n in SECTIONS if n not in order]

        # Defensa: el puesto nunca puede ser una URL (el link va al CSV,
        # jamás al PDF). Si el parser no pudo evitarlo, se omite.
        target_position = job.position
        if target_position.strip().lower().startswith(("http://", "https://")):
            target_position = None

        return TargetedCV(
            name=master.profile.name,
            title=master.profile.title,
            target_position=target_position,
            target_company=job.company,
            summary=str(data.get("summary") or "").strip() or None,
            section_order=order,
            contact=CVContact(
                location=master.profile.location,
                email=master.profile.email,
                phone=master.profile.phone,
                website=master.profile.website,
                github=master.profile.github,
                linkedin=master.profile.linkedin,
            ),
            experiences=experiences,
            projects=projects,
            skill_groups=skill_groups,
            education=[
                CVEducation(
                    institution=e.institution,
                    degree=e.degree,
                    start_date=e.start_date,
                    end_date=e.end_date,
                    description=e.description,
                )
                for e in master.education
            ],
        )

    def generate(
        self, master: MasterProfile, job: JobDescription
    ) -> TargetedCV:
        prompt = self._build_prompt(master, job)
        response = self.client.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un generador de CVs. Escribes en español. "
                        "Copias únicamente información presente en los registros "
                        "que te proporcionan. Devuelves únicamente JSON válido."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=4096,
        )
        return self._assemble(master, job, extract_json(response))
