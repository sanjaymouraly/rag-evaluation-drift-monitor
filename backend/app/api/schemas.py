"""Request/response schemas (Pydantic v2)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class AppIn(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=200)
    version_label: str = "v1"
    environment: str = "dev"
    description: str = ""
    config: dict = Field(default_factory=dict)


class DocumentIn(BaseModel):
    project_id: int
    doc_id: str = Field(min_length=1, max_length=200)
    title: str = ""
    text: str
    source: str = "api"
    metadata: dict = Field(default_factory=dict)

    @field_validator("doc_id")
    @classmethod
    def _safe_doc_id(cls, value: str) -> str:
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError("doc_id must not contain path separators")
        return value


class DatasetIn(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=200)
    version: str = "1.0"
    description: str = ""


class ItemIn(BaseModel):
    question: str = Field(min_length=1)
    reference_answer: str = ""
    aliases: list[str] = Field(default_factory=list)
    relevant_doc_ids: list[str] = Field(default_factory=list)
    relevance_grades: dict[str, float] = Field(default_factory=dict)
    expected_citations: list[dict] = Field(default_factory=list)
    category: str = "factual"
    difficulty: str = "medium"
    answerable: bool = True
    language: str = "en"
    topic: str = ""
    cohorts: list[str] = Field(default_factory=list)
    notes: str = ""


class RunIn(BaseModel):
    app_id: int
    dataset_id: int
    mode: str = "end_to_end"
    wait: bool = False
    idempotency_key: str | None = None
    judge_provider_id: int | None = None
    judge_budget_usd: float = 1.0
    judge_dimensions: list[str] = Field(default_factory=list)


class PolicyIn(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    baseline_run_id: int | None = None
    rules: list[dict] = Field(default_factory=list)
    min_samples: int = 5


class ProviderIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str = "offline"
    role: str = "judge"
    base_url: str = ""
    api_key: str | None = None
    model: str = ""
    timeout_s: float = 30.0
    retries: int = 2
    price_per_1k_input: float = 0.0
    price_per_1k_output: float = 0.0
    is_default: bool = False
    enabled: bool = True
    max_concurrency: int = 4


class GateEvalIn(BaseModel):
    candidate_run_id: int
    baseline_run_id: int | None = None


class JudgeIn(BaseModel):
    provider_id: int
    run_id: int
    budget_usd: float = 1.0
    dimensions: list[str] = Field(default_factory=list)


class ReviewIn(BaseModel):
    verdict: str

    @field_validator("verdict")
    @classmethod
    def _valid(cls, value: str) -> str:
        if value not in ("agree", "disagree"):
            raise ValueError("verdict must be 'agree' or 'disagree'")
        return value


class SyntheticIn(BaseModel):
    max_items: int = Field(default=10, ge=1, le=500)


class ScheduledJobIn(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=200)
    app_id: int
    dataset_id: int
    policy_id: int | None = None
    interval_minutes: int = Field(default=60, ge=1, le=10080)
    mode: str = "end_to_end"
    enabled: bool = True


class TraceIn(BaseModel):
    project_id: int
    question: str = Field(min_length=1)
    answer: str = ""
    retrieved_doc_ids: list[str] = Field(default_factory=list)
    category: str = "production"
    latency_ms: float = 0.0
    source: str = "import"
