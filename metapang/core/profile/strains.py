from __future__ import annotations

import math
import typing as tp
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import nnls

from metapang.config import metapang_profile_c
from metapang.core.profile.mixture import Mixture
from metapang.core.graph import (
    PWGraph, pw_node_property, pw_graph_property,
)


_PD = metapang_profile_c()


@dataclass
class StrainProfileConfig:
    """Tunable knobs controlling strain selection, decomposition, and abundance refinement."""
    merge_jaccard: float = _PD.merge_jaccard
    k_max: int = _PD.k_max
    stop_rule: str = _PD.stop_rule
    cv_folds: int = _PD.cv_folds
    cv_min_rel_reduction: float = _PD.cv_min_rel_reduction
    refine_ra: bool = _PD.refine_ra
    impute_min_neighbour_frac: float = _PD.impute_min_neighbour_frac
    reassign_max_rel_residual: float = _PD.reassign_max_rel_residual
    tie_rel: float = 0.01


@dataclass
class SelectionStep:
    """One forward-selection increment: the strain considered and whether it was accepted."""
    added_label: str
    residual: float
    cv_error: float
    accepted: bool
    stop_reason: str | None = None


@dataclass
class Selection:
    """The chosen strains with fitted abundances, fit quality, and the selection trace."""
    indices: list[int]
    labels: list[str]
    x: NDArray[np.float64]
    ra: NDArray[np.float64]
    residual: float
    r_squared: float
    groups: dict[str, list[str]]
    trace: list[SelectionStep]

    @property
    def k(self) -> int:
        return len(self.indices)

    @classmethod
    def empty(cls) -> "Selection":
        """An empty selection (no strains chosen)."""
        return cls(indices=[], labels=[], x=np.zeros(0), ra=np.zeros(0),
                   residual=0.0, r_squared=0.0, groups={}, trace=[])


@dataclass
class GeneSet:
    """A detected strain's gene content: anchor references, abundance, and per-family assignment."""
    component_id: int
    anchor_refs: list[str]
    abundance: float
    ra: float
    family_ids: list[str]
    family_abundances: dict[str, float] | None = None
    family_status: dict[str, str] | None = None


@dataclass
class StrainProfile:
    """The full profiling result: detected strains, their gene sets, and fit quality."""
    k: int
    components: list[GeneSet]
    residual: float
    r_squared: float
    selection: Selection


@tp.runtime_checkable
class StrainSelector(tp.Protocol):
    """Protocol for objects that select strains from a mixture."""
    def select(self, mix: Mixture, pwg: PWGraph | None = None) -> Selection: ...


@tp.runtime_checkable
class GeneSetAssigner(tp.Protocol):
    """Protocol for objects that assign gene families to selected strains."""
    def assign(self, selection: Selection, mix: Mixture, pwg: PWGraph) -> list[GeneSet]: ...


def collapse_columns(mix: Mixture, jaccard: float = 0.95) -> tuple[Mixture, dict[str, list[str]]]:
    """Merge strain columns whose Jaccard similarity >= threshold (single-linkage).

    Returns:
        The reduced mixture (merged column = union of families) and a map from the
        representative label to its member genome labels.
    """
    n = mix.n_strains
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    C = (mix.m > 0).astype(np.float64)
    inter = C.T @ C
    deg = np.diag(inter)
    union_counts = deg[:, None] + deg[None, :] - inter
    with np.errstate(divide="ignore", invalid="ignore"):
        sim = np.where(union_counts > 0, inter / union_counts, 1.0)
    iu, ju = np.where(np.triu(sim >= jaccard, k=1))
    for i, j in zip(iu.tolist(), ju.tolist()):
        union(i, j)

    grouped: dict[int, list[int]] = {}
    for i in range(n):
        grouped.setdefault(find(i), []).append(i)

    new_cols, new_labels = [], []
    group_map: dict[str, list[str]] = {}
    for _root, idxs in grouped.items():
        merged = np.any(mix.m[:, idxs] > 0, axis=1).astype(float)
        new_cols.append(merged)
        label = mix.strain_labels[idxs[0]]
        new_labels.append(label)
        group_map[label] = [mix.strain_labels[k] for k in idxs]

    new_m = np.column_stack(new_cols) if new_cols else np.empty((mix.n_families, 0))
    reduced = Mixture(m=new_m, y=mix.y.copy(), strain_labels=new_labels,
                      family_labels=mix.family_labels)
    return reduced, group_map


