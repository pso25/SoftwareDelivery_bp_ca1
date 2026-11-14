"""E2E tests run in a real browser (Playwright) against a deployed site:

    pytest tests/e2e --base-url https://<site>

Without --base-url they are skipped before any browser starts, so the normal
test runs (and CI) need no browser installed."""
from pathlib import Path

import pytest

E2E_DIR = Path(__file__).parent


def pytest_collection_modifyitems(config, items):
    if config.getoption("base_url"):
        return
    skip = pytest.mark.skip(reason="E2E tests need --base-url")
    for item in items:
        if E2E_DIR in item.path.parents:
            item.add_marker(skip)
