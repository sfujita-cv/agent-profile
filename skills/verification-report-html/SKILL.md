---
name: verification-report-html
description: "実装や検証の結果を HTML レポートにまとめ、Artifact として公開して URL で渡すときに使う。画像・点群・3D の結果を見ないと良し悪しが判断できない検証、before/after 比較が主題の報告、数値や表が多くターミナルでは追えない報告で使う。「レポートにして」「web で見せて」「結果を可視化して」などで呼び出す。"
user-invocable: true
---

# 検証レポート (HTML)

実装・検証の結果を HTML レポートにして、**Artifact として公開し URL で渡す**。ユーザーはスマホや外出先の
PC から読むので、URL は必須。ローカルの path だけで報告を終えない。

要件:

1. **値だけで終わらせない。** 失敗していれば見え方が変わる図 (GT との画素比較、再投影、分布) を添え、各図の
   caption に「どこを見れば妥当性が判断できるか」を書く。
2. **3 次元点群は three.js のビューワで触れるようにする。**
3. **図はタップ / クリックで拡大表示できること。** matplotlib の図は本文幅では小さくて読めない。
4. **開いたら壊れている、を出さない。** viewer が点群を表示しない不具合を 1 度出している (下の「失敗の記録」)。

## 使うかどうか

使う: 画像・点群・3D を見ないと判断できない / before-after 比較 / 表と数値が多い。
使わない: 数行のログとテキストの結論で足りる。その場合は `agent-work-report` skill の書式だけで報告する。

## 骨格の正本は 1 つだけ

**report の HTML を過去の report から copy しない。** head (CSS)、3D viewer の JS、拡大表示の JS は
`templates/skeleton.html` だけが正本で、report ごとに書くのは **body (`<section>` の並び) だけ**。
過去 report を copy すると、骨格側の bug がそのまま次の report に伝播する (実際に起きた。下の記録)。
骨格を直すときは skeleton を直し、既存 report は `build_report.py` で組み直す。

## 手順

### 1. 素材を作る

**まず検証が既に出力している画像・動画を流用する。** 無い場合にだけ追加レンダリングする。無駄な GPU 実行を増やさないため。
図・点群・画像は検証 script に `report_assets/` のような 1 つのディレクトリへ書き出させる。

- 図の文字は英語 (container に日本語 font が無いことが多い)。説明は HTML の caption に書く。
- 点群は 1 cloud につき 1 つの base64 text file (`assets/clouds/<name>.txt`) にする。中身は `count * 9` byte で、
  先頭に xyz を cloud ごとの `min` / `max` で uint16 に量子化した列 (little-endian、`count * 3` 個)、続けて
  rgb の uint8 列 (`count * 3` 個)。そのうえで `assets/clouds/meta.json` を下の schema で書く。
- `.ply` から turntable のプレビュー (静止画 + 動画) が要るときだけ `scripts/render_ply_preview.py` を使う。
  入力の property から 3DGS か点群かを自動判定する。色付き点群は CPU だけで動くが、3DGS は GPU と gsplat が
  要るので container 内で実行する。姿勢がおかしければ `--up` / `--elevation` / `--distance-scale` で調整する。

```bash
python ~/.claude/skills/verification-report-html/scripts/render_ply_preview.py \
  <input.ply> --out-dir <report_assets dir> --frames 60
```

### 2. body を書く

`<section>` を並べる。節の構成: 状態の要約 / 何をしたか / 検証 (図ごとに 1 節) / 3D ビューワ /
判断と残課題 / **再現コマンド**。根拠出力と再現コマンドは `agent-work-report` skill と同じ内容にし、
テキスト報告と食い違わせない。数値は `{{key}}` にして `--values` の JSON で埋めてよい。

部品の書き方 (これ以外の書き方をすると、拡大表示や横スクロールが効かない):

