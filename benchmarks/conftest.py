"""
Pydantic-Resolve Benchmark Suite - Common Fixtures and Utilities

共享的 fixtures 和辅助函数
"""


# ============================================================================
# Helper Functions
# ============================================================================

def measure_performance(result, elapsed, node_count=None, item_count=None):
    """打印性能统计信息"""
    print(f"\n  ✅ Test completed in {elapsed:.4f}s")
    if node_count:
        print(f"  📊 Nodes processed: {node_count}")
        if elapsed > 0:
            print(f"  📈 Average: {elapsed/node_count*1000:.2f}ms per node")
    if item_count:
        print(f"  📦 Total items: {item_count}")


def assert_performance(elapsed, max_time, test_name: str):
    """性能断言"""
    assert elapsed < max_time, (
        f"{test_name} too slow: {elapsed:.4f}s (expected < {max_time:.4f}s)"
    )


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """配置 pytest 标记"""
    config.addinivalue_line(
        "markers", "benchmark: mark test as benchmark test"
    )
