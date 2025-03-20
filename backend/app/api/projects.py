"""Projects, RAG applications and document ingestion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..ingestion import IngestionError, parse_document
from ..models import (
    Alert,
    Dataset,
    DatasetItem,
    Document,
    DriftReport,
    EvaluationRun,
    GateEvaluation,
    GatePolicy,
    JudgeResult,
    ProductionTrace,
    Project,
    RagApp,
    RunResult,
    ScheduledJob,
)
from ..security import fingerprint
from .deps import app_out, document_out, get_or_404, project_out
from .schemas import AppIn, DocumentIn, ProjectIn

router = APIRouter(prefix="/api", tags=["projects"])


# ------------------------------------------------------------------ projects


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    return [project_out(p) for p in db.query(Project).order_by(Project.id).all()]


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, db: Session = Depends(get_db)):
    project = Project(name=body.name, description=body.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project_out(project)


@router.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Delete a project and everything that belongs to it."""
    project = get_or_404(db, Project, project_id, "project")
    for app in db.query(RagApp).filter_by(project_id=project_id).all():
        for run in db.query(EvaluationRun).filter_by(app_id=app.id).all():
            db.query(JudgeResult).filter_by(run_id=run.id).delete()
            db.query(RunResult).filter_by(run_id=run.id).delete()
        db.query(EvaluationRun).filter_by(app_id=app.id).delete()
        db.delete(app)
    db.flush()
    for evaluation in db.query(GateEvaluation).all():
        if evaluation.policy_id in {p.id for p in db.query(GatePolicy).filter_by(project_id=project_id).all()}:
            db.delete(evaluation)
    for policy in db.query(GatePolicy).filter_by(project_id=project_id).all():
        db.delete(policy)
    db.flush()
    for dataset in db.query(Dataset).filter_by(project_id=project_id).all():
        db.query(DatasetItem).filter_by(dataset_id=dataset.id).delete()
        db.delete(dataset)
    db.query(ScheduledJob).filter_by(project_id=project_id).delete()
    db.query(ProductionTrace).filter_by(project_id=project_id).delete()
    db.query(DriftReport).filter_by(project_id=project_id).delete()
    db.query(Alert).filter_by(project_id=project_id).delete()
    db.query(Document).filter_by(project_id=project_id).delete()
    db.delete(project)
    db.commit()
    return {"deleted": project_id}


# ---------------------------------------------------------------------- apps


@router.get("/apps")
def list_apps(project_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(RagApp)
    if project_id:
        query = query.filter_by(project_id=project_id)
    return [app_out(a) for a in query.order_by(RagApp.id).all()]


@router.post("/apps", status_code=201)
def create_app(body: AppIn, db: Session = Depends(get_db)):
    get_or_404(db, Project, body.project_id, "project")
    app = RagApp(
        project_id=body.project_id,
        name=body.name,
        version_label=body.version_label,
        environment=body.environment,
        description=body.description,
        config=body.config,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app_out(app)


@router.put("/apps/{app_id}")
def update_app(app_id: int, body: AppIn, db: Session = Depends(get_db)):
    app = get_or_404(db, RagApp, app_id, "app")
    app.project_id = body.project_id
    app.name = body.name
    app.version_label = body.version_label
    app.environment = body.environment
    app.description = body.description
    app.config = body.config
    db.commit()
    db.refresh(app)
    return app_out(app)


@router.delete("/apps/{app_id}")
def delete_app(app_id: int, db: Session = Depends(get_db)):
    app = get_or_404(db, RagApp, app_id, "app")
    runs = db.query(EvaluationRun).filter_by(app_id=app_id).all()
    for run in runs:
        db.query(RunResult).filter_by(run_id=run.id).delete()
    db.query(EvaluationRun).filter_by(app_id=app_id).delete()
    db.delete(app)
    db.commit()
    return {"deleted_app": app_id, "deleted_runs": len(runs)}


# ----------------------------------------------------------------- documents


@router.get("/documents")
def list_documents(project_id: int, db: Session = Depends(get_db)):
    documents = db.query(Document).filter_by(project_id=project_id).order_by(Document.doc_id).all()
    return [document_out(d) for d in documents]


@router.post("/documents", status_code=201)
def upsert_document(body: DocumentIn, db: Session = Depends(get_db)):
    get_or_404(db, Project, body.project_id, "project")
    if len(body.text.encode("utf-8")) > settings.max_upload_bytes:
        raise HTTPException(413, "document too large")
    existing = db.query(Document).filter_by(project_id=body.project_id, doc_id=body.doc_id).first()
    if existing:
        existing.text = body.text
        existing.title = body.title
        existing.revision += 1
        existing.fingerprint = fingerprint(body.text)
        existing.metadata_ = body.metadata or existing.metadata_ or {}
        db.commit()
        db.refresh(existing)
        return {"id": existing.id, "doc_id": existing.doc_id, "revision": existing.revision, "updated": True}
    document = Document(
        project_id=body.project_id,
        doc_id=body.doc_id,
        title=body.title,
        text=body.text,
        source=body.source,
        fingerprint=fingerprint(body.text),
        metadata_=body.metadata or {},
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return {"id": document.id, "doc_id": document.doc_id, "revision": document.revision, "updated": False}


@router.post("/documents/upload", status_code=201)
async def upload_document(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a plain-text document. The file name is sanitised and the content
    is stored as data only."""
    get_or_404(db, Project, project_id, "project")
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(413, "file too large")
    try:
        parsed = parse_document(file.filename or "document.txt", raw, settings.max_upload_bytes)
    except IngestionError as exc:
        raise HTTPException(422, str(exc)) from exc
    existing = db.query(Document).filter_by(project_id=project_id, doc_id=parsed["doc_id"]).first()
    if existing:
        existing.text = parsed["text"]
        existing.title = parsed["title"]
        existing.revision += 1
        existing.fingerprint = fingerprint(parsed["text"])
        existing.metadata_ = parsed["metadata"]
        db.commit()
        db.refresh(existing)
        return {"id": existing.id, "doc_id": existing.doc_id, "revision": existing.revision, "updated": True}
    document = Document(
        project_id=project_id,
        doc_id=parsed["doc_id"],
        title=parsed["title"],
        text=parsed["text"],
        source=parsed["source"],
        fingerprint=fingerprint(parsed["text"]),
        metadata_=parsed["metadata"],
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return {"id": document.id, "doc_id": document.doc_id, "revision": document.revision, "updated": False}


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    document = get_or_404(db, Document, document_id, "document")
    db.delete(document)
    db.commit()
    return {"deleted": document_id}
