from agriprice.store import Store

def test_store_identity_and_checkpoint():
    con = Store().connect()
    st = Store(con)
    st.reset()
    try:
        record = {"id": "sample", "ts": "t1", "v": 1}
        assert st.upsert(record) is True
        assert st.upsert(record) is False
        st.set_watermark("checkpoint")
        assert st.watermark() == "checkpoint"
    finally:
        st.reset()
        con.close()


def test_stored_results_are_not_rewritten_without_cause():
    con = Store().connect()
    st = Store(con)
    st.reset()
    try:
        source = {"id": "q1", "ts": "t1", "value": 5, "unit": "kg"}
        enriched = dict(source, value_norm=5000.0, rule="quote-norm-v1")
        assert st.upsert(enriched, identity=source) is True
        key = st.hash(source)

        # Identical re-delivery is ignored.
        assert st.upsert(enriched, identity=source) is False
        assert st.count() == 1

        # A new rule label alone is not a cause to rewrite the old result.
        relabelled = dict(enriched, rule="quote-norm-v2")
        assert st.upsert(relabelled, identity=source) is False
        assert st.get(key)["rule"] == "quote-norm-v1"

        # A rule change that alters the outcome is a cause: the row is
        # rewritten and carries the new processing basis.
        changed = dict(enriched, value_norm=5001.0, rule="quote-norm-v2")
        assert st.upsert(changed, identity=source) is True
        stored = st.get(key)
        assert stored["value_norm"] == 5001.0
        assert stored["rule"] == "quote-norm-v2"
        assert st.count() == 1
    finally:
        st.reset()
        con.close()
