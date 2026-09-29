#!/usr/bin/env python3
"""相対パス参照の HTML を、data: URI 内包の自己完結 HTML に変換する。

レポートをブラウザに D&D / ダブルクリックするだけで開けるようにするための後処理。
file:// では fetch が CORS (origin null) で落ちるが、<img> と <video> の src は
通常のサブリソース読み込みなので data: URI にしておけば確実に表示される。

agent が base64 を自分の出力に書くとトークンを大量に消費するため、変換は必ず
この script に行わせる。
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import re
import sys
from pathlib import Path

# 目安と上限。base64 で約 4/3 に膨らむ分を見込んでいる。
WARN_BYTES = 20 * 1024 * 1024
LIMIT_BYTES = 50 * 1024 * 1024

# src="..." / href="..." のうち、data: や http(s): でない相対パスだけを拾う。
ATTR_RE = re.compile(r'(?P<attr>\b(?:src|href|poster)\s*=\s*)(?P<q>["\'])(?P<url>[^"\']+)(?P=q)')

EMBEDDABLE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif",
    ".mp4", ".webm", ".mov", ".m4v", ".ogg",
}


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024.0
    return f"{n}B"


def guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if mime:
        return mime
    # mimetypes が黙って None を返す拡張子だけ補う。
    return {".webm": "video/webm", ".m4v": "video/x-m4v", ".avif": "image/avif"}.get(
        path.suffix.lower(), "application/octet-stream"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_html", type=Path, help="相対パスで assets を参照する編集版 HTML")
    ap.add_argument("output_html", type=Path, help="出力する自己完結 HTML")
    args = ap.parse_args()

    src_html: Path = args.input_html
    if not src_html.is_file():
        print(f"ERROR: input not found: {src_html}", file=sys.stderr)
        return 1

    text = src_html.read_text(encoding="utf-8")
    base_dir = src_html.parent

    embedded: list[tuple[str, int]] = []
    missing: list[str] = []
    skipped: list[str] = []

    def replace(m: re.Match[str]) -> str:
        url = m.group("url")
        # 外部 URL、data:、ページ内アンカーはそのまま残す (KaTeX/Prism の CDN 等)。
        if url.startswith(("data:", "http://", "https://", "//", "#", "mailto:")):
            return m.group(0)

        asset = (base_dir / url).resolve()
        if not asset.is_file():
            missing.append(url)
            return m.group(0)
        if asset.suffix.lower() not in EMBEDDABLE_SUFFIXES:
            skipped.append(url)
            return m.group(0)

        raw = asset.read_bytes()
        embedded.append((url, len(raw)))
        b64 = base64.b64encode(raw).decode("ascii")
        return f'{m.group("attr")}{m.group("q")}data:{guess_mime(asset)};base64,{b64}{m.group("q")}'

    out_text = ATTR_RE.sub(replace, text)
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(out_text, encoding="utf-8")

    final = args.output_html.stat().st_size
    print(f"[embed-assets] {src_html} -> {args.output_html}")
    for url, size in embedded:
        print(f"[embed-assets]   embedded {url} ({human(size)})")
    for url in skipped:
        print(f"[embed-assets]   skipped (未対応の拡張子) {url}", file=sys.stderr)
    for url in missing:
        print(f"[embed-assets]   WARNING: file not found, left as-is: {url}", file=sys.stderr)
    print(f"[embed-assets] 埋め込み {len(embedded)} 件 / 最終サイズ {human(final)}")

    # 残った相対参照があると「単体で開ける」前提が崩れるので明示的に警告する。
    if missing:
        print("[embed-assets] WARNING: 未解決の相対参照が残っています。"
              "このファイルは単体では完全に表示できません。", file=sys.stderr)

    if final > LIMIT_BYTES:
        print(f"[embed-assets] ERROR: 上限 {human(LIMIT_BYTES)} を超えました。"
              "画像を長辺 1280px に縮小するか、動画を 720p / 6-10 秒に収めてください。",
              file=sys.stderr)
        return 1
    if final > WARN_BYTES:
        print(f"[embed-assets] WARNING: 目安 {human(WARN_BYTES)} を超えています。"
              "画像・動画の縮小を検討してください。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