```html
<!-- 図: figure > img は自動で拡大表示 (タップで全画面、もう一度で等倍、Esc で閉じる) になる -->
<figure>
  <img src="assets/xxx.png" alt="何の図か (拡大表示の見出しにも出る)" loading="lazy">
  <figcaption><b>見るところ</b>: 健全ならどう見え、壊れていればどう見えるか。</figcaption>
</figure>

<!-- 表: 必ず .table-wrap (または .scroll) で包む。スマホ幅で本文ごと横に流れないように -->
<div class="table-wrap"><table>...</table></div>

<!-- 3D ビューワ: この markup をそのまま使う。id は JS が参照する -->
<div class="viewer">
  <div class="viewer-stage" id="stage">
    <div class="viewer-hud" id="hud">読み込み中…</div>
    <div class="viewer-hint">ドラッグ: 回転 ・ ホイール: ズーム ・ 右ドラッグ: 移動</div>
  </div>
  <div class="viewer-bar">
    <div class="cloudpick" id="cloudpick"></div>
    <label>点サイズ <input type="range" id="psize" min="1" max="10" step="1" value="3"></label>
    <label><input type="checkbox" id="showcams" checked> camera</label>
    <label><input type="checkbox" id="showpred" checked> 予測 camera</label>  <!-- meta に無ければ自動で隠れる -->
    <button type="button" id="resetview">視点を戻す</button>
  </div>
</div>
```

`assets/clouds/meta.json` の schema (viewer はこれ以外の key に依存しない):

| key | 必須 | 内容 |
|---|---|---|
| `clouds` | ✓ | `{name: {file, count, min[3], max[3], label, frame?}}`。1 つ以上。**初期表示は `all` があればそれ、無ければ先頭**。名前は自由 |
| `cameras` | ✓ | `[{K: 3x3, T_cw: 4x4 (OpenCV w2c), hw: [H, W]}]`。空 list 可 |
| `cameras_pred_aligned` | ✓ | 同上 (破線で描く)。無ければ `[]`。空なら toggle は隠れる |
| `scene_bbox` | 任意 | `{min[3], max[3]}`。無ければ全 cloud の bbox の和で正規化する |
| `frame` | 任意 | HUD に出す座標系の名前 (既定 `episode`) |

### 3. 組み立てて検査する

```bash
python ~/.claude/skills/verification-report-html/scripts/build_report.py \
  --body <body.html> --assets <report_assets dir> --out reports/<topic> \
  --title "<2〜4 語の名詞句>" [--values values.json]
```

`reports/` は **primary checkout 側** (worktree 内は削除で消える。gitignore 対象なので merge でも運ばれない)。
`build_report.py` は最後に `validate_report.py` (静的チェック) を自動で走らせる: placeholder の置換漏れ、
`assets/` の参照切れ、拡大表示 JS の有無、meta.json の schema と点群 file の byte 数、viewer JS の
既知の誤り (点群名の hardcode、`scene_bbox` の必須化)。

**続けて実ブラウザで検査する (必須。NG なら publish しない):**

```bash
pixi run --manifest-path ~/nanokit/claude/mcp-servers/scrapling/pixi.toml \
  python ~/.claude/skills/verification-report-html/scripts/browser_check.py reports/<topic>/report.html
```

headless Chromium (scrapling の pixi env に入っている Playwright。読み取りのみで使う) で report を HTTP 配信して開き、
page error が 0 件、点群ボタンを全部押して HUD が「label / N points」になる、図を押すと拡大表示が開いて等倍・Esc
が効く、**390px 幅 (スマホ) で本文が横にはみ出さず、拡大表示の画像が画面内に収まる**ことを確かめる。
screenshot を `reports/<topic>/_browser_check/` に残すので、**viewer.png は目でも見る** (点が描画され、
camera 錐体が点群の手前にあるか)。

### 4. Artifact として公開する

`build_report.py` が出力する `file_path` / `root` / `files` をそのまま Artifact tool に渡す。`icon` は初回だけ。
更新は同じ conversation なら同じ `file_path` で再 publish (同じ URL)。別の conversation からは `url` を渡す。

報告には Artifact の URL と、ローカルの path (`reports/<topic>/report.html`) の両方を書く。3D ビューワは
`fetch` を使うので `file://` では動かない (図と表は動く) ことを添える。

## 設計上の決めごと

- **three.js は cdnjs の UMD `three.js/r128/three.min.js`**。Artifact の CSP は cdnjs 以外の script を弾く。
  OrbitControls は含まれないので orbit 操作は skeleton の自前実装。
