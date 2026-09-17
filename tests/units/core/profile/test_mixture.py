import numpy as np
import pytest

from metapang.core.profile.mixture import Mixture


def _toy() -> Mixture:
    m = np.array([[1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    y = np.array([3.0, 8.0, 5.0])
    return Mixture(m=m, y=y, strain_labels=["A", "B"], family_labels=["f0", "f1", "f2"])


def test_shapes():
    mix = _toy()
    assert mix.n_families == 3
    assert mix.n_strains == 2


def test_copy():
    mix = _toy()
    dup = mix.copy()
    dup.m[0, 0] = 42.0
    dup.strain_labels[0] = "Z"
    assert mix.m[0, 0] == 1.0
    assert mix.strain_labels[0] == "A"


def test_validate():
    mix = _toy()
    mix.validate()
    bad = Mixture(m=np.ones((3, 2)), y=np.ones(2), strain_labels=["A", "B"])
    with pytest.raises(AssertionError):
        bad.validate()
