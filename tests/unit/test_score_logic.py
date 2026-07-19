"""Offline tests for path parsing and hop-by-hop scoring.

Scoring normally reads Neo4j through a ``ScoringContext``; here we substitute a
tiny in-memory fake exposing the three members ``verify_path`` /
``score_agent_result`` actually use — ``resolve``, ``edge_between``,
``goal_oid`` — plus ``baseline`` for the top-level scorer.
"""

from __future__ import annotations

from types import SimpleNamespace

from ariadne.inference import justifies_hop
from ariadne.evaluation.score import (
    parse_path_tokens,
    score_agent_result,
    verify_path,
)


class FakeCtx:
    """In-memory stand-in for ScoringContext (no database).

    A hop is a real canonical ``edge`` if it's in ``edges``, an ``inferred`` step
    if a property rule justifies it (via ``props``), else None (hallucination) —
    mirroring the real ``hop_kind``. ``bloodhound`` reachability defaults to mirror
    ``baseline`` unless overridden, so tests can model the "advanced-only" case
    where a true path exists but the canonical query can't find it.
    """

    def __init__(self, edges, name_to_oid, goal_oid, reachable=True, hops=3,
                 bh_reachable=None, bh_hops=None, props=None):
        self._edges = dict(edges)            # (a_oid, b_oid) -> canonical edge type
        self.name_to_oid = {k.upper(): v for k, v in name_to_oid.items()}
        self.oids = set(name_to_oid.values())
        self.goal_oid = goal_oid
        self.props = props or {}
        self._reachable = reachable
        self._hops = hops
        self._bh_reachable = reachable if bh_reachable is None else bh_reachable
        self._bh_hops = hops if bh_hops is None else bh_hops

    def resolve(self, token):
        t = (token or "").strip()
        if t in self.oids:
            return t
        return self.name_to_oid.get(t.upper())

    def hop_kind(self, a, b):
        t = self._edges.get((a, b))
        if t is not None:
            return ("edge", t)
        rule = justifies_hop(self.props, a, b, self.goal_oid)
        return ("inferred", rule) if rule else None

    def baseline(self, start_oid):
        return {"reachable": self._reachable, "hops": self._hops}

    def bloodhound(self, start_oid):
        return {"reachable": self._bh_reachable, "hops": self._bh_hops}


def _abc_ctx(**kw):
    # A -> B -> DA, all real canonical edges; DA is the goal.
    return FakeCtx(
        edges={("A", "B"): "ForceChangePassword", ("B", "DA"): "GenericAll"},
        name_to_oid={"A": "A", "B": "B", "DOMAIN ADMINS": "DA"},
        goal_oid="DA",
        **kw,
    )


def _inferred_ctx(**kw):
    # A -[roast, INFERRED]-> SVC -[GenericAll edge]-> DA. Only the last hop is a
    # real edge; the first is a property-justified inferred step.
    return FakeCtx(
        edges={("SVC", "DA"): "GenericAll"},
        name_to_oid={"A": "A", "SVC": "SVC", "DOMAIN ADMINS": "DA"},
        goal_oid="DA",
        props={"A": {"roastable_target": "SVC"}},
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


def test_score_beats_bloodhound_when_path_uses_inferred_step():
    # Path uses an inferred (non-edge) roast step, and the canonical query finds
    # nothing — the agent's real path beats the rule-based baseline.
    result = SimpleNamespace(
        answer="A -> SVC -> DOMAIN ADMINS", path_field=["A", "SVC", "DOMAIN ADMINS"], finished=True
    )
    ctx = _inferred_ctx(reachable=True, hops=2, bh_reachable=False, bh_hops=-1)
    score = score_agent_result(ctx, result, "A")
    assert score["correct"] is True
    assert score["path_valid"] is True
    assert score["derived_steps"] == 1
    assert score["bloodhound_reachable"] is False
    assert score["beats_bloodhound"] is True


def test_score_all_canonical_path_does_not_beat_bloodhound():
    # A fully-canonical valid path uses no inferred step, so it never "beats"
    # BloodHound even if we (contrived) claim the canonical query missed it.
    result = SimpleNamespace(
        answer="A -> B -> DOMAIN ADMINS", path_field=["A", "B", "DOMAIN ADMINS"], finished=True
    )
    ctx = _abc_ctx(reachable=True, hops=2, bh_reachable=False, bh_hops=-1)
    score = score_agent_result(ctx, result, "A")
    assert score["derived_steps"] == 0
    assert score["beats_bloodhound"] is False


def test_score_no_beat_credit_for_hallucinated_path():
    # A fabricated path must never count as beating BloodHound.
    result = SimpleNamespace(
        answer="A -> DOMAIN ADMINS", path_field=["A", "DOMAIN ADMINS"], finished=True
    )
    ctx = _inferred_ctx(reachable=True, hops=2, bh_reachable=False, bh_hops=-1)
    score = score_agent_result(ctx, result, "A")
    assert score["path_valid"] is False
    assert score["beats_bloodhound"] is False


def test_verify_accepts_inferred_hop():
    v = verify_path(_inferred_ctx(), ["A", "SVC", "DOMAIN ADMINS"], expected_start_oid="A")
    assert v["valid"] is True
    assert v["hallucinated"] is False
    assert v["derived_steps"] == 1
    assert v["uses_derived"] is True
