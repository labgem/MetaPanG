import graph_tool.all as gt
import pytest

from metapang.core.graph import (
    PWGraph,
    pw_graph_property_type,
    pw_node_property,
    pw_node_property_type,
)


def make_toy_pwg(nids, strains_per_node, partitions, weights, edges):
    """Build a small PWGraph. `edges` is a list of (i, j) index pairs."""
    g = gt.Graph(directed=False)
    for prop, ptype in pw_node_property_type.items():
        g.vp[prop.value] = g.new_vp(ptype)
    for prop, ptype in pw_graph_property_type.items():
        g.gp[prop.value] = g.new_gp(ptype)

    vs = []
    for i, nid in enumerate(nids):
        v = g.add_vertex()
        vs.append(v)
        g.vp[pw_node_property.nid.value][v] = nid
        g.vp[pw_node_property.strains.value][v] = list(strains_per_node[i])
        g.vp[pw_node_property.partition.value][v] = partitions[i]
        g.vp[pw_node_property.weight.value][v] = float(weights[i])
        g.vp[pw_node_property.length.value][v] = 100
    for a, b in edges:
        g.add_edge(vs[a], vs[b])
    return PWGraph(g)


@pytest.fixture
def toy_pwg():
    """Return the make_toy_pwg builder (avoids importing the tests package)."""
    return make_toy_pwg
