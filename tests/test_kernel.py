import importlib

def test_transform_module_has_a_public_entrypoint():
    module = importlib.import_module("agriprice.kernel")
    assert callable(getattr(module, "process", None))
    result = module.process({"id": "sample", "name": "item", "value": 7, "status": "active", "ts": "t1"})
    assert isinstance(result, dict)


def test_same_quote_in_kg_and_ton_yields_one_amount():
    from agriprice import kernel
    per_kg = kernel.process({"id": "q1", "value": 4.5, "unit": "kg"})
    per_ton = kernel.process({"id": "q1", "value": 4500, "unit": "ton"})
    assert per_kg["value_norm"] == per_ton["value_norm"] == 4500.0
    assert per_kg["unit_norm"] == per_ton["unit_norm"] == "ton"


def test_quote_categories_are_distinguished():
    from agriprice import kernel
    assert kernel.process({"value": None})["quality"] == "missing"
    assert kernel.process({"value": ""})["quality"] == "missing"
    assert kernel.process({"value": 0})["quality"] == "zero"
    negative = kernel.process({"value": -3, "unit": "kg"})
    assert negative["quality"] == "negative"
    assert negative["value_norm"] == -3000.0
    sci = kernel.process({"value": "1.25e3", "unit": "ton"})
    assert sci["value_norm"] == 1250.0
    assert "scientific_notation" in sci["flags"]
    extreme = kernel.process({"value": 5e12, "unit": "ton"})
    assert extreme["quality"] == "extreme"
    assert extreme["value_norm"] == 5e12
    invalid = kernel.process({"value": "not-a-price"})
    assert invalid["quality"] == "invalid"
    assert invalid["value_norm"] is None


def test_extreme_quotes_are_not_rescaled():
    from agriprice import kernel
    result = kernel.process({"value": 2000000000, "unit": "ton"})
    assert result["value_norm"] == 2000000000.0


def test_result_carries_original_expression_and_rule():
    from agriprice import kernel
    result = kernel.process({"value": "4.5", "unit": "公斤"})
    assert result["value_raw"] == "4.5"
    assert result["unit_raw"] == "公斤"
    assert result["rule"] == kernel.RULE_VERSION
    assert result["scale_factor"] == 1000.0


def test_process_is_deterministic_regardless_of_arrival():
    from agriprice import kernel
    record = {"value": "4.5", "unit": "kg"}
    assert kernel.process(record) == kernel.process(dict(record))
