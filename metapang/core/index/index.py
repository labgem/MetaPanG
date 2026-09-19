import json
import os
import signal
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from multiprocessing import Lock, get_context
from multiprocessing.managers import BaseManager
from pathlib import Path

import gb_io
from pyfastx import Fastx
from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn
from sourmash import MinHash, SourmashSignature
from sourmash.sbt import SBT, GraphFactory

from metapang.logger import mp_log_error, mp_log_info
from metapang.utils.io import is_fastx, silence, zopen
from metapang.utils.parallel import BoundedProcessPoolExecutor

_MP_CONTEXT = get_context("forkserver")


def _ignore_sigint() -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)


LOCK = Lock()


@dataclass
class IndexBuildConfig:
    """Configuration for the index building process."""

    kmer_size: int
    scaled: int
    n: int
    pangenomes: list[tuple[str, list[Path]]]
    output: Path
    genome_index_name: str = "genome_index.sbt.zip"
    pangenome_index_name: str = "pangenome_index.sbt.zip"
    use_parent_directory_as_genome_id: bool = False


@dataclass
class IndexInfo:
    """Metadata describing a built index (file names, sketch params, pangenomes)."""

    genome_index: str
    pangenome_index: str
    kmer_size: int
    scaled: int
    n: int
    pangenomes: dict[str, list[str]] = field(default_factory=dict)

    def save_json(self, output: Path):
        """Save the index information as a JSON file."""
        with open(output, "w") as f:
            json.dump(asdict(self), f, indent=4)

    @staticmethod
    def load_json(file: Path) -> "IndexInfo":
        """Load the index information from a JSON file."""
        with open(file) as f:
            data = json.load(f)
        return IndexInfo(**data)


class SBTManager(BaseManager):
    """BaseManager subclass used to share SBT instances across processes."""

    pass


class MinHashManager(BaseManager):
    """BaseManager subclass used to share MinHash instances across processes."""

    pass


def make_pangenome_signature_name(
    pangenome_id: str, genome_file: Path, use_parent_as_name: bool = False
) -> str:
    """Build a pangenome signature name, i.e. {pangenome_id}@{genome stem or parent name}."""
    if not use_parent_as_name:
        return f"{pangenome_id}@{genome_file.stem}"
    else:
        return f"{pangenome_id}@{genome_file.parent.name}"


