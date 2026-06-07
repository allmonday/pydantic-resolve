"""Pytest configuration and fixtures for pydantic-resolve tests."""

import pytest
from pydantic_resolve.utils.resolver_configurator import reset_global_resolver
from pydantic_resolve.resolver import Resolver as _OriginalResolver


@pytest.fixture(autouse=True)
def reset_global_resolver_state():
    """Reset global resolver state after each test to prevent cross-contamination.

    This ensures that tests using config_global_resolver() don't affect other tests.
    """
    yield
    reset_global_resolver()


def pytest_addoption(parser):
    parser.addoption(
        "--bfs-compat",
        action="store_true",
        default=False,
        help="Force all Resolver() to use BFS mode for compatibility testing",
    )


@pytest.fixture(autouse=True)
def force_bfs_mode(request):
    """When --bfs-compat is set, monkey-patch Resolver to default to BFS."""
    if request.config.getoption("--bfs-compat", default=False):
        _orig_init = _OriginalResolver.__init__

        def _patched_init(self, *args, **kwargs):
            kwargs.setdefault("mode", "bfs")
            _orig_init(self, *args, **kwargs)

        _OriginalResolver.__init__ = _patched_init
        yield
        _OriginalResolver.__init__ = _orig_init
    else:
        yield
