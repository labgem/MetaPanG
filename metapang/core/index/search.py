from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pandas as pd
import sourmash.index
from sourmash import SourmashSignature, load_file_as_index
from sourmash.index import IndexSearchResult

from metapang.core.index.index import IndexBuilder, IndexInfo
from metapang.exceptions import check_paths_exist


class SearchMode(Enum):
    """Search modes: Jaccard similarity, containment, or max containment."""

    jaccard = 1
    containment = 2
    max_containment = 3


@dataclass
class SearchResult:
    """A single search result: query name, matched name, score, and coverage."""

    query_name: str
    name: str
    score: float
    coverage: float

    @staticmethod
    def to_dataframe(results: list["SearchResult"]) -> pd.DataFrame:
        """Convert a list of SearchResult objects to a pandas DataFrame."""
        return pd.DataFrame([r.__dict__ for r in results])


class IndexType(Enum):
    """Index types: pangenome, genome, or all."""

    pangenome = 1
    genome = 2
    all = 3


class IndexSearch:
    """Search sequences, genomes, or signatures in a MetaPanG index."""

    def __init__(
        self,
        index_directory: Path,
        to_load: IndexType | None = IndexType.all,
        info_filename: str = "index_info.json",
    ) -> None:
        """Open a MetaPanG index directory.

        Args:
            index_directory: Path to the MetaPanG index directory.
            to_load: Index type to load eagerly; None defers to lazy loading.
            info_filename: Name of the index info file.
        """
        self.directory = index_directory
        self.index_info = IndexInfo.load_json(index_directory / info_filename)
        self.pangenome_index = None
        self.genome_index = None

        if to_load is not None:
            self._load_index(to_load)

    @property
    def info(self) -> IndexInfo:
        return self.index_info

    def _load_index(self, index_type: IndexType) -> None:
        match index_type:
            case IndexType.pangenome | IndexType.all:
                self.pangenome_index = load_file_as_index(
                    str(self._index_path(IndexType.pangenome))
                )
            case IndexType.genome | IndexType.all:
                self.genome_index = load_file_as_index(
                    str(self._index_path(IndexType.genome))
                )

    def _index_path(self, index_type: IndexType) -> Path:
        match index_type:
            case IndexType.pangenome:
                p = self.directory / self.index_info.pangenome_index
            case IndexType.genome:
                p = self.directory / self.index_info.genome_index
            case _:
                raise ValueError(f"Invalid index type {str(index_type)}")
        check_paths_exist(p)
        return p

    def _index(self, index_type: IndexType) -> sourmash.index.Index:
        match index_type:
            case IndexType.pangenome:
                if self.pangenome_index is None:
                    self._load_index(IndexType.pangenome)
                assert self.pangenome_index is not None
                return self.pangenome_index
            case IndexType.genome:
                if self.genome_index is None:
                    self._load_index(IndexType.genome)
                assert self.genome_index is not None
                return self.genome_index
            case _:
                raise ValueError(f"Invalid index type {str(index_type)}")

    def _search_results(
        self, query_signature: SourmashSignature, results: list[IndexSearchResult]
    ) -> list[SearchResult]:
        return [
            SearchResult(
                query_signature.name,
                r.signature.name,
                round(r.score, 4),
                round(r.signature.similarity(query_signature), 4),
            )
            for r in results
        ]

    def search_sequence_p(
        self,
        name: str,
        sequence: str,
        mode: SearchMode = SearchMode.jaccard,
        threshold: float | None = 0.01,
    ) -> list[SearchResult]:
        """Search a sequence in the pangenome index (wraps search_sequence with IndexType.pangenome)."""
        return self.search_sequence(
            name, sequence, IndexType.pangenome, mode, threshold
        )

    def search_sequence_g(
        self,
        name: str,
        sequence: str,
        mode: SearchMode = SearchMode.jaccard,
        threshold: float | None = 0.01,
    ) -> list[SearchResult]:
        """Search a sequence in the genome index (wraps search_sequence with IndexType.genome)."""
        return self.search_sequence(name, sequence, IndexType.genome, mode, threshold)

    def search_sequence(
        self,
        name: str,
        sequence: str,
        index_type: IndexType,
        mode: SearchMode = SearchMode.jaccard,
        threshold: float | None = 0.01,
    ) -> list[SearchResult]:
        """Sketch a sequence and search it in the given index.

        Returns:
            One SearchResult per match, possibly empty.
        """
        sig = IndexBuilder.sequence_signature(
            name,
            sequence,
            k=self.info.kmer_size,
            n=self.info.n,
            scaled=self.info.scaled,
        )
        return self.search_signature(sig, index_type, mode, threshold)

    def search_genome_p(
        self,
        name: str,
        genome: Path,
        mode: SearchMode = SearchMode.jaccard,
        threshold: float | None = 0.01,
    ) -> list[SearchResult]:
        """Search a genome in the pangenome index (wraps search_genome with IndexType.pangenome)."""
        return self.search_genome(name, genome, IndexType.pangenome, mode, threshold)

    def search_genome_g(
        self,
        name: str,
        genome: Path,
        mode: SearchMode = SearchMode.jaccard,
        threshold: float | None = 0.01,
    ) -> list[SearchResult]:
        """Search a genome in the genome index (wraps search_genome with IndexType.genome)."""
        return self.search_genome(name, genome, IndexType.genome, mode, threshold)

    def search_genome(
        self,
        name: str,
        genome: Path,
        index_type: IndexType,
        mode: SearchMode = SearchMode.jaccard,
        threshold: float | None = 0.01,
    ) -> list[SearchResult]:
        """Sketch a genome file and search it in the given index.

        Returns:
            One SearchResult per match, possibly empty.
        """
        print(self.info.kmer_size, self.info.n, self.info.scaled)
        sig = IndexBuilder.file_signature(
            name, genome, k=self.info.kmer_size, n=self.info.n, scaled=self.info.scaled
        )
        return self.search_signature(sig, index_type, mode, threshold)

    def search_signature(
        self,
        signature: SourmashSignature,
        index_type: IndexType,
        mode: SearchMode = SearchMode.jaccard,
        threshold: float | None = 0.01,
    ) -> list[SearchResult]:
        """Search a signature in the given index.

        Returns:
            One SearchResult per match, possibly empty.
        """
        do_containment, do_max_containment = {
            SearchMode.jaccard: (False, False),
            SearchMode.containment: (True, False),
            SearchMode.max_containment: (False, True),
        }[mode]

        res = self._index(index_type).search(
            signature,
            threshold=threshold,
            do_containment=do_containment,
            do_max_containment=do_max_containment,
        )
        return self._search_results(signature, res)

    def gather_signature(
        self,
        signature: SourmashSignature,
        index_type: IndexType,
        threshold: float = 0.0,
    ) -> list[tuple]:
        """Greedy min-set-cover (gather) over the index.

        Returns:
            (name, f_query, f_match) per selection round, where f_query is the fraction of
            the whole sample newly explained and f_match is the match covered breadth.
        """
        index = self._index(index_type)
        query_mh = signature.minhash
        total = len(query_mh)
        if total == 0:
            return []

        remaining = query_mh.to_mutable()
        out: list[tuple] = []
        while len(remaining) > 0:
            matches = index.search(
                SourmashSignature(remaining.to_frozen()),
                threshold=threshold,
                do_containment=True,
            )
            if not matches:
                break
            best_m, best_ov, best_mh = None, 0, None
            for m in matches:
                mh = m.signature.minhash
                ov = remaining.count_common(mh, downsample=True)
                if ov > best_ov:
                    best_m, best_ov, best_mh = m, ov, mh
            if best_m is None or best_ov == 0:
                break
            assert best_mh is not None
            remaining.remove_many(best_mh.hashes)
            out.append(
                (
                    best_m.signature.name,
                    round(best_ov / total, 4),
                    round(best_ov / len(best_mh), 4) if len(best_mh) else 0.0,
                )
            )
        return out
