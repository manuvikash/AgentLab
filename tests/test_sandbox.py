"""Tests for the local sandbox."""

from __future__ import annotations

import pytest

from agentlab.components.sandboxes.local import LocalSandbox


@pytest.mark.asyncio
async def test_execute_command(tmp_path):
    sandbox = LocalSandbox(workdir=str(tmp_path))
    await sandbox.start()

    result = await sandbox.execute("echo hello")
    assert result.success
    assert "hello" in result.stdout

    await sandbox.stop()


@pytest.mark.asyncio
async def test_read_write_file(tmp_path):
    sandbox = LocalSandbox(workdir=str(tmp_path))
    await sandbox.start()

    await sandbox.write_file("test.txt", "content")
    text = await sandbox.read_file("test.txt")
    assert text == "content"

    await sandbox.stop()


@pytest.mark.asyncio
async def test_list_files(tmp_path):
    sandbox = LocalSandbox(workdir=str(tmp_path))
    await sandbox.start()

    await sandbox.write_file("a.txt", "a")
    await sandbox.write_file("b.txt", "b")

    files = await sandbox.list_files()
    assert "a.txt" in files
    assert "b.txt" in files

    await sandbox.stop()


@pytest.mark.asyncio
async def test_path_escape_blocked(tmp_path):
    sandbox = LocalSandbox(workdir=str(tmp_path))
    await sandbox.start()

    with pytest.raises(PermissionError, match="Path escapes sandbox"):
        await sandbox.read_file("../../etc/passwd")

    await sandbox.stop()


@pytest.mark.asyncio
async def test_context_manager(tmp_path):
    async with LocalSandbox(workdir=str(tmp_path)) as sandbox:
        result = await sandbox.execute("echo works")
        assert result.success
