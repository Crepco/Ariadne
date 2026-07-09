"""Configuration loaded from the repo-root ``.env`` file.

Every component (generator, tools, agent, scoring) gets its Neo4j credentials
from here so there is a single source of truth. Copy ``.env.example`` to ``.env``
and fill it in — ``.env`` is git-ignored.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load the repo-root .env explicitly (works regardless of current working dir),
# then fall back to the default search so real environment variables still win.
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")
load_dotenv()


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    user: str
    password: str
    database: str = "neo4j"


def load_neo4j_config() -> Neo4jConfig:
    """Read Neo4j connection settings from the environment.

    Raises a clear error if the URI or password is missing, since that is the
    most common first-run mistake (forgetting to fill in ``.env``).
    """
    uri = os.environ.get("NEO4J_URI", "").strip()
    user = os.environ.get("NEO4J_USER", "neo4j").strip()
    password = os.environ.get("NEO4J_PASSWORD", "").strip()
    database = os.environ.get("NEO4J_DATABASE", "neo4j").strip() or "neo4j"

    missing = [
        name
        for name, value in (("NEO4J_URI", uri), ("NEO4J_PASSWORD", password))
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing Neo4j settings: "
            + ", ".join(missing)
            + f".\nCopy .env.example to .env (at {_REPO_ROOT}) and fill in your "
            "Aura connection URI and password."
        )
    return Neo4jConfig(uri=uri, user=user, password=password, database=database)


# Default domain for generated graphs; override with DOMAIN in .env if desired.
DEFAULT_DOMAIN = os.environ.get("DOMAIN", "ARIADNE.LOCAL").strip().upper()
