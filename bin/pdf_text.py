#!/usr/bin/env python3
"""Extract text from a PDF with no third-party dependency.

Hand-rolled because no PDF library is installed and pip cannot reach PyPI here.

## Why this is not a one-liner

A PDF does not store text as text. It stores glyph codes plus a font, and those
codes are meaningless without the font's mapping. There are two shapes in the
wild and a naive extractor silently produces gibberish or nothing on the second:

  1. **Simple fonts** store ASCII-ish codes in literal `(strings)`, so a regex
     over `Tj`/`TJ` operands nearly works.
  2. **Subset/embedded fonts** (most exports from Word, Google Docs, Canva,
     LaTeX) store *glyph indices* as hex `<0022>` and rely on a `ToUnicode` CMap
     to say that `<0022>` is `S`. Ignoring the CMap yields mojibake, and ignoring
     hex strings yields an empty document.

So this resolves each font's ToUnicode CMap first, then applies it per text run,
tracking which font is active via `/Fx n Tf`.

It is a reader for content, not a general PDF parser. It handles FlateDecode and
the common CMap forms, and reports plainly when it cannot read a file instead of
returning plausible nonsense.
"""
from __future__ import annotations

import re
import sys
import zlib
from pathlib import Path


# ── stream plumbing ──────────────────────────────────────────────────────────
def _inflate(data: bytes) -> bytes | None:
    """zlib-decompress a stream body, tolerating leading whitespace/junk."""
    for offset in range(0, min(len(data), 64)):
        try:
            return zlib.decompress(data[offset:])
        except zlib.error:
            continue
    return None


def _all_streams(raw: bytes) -> list[bytes]:
    out: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n", raw):
        start = match.end()
        end = raw.find(b"endstream", start)
        if end == -1:
            continue
        body = raw[start:end].rstrip(b"\r\n")
        decoded = _inflate(body)
        if decoded is not None:
            out.append(decoded)
    return out


# ── ToUnicode CMaps ──────────────────────────────────────────────────────────
def _parse_cmap(data: bytes) -> dict[int, str]:
    """Parse beginbfchar / beginbfrange blocks into a code -> text map."""
    text = data.decode("latin-1", errors="replace")
    mapping: dict[int, str] = {}

    def utf16(hexstr: str) -> str:
        try:
            b = bytes.fromhex(hexstr)
        except ValueError:
            return ""
        try:
            return b.decode("utf-16-be")
        except UnicodeDecodeError:
            return b.decode("latin-1", errors="replace")

    # <src> <dst>
    for block in re.findall(r"beginbfchar(.*?)endbfchar", text, re.DOTALL):
        for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            mapping[int(src, 16)] = utf16(dst)

    # <lo> <hi> <dstStart>   and the [ <d1> <d2> ... ] array form
    for block in re.findall(r"beginbfrange(.*?)endbfrange", text, re.DOTALL):
        for lo, hi, dst in re.findall(
            r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block
        ):
            start, end, base = int(lo, 16), int(hi, 16), int(dst, 16)
            for i in range(end - start + 1):
                mapping[start + i] = chr(base + i) if base + i < 0x110000 else ""
        for lo, hi, arr in re.findall(
            r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]", block, re.DOTALL
        ):
            start = int(lo, 16)
            items = re.findall(r"<([0-9A-Fa-f]+)>", arr)
            for i, item in enumerate(items):
                mapping[start + i] = utf16(item)
    return mapping


