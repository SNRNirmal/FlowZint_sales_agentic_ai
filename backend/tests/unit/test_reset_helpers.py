"""The test-isolation contract: singletons must be resettable so every
test can get a fresh compiled graph and a fresh checkpoint DB."""

import pytest

import graphs.builder as builder_module
import memory.checkpointer as checkpointer_module


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))
    yield
    builder_module.reset_for_testing()
    checkpointer_module.reset_for_testing()


def test_build_graph_is_singleton_until_reset():
    g1 = builder_module.build_graph()
    assert builder_module.build_graph() is g1

    builder_module.reset_for_testing()
    g2 = builder_module.build_graph()
    assert g2 is not g1


def test_checkpointer_reset_rereads_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "first.db"))
    c1 = checkpointer_module.get_checkpointer()
    assert checkpointer_module.get_checkpointer() is c1
    assert (tmp_path / "first.db").exists()

    checkpointer_module.reset_for_testing()
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "second.db"))
    c2 = checkpointer_module.get_checkpointer()
    assert c2 is not c1
    assert (tmp_path / "second.db").exists()