def kstar_one_se(fold_errors: list[list[float]]) -> int:
    """Pick the fewest strains whose CV error is within one SE of the minimum.

    NNLS zeros spurious strains, so the CV curve drops to the true k then plateaus
    (never rises). A plain argmin chases noise to k_max, the 1-SE rule stops at the elbow.
    """
    means = [float(np.mean(e)) for e in fold_errors]
    kbest = int(np.argmin(means))
    errs = fold_errors[kbest]
    se = float(np.std(errs) / math.sqrt(len(errs))) if len(errs) > 1 else 0.0
    thresh = means[kbest] + se
    for k in range(len(means)):
        if means[k] <= thresh:
            return k
    return kbest


def kstar_paired(fold_errors: list[list[float]], min_rel_reduction: float = 0.0) -> int:
    """Sequential paired-difference stop: add a strain only while it both significantly and meaningfully lowers held-out error.

    Unlike the 1-SE rule, this tests each increment locally: per-fold improvement
    ``d_f = eps[k,f] - eps[k+1,f]``. Accept only if ``dbar > se`` AND the
    gain is a fraction ``min_rel_reduction`` of current error. The second
    gate stops collinear near-duplicates from marching to k_max. Stop at the first failure.
    """
    K = len(fold_errors) - 1
    kstar = 0
    for k in range(K):
        cur = np.asarray(fold_errors[k], dtype=float)
        nxt = np.asarray(fold_errors[k + 1], dtype=float)
        if cur.size == 0 or cur.size != nxt.size:
            break
        d = cur - nxt                       # per-fold improvement from strain k+1
        dbar = float(np.mean(d))
        se = float(np.std(d) / math.sqrt(d.size)) if d.size > 1 else 0.0
        mean_cur = float(np.mean(cur))
        rel = dbar / mean_cur if mean_cur > 0 else 0.0
        significant = dbar > se                 # improvement beats its own noise
        meaningful = rel >= min_rel_reduction
        if significant and meaningful:
            kstar = k + 1
        else:
            break
    return kstar


def _nnls_via_gram(G: NDArray[np.float64], b: NDArray[np.float64], yty: float,
                   cols: tp.Sequence[int]) -> tuple[NDArray[np.float64], float]:
    """Exact NNLS on a subset of a fixed tall design, via its Gram matrix.

    With precomputed ``G = M.T @ M``, ``b = M.T @ y``, ``yty = y.T @ y``, solving
    ``min_{x>=0} ||M[:, cols] x - y||^2`` needs neither M nor y. Whitening the k x k block
    ``G_S = A.T A`` by symmetric eigendecomposition makes each solve O(k^3).

    Returns:
        (x aligned to ``cols``, residual sum of squares).
    """
    cols = list(cols)
    if not cols:
        return np.zeros(0), float(yty)
    Gs = G[np.ix_(cols, cols)]
    bs = b[cols]
    w, V = np.linalg.eigh(Gs)
    if w[-1] <= 0:                       # all-zero columns -> only x = 0 feasible
        return np.zeros(len(cols)), float(yty)
    pos = w > w[-1] * 1e-12
    sw = np.sqrt(w[pos])
    A = V[:, pos].T * sw[:, None]        # (r x k): A.T @ A == Gs on its range
    rhs = (V[:, pos].T @ bs) / sw        # A.T @ rhs == bs (b lies in range(G))
    x, _ = nnls(A, rhs)
    rss = float(x @ Gs @ x - 2.0 * x @ bs + yty)
    return x, max(rss, 0.0)


