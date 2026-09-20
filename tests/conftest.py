from pathlib import Path

import pytest

from metapang.logger import mp_log


def pytest_configure(config):
    mp_log.disable("metapang")


def pytest_collection_modifyitems(items):
    def rank(item):
        path = str(item.path)
        if "test_profile.py" in path:
            return 2
        if "/integration/" in path:
            return 1
        return 0

    items.sort(key=rank)


@pytest.fixture(scope="session")
def data_dir():
    return Path(__file__).resolve().parent / "data"


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    item._assert_count = 0
    item._fail_count = 0


@pytest.hookimpl(tryfirst=True)
def pytest_assertion_pass(item, lineno, orig, expl):
    item._assert_count += 1


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        if report.failed:
            item._fail_count = 1

        report.user_properties.append(
            ("test_summary", (item._assert_count, item._fail_count))
        )


def pytest_report_teststatus(report, config):
    category, letter, word = report.outcome, "", report.outcome.upper()

    if report.when == "call":
        summary = next(
            (
                v
                for k, v in getattr(report, "user_properties", [])
                if k == "test_summary"
            ),
            None,
        )
        if summary:
            nb_asserts, nb_failed = summary
            word = f"[{nb_asserts} success, {nb_failed} failed]"
        return category, letter, word
