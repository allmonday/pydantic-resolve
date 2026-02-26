"""Pytest configuration and fixtures for pydantic-resolve tests."""

import pytest
from pydantic_resolve.utils.resolver_configurator import reset_global_resolver


@pytest.fixture(autouse=True)
def reset_global_resolver_state():
    """Reset global resolver state after each test to prevent cross-contamination.

    This ensures that tests using config_global_resolver() don't affect other tests.
    """
    yield
    reset_global_resolver()