class GreedyStrainSelector:
    """Selects strains by greedy forward NNLS with cross-validated stopping."""
    def __init__(self,
                 config: StrainProfileConfig | None = None,
                 priority: dict[str, float] | None = None) -> None:
        self.config = config or StrainProfileConfig()
        self.priority = priority or {}
        self._G: NDArray[np.float64] = np.zeros((0, 0))
        self._b: NDArray[np.float64] = np.zeros(0)
        self._yty: float = 0.0
        self._n_fam: int = 0
        self._fold: list[tuple[NDArray[np.float64], NDArray[np.float64], float, int]] = []

    def _solve_subset(self, M, y, cols, labels):
        return _nnls_via_gram(self._G, self._b, self._yty, cols)

    def _pick_best(self, M, y, selected, remaining, labels):
        """Best next candidate by residual; ties (within tie_rel) broken by priority (shell coverage), then residual, then label."""
        evals = [(j, self._solve_subset(M, y, selected + [j], labels)[1]) for j in remaining]
        best_rss = min(r for _, r in evals)
        tie_cut = best_rss * (1.0 + self.config.tie_rel)
        tied = [(j, r) for j, r in evals if r <= tie_cut]
        tied.sort(key=lambda e: (-self.priority.get(labels[e[0]], 0.0), e[1], labels[e[0]]))
        return tied[0]

    def _cv_fold_errors(self, cols, n_folds: int) -> list[float]:
        """Per-fold cross-validated MSE for the model using `cols`: fit on training folds, predict the held-out fold."""
        cols = list(cols)
        errs: list[float] = []
        for f in range(n_folds):
            Gf, bf, ytf, cnt = self._fold[f]
            if cnt == 0 or cnt == self._n_fam:
                continue
            if not cols:
                errs.append(ytf / cnt)
                continue
            xx, _ = _nnls_via_gram(self._G - Gf, self._b - bf, self._yty - ytf, cols)
            Gfc = Gf[np.ix_(cols, cols)]
            test_rss = float(xx @ Gfc @ xx - 2.0 * xx @ bf[cols] + ytf)
            errs.append(max(test_rss, 0.0) / cnt)
        return errs

    def _finalize(self, reduced, sel_cols, groups, trace) -> Selection:
        """Final solve on the chosen columns. Drop any strain NNLS zeroed out."""
        M, y = reduced.m, reduced.y
        labels = reduced.strain_labels
        n_fam = reduced.n_families
        tss = float(np.sum((y - y.mean()) ** 2)) if n_fam else 0.0

        def empty():
            return Selection([], [], np.zeros(0), np.zeros(0),
                             float(np.linalg.norm(y)), 0.0, groups, trace)

        if not sel_cols:
            return empty()
        x, rss = self._solve_subset(M, y, sel_cols, labels)
        keep = [i for i in range(len(sel_cols)) if x[i] > 1e-9]
        if not keep:
            return empty()
        if len(keep) < len(sel_cols):
            sel_cols = [sel_cols[i] for i in keep]
            x, rss = self._solve_subset(M, y, sel_cols, labels)
        total = float(np.sum(x))
        ra = x / total if total > 0 else x
        r2 = 1.0 - rss / tss if tss > 0 else 0.0
        return Selection(indices=list(sel_cols), labels=[labels[c] for c in sel_cols],
                         x=x, ra=ra, residual=math.sqrt(rss), r_squared=r2,
                         groups=groups, trace=trace)

    def _greedy_order(self, reduced, pwg):
        """Greedy forward ordering of strains (no early stop).

        Returns:
            The ordered column indices, their residuals, and the skip trace.
        """
        cfg = self.config
        M, y = reduced.m, reduced.y
        labels = reduced.strain_labels
        selected: list[int] = []
        order_rss: list[float] = []
        trace: list[SelectionStep] = []
        remaining = set(range(reduced.n_strains))
        while len(selected) < cfg.k_max and remaining:
            j, rss = self._pick_best(M, y, selected, remaining, labels)
            selected.append(j)
            order_rss.append(rss)
            remaining.discard(j)
        return selected, order_rss, trace

    def _select_cv(self, reduced, groups, pwg) -> Selection:
        cfg = self.config
        M, y = reduced.m, reduced.y
        labels = reduced.strain_labels
        n_fam = reduced.n_families
        tss = float(np.sum((y - y.mean()) ** 2)) if n_fam else 0.0

        # Precompute the Gram once: every greedy/CV NNLS below then costs O(k^3)
        # instead of O(F k^2), so the tall design M (F rows) is touched only here.
        self._G = M.T @ M
        self._b = M.T @ y
        self._yty = float(y @ y)
        self._n_fam = n_fam

        # Per-fold Gram pieces (same fixed partition/seed as before) so CV folds
        # reuse the precomputed Gram: G_train = G - G_fold, etc.
        fold = np.random.default_rng(0).integers(0, cfg.cv_folds, size=n_fam)
        self._fold = []
        for f in range(cfg.cv_folds):
            rows = fold == f
            Mf = M[rows]
            self._fold.append((Mf.T @ Mf, Mf.T @ y[rows],
                               float(y[rows] @ y[rows]), int(rows.sum())))

        order, order_rss, trace = self._greedy_order(reduced, pwg)

        fold_errs = [self._cv_fold_errors(order[:k], cfg.cv_folds)
                     for k in range(len(order) + 1)]
        means = [float(np.mean(e)) for e in fold_errs]
        if cfg.stop_rule == "cv_paired":
            kstar = kstar_paired(fold_errs, cfg.cv_min_rel_reduction)
            reason = "cv_paired"
        else:
            kstar = kstar_one_se(fold_errs)
            reason = "cv"

        for k in range(1, len(order) + 1):
            trace.append(SelectionStep(added_label=labels[order[k - 1]],
                                       residual=math.sqrt(order_rss[k - 1]),
                                       cv_error=means[k],
                                       accepted=(k <= kstar),
                                       stop_reason=None if k <= kstar else reason))
        return self._finalize(reduced, order[:kstar], groups, trace)

    def select(self, mix: Mixture, pwg: PWGraph | None = None) -> Selection:
        """Collapse near-duplicate columns, then run cross-validated greedy selection."""
        cfg = self.config
        reduced, groups = collapse_columns(mix, cfg.merge_jaccard)
        if not np.any(reduced.y > 0) or reduced.n_strains == 0:
            return Selection.empty()
        return self._select_cv(reduced, groups, pwg)


