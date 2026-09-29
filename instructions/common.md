# 個人共通ルール

すべてのリポジトリで原則として守るルール。リポジトリの `CLAUDE.md` / `AGENTS.md` と食い違う場合はリポジトリ側を優先する。

## 回答と説明文書の言語方針

回答、README、plan、design note、review summary、PR description など、説明を伴う自然言語の成果物は原則として日本語で作成する。

コード内コメント、識別子、API 名、ログの key、設定項目名、外部ライブラリ由来の用語は、既存のコード規約や周辺文脈に合わせて英語のままでよい。

pull request も同じ方針で、**title の説明部分と body は日本語**で書く。英語のまま残すのは、Conventional Commits の type 接頭辞 (`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:` / `perf:` / `ci:`) と、上で挙げた識別子・API 名・path・設定キーの類だけ。PR 作成の手順は `create-pr` Skill にある。

第三者が読む文章では、見た目の幅を揃えるためだけの改行を入れない。改行は段落・箇条書き・コードブロックなど構造上の意味がある位置にだけ使う。

## 着手前

- 変更前に既存コード・設定・ドキュメントを読み、現在の設計意図と制約を確認する。変な実装に見えても、理由を確かめる前に消さない。
- 依頼内容を 1〜3 行で言い換え、仮定を明示する。解釈が複数あり結果が変わる場合は実装前に質問する。
- 検証可能な完了条件（どのコマンドがどう通れば終わりか）を先に決める。
- 設計書に MUST / 禁止 がある場合は実装契約として扱い、「適宜変更」して同じ実験 ID に混ぜない。

## 変更

- 要求を満たす最小の変更を優先し、無関係なリファクタリング・整形・依存更新を同時に行わない。
- 既存の public API、CLI、設定キー、データ形式、出力 path、実行手順を変える場合は互換性への影響を明示する。
- 調査用に入れた一時ログや計測コードは、最終差分に残すべきかを必ず判断する。

## 数値・幾何・テンソル

- 画像・テンソル・点群を扱う境界では shape、軸順（HWC / CHW / NCHW）、dtype、値域、device、座標系、単位を明示する。
- カメラ行列は world-to-camera か camera-to-world か、3x4 か 4x4 か、どの座標系規約（OpenCV / OpenGL / PyTorch3D など）かを命名かコメントで残す。
- 詳しいチェックリストは `python-cv-implementation` / `pytorch-debugging` Skill を使う。

## 標準 agent ワークフロー

container-use は使わない。Git submodule / 外部 vendor tree を含む構成で十分に安定しなかったため、標準の agent sandbox から外した。代わりに、Claude Code / Codex の agent 作業は git worktree と agent ごとの Docker Compose project で分離する。

次のコマンドは、主に agent が自分で実行する標準フロー。ユーザーに事前実行を求めず、実装・デバッグ・性能調査などの作業依頼を受けた agent が必要に応じて作成する。

```bash
scripts/create_agent_worktree.sh <agent-name>
scripts/enter_agent_container.sh <agent-name>
```

各 agent は `.claude/worktrees/<agent-name>` で作業する。ユーザーが既存 worktree や current checkout の使用を明示した場合だけ、その指示を優先する。各 agent は Docker Compose project name を分けて実行する (`docker compose -p <project-name> ...`)。作業後の片付けは `scripts/remove_agent_worktree.sh <agent-name>`。

ユーザーと agent の役割:

