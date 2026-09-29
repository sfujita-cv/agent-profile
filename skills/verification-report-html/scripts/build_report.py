#!/usr/bin/env python
"""検証レポートの HTML を `templates/skeleton.html` から組み立てる。

**report の HTML を過去の report から copy しない。** 骨格 (head / CSS / viewer JS / lightbox JS) の
正本はこの skill の `templates/skeleton.html` だけで、body だけを report ごとに書く。過去 report を
copy すると、骨格側の bug (例: viewer が点群名を hardcode していた件) がそのまま伝播する。

使い方:

    python ~/.claude/skills/verification-report-html/scripts/build_report.py \
        --body /path/to/body.html --assets /runs/<x>/report_assets \
        --out reports/<topic> --title "Camera path 検証" \
        [--values values.json] [--no-validate]

- `--body` は `<section>` の並び (skeleton の `{{BODY}}` に入る)。`{{key}}` を含んでよく、
  `--values` の JSON で置換する (未置換が残れば validator が落とす)。
- `--assets` の中身を `<out>/assets/` に copy する。body は `assets/...` の相対 path で参照する。
- 出力: `<out>/report.html` と、Artifact publish 用の `files` dict (stdout)。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SKELETON = SKILL_DIR / "templates" / "skeleton.html"


def build(body_path: Path, assets: Path | None, out_dir: Path, title: str, values: dict) -> Path:
    body = body_path.read_text(encoding="utf-8")
    for key, value in values.items():
        body = body.replace("{{" + key + "}}", str(value))
    skeleton = SKELETON.read_text(encoding="utf-8")
    html = skeleton.replace("{{TITLE}}", title).replace("{{BODY}}", body)
    out_dir.mkdir(parents=True, exist_ok=True)
    if assets is not None:
        dst = out_dir / "assets"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(assets, dst)
    report = out_dir / "report.html"
    report.write_text(html, encoding="utf-8")
    return report


def files_map(out_dir: Path) -> dict[str, str]:
    root = out_dir / "assets"
    return {str(p.relative_to(out_dir)): str(p.relative_to(out_dir))
            for p in sorted(root.rglob("*")) if p.is_file()} if root.exists() else {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body", type=Path, required=True)
    ap.add_argument("--assets", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True, help="primary checkout の reports/<topic>")
    ap.add_argument("--title", required=True, help="2〜4 語の名詞句 (タブとギャラリーの名前)")
    ap.add_argument("--values", type=Path, default=None, help="body の {{key}} を置換する JSON")
    ap.add_argument("--no-validate", action="store_true")
    args = ap.parse_args()
    values = json.loads(args.values.read_text(encoding="utf-8")) if args.values else {}
    report = build(args.body, args.assets, args.out, args.title, values)
    if not args.no_validate:
        rc = subprocess.call([sys.executable, str(SKILL_DIR / "scripts" / "validate_report.py"), str(report)])
        if rc != 0:
            return rc
    print(f"[build_report] wrote {report} ({report.stat().st_size // 1024} KB)")
    print("[build_report] Artifact publish:")
    print(f"  file_path: {report}")
    print(f"  root:      {args.out}")
    print(f"  files:     {json.dumps(files_map(args.out), ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
