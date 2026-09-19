import typing as tp

# Ignore warnings from pytables when reading pangenome HDF5 files
import warnings
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
from graph_tool import Graph, GraphView, Vertex, VertexPropertyMap, load_graph
from graph_tool import VertexBase as VertexType
from tables.exceptions import FiltersWarning

warnings.simplefilter("ignore", FiltersWarning)


class pw_graph_property(str, Enum):
    """Graph-level property keys stored on a PWGraph."""

    annotation_report = "annotation_report"
    per_organism_nodes = "per_organism_nodes"


class pw_node_property(str, Enum):
    """Vertex-level property keys stored on a PWGraph."""

    nid = "nid"
    strains = "strains"
    partition = "partition"  # type: ignore[assignment]
    weight = "weight"
    read_count = "read_count"
    kmer_count = "kmer_count"
    length = "length"


pw_node_property_type: dict[pw_node_property, str] = {
    pw_node_property.nid: "string",
    pw_node_property.strains: "vector<string>",
    pw_node_property.partition: "string",
    pw_node_property.weight: "float",
    pw_node_property.read_count: "int",
    pw_node_property.kmer_count: "int",
    pw_node_property.length: "int",
}

pw_graph_property_type: dict[pw_graph_property, str] = {
    pw_graph_property.annotation_report: "python::object",
    pw_graph_property.per_organism_nodes: "python::object",
}


@dataclass
class GenomeCoverage:
    """Per-organism node counts and covered-node counts by partition (P/S/C)."""

    nb_p: int
    nb_s: int
    nb_c: int
    cov_p: int
    cov_s: int
    cov_c: int

    @property
    def r_p(self):
        return self.cov_p / self.nb_p

    @property
    def r_s(self):
        return self.cov_s / self.nb_s

    @property
    def r_c(self):
        return self.cov_c / self.nb_c

    @property
    def nodes(self):
        return self.nb_p + self.nb_s + self.nb_c

    @property
    def cov_nodes(self):
        return self.cov_p + self.cov_s + self.cov_c

    @property
    def r(self):
        return self.cov_nodes / self.nodes


