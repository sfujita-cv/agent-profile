#!/usr/bin/env python
"""検証レポート HTML の静的チェック。publish の前に必ず通す (build_report.py が自動で呼ぶ)。

Artifact 上の失敗は無言か、開いた人にしか見えない。ここで落とせるものは全部落とす。

- `{{key}}` の置換漏れ
- `assets/...` の参照先が存在しない
- 図 (figure / .views の img) があるのに lightbox (拡大表示) の JS が無い
- 3D ビューワ (`id="stage"`) があるのに:
  - viewer の JS が meta の任意 key (scene_bbox) を必須として読んでいる
  - `assets/clouds/meta.json` が無い / `clouds` が空 / 必須 key が欠けている
  - 点群 file が無い、または base64 を decode した長さが `count * 9` byte (uint16 xyz + uint8 rgb) と合わない
  - `cameras` / `cameras_pred_aligned` が list でない、camera の K / T_cw の形が違う
  - viewer の JS が点群名を hardcode している (`show("...")`)。初期表示は meta から決める

使い方: python validate_report.py reports/<topic>/report.html
"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path


def check(report: Path) -> list[str]:
    errors: list[str] = []
    html = report.read_text(encoding="utf-8")
    root = report.parent

    left = sorted(set(re.findall(r"\{\{\s*[A-Za-z0-9_]+\s*\}\}", html)))
    if left:
        errors.append(f"置換されていない placeholder: {left[:8]}")

    for ref in sorted(set(re.findall(r'(?:src|href)="(assets/[^"#?]+)"', html))):
        if not (root / ref).is_file():
            errors.append(f"参照先が無い: {ref}")

    has_figure_img = bool(re.search(r"<figure[^>]*>\s*<img|class=\"views\"", html))
    if has_figure_img and 'querySelectorAll("figure img, .views img")' not in html:
        errors.append("図があるのに lightbox (拡大表示) の JS が無い。templates/skeleton.html から組み立てること")

    if 'id="stage"' in html:
        if re.search(r'\bshow\(\s*["\']', html):
            errors.append('viewer の JS が点群名を hardcode している (show("...")。初期表示は meta.clouds から決める)')
        if "names.indexOf" not in html:
            errors.append("viewer の JS が skeleton の正本と違う (初期点群を meta から決める処理が無い)")
        if "normalizer(META.scene_bbox)" in html:
            errors.append("viewer の JS が meta.scene_bbox を必須として読んでいる (無い meta で undefined.min になる)")
        meta_path = root / "assets" / "clouds" / "meta.json"
        if not meta_path.is_file():
            errors.append("3D ビューワがあるのに assets/clouds/meta.json が無い")
        else:
            errors += check_meta(meta_path)
    return errors


def check_meta(meta_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"meta.json を parse できない: {exc}"]
    clouds = meta.get("clouds")
    if not isinstance(clouds, dict) or not clouds:
        return ["meta.json の clouds が空か dict でない"]
    for name, info in clouds.items():
        missing = [k for k in ("file", "count", "min", "max", "label") if k not in info]
        if missing:
            errors.append(f"cloud {name!r} に key が無い: {missing}")
            continue
        if len(info["min"]) != 3 or len(info["max"]) != 3:
            errors.append(f"cloud {name!r} の min / max が 3 要素でない")
        f = meta_path.parent / info["file"]
        if not f.is_file():
            errors.append(f"cloud {name!r} の file が無い: {info['file']}")
            continue
        try:
            n = len(base64.b64decode(f.read_text(encoding="ascii").strip(), validate=True))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"cloud {name!r} の base64 が壊れている: {exc}")
            continue
        if n != int(info["count"]) * 9:
            errors.append(f"cloud {name!r}: decode {n} byte != count {info['count']} * 9 (uint16 xyz + uint8 rgb)")
    sb = meta.get("scene_bbox")
    if sb is not None and not (isinstance(sb, dict) and len(sb.get("min", [])) == 3 and len(sb.get("max", [])) == 3):
        errors.append("meta.json の scene_bbox は {min:[3], max:[3]} (任意。無ければ全 cloud の bbox の和を使う)")
    for key in ("cameras", "cameras_pred_aligned"):
        cams = meta.get(key, [])
        if not isinstance(cams, list):
            errors.append(f"meta.json の {key} が list でない")
            continue
        for i, c in enumerate(cams):
            K, T = c.get("K"), c.get("T_cw")
            if not (isinstance(K, list) and len(K) == 3 and all(len(r) == 3 for r in K)):
                errors.append(f"{key}[{i}].K が 3x3 でない")
            if not (isinstance(T, list) and len(T) == 4 and all(len(r) == 4 for r in T)):
                errors.append(f"{key}[{i}].T_cw が 4x4 でない")
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    report = Path(sys.argv[1])
    errors = check(report)
    if errors:
        print(f"[validate_report] NG: {report}")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"[validate_report] OK: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
