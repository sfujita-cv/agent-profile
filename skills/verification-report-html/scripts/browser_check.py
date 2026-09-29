#!/usr/bin/env python
"""検証レポートを実ブラウザ (headless Chromium) で開いて、図の拡大表示と 3D ビューワが動くかを確かめる。

validate_report.py は静的チェックしかできない。viewer の JS が実行時に落ちる (例: 点群名の取り違えで
`undefined.label`) と、Artifact 上では開いた人にしか見えない。publish の前にここで落とす。

検査内容:
1. report の directory を HTTP で配信する (viewer は fetch を使うので file:// では動かない)。
2. page error / console error が 0 件。
3. 3D ビューワがあれば: 点群ボタンを 1 つずつ押し、HUD が「<label> / <N> points」になり、
   エラー文言 (読み込めません / ありません) が出ないこと。WebGL の canvas が描画されること。
4. 図があれば: 最初の図を押すと lightbox が開き、拡大画像が読み込まれ (naturalWidth > 0)、
   もう一度押すと等倍表示、Esc で閉じること。
5. 証跡として viewer と lightbox の screenshot を `<report dir>/_browser_check/` に保存する
   (公開 assets には含めない)。

使い方 (Playwright + Chromium は scrapling の pixi env に入っている。読み取りのみで使う):

    pixi run --manifest-path ~/nanokit/claude/mcp-servers/scrapling/pixi.toml \\
        python ~/.claude/skills/verification-report-html/scripts/browser_check.py reports/<topic>/report.html

終了コード: 0 = OK、1 = NG、2 = 実行環境が無い (Playwright / Chromium)。
"""
from __future__ import annotations

import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path


class _Handler(http.server.SimpleHTTPRequestHandler):
    # charset を付けないと Chromium は windows-1252 と解釈し、日本語の HUD 文言の判定が狂う
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8",
                      ".txt": "text/plain; charset=utf-8"}

    def log_message(self, *args, **kwargs) -> None:   # アクセスログを出さない
        pass


def serve(root: Path) -> tuple[socketserver.TCPServer, int]:
    handler = functools.partial(_Handler, directory=str(root))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    report = Path(sys.argv[1]).resolve()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[browser_check] Playwright が無い。scrapling の pixi env で実行すること (docstring 参照)")
        return 2
    out = report.parent / "_browser_check"
    out.mkdir(exist_ok=True)
    httpd, port = serve(report.parent)
    url = f"http://127.0.0.1:{port}/{report.name}"
    errors: list[str] = []
    notes: list[str] = []
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                                  "--ignore-gpu-blocklist"])
            except Exception as exc:  # noqa: BLE001
                print(f"[browser_check] Chromium を起動できない: {exc}")
                return 2
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
            page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
            try:   # networkidle は重い図が多い page で不安定なので load (全 subresource) を待つ
                page.goto(url, wait_until="load", timeout=90000)
            except Exception as exc:  # noqa: BLE001
                print(f"[browser_check] NG: page を開けない: {str(exc).splitlines()[0][:200]}")
                return 1

            # --- 3D viewer ---
            if page.locator("#stage").count():
                page.wait_for_function("document.querySelectorAll('#cloudpick button').length > 0 || "
                                       "/読み込め|ありません/.test(document.getElementById('hud').textContent)",
                                       timeout=20000)
                hud0 = page.locator("#hud").inner_text()
                if any(w in hud0 for w in ("読み込め", "ありません")):
                    errors.append(f"viewer の初期表示が失敗: {hud0!r}")
                buttons = page.locator("#cloudpick button")
                for i in range(buttons.count()):
                    b = buttons.nth(i)
                    label = b.inner_text().strip()
                    b.click()
                    try:
                        page.wait_for_function("(l) => { const t = document.getElementById('hud').textContent;"
                                               " return t.includes(l) && /points/.test(t) && !/読み込み中/.test(t); }",
                                               arg=label, timeout=30000)
                    except Exception:  # noqa: BLE001
                        errors.append(f"点群 {label!r} が表示されない (HUD: {page.locator('#hud').inner_text()!r})")
                        continue
                    hud = page.locator("#hud").inner_text()
                    if any(w in hud for w in ("読み込め", "ありません", "undefined")):
                        errors.append(f"点群 {label!r} の HUD にエラー: {hud!r}")
                        continue
                    notes.append(f"cloud ok: {hud.splitlines()[0]} / {hud.splitlines()[1] if len(hud.splitlines()) > 1 else ''}")
                if not page.locator("#stage canvas").count():
                    errors.append("viewer の canvas が無い (WebGL を初期化できていない)")
                page.locator("#stage").scroll_into_view_if_needed()
                page.locator(".viewer").screenshot(path=str(out / "viewer.png"))

            # --- lightbox ---
            imgs = page.locator("figure img, .views img")
            if imgs.count():
                first = imgs.first
                first.scroll_into_view_if_needed()
                first.click()
                box = page.locator(".lightbox")
                try:
                    page.wait_for_function("() => { const b = document.querySelector('.lightbox');"
                                           " const i = b && b.querySelector('img');"
                                           " return b && b.getAttribute('aria-hidden') === 'false' && i && i.complete && i.naturalWidth > 0; }",
                                           timeout=15000)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"図を押しても lightbox が開かない / 画像が読み込まれない: {str(exc).splitlines()[0][:200]}")
                else:
                    page.screenshot(path=str(out / "lightbox_fit.png"))
                    box.locator("img").click()
                    if "is-actual" not in (box.get_attribute("class") or ""):
                        errors.append("lightbox の画像を押しても等倍表示に切り替わらない")
                    else:
                        page.screenshot(path=str(out / "lightbox_actual.png"))
                    page.keyboard.press("Escape")
                    if box.get_attribute("aria-hidden") != "true":
                        errors.append("Esc で lightbox が閉じない")
                    notes.append(f"lightbox ok ({imgs.count()} images bound)")

            # --- スマホ幅 (390px): 本文が横に流れず、拡大表示の画像が画面内に収まる ---
            m = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            m.on("pageerror", lambda e: errors.append(f"pageerror (mobile): {e}"))
            m.goto(url, wait_until="load", timeout=90000)
            overflow = m.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if overflow > 1:
                errors.append(f"スマホ幅で本文が横に {overflow}px はみ出す")
            mimgs = m.locator("figure img, .views img")
            if mimgs.count():
                target = mimgs.nth(min(1, mimgs.count() - 1))
                target.scroll_into_view_if_needed()
                target.tap()
                try:
                    m.wait_for_function("() => { const i = document.querySelector('.lightbox img');"
                                        " return i && i.complete && i.naturalWidth > 0; }", timeout=15000)
                    w = m.evaluate("document.querySelector('.lightbox img').getBoundingClientRect().width")
                    if w > 390 + 1:
                        errors.append(f"スマホ幅の拡大表示 (全体表示) で画像が画面より広い: {w:.0f}px")
                    m.screenshot(path=str(out / "mobile_lightbox_fit.png"))
                    m.locator(".lightbox img").tap()
                    m.screenshot(path=str(out / "mobile_lightbox_actual.png"))
                    notes.append("mobile ok (no horizontal overflow, lightbox fits)")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"スマホ幅で拡大表示の検査に失敗: {type(exc).__name__}: {str(exc).splitlines()[0][:200]}")
            browser.close()
    finally:
        httpd.shutdown()
    for n in notes:
        print(f"[browser_check] {n}")
    if errors:
        print(f"[browser_check] NG: {report}")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"[browser_check] OK: {report} (screenshots: {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
