from metapang.core.index.dbg import MetagraphBuildOptions, MetagraphQueryOptions


def _val(args, key):
    return args[args.index(key) + 1]


def test_build_options_render():
    opt = MetagraphBuildOptions(
        inputs=["a.fa", "b.fa"],
        outfile_base="out",
        kmer_length=31,
        parallel=4,
        inplace=True,
    )
    cli = opt.get_cli()
    assert _val(cli, "--outfile-base") == "out"
    assert _val(cli, "--kmer-length") == "31"
    assert _val(cli, "--parallel") == "4"
    assert "--inplace" in cli
    assert "--complete" not in cli
    assert "a.fa" not in cli


def test_build_options_inputs_go_to_stdin():
    opt = MetagraphBuildOptions(inputs=["a.fa", "b.fa"], outfile_base="out")
    assert opt.get_cli_input() == "a.fa\nb.fa"


def test_query_options_render():
    opt = MetagraphQueryOptions(
        output_file="out.tsv",
        i="graph.dbg",
        a="anno.annodbg",
        query_file="reads.fa",
        query_mode="matches",
        parallel=8,
    )
    cli = opt.get_cli()
    assert _val(cli, "-i") == "graph.dbg"
    assert _val(cli, "-a") == "anno.annodbg"
    assert _val(cli, "--query-mode") == "matches"
    assert _val(cli, "--parallel") == "8"
    assert "reads.fa" in cli
    assert "out.tsv" not in cli


def test_query_options_flag_off_by_default():
    opt = MetagraphQueryOptions(output_file="o", i="g", a="an", query_file="q")
    assert "--json" not in opt.get_cli()
