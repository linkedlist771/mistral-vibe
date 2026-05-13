"""Image attachment utilities for multimodal LLM requests.

Mirrors the design used by claude-code (`src/utils/imagePaste.ts`,
`src/utils/imageResizer.ts`, `src/constants/apiLimits.ts`):

1. Detect image file path tokens in a user prompt (`@/abs/path/to/img.png`
   or bare `./pic.jpg`).
2. Load bytes, validate, downscale if it would exceed the API's 5 MB
   base64 limit, base64-encode.
3. Emit an Anthropic-compatible image block:
   ``{"type":"image","source":{"type":"base64","media_type":"image/png","data":"..."}}``

The Anthropic backend (``vibe/core/llm/backend/anthropic.py``) is the only
consumer for now; other backends ignore the ``attachments`` field on
``LLMMessage``.
"""

from __future__ import annotations

import base64
import io
import logging
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

log = logging.getLogger(__name__)

# Anthropic API limits (verified against claude-code's apiLimits.ts).
API_IMAGE_MAX_BASE64_SIZE = 5 * 1024 * 1024  # 5 MB base64 string length
IMAGE_TARGET_RAW_SIZE = (API_IMAGE_MAX_BASE64_SIZE * 3) // 4  # ~3.75 MB raw
IMAGE_MAX_DIMENSION = 2000  # Client-side resize cap

SUPPORTED_EXTENSIONS = ("png", "jpg", "jpeg", "gif", "webp")

# PIL format name -> Anthropic media_type
_PIL_FORMAT_TO_MEDIA_TYPE = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}

# Matches @path tokens where path ends in a supported image extension.
# Accepts absolute, relative, ~-prefixed, and POSIX-escaped paths.
_IMAGE_TOKEN_RE = re.compile(
    r"@(?P<path>(?:[^\s'\"]|\\\s)+\."
    r"(?:png|jpe?g|gif|webp))"
    r"(?=\s|$|[,.!?:;])",
    re.IGNORECASE,
)


def _resolve_path(raw: str) -> Path:
    """Strip shell escapes / outer quotes and expand ~."""
    cleaned = raw.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ("'", '"'):
        cleaned = cleaned[1:-1]
    # POSIX shell-escape: "name\ \(1\).png" -> "name (1).png"
    cleaned = re.sub(r"\\(.)", r"\1", cleaned)
    return Path(cleaned).expanduser()


def _downscale_if_needed(img: Image.Image) -> Image.Image:
    if img.width <= IMAGE_MAX_DIMENSION and img.height <= IMAGE_MAX_DIMENSION:
        return img
    img.thumbnail((IMAGE_MAX_DIMENSION, IMAGE_MAX_DIMENSION), Image.Resampling.LANCZOS)
    return img


def _encode(img: Image.Image, fmt: str) -> tuple[bytes, str]:
    buf = io.BytesIO()
    save_fmt = fmt if fmt in _PIL_FORMAT_TO_MEDIA_TYPE else "PNG"
    save_kwargs: dict[str, Any] = {}
    if save_fmt == "JPEG":
        save_kwargs["quality"] = 85
        save_kwargs["optimize"] = True
        # JPEG can't carry alpha; flatten on a white background.
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
            img = background
    img.save(buf, format=save_fmt, **save_kwargs)
    return buf.getvalue(), _PIL_FORMAT_TO_MEDIA_TYPE.get(save_fmt, "image/png")


def load_image_block(path: Path) -> dict[str, Any] | None:
    """Read an image from disk and return an Anthropic image content block.

    Returns ``None`` if the file is missing, unreadable, or not an image.
    Downscales / re-encodes until the base64 payload is under
    ``API_IMAGE_MAX_BASE64_SIZE``; gives up after a few iterations and
    logs a warning.
    """
    if not path.is_file():
        return None
    try:
        with Image.open(path) as img:
            img.load()
            fmt = img.format or "PNG"
            img = _downscale_if_needed(img.copy())
    except (UnidentifiedImageError, OSError) as e:
        log.warning("Failed to load image %s: %s", path, e)
        return None

    raw, media_type = _encode(img, fmt)
    b64 = base64.b64encode(raw).decode("ascii")

    # If still over the limit, progressively shrink. JPEG path makes the
    # biggest difference; switch to it if we started as PNG.
    attempts = 0
    while len(b64) > API_IMAGE_MAX_BASE64_SIZE and attempts < 4:
        attempts += 1
        new_w = max(int(img.width * 0.75), 256)
        new_h = max(int(img.height * 0.75), 256)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        raw, media_type = _encode(img, "JPEG")
        b64 = base64.b64encode(raw).decode("ascii")

    if len(b64) > API_IMAGE_MAX_BASE64_SIZE:
        log.warning(
            "Image %s still %d bytes base64 after downscaling, skipping",
            path,
            len(b64),
        )
        return None

    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": b64,
        },
    }


# Used by the input widget to delete an entire `@<path>` token on a single
# backspace, instead of one character at a time. Matches an `@` followed by
# at least one `/` and any number of non-whitespace chars, anchored to the
# end of the input.
_AT_PATH_TOKEN_RE = re.compile(r"@\S*/\S*$")


