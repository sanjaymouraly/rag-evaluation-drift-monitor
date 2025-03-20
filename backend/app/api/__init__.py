"""API routers."""

from __future__ import annotations

from . import datasets, drift, gates, projects, providers, reports, runs, system

ROUTERS = [
    projects.router,
    datasets.router,
    runs.router,
    gates.router,
    drift.router,
    providers.router,
    reports.router,
    system.router,
]

__all__ = ["ROUTERS"]
