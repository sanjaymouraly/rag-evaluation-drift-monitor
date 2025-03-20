"""Integration tests: ingestion, adapters, persistence and the evaluation workflow."""

from __future__ import annotations

import json

import httpx
import pytest

from app.evaluation import dataset_checksum, execute_run, score_item
from app.ingestion import IngestionError, parse_dataset_file, parse_document
from app.metrics import MetricContext
from app.models import Dataset, DatasetItem, Document, EvaluationRun, Project, RagApp
from app.rag import SampleRAG, extractive_answer, parse_citations, run_rest_adapter
from app.retrievers import build_retriever, chunk_document

# ------------------------------------------------------------------ ingestion


def test_parse_text_document():
    parsed = parse_document("notes.md", b"# Title\n\nSome body text about bees.")
    assert parsed["doc_id"] == "notes"
    assert "bees" in parsed["text"]
    assert parsed["metadata"]["bytes"] > 0


def test_parse_document_rejects_path_traversal_names():
    parsed = parse_document("../../etc/passwd", b"content")
    assert "/" not in parsed["doc_id"]
    assert ".." not in parsed["doc_id"]


def test_parse_document_rejects_empty_files():
    with pytest.raises(IngestionError):
        parse_document("empty.txt", b"   ")


def test_parse_document_enforces_the_size_limit():
    with pytest.raises(IngestionError):
        parse_document("big.txt", b"x" * 100, max_bytes=10)


def test_parse_jsonl_dataset():
    rows = [
        {
            "question": "Q1?",
            "reference_answer": "A1",
            "relevant_doc_ids": ["doc_a"],
            "category": "factual",
            "answerable": True,
            "aliases": ["A1 alt"],
        },
        {
            "question": "Q2?",
            "reference_answer": "",
            "relevant_doc_ids": [],
            "category": "unanswerable",
            "answerable": False,
        },
    ]
    payload = "\n".join(json.dumps(r) for r in rows).encode()
    items = parse_dataset_file("bench.jsonl", payload)
    assert len(items) == 2
    assert items[0]["aliases"] == ["A1 alt"]
    assert items[1]["answerable"] is False


def test_parse_csv_dataset_with_pipe_separated_lists():
    payload = (
        b"question,reference_answer,relevant_doc_ids,aliases,answerable\n"
        b"What is X?,X value,doc_a|doc_b,alias one|alias two,true\n"
    )
    items = parse_dataset_file("bench.csv", payload)
    assert items[0]["relevant_doc_ids"] == ["doc_a", "doc_b"]
    assert items[0]["aliases"] == ["alias one", "alias two"]


def test_parse_dataset_rejects_rows_without_a_question():
    with pytest.raises(IngestionError):
        parse_dataset_file("bench.jsonl", b'{"reference_answer": "no question"}\n')


def test_parse_dataset_rejects_invalid_json():
    with pytest.raises(IngestionError):
        parse_dataset_file("bench.jsonl", b"{not json}\n")


# ------------------------------------------------------------------- chunking


def test_chunking_is_deterministic_and_overlapping():
    text = "Sentence one. " * 60
    first = chunk_document("d", text, chunk_chars=200, overlap_chars=40)
    second = chunk_document("d", text, chunk_chars=200, overlap_chars=40)
    assert first == second
    assert len(first) > 1
    assert all(c["doc_id"] == "d" for c in first)
    assert first[0]["char_start"] == 0


def test_chunking_empty_document():
    assert chunk_document("d", "", 200, 20) == []


# ----------------------------------------------------------------- retrieval


def test_bm25_ranks_the_relevant_chunk_first():
    chunks = [
        {"chunk_id": "a", "doc_id": "a", "text": "Bees signal distance with a waggle dance."},
        {"chunk_id": "b", "doc_id": "b", "text": "Sourdough starter needs flour and water."},
    ]
    index = build_retriever("bm25", chunks)
    results = index.search("how do bees signal distance", top_k=2)
    assert results[0]["doc_id"] == "a"


