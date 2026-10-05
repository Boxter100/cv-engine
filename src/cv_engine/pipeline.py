from dataclasses import dataclass
from pathlib import Path

from cv_engine.ai.llama_server import LlamaServerClient
from cv_engine.analysis.parser import parse_job_file
from cv_engine.generation.generator import CVGenerator
from cv_engine.models import JobDescription, TargetedCV, ValidationReport
from cv_engine.profile import MasterProfile
from cv_engine.validation.validator import CVValidator


class CVValidationFailure(RuntimeError):
    def __init__(self, cv: TargetedCV, report: ValidationReport):
        self.cv = cv
        self.report = report
        details = "\n".join(
            f"- [{i.severity}] {i.location}: {i.message}"
            for i in report.issues
        )
        super().__init__(
            "El CV generado no pasó la validación. "
            f"No se generó el PDF.\n{details}"
        )


@dataclass
class PipelineResult:
    cv: TargetedCV
    job: JobDescription
    report: ValidationReport


def run_pipeline(
    job_path: Path | str,
    master: MasterProfile | None = None,
    client: LlamaServerClient | None = None,
) -> PipelineResult:
    """Pipeline simple: oferta + maestro → IA → validación → CV."""
    master = master or MasterProfile.load()
    client = client or LlamaServerClient()

    job = parse_job_file(job_path)
    cv = CVGenerator(client).generate(master, job)
    report = CVValidator(master).validate(cv)

    if not report.ok:
        raise CVValidationFailure(cv, report)

    return PipelineResult(cv=cv, job=job, report=report)
