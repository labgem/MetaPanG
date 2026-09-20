import pytest

from metapang.core.index.index import IndexBuildConfig, IndexBuilder
from metapang.core.index.search import IndexSearch, IndexType, SearchMode


@pytest.fixture(scope="module")
def built_index(tmp_path_factory, data_dir):
    out = tmp_path_factory.mktemp("index")
    config = IndexBuildConfig(
        kmer_size=21,
        scaled=100,
        n=0,
        pangenomes=[
            ("pangenome1", [data_dir / f"genome1{i}.fa" for i in range(1, 5)]),
            ("pangenome2", [data_dir / f"genome2{i}.fa" for i in range(1, 5)]),
        ],
        output=out,
    )
    IndexBuilder(config).construct(nb_cores=1, with_log=False)
    return out


def test_index_files_created(built_index):
    assert (built_index / "genome_index.sbt.zip").exists()
    assert (built_index / "pangenome_index.sbt.zip").exists()
    assert (built_index / "index_info.json").exists()


def test_search_genome_self_match(built_index, data_dir):
    search = IndexSearch(built_index, to_load=IndexType.genome)
    results = search.search_genome(
        "q", data_dir / "genome11.fa", IndexType.genome, SearchMode.containment, 0.0
    )
    assert any("genome11" in r.name for r in results)


def test_search_pangenome_match(built_index, data_dir):
    search = IndexSearch(built_index, to_load=IndexType.pangenome)
    results = search.search_genome(
        "q", data_dir / "genome11.fa", IndexType.pangenome, SearchMode.containment, 0.0
    )
    assert "pangenome1" in [r.name for r in results]


def test_search_self_match_score(built_index, data_dir):
    search = IndexSearch(built_index, to_load=IndexType.genome)
    results = search.search_genome(
        "q", data_dir / "genome11.fa", IndexType.genome, SearchMode.containment, 0.0
    )
    self_hits = [r for r in results if "genome11" in r.name]
    assert self_hits
    assert self_hits[0].score == pytest.approx(1.0, abs=0.01)
