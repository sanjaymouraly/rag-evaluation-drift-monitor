"""Security and robustness tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.scheduler import Scheduler
from app.security import (
    constant_time_equals,
    fingerprint,
    mask_key,
    redact_obj,
    redact_text,
    safe_join,
    sanitize_filename,
)


def test_redact_text_removes_known_secret_shapes():
    text = "key sk-abcdefghijklmnop and Bearer abcdefghijklmnop and password=hunter2"
    redacted = redact_text(text)
    assert "sk-abcdefghijklmnop" not in redacted
    assert "abcdefghijklmnop" not in redacted
    assert "hunter2" not in redacted


def test_redact_text_removes_explicit_secrets():
    assert "supersecret" not in redact_text("value=supersecret", ["supersecret"])


def test_redact_obj_walks_nested_structures():
    payload = {
        "api_key": "sk-1234567890",
        "nested": {"authorization": "Bearer xyz", "safe": "value"},
        "list": [{"password": "p"}],
    }
    redacted = redact_obj(payload)
    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["nested"]["authorization"] == "***REDACTED***"
    assert redacted["nested"]["safe"] == "value"
    assert redacted["list"][0]["password"] == "***REDACTED***"


def test_mask_key_never_reveals_the_whole_key():
    assert mask_key("sk-1234567890abcdef").endswith("cdef")
    assert "1234567890" not in mask_key("sk-1234567890abcdef")
    assert mask_key(None) == ""
    assert mask_key("ab") == "**"


def test_safe_join_blocks_path_traversal(tmp_path: Path):
    with pytest.raises(ValueError):
        safe_join(tmp_path, "../etc/passwd")
    with pytest.raises(ValueError):
        safe_join(tmp_path, "/etc/passwd")
    assert safe_join(tmp_path, "a", "b").name == "b"


def test_sanitize_filename():
    assert sanitize_filename("../../evil.sh") == "evil.sh"
    assert sanitize_filename("ok name.txt") == "ok_name.txt"
    assert sanitize_filename("..") == "upload"


def test_constant_time_equals():
    assert constant_time_equals("abc", "abc") is True
    assert constant_time_equals("abc", "abd") is False
    assert constant_time_equals("", "") is True


def test_fingerprint_is_stable_and_short():
    assert fingerprint("hello") == fingerprint("hello")
    assert fingerprint("hello") != fingerprint("hello!")
    assert len(fingerprint("hello")) == 16


def test_upload_limit_is_enforced(client):
    response = client.post("/api/projects", json={"name": "x", "description": "y" * 10})
    assert response.status_code == 201


def test_rate_limit_headers_are_not_leaked(client):
    response = client.get("/health")
    assert "x-powered-by" not in {k.lower() for k in response.headers}


def test_scheduler_runs_due_jobs(db):
    """A scheduled job executes and records its next run time."""
    import datetime as dt

    from app.models import Dataset, DatasetItem, Document, EvaluationRun, Project, RagApp, ScheduledJob

    project = Project(name="scheduler-test")
    db.add(project)
    db.flush()
    db.add(Document(project_id=project.id, doc_id="d", text="Bees waggle.", fingerprint="f"))
    dataset = Dataset(project_id=project.id, name="bench", version="1.0")
    db.add(dataset)
    db.flush()
    db.add(
        DatasetItem(dataset_id=dataset.id, question="Q?", reference_answer="A", relevant_doc_ids=["d"], answerable=True)
    )
    app = RagApp(
        project_id=project.id,
        name="rag",
        version_label="v1",
        config={"retriever": "bm25", "chunk_chars": 200, "top_k": 2},
    )
    db.add(app)
    db.flush()
    job = ScheduledJob(
        project_id=project.id,
        name="job",
        app_id=app.id,
        dataset_id=dataset.id,
        interval_minutes=30,
        next_run_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1),
    )
    db.add(job)
    db.commit()

    scheduler = Scheduler()
    executed = scheduler.tick()
    assert any(e["job_id"] == job.id for e in executed)
    db.refresh(job)
    assert job.last_run_id is not None
    assert job.next_run_at is not None
    run = db.get(EvaluationRun, job.last_run_id)
    assert run.status == "completed"


def test_scheduler_does_not_run_a_job_twice(db):
    import datetime as dt

    from app.models import Dataset, Document, Project, RagApp, ScheduledJob

    project = Project(name="scheduler-twice")
    db.add(project)
    db.flush()
    db.add(Document(project_id=project.id, doc_id="d", text="Bees waggle.", fingerprint="f"))
    dataset = Dataset(project_id=project.id, name="bench", version="1.0")
    db.add(dataset)
    db.flush()
    app = RagApp(
        project_id=project.id,
        name="rag",
        version_label="v1",
        config={"retriever": "bm25", "chunk_chars": 200, "top_k": 2},
    )
    db.add(app)
    db.flush()
    job = ScheduledJob(
        project_id=project.id,
        name="job",
        app_id=app.id,
        dataset_id=dataset.id,
        interval_minutes=30,
        next_run_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1),
    )
    db.add(job)
    db.commit()

    scheduler = Scheduler()
    first = scheduler.tick()
    second = scheduler.tick()
    assert any(e["job_id"] == job.id for e in first)
    assert not any(e["job_id"] == job.id for e in second)


def test_api_key_is_required_when_configured(monkeypatch):
    """The API key guard protects every endpoint except the health probes."""
    from fastapi.testclient import TestClient

    from app import config as config_module
    from app.main import app

    monkeypatch.setattr(config_module.settings, "api_key", "test-key-1234")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        denied = client.get("/api/overview")
        assert denied.status_code == 401
        allowed = client.get("/api/overview", headers={"X-API-Key": "test-key-1234"})
        assert allowed.status_code == 200
        wrong = client.get("/api/overview", headers={"X-API-Key": "wrong"})
        assert wrong.status_code == 401