def find_at_token_start(prefix: str) -> int | None:
    """If ``prefix`` (line text up to the cursor) ends with an ``@<path>``
    token (preceded by whitespace or start-of-line), return the column where
    the ``@`` sits. Otherwise return ``None``.

    Backspace deletes from this column to the cursor in one shot.
    """
    match = _AT_PATH_TOKEN_RE.search(prefix)
    if not match:
        return None
    if match.start() > 0 and not prefix[match.start() - 1].isspace():
        return None
    return match.start()


def _clipboard_image_cache_dir() -> Path:
    base = Path.home() / ".vibe" / "image-cache"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _grab_clipboard_image_macos() -> Path | None:
    """macOS: use AppleScript to dump «class PNGf» onto disk."""
    out_path = _clipboard_image_cache_dir() / f"{uuid.uuid4().hex}.png"
    script = (
        "set png_data to (the clipboard as «class PNGf»)\n"
        f'set fp to open for access POSIX file "{out_path}" with write permission\n'
        "write png_data to fp\n"
        "close access fp\n"
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.debug("osascript clipboard read failed: %s", e)
        return None
    if result.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
        out_path.unlink(missing_ok=True)
        return None
    return out_path


def _grab_clipboard_image_linux() -> Path | None:
    """Linux: try wl-paste (Wayland) then xclip (X11). Both have to be
    installed by the user; if neither is present we silently return None.
    """
    import os
    import shutil

    out_path = _clipboard_image_cache_dir() / f"{uuid.uuid4().hex}.png"

    candidates: list[tuple[str, list[str]]] = []
    # Wayland — wl-paste -t image/png writes binary PNG to stdout.
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
        candidates.append(("wl-paste", ["wl-paste", "-t", "image/png"]))
    # X11 — xclip -selection clipboard -t image/png -o
    if os.environ.get("DISPLAY") and shutil.which("xclip"):
        candidates.append(
            ("xclip", ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"])
        )

    for name, cmd in candidates:
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=5, check=False
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            log.debug("%s clipboard read failed: %s", name, e)
            continue
        if result.returncode != 0 or not result.stdout:
            continue
        try:
            out_path.write_bytes(result.stdout)
        except OSError as e:
            log.debug("Failed to write clipboard image to %s: %s", out_path, e)
            continue
        # Round-trip via PIL to confirm it's a real image and to strip any
        # leading garbage some clipboard managers attach.
        try:
            with Image.open(out_path) as img:
                img.verify()
        except (UnidentifiedImageError, OSError):
            out_path.unlink(missing_ok=True)
            continue
        return out_path

    return None


def _grab_clipboard_image_windows() -> Path | None:
    """Windows: use Pillow's ImageGrab to read clipboard."""
    try:
        from PIL import ImageGrab
    except ImportError:
        return None
    try:
        img = ImageGrab.grabclipboard()
    except (OSError, NotImplementedError):
        return None
    if not isinstance(img, Image.Image):
        return None
    out_path = _clipboard_image_cache_dir() / f"{uuid.uuid4().hex}.png"
    try:
        img.save(out_path, format="PNG")
    except OSError as e:
        log.debug("Failed to write clipboard image to %s: %s", out_path, e)
        return None
    return out_path


def grab_clipboard_image() -> Path | None:
    """If the OS clipboard currently holds an image, write it to disk and
    return the saved path. Returns ``None`` if there is no image or the
    platform's clipboard tool isn't available.

    macOS uses ``osascript`` (``«class PNGf»``), Linux uses ``wl-paste``
    (Wayland) or ``xclip`` (X11), Windows uses ``PIL.ImageGrab``.
    """
    if sys.platform == "darwin":
        return _grab_clipboard_image_macos()
    if sys.platform.startswith("linux"):
        return _grab_clipboard_image_linux()
    if sys.platform == "win32":
        return _grab_clipboard_image_windows()
    return None


def extract_image_attachments(
    text: str, base_dir: Path | None = None
) -> tuple[str, list[dict[str, Any]]]:
    """Find ``@<image_path>`` tokens in ``text``, load them, and return
    ``(stripped_text, attachments)``.

    The matched tokens are removed from the returned text so the model sees
    a clean prompt; a short ``[image: <path>]`` placeholder is left in
    their place to preserve word ordering / context. Tokens that fail to
    resolve as readable images are left untouched in the text.
    """
    attachments: list[dict[str, Any]] = []
    base = base_dir or Path.cwd()

    def _replace(match: re.Match[str]) -> str:
        raw_path = match.group("path")
        path = _resolve_path(raw_path)
        if not path.is_absolute():
            path = (base / path).resolve()
        block = load_image_block(path)
        if block is None:
            return match.group(0)
        attachments.append(block)
        return f"[image: {path.name}]"

    new_text = _IMAGE_TOKEN_RE.sub(_replace, text)
    # Diagnostic — visible at the default WARNING level so failures to
    # match a pasted token are obvious in ~/.vibe/logs/vibe.log.
    if "@" in text:
        log.warning(
            "extract_image_attachments: input_len=%d had_at=True "
            "matched=%d (regex=%s)",
            len(text),
            len(attachments),
            _IMAGE_TOKEN_RE.pattern[:80],
        )
    return new_text, attachments
