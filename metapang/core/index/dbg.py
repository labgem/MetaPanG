import os
from typing import Literal
from pathlib import Path

from metapang.logger import mp_log
from metapang.utils.io import smart_io
from metapang.utils.time import timer
from metapang.utils.execution import find_executable, cli_dataclass, cli_field
from metapang.utils.execution import CLIExecutor
from metapang.exceptions import MetaPanG_ConfigError
import msgspec

@cli_dataclass
class MetagraphBuildOptions:
    """Options for the metagraph `build` command."""
    inputs: list[str] = cli_field(list[str], positional=True, stdin=True)
    outfile_base: str = cli_field(str)
    min_count: int = cli_field(int, default=1)
    max_count: int | None = cli_field(int | None, default=None)
    min_count_q: float | None = cli_field(float | None, default=None)
    max_count_q: float | None = cli_field(float | None, default=None)

    inplace: bool = cli_field(bool, default=False, flag=True)
    complete: bool = cli_field(bool, default=False, flag=True)

    count_kmers: bool = cli_field(bool, default=False, flag=True)
    count_width: int | None = cli_field(int | None, default=None)

    mem_cap_gb: int | None = cli_field(int | None, default=None)
    index_ranges: int | None = cli_field(int | None, default=None)
    disk_swap: str | None = cli_field(str | None, default=None)

    kmer_length: int = cli_field(int, default=31)
    graph: Literal["succinct", "bitmap", "hash", "hashstr", "hashfast"] = cli_field(
        Literal["succinct", "bitmap", "hash", "hashstr", "hashfast"],
        default="succinct"
    )
    state: Literal["small", "dynamic", "stat", "fast"] = cli_field(
        Literal["small", "dynamic", "stat", "fast"],
        default="small"
    )
    mode: Literal["basic", "canonical", "primary"] = cli_field(
        Literal["basic", "canonical", "primary"],
        default="basic"
    )
    parallel: int = cli_field(int, default=1)

@cli_dataclass
class MetagraphTransformOptions:
    """Options for the metagraph `transform` command."""
    graph: str = cli_field(str, positional=True)
    outfile_base: str = cli_field(str)
    to_fasta: bool = cli_field(bool, default=False, flag=True)
    primary_kmers: bool = cli_field(bool, default=False, flag=True)
    parallel: int = cli_field(int, default=1)

@cli_dataclass
class MetagraphAnnotateOptions:
    """Options for the metagraph `annotate` command."""
    inputs: list[str] = cli_field(list[str], positional=True, stdin=True)
    i: str = cli_field(str, prefix="-")
    outfile_base: str = cli_field(str)
    anno_header: bool = cli_field(bool, default=False, flag=True)
    anno_filename: str = cli_field(bool, default=False, flag=True)
    parallel: int = cli_field(int, default=1)

@cli_dataclass
class MetagraphRelaxOptions:
    """Options for the metagraph `relax_brwt` command."""
    annotator: str = cli_field(str, positional=True)
    outfile_base: str = cli_field(str)
    relax_arity: int = cli_field(int, default=10)
    parallel: int = cli_field(int, default=1)

@cli_dataclass
class MetagraphQueryOptions:
    """Options for the metagraph `query` command."""
    output_file: str
    i: str = cli_field(str, prefix="-")
    a: str = cli_field(str, prefix="-")
    query_file: "str | list[str]" = cli_field(str, positional=True)  # one or several query files
    json: bool = cli_field(bool, default=False, flag=True)
    query_mode: Literal["labels", "matches"] = cli_field(
        Literal["labels", "matches"],
        default="labels"
    )
    num_top_labels: int | None = cli_field(int, default=None)
    min_kmers_fraction_label : float = cli_field(float, default=0.7)
    min_kmers_fraction_graph : float = cli_field(float, default=0.0)
    batch_size: int | None = cli_field(int | None, default=None)
    mmap: bool = cli_field(bool, default=True, flag=True)
    parallel: int = cli_field(int, default=1)

@cli_dataclass
class MetagraphAlignOptions:
    """Options for the metagraph `align` command."""
    pass

@cli_dataclass
class MetagraphVersion:
    """Options for the metagraph `--version` command."""
    pass

