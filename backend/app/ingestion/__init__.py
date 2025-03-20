"""Ingestion: safe parsing of documents and benchmark datasets."""

from __future__ import annotations

from .parsers import (
    DATA_SUFFIXES,
    TEXT_SUFFIXES,
    IngestionError,
    parse_dataset_file,
    parse_document,
    read_upload,
)

__all__ = [
    "DATA_SUFFIXES",
    "TEXT_SUFFIXES",
    "IngestionError",
    "parse_dataset_file",
    "parse_document",
    "read_upload",
]