def test_degraded_retriever_only_uses_the_first_query_token():
    # The degraded retriever is the deliberately broken configuration used to
    # demonstrate regression detection: only the first query token is used.
    chunks = [
        {"chunk_id": "a", "doc_id": "a", "text": "Bees signal distance with a waggle dance."},
        {"chunk_id": "b", "doc_id": "b", "text": "Sourdough starter needs flour and water."},
    ]
    degraded = build_retriever("degraded_keyword", chunks)
    first = degraded.search("bees waggle", top_k=1)
    same_first_token = degraded.search("bees something entirely different", top_k=1)
    other_first_token = degraded.search("sourdough something entirely different", top_k=1)
    assert first[0]["chunk_id"] == same_first_token[0]["chunk_id"]
    assert first[0]["chunk_id"] != other_first_token[0]["chunk_id"]

    # The healthy BM25 index uses the whole query and ranks differently.
    good = build_retriever("bm25", chunks)
    assert good.search("bees waggle", top_k=1)[0]["doc_id"] == "a"
    assert good.search("sourdough flour", top_k=1)[0]["doc_id"] == "b"


# ----------------------------------------------------------------------- RAG


def test_extractive_answer_cites_the_source_chunk():
    contexts = [{"chunk_id": "a::c0", "doc_id": "a", "text": "Bees signal distance with a waggle dance."}]
    answer = extractive_answer("how do bees signal distance", contexts)
    assert answer["abstained"] is False
    assert answer["citations"][0]["doc_id"] == "a"
    assert "waggle" in answer["answer"]


def test_extractive_answer_abstains_without_context():
    answer = extractive_answer("anything", [])
    assert answer["abstained"] is True
    assert answer["citations"] == []


def test_sample_rag_runs_end_to_end():
    rag = SampleRAG(
        [{"doc_id": "a", "text": "Bees signal distance with a waggle dance."}],
        {"retriever": "bm25", "chunk_chars": 300, "top_k": 3},
    )
    out = rag.run("how do bees signal distance")
    assert out["retrieved"]
    assert out["latency_ms"] >= 0
    assert out["retrieval_ms"] >= 0


def test_parse_citations_from_generated_text():
    chunks = {"a::c0": {"chunk_id": "a::c0", "doc_id": "a", "text": "text"}}
    citations = parse_citations("Bees waggle [a] and again [a::c0].", chunks)
    assert {c["doc_id"] for c in citations} == {"a"}
    assert len(citations) == 1  # duplicates are collapsed


# --------------------------------------------------------------- REST adapter


def test_rest_adapter_maps_a_custom_response_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["query"] == "question text"
        return httpx.Response(
            200,
            json={
                "data": {
                    "output": "The answer is 42.",
                    "sources": [{"id": "doc_x", "content": "The answer is 42."}],
                    "refs": [{"document": "doc_x"}],
                }
            },
        )

    adapter = {
        "url": "http://rag.example/ask",
        "method": "POST",
        "question_field": "query",
        "answer_path": "data.output",
        "retrieved_path": "data.sources",
        "citations_path": "data.refs",
    }
    out = run_rest_adapter(adapter, "question text", transport=httpx.MockTransport(handler))
    assert out["answer"] == "The answer is 42."
    assert out["retrieved"][0]["doc_id"] == "doc_x"
    assert out["citations"][0]["doc_id"] == "doc_x"


def test_rest_adapter_reports_http_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    adapter = {"url": "http://rag.example/ask"}
    with pytest.raises(RuntimeError):
        run_rest_adapter(adapter, "q", transport=httpx.MockTransport(handler))


# ----------------------------------------------------------------- persistence


def _make_project(db, name: str) -> Project:
    project = Project(name=name, description="test")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def test_dataset_checksum_changes_with_content():
    db_items = [DatasetItem(question="Q", reference_answer="A", relevant_doc_ids=["d"])]
    first = dataset_checksum(db_items)
    db_items[0].reference_answer = "B"
    assert dataset_checksum(db_items) != first
    # The same content in a different order of fields yields the same checksum.
    other = [DatasetItem(question="Q", reference_answer="A", relevant_doc_ids=["d"])]
    assert dataset_checksum(other) == first