@cli_dataclass
class MetagraphTransformAnnoOptions:
    """Options for the metagraph `transform_anno` command."""
    inputs: list[str] = cli_field(list[str], positional=True, stdin=True)
    i: str = cli_field(str, prefix="-")
    o: str = cli_field(str, prefix="-")
    anno_type: str | None = cli_field(str | None, default=None)
    row_diff_stage: int | None = cli_field(int | None, default=None)
    greedy: bool = cli_field(bool, default=False, flag=True)
    parallel: int = cli_field(int, default=1)
    subsample: int | None = cli_field(int | None, default=None)
    rename_cols: str | None = cli_field(str | None, default=None)

class MetagraphCLI(CLIExecutor):
    """Wrapper around the metagraph CLI binary."""
    def __init__(self, executable: str="metagraph", wd: str = os.getcwd(), paths: list[str] = []):
        self._exe = find_executable(executable, paths)
        self._wd = wd

    def build(self, options: MetagraphBuildOptions, wd = None) -> tuple[int, str, str]:
        """Run the metagraph `build` command."""
        return self._execute(self._exe, "build", options, wd)

    def transform(self, options: MetagraphTransformOptions, wd = None) -> tuple[int, str, str]:
        """Run the metagraph `transform` command."""
        return self._execute(self._exe, "transform", options, wd)

    def annotate(self, options: MetagraphAnnotateOptions, wd = None) -> tuple[int, str, str]:
        """Run the metagraph `annotate` command."""
        return self._execute(self._exe, "annotate", options, wd)

    def query(self, options: MetagraphQueryOptions, wd = None) -> tuple[int, str, str]:
        """Run the metagraph `query` command, writing results to the output file."""
        with smart_io(options.output_file) as f:
            return self._execute(self._exe, "query", options, wd, False, True, stdout_file=f)

    def align(self, options: MetagraphAlignOptions, wd = None) -> tuple[int, str, str]:
        """Run the metagraph `align` command."""
        return self._execute(self._exe, "align", options, wd)

    def transform_anno(self, options: MetagraphTransformAnnoOptions, wd = None) -> tuple[int, str, str]:
        """Run the metagraph `transform_anno` command."""
        return self._execute(self._exe, "transform_anno", options, wd)

    def relax_brwt(self, options: MetagraphRelaxOptions, wd = None) -> tuple[int, str, str]:
        """Run the metagraph `relax_brwt` command."""
        return self._execute(self._exe, "relax_brwt", options, wd)

    def version(self) -> str:
        """Return the metagraph binary version string."""
        r = self._execute(self._exe, "--version", MetagraphVersion(), None, True, True)
        return r[1].decode().strip().split(":")[-1].strip()


class MetagraphPipeline:
    """Base class for metagraph CLI pipelines."""
    def __init__(self, cli: MetagraphCLI, wd: str = None):
        self._cli = cli

    @property
    def cli(self) -> MetagraphCLI:
        return self._cli

class MetagraphBuildPipelineOptions(msgspec.Struct):
    """Configuration for the metagraph build pipeline."""
    inputs: list[str]
    annotation_inputs: list[str]
    name: str
    tmp_dir: str
    output_dir: str
    kmer_size: int = msgspec.field(default=31)
    parallel: int = msgspec.field(default=1)
    subsample: int = msgspec.field(default=100000)
    anno_header: bool = msgspec.field(default=True)
    anno_filename: bool = msgspec.field(default=False)
    suffix: str = msgspec.field(default="")

    annotation_type: Literal["columns", "rainbowfish", "brwt", "rd_brwt", "rd_sparse"] = msgspec.field(default="rd_brwt")