def _font_cmaps(raw: bytes, streams: list[bytes]) -> dict[str, dict[int, str]]:
    """Map font resource names (F4, F5, ...) to their ToUnicode tables.

    Resolved by scanning the raw file for `/Fx ... /ToUnicode N 0 R` and pairing
    each with the Nth object's stream. Approximate, but fonts are referenced by
    resource name in the content stream and that is all we need.
    """
    # Index the objects we can decompress by their object number.
    objects: dict[int, bytes] = {}
    for m in re.finditer(rb"(\d+)\s+0\s+obj", raw):
        num = int(m.group(1))
        end = raw.find(b"endobj", m.end())
        body = raw[m.end():end if end != -1 else len(raw)]
        sm = re.search(rb"stream\r?\n", body)
        if sm:
            s = sm.end()
            e = body.find(b"endstream", s)
            decoded = _inflate(body[s:e].rstrip(b"\r\n"))
            if decoded is not None:
                objects[num] = decoded

    cmaps: dict[str, dict[int, str]] = {}
    for m in re.finditer(rb"/?(F\d+)\s+(\d+)\s+0\s+R", raw):
        name = m.group(1).decode()
        objnum = int(m.group(2))
        if objnum in objects:
            parsed = _parse_cmap(objects[objnum])
            if parsed:
                cmaps[name] = parsed

    # Some writers attach ToUnicode inside the font object rather than by
    # reference; fall back to "one CMap per font object, in order".
    if not cmaps:
        parsed_all = [p for p in (_parse_cmap(s) for s in streams) if p]
        for i, p in enumerate(parsed_all, start=4):
            cmaps[f"F{i}"] = p
    return cmaps


# ── content stream walking ───────────────────────────────────────────────────
_TOKEN = re.compile(
    r"/(?P<font>F\d+)\s+(?P<size>[\d.]+)\s+Tf"          # font selection
    r"|(?P<tm>(?:-?[\d.]+\s+){6}Tm)"                    # text matrix (absolute)
    r"|(?P<td>(?P<tx>-?[\d.]+)\s+(?P<ty>-?[\d.]+)\s+T[dD])"  # relative move
    r"|\[(?P<arr>.*?)\]\s*TJ"                           # array of strings
    r"|(?P<hex><[0-9A-Fa-f\s]*>)\s*Tj"                  # hex string
    r"|\((?P<lit>(?:\\.|[^\\()])*)\)\s*Tj"              # literal string
    r"|(?P<star>T\*)"                                   # next line
    r"|(?P<bt>BT)|(?P<et>ET)",
    re.DOTALL,
)

_OCTAL = re.compile(r"\\(n|r|t|\(|\)|\\|x[0-9A-Fa-f]{2}|[0-7]{1,3})")
_WS_RUN = re.compile(r"[ \t]{2,}")


def _unescape(s: str) -> str:
    def repl(m: re.Match) -> str:
        b = m.group(1)
        if b == "n":
            return "\n"
        if b == "r":
            return "\r"
        if b == "t":
            return "\t"
        if b in "()\\":
            return b
        if b.startswith("x"):
            return chr(int(b[1:], 16))
        try:
            return chr(int(b, 8))
        except ValueError:
            return ""

    return _OCTAL.sub(repl, s)


def _decode_hex(hexstr: str, cmap: dict[int, str] | None) -> str:
    """Decode a hex string, choosing 1- or 2-byte codes by what the CMap knows."""
    digits = re.sub(r"\s+", "", hexstr.strip("<>"))
    if len(digits) % 2:
        digits = digits[:-1]
    raw = bytes.fromhex(digits) if digits else b""

    if not cmap:
        return raw.decode("latin-1", errors="replace")

    wide = any(code > 0xFF for code in cmap)
    out: list[str] = []
    if wide:
        for i in range(0, len(raw) - 1, 2):
            code = (raw[i] << 8) | raw[i + 1]
            out.append(cmap.get(code, ""))
    else:
        for byte in raw:
            out.append(cmap.get(byte, chr(byte) if 32 <= byte < 127 else ""))
    return "".join(out)


