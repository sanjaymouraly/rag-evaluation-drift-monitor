"""Datasets and benchmark items."""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..evaluation import dataset_checksum
from ..ingestion import IngestionError, parse_dataset_file
from ..metrics import content_tokens
from ..models import Dataset, DatasetItem, Document, EvaluationRun, Project
from .deps import dataset_out, get_or_404, item_out
from .schemas import DatasetIn, ItemIn, SyntheticIn

router = APIRouter(prefix="/api", tags=["datasets"])


def _refresh_checksum(db: Session, dataset_id: int) -> None:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        return
    items = db.query(DatasetItem).filter_by(dataset_id=dataset_id).order_by(DatasetItem.id).all()
    dataset.checksum = dataset_checksum(items)
    db.commit()


@router.get("/datasets")
def list_datasets(db: Session = Depends(get_db)):
    out = []
    for dataset in db.query(Dataset).order_by(Dataset.id).all():
        n_items = db.query(DatasetItem).filter_by(dataset_id=dataset.id).count()
        out.append(dataset_out(dataset, n_items))
    return out


@router.post("/datasets", status_code=201)
def create_dataset(body: DatasetIn, db: Session = Depends(get_db)):
    get_or_404(db, Project, body.project_id, "project")
    dataset = Dataset(project_id=body.project_id, name=body.name, version=body.version, description=body.description)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset_out(dataset, 0)


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: int, db: Session = Depends(get_db)):
    dataset = get_or_404(db, Dataset, dataset_id, "dataset")
    n_items = db.query(DatasetItem).filter_by(dataset_id=dataset_id).count()
    return dataset_out(dataset, n_items)


@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: int, db: Session = Depends(get_db)):
    dataset = get_or_404(db, Dataset, dataset_id, "dataset")
    used = db.query(EvaluationRun).filter_by(dataset_id=dataset_id).count()
    if used:
        raise HTTPException(
            409,
            f"dataset is referenced by {used} evaluation run(s); "
            "delete those runs first to keep the evidence auditable",
        )
    db.query(DatasetItem).filter_by(dataset_id=dataset_id).delete()
    db.delete(dataset)
    db.commit()
    return {"deleted": dataset_id}


@router.get("/datasets/{dataset_id}/items")
def list_items(dataset_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Dataset, dataset_id, "dataset")
    items = db.query(DatasetItem).filter_by(dataset_id=dataset_id).order_by(DatasetItem.id).all()
    return [item_out(i) for i in items]


