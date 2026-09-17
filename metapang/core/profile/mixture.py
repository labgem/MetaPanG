from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass
class Mixture:
    """Raw problem instance: M x = y, x >= 0."""
    m: NDArray[np.float64]          # (n_families, n_strains)
    y: NDArray[np.float64]          # (n_families,)
    strain_labels: list[str]        # length n_strains
    family_labels: list[str] | None = None  # length n_families (optional)
    laplacian: NDArray[np.float64] | None = None

    @property
    def n_families(self) -> int:
        return self.m.shape[0]

    @property
    def n_strains(self) -> int:
        return self.m.shape[1]

    def copy(self) -> "Mixture":
        """Return a deep copy of this mixture."""
        return Mixture(
            m=self.m.copy(),
            y=self.y.copy(),
            strain_labels=list(self.strain_labels),
            family_labels=list(self.family_labels) if self.family_labels else None,
        )

    def validate(self):
        """Assert the matrix, vector, and label shapes are mutually consistent."""
        assert self.m.shape[0] == self.y.shape[0], "M rows must match y length"
        assert self.m.shape[1] == len(self.strain_labels), "M cols must match strain labels"
        if self.family_labels is not None:
            assert self.m.shape[0] == len(self.family_labels), "M rows must match family labels"
