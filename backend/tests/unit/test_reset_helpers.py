"""The test-isolation contract: singletons must be resettable so every
test can get a fresh compiled graph and a fresh checkpoint DB.

Env + init/close per test comes from conftest's autouse
fresh_graph_and_checkpointer fixture; these tests exercise the reset
APIs themselves on top of it.
"""

import pytest

import graphs.builder as builder_module
import memory.checkpointer as checkpointer_module


def test_build_graph_is_singleton_until_reset():
    g1 = builder_module.build_graph()
    assert builder_module.build_graph() is g1

    builder_module.reset_for_testing()
    g2 = builder_module.build_graph()
    assert g2 is not g1


async def test_checkpointer_reinit_rereads_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "first.db"))
    # Close the fixture-provided instance so ainit re-reads the env var.
    await checkpointer_module.aclose_checkpointer()
    c1 = await checkpointer_module.ainit_checkpointer()
    assert await checkpointer_module.ainit_checkpointer() is c1  # idempotent
    assert checkpointer_module.get_checkpointer() is c1  # sync fast-path
    # setup() committed the DDL — the file must exist eagerly, not lazily.
    assert (tmp_path / "first.db").exists()

    await checkpointer_module.aclose_checkpointer()
    with pytest.raises(RuntimeError):
        checkpointer_module.get_checkpointer()
    # Proves the SQLite handle was actually released (unlink of an
    # open file raises PermissionError on Windows).
    (tmp_path / "first.db").unlink()
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "second.db"))
    c2 = await checkpointer_module.ainit_checkpointer()
    assert c2 is not c1
    assert (tmp_path / "second.db").exists()