def _text_from_content(content: bytes, cmaps: dict[str, dict[int, str]]) -> str:
    """Walk the content stream, inserting a newline only on a real line move.

    The trap: a PDF advances the text position with `Td` *between glyphs* as well
    as between lines. Breaking on every `Td` produces one character per line. So
    track the position and break only when the baseline moves down (or the x
    position jumps backwards, which is a new line at the same height).
    """
    text = content.decode("latin-1", errors="replace")
    active: dict[int, str] | None = None
    pieces: list[str] = []

    x = y = 0.0
    line_y: float | None = None
    line_start_x = 0.0
    font_size = 10.0

    for m in _TOKEN.finditer(text):
        if m.group("font"):
            active = cmaps.get(m.group("font"))
            try:
                font_size = float(m.group("size")) or 10.0
            except (TypeError, ValueError):
                font_size = 10.0
            continue

        if m.group("bt") or m.group("et"):
            # New text object: always a fresh line.
            if pieces and not pieces[-1].endswith("\n"):
                pieces.append("\n")
            x = y = 0.0
            line_y = None
            continue

        if m.group("tm"):
            nums = [float(v) for v in re.findall(r"-?[\d.]+", m.group("tm"))]
            x, y = nums[4], nums[5]
            line_y = y
            line_start_x = x
            if pieces and not pieces[-1].endswith("\n"):
                pieces.append("\n")
            continue

        if m.group("td"):
            tx = float(m.group("tx"))
            ty = float(m.group("ty"))
            x += tx
            y += ty
            if pieces:
                if ty != 0:
                    # Vertical move bad enough to be a new line.
                    if abs(ty) > font_size * 0.6 and not pieces[-1].endswith("\n"):
                        pieces.append("\n")
                        line_y = y
                        line_start_x = x
                elif line_y is not None and tx < 0 and x < line_start_x:
                    # Jumped backwards without changing height: new line.
                    if not pieces[-1].endswith("\n"):
                        pieces.append("\n")
                    line_start_x = x
            continue

        if m.group("star"):
            if pieces and not pieces[-1].endswith("\n"):
                pieces.append("\n")
            continue

        if m.group("arr") is not None:
            for s in re.finditer(r"<([0-9A-Fa-f\s]*)>|\((?:\\.|[^\\()])*\)", m.group("arr"), re.DOTALL):
                if s.group(0).startswith("<"):
                    pieces.append(_decode_hex(s.group(0), active))
                else:
                    pieces.append(_unescape(s.group(0)[1:-1]))
            continue
        if m.group("hex") is not None:
            pieces.append(_decode_hex(m.group("hex"), active))
            continue
        if m.group("lit") is not None:
            pieces.append(_unescape(m.group("lit")))

    joined = "".join(pieces)
    # Letter-spacing padding shows up as runs of spaces between glyphs.
    joined = _WS_RUN.sub(" ", joined)
    joined = "\n".join(line.rstrip() for line in joined.splitlines())
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    return joined.strip()


def extract(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if not raw.startswith(b"%PDF"):
        return "", "not a PDF (missing %PDF header)"
    if b"/Encrypt" in raw:
        return "", "PDF is encrypted; cannot read without the password"

    streams = _all_streams(raw)
    if not streams:
        return "", "no decompressible streams (unsupported filter?)"

    cmaps = _font_cmaps(raw, streams)
    text_streams = [s for s in streams if b"Tj" in s or b"TJ" in s]
    if not text_streams:
        has_images = raw.count(b"/Image") > 0
        hint = " This looks like a scan." if has_images else ""
        return "", f"no text operators found.{hint} OCR or a re-export is needed."

    chunks = [_text_from_content(s, cmaps) for s in text_streams]
    body = "\n\n".join(c for c in chunks if c.strip())
    if not body.strip():
        return "", "text operators present but no glyphs decoded"

    # A readable CV is mostly letters and spaces. If it is not, say so rather
    # than hand back mojibake and let it be mistaken for the real content.
    printable = sum(1 for c in body if c.isalnum() or c.isspace())
    ratio = printable / max(1, len(body))
    note = f"{len(text_streams)} text stream(s), {len(cmaps)} font map(s)"
    if ratio < 0.75:
        note += f" - WARNING: only {ratio:.0%} printable, output may be garbled"
    return body, note


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"not found: {path}", file=sys.stderr)
        return 2
    text, note = extract(path)
    print(f"# {path.name}")
    print(f"# {note}")
    print()
    print(text if text else "(no text extracted)")
    return 0 if text else 1


if __name__ == "__main__":
    raise SystemExit(main())
