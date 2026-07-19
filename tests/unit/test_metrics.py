"""Offline tests for metrics aggregation (reads a temp CSV, no database)."""

from __future__ import annotations

from ariadne.evaluation import metrics

_HEADER = (
    "graph_size,correct,path_valid,hallucinated_edge,baseline_reachable,"
    "incomplete,optimal,tool_calls,time_seconds,error\n"
)


def _write_csv(tmp_path, body):
    p = tmp_path / "results.csv"
    p.write_text(_HEADER + body, encoding="utf-8")
    return p


def test_load_results_coerces_types(tmp_path):
    p = _write_csv(tmp_path, "210,True,True,False,True,False,True,4,10.0,\n")
    df = metrics.load_results(p)
    assert df is not None and len(df) == 1
    assert df["correct"].dtype == bool
    assert df["tool_calls"].iloc[0] == 4


def test_valid_runs_drops_infrastructure_errors(tmp_path):
    body = (
        "210,True,True,False,True,False,True,4,10.0,\n"
        "210,False,False,False,True,True,False,12,30.0,\n"
        "210,,,,,,,,,OpenRouter HTTP 402 out of credit\n"
    )
    df = metrics.load_results(_write_csv(tmp_path, body))
    valid = metrics.valid_runs(df)
    assert len(df) == 3
    assert len(valid) == 2  # the error row is excluded


def test_overall_optimal_denominator_is_paths_found(tmp_path):
    # 1 valid path found (optimal), 1 correct no-path (optimal=False),
    # 1 incomplete. "optimal_of_found" must divide by paths FOUND (1), not by
    # all correct runs (2), i.e. 1.0 not 0.5.
    body = (
        "210,True,True,False,True,False,True,4,10.0,\n"
        "210,True,False,False,False,False,False,6,12.0,\n"
        "210,False,False,False,True,True,False,12,30.0,\n"
    )
    df = metrics.valid_runs(metrics.load_results(_write_csv(tmp_path, body)))
    o = metrics._overall(df)
    assert o["runs"] == 3
    assert o["found"] == 1
    assert o["optimal_of_found"] == 1.0
    assert o["incomplete"] == 1


def test_by_size_groups_and_sorts(tmp_path):
    body = (
        "409,True,True,False,True,False,True,4,10.0,\n"
        "210,False,False,False,True,True,False,12,30.0,\n"
        "210,True,True,False,True,False,True,5,11.0,\n"
    )
    df = metrics.valid_runs(metrics.load_results(_write_csv(tmp_path, body)))
    by = metrics._by_size(df)
    assert list(by["graph_size"]) == [210, 409]
    assert by[by["graph_size"] == 210]["runs"].iloc[0] == 2


def test_old_csv_missing_new_columns_still_aggregates(tmp_path):
    # An old-format log (no bloodhound/token columns) must load and aggregate
    # without KeyError — missing columns are filled with defaults. beats_bloodhound
    # is a stored column (defaults False -> 0); a full markdown render must work too.
    p = _write_csv(tmp_path, "210,True,True,False,True,False,True,4,10.0,\n")
    df = metrics.valid_runs(metrics.load_results(p))
    o = metrics._overall(df)
    assert o["beats_bloodhound"] == 0
    assert "advanced_required" in o           # computed field present, no KeyError
    assert isinstance(metrics.metrics_markdown(p), str)


_BH_HEADER = (
    "graph_size,correct,path_valid,hallucinated_edge,incomplete,declared_no_path,"
    "baseline_reachable,bloodhound_reachable,beats_bloodhound,optimal,tool_calls,time_seconds,error\n"
)


def test_overall_counts_beats_bloodhound_and_advanced_required(tmp_path):
    body = (
        # advanced-only solve: truly reachable, canonical-blind, agent found it
        "210,True,True,False,False,False,True,False,True,True,5,10.0,\n"
        # ordinary solve: canonical also reaches, no beat
        "210,True,True,False,False,False,True,True,False,True,4,9.0,\n"
    )
    p = tmp_path / "r.csv"
    p.write_text(_BH_HEADER + body, encoding="utf-8")
    df = metrics.valid_runs(metrics.load_results(p))
    o = metrics._overall(df)
    assert o["beats_bloodhound"] == 1
    assert o["advanced_required"] == 1  # baseline_reachable & not bloodhound_reachable


def test_classify_assigns_one_bucket_per_run(tmp_path):
    body = (
        "210,True,True,False,False,False,True,True,False,True,4,9,\n"     # correct
        "210,False,False,True,False,False,True,True,False,False,6,12,\n"  # hallucinated
        "210,False,False,False,False,True,True,True,False,False,7,15,\n"  # false_no_path
        "210,False,False,False,True,False,True,True,False,False,12,30,\n" # incomplete
        "210,False,False,False,False,False,True,True,False,False,5,11,\n" # wrong_path
    )
    p = tmp_path / "r.csv"
    p.write_text(_BH_HEADER + body, encoding="utf-8")
    df = metrics.valid_runs(metrics.load_results(p))
    assert metrics.classify(df).tolist() == [
        "correct", "hallucinated", "false_no_path", "incomplete", "wrong_path",
    ]
    fm = metrics._failure_modes(df)
    assert int(fm.loc[210, "correct"]) == 1
    assert int(fm.loc[210, "wrong_path"]) == 1