- ユーザーは、目的、変更してよい範囲、検証方法、制約を伝える。必要なら agent 名や既存 worktree を指定する。指定がなければ agent が短く安全な名前を決める。
- agent は、標準作業では worktree 作成、submodule 初期化、per-agent container 起動、検証、差分報告まで担当する。
- agent は、同名 worktree が既にあり未整理の差分がある場合、勝手に上書きせずユーザーに確認する。
- agent は、merge、branch 削除、worktree 削除を勝手に行わない。ユーザーが明示した場合だけ実行する。
- merge、push / PR 作成、branch 削除、worktree 削除を指示されたら、それを実行する**前に** `docs/<worktree-name>/YYYY-MM-DD-hhmm.md` として記録を残す (`worktree-retrospective` Skill)。同じ worktree で契機が続くときも、追記ではなく新しい file を作る。最終的な設計だけでなく、ユーザーとのやりとりの経緯と、なぜその決定に至ったか（却下した案を含む）を書く。
- agent は、検証目的の GPU ジョブ（バグ再現、テスト、性能計測、E2E 検証、smoke）を確認なしで実行してよい。事前確認が必要なのは、学習ジョブ、本番規模のデータ生成・cache 生成、数時間規模の実験だけ。
- agent が使う GPU はリポジトリの `CLAUDE.md` に従う。per-agent container では `CUDA_VISIBLE_DEVICES` が自動で設定される（リポジトリ固有の環境変数で上書きできる）。既存 container 内で直接実行する場合は `CUDA_VISIBLE_DEVICES` を明示する。
- agent が使う GPU を人間と共有している場合は、長い GPU ジョブを始める前に `nvidia-smi` で使用状況を確認し、他プロセスが専有していれば実行前にユーザーへ知らせる。

## 環境と依存関係の方針

Pixi を最上位の Python 依存管理ツールとして使う (pixi-only)。`uv` は禁止ではないが、必ず Pixi 環境の内側で使う。

許可される依存操作:

* `pixi add ...` / `pixi add --pypi ...`
* `pixi install` / `pixi install --locked`
* `pixi lock`
* `pixi run ...`
* `pixi run uv pip install ...`、ただし `pixi.toml` で安全に表現できない依存に限る

通常の agent 作業で禁止される依存操作:

* `pip install ...` / `python -m pip install ...` / `uv pip install ...`
* container image 内に焼いた Python 環境への直接書き込み
* グローバルな Python package installation
* `sudo apt install ...` / `apt-get install ...`
* `npm install -g ...` / `pnpm add -g ...` / `yarn global add ...`

新しい Python 依存が必要な場合は `pixi.toml` と `pixi.lock` を更新する。`pixi install` / `pixi run` は原則として container の中で実行する。ホストで実行すると、CUDA 版 torch などを含む環境一式をホストの worktree に作ってしまう。`pixi lock` のように環境を作らない操作はホストで実行してよい。

`--no-build-isolation`、`--find-links`、カスタム CUDA wheel index、Git URL、local editable install など pip 固有の指定が必要な例外的パッケージは、`scripts/install_pixi_uv_extras.sh` を更新し、`pixi run install-pip-extras` 経由で実行する。

OS レベルの依存が必要な場合は、実行中 container を直接変更せず、Dockerfile の変更として提案する。

## Docker と system 依存の方針

CUDA、apt package、OS library、CMake や native build、COLMAP、OpenGL / EGL / GLX / Qt / libX11 系の依存は Dockerfile 管理に残す。

共有 container に入って直接 package install してはいけない。agent 作業では worktree と Compose project name を分ける。

開発用 compose は `AGENT_WORKTREE_DIR` で現在の worktree を mount する。helper script は `.env.agent.<agent-name>` と、必要に応じて submodule read-only mount 用の `.claude/agent-compose/<agent-name>.submodules*.yml` を生成する。

## Git submodule 方針

- 通常の agent 作業では、submodule を読み取り専用の依存として扱う。
- ユーザーが明示的に submodule 変更を依頼しない限り、submodule 内のファイルを編集しない。
- submodule 変更が必要な場合は、submodule 側 repository で別タスク・別 PR として扱う。
- 親 repository の submodule pointer を不用意に更新しない。
- 作業前に submodule を初期化する (`git submodule update --init --recursive`)。
- submodule URL は、可能な限りローカル相対 path より remote URL (https) を優先する。相対 path は Docker や agent 環境内で壊れやすいため。

## AI コーディング依頼の進め方

実装、デバッグ、性能調査、レビューは原則として agent ごとの worktree で行う。これはユーザーの準備手順ではなく、依頼を受けた agent の行動規約である。

依頼を受けたら、まず現在位置と作業対象を確認する。