class DecompositionGeneSetAssigner:
    """Reconcile observed gene coverage against the detected strains

    Per gene family (node) with weight y and detected-strain abundances {a_j}:
    1. y>0 carried by detected strains: split y among them proportional to a_j ("observed").
    2. y>0 carried by none: the real strain has a gene its nearest reference lacks. Split
       y across the subset T whose abundances best sum to y, co-location breaks ties ("reassigned").
    3. y==0 carried by a strain: impute a_j scaled by the covered fraction of that strain's
       co-located neighbours. If none are covered treat as absent ("imputed", or dropped).
    """

    def __init__(self, impute_min_neighbour_frac: float = 0.5,
                 reassign_max_rel_residual: float = 0.5) -> None:
        self.impute_min_neighbour_frac = impute_min_neighbour_frac
        self.reassign_max_rel_residual = reassign_max_rel_residual

    def assign(self, selection: Selection, mix: Mixture | None, pwg: PWGraph) -> list[GeneSet]:
        """Assign each gene family to detected strains (observed, reassigned, or imputed)."""
        import itertools

        labels = selection.labels
        n = len(labels)
        a = [float(selection.x[i]) for i in range(n)]
        members = [set(selection.groups.get(labels[i], [labels[i]])) for i in range(n)]

        g = pwg.graph
        nid_prop = g.vp[pw_node_property.nid.value]
        weight_prop = g.vp[pw_node_property.weight.value]
        strains_prop = g.vp[pw_node_property.strains.value]

        subsets = []
        for r in range(1, n + 1):
            for combo in itertools.combinations(range(n), r):
                subsets.append((combo, sum(a[c] for c in combo)))

        def carriers(node_strains: set[str]) -> list[int]:
            return [i for i in range(n) if members[i] & node_strains]

        def neighbour_carrier_indices(v) -> set[int]:
            out: set[int] = set()
            for u in v.all_neighbors():
                out.update(carriers(set(strains_prop[u])))
            return out

        def best_subset(y: float, v) -> tuple[int, ...]:
            best_d = min(abs(y - s) for _, s in subsets)
            tied = [combo for combo, s in subsets if abs(abs(y - s) - best_d) <= 1e-9]
            if len(tied) == 1:
                return tied[0]
            support = neighbour_carrier_indices(v)
            return max(tied, key=lambda combo: (len(set(combo) & support), -len(combo),
                                                tuple(-c for c in combo)))

        def covered_neighbour_frac(v, j: int) -> float:
            tot = cov = 0
            for u in v.all_neighbors():
                if members[j] & set(strains_prop[u]):
                    tot += 1
                    if weight_prop[u] > 0:
                        cov += 1
            return cov / tot if tot > 0 else 0.0

        fam_ab: list[dict[str, float]] = [{} for _ in range(n)]
        fam_st: list[dict[str, str]] = [{} for _ in range(n)]

        def split_among(v, T) -> None:
            fid = nid_prop[v]
            y = float(weight_prop[v])
            tot = sum(a[c] for c in T)
            for c in T:
                fam_ab[c][fid] = fam_ab[c].get(fid, 0.0) + (y * a[c] / tot if tot > 0 else y / len(T))
                fam_st[c][fid] = "reassigned"

        def match_ok(y: float, T) -> bool:
            """Guards against force-reassigning orphans"""
            tot = sum(a[c] for c in T)
            denom = max(y, tot)
            if denom <= 0:
                return False
            return abs(y - tot) / denom <= self.reassign_max_rel_residual

        orphans = []
        for v in g.vertices():
            fid = nid_prop[v]
            y = float(weight_prop[v])
            carr = carriers(set(strains_prop[v]))

            if y > 0 and carr:
                tot = sum(a[i] for i in carr)
                for i in carr:
                    fam_ab[i][fid] = y * a[i] / tot if tot > 0 else y / len(carr)
                    fam_st[i][fid] = "observed"
            elif y > 0 and not carr and n > 0:
                orphans.append(v)
            elif y == 0 and carr:
                for i in carr:
                    frac = covered_neighbour_frac(v, i)
                    if frac >= self.impute_min_neighbour_frac and frac > 0:
                        fam_ab[i][fid] = a[i] * frac
                        fam_st[i][fid] = "imputed"

        if orphans and n > 0:
            for v in orphans:
                y = float(weight_prop[v])
                T = best_subset(y, v)
                if match_ok(y, T):
                    split_among(v, T)
                # else: coverage matches no strain combination -> family dropped

        result: list[GeneSet] = []
        for cid, label in enumerate(labels):
            result.append(GeneSet(
                component_id=cid,
                anchor_refs=selection.groups.get(label, [label]),
                abundance=a[cid],
                ra=float(selection.ra[cid]),
                family_ids=list(fam_ab[cid].keys()),
                family_abundances=fam_ab[cid],
                family_status=fam_st[cid],
            ))
        return result


