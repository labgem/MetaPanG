import shutil

import pytest

from metapang.core.index.dbg import (
    MetagraphBuildPipeline,
    MetagraphBuildPipelineOptions,
    MetagraphCLI,
    MetagraphQueryOptions,
)


@pytest.fixture(scope="module")
def cli():
    if shutil.which("metagraph") is None:
        pytest.skip("metagraph binary not on PATH")
    return MetagraphCLI()


def test_version(cli):
    version = cli.version()
    assert isinstance(version, str)
    assert version


@pytest.fixture(scope="module")
def built_dbg(cli, tmp_path_factory, data_dir):
    out = tmp_path_factory.mktemp("dbg_out")
    tmp = tmp_path_factory.mktemp("dbg_tmp")
    genome = str(data_dir / "genome11.fa")
    options = MetagraphBuildPipelineOptions(
        inputs=[genome],
        annotation_inputs=[genome],
        name="testpan",
        tmp_dir=str(tmp),
        output_dir=str(out),
        kmer_size=21,
        parallel=1,
        annotation_type="rd_brwt",
    )
    MetagraphBuildPipeline(cli, options).run(move_graph=True)
    return out


def test_construction_creates_files(built_dbg):
    assert (built_dbg / "testpan.dbg").exists()
    assert (built_dbg / "testpan.row_diff_brwt.annodbg").exists()


def test_query_matches(cli, built_dbg, data_dir, tmp_path):
    result = tmp_path / "result.tsv"
    options = MetagraphQueryOptions(
        output_file=str(result),
        i=str(built_dbg / "testpan.dbg"),
        a=str(built_dbg / "testpan.row_diff_brwt.annodbg"),
        query_file=str(data_dir / "genome11.fa"),
        query_mode="matches",
    )
    cli.query(options)
    assert result.exists()
    assert result.read_text().strip()
