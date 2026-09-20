from metapang.utils.time import StepCollection, TimeFormatter


def test_format_time_seconds():
    assert TimeFormatter.format_time(1.5, "seconds", 2) == "1.50s"


def test_format_time_minutes():
    assert TimeFormatter.format_time(120.0, "minutes", 1) == "2.0m"


def test_format_time_auto_units():
    assert TimeFormatter.format_time(30.0).endswith("s")
    assert TimeFormatter.format_time(120.0).endswith("m")
    assert TimeFormatter.format_time(7200.0).endswith("h")


def test_format_custom():
    assert TimeFormatter.format_custom(3661.0, "%Hh%Mm%Ss") == "1h1m1s"
    assert TimeFormatter.format_custom(3661.0, "%%") == "%"


def test_step_collection_empty():
    assert StepCollection().get_last_step() is None


def test_step_collection_add_and_query():
    c = StepCollection()
    c.add_step("a", 1.0, 1.0, 100)
    c.add_step("b", 2.0, 1.0, 200)
    assert c.get_step_names() == ["a", "b"]
    assert c.get_last_step().name == "b"
    assert c.get_durations() == [1.0, 1.0]
    assert c.get_step("a").name == "a"


def test_step_collection_clear():
    c = StepCollection()
    c.add_step("a", 1.0, 1.0, 100)
    c.clear()
    assert c.get_last_step() is None
