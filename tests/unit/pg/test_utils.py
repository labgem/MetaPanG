from metapang.pg.utils import colors


def test_colors_persistent():
    assert colors("P") == "#e59c04"
    assert colors("persistent") == "#e59c04"


def test_colors_shell():
    assert colors("S") == "#00d860"
    assert colors("shell") == "#00d860"


def test_colors_cloud():
    assert colors("C") == "#79deff"
    assert colors("cloud") == "#79deff"


def test_colors_unknown():
    assert colors("X") == "#d62728"
    assert colors("") == "#d62728"
