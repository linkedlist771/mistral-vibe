"""Tests for the multimodal image attachment helpers."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

from vibe.core.llm.images import (
    API_IMAGE_MAX_BASE64_SIZE,
    extract_image_attachments,
    find_at_token_start,
    load_image_block,
)


def _write_png(path: Path, size: tuple[int, int] = (32, 32), color: str = "red") -> None:
    img = Image.new("RGB", size, color)
    img.save(path, format="PNG")


def _write_jpeg(path: Path, size: tuple[int, int] = (32, 32)) -> None:
    img = Image.new("RGB", size, "blue")
    img.save(path, format="JPEG", quality=85)


def test_load_image_block_png(tmp_path: Path) -> None:
    p = tmp_path / "tiny.png"
    _write_png(p)
    block = load_image_block(p)
    assert block is not None
    assert block["type"] == "image"
    assert block["source"]["type"] == "base64"
    assert block["source"]["media_type"] == "image/png"
    # Must be decodable base64
    base64.b64decode(block["source"]["data"], validate=True)


def test_load_image_block_jpeg(tmp_path: Path) -> None:
    p = tmp_path / "tiny.jpg"
    _write_jpeg(p)
    block = load_image_block(p)
    assert block is not None
    assert block["source"]["media_type"] == "image/jpeg"


def test_load_image_block_missing_file(tmp_path: Path) -> None:
    assert load_image_block(tmp_path / "does-not-exist.png") is None


def test_load_image_block_not_an_image(tmp_path: Path) -> None:
    p = tmp_path / "not-an-image.png"
    p.write_text("definitely not a PNG", encoding="utf-8")
    assert load_image_block(p) is None


def test_load_image_block_downscales_oversized(tmp_path: Path) -> None:
    # A 4000x4000 image is way over the 2000 cap; the block should still load
    # and the base64 payload must be under the API limit.
    p = tmp_path / "huge.png"
    Image.new("RGB", (4000, 4000), "green").save(p, format="PNG")
    block = load_image_block(p)
    assert block is not None
    assert len(block["source"]["data"]) <= API_IMAGE_MAX_BASE64_SIZE


def test_extract_image_attachments_strips_token(tmp_path: Path) -> None:
    p = tmp_path / "pic.png"
    _write_png(p)
    prompt = f"describe @{p} for me"
    text, attachments = extract_image_attachments(prompt)
    assert len(attachments) == 1
    assert attachments[0]["source"]["media_type"] == "image/png"
    assert "@" + str(p) not in text
    assert "[image: pic.png]" in text


def test_extract_image_attachments_leaves_unresolvable_token(tmp_path: Path) -> None:
    prompt = "look at @/nope/does-not-exist.png please"
    text, attachments = extract_image_attachments(prompt)
    assert attachments == []
    assert "@/nope/does-not-exist.png" in text


def test_extract_image_attachments_multiple(tmp_path: Path) -> None:
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.jpg"
    _write_png(p1)
    _write_jpeg(p2)
    prompt = f"compare @{p1} and @{p2}"
    text, attachments = extract_image_attachments(prompt)
    assert len(attachments) == 2
    assert "[image: a.png]" in text
    assert "[image: b.jpg]" in text


def test_extract_image_attachments_no_match() -> None:
    prompt = "just a regular question with no images"
    text, attachments = extract_image_attachments(prompt)
    assert attachments == []
    assert text == prompt


def test_extract_image_attachments_relative_path(tmp_path: Path) -> None:
    p = tmp_path / "rel.png"
    _write_png(p)
    text, attachments = extract_image_attachments("see @rel.png", base_dir=tmp_path)
    assert len(attachments) == 1
    assert "[image: rel.png]" in text


def test_grab_clipboard_image_no_image(monkeypatch) -> None:
    import sys

    from vibe.core.llm import images as images_mod

    monkeypatch.setattr(sys, "platform", "darwin")

    class FakeResult:
        returncode = 1
        stdout = b""
        stderr = b"AppleScript error"

    monkeypatch.setattr(images_mod.subprocess, "run", lambda *a, **kw: FakeResult())
    assert images_mod.grab_clipboard_image() is None


def test_grab_clipboard_image_returns_path(monkeypatch, tmp_path: Path) -> None:
    import sys

    from vibe.core.llm import images as images_mod

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(images_mod, "_clipboard_image_cache_dir", lambda: tmp_path)

    def fake_run(args, **kw):
        script = args[2]
        marker = 'POSIX file "'
        start = script.index(marker) + len(marker)
        end = script.index('"', start)
        out = Path(script[start:end])
        _write_png(out)

        class R:
            returncode = 0
            stdout = b""
            stderr = b""

        return R()

    monkeypatch.setattr(images_mod.subprocess, "run", fake_run)
    result = images_mod.grab_clipboard_image()
    assert result is not None and result.is_file() and result.stat().st_size > 0


def test_grab_clipboard_image_unsupported_platform(monkeypatch) -> None:
    import sys

    from vibe.core.llm import images as images_mod

    monkeypatch.setattr(sys, "platform", "linux")
    assert images_mod.grab_clipboard_image() is None


def test_find_at_token_start_full_path() -> None:
    prefix = "look at @/Users/dingli/pic.png"
    start = find_at_token_start(prefix)
    assert start == prefix.index("@")


def test_find_at_token_start_partial_path() -> None:
    # User has been backspacing — the token no longer has a valid extension
    # but should still be deletable atomically.
    prefix = "look at @/Users/dingli/.vibe/image-cache/deecd3b5"
    start = find_at_token_start(prefix)
    assert start == prefix.index("@")


def test_find_at_token_start_at_start_of_line() -> None:
    prefix = "@/abs/path.png"
    assert find_at_token_start(prefix) == 0


def test_find_at_token_start_at_without_slash_does_not_match() -> None:
    # ``@mention`` style with no slash should not be treated as a path token.
    assert find_at_token_start("hello @username") is None


def test_find_at_token_start_not_preceded_by_whitespace() -> None:
    # `name@/path` is not a standalone token — `@` is preceded by `e`.
    assert find_at_token_start("name@/path/img.png") is None


def test_find_at_token_start_token_then_space() -> None:
    # Cursor sits after a trailing space; token doesn't end at cursor.
    assert find_at_token_start("@/path/img.png ") is None


def test_find_at_token_start_empty() -> None:
    assert find_at_token_start("") is None


def test_find_at_token_start_no_at() -> None:
    assert find_at_token_start("just regular text") is None


def test_grab_clipboard_image_no_op_when_unsupported(monkeypatch) -> None:
    """Without an X11/Wayland session and without xclip/wl-paste installed,
    the Linux helper should return ``None`` without raising."""
    import sys

    from vibe.core.llm import images as imgs

    monkeypatch.setattr(sys, "platform", "linux")
    # Strip the env vars the helper looks at.
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert imgs.grab_clipboard_image() is None


def test_grab_clipboard_image_returns_none_on_unknown_platform(monkeypatch) -> None:
    import sys

    from vibe.core.llm import images as imgs

    monkeypatch.setattr(sys, "platform", "freebsd14")
    assert imgs.grab_clipboard_image() is None
