"""Initial schema for RAG Quality Monitor.

The migration is written out explicitly (rather than calling ``create_all``)
so that the schema history is reviewable, reversible and portable between
SQLite and PostgreSQL.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

JSON = sa.JSON
BOOLEAN = sa.Boolean()
FLOAT = sa.Float()
INTEGER = sa.Integer()
STRING = sa.String
TEXT = sa.Text
DATE_TIME = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("name", STRING(200), nullable=False),
        sa.Column("description", TEXT, nullable=False, server_default=""),
        sa.Column("is_demo", BOOLEAN, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", DATE_TIME, nullable=True),
    )
    op.create_table(
        "rag_apps",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("project_id", INTEGER, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", STRING(200), nullable=False),
        sa.Column("version_label", STRING(100), nullable=False, server_default="v1"),
        sa.Column("environment", STRING(50), nullable=False, server_default="dev"),
        sa.Column("description", TEXT, nullable=False, server_default=""),
        sa.Column("config", JSON, nullable=True),
        sa.Column("created_at", DATE_TIME, nullable=True),
    )
    op.create_index("ix_rag_apps_project_id", "rag_apps", ["project_id"])

    op.create_table(
        "documents",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("project_id", INTEGER, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("doc_id", STRING(200), nullable=False),
        sa.Column("title", STRING(300), nullable=False, server_default=""),
        sa.Column("source", STRING(300), nullable=False, server_default="import"),
        sa.Column("revision", INTEGER, nullable=False, server_default="1"),
        sa.Column("text", TEXT, nullable=False),
        sa.Column("fingerprint", STRING(64), nullable=False, server_default=""),
        sa.Column("metadata", JSON, nullable=True),
        sa.Column("created_at", DATE_TIME, nullable=True),
        sa.Column("updated_at", DATE_TIME, nullable=True),
        sa.UniqueConstraint("project_id", "doc_id", name="uq_doc_project_docid"),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index("ix_documents_project_fingerprint", "documents", ["project_id", "fingerprint"])

    op.create_table(
        "datasets",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("project_id", INTEGER, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", STRING(200), nullable=False),
        sa.Column("version", STRING(50), nullable=False, server_default="1.0"),
        sa.Column("description", TEXT, nullable=False, server_default=""),
        sa.Column("checksum", STRING(64), nullable=False, server_default=""),
        sa.Column("is_synthetic", BOOLEAN, nullable=False, server_default=sa.text("0")),
        sa.Column("reviewed", BOOLEAN, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", DATE_TIME, nullable=True),
        sa.UniqueConstraint("project_id", "name", "version", name="uq_dataset_version"),
    )
    op.create_index("ix_datasets_project_id", "datasets", ["project_id"])

    op.create_table(
        "dataset_items",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("dataset_id", INTEGER, sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("question", TEXT, nullable=False),
        sa.Column("reference_answer", TEXT, nullable=False, server_default=""),
        sa.Column("aliases", JSON, nullable=True),
        sa.Column("relevant_doc_ids", JSON, nullable=True),
        sa.Column("relevance_grades", JSON, nullable=True),
        sa.Column("expected_citations", JSON, nullable=True),
        sa.Column("category", STRING(80), nullable=False, server_default="factual"),
        sa.Column("difficulty", STRING(30), nullable=False, server_default="medium"),
        sa.Column("answerable", BOOLEAN, nullable=False, server_default=sa.text("1")),
        sa.Column("language", STRING(10), nullable=False, server_default="en"),
        sa.Column("topic", STRING(100), nullable=False, server_default=""),
        sa.Column("cohorts", JSON, nullable=True),
        sa.Column("is_synthetic", BOOLEAN, nullable=False, server_default=sa.text("0")),
        sa.Column("human_reviewed", BOOLEAN, nullable=False, server_default=sa.text("0")),
        sa.Column("notes", TEXT, nullable=False, server_default=""),
    )
    op.create_index("ix_dataset_items_dataset_id", "dataset_items", ["dataset_id"])
    op.create_index("ix_dataset_items_dataset", "dataset_items", ["dataset_id", "id"])

    op.create_table(
        "evaluation_runs",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("app_id", INTEGER, sa.ForeignKey("rag_apps.id"), nullable=False),
        sa.Column("dataset_id", INTEGER, sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("mode", STRING(30), nullable=False, server_default="end_to_end"),
        sa.Column("status", STRING(30), nullable=False, server_default="queued"),
        sa.Column("progress", INTEGER, nullable=False, server_default="0"),
        sa.Column("metrics", JSON, nullable=True),
        sa.Column("config_snapshot", JSON, nullable=True),
        sa.Column("idempotency_key", STRING(200), nullable=True, unique=True),
        sa.Column("cancel_requested", BOOLEAN, nullable=False, server_default=sa.text("0")),
        sa.Column("error", TEXT, nullable=False, server_default=""),
        sa.Column("total_input_tokens", INTEGER, nullable=False, server_default="0"),
        sa.Column("total_output_tokens", INTEGER, nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", FLOAT, nullable=False, server_default="0"),
        sa.Column("cost_is_estimate", BOOLEAN, nullable=False, server_default=sa.text("1")),
        sa.Column("judge_config", JSON, nullable=True),
        sa.Column("started_at", DATE_TIME, nullable=True),
        sa.Column("finished_at", DATE_TIME, nullable=True),
        sa.Column("created_at", DATE_TIME, nullable=True),
    )
    op.create_index("ix_evaluation_runs_app_id", "evaluation_runs", ["app_id"])
    op.create_index("ix_evaluation_runs_dataset_id", "evaluation_runs", ["dataset_id"])
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"])
    op.create_index("ix_runs_app_created", "evaluation_runs", ["app_id", "created_at"])

    op.create_table(
        "run_results",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("run_id", INTEGER, sa.ForeignKey("evaluation_runs.id"), nullable=False),
        sa.Column("item_id", INTEGER, sa.ForeignKey("dataset_items.id"), nullable=False),
        sa.Column("question", TEXT, nullable=False, server_default=""),
        sa.Column("category", STRING(80), nullable=False, server_default=""),
        sa.Column("cohorts", JSON, nullable=True),
        sa.Column("answerable", BOOLEAN, nullable=False, server_default=sa.text("1")),
        sa.Column("answer", TEXT, nullable=False, server_default=""),
        sa.Column("abstained", BOOLEAN, nullable=False, server_default=sa.text("0")),
        sa.Column("retrieved", JSON, nullable=True),
        sa.Column("citations", JSON, nullable=True),
        sa.Column("metrics", JSON, nullable=True),
        sa.Column("evidence", JSON, nullable=True),
        sa.Column("latency_ms", FLOAT, nullable=False, server_default="0"),
        sa.Column("retrieval_latency_ms", FLOAT, nullable=False, server_default="0"),
        sa.Column("generation_latency_ms", FLOAT, nullable=False, server_default="0"),
        sa.Column("input_tokens", INTEGER, nullable=False, server_default="0"),
        sa.Column("output_tokens", INTEGER, nullable=False, server_default="0"),
        sa.Column("error", TEXT, nullable=False, server_default=""),
    )
    op.create_index("ix_run_results_run_id", "run_results", ["run_id"])
    op.create_index("ix_run_results_item_id", "run_results", ["item_id"])
    op.create_index("ix_run_results_run_item", "run_results", ["run_id", "item_id"])

    op.create_table(
        "gate_policies",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("project_id", INTEGER, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", STRING(200), nullable=False),
        sa.Column("version", INTEGER, nullable=False, server_default="1"),
        sa.Column("description", TEXT, nullable=False, server_default=""),
        sa.Column("baseline_run_id", INTEGER, nullable=True),
        sa.Column("rules", JSON, nullable=True),
        sa.Column("min_samples", INTEGER, nullable=False, server_default="5"),
        sa.Column("created_at", DATE_TIME, nullable=True),
    )
    op.create_index("ix_gate_policies_project_id", "gate_policies", ["project_id"])

    op.create_table(
        "gate_evaluations",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("policy_id", INTEGER, sa.ForeignKey("gate_policies.id"), nullable=False),
        sa.Column("candidate_run_id", INTEGER, nullable=False),
        sa.Column("baseline_run_id", INTEGER, nullable=True),
        sa.Column("verdict", STRING(20), nullable=False),
        sa.Column("checks", JSON, nullable=True),
        sa.Column("summary", TEXT, nullable=False, server_default=""),
        sa.Column("created_at", DATE_TIME, nullable=True),
    )
    op.create_index("ix_gate_evaluations_policy_id", "gate_evaluations", ["policy_id"])
    op.create_index("ix_gate_evaluations_candidate_run_id", "gate_evaluations", ["candidate_run_id"])

    op.create_table(
        "provider_profiles",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("name", STRING(200), nullable=False),
        sa.Column("kind", STRING(40), nullable=False, server_default="offline"),
        sa.Column("role", STRING(40), nullable=False, server_default="judge"),
        sa.Column("base_url", STRING(500), nullable=False, server_default=""),
        sa.Column("api_key", STRING(500), nullable=False, server_default=""),
        sa.Column("model", STRING(200), nullable=False, server_default=""),
        sa.Column("timeout_s", FLOAT, nullable=False, server_default="30"),
        sa.Column("retries", INTEGER, nullable=False, server_default="2"),
        sa.Column("price_per_1k_input", FLOAT, nullable=False, server_default="0"),
        sa.Column("price_per_1k_output", FLOAT, nullable=False, server_default="0"),
        sa.Column("price_source", STRING(60), nullable=False, server_default="user-supplied"),
        sa.Column("is_default", BOOLEAN, nullable=False, server_default=sa.text("0")),
        sa.Column("enabled", BOOLEAN, nullable=False, server_default=sa.text("1")),
        sa.Column("max_concurrency", INTEGER, nullable=False, server_default="4"),
        sa.Column("created_at", DATE_TIME, nullable=True),
    )

    op.create_table(
        "drift_reports",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("project_id", INTEGER, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("baseline_run_id", INTEGER, nullable=False),
        sa.Column("candidate_run_id", INTEGER, nullable=False),
        sa.Column("signals", JSON, nullable=True),
        sa.Column("hypotheses", JSON, nullable=True),
        sa.Column("created_at", DATE_TIME, nullable=True),
    )
    op.create_index("ix_drift_reports_project_id", "drift_reports", ["project_id"])

    op.create_table(
        "judge_results",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("run_id", INTEGER, sa.ForeignKey("evaluation_runs.id"), nullable=False),
        sa.Column("result_id", INTEGER, nullable=False),
        sa.Column("provider_id", INTEGER, nullable=False),
        sa.Column("provider_name", STRING(200), nullable=False, server_default=""),
        sa.Column("model", STRING(200), nullable=False, server_default=""),
        sa.Column("rubric_version", STRING(50), nullable=False, server_default="faithfulness-v1"),
        sa.Column("dimension", STRING(50), nullable=False, server_default="faithfulness"),
        sa.Column("score", FLOAT, nullable=True),
        sa.Column("rationale", TEXT, nullable=False, server_default=""),
        sa.Column("raw_output", TEXT, nullable=False, server_default=""),
        sa.Column("usage_exact", BOOLEAN, nullable=False, server_default=sa.text("0")),
        sa.Column("input_tokens", INTEGER, nullable=False, server_default="0"),
        sa.Column("output_tokens", INTEGER, nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", FLOAT, nullable=False, server_default="0"),
        sa.Column("human_verdict", STRING(30), nullable=False, server_default=""),
        sa.Column("created_at", DATE_TIME, nullable=True),
    )
    op.create_index("ix_judge_results_run_id", "judge_results", ["run_id"])
    op.create_index("ix_judge_results_result_id", "judge_results", ["result_id"])
    op.create_index("ix_judge_run_result", "judge_results", ["run_id", "result_id"])

    op.create_table(
        "alerts",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("project_id", INTEGER, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("fingerprint", STRING(200), nullable=False),
        sa.Column("kind", STRING(80), nullable=False, server_default="drift"),
        sa.Column("severity", STRING(20), nullable=False, server_default="warning"),
        sa.Column("message", TEXT, nullable=False, server_default=""),
        sa.Column("status", STRING(30), nullable=False, server_default="open"),
        sa.Column("created_at", DATE_TIME, nullable=True),
    )
    op.create_index("ix_alerts_project_id", "alerts", ["project_id"])
    op.create_index("ix_alerts_fingerprint", "alerts", ["fingerprint"])
    op.create_index("ix_alerts_fingerprint_status", "alerts", ["fingerprint", "status"])

    op.create_table(
        "scheduled_jobs",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("project_id", INTEGER, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", STRING(200), nullable=False),
        sa.Column("app_id", INTEGER, sa.ForeignKey("rag_apps.id"), nullable=False),
        sa.Column("dataset_id", INTEGER, sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("policy_id", INTEGER, sa.ForeignKey("gate_policies.id"), nullable=True),
        sa.Column("interval_minutes", INTEGER, nullable=False, server_default="60"),
        sa.Column("mode", STRING(30), nullable=False, server_default="end_to_end"),
        sa.Column("enabled", BOOLEAN, nullable=False, server_default=sa.text("1")),
        sa.Column("last_run_at", DATE_TIME, nullable=True),
        sa.Column("last_run_id", INTEGER, nullable=True),
        sa.Column("next_run_at", DATE_TIME, nullable=True),
        sa.Column("created_at", DATE_TIME, nullable=True),
    )
    op.create_index("ix_scheduled_jobs_project_id", "scheduled_jobs", ["project_id"])

    op.create_table(
        "production_traces",
        sa.Column("id", INTEGER, primary_key=True),
        sa.Column("project_id", INTEGER, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("question", TEXT, nullable=False),
        sa.Column("answer", TEXT, nullable=False, server_default=""),
        sa.Column("retrieved_doc_ids", JSON, nullable=True),
        sa.Column("category", STRING(80), nullable=False, server_default="production"),
        sa.Column("latency_ms", FLOAT, nullable=False, server_default="0"),
        sa.Column("source", STRING(120), nullable=False, server_default="import"),
        sa.Column("created_at", DATE_TIME, nullable=True),
    )
    op.create_index("ix_production_traces_project_id", "production_traces", ["project_id"])


def downgrade() -> None:
    for table in ("production_traces", "scheduled_jobs", "alerts", "judge_results", "drift_reports",
                  "provider_profiles", "gate_evaluations", "gate_policies", "run_results",
                  "evaluation_runs", "dataset_items", "datasets", "documents", "rag_apps", "projects"):
        op.drop_table(table)
