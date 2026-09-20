from pathlib import Path

from metapang.core.index.index import (
    IndexBuilder,
    IndexInfo,
    make_pangenome_signature_name,
)

K, N, SCALED = 21, 0, 100


def test_index_info_roundtrip(tmp_path):
    pangenomes = {"pangenome1": ["genome11.fa"], "pangenome2": ["genome21.fa"]}
    info = IndexInfo(
        genome_index="g",
        pangenome_index="p",
        kmer_size=31,
        scaled=1000,
        n=0,
        pangenomes=pangenomes,
    )
    path = tmp_path / "index_info.json"
    info.save_json(path)
    loaded = IndexInfo.load_json(path)
    assert loaded.genome_index == "g"
    assert loaded.pangenome_index == "p"
    assert loaded.kmer_size == 31
    assert loaded.pangenomes == pangenomes


def test_sequence_minhash_params():
    mh = IndexBuilder.sequence_minhash("ACGTACGTACGT" * 20, K, N, SCALED)
    assert mh.ksize == K
    assert mh.scaled == SCALED


def test_file_minhash(data_dir):
    mh = IndexBuilder.file_minhash(data_dir / "genome11.fa", K, N, SCALED)
    assert len(mh) > 0


def test_file_minhash_deterministic(data_dir):
    a = IndexBuilder.file_minhash(data_dir / "genome11.fa", K, N, SCALED)
    b = IndexBuilder.file_minhash(data_dir / "genome11.fa", K, N, SCALED)
    assert a.hashes == b.hashes


def test_pangenome_signature(data_dir):
    genomes = [data_dir / "genome11.fa", data_dir / "genome12.fa"]
    pan_sig, gen_sigs = IndexBuilder.pangenome_signature("pan1", genomes, K, N, SCALED)
    assert pan_sig.name == "pan1"
    assert len(gen_sigs) == 2


def test_make_pangenome_signature_name():
    assert (
        make_pangenome_signature_name("pan1", Path("/x/genome11.fa")) == "pan1@genome11"
    )
    assert (
        make_pangenome_signature_name(
            "pan1", Path("/x/dir/genome11.fa"), use_parent_as_name=True
        )
        == "pan1@dir"
    )
