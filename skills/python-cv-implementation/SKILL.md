---
name: python-cv-implementation
description: Python / NumPy / OpenCV / PyTorch / PyTorch3D による画像処理、computer vision、multi-view geometry、camera pose、depth、点群、NeRF、3D Gaussian Splatting の実装・リファクタ・レビューで使う規約とチェックリスト。shape / dtype / device / 座標系 / 単位 / 再現性を取り違えると静かに壊れる変更（新規実装、幾何変換、カメラ行列、resize/crop と intrinsics の更新、画像 I/O、テスト追加）では必ず使う。
---

# Python / CV / 3D 実装規約

画像処理、CV、3D reconstruction、NeRF、3D Gaussian Splatting、PyTorch 系コードを書くときの個人共通規約。リポジトリ固有の座標系・データ layout・検証コマンドは、そのリポジトリの `CLAUDE.md` / 設計書を優先する。

## 1. 着手前に確認すること

変更するすべての境界について、次の「データ契約」を書き出してから実装する。

| 項目 | 例 |
|---|---|
| shape と軸順 | `HWC` / `CHW` / `NCHW`、`N×3` / `B×N×3`、batch 次元の有無 |
| dtype と値域 | `uint8 [0,255]` / `float32 [0,1]` / `float16`、depth の invalid 値（0、NaN、負値） |
| device | CPU / CUDA、NumPy と Tensor のどちらか |
| 色 | RGB / BGR / RGBA、sRGB か linear か |
| 座標系 | OpenCV (x右 y下 z前) / OpenGL・three.js (x右 y上 z後) / PyTorch3D (x左 y上 z前)、右手系か左手系か |
| 単位 | meter / millimeter / scene-normalized unit、pixel か normalized coordinate か |
| 変換の向き | world-to-camera (`T_cw`) か camera-to-world (`T_wc`)、3x4 か 4x4、行ベクトルか列ベクトルか |

既存の public API、呼び出し元、既存テスト、サンプルコードも読む。規約が推測でしか分からない場合は、推測であることを報告に明記する。

## 2. shape / dtype / device

Tensor や配列を受け渡す関数では、docstring かコメントで次を明示する。

- `image`: HWC か CHW か、RGB か BGR か、値域。
- `depth`: shape、単位、invalid 値の表現。z-depth か ray 距離か。
- `intrinsics`: 3x3 か 4x4 か、`fx, fy, cx, cy` の並び、どの解像度に対する値か。
- `extrinsics`: world-to-camera か camera-to-world か。
- `points`: `N×3` か `B×N×3` か、どの座標系か。
- `transform`: 3x4 か 4x4 か、左から掛けるか右から掛けるか。

## 3. OpenCV / NumPy / PyTorch の落とし穴

- OpenCV の画像は BGR。`cv2.imread` は alpha を落とし、`IMREAD_UNCHANGED` 以外では 16bit depth も 8bit 化される。
- NumPy は HWC、PyTorch の画像 Tensor は CHW が多い。変換箇所を 1 箇所に集め、軸順を明示する。
- `torch.tensor(np_array)` は常にコピーする。共有したいなら `torch.from_numpy`、コピー意図を明確にしたいなら `torch.as_tensor` などを選び、意図をコメントに残す。
- device 指定のない `torch.tensor(...)` / `torch.zeros(...)` で CPU Tensor を混入させない。`x.new_tensor(...)` や `device=x.device` を使う。
- `permute` / `transpose` 後に `view` するなら `contiguous()` が必要。NumPy からの変換では負の stride（`[::-1]` など）に注意する。
- in-place 操作は autograd や共有 Tensor への影響を確認してから使う。
- `float16` / `bfloat16` では、正規化の分母、`exp`、大きな座標値の二乗で overflow・精度落ちが起きやすい。

## 4. camera / geometry

- OpenCV、OpenGL、three.js、PyTorch3D、COLMAP、Blender の座標系差を暗黙にしない。変換は名前付き関数にまとめ、変換行列をコメントに残す。
- `R`, `t`, `T_cw`, `T_wc` の命名を一貫させる。inverse を取る場合は何から何への変換かを書く。
- resize / crop / pad をしたら intrinsics を必ず更新する。pixel center 規約（整数座標が中心か角か、`+0.5` の有無）を明示する。
- depth から point cloud に戻すときは、pixel center、scale、intrinsics の解像度、z-depth と ray 距離の違いを明示する。
- 同次座標で depth 除算するときは、z ≤ 0（カメラの後ろ）と z ≈ 0 を扱う。
- metric と scale 不定の幾何を混ぜない。単位を黙って変えない。
- 正規化、逆行列、三角測量、投影、SVD / 固有値分解の境界では NaN / Inf と退化ケース（共線、平面、ゼロ baseline）を確認する。
- 回転は正規直交性（`R^T R = I`、`det R = +1`）が崩れていないか確認する。quaternion は `wxyz` / `xyzw` の並びを明示する。

## 5. テスト方針

重い GPU 実験の前に、小さく決定的なテストで幾何を切り分ける。

- shape と dtype のテスト。
- identity camera、純粋な平行移動、既知の回転での値の一致。
- round-trip（投影 → 逆投影、`T_wc @ T_cw = I`、座標系変換の往復）で元に戻ること。
- 光軸上の点、平面上の点、カメラ後方の点。
- resize / crop 後の intrinsics 更新。
- 空入力、1 要素入力、壊れた入力や欠損ファイル。
- 関係する場合は CPU / GPU の結果一致。

## 6. 変更時の注意

- 既存 API を変える場合は互換性への影響を明示する。
- 性能改善では、メモリ使用量・可読性とのトレードオフを説明する。
- 学習コードを変える場合は、再現性、seed、deterministic 設定への影響を報告する。
- dataset 処理を変える場合は、既存 cache や中間ファイルとの互換性（cache key に入るべき設定が入っているか）を確認する。
- 規約を repository から確認できず推測で補った箇所は、報告で「推測」と明記する。
