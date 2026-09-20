from metapang.core.graph import GenomeCoverage, pw_node_property


def _graph(toy_pwg):
    return toy_pwg(
        nids=["n0", "n1", "n2", "n3"],
        strains_per_node=[["A"], ["A", "B"], ["B"], ["B"]],
        partitions=["P", "P", "S", "C"],
        weights=[2.0, 0.0, 1.0, 0.0],
        edges=[(0, 1), (1, 2), (2, 3)],
    )


def test_genome_coverage_math():
    gc = GenomeCoverage(nb_p=10, nb_s=4, nb_c=2, cov_p=5, cov_s=2, cov_c=0)
    assert gc.r_p == 0.5
    assert gc.r_s == 0.5
    assert gc.r_c == 0.0
    assert gc.nodes == 16
    assert gc.cov_nodes == 7
    assert gc.r == 7 / 16


def test_num_vertices(toy_pwg):
    assert _graph(toy_pwg).graph.num_vertices() == 4


def test_node_lookup(toy_pwg):
    pwg = _graph(toy_pwg)
    assert pwg.node("n0") is not None
    assert pwg.node("missing") is None


def test_node_property(toy_pwg):
    pwg = _graph(toy_pwg)
    node = pwg.node("n1")
    assert pwg.node_property(node, pw_node_property.partition) == "P"
    assert list(pwg.node_property(node, pw_node_property.strains)) == ["A", "B"]


def test_filter_by_partition(toy_pwg):
    pwg = _graph(toy_pwg)
    assert pwg.filter_persistent().num_vertices() == 2
    assert pwg.filter_shell().num_vertices() == 1
    assert pwg.filter_cloud().num_vertices() == 1


def test_partition_coverage(toy_pwg):
    pwg = _graph(toy_pwg)
    assert pwg.persistent_coverage() == 0.25
    assert pwg.shell_coverage() == 0.25
    assert pwg.cloud_coverage() == 0.0


def test_update_node_property(toy_pwg):
    pwg = _graph(toy_pwg)
    pwg.update_node_property("n3", pw_node_property.weight, 5.0)
    assert pwg.cloud_coverage() == 0.25


def test_inc_node_property(toy_pwg):
    pwg = _graph(toy_pwg)
    pwg.inc_node_property("n1", 3.0)
    assert pwg.persistent_coverage() == 0.5
