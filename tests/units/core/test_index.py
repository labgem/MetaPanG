from pathlib import Path

import pytest

from metapang.core.index.index import IndexBuildConfig, IndexBuilder, IndexInfo


@pytest.fixture(scope="module")
def index_configuration(tmp_path_factory):
    index_directory = tmp_path_factory.mktemp("metapang_test_index")

    ibc = IndexBuildConfig(
        kmer_size=25, scaled=1000, n=0, pangenomes=[], output=index_directory
    )
    return ibc


@pytest.fixture(scope="module")
def index(index_configuration):
    b = IndexBuilder(index_configuration)
    b.construct(nb_cores=1, with_log=False)
    return index_configuration


def test_IndexInfo(tmp_path):
    pangenomes = {
        "pangenome1": [
            "genome11.fa",
            "genome12.fa",
            "genome13.fa",
            "genome14.fa",
        ],
        "pangenome2": [
            "genome21.fa",
            "genome22.fa",
            "genome23.fa",
            "genome24.fa",
        ],
    }

    info = IndexInfo(
        genome_index="genome_fake_name",
        pangenome_index="pangenome_fake_name",
        kmer_size=31,
        scaled=1000,
        n=0,
        pangenomes=pangenomes,
    )

    info_path = tmp_path / "index_info.json"

    info.save_json(info_path)

    loaded_info = IndexInfo.load_json(info_path)
    assert info.genome_index == loaded_info.genome_index
    assert info.pangenome_index == loaded_info.pangenome_index
    assert info.kmer_size == loaded_info.kmer_size
    assert info.scaled == loaded_info.scaled
    assert info.n == loaded_info.n
    assert info.pangenomes == loaded_info.pangenomes


def test_index_creation(index):
    assert Path(index.output / index.genome_index_name).exists()
    assert Path(index.output / index.pangenome_index_name).exists()
    assert Path(index.output / "index_info.json").exists()

    IndexInfo.load_json(index.output / "index_info.json")