class PWGraph:
    """Pangenome graph wrapper over a graph_tool Graph with typed node properties."""

    def __init__(self, pangenome: Path | GraphView) -> None:
        self._gt: Graph = Graph()
        self._vmap: dict[str, VertexType] | None = None
        self._init_graph(pangenome)

    @staticmethod
    def _default_vfilt(*_) -> bool:
        return True

    def _init_graph(self, pangenome: Path | GraphView | Graph) -> None:
        if isinstance(pangenome, Path):
            if pangenome.suffix == ".h5":
                self._from_h5(pangenome)
            else:
                self._gt = load_graph(str(pangenome))
        elif isinstance(pangenome, GraphView):
            self._gt = Graph(pangenome, prune=True)
        elif isinstance(pangenome, Graph):
            self._gt = pangenome

    def _from_h5(self, pangenome_h5: Path) -> None:
        from ppanggolin.formats.readBinaries import check_pangenome_info
        from ppanggolin.pangenome import Pangenome  # heavy: lazy

        pangenome = Pangenome()
        pangenome.add_file(pangenome_h5)
        check_pangenome_info(
            pangenome,
            need_families=True,
            need_annotations=True,
            need_graph=True,
            disable_bar=True,
        )

        self._gt = Graph(directed=False)
        self._vmap = {}

        per_organism_nodes = {}

        for prop, ptype in pw_node_property_type.items():
            self._gt.vp[prop.value] = self._gt.new_vp(ptype)
        for prop, ptype in pw_graph_property_type.items():
            self._gt.gp[prop.value] = self._gt.new_gp(ptype)

        for fam in pangenome.gene_families:
            v = self.graph.add_vertex()
            self._vmap[fam.name] = v
            self._gt.vp[pw_node_property.nid.value][v] = fam.name
            self._gt.vp[pw_node_property.partition.value][v] = fam.partition[0]
            self._gt.vp[pw_node_property.length.value][v] = len(fam.sequence * 3)

            organisms = list(x.name for x in fam.organisms)
            for o in organisms:
                if o not in per_organism_nodes:
                    per_organism_nodes[o] = {"P": 0, "S": 0, "C": 0, "sum": 0}
                per_organism_nodes[o][fam.partition[0]] += 1
                per_organism_nodes[o]["sum"] += 1

            self._gt.vp[pw_node_property.strains.value][v] = organisms

        self._gt.gp[pw_graph_property.per_organism_nodes.value] = dict(
            per_organism_nodes
        )
        for fam in pangenome.gene_families:
            for n in fam.neighbors:
                if self._gt.edge(self._vmap[fam.name], self._vmap[n.name]):
                    continue
                self._gt.add_edge(self._vmap[fam.name], self._vmap[n.name])

    @property
    def graph(self) -> Graph:
        return self._gt

    def node(self, name: str) -> VertexType | None:
        """Return the vertex with the given node id, or None if absent."""
        if self._vmap is None:
            nid = self._gt.vp[pw_node_property.nid.value]
            self._vmap = {nid[v]: v for v in self.graph.vertices()}
        return self._vmap.get(name, None)

    def save(self, path: Path) -> None:
        """Save the underlying graph to the given path."""
        self._gt.save(str(path))

    def property(self, prop: pw_node_property) -> int | str | list[str] | None:
        """Return the vertex property map for the given property."""
        return self._gt.vp[prop.value]

    def node_property(
        self, node: VertexType | str, prop: pw_node_property
    ) -> int | str | list[str] | None:
        """Return the value of a property for a single node."""
        return self._gt.vp[prop.value][
            node if isinstance(node, Vertex) else self.node(node)
        ]

    def node_properties(
        self, node: VertexType | str
    ) -> dict[pw_node_property, int | str | list[str] | None]:
        """Return all properties of a single node as a dict."""
        return {prop: self.node_property(node, prop) for prop in pw_node_property}

    def graph_property(self, prop: pw_graph_property) -> int | str | list[str] | None:
        """Return the graph-level property value for the given key."""
        return self._gt.gp[prop.value]

    def graph_properties(self) -> dict[pw_graph_property, int | str | list[str] | None]:
        """Return all graph-level properties as a dict."""
        return {prop: self.graph_property(prop) for prop in pw_graph_property}

    def update_node_property(
        self,
        node: VertexType | str,
        prop: pw_node_property,
        value: int | str | list[str],
    ) -> None:
        """Set a property value for a single node."""
        self._gt.vp[prop.value][
            node if isinstance(node, Vertex) else self.node(node)
        ] = value

    def inc_node_property(
        self,
        node: VertexType | str,
        inc: int | float = 1,
        prop: pw_node_property = pw_node_property.weight,
    ) -> None:
        """Increment a numeric property of a single node by the given amount."""
        v = node if isinstance(node, Vertex) else self.node(node)
        self._gt.vp[prop.value][v] += inc

    def filter(
        self,
        prop: pw_node_property,
        vfilt: tp.Callable[[VertexType, VertexPropertyMap], bool] = _default_vfilt,
    ) -> Graph:
        """Return a pruned copy of the graph filtered by the given predicate."""
        return Graph(self.view(prop, vfilt), prune=True)

    def filter_persistent(self) -> Graph:
        """Return a pruned copy containing only persistent (P) nodes."""
        return self.filter(pw_node_property.partition, lambda v, p: p[v] == "P")

    def filter_shell(self) -> Graph:
        """Return a pruned copy containing only shell (S) nodes."""
        return self.filter(pw_node_property.partition, lambda v, p: p[v] == "S")

    def filter_cloud(self) -> Graph:
        """Return a pruned copy containing only cloud (C) nodes."""
        return self.filter(pw_node_property.partition, lambda v, p: p[v] == "C")

    def view(
        self,
        prop: pw_node_property,
        vfilt: tp.Callable[[VertexType, VertexPropertyMap], bool] = _default_vfilt,
    ) -> GraphView:
        """Return a filtered GraphView selecting nodes by the given predicate."""
        return GraphView(self._gt, vfilt=lambda v: vfilt(v, self._gt.vp[prop.value]))

    def pw_view(
        self,
        prop: pw_node_property,
        vfilt: tp.Callable[[VertexType, VertexPropertyMap], bool] = _default_vfilt,
    ) -> "PWGraph":
        """Return a new PWGraph wrapping the filtered view, sharing the node map."""
        v = PWGraph(self.view(prop, vfilt))
        v._vmap = self._vmap
        return v

    def view_persistent(self) -> GraphView:
        """Return a view of the persistent (P) subgraph."""
        return self.view(pw_node_property.partition, vfilt=lambda v, p: p[v] == "P")

    def view_no_persistent(self) -> GraphView:
        """Return a view of the non-persistent (shell and cloud) subgraph."""
        return self.view(pw_node_property.partition, vfilt=lambda v, p: p[v] != "P")

    def view_shell(self) -> GraphView:
        """Return a view of the shell (S) subgraph."""
        return self.view(pw_node_property.partition, vfilt=lambda v, p: p[v] == "S")

    def view_cloud(self) -> GraphView:
        """Return a view of the cloud (C) subgraph."""
        return self.view(pw_node_property.partition, vfilt=lambda v, p: p[v] == "C")

    def _coverage(
        self,
        graph: Graph | GraphView,
        prop: pw_node_property = pw_node_property.weight,
        predicate: tp.Callable[[VertexType, VertexPropertyMap], bool] = lambda v, p: (
            p[v] > 0
        ),
    ) -> float:
        c = 0
        for v in graph.vertices():
            if predicate(v, self._gt.vp[prop.value]):
                c += 1
        return c / self._gt.num_vertices() if self._gt.num_vertices() > 0 else 0

    def persistent_coverage(self) -> float:
        """Return the fraction of persistent nodes with non-zero weight."""
        return self._coverage(self.view_persistent())

    def shell_coverage(self) -> float:
        """Return the fraction of shell nodes with non-zero weight."""
        return self._coverage(self.view_shell())

    def cloud_coverage(self) -> float:
        """Return the fraction of cloud nodes with non-zero weight."""
        return self._coverage(self.view_cloud())

    def _coverage_per_organisms(self, view: Graph | GraphView) -> dict[str, float]:
        coverage = {}
        node_per_org = {}
        for v in view.vertices():
            for o in self.node_property(v, pw_node_property.strains):  # type: ignore
                node_per_org[o] = node_per_org.get(o, 0) + 1
                if self.node_property(v, pw_node_property.weight) > 0:  # type: ignore
                    coverage[o] = coverage.get(o, 0) + 1

        return {
            o: round(coverage.get(o, 0) / total, 4) for o, total in node_per_org.items()
        }

    def coverage(self) -> dict[str, GenomeCoverage]:
        """Return per-organism GenomeCoverage (node and covered counts by partition)."""
        coverage = {}
        nodes = {}

        for v in self.graph.vertices():
            for o in self.node_property(v, pw_node_property.strains):  # type: ignore
                if o not in coverage:
                    coverage[o] = {"P": 0, "S": 0, "C": 0}
                if o not in nodes:
                    nodes[o] = {"P": 0, "S": 0, "C": 0}

                pp = self.node_property(v, pw_node_property.partition)
                nodes[o][pp] += 1
                if self.node_property(v, pw_node_property.weight) > 0:  # type: ignore
                    coverage[o][pp] += 1

        return {
            name: GenomeCoverage(
                nodes[name]["P"],
                nodes[name]["S"],
                nodes[name]["C"],
                coverage[name]["P"],
                coverage[name]["S"],
                coverage[name]["C"],
            )
            for name in coverage
        }

    def coverage_per_organisms(self) -> dict[str, float]:
        """Return per-organism coverage over all nodes."""
        return self._coverage_per_organisms(self.graph)

    def persistent_coverage_per_organisms(self) -> dict[str, float]:
        """Return per-organism coverage over persistent nodes."""
        return self._coverage_per_organisms(self.view_persistent())

    def shell_coverage_per_organisms(self) -> dict[str, float]:
        """Return per-organism coverage over shell nodes."""
        return self._coverage_per_organisms(self.view_shell())

    def cloud_coverage_per_organisms(self) -> dict[str, float]:
        """Return per-organism coverage over cloud nodes."""
        return self._coverage_per_organisms(self.view_cloud())

    def shell_cloud_coverage_per_organisms(self) -> dict[str, float]:
        """Return per-organism coverage over non-persistent (shell and cloud) nodes."""
        return self._coverage_per_organisms(self.view_no_persistent())

    def _mean_per_organism(
        self, view: Graph | GraphView, prop: pw_node_property = pw_node_property.weight
    ) -> dict[str, float]:
        values, counts = {}, {}
        for v in view.vertices():
            value = self._gt.vp[prop.value][v]
            for o in self._gt.vp[pw_node_property.strains.value][v]:
                values[o] = values.get(o, 0) + value
                counts[o] = counts.get(o, 0) + 1
        return {o: round(values[o] / counts[o], 4) for o in values.keys()}

    def mean_per_organisms(
        self, prop: pw_node_property = pw_node_property.weight
    ) -> dict[str, float]:
        """Return per-organism mean of a property over all nodes."""
        return self._mean_per_organism(self.graph, prop)

    def persistent_mean_per_organisms(
        self, prop: pw_node_property = pw_node_property.weight
    ) -> dict[str, float]:
        """Return per-organism mean of a property over persistent nodes."""
        return self._mean_per_organism(self.view_persistent(), prop)

    def shell_mean_per_organisms(
        self, prop: pw_node_property = pw_node_property.weight
    ) -> dict[str, float]:
        """Return per-organism mean of a property over shell nodes."""
        return self._mean_per_organism(self.view_shell(), prop)

    def cloud_mean_per_organisms(
        self, prop: pw_node_property = pw_node_property.weight
    ) -> dict[str, float]:
        """Return per-organism mean of a property over cloud nodes."""
        return self._mean_per_organism(self.view_cloud(), prop)

    def shell_cloud_mean_per_organisms(
        self, prop: pw_node_property = pw_node_property.weight
    ) -> dict[str, float]:
        """Return per-organism mean of a property over non-persistent (shell and cloud) nodes."""
        return self._mean_per_organism(self.view_no_persistent(), prop)

    def persistent_mean_weight(
        self, prop: pw_node_property = pw_node_property.weight
    ) -> float | np.floating:
        """Return the mean property value across persistent nodes (0.0 if none)."""
        return (
            np.mean(
                [self._gt.vp[prop.value][v] for v in self.view_persistent().vertices()]
            )
            if self.view_persistent().num_vertices() > 0
            else 0.0
        )

    def mean_weight_from_specific_nodes(
        self,
        organism: str,
        avoid: list[str],
        prop: pw_node_property = pw_node_property.weight,
    ) -> float | np.floating:
        """Return the mean weight over nodes of an organism, excluding avoided strains."""
        strains_prop = self._gt.vp[pw_node_property.strains.value]
        weights_prop = self._gt.vp[prop.value]

        def is_avoided(v: VertexType) -> bool:
            for a in avoid:
                if a in strains_prop[v]:
                    return True
            return False

        strain_nodes = [
            v
            for v in self.graph.vertices()
            if organism in strains_prop[v] and not is_avoided(v)
        ]
        if not strain_nodes:
            return 0.0

        weights = [weights_prop[v] for v in strain_nodes]
        mean_weight = np.mean(weights)
        return mean_weight