@router.post("/datasets/{dataset_id}/items", status_code=201)
def add_item(dataset_id: int, body: ItemIn, db: Session = Depends(get_db)):
    get_or_404(db, Dataset, dataset_id, "dataset")
    item = DatasetItem(dataset_id=dataset_id, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    _refresh_checksum(db, dataset_id)
    return item_out(item)


@router.put("/datasets/{dataset_id}/items/{item_id}")
def update_item(dataset_id: int, item_id: int, body: ItemIn, db: Session = Depends(get_db)):
    get_or_404(db, Dataset, dataset_id, "dataset")
    item = get_or_404(db, DatasetItem, item_id, "dataset item")
    if item.dataset_id != dataset_id:
        raise HTTPException(404, "dataset item not found in this dataset")
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    _refresh_checksum(db, dataset_id)
    return item_out(item)


@router.delete("/datasets/{dataset_id}/items/{item_id}")
def delete_item(dataset_id: int, item_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Dataset, dataset_id, "dataset")
    item = get_or_404(db, DatasetItem, item_id, "dataset item")
    if item.dataset_id != dataset_id:
        raise HTTPException(404, "dataset item not found in this dataset")
    db.delete(item)
    db.commit()
    _refresh_checksum(db, dataset_id)
    return {"deleted": item_id}


@router.post("/datasets/{dataset_id}/clone", status_code=201)
def clone_dataset(dataset_id: int, db: Session = Depends(get_db)):
    source = get_or_404(db, Dataset, dataset_id, "dataset")
    clone = Dataset(
        project_id=source.project_id,
        name=f"{source.name} (copy)",
        version=source.version,
        description=source.description,
    )
    db.add(clone)
    db.flush()
    for item in db.query(DatasetItem).filter_by(dataset_id=dataset_id).all():
        db.add(
            DatasetItem(
                dataset_id=clone.id,
                question=item.question,
                reference_answer=item.reference_answer,
                aliases=item.aliases,
                relevant_doc_ids=item.relevant_doc_ids,
                relevance_grades=item.relevance_grades,
                expected_citations=item.expected_citations,
                category=item.category,
                difficulty=item.difficulty,
                answerable=item.answerable,
                language=item.language,
                topic=item.topic,
                cohorts=item.cohorts,
                is_synthetic=item.is_synthetic,
                notes=item.notes,
            )
        )
    db.commit()
    db.refresh(clone)
    _refresh_checksum(db, clone.id)
    return dataset_out(clone, db.query(DatasetItem).filter_by(dataset_id=clone.id).count())


@router.post("/datasets/{dataset_id}/import", status_code=201)
async def import_items(dataset_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import benchmark items from a CSV, JSONL or JSON file (duplicates skipped)."""
    get_or_404(db, Dataset, dataset_id, "dataset")
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(413, "file too large")
    try:
        rows = parse_dataset_file(file.filename or "dataset.csv", raw, settings.max_upload_bytes)
    except IngestionError as exc:
        raise HTTPException(422, str(exc)) from exc
    existing = {i.question.strip().lower() for i in db.query(DatasetItem).filter_by(dataset_id=dataset_id).all()}
    added, skipped = 0, 0
    for row in rows:
        key = row["question"].strip().lower()
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        db.add(DatasetItem(dataset_id=dataset_id, **row))
        added += 1
    db.commit()
    _refresh_checksum(db, dataset_id)
    return {"imported": added, "skipped_duplicates": skipped, "received": len(rows)}


@router.get("/datasets/{dataset_id}/export")
def export_items(dataset_id: int, format: str = "jsonl", db: Session = Depends(get_db)):
    get_or_404(db, Dataset, dataset_id, "dataset")
    items = db.query(DatasetItem).filter_by(dataset_id=dataset_id).order_by(DatasetItem.id).all()
    rows = [item_out(i) for i in items]
    if format == "jsonl":
        body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
        return PlainTextResponse(
            body,
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f"attachment; filename=dataset-{dataset_id}.jsonl"},
        )
    if format == "csv":
        buf = io.StringIO()
        columns = [
            "question",
            "reference_answer",
            "aliases",
            "relevant_doc_ids",
            "relevance_grades",
            "expected_citations",
            "category",
            "difficulty",
            "answerable",
            "language",
            "topic",
            "cohorts",
        ]
        writer = csv.DictWriter(buf, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "question": row["question"],
                    "reference_answer": row["reference_answer"],
                    "aliases": "|".join(row["aliases"]),
                    "relevant_doc_ids": "|".join(row["relevant_doc_ids"]),
                    "relevance_grades": json.dumps(row["relevance_grades"]),
                    "expected_citations": json.dumps(row["expected_citations"]),
                    "category": row["category"],
                    "difficulty": row["difficulty"],
                    "answerable": row["answerable"],
                    "language": row["language"],
                    "topic": row["topic"],
                    "cohorts": "|".join(row["cohorts"]),
                }
            )
        return PlainTextResponse(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=dataset-{dataset_id}.csv"},
        )
    raise HTTPException(422, "format must be jsonl|csv")


@router.get("/datasets/{dataset_id}/validate")
def validate_dataset(dataset_id: int, db: Session = Depends(get_db)):
    """Check dataset / corpus consistency before running an evaluation.

    Retrieval metrics cannot be computed for items whose source documents are
    absent — this endpoint surfaces that *before* a run instead of silently
    scoring zero.
    """
    dataset = get_or_404(db, Dataset, dataset_id, "dataset")
    items = db.query(DatasetItem).filter_by(dataset_id=dataset_id).order_by(DatasetItem.id).all()
    corpus = {d.doc_id for d in db.query(Document).filter_by(project_id=dataset.project_id).all()}
    seen: dict[str, int] = {}
    issues: list[dict] = []
    for item in items:
        key = item.question.strip().lower()
        if key in seen:
            issues.append(
                {
                    "item_id": item.id,
                    "kind": "duplicate_question",
                    "detail": f"duplicates item {seen[key]}",
                    "severity": "warning",
                }
            )
        seen[key] = item.id
        missing = [d for d in (item.relevant_doc_ids or []) if d not in corpus]
        if missing:
            issues.append(
                {
                    "item_id": item.id,
                    "kind": "missing_source",
                    "detail": f"relevant documents not in the corpus: {missing}",
                    "severity": "error",
                }
            )
        if item.answerable and not (item.relevant_doc_ids or []):
            issues.append(
                {
                    "item_id": item.id,
                    "kind": "no_relevance_labels",
                    "detail": "retrieval metrics will be null (no evidence); answer metrics are still computed",
                    "severity": "warning",
                }
            )
        if item.answerable and not item.reference_answer.strip():
            issues.append(
                {
                    "item_id": item.id,
                    "kind": "no_reference",
                    "detail": "token-F1 / exact match will be null for this item",
                    "severity": "warning",
                }
            )
        if not item.answerable and item.reference_answer.strip():
            issues.append(
                {
                    "item_id": item.id,
                    "kind": "unanswerable_with_reference",
                    "detail": "a reference answer is present but the item is marked unanswerable; "
                    "only abstention is scored",
                    "severity": "warning",
                }
            )
        if item.is_synthetic:
            issues.append(
                {
                    "item_id": item.id,
                    "kind": "synthetic_unreviewed",
                    "detail": "synthetic item — not automatically trusted as ground truth",
                    "severity": "warning",
                }
            )
    errors = [i for i in issues if i.get("severity") == "error"]
    return {
        "dataset_id": dataset_id,
        "n_items": len(items),
        "corpus_docs": len(corpus),
        "ok": not errors,
        "n_issues": len(issues),
        "issues": issues,
        "summary": (
            "Dataset is consistent with the corpus."
            if not issues
            else f"{len(errors)} blocking issue(s), {len(issues) - len(errors)} warning(s)."
        ),
    }


@router.post("/datasets/{dataset_id}/generate-synthetic", status_code=201)
def generate_synthetic(dataset_id: int, body: SyntheticIn, db: Session = Depends(get_db)):
    """Generate synthetic QA *drafts* from the corpus.

    The items are clearly labelled ``synthetic-unreviewed``: they are never
    automatically trusted as ground truth and a human must review them before
    they are used in a release gate.
    """
    dataset = get_or_404(db, Dataset, dataset_id, "dataset")
    documents = db.query(Document).filter_by(project_id=dataset.project_id).order_by(Document.doc_id).all()
    existing = {i.question.strip().lower() for i in db.query(DatasetItem).filter_by(dataset_id=dataset_id).all()}
    created = 0
    for document in documents:
        if created >= body.max_items:
            break
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", document.text or "") if len(s.strip()) > 40]
        if not sentences:
            continue
        best = max(sentences, key=lambda s: len(content_tokens(s)))
        terms = [t for t, _ in Counter(content_tokens(best)).most_common(3)]
        question = (
            f"[SYNTHETIC — review required] What does “{document.title or document.doc_id}” "
            f"state about {' '.join(terms)}?"
        )
        if question.lower() in existing:
            continue
        existing.add(question.lower())
        db.add(
            DatasetItem(
                dataset_id=dataset_id,
                question=question,
                reference_answer=best,
                relevant_doc_ids=[document.doc_id],
                expected_citations=[{"doc_id": document.doc_id}],
                category="synthetic-unreviewed",
                difficulty="unknown",
                answerable=True,
                topic="synthetic",
                cohorts=["synthetic"],
                is_synthetic=True,
                notes="Generated from corpus sentences. Requires human review.",
            )
        )
        created += 1
    db.commit()
    _refresh_checksum(db, dataset_id)
    return {
        "created": created,
        "warning": "Synthetic items are drafts labelled synthetic-unreviewed. "
        "Human review is required before gating on them.",
    }
