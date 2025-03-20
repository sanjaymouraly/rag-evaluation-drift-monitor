"""RAG Quality Monitor backend.

Evaluate, compare, gate and monitor retrieval-augmented generation systems.
"""

from __future__ import annotations

__version__ = "1.1.0"
#: Version of the evaluation code, recorded in every run's config snapshot so a
#: result can always be traced back to the code that produced it.
EVAL_CODE_VERSION = "1.1.0"
