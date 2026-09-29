---
name: pytorch-debugging
description: PyTorch / CUDA / mixed precision / DataLoader / training loop / loss / gradient の不具合（shape mismatch、device・dtype mismatch、NaN・Inf、CUDA OOM、メモリリーク、静かな数値破損、速度低下・性能 regression）を、最小再現 → 仮説の切り分け → 最小修正の順で調べるときに使う。学習・推論・テンソル処理が落ちる、遅い、値がおかしいと言われたら修正前に必ず使う。
---

# PyTorch デバッグ手順

## 1. 基本方針

1. 修正前に失敗を再現する。最小の command / 入力 / step 数 / batch で再現できる形に固定し、記録する。
2. 観測事実と仮説を分ける。
3. 最も早い怪しい境界に計測を入れ、shape、dtype、device、min / max、finite 比率、意味上重要な次元を見る。
4. 最も安く、仮説を区別できる確認から実行する。
5. 観測を説明できる最小の修正を入れる。
6. 元の再現手順と、近い regression テストを再実行する。

長時間学習ではなく、短い step 数や小さい batch で再現する。調査用ログは最終差分に残すものだけ残す。GPU の割り当てや container での実行方法はリポジトリの `CLAUDE.md` に従う。

## 2. NaN / Inf

最終的な loss ではなく、最初に非有限値が出た Tensor を探す。

1. 入力 Tensor に NaN / Inf がないか。
2. loss 計算の前後。
3. ゼロ除算、`log(0)`、負値の `sqrt`、`acos` / `asin` の定義域外、空の reduction（要素 0 個の `mean`）。
4. mixed precision での overflow（`exp`、大きな二乗和、softmax 前の logits）。
5. `GradScaler` の `unscale_` と gradient clipping の順序。
6. learning rate、loss weight、正規化係数が極端でないか。
7. clip 前後の gradient norm。

```python
assert torch.isfinite(x).all(), "x contains NaN or Inf"
torch.autograd.set_detect_anomaly(True)  # slow; enable only while narrowing down
```

## 3. CUDA OOM・メモリ

- `torch.cuda.memory_allocated()` と `memory_reserved()` を分けて見る。reserved だけ大きいなら断片化（`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` など）を疑う。
- 期待されるモデル・入力の footprint と、リークを区別する。step ごとに allocated が増え続けるならリーク。
- Tensor を Python の list / dict に蓄積していないか（`loss` をそのまま append すると graph ごと保持される。`.item()` か `.detach()`）。
- 不要な `retain_graph=True`。
- validation / 推論で `torch.no_grad()` / `torch.inference_mode()` を使っているか。
- 大きな中間 Tensor、attention など二次のメモリを使う演算、モデルの重複コピー。
- batch size、解像度、ray 数、点数、sample 数が増えていないか。

## 4. device / dtype mismatch

よくある原因:

- device 指定なしの `torch.tensor(...)` による CPU Tensor の混入。
- `register_buffer` すべき定数がただの attribute になっていて `.to(device)` で移動しない。
- NumPy 変換後に device へ戻し忘れている。
- DataLoader の batch の一部だけ device 転送されている（ネストした dict / list）。
- autocast の境界で dtype が変わり、index Tensor や integer Tensor と混ざる。

対策は `x.new_tensor(...)` / `device=x.device`、`register_buffer`、batch 転送を再帰的に行う関数への集約。

## 5. shape mismatch

1. エラーが出た演算の直前で shape を確認する。
2. batch 次元の有無を確認する。
3. channel 次元の位置を確認する。
4. broadcasting が意図通りか確認する（`(N,)` と `(N,1)` の混同は静かに `N×N` になる）。
5. `view` より `reshape`、あるいは einops 相当の明示的な書き方を検討する。
6. HWC / CHW、`B×N×3` / `N×3`、3x4 / 4x4、行ベクトル / 列ベクトルの混同を確認する。

## 6. DataLoader

- まず `num_workers=0` で再現するか確認する。
- 壊れた画像・動画・json・npz・pth が混ざっていないか。
- `collate_fn` が可変長データを正しく扱うか。
- worker ごとの random seed が意図通りか（`worker_init_fn`）。
- multiprocessing で pickle できない object を持っていないか。shared memory（`/dev/shm`）が足りているか。
- `persistent_workers` と transform の状態の組み合わせ。

## 7. 性能 regression

- warm-up と steady state を分ける。初回の cuDNN autotune、`torch.compile` の compile、model load を混ぜない。
- 同期点（`.item()`、`.cpu()`、`print(tensor)`、`torch.cuda.synchronize()`）と host-device 転送を探す。
- Python ループ、DataLoader 待ち、I/O、再コンパイル（shape が毎回変わる）、cache miss を確認する。
- 計測は同じ入力、同じ warm / cold 条件、同じ image / container、複数回の反復で比べ、統計量（中央値など）を明記する。

## 8. 報告テンプレート

```md
## 再現
- `<command>`（入力、step 数、GPU、image）

## 原因候補
1. <仮説> - <根拠>
2. <仮説> - <根拠>

## 切り分け
- `<command / check>`: <結果>（どの仮説を棄却・支持したか）

## 修正
- `<path>`: <最小修正の説明>

## 検証
- `<command>` → <結果>
- 未実行: <高コスト・環境がなく実行していない確認と、その理由>
```
