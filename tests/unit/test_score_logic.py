"""Offline tests for path parsing and hop-by-hop scoring.

Scoring normally reads Neo4j through a ``ScoringContext``; here we substitute a
tiny in-memory fake exposing the three members ``verify_path`` /
``score_agent_result`` actually use — ``resolve``, ``edge_between``,
``goal_oid`` — plus ``baseline`` for the top-level scorer.
"""

from __future__ import annotations

from types import SimpleNamespace

from ariadne.evaluation.score import (
    parse_path_tokens,
    score_agent_result,
    verify_path,
)


class FakeCtx:
    """In-memory stand-in for ScoringContext (no database)."""

    def __init__(self, edges, name_to_oid, goal_oid, reachable=True, hops=3):
        self._edges = dict(edges)            # (a_oid, b_oid) -> edge type
        self.name_to_oid = {k.upper(): v for k, v in name_to_oid.items()}
        self.oids = set(name_to_oid.values())
        self.goal_oid = goal_oid
        self._reachable = reachable
        self._hops = hops

    def resolve(self, token):
        t = (token or "").strip()
        if t in self.oids:
            return t
        return self.name_to_oid.get(t.upper())

    def edge_between(self, a, b):
        return self._edges.get((a, b))

    def baseline(self, start_oid):
        return {"reachable": self._reachable, "hops": self._hops}


def _abc_ctx(**kw):
    # A -> B -> DA, all real edges; DA is the goal.
    return FakeCtx(
        edges={("A", "B"): "ForceChangePassword", ("B", "DA"): "GenericAll"},
        name_to_oid={"A": "A", "B": "B", "DOMAIN ADMINS": "DA"},
        goal_oid="DA",
        **kw,
    )


# --- parse_path_tokens -----------------------------------------------------
def test_parse_prefers_path_field():
    assert parse_path_tokens("ignored", ["A", "B", "DOMAIN ADMINS"]) == ["A", "B", "DOMAIN ADMINS"]


def test_parse_drops_edge_type_tokens_from_text():
    answer = "A -> ForceChangePassword -> B -> GenericAll -> DOMAIN ADMINS"
    assert parse_path_tokens(answer) == ["A", "B", "DOMAIN ADMINS"]


def test_parse_no_path_text():
    assert parse_path_tokens("NO PATH FOUND") == ["NO PATH FOUND"]


# --- verify_path -----------------------------------------------------------
def test_verify_valid_path():
    v = verify_path(_abc_ctx(), ["A", "B", "DOMAIN ADMINS"], expected_start_oid="A")
    assert v["valid"] is True
    assert v["hallucinated"] is False
    assert v["reaches_goal"] is True
    assert v["hops"] == 2


def test_verify_flags_missing_edge_as_hallucination():
    v = verify_path(_abc_ctx(), ["A", "DOMAIN ADMINS"], expected_start_oid="A")
    assert v["valid"] is False
    assert v["hallucinated"] is True  # no direct A->DA edge


def test_verify_flags_unresolved_node():
    v = verify_path(_abc_ctx(), ["A", "GHOST", "DOMAIN ADMINS"], expected_start_oid="A")
    assert v["hallucinated"] is True
    assert v["unresolved"] == ["GHOST"]
    assert v["valid"] is False


# --- score_agent_result ----------------------------------------------------
def test_score_incomplete_run_is_not_hallucination():
    result = SimpleNamespace(answer="Maximum reasoning steps exceeded.", path_field=None, finished=False)
    score = score_agent_result(_abc_ctx(), result, "A")
    assert score["incomplete"] is True
    assert score["hallucinated_edge"] is False
    assert score["correct"] is False


def test_score_correct_valid_path_is_optimal_when_hops_match():
    result = SimpleNamespace(
        answer="A -> B -> DOMAIN ADMINS", path_field=["A", "B", "DOMAIN ADMINS"], finished=True
    )
    score = score_agent_result(_abc_ctx(reachable=True, hops=2), result, "A")
    assert score["correct"] is True
    assert score["path_valid"] is True
    assert score["optimal"] is True


def test_score_valid_but_longer_than_baseline_is_not_optimal():
    result = SimpleNamespace(
        answer="A -> B -> DOMAIN ADMINS", path_field=["A", "B", "DOMAIN ADMINS"], finished=True
    )
    score = score_agent_result(_abc_ctx(reachable=True, hops=1), result, "A")
    assert score["correct"] is True
    assert score["optimal"] is False


def test_score_no_path_correct_when_unreachable():
    result = SimpleNamespace(answer="NO PATH FOUND", path_field=[], finished=True)
    score = score_agent_result(_abc_ctx(reachable=False, hops=-1), result, "A")
    assert score["declared_no_path"] is True
    assert score["correct"] is True
    assert score["hallucinated_edge"] is False


def test_score_no_path_wrong_when_reachable():
    result = SimpleNamespace(answer="NO PATH FOUND", path_field=[], finished=True)
    score = score_agent_result(_abc_ctx(reachable=True, hops=3), result, "A")
    assert score["declared_no_path"] is True
    assert score["correct"] is False


def test_score_hallucinated_path_is_wrong():
    result = SimpleNamespace(
        answer="A -> DOMAIN ADMINS", path_field=["A", "DOMAIN ADMINS"], finished=True
    )
    score = score_agent_result(_abc_ctx(reachable=True, hops=2), result, "A")
    assert score["hallucinated_edge"] is True
    assert score["correct"] is False
