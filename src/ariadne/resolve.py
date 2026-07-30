"""Name -> object id resolution. The single source of truth.

A path token the agent proposes is either an object id (``S-1-5-21-…-1234``) or a
node *name*, and names come in two shapes: the full one Neo4j stores
(``USER0001@ARIADNE.LOCAL``, ``HOST01.ARIADNE.LOCAL``) and the short leading label
(``USER0001``, ``HOST01``) an LLM naturally writes.

This module exists because that mapping used to be built **twice** — once in
``tools.verify_path`` and once in ``ScoringContext.load`` — with a one-word
difference: the tool kept the *first* oid for a short name (``setdefault``), the
scorer kept the *last* (assignment). When two nodes share a short name (a User
``SVC01@DOM`` and a Computer ``SVC01.DOM`` both shorten to ``SVC01``) the two
resolved to *different nodes*, silently breaking the invariant the project rests
on: *a path ``verify_path`` calls valid is the path that will score as correct.*

So there is now one :class:`NameIndex`, used by both, and an ambiguous short name
resolves to **nothing** in both — reported as ambiguous rather than guessed. A
guess that is right half the time is worse than an error message that tells the
agent to use the full name.
"""

from __future__ import annotations

import re
from collections import defaultdict

from ariadne.schema import GOAL_GROUP, INFERENCE_PROPERTIES

_SEPARATORS = re.compile(r"[@.]")


def short_name(name: str | None) -> str:
    """The leading label of a node name, upper-cased.

    ``USER0001@ARIADNE.LOCAL`` -> ``USER0001``; ``HOST01.ARIADNE.LOCAL`` -> ``HOST01``.
    """
    return _SEPARATORS.split(name or "")[0].upper()


class Ambiguous(str):
    """A short name that matches more than one node.

    Subclasses ``str`` (the rendered "did you mean" message) so a caller can
    report it directly, while ``isinstance(x, Ambiguous)`` distinguishes it from
    an unknown name.
    """


class NameIndex:
    """Maps path tokens (object ids or names) to object ids, and carries the
    inference properties + goal id the hop classifier needs.

    Build it with :meth:`add` per node then :meth:`finalize`, or in one shot with
    :meth:`from_rows`.
    """

    def __init__(self) -> None:
        self.oids: set[str] = set()
        self.names: dict[str, str] = {}                       # oid -> display name
        self.props: dict[str, dict] = {}                      # oid -> inference props
        self.goal_oid: str | None = None
        self._exact: dict[str, str] = {}                      # UPPER full name -> oid
        self._short: dict[str, set[str]] = defaultdict(set)   # UPPER short name -> oids
        self.name_to_oid: dict[str, str] = {}                 # flattened, unambiguous only

    # -- building ----------------------------------------------------------
    def add(self, oid: str | None, name: str | None, props: dict | None = None) -> None:
        if not oid:
            return
        self.oids.add(oid)
        self.props[oid] = props or {}
        if not name:
            return
        self.names[oid] = name
        self._exact[name.upper()] = oid
        self._short[short_name(name)].add(oid)
        if name.upper().startswith(GOAL_GROUP + "@"):
            self.goal_oid = oid

    def finalize(self) -> "NameIndex":
        """Flatten the lookups into ``name_to_oid`` (exact names, plus short names
        that are unambiguous). Callers that only need a plain dict use that;
        callers that want the ambiguity signal use :meth:`resolution`."""
        self.name_to_oid = dict(self._exact)
        for short, oids in self._short.items():
            if len(oids) == 1 and short not in self.name_to_oid:
                self.name_to_oid[short] = next(iter(oids))
        return self

    @classmethod
    def from_rows(cls, rows, prop_keys=INFERENCE_PROPERTIES) -> "NameIndex":
        """Build from query rows exposing ``oid``/``name`` plus the property columns."""
        index = cls()
        for row in rows:
            index.add(
                row.get("oid"),
                row.get("name"),
                {p: row.get(p) for p in prop_keys},
            )
        return index.finalize()

    # -- resolution --------------------------------------------------------
    def resolution(self, token: str | None) -> tuple[str | None, Ambiguous | None]:
        """Resolve one token to ``(oid, problem)``.

        ``problem`` is ``None`` on success, or an :class:`Ambiguous` message when
        a short name matches several nodes. An unknown token returns
        ``(None, None)`` — the caller reports it as unresolved.
        """
        t = (token or "").strip()
        if not t:
            return None, None
        if t in self.oids:
            return t, None
        upper = t.upper()
        if upper in self._exact:
            return self._exact[upper], None
        candidates = self._short.get(upper)
        if not candidates:
            return None, None
        if len(candidates) == 1:
            return next(iter(candidates)), None
        options = ", ".join(sorted(self.names.get(o, o) for o in candidates))
        return None, Ambiguous(f"{t} is ambiguous — it could be {options}. Use the full name.")

    def resolve(self, token: str | None) -> str | None:
        """The oid for a token, or None if unknown *or* ambiguous."""
        return self.resolution(token)[0]

    def resolve_all(self, tokens) -> tuple[list[str | None], list[str], list[str]]:
        """Resolve a whole path. Returns ``(oids, unknown, ambiguous_messages)``,
        where ``oids`` is aligned with ``tokens`` (None where unresolved)."""
        oids: list[str | None] = []
        unknown: list[str] = []
        ambiguous: list[str] = []
        for token in tokens:
            oid, problem = self.resolution(token)
            oids.append(oid)
            if oid is None:
                (ambiguous if problem is not None else unknown).append(
                    str(problem) if problem is not None else token
                )
        return oids, unknown, ambiguous
