"""Scheduled evaluations.

A small, dependency-free scheduler: every tick it looks for jobs whose
``next_run_at`` has passed, starts an evaluation run and (optionally)
evaluates a release gate against the previous run. Jobs are idempotent per
tick, so a restart does not run the same job twice in the same minute.
"""

from __future__ import annotations

import datetime as dt
import threading

from .config import settings
from .db import SessionLocal
from .models import EvaluationRun, ScheduledJob


def _naive_utc(value: dt.datetime | None) -> dt.datetime | None:
    """Normalise a datetime for comparison.

    SQLite stores timezone-aware columns as naive values, so comparisons must
    be made on a consistently normalised value.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(dt.UTC).replace(tzinfo=None)


class Scheduler:
    def __init__(self, interval_s: int | None = None):
        self.interval_s = interval_s or settings.scheduler_tick_s
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.last_tick: str | None = None
        self.ticks = 0

    # -- lifecycle ------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="rqm-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:  # noqa: BLE001 - a failing job must not kill the scheduler
                pass
            self._stop.wait(self.interval_s)

    # -- work -----------------------------------------------------------
    def tick(self, now: dt.datetime | None = None) -> list[dict]:
        """Run every job that is due. Returns a list of executed job summaries."""
        now = now or dt.datetime.now(dt.UTC)
        self.ticks += 1
        self.last_tick = now.isoformat()
        executed: list[dict] = []
        db = SessionLocal()
        try:
            jobs = db.query(ScheduledJob).filter_by(enabled=True).all()
            reference = _naive_utc(now)
            for job in jobs:
                due_at = _naive_utc(job.next_run_at)
                due = due_at is None or due_at <= reference
                if not due:
                    continue
                summary = self._run_job(db, job, now)
                executed.append(summary)
            db.commit()
        finally:
            db.close()
        return executed

    def _run_job(self, db, job: ScheduledJob, now: dt.datetime) -> dict:
        from .evaluation import execute_run
        from .gates import RunView, evaluate_gate
        from .models import GateEvaluation, GatePolicy, RunResult

        previous_run_id = job.last_run_id
        run = EvaluationRun(
            app_id=job.app_id,
            dataset_id=job.dataset_id,
            mode=job.mode,
            status="queued",
            idempotency_key=f"sched-{job.id}-{now.isoformat()}",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        execute_run(db, run.id)
        job.last_run_at = now
        job.last_run_id = run.id
        job.next_run_at = now + dt.timedelta(minutes=max(1, int(job.interval_minutes or 60)))
        db.commit()

        verdict = None
        if job.policy_id and previous_run_id:
            policy = db.get(GatePolicy, job.policy_id)
            if policy is not None:
                baseline = db.get(EvaluationRun, previous_run_id)
                if baseline is not None and baseline.status == "completed":

                    def _view(target_run) -> RunView:
                        rows = db.query(RunResult).filter_by(run_id=target_run.id).all()
                        return RunView(
                            run_id=target_run.id,
                            metrics=target_run.metrics or {},
                            results=[
                                {
                                    "item_id": r.item_id,
                                    "question": r.question,
                                    "category": r.category,
                                    "cohorts": r.cohorts or [],
                                    "metrics": r.metrics or {},
                                }
                                for r in rows
                            ],
                            label=target_run.id,
                        )

                    result = evaluate_gate(policy.rules, policy.min_samples, _view(run), _view(baseline))
                    evaluation = GateEvaluation(
                        policy_id=policy.id,
                        candidate_run_id=run.id,
                        baseline_run_id=previous_run_id,
                        verdict=result["verdict"],
                        checks=result["checks"],
                        summary=result["summary"],
                    )
                    db.add(evaluation)
                    db.commit()
                    verdict = result["verdict"]
        return {"job_id": job.id, "job": job.name, "run_id": run.id, "status": run.status, "gate_verdict": verdict}


scheduler = Scheduler()
