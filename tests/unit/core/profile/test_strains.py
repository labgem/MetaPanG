import numpy as np
import pytest
from scipy.optimize import nnls

from metapang.core.profile.mixture import Mixture
from metapang.core.profile.strains import (
    GreedyStrainSelector,
    Selection,
    StrainProfileConfig,
    _nnls_via_gram,
    build_mixture,
    collapse_columns,
    kstar_one_se,
    kstar_paired,
    profile_strains,
)


def test_config_defaults():
    c = StrainProfileConfig()
    assert c.merge_jaccard == 0.95
    assert c.k_max == 12
    assert c.stop_rule == "cv_paired"
    assert c.cv_folds == 5
    assert c.refine_ra is True


def test_empty_selection():
    s = Selection.empty()
    assert s.k == 0
    assert s.labels == []
    assert np.asarray(s.x).size == 0


def test_collapse_merges():
    m = np.array([[1.0, 1.0, 0.0], [1.0, 1.0, 1.0], [0.0, 0.0, 1.0]])
    mix = Mixture(m=m, y=np.array([2.0, 4.0, 3.0]), strain_labels=["A", "B", "C"])
    reduced, groups = collapse_columns(mix, jaccard=0.95)
    assert reduced.n_strains == 2
    rep = next(k for k, v in groups.items() if set(v) == {"A", "B"})
    assert rep == "A"
    np.testing.assert_array_equal(reduced.y, mix.y)


def test_collapse_keeps_distinct():
    m = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    mix = Mixture(m=m, y=np.array([1.0, 1.0, 1.0]), strain_labels=["A", "B"])
    reduced, groups = collapse_columns(mix, jaccard=0.95)
    assert reduced.n_strains == 2
    assert {frozenset(v) for v in groups.values()} == {
        frozenset(["A"]),
        frozenset(["B"]),
    }


def test_kstar_one_se():
    fold_errors = [[10.0] * 5, [5.0] * 5, [2.0] * 5, [2.0] * 5, [2.0] * 5]
    assert kstar_one_se(fold_errors) == 2


def test_kstar_paired_stops():
    fold_errors = [[10.0] * 5, [5.0] * 5, [4.99] * 5, [4.98] * 5]
    assert kstar_paired(fold_errors, min_rel_reduction=0.02) == 1


def test_kstar_paired_accepts():
    fold_errors = [[10.0] * 5, [6.0] * 5, [3.0] * 5, [2.999] * 5]
    assert kstar_paired(fold_errors, min_rel_reduction=0.02) == 2


@pytest.mark.parametrize("dup", [False, True])
def test_gram_matches_scipy(dup):
    rng = np.random.default_rng(7)
    M = (rng.random((150, 5)) < 0.4).astype(float)
    if dup:
        M[:, 1] = M[:, 0]
    y = np.abs(rng.normal(5, 2, size=150)) * (M.sum(axis=1) > 0)
    G, b, yty = M.T @ M, M.T @ y, float(y @ y)
    cols = [0, 2, 4]
    xg, rg = _nnls_via_gram(G, b, yty, cols)
    xt, _ = nnls(M[:, cols], y)
    rt = float(np.sum((M[:, cols] @ xt - y) ** 2))
    assert rg == pytest.approx(rt, abs=1e-6)
    np.testing.assert_allclose(M[:, cols] @ xg, M[:, cols] @ xt, atol=1e-6)


def test_greedy_recovers():
    F = 300
    M = np.zeros((F, 5))
    M[0:100, 0] = 1.0
    M[100:200, 1] = 1.0
    M[200:230, 2] = 1.0
    M[230:260, 3] = 1.0
    M[260:280, 4] = 1.0
    y = 3.0 * M[:, 0] + 5.0 * M[:, 1]
    mix = Mixture(m=M, y=y, strain_labels=["A", "B", "N1", "N2", "N3"])
    selection = GreedyStrainSelector(config=StrainProfileConfig()).select(mix)
    assert selection.k == 2
    assert set(selection.labels) == {"A", "B"}


def test_build_mixture(toy_pwg):
    pwg = toy_pwg(
        nids=["fam0", "fam1"],
        strains_per_node=[["A", "B"], ["A"]],
        partitions=["P", "S"],
        weights=[8.0, 3.0],
        edges=[],
    )
    mix = build_mixture(pwg)
    assert mix.strain_labels == ["A", "B"]
    assert mix.family_labels == ["fam0", "fam1"]
    np.testing.assert_array_equal(mix.y, np.array([8.0, 3.0]))
    np.testing.assert_array_equal(mix.m, np.array([[1.0, 1.0], [1.0, 0.0]]))


def test_profile_two_strains(toy_pwg):
    nids, strains, parts, weights = [], [], [], []
    for i in range(10):
        nids.append(f"privA{i}")
        strains.append(["A"])
        parts.append("S")
        weights.append(4.0)
    for i in range(10):
        nids.append(f"privB{i}")
        strains.append(["B"])
        parts.append("S")
        weights.append(6.0)
    for i in range(10):
        nids.append(f"core{i}")
        strains.append(["A", "B", "C"])
        parts.append("P")
        weights.append(10.0)
    for i in range(5):
        nids.append(f"privC{i}")
        strains.append(["C"])
        parts.append("S")
        weights.append(0.0)

    pwg = toy_pwg(
        nids=nids, strains_per_node=strains, partitions=parts, weights=weights, edges=[]
    )
    prof = profile_strains(pwg, config=StrainProfileConfig())

    assert prof.k == 2
    assert {c.anchor_refs[0] for c in prof.components} == {"A", "B"}
    assert sum(c.ra for c in prof.components) == pytest.approx(1.0, abs=1e-6)
    ra = {c.anchor_refs[0]: c.ra for c in prof.components}
    assert ra["B"] > ra["A"]
    valid = {"observed", "reassigned", "imputed"}
    for c in prof.components:
        assert set((c.family_status or {}).values()) <= valid