@dataclass
class PWGraphAnnotationReport:
    """Summary of sequences seen and mapped during annotation."""

    total_seq: int
    total_seq_mapped: int


class PWGraphAnnotator:
    """Annotate a PWGraph with read, kmer, and weight counts from a query result file."""

    def __init__(self, graph: PWGraph, annotation_file: Path) -> None:
        self._graph = graph
        self._annotation_file = annotation_file
        self._report = PWGraphAnnotationReport(0, 0)

    def _parse_query_result(self, line: str) -> tuple[str, int] | None:
        s = line.strip().split("\t")
        if len(s) < 3:
            return None
        r = s[2].split(":")
        return r[0][1:-1], int(r[1])

    def annotate(self) -> PWGraphAnnotationReport:
        """Parse the annotation file and update node counts, returning the report."""
        with open(self._annotation_file) as f:
            for line in f:
                if line:
                    self._report.total_seq += 1
                    if v := self._parse_query_result(line):
                        node = self._graph.node(v[0])
                        if node is None:
                            continue
                        self._graph._gt.vp[pw_node_property.read_count.value][node] += 1
                        self._graph._gt.vp[pw_node_property.kmer_count.value][node] += (
                            v[1]
                        )
                        w = (v[1] + 21) / self._graph._gt.vp[
                            pw_node_property.length.value
                        ][node]
                        self._graph._gt.vp[pw_node_property.weight.value][node] += w
                        self._report.total_seq_mapped += 1
        self._graph._gt.gp[pw_graph_property.annotation_report.value] = (
            self._report.__dict__
        )
        return self._report
