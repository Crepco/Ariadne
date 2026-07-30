"""Offline tests for the shared hop-by-hop walk.

``ariadne.verify.verify_walk`` is the one implementation behind both the agent's
``verify_path`` tool and the scorer, so these tests cover the rules once and
:func:`as_tool_result` covers how the agent is told to fix a rejected path.
"""

from __future__ import annotations

from ariadne.verify import as_tool_result, verify_walk

# A -[edge]-> B -[inferred roast]-> SVC -[edge]-> DA
_EDGES = {("A", "B"): "GenericAll", ("SVC", "DA"): "MemberOf"}
_PROPS = {"B": {"roastable_target": "SVC"}}


def _hop_kind(a, b):
    if (a, b) in _EDGES:
        return ("edge", _EDGES[(a, b)])
    if (_PROPS.get(a) or {}).get("roastable_target") == b:
        return ("inferred", "Kerberoast")
    return None


def _walk(tokens, resolved, **kw):
    return verify_walk(tokens, resolved, hop_kind=_hop_kind, goal_oid="DA", **kw)


def test_valid_mixed_edge_and_inferred_path():
    r = _walk(["A", "B", "SVC", "DOMAIN ADMINS"], ["A", "B", "SVC", "DA"])
    assert r["valid"] is True
    assert r["hallucinated"] is False
    assert r["derived_steps"] == 1 and r["uses_derived"] is True
    assert r["hops"] == 3
    assert r["first_bad_hop"] is None


def test_skipped_node_is_rejected_and_names_the_first_bad_hop():
    # The classic failure: jumping from the host straight past the roasted account.
    r = _walk(["A", "B", "DOMAIN ADMINS"], ["A", "B", "DA"])
    assert r["valid"] is False
    assert r["hallucinated"] is True
    assert r["first_bad_hop"] == 1

    out = as_tool_result(r)
    assert out["valid"] is False
    assert "B -> DOMAIN ADMINS" in out["reason"]
    assert "skipped a node" in out["reason"]


def test_path_not_reaching_the_goal_is_rejected_without_being_a_hallucination():
    # Every hop is real; it just stops short. That's an incomplete answer, not a
    # fabricated one.
    r = _walk(["A", "B"], ["A", "B"])
    assert r["valid"] is False
    assert r["reaches_goal"] is False
    assert r["hallucinated"] is False
    assert "must be DOMAIN ADMINS" in as_tool_result(r)["reason"]


def test_unknown_node_is_a_hallucination():
    r = _walk(["A", "GHOST", "DOMAIN ADMINS"], ["A", None, "DA"])
    assert r["hallucinated"] is True
    assert r["unresolved"] == ["GHOST"]
    assert "do not exist in the graph" in as_tool_result(r)["reason"]


def test_ambiguous_name_is_rejected_but_is_not_a_hallucination():
    # The node exists — the agent just didn't say which one. Counting that as a
    # fabricated edge would overstate the hallucination rate.
    r = _walk(["A", "SVC01", "DOMAIN ADMINS"], ["A", None, "DA"],
              unknown=[], ambiguous=["SVC01 is ambiguous — it could be X, Y."])
    assert r["valid"] is False
    assert r["hallucinated"] is False
    assert "ambiguous" in as_tool_result(r)["reason"]


def test_expected_start_is_reported_separately_from_validity():
    r = _walk(["B", "SVC", "DOMAIN ADMINS"], ["B", "SVC", "DA"], expected_start_oid="A")
    assert r["valid"] is True        # the path itself is real …
    assert r["starts_ok"] is False   # … but it didn't start where we asked


def test_tool_result_lists_each_hop_with_its_step_label():
    out = as_tool_result(_walk(["A", "B", "SVC", "DOMAIN ADMINS"], ["A", "B", "SVC", "DA"]))
    assert [h["step"] for h in out["hops"]] == ["GenericAll", "Kerberoast", "MemberOf"]
    assert all(h["valid"] for h in out["hops"])
    assert out["derived_steps"] == 1
