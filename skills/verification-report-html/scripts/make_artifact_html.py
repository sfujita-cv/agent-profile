#!/usr/bin/env python3
"""``src/report.html`` を Artifact に publish できる形へ落とす。

自己完結版 (``embed_assets.py`` の出力) をそのまま publish してはいけない。
1 ファイルが数 MB になって読み込みが重く、assets を差し替えるたび全体を作り直す
ことになる。publish では assets を個別ファイルとして並べる。

Artifact の実行環境は `file://` で開く自己完結 HTML とは前提が違うので、
機械的に 4 つ直す。どれも**失敗しても無言**なので、手で直すと取りこぼす。

1. ``<!doctype>`` / ``<html>`` / ``<head>`` / ``<body>`` を落とす。publish 時に
   同等のものが被せられるため、二重になる。``<title>`` と ``<style>`` は残す。
2. CDN の stylesheet を落とす。Artifact の CSP は ``fonts.googleapis.com`` 以外の
   stylesheet を弾く。template が読む KaTeX / Prism がこれに当たる。数式や
   ハイライトを使っているレポートは、CSS を inline してから publish すること
   (script は cdnjs から読めるが、stylesheet は読めない)。
3. dark theme を 3 状態で解決させる。template は ``prefers-color-scheme`` しか
   見ていないが、viewer は明示的なテーマ選択を root の ``data-theme`` に刻む。
   OS が dark でも「light を選んだ viewer」がいるので、両方効くようにする。
4. 表を ``overflow-x: auto`` の container で包む。包まないと 400px 幅で本文ごと
   横に流れる。

使い方::

    python ~/.claude/skills/verification-report-html/scripts/make_artifact_html.py \\
      reports/<name>/src/report.html

そのあと Artifact tool で publish する::

    file_path: reports/<name>/src/artifact.html
    root:      reports/<name>/src
    files:     {"assets/xxx.jpg": "assets/xxx.jpg", ...}
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

# 400px 幅で本文が横スクロールしないための追補。table と、狭い画面での gutter。
_EXTRA_CSS = """
    /* --- Artifact 向けの追補 (make_artifact_html.py) --- */
    .tablewrap { overflow-x: auto; margin: 12px 0; }
    .tablewrap table { margin: 0; min-width: 480px; }
    @media (max-width: 520px) {
      .layout { padding-left: 16px; padding-right: 16px; }
    }
"""


def _split_document(src: str) -> tuple[str, str]:
    if "<body>" not in src:
        sys.exit("<body> が無い。src/report.html は完全な HTML 文書のはず。")
    head, body = src.split("<body>", 1)
    return head, body.rsplit("</body>", 1)[0]


def _extract(head: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", head, re.S)
    if not m:
        sys.exit(f"<{tag}> が head に無い。")
    return m.group(1)


def _theme_aware(css: str) -> str:
    """``prefers-color-scheme`` だけの dark block を 3 状態に広げる。"""
    pattern = r"@media \(prefers-color-scheme: dark\) \{\n(\s*):root \{(.*?)\n\1\}\n\s*\}"
    m = re.search(pattern, css, re.S)
    if not m:
        # 既に data-theme 対応済みなら何もしない。単一テーマ設計も素通しでよい。
        if "data-theme" not in css:
            print("  [warn] dark token block が見つからない。theme は素通し。")
        return css
    tokens = m.group(2)
    widened = (
        '@media (prefers-color-scheme: dark) {\n'
        '      :root:not([data-theme="light"]) {' + tokens + "\n      }\n    }\n"
        '    :root[data-theme="dark"] {' + tokens + "\n    }"
    )
    return css[: m.start()] + widened + css[m.end():]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", type=pathlib.Path, help="src/report.html")
    ap.add_argument("-o", "--out", type=pathlib.Path, help="既定: 入力と同じ場所の artifact.html")
    ap.add_argument("--title", help="Artifact 名。省略時は <title> をそのまま使う")
    args = ap.parse_args()

    out = args.out or args.report.with_name("artifact.html")
    head, body = _split_document(args.report.read_text())

    title = args.title or _extract(head, "title")
    # 「名前 — 説明」は Artifact の gallery では説明部分が邪魔になる。名前だけ残す。
    if args.title is None and " — " in title:
        print(f"  [warn] title に説明が付いている: {title!r}")
        print("         --title で短い名前 (2-4 語の名詞句) を渡すとよい。")

    if "cdn." in head or "cdnjs" in head:
        print("  CDN stylesheet を除去 (Artifact の CSP が弾くため)")

    css = _theme_aware(_extract(head, "style")) + _EXTRA_CSS
    # Idempotent: a table the author already wrapped is left alone.
    body, n = re.subn(r'(?<!<div class="tablewrap">)(<table[^>]*>.*?</table>)', r'<div class="tablewrap">\1</div>', body, flags=re.S)

    out.write_text(f"<title>{title}</title>\n<style>{css}</style>\n{body}")

    assets = sorted(set(re.findall(r'(?:src|href)="(assets/[^"]+)"', body)))
    print(f"[make-artifact] {args.report} -> {out}")
    print(f"  title = {title!r} / table {n} 件を包んだ / assets {len(assets)} 件")
    missing = [a for a in assets if not (args.report.parent / a).exists()]
    if missing:
        sys.exit(f"  参照されている assets が無い: {missing}")
    if assets:
        print("  publish 時の files (root は src/):")
        print("    {" + ", ".join(f'"{a}": "{a}"' for a in assets) + "}")


if __name__ == "__main__":
    main()