def test_evaluation_run_persists_results_and_metrics(db):
    project = _make_project(db, "integration-run")
    db.add(
        Document(
            project_id=project.id,
            doc_id="doc_a",
            title="A",
            text="Bees signal distance with a waggle dance. The angle encodes direction.",
            fingerprint="f1",
        )
    )
    db.commit()
    dataset = Dataset(project_id=project.id, name="bench", version="1.0")
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.add(
        DatasetItem(
            dataset_id=dataset.id,
            question="How do bees signal distance?",
            reference_answer="With a waggle dance.",
            relevant_doc_ids=["doc_a"],
            relevance_grades={"doc_a": 1.0},
            expected_citations=[{"doc_id": "doc_a"}],
            category="factual",
            answerable=True,
        )
    )
    db.add(
        DatasetItem(
            dataset_id=dataset.id,
            question="What is the capital of Mars?",
            reference_answer="",
            relevant_doc_ids=[],
            category="unanswerable",
            answerable=False,
        )
    )
    db.commit()

    app = RagApp(
        project_id=project.id,
        name="rag",
        version_label="v1",
        config={"retriever": "bm25", "chunk_chars": 300, "top_k": 3},
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    run = EvaluationRun(app_id=app.id, dataset_id=dataset.id, mode="end_to_end", status="queued")
    db.add(run)
    db.commit()
    db.refresh(run)

    execute_run(db, run.id)
    db.refresh(run)
    assert run.status == "completed"
    metrics = run.metrics["metrics"]
    assert metrics["recall_at_5"]["value"] == pytest.approx(1.0)
    assert metrics["citation_support"]["value"] == pytest.approx(1.0)
    assert metrics["token_f1"]["value"] > 0
    assert run.config_snapshot["dataset_checksum"]
    assert run.config_snapshot["corpus_manifest"][0]["doc_id"] == "doc_a"
    assert run.config_snapshot["eval_code_version"]


def test_run_results_are_persisted_per_item(db):
    project = _make_project(db, "integration-results")
    db.add(Document(project_id=project.id, doc_id="doc_a", text="Bees waggle.", fingerprint="f"))
    db.commit()
    dataset = Dataset(project_id=project.id, name="bench2", version="1.0")
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    db.add(
        DatasetItem(
            dataset_id=dataset.id, question="Q?", reference_answer="A", relevant_doc_ids=["doc_a"], answerable=True
        )
    )
    db.commit()
    app = RagApp(
        project_id=project.id,
        name="rag2",
        version_label="v1",
        config={"retriever": "bm25", "chunk_chars": 200, "top_k": 3},
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    run = EvaluationRun(app_id=app.id, dataset_id=dataset.id, mode="end_to_end", status="queued")
    db.add(run)
    db.commit()
    db.refresh(run)
    execute_run(db, run.id)
    from app.models import RunResult

    results = db.query(RunResult).filter_by(run_id=run.id).all()
    assert len(results) == 1
    assert results[0].evidence
    assert "recall_at_5" in results[0].evidence


def test_score_item_reports_missing_evidence():
    item = DatasetItem(question="Q?", reference_answer="", relevant_doc_ids=[], answerable=True)
    values, evidence = score_item(item, {"answer": "A", "retrieved": [], "citations": []}, {}, [], "end_to_end")
    assert values["token_f1"] is None
    assert "missing_reason" in evidence["token_f1"]
    assert values["recall_at_5"] is None


def test_score_item_with_empty_retrieval():
    item = DatasetItem(question="Q?", reference_answer="A", relevant_doc_ids=["d"], answerable=True)
    values, _ = score_item(item, {"answer": "", "retrieved": [], "citations": []}, {}, ["d"], "end_to_end")
    assert values["empty_retrieval"] == 1.0
    assert values["recall_at_5"] == 0.0


def test_generation_only_mode_bypasses_retrieval():
    ctx = MetricContext(mode="generation_only")
    from app.metrics import all_metrics

    assert all_metrics()["recall_at_5"].compute(ctx).value is None