- **点群は base64 text (.txt)**。Artifact は `.bin` を配信しない。PNG に詰める案は browser の color management が
  byte を書き換えて幾何が静かに壊れうるので使わない。
- viewer は OpenCV の y 下向きを見やすさのため y 反転して描く。camera 錐体も同じ変換。
- dark theme は `:root` / `prefers-color-scheme` / `data-theme` の 3 状態で解決させる (skeleton の CSS)。

## 失敗の記録 (なぜこの手順か)

複数の report で 3D ビューワが「点群 metadata を読み込めませんでした (Cannot read properties of undefined
(reading 'label'))」と出て点群が表示されなかった (ユーザー指摘)。原因は 2 つ重なっていた。

1. viewer の JS が初期表示を `show("all")` と **点群名を hardcode** していた。最初の report は点群名に `all` を
   含んでいたので動き、別の名前を使う後続 report で `undefined.label` になった。
2. その奥で `normalizer(META.scene_bbox)` が **最初の report の生成 script だけが書く meta の key** を必須に
   していた。1 を直すと次に `undefined.min` で落ちる。

どちらも「過去の report HTML を copy して body を差し替える」作り方で伝播し、静的には見えず、開いた人にしか
分からなかった。対策は (a) 骨格を skill の skeleton 1 つに集約、(b) meta の schema を明文化し viewer が
それ以外に依存しない、(c) 静的チェックと実ブラウザ検査を publish の前に必須にする、の 3 つ。
同じときに、表の横スクロール用 class (`table-wrap`) が CSS に定義されておらずスマホ幅で本文がはみ出していたこと、
拡大表示が無く図が読めないことも指摘・修正した。

## オフライン配布用の自己完結 HTML

3D ビューワは `fetch` を使うので HTTP 配信が要る (`file://` では CORS で読めない)。ネットワークの無い相手に
ファイルだけで渡したいときは、画像・動画を data: URI で内包した自己完結 HTML を別に作る。`<img>` と `<video>` は
fetch ではない通常のサブリソース読み込みなので、`file://` でも表示される (3D ビューワは動かないので、点群は
`render_ply_preview.py` の静止画・動画で見せる)。

```bash
python ~/.claude/skills/verification-report-html/scripts/embed_assets.py \
  reports/<topic>/report.html reports/<topic>/YYYY-MM-DD_<topic>.html
```

- **base64 を自分の出力に書かない。** 数 MB のテキストになりトークンを浪費する。変換は必ず script に行わせる。
- 最終 HTML は **20MB 目安 / 50MB 上限** (base64 で約 1.33 倍に膨らむ)。超えそうなら画像を長辺 1280px に縮小し、
  動画を 720p / 6-10 秒に収める。`embed_assets.py` が目安超過で警告、上限超過で異常終了する。
- 自己完結版をそのまま Artifact に publish しない。1 ファイルが数 MB になり読み込みが重い。publish は上の手順で
  assets を個別ファイルとして渡す。

## 同梱 script

- `scripts/build_report.py`: skeleton と body から report を組み立て、Artifact 用の `files` を出力する。
- `scripts/validate_report.py`: 静的チェック (`build_report.py` が自動で呼ぶ)。
- `scripts/browser_check.py`: headless Chromium での実ブラウザ検査。
- `scripts/render_ply_preview.py`: `.ply` (色付き点群 / 3DGS) の turntable 画像 / 動画。
- `scripts/embed_assets.py`: 画像・動画を data: URI で内包した自己完結 HTML を作る。
- `scripts/template.html` / `scripts/make_artifact_html.py`: skeleton 以前の旧テンプレート (doctype 付き) と、
  そこから公開用を派生させる script。skeleton で組んだ report には不要 (skeleton は最初から doctype /
  head / body を持たない)。

## 関連

- `agent-work-report` skill — 再現コマンドと証跡の書式。
- `worktree-retrospective` skill — worktree の記録から report を参照する。
- `html-report-writing` skill (nanokit) — HTML レポートの骨格・CSS 規約。旧テンプレートの土台。
