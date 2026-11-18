from agriprice.config import SPEC
from agriprice.pipeline import run
from agriprice.store import Store

def test_pipeline_returns_a_status():
    con = Store().connect()
    Store(con).reset()
    try:
        result = run(con=con)
    finally:
        con.close()
    assert isinstance(result, dict)
    assert result.get("engine") == SPEC.engine
    assert result


def test_rerun_is_idempotent_and_results_are_traceable():
    con = Store().connect()
    st = Store(con)
    st.reset()
    try:
        first = run(con=con)
        second = run(con=con)
        assert second["count"] == first["count"]
        assert second["ingested"] == 0
        assert second["updated"] == 0
        records = st.all_records()
        assert records
        for rec in records:
            assert "value_norm" in rec
            assert "value_raw" in rec
            assert "rule" in rec
            assert rec["quality"] in ("ok", "zero", "negative",
                                      "extreme", "missing", "invalid")
    finally:
        st.reset()
        con.close()


def test_full_and_incremental_runs_agree():
    con = Store().connect()
    st = Store(con)
    st.reset()
    try:
        full = run(mode="full", con=con)
        inc = run(mode="incremental", con=con)
        assert inc["count"] == full["count"]
        assert inc["ingested"] == 0
        assert st.count() == full["count"]
    finally:
        st.reset()
        con.close()


def test_incremental_ingests_out_of_order_backfill():
    import mockapp.main as mock_main
    con = Store().connect()
    st = Store(con)
    st.reset()
    late = {"id": "AGR-LATE", "name": "Late Lot", "value": 10,
            "status": "active", "ts": "2029-12-01T00:00:00Z", "unit": "ton"}
    try:
        first = run(mode="full", con=con)
        assert late["ts"] < first["watermark"]
        mock_main._extra.append(late)
        try:
            second = run(mode="incremental", con=con)
        finally:
            mock_main._extra.remove(late)
        assert second["ingested"] == 1
        assert second["count"] == first["count"] + 1
    finally:
        st.reset()
        con.close()


def test_interrupted_run_leaves_no_progress_and_recovers(monkeypatch):
    from agriprice import framework
    con = Store().connect()
    st = Store(con)
    st.reset()
    try:
        def boom(http):
            raise RuntimeError("page fetch interrupted")
        monkeypatch.setattr(framework, "fetch_all", boom)
        try:
            run(con=con)
            raise AssertionError("expected the run to fail")
        except RuntimeError:
            pass
        # A failed run must not mark collection progress as completed.
        assert st.count() == 0
        assert st.watermark() is None
        monkeypatch.undo()
        recovered = run(con=con)
        assert recovered["count"] > 0
        again = run(con=con)
        assert again["count"] == recovered["count"]
    finally:
        st.reset()
        con.close()
