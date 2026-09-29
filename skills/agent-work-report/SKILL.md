---
name: agent-work-report
description: "branch / worktree で実装・修正・検証を行った作業の報告を書くときに使う。人間が同じ処理を再実行できる再現コマンドと、検証の根拠となった出力の所在を、決まった書式で報告に含める。「作業報告」「再現コマンドを出して」「証跡をまとめて」などで呼び出す。実装・デバッグ・性能調査・E2E 検証の報告の締めくくりでは、明示指示がなくても必ずこの書式に従う。"
user-invocable: true
---

# 作業報告の書式

branch や worktree を作って作業したら、報告の最後に **再現コマンド** と **根拠出力の所在** を必ず載せる。
リポジトリの `CLAUDE.md` に `## 作業報告の必須項目` があればそれが規範、この skill が書式。

## 原則

- 人間がコピペしてそのまま通ること。「適宜読み替えてください」で逃げない。
- 実行していないコマンドを実行済みのように並べない。未実行の行には `# 未実行` を付ける。
- path は worktree 内か primary checkout 側かを区別する。worktree 内の成果物は worktree 削除で消える。

## 1. 再現コマンド

リポジトリ root からの相対 path で、4 段に分けて書く。worktree / container の具体的なコマンドはリポジトリの `CLAUDE.md` に従う。以下は agent worktree と per-agent container を使うリポジトリでの形。

```bash
# 1. worktree 作成
scripts/create_agent_worktree.sh <agent-name>

# 2. container 起動（対話で入る場合）
scripts/enter_agent_container.sh <agent-name>

# 3. 検証実行（非対話。-- 以降は worktree root で実行される）
scripts/enter_agent_container.sh <agent-name> -- python -m pytest tests/<target> -v

# 4. 後片付け（ユーザー判断。agent は勝手に実行しない）
scripts/remove_agent_worktree.sh <agent-name>
```

書くときに外さない点:

| 項目 | 理由 |
|---|---|
| 実行時の cwd を明示する（必要なら `-- bash -c "cd <subdir> && ..."`） | wrapper 経由の `--` 以降は worktree root で実行されるため、サブディレクトリ前提のコマンドは通らない |
| 本番と挙動が変わる既定値は、本番相当の設定を明示的に指定する | debug 出力や中間 cache を書く既定のままだと、2 回目以降が cache に当たって本番と違う経路になる |
| cwd 相対の resource path に依存しない設定を選ぶ | gitignore された resource は worktree に存在しない |
| 複数の container / compose を持つリポジトリでは、どれで実行したかを書く | 依存やハードウェアが違い、同じコマンドでも経路が変わる |
| cache の key と hit / miss を書く | 入力や設定で key が変わり、hit と miss で経路も時間も違う |
| 使った GPU を書く。既定と違う GPU なら上書きの環境変数を前置する | 別の shell では既定値が違う |
| 10 分超の見込みなら background 実行と書く | agent の Bash tool の timeout 上限に当たる |

コード変更を伴う場合は、branch 名と commit を添える。branch が消えても追試できるようにするため。

```bash
git -C .claude/worktrees/<agent-name> log --oneline -5
# branch: agent/<agent-name>  tip: <SHA>
```

## 2. 根拠出力の所在

検証で証跡を作ったら、**必ず表で**出す。「出力を確認しました」だけの報告は不可。

| 出力 | path | 何を示すか | 生成コマンド |
|---|---|---|---|
| 点群 | `.claude/worktrees/<name>/<out>/points.ply` (worktree 内) | 穴の有無、scale の異常を見る | 上記 3 |
| cache 診断 | `<cache-root>/<key>/diagnostics.json` (共有ディレクトリ) | cache の中身と統計 | 上記 3 |
| 実行ログ | `reports/<name>/src/assets/run.log` (primary) | 各 step の所要時間 | 上記 3 を `tee` |

書き方のルール:

- path は「worktree 内」か「primary checkout」かを括弧で明記する。
- 数値の主張（速くなった、精度が上がった）には、その数値が載っている file と行を示す。
- 残す必要がある証跡は、worktree 削除の前に primary checkout 側へ退避する。

## 3. 実行済み / 未実行の区別

```bash
# 実行済み: 3 回計測して中央値 42.1s
scripts/enter_agent_container.sh impl-x -- python scripts/bench.py

# 未実行: 全条件の評価は数時間かかるため未実行。必要なら以下で確認できる
scripts/enter_agent_container.sh impl-x -- python scripts/evaluate.py --split val
```

## 4. 性能値を報告するとき

「N 秒になった」と数値で主張するなら、**その数値が何を含み何を含まないか**を同じ表に書く。
条件が 1 つ違うだけで 2 倍変わるので、数値だけ出すと受け取り側が本番の値として読む。

| 条件 | 書くこと | 省くと起きること |
|---|---|---|
| image | 計測に使った image ID (`docker images <image> -q`) | **常駐 container は image を再ビルドしただけでは切り替わらない。**`docker compose run` は毎回新しい container なので新 image、起動しっぱなしの container は作り直すまで旧 image。新 image で測った値が相手の手元で再現しない |
| cache | 各 cache が `hit` か `miss` か、中間結果を再利用したか新規作成したか | hit / 再利用の値を cold path と誤読される。比較には cache を無効化する設定を使う |
| model load | cold (model load 込み) か warm か | 大きなモデルのロードは秒〜十秒単位。どの区間を測ったかを区間名で書く |
| 設定 | debug 出力、resource、runtime などの override | debug 出力を書く設定は本番より遅い。model load を job の外に出す設定では値が大きく変わる |
| 入力規模 | 入力 ID、枚数・視点数、解像度、要求した予算と実際の値 | 計算量と処理経路が変わる。要求値と実際の値を混同しない |

そのうえで、**ユーザーが実際に打つコマンドそのままの実測を最低 1 本**載せる。
条件を削った最良値だけを示さない。

過去の失敗例:

| 条件 | 前処理の所要時間 |
|---|---|
| 元コマンドそのまま (中間結果 reuse / cache miss / 改善前) | 36.55s |
| 同条件 / 改善後 | 17.89s |
| + model load を job の外に出す設定 + 本番相当の debug 設定 | 5.93s |

この 3 行目だけを「本番プロファイルでは 5.93s」と報告したところ、ユーザーの手元では 11.59s だった。
差は **SfM 4.3s (中間結果を作る cold path だった)** と **旧 image の container で後処理が
旧実装にフォールバックした 1.3s**。どちらも条件欄があれば防げた。

## 5. HTML レポートに格上げする判断

次に当てはまるならテキスト報告に加えて `verification-report-html` skill で HTML レポートを作る。

- 画像・点群・3D の結果を見ないと良し悪しが判断できない。
- before/after の比較が主題である。
- 表や数値が多く、ターミナルのスクロールでは追えない。

数行のログとテキストの結論で足りるなら、HTML は作らない。

HTML レポートを作ったら、**Artifact として公開して報告に URL を載せる**。ユーザーはスマホや
外出先の PC から報告を読むことがあり、ローカルの絶対 path だけでは開けない。手順は
`verification-report-html` skill の「Artifact として公開する」節にある。
