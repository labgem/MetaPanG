from metapang.app.issue import _hide_run_toml, _parse_toml, _scrub


def test_parse_toml_ok():
    assert _parse_toml("a = 1\n") == {"a": 1}


def test_parse_toml_invalid():
    assert _parse_toml("not = = toml") is None


def test_hide_run_toml_hides_private_fields():
    data = {
        "sample": "S1",
        "output": "OUT",
        "query": ["a.fastq", "b.fastq"],
        "metagraph_path": "/custom/metagraph_DNA",
        "k_max": 12,
    }
    out = _hide_run_toml(data)
    assert "<sample>" in out
    assert "<output>" in out
    assert "<query file>" in out
    assert "<custom>" in out
    assert "S1" not in out
    assert "a.fastq" not in out
    assert "/custom/metagraph_DNA" not in out
    assert "k_max = 12" in out


def test_hide_run_toml_keeps_default_metagraph():
    out = _hide_run_toml({"metagraph_path": "metagraph"})
    assert 'metagraph_path = "metagraph"' in out


def test_scrub_replaces_run_values():
    data = {"sample": "S1", "output": "OUT", "query": ["data/x.fastq"]}
    text = "run S1 wrote to OUT reading data/x.fastq"
    scrubbed = _scrub(text, data)
    assert "S1" not in scrubbed
    assert "OUT" not in scrubbed
    assert "data/x.fastq" not in scrubbed
    assert "<sample>" in scrubbed
    assert "<output>" in scrubbed
    assert "<query file>" in scrubbed