class MetagraphBuildPipeline(MetagraphPipeline):
    """Build a de Bruijn graph and its annotation via the metagraph CLI."""
    def __init__(self, cli: MetagraphCLI, options: MetagraphBuildPipelineOptions | None = None):
        super().__init__(cli)
        self.options = options

    def _basic_graph(self):
        opt = MetagraphBuildOptions(
            inputs=self.options.inputs,
            outfile_base=f"{self.options.name}_graph",
            kmer_length=self.options.kmer_size,
            parallel=self.options.parallel,
            mode="basic"
        )
        self.cli.build(opt, wd=self.options.tmp_dir)

    def _canonical_graph(self):
        opt = MetagraphBuildOptions(
            inputs=self.options.inputs,
            outfile_base=f"{self.options.name}_graph",
            kmer_length=self.options.kmer_size,
            parallel=self.options.parallel,
            mode="canonical"
        )
        self.cli.build(opt, wd=self.options.tmp_dir)

    def _primary_graph(self):
        if Path(f"{self.options.name}.dbg").exists():
            return

        self._canonical_graph()
        opt = MetagraphTransformOptions(
            graph=f"{self.options.name}_graph.dbg",
            outfile_base=f"{self.options.name}_primary_contigs",
            to_fasta=True,
            primary_kmers=True,
            parallel=self.options.parallel
        )
        self.cli.transform(opt, wd=self.options.tmp_dir)
        opt = MetagraphBuildOptions(
            inputs=[f"{self.options.name}_primary_contigs.fasta.gz"],
            outfile_base=self.options.name,
            kmer_length=self.options.kmer_size,
            parallel=self.options.parallel,
            mode="primary"
        )
        self.cli.build(opt, wd=self.options.tmp_dir)

    def _annotation_columns(self):
        opt = MetagraphAnnotateOptions(
            inputs=self.options.annotation_inputs,
            i=f"{self.options.name}.dbg",
            outfile_base=f"{self.options.name}_annotation",
            anno_header=self.options.anno_header,
            anno_filename=self.options.anno_filename,
            parallel=self.options.parallel
        )
        self.cli.annotate(opt, wd=self.options.tmp_dir)

        if self.options.anno_filename:
            with open(f"{self.options.tmp_dir}/rename.txt", "w") as rf:
                for f in self.options.inputs:
                    rf.write(f"{f} {Path(f).name}\n")

            opt = MetagraphTransformAnnoOptions(
                inputs=[f"{self.options.name}_annotation.column.annodbg"],
                rename_cols=f"{self.options.tmp_dir}/rename.txt",
                o=f"{self.options.name}_annotation",
                anno_type=None,
                row_diff_stage=None
            )

            self.cli.transform_anno(opt, wd=self.options.tmp_dir)

    def _annotation_rainbowfish(self):
        self._annotation_columns()
        opt = MetagraphTransformAnnoOptions(
            inputs=[f"{self.options.name}_annotation.column.annodbg"],
            o=f"{self.options.name}_annotation",
            anno_type="row",
            parallel=self.options.parallel
        )
        self.cli.transform_anno(opt, wd=self.options.tmp_dir)
        opt = MetagraphTransformAnnoOptions(
            inputs=[f"{self.options.name}_annotation.row.annodbg"],
            anno_type="rbfish",
            o=f"{self.options.name}_annotation",
        )
        self.cli.transform_anno(opt, wd=self.options.tmp_dir)

    def _annotation_brwt(self):
        self._annotation_columns()
        opt = MetagraphTransformAnnoOptions(
            inputs=[f"{self.options.name}_annotation.column.annodbg"],
            o=f"{self.options.name}_annotation",
            anno_type="brwt",
            greedy=True,
            parallel=self.options.parallel
        )
        self.cli.transform_anno(opt, wd=self.options.tmp_dir)
        opt = MetagraphRelaxOptions(
            annotator=f"{self.options.name}_annotation.brwt.annodbg",
            outfile_base=f"{self.options.name}_annotation_relaxed",
            parallel=self.options.parallel
        )
        self.cli.relax_brwt(opt, wd=self.options.tmp_dir)
        Path(f"{self.options.name}_annotation_relaxed.brwt.annodbg").rename(f"{self.options.name}_annotation.brwt.annodbg.tmp")

    def _annotation_rd_brwt(self):
        self._annotation_columns()
        opt = MetagraphTransformAnnoOptions(
            inputs=[f"{self.options.name}_annotation.column.annodbg"],
            i=f"{self.options.name}.dbg",
            anno_type="row_diff",
            row_diff_stage=0,
            o=f"{self.options.name}.row_count",
            parallel=self.options.parallel,
            subsample=self.options.subsample
        )
        self.cli.transform_anno(opt, wd=self.options.tmp_dir)
        opt.row_diff_stage = 1
        opt.o = f"{self.options.name}.row_reduction"
        self.cli.transform_anno(opt, wd=self.options.tmp_dir)
        opt.row_diff_stage = 2
        opt.o = "required_but_not_used"
        self.cli.transform_anno(opt, wd=self.options.tmp_dir)

        opt.inputs = [f"{self.options.name}_annotation.row_diff.annodbg"]
        opt.anno_type = "row_diff_brwt"
        opt.greedy = True
        opt.o = f"{self.options.name}_annotation"
        self.cli.transform_anno(opt, wd=self.options.tmp_dir)

        opt = MetagraphRelaxOptions(
            annotator=f"{self.options.name}_annotation.row_diff_brwt.annodbg",
            outfile_base=f"{self.options.name}_annotation_relaxed",
            parallel=self.options.parallel
        )

        self.cli.relax_brwt(opt, wd=self.options.tmp_dir)

    def _annotation_rd_sparse(self):
        self._annotation_columns()
        opt = MetagraphTransformAnnoOptions(
            inputs=[f"{self.options.name}_annotation.column.annodbg"],
            i=f"{self.options.name}.dbg",
            anno_type="row_diff",
            row_diff_stage=0,
            o=f"{self.options.name}.row_count",
            parallel=self.options.parallel,
            subsample=self.options.subsample
        )
        self.cli.transform_anno(opt, wd=self.options.tmp_dir)
        opt.row_diff_stage = 1
        opt.o = f"{self.options.name}.row_reduction"
        self.cli.transform_anno(opt, wd=self.options.tmp_dir)
        opt.row_diff_stage = 2
        opt.o = "required_but_not_used"
        self.cli.transform_anno(opt, wd=self.options.tmp_dir)

        opt.inputs = [f"{self.options.name}_annotation.row_diff.annodbg"]
        opt.anno_type = "row_diff_sparse"
        opt.greedy = True
        opt.o = f"{self.options.name}_annotation"
        self.cli.transform_anno(opt, wd=self.options.tmp_dir)


    def run(self, options: MetagraphBuildPipelineOptions | None = None, *,
                  skip_graph: bool = False, move_graph: bool = False):
        """Run the full build pipeline (graph construction and annotation)."""
        if options is not None:
            self.options = options

        if not self.options:
            raise MetaPanG_ConfigError("Metagraph pipeline: options are not set")

        if not Path(self.options.output_dir).exists():
            Path(self.options.output_dir).mkdir(parents=True)

        tmp_prefix = f"{self.options.tmp_dir}/{self.options.name}"
        out_prefix = f"{self.options.output_dir}/{self.options.name}{self.options.suffix}"

        with timer(f"Metagraph pipeline: {self.options.name}") as t:

            if not skip_graph:
                mp_log.info("Step 1. DBG Construction")
                self._primary_graph()
                t.step("primary graph")
                mp_log.info(f"Step 1. Done {t.get_last_step().format()}")

            mp_log.info("Step 2. DBG Annotation")
            match self.options.annotation_type:
                case "columns":
                    self._annotation_columns()
                    Path(f"{tmp_prefix}_annotation.column.annodbg").replace(f"{out_prefix}.column.annodbg")
                    t.step("annotation columns")
                case "rainbowfish":
                    self._annotation_rainbowfish()
                    Path(f"{tmp_prefix}_annotation.rbfish.annodbg").replace(f"{out_prefix}.rbfish.annodbg")
                    t.step("annotation rainbowfish")
                case "brwt":
                    self._annotation_brwt()
                    Path(f"{tmp_prefix}_annotation.brwt.annodbg").replace(f"{out_prefix}.brwt.annodbg")
                    t.step("annotation brwt")
                case "rd_brwt":
                    self._annotation_rd_brwt()
                    Path(f"{tmp_prefix}_annotation_relaxed.row_diff_brwt.annodbg").replace(f"{out_prefix}.row_diff_brwt.annodbg")
                    t.step("annotation row_diff_brwt")
                case "rd_sparse":
                    self._annotation_rd_sparse()
                    Path(f"{tmp_prefix}_annotation.row_diff_sparse.annodbg").replace(f"{out_prefix}.row_diff_sparse.annodbg")
                    t.step("annotation row_diff_sparse")
                case _:
                    raise MetaPanG_ConfigError(f"Metagraph pipeline: unknown annotation type {self.options.annotation_type}")
            t.step("annotation")

            if move_graph:
                Path(f"{tmp_prefix}.dbg").replace(f"{self.options.output_dir}/{self.options.name}.dbg")

            mp_log.info(f"Step 2. Done {t.get_last_step().format()}")

