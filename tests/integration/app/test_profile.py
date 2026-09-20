import json
import shutil

import pytest
from click.testing import CliRunner

from metapang.app.metapang import metapang
from metapang.config import PanGBank_Config
from metapang.pg.api import PanGBank_API

READS = "reads.fastq.gz"
SPEC = "GTDB_refseq@2.0.0:s__Abiotrophia_defectiva"
SOURCE_GENOME = "GCF_013267415.1"


@pytest.fixture(scope="module")
def requirements(data_dir):
    if shutil.which("metagraph") is None:
        pytest.skip("metagraph binary not on PATH")
    if not (data_dir / READS).exists():
        pytest.skip(f"test reads '{READS}' not present in tests/data")
    try:
        PanGBank_API(PanGBank_Config(with_tty_log=False)).get_collections()
    except Exception as e:
        pytest.skip(f"PanGBank API not reachable: {e}")


def test_profile_full_run(requirements, data_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("METAPANG_PANGBANK_CACHE_DIRECTORY", str(tmp_path / "cache"))
    out = tmp_path / "out"
    species = SPEC.split(":")[1]

    result = CliRunner().invoke(
        metapang,
        ["profile", "-q", str(data_dir / READS), "-b", SPEC, "-o", str(out)],
    )

    assert result.exit_code == 0, result.output
    assert (out / f"{species}.strains.tsv").exists()
    assert (out / f"{species}.genes.tsv").exists()
    assert (out / "report.html").exists()
    assert (out / "run.toml").exists()

    profile = json.loads((out / f"{species}.profile.json").read_text())
    assert profile["candidate"] == species
    assert profile["k"] >= 1
    assert profile["reads_mapped"] / profile["reads_total"] > 0.8

    members = {m for c in profile["components"] for m in c["anchor_refs"]}
    assert SOURCE_GENOME in members