- すでに `.claude/worktrees/<agent-name>` 内で、依頼内容と一致する worktree なら、その worktree を再利用する。
- repository root や通常 checkout で依頼を受けた場合、実装・デバッグ・性能調査では agent 用 worktree を作成する。
- レビューだけでコード変更しない場合は、対象 diff を直接読んでよい。branch checkout や検証が必要なら review 用 worktree を作成する。
- current checkout での直接編集は、ユーザーが明示した場合、または小さなドキュメント・設定修正で worktree 分離の利益が小さい場合に限る。その場合も差分を明確に報告する。

worktree が必要な場合は、短く目的が分かる agent 名（例: `impl-camera-path`）を使う。

実装の依頼では、目的、変更してよい範囲、期待する検証コマンドを確認する。依存追加が必要な場合は `pixi.toml` / `pixi.lock` を更新し、OS 依存は Dockerfile 変更として扱う。

デバッグや性能調査の依頼では、再現手順、入力データ、ログ、期待値、実際の挙動を確認する。

レビューの依頼では、対象 branch / PR / diff と、特に見てほしい観点を確認する。レビュー担当 agent は原則としてコードを直接変更せず、重大度順に指摘する。設計書がある場合は MUST / 禁止 との整合（型の分離、cache key、予算などの契約）を必ず見る。

## 作業報告の必須項目

branch や worktree を作って実装・修正・検証を行ったら、報告の最後に次の 2 つを必ず含める。書式とテンプレートは `agent-work-report` Skill にある。

- **再現コマンド**: 人間が同じ処理を再実行できるコマンド列。worktree 作成 → container 起動 → 検証実行まで、リポジトリ root からコピペでそのまま通る形にする。省略や「適宜読み替えてください」は書かない。
- **根拠出力の所在**: 検証で証跡（画像、`.ply`、ログ、メトリクス、cache の diagnostics.json など）を作った場合、それぞれについて「何の出力か」「どこにあるか（path）」「どのコマンドで生成したか」を表で明記する。「出力を確認しました」だけの報告は不可。

path は worktree 内かどうかも書く。worktree 内の成果物は worktree 削除で消えるため、残す必要があるものは primary checkout 側（または run 出力用の共有ディレクトリ）へ退避する。

実行していない手順を再現コマンドに混ぜる場合は、その行に「未実行」と明示する。

画像や点群を見ないと評価できない検証は、テキストの報告に加えて HTML レポートを作る（`verification-report-html` Skill）。**HTML レポートを作ったら、必ず Artifact として公開し、報告に URL を載せる。** ユーザーはスマホや外出先の PC から報告を読むことがあり、ローカルの絶対 path だけでは開けない。ローカルの HTML は配布用として残したうえで、URL を併記する。

## 検証方針

- 実行していない検証を、実行済みとして報告しない。未実施なら理由と残るリスクを分けて書く。
- CPU fixture や synthetic テストの pass を、実モデル・GPU・画質・本番条件での検証と混同しない。
- 性能比較では入力、ハードウェア、container / image、warm / cold、cache hit / miss、反復回数、統計量を揃えて書く。条件を削った最良値だけを示さない。
- 環境変更では、リポジトリの doctor script（`scripts/doctor_agent_worktree_pixi.sh`）と `docker compose ... config` を優先して確認する。`pixi.toml` / `pixi.lock` を変えた場合は `pixi lock && pixi install --locked && pixi run python --version` まで確認する。具体的な実行場所とコマンドはリポジトリの `CLAUDE.md` に従う。
- 10 分を超える見込みのジョブ（Docker image の build を含む）は、agent の Bash tool の timeout 上限に当たるため background 実行にする。

## Git と破壊的操作

- 破壊的 Git 操作（`reset --hard`、`checkout -- .`、`clean -fd`、force push、履歴の書き換え）、既存 worktree や branch の削除は、明示要求がない限り行わない。
- 1 commit = 1 つの論理的変更にする（`git-commits` Skill）。commit / push / PR 作成はユーザーが求めたときだけ行う。
- 秘密情報（API token、認証情報、private key）をコード・ログ・報告・commit に含めない。