def refine_abundances(selection: Selection, components: list[GeneSet]) -> Selection:
    """Refit strain abundances (NNLS) on the decomposition-corrected membership.
    Returns:
        A new Selection with updated x / ra / residual; k is unchanged.
    """
    n = len(selection.labels)
    if n == 0:
        return selection

    y_by_gene: dict[str, float] = {}
    mem_by_gene: dict[str, set[int]] = {}
    for cid, comp in enumerate(components):
        ab = comp.family_abundances or {}
        st = comp.family_status or {}
        for fid, val in ab.items():
            if st.get(fid) in ("observed", "reassigned"):
                y_by_gene[fid] = y_by_gene.get(fid, 0.0) + val
                mem_by_gene.setdefault(fid, set()).add(cid)

    genes = list(y_by_gene)
    if not genes:
        return selection

    M = np.zeros((len(genes), n))
    y = np.zeros(len(genes))
    for i, fid in enumerate(genes):
        y[i] = y_by_gene[fid]
        for cid in mem_by_gene[fid]:
            M[i, cid] = 1.0

    x, _ = nnls(M, y)
    total = float(np.sum(x))
    ra = x / total if total > 0 else x

    return Selection(indices=selection.indices, labels=selection.labels,
                     x=x, ra=ra, residual=selection.residual,
                     r_squared=selection.r_squared,
                     groups=selection.groups, trace=selection.trace)


