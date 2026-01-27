"""
Pydantic-Resolve Benchmark Suite - Common Fixtures and Utilities

共享的 fixtures 和辅助函数
"""


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """配置 pytest 标记"""
    config.addinivalue_line(
        "markers", "benchmark: mark test as benchmark test"
    )
