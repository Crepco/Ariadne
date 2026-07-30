"""Offline tests for name resolution — the invariant the project rests on.

``verify_path`` (what the agent calls before finishing) and the scorer (what
decides whether the run counted) must resolve a name to the SAME node. They used
to build that mapping separately, and disagreed whenever two nodes shared a short
name. These tests pin the shared behaviour down.
"""

from __future__ import annotations

from ariadne.resolve import Ambiguous, NameIndex, short_name


def _rows(*pairs):
    return [{"oid": oid, "name": name} for oid, name in pairs]


def test_short_name_splits_on_either_separator():
    # Users are USER@DOMAIN, computers are HOST.DOMAIN.
    assert short_name("USER0001@ARIADNE.LOCAL") == "USER0001"
    assert short_name("HOST01.ARIADNE.LOCAL") == "HOST01"
    assert short_name("") == ""
    assert short_name(None) == ""


def test_resolves_object_id_full_name_and_short_name():
    index = NameIndex.from_rows(_rows(("oid-1", "USER0001@CORP.LOCAL")))
    assert index.resolve("oid-1") == "oid-1"
    assert index.resolve("USER0001@CORP.LOCAL") == "oid-1"
    assert index.resolve("user0001") == "oid-1"          # case-insensitive short name
    assert index.resolve("  USER0001  ") == "oid-1"      # tolerates whitespace
    assert index.resolve("NOBODY") is None


def test_colliding_short_name_is_ambiguous_not_a_coin_flip():
    # A User SVC01@CORP.LOCAL and a Computer SVC01.CORP.LOCAL both shorten to
    # SVC01. Picking one silently is how the tool and the scorer used to end up
    # pointing at different nodes; the honest answer is "say which one".
    index = NameIndex.from_rows(_rows(
        ("oid-user", "SVC01@CORP.LOCAL"),
        ("oid-host", "SVC01.CORP.LOCAL"),
    ))

    oid, problem = index.resolution("SVC01")
    assert oid is None
    assert isinstance(problem, Ambiguous)
    assert "SVC01@CORP.LOCAL" in problem and "SVC01.CORP.LOCAL" in problem

    # The full names still resolve, so the agent has a way forward.
    assert index.resolve("SVC01@CORP.LOCAL") == "oid-user"
    assert index.resolve("SVC01.CORP.LOCAL") == "oid-host"


def test_ambiguous_short_name_is_absent_from_the_flat_mapping():
    # name_to_oid is what the chat/web layers read directly; an ambiguous short
    # name must not appear there with an arbitrary winner.
    index = NameIndex.from_rows(_rows(
        ("oid-user", "SVC01@CORP.LOCAL"),
        ("oid-host", "SVC01.CORP.LOCAL"),
    ))
    assert "SVC01" not in index.name_to_oid
    assert index.name_to_oid["SVC01@CORP.LOCAL"] == "oid-user"


def test_resolution_is_order_independent():
    # The historical bug: one builder kept the FIRST oid for a short name
    # (setdefault), the other kept the LAST (assignment). Feeding the same nodes
    # in either order must now give the same answer.
    forward = NameIndex.from_rows(_rows(("a", "SVC01@CORP.LOCAL"), ("b", "SVC01.CORP.LOCAL")))
    backward = NameIndex.from_rows(_rows(("b", "SVC01.CORP.LOCAL"), ("a", "SVC01@CORP.LOCAL")))
    assert forward.resolve("SVC01") == backward.resolve("SVC01") is None
    assert forward.name_to_oid == backward.name_to_oid


def test_goal_is_detected_from_the_domain_admins_name():
    index = NameIndex.from_rows(_rows(
        ("oid-da", "DOMAIN ADMINS@CORP.LOCAL"),
        ("oid-u", "USER0001@CORP.LOCAL"),
    ))
    assert index.goal_oid == "oid-da"


def test_resolve_all_separates_unknown_from_ambiguous():
    index = NameIndex.from_rows(_rows(
        ("a", "SVC01@CORP.LOCAL"),
        ("b", "SVC01.CORP.LOCAL"),
        ("c", "USER0001@CORP.LOCAL"),
    ))
    oids, unknown, ambiguous = index.resolve_all(["USER0001", "SVC01", "GHOST"])
    assert oids == ["c", None, None]
    assert unknown == ["GHOST"]
    assert len(ambiguous) == 1 and "SVC01" in ambiguous[0]
