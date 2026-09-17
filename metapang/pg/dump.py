from metapang.utils.io import zopen

import tables
from pathlib import Path


def get_gene_families(h5f: tables.File, families: set) -> tuple[set, dict]:
    """Return the genes belonging to the given families and a gene-to-family mapping."""
    from ppanggolin.formats.readBinaries import read_chunks
    matching_genes = set()

    gene_fam_table = h5f.root.geneFamilies
    mapping = {}

    for row in read_chunks(gene_fam_table, chunk=20000):
        if row["geneFam"] in families:
            mapping[row["gene"]] = row["geneFam"]
            matching_genes.add(row["gene"])
    return matching_genes, mapping


from collections import defaultdict
import os


def pg_fam_from_h5(
    pangenome: Path,
    output: Path,
    compress: bool,
    split: bool = False,
    filter: str = "all",
) -> None:
    """Dump family sequences from a pangenome (FASTA headers/filenames are family IDs).

    Args:
        output: Output file, or output directory when split is True.
        split: Write each family to a separate file.
        filter: Partition filter in ["persistent", "shell", "cloud", "all"].
    """
    from ppanggolin.formats.readBinaries import read_chunks

    with tables.open_file(str(pangenome), "r", driver_core_backing_store=0) as h5:
        gene_fam = h5.root.geneFamilies
        gene_seq = h5.root.annotations.geneSequences
        sequences = h5.root.annotations.sequences
        info = h5.root.geneFamiliesInfo

        selected = set()
        if filter in ("persistent", "shell", "cloud"):
            c = filter[0].upper()

            for row in read_chunks(info, chunk=20000):
                if row["partition"].decode().startswith(c):
                    selected.add(row["name"])

        gene_seq_map = {}
        for row in read_chunks(gene_seq, chunk=20000):
            gene_seq_map[row["gene"]] = row["seqid"]

        gene_fam_map = {}
        for row in read_chunks(gene_fam, chunk=20000):
            if selected and row["geneFam"] in selected:
                gene_fam_map[gene_seq_map[row["gene"]]] = row["geneFam"]
            else:
                gene_fam_map[gene_seq_map[row["gene"]]] = row["geneFam"]

        if split:
            to_write = defaultdict(list)
            for row in read_chunks(sequences, chunk=10000):
                to_write[gene_fam_map[row["seqid"]]].append(row["dna"])

            os.makedirs(output, exist_ok=True)
            for k, v in to_write.items():
                with zopen(
                    f"{output}/{k.decode()}.fa", mode="w", compress=compress
                ) as fout:
                    for x in v:
                        fout.write(f">{k.decode()}\n") # type: ignore
                        fout.write(x.decode() + "\n")
        else:
            with zopen(output, mode="wt", compress=compress) as fout:
                for row in read_chunks(sequences, chunk=10000):
                    fout.write(
                        f">{gene_fam_map[row['seqid']].decode()}\n{row['dna'].decode()}\n" # type: ignore
                    ) # type: ignore


def pg_gene_from_h5(
    pangenome: Path, output: Path, compress: bool, filter: str = "all"
) -> None:
    """Dump all gene sequences from a pangenome.

    Args:
        filter: Partition filter in ["persistent", "shell", "cloud", "all"].
    """
    from ppanggolin.formats.readBinaries import (
        get_families_matching_partition, get_seqid_to_genes,
        write_genes_seq_from_pangenome_file)
    with tables.open_file(str(pangenome), "r", driver_core_backing_store=0) as h5:
        if filter in ("persistent", "shell", "cloud"):
            fam = get_families_matching_partition(h5, filter)
            to_write, _ = get_gene_families(h5, fam)
        else:
            to_write = set()

        seq_id = get_seqid_to_genes(
            h5, to_write, get_all_genes=len(to_write) == 0, disable_bar=True
        )
        write_genes_seq_from_pangenome_file(
            h5, output, compress, seq_id, disable_bar=True
        )


def pg_repr_from_h5(
    pangenome: Path, output: Path, compress: bool, filter: str = "all"
) -> None:
    """Dump representative gene sequences from a pangenome.

    Args:
        filter: Partition filter in ["persistent", "shell", "cloud", "all"].
    """
    from ppanggolin.formats.readBinaries import (
        get_families_matching_partition, get_seqid_to_genes,
        write_genes_seq_from_pangenome_file)
    with tables.open_file(str(pangenome), "r", driver_core_backing_store=0) as h5:
        fam = get_families_matching_partition(h5, filter)
        seq_id = get_seqid_to_genes(h5, set(fam), disable_bar=True)
        write_genes_seq_from_pangenome_file(
            h5, output, compress, seq_id, disable_bar=True
        )
