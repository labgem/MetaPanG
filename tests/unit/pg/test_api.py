from metapang.pg.api import CollectionReleases, parse_collection_name_version


def test_parse_name_only():
    assert parse_collection_name_version("GTDB_refseq") == (
        "GTDB_refseq",
        "latest",
        None,
    )


def test_parse_name_version():
    assert parse_collection_name_version("GTDB_refseq@2.0.0") == (
        "GTDB_refseq",
        "2.0.0",
        None,
    )


def test_parse_name_version_pangenome():
    assert parse_collection_name_version("GTDB_refseq@2.0.0:s__Foo") == (
        "GTDB_refseq",
        "2.0.0",
        "s__Foo",
    )


def test_parse_name_pangenome_latest():
    assert parse_collection_name_version("GTDB_refseq:s__Foo") == (
        "GTDB_refseq",
        "latest",
        "s__Foo",
    )


def _collection_dict():
    return {
        "name": "GTDB_refseq",
        "id": 1,
        "releases": [
            {
                "version": "2.0.0",
                "latest": True,
                "ppanggolin_version": "2.1",
                "pangbank_wf_version": "1.1",
                "taxonomy_source": {"name": "GTDB", "version": "11-RS232"},
                "pangenome_count": 200,
            },
            {
                "version": "1.0.0",
                "latest": False,
                "ppanggolin_version": "2.0",
                "pangbank_wf_version": "1.0",
                "taxonomy_source": {"name": "GTDB", "version": "10-RS226"},
                "pangenome_count": 100,
            },
        ],
    }


def test_from_api_response_sorted_by_version():
    releases = CollectionReleases.from_api_response(_collection_dict())
    assert len(releases) == 2
    assert [r.version for r in releases.releases] == ["1.0.0", "2.0.0"]


def test_from_api_response_latest():
    releases = CollectionReleases.from_api_response(_collection_dict())
    assert releases.latest.version == "2.0.0"
    assert releases.latest.full_name == "GTDB_refseq@2.0.0"
