"""Proves the test harness can import the project and see its deps."""


def test_project_imports():
    from graphs.builder import build_graph  # noqa: F401
    from schemas.graph_state import GraphState  # noqa: F401
    from services.deal_service import process_deal_via_graph  # noqa: F401


async def test_async_mode_works():
    assert True