def _all_strains(pwg: PWGraph) -> list[str]:
    """Strain labels from the per_organism_nodes graph property, else the sorted union of node strain lists."""
    per_org = pwg.graph_property(pw_graph_property.per_organism_nodes)
    if per_org:
        return list(per_org.keys())
    g = pwg.graph
    strains_prop = g.vp[pw_node_property.strains.value]
    seen: set[str] = set()
    for v in g.vertices():
        seen.update(strains_prop[v])
    return sorted(seen)


def build_mixture(pwg: PWGraph, strains: list[str] | None = None,
                  exclude: set[str] | None = None) -> Mixture:
    """Build the NNLS mixture (M, y) from a PWGraph.

    `exclude` holds out genomes from the candidate set (leave-one-out): nodes and weights
    are unchanged, but held-out genomes private families become orphan observed genes.
    """
    g = pwg.graph
    if strains is None:
        strains = _all_strains(pwg)
    if exclude:
        strains = [s for s in strains if s not in exclude]
    idx = {s: j for j, s in enumerate(strains)}

    n_nodes = g.num_vertices()
    m = np.zeros((n_nodes, len(strains)))
    y = np.zeros(n_nodes)

    nid_prop = g.vp[pw_node_property.nid.value]
    weight_prop = g.vp[pw_node_property.weight.value]
    strains_prop = g.vp[pw_node_property.strains.value]

    labels: list[str] = []
    for i, v in enumerate(g.vertices()):
        labels.append(nid_prop[v])
        y[i] = weight_prop[v]
        for s in set(strains_prop[v]):
            if s in idx:
                m[i, idx[s]] = 1.0
    return Mixture(m=m, y=y, strain_labels=list(strains), family_labels=labels)


def profile_strains(pwg: PWGraph, *, config: StrainProfileConfig | None = None,
                    selector: StrainSelector | None = None,
                    assigner: GeneSetAssigner | None = None,
                    exclude: set[str] | None = None) -> StrainProfile:
    """Profile strains present in a PWGraph: select strains, then assign gene content."""
    config = config or StrainProfileConfig()
    mix = build_mixture(pwg, exclude=exclude)

    if not np.any(mix.y > 0):
        return StrainProfile(k=0, components=[], residual=0.0, r_squared=0.0,
                             selection=Selection.empty())

    if selector is None:
        g = pwg.graph
        part_prop = g.vp[pw_node_property.partition.value]
        shell = np.fromiter((part_prop[v] == "S" for v in g.vertices()),
                            dtype=bool, count=g.num_vertices())
        cov_s = mix.m[shell & (mix.y > 0)].sum(axis=0)   # covered shell families per genome
        priority = {lbl: float(cov_s[j]) for j, lbl in enumerate(mix.strain_labels)}
        selector = GreedyStrainSelector(config=config, priority=priority)

    selection = selector.select(mix, pwg)

    if assigner is not None:
        components = assigner.assign(selection, mix, pwg)
    else:
        decomposer = DecompositionGeneSetAssigner(config.impute_min_neighbour_frac,
                                                  config.reassign_max_rel_residual)
        components = decomposer.assign(selection, mix, pwg)
        if config.refine_ra and selection.k > 0:
            selection = refine_abundances(selection, components)
            components = decomposer.assign(selection, mix, pwg)

    return StrainProfile(k=selection.k, components=components,
                         residual=selection.residual, r_squared=selection.r_squared,
                         selection=selection)