class IndexBuilder:
    """Construct a MetaPanG index."""

    def __init__(self, config: IndexBuildConfig):
        self._config = config

    @staticmethod
    def sequence_minhash(
        sequence: str, k: int, n: int, scaled: int, force: bool = True
    ) -> MinHash:
        """Compute a Sourmash MinHash sketch from a sequence."""
        m = MinHash(n=n, ksize=k, scaled=scaled)
        m.add_sequence(sequence, force=force)
        return m

    @staticmethod
    def add_sequence_minhash(
        mh: MinHash, sequence: str, k: int, n: int, scaled: int, force: bool = True
    ) -> None:
        """Sketch a sequence and merge it into an existing MinHash."""
        m = MinHash(ksize=k, n=n, scaled=scaled)
        m.add_sequence(sequence, force=force)
        mh.merge(m)

    @staticmethod
    def add_sequences_minhash(
        mh: MinHash,
        sequences: Iterable[str],
        k: int,
        n: int,
        scaled: int,
        force: bool = True,
    ) -> None:
        """Sketch several sequences and merge them into an existing MinHash (LOCK-guarded)."""
        m = MinHash(ksize=k, n=n, scaled=scaled)
        for sequence in sequences:
            m.add_sequence(sequence, force=force)
        with LOCK:
            mh.merge(m)

    @staticmethod
    def sequence_signature(
        name: str, sequence: str, k: int, n: int, scaled: int, force: bool = True
    ) -> SourmashSignature:
        """Compute a Sourmash signature from a sequence."""
        return SourmashSignature(
            IndexBuilder.sequence_minhash(sequence, k, n, scaled, force), name=name
        )

    @staticmethod
    def sequence_batch_minhash(
        sequences: Iterable[str], k: int, n: int, scaled: int, force: bool = True
    ) -> MinHash:
        """Compute a Sourmash MinHash sketch from a batch of sequences."""
        m = MinHash(n=n, ksize=k, scaled=scaled)
        for sequence in sequences:
            m.add_sequence(sequence, force=force)
        return m

    @staticmethod
    def sequence_batch_signature(
        name: str,
        sequences: Iterable[str],
        k: int,
        n: int,
        scaled: int,
        force: bool = True,
    ) -> SourmashSignature:
        """Compute a Sourmash signature from a batch of sequences."""
        return SourmashSignature(
            IndexBuilder.sequence_batch_minhash(sequences, k, n, scaled, force),
            name=name,
        )

    @staticmethod
    def file_minhash(
        file: Path, k: int, n: int, scaled: int, force: bool = True
    ) -> MinHash:
        """Compute a Sourmash MinHash sketch from a file (fasta/fastq/gzipped)."""
        m = MinHash(n=n, ksize=k, scaled=scaled)
        if not is_fastx(file):
            with zopen(file, "rb") as file_io:
                for record in gb_io.iter(file_io):
                    m.add_sequence(record.sequence.decode("utf-8"), force=force)
        else:
            for record in Fastx(file):
                m.add_sequence(record[1], force=force)
        return m

    @staticmethod
    def file_signature(
        name: str, file: Path, k: int, n: int, scaled: int, force: bool = True
    ) -> SourmashSignature:
        """Compute a Sourmash signature from a file (fasta/fastq/gzipped)."""
        return SourmashSignature(
            IndexBuilder.file_minhash(file, k, n, scaled, force), name=name
        )

    @staticmethod
    def pangenome_signature(
        name: str,
        genomes: list[Path],
        k: int,
        n: int,
        scaled: int,
        force: bool = True,
        use_parent: bool = False,
    ) -> tuple[SourmashSignature, list[SourmashSignature]]:
        """Compute a pangenome signature from a list of genomes.

        Returns:
            The merged pangenome signature and the per-genome signatures.
        """
        signatures = []
        m = MinHash(n=n, ksize=k, scaled=scaled)
        for genome in genomes:
            sg = IndexBuilder.file_signature(
                make_pangenome_signature_name(name, genome, use_parent),
                genome,
                k,
                n,
                scaled,
                force,
            )
            m.merge(sg.minhash)
            signatures.append(sg)
        return SourmashSignature(m, name=name), signatures

    @staticmethod
    def add_signature_to_sbt(
        sbt: SBT, signatures: SourmashSignature | list[SourmashSignature]
    ):
        """Add one or several Sourmash signatures to an SBT."""
        if isinstance(signatures, SourmashSignature):
            signatures = [signatures]
        for signature in signatures:
            sbt.insert(signature)

    @staticmethod
    def pangenome_construct(
        pangenome_id: str,
        genomes: list[Path],
        genome_sbt: SBT,
        pangenome_sbt: SBT,
        k: int,
        n: int,
        scaled: int,
        use_parent: bool = False,
    ) -> None:
        """Construct a pangenome signature and add it to the genome and pangenome SBTs."""
        pangenome_signature, genome_signatures = IndexBuilder.pangenome_signature(
            pangenome_id, genomes, k, n, scaled, use_parent=use_parent
        )
        IndexBuilder.add_signature_to_sbt(genome_sbt, genome_signatures)
        IndexBuilder.add_signature_to_sbt(pangenome_sbt, pangenome_signature)

    @staticmethod
    def file_batch_signature(
        file: "Path | list[Path]",
        k: int,
        scaled: int,
        n: int,
        force: bool,
        nb_cores: int,
        queue_size: int,
        batch_size: int,
        with_log: bool = True,
    ) -> SourmashSignature:
        """Compute one Sourmash signature for one or several files, in parallel batches.

        Several files (e.g. paired-end or split reads) are folded into a single MinHash,
        so the result is one signature for the whole sample.
        """
        files = [file] if isinstance(file, (str, Path)) else list(file)

        man = MinHashManager(ctx=_MP_CONTEXT)
        man.register("MinHash", MinHash)
        man.start()
        m = man.MinHash(n=n, ksize=k, scaled=scaled)

        with BoundedProcessPoolExecutor(
            queue_size,
            max_workers=nb_cores,
            mp_context=_MP_CONTEXT,
            initializer=_ignore_sigint,
        ) as executor:
            try:
                sequences = []
                i = 0
                for f in files:
                    if is_fastx(f):
                        for record in Fastx(f):
                            sequences.append(record[1])
                            i += 1
                            if i % batch_size == 0:
                                executor.submit(
                                    IndexBuilder.add_sequences_minhash,
                                    m,
                                    sequences,
                                    k,
                                    n,
                                    scaled,
                                    force,
                                )
                                sequences = []
                    else:
                        with zopen(f, "rb") as file_io:
                            for record in gb_io.iter(file_io):
                                sequences.append(record.sequence.decode("utf-8"))
                                i += 1
                                if i % batch_size == 0:
                                    executor.submit(
                                        IndexBuilder.add_sequences_minhash,
                                        m,
                                        sequences,
                                        k,
                                        n,
                                        scaled,
                                        force,
                                    )
                                    sequences = []

                if sequences:
                    executor.submit(
                        IndexBuilder.add_sequences_minhash,
                        m,
                        sequences,
                        k,
                        n,
                        scaled,
                        force,
                    )

            except KeyboardInterrupt:
                mp_log_error(with_log, "Interrupted by user (Ctrl+C)")
                executor.shutdown(wait=False)
                os._exit(1)

        signature = SourmashSignature(m.copy(), name=files[0].stem)
        man.shutdown()
        return signature

    def construct(self, nb_cores: int, with_log: bool = True) -> IndexInfo:
        """Construct and save the index, returning its IndexInfo."""
        with silence():
            manager = SBTManager(ctx=_MP_CONTEXT)
            manager.register(
                "SBT", SBT, exposed=("insert", "save", "_fill_min_n_below")
            )
            manager.start()

        genome_sbt = manager.SBT(GraphFactory(1, 1e5, 4), d=2)
        pangenome_sbt = manager.SBT(GraphFactory(1, 1e5, 4), d=2)

        info = IndexInfo(
            self._config.genome_index_name,
            self._config.pangenome_index_name,
            self._config.kmer_size,
            self._config.scaled,
            self._config.n,
        )

        with ProcessPoolExecutor(
            max_workers=nb_cores, mp_context=_MP_CONTEXT, initializer=_ignore_sigint
        ) as executor:
            try:
                futures = {}
                for pangenome_id, genomes in self._config.pangenomes:
                    info.pangenomes[pangenome_id] = [
                        g.stem
                        if not self._config.use_parent_directory_as_genome_id
                        else g.parent.stem
                        for g in genomes
                    ]

                    f = executor.submit(
                        IndexBuilder.pangenome_construct,
                        pangenome_id,
                        genomes,
                        genome_sbt,
                        pangenome_sbt,
                        self._config.kmer_size,
                        self._config.n,
                        self._config.scaled,
                        self._config.use_parent_directory_as_genome_id,
                    )
                    futures[f] = pangenome_id

                if with_log:
                    with Progress(
                        *Progress.get_default_columns(),
                        TimeElapsedColumn(),
                        MofNCompleteColumn(),
                    ) as progress:
                        task = progress.add_task(
                            "[bold]MetaPanG[Index][/]", total=len(futures)
                        )
                        for _ in as_completed(futures):
                            progress.update(task, advance=1)
            except KeyboardInterrupt:
                mp_log_error(with_log, "Interrupted by user (Ctrl+C)")
                executor.shutdown(wait=False)
                os._exit(1)

        genome_sbt._fill_min_n_below()
        pangenome_sbt._fill_min_n_below()

        mp_log_info(
            with_log,
            f"Saving '{self._config.genome_index_name}' at '{self._config.output}'",
        )
        genome_sbt.save(
            str(self._config.output / self._config.genome_index_name), sparseness=0.0
        )
        mp_log_info(
            with_log,
            f"Saving '{self._config.pangenome_index_name}' at '{self._config.output}'",
        )
        pangenome_sbt.save(
            str(self._config.output / self._config.pangenome_index_name), sparseness=0.0
        )
        mp_log_info(with_log, f"Saving index info at '{self._config.output}'")
        info.save_json(self._config.output / "index_info.json")

        manager.shutdown()
        return info
