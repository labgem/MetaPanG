import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if "/integration/" in str(item.path):
            item.add_marker(pytest.mark.integration)
