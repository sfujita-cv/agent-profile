#!/usr/bin/env python3
"""`.ply` から turntable の静止画 + プレビュー動画 (MP4) を作る。

対話的な 3D ビューワは作らない。file:// では PLYLoader の fetch が CORS で落ちて
HTTP 配信が必須になり、「レポートを D&D するだけで開ける」という要件と両立しないため。
代わりにオフラインでレンダリングした画像と動画を置き、embed_assets.py で HTML に内包する。

入力の property を見て 2 経路に分岐する:
  - 3DGS  (f_dc_*, opacity, scale_*, rot_* を持つ) -> gsplat.rendering.rasterization (GPU 必須)
  - 色付き点群 (x,y,z + red,green,blue)            -> numpy + cv2 で z-sort 投影 (CPU のみ)

点群側に OpenGL / Open3D offscreen を使わないのは、headless container で EGL/OSMesa 依存が
壊れやすいため。数十行の投影で目的を満たす。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

# 3DGS の DC 項を RGB に直す係数 (spherical harmonics の 0 次)。
SH_C0 = 0.28209479177387814

UP_VECTORS = {
    "+x": (1.0, 0.0, 0.0), "-x": (-1.0, 0.0, 0.0),
    "+y": (0.0, 1.0, 0.0), "-y": (0.0, -1.0, 0.0),
    "+z": (0.0, 0.0, 1.0), "-z": (0.0, 0.0, -1.0),
}


def lookat_c2w(eye, target, up, keyframe_index: int = 0) -> np.ndarray:
    """OpenCV 規約 (右 x / 下 y / 前 z) の camera-to-world 4x4 を作る。

    `up` は world の上方向。camera の y 軸 (下) が -up を向くように x = cross(z, up) と取る。
    """
    eye = np.asarray(eye, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    up = np.asarray(up, dtype=np.float64)
    z = target - eye
    z /= max(np.linalg.norm(z), 1e-12)
    x = np.cross(z, up)
    if np.linalg.norm(x) < 1e-9:
        raise ValueError(f"view direction is parallel to up at keyframe {keyframe_index}")
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    c2w = np.eye(4)
    c2w[:3, 0], c2w[:3, 1], c2w[:3, 2], c2w[:3, 3] = x, y, z, eye
    return c2w


def write_video_mp4(path: Path, frames, fps: int) -> None:
    """H.264 (imageio-ffmpeg があれば) か、無ければ OpenCV の mp4v で書く。

    ブラウザ再生には H.264 が要る。mp4v で書いた場合は警告を出す。
    """
    try:
        import imageio.v2 as imageio

        writer = imageio.get_writer(str(path), fps=fps, codec="libx264", quality=7,
                                    macro_block_size=None)
        for f in frames:
            writer.append_data(f)
        writer.close()
        return
    except Exception as exc:  # imageio-ffmpeg が無い / codec 不可
        print(f"[render-ply-preview] imageio/ffmpeg unavailable ({exc}); falling back to OpenCV mp4v",
              file=sys.stderr)
    import cv2

    h, w = frames[0].shape[:2]
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        out.write(cv2.cvtColor(f, cv2.COLOR_RGB2BGR))
    out.release()
    print("[render-ply-preview] WARNING: mp4v で書き出した。ブラウザで再生できない場合は "
          "imageio-ffmpeg を入れて再実行する。", file=sys.stderr)


# ---------------------------------------------------------------------------
# PLY 読み込みと種別判定
# ---------------------------------------------------------------------------

def load_ply(path: Path):
    from plyfile import PlyData

    ply = PlyData.read(str(path))
    vertex = ply["vertex"]
    names = set(vertex.data.dtype.names or ())
    return vertex, names


def is_splat(names: set[str]) -> bool:
    # 3DGS は色を f_dc_* で持ち、scale_/rot_/opacity を伴う。
    return "f_dc_0" in names and "opacity" in names and "scale_0" in names


def xyz_of(vertex) -> np.ndarray:
    return np.stack([vertex["x"], vertex["y"], vertex["z"]], axis=1).astype(np.float64)


def rgb_of(vertex, names: set[str], n: int) -> np.ndarray:
    """0-1 の float RGB を返す。色が無ければ薄いグレーにする。"""
    for r, g, b in (("red", "green", "blue"), ("r", "g", "b")):
        if {r, g, b} <= names:
            c = np.stack([vertex[r], vertex[g], vertex[b]], axis=1).astype(np.float64)
            # uint8 で入っていれば 0-255、float なら既に 0-1 とみなす。
            return np.clip(c / 255.0 if c.max() > 1.5 else c, 0.0, 1.0)
    return np.full((n, 3), 0.75)


# ---------------------------------------------------------------------------
# カメラ
# ---------------------------------------------------------------------------

def scene_frame(points: np.ndarray) -> tuple[np.ndarray, float]:
    """外れ値に引きずられないよう、中央値と分位数で中心・半径を決める。"""
    center = np.median(points, axis=0)
    radius = float(np.percentile(np.linalg.norm(points - center, axis=1), 95))
    return center, max(radius, 1e-6)


def orbit_c2ws(center, radius, up_key, frames, fov_deg, elevation_deg, distance_scale):
    """turntable の各姿勢を lookat_c2w で作る。"""
    up = np.asarray(UP_VECTORS[up_key], dtype=np.float64)
    # up と直交する 2 軸を作り、その平面上を周回する。
    seed = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(seed, up)) > 0.9:
        seed = np.array([0.0, 0.0, 1.0])
    axis_a = np.cross(up, seed)
    axis_a /= np.linalg.norm(axis_a)
    axis_b = np.cross(up, axis_a)
    axis_b /= np.linalg.norm(axis_b)

    dist = distance_scale * radius / np.tan(np.deg2rad(fov_deg) * 0.5)
    elev = np.deg2rad(elevation_deg)

    out = []
    for i in range(frames):
        theta = 2.0 * np.pi * i / frames
        offset = (np.cos(theta) * axis_a + np.sin(theta) * axis_b) * np.cos(elev) + up * np.sin(elev)
        out.append(lookat_c2w(center + offset * dist, center, up, keyframe_index=i))
    return out


def intrinsics(width: int, height: int, fov_deg: float) -> np.ndarray:
    f = 0.5 * width / np.tan(np.deg2rad(fov_deg) * 0.5)
    return np.array([[f, 0.0, width * 0.5], [0.0, f, height * 0.5], [0.0, 0.0, 1.0]])


# ---------------------------------------------------------------------------
# 点群のレンダリング (CPU)
# ---------------------------------------------------------------------------

def disc_offsets(radius_px: int) -> list[tuple[int, int]]:
    r = max(int(radius_px), 0)
    return [(dx, dy) for dy in range(-r, r + 1) for dx in range(-r, r + 1)
            if dx * dx + dy * dy <= r * r]


def render_points(points, colors, c2w, K, width, height, point_size, bg):
    """z-sort して遠い順に描く painter's algorithm。後の書き込みが手前になる。"""
    w2c = np.linalg.inv(c2w)
    cam = points @ w2c[:3, :3].T + w2c[:3, 3]

    z = cam[:, 2]
    in_front = z > 1e-6
    if not np.any(in_front):
        return np.full((height, width, 3), bg, dtype=np.uint8)
    cam, z, col = cam[in_front], z[in_front], colors[in_front]

    uv = (cam @ K.T)[:, :2] / z[:, None]
    u = np.round(uv[:, 0]).astype(np.int64)
    v = np.round(uv[:, 1]).astype(np.int64)

    order = np.argsort(-z)  # 遠い順
    u, v, col = u[order], v[order], col[order]
    rgb8 = (np.clip(col, 0.0, 1.0) * 255.0).astype(np.uint8)

    img = np.full((height, width, 3), bg, dtype=np.uint8)
    for dx, dy in disc_offsets(point_size):
        uu, vv = u + dx, v + dy
        ok = (uu >= 0) & (uu < width) & (vv >= 0) & (vv < height)
        img[vv[ok], uu[ok]] = rgb8[ok]
    return img


# ---------------------------------------------------------------------------
# 3DGS のレンダリング (GPU)
# ---------------------------------------------------------------------------

def load_splats(vertex):
    import torch

    def col(name):
        return np.asarray(vertex[name], dtype=np.float32)

    means = np.stack([col("x"), col("y"), col("z")], axis=1)
    scales = np.exp(np.stack([col(f"scale_{i}") for i in range(3)], axis=1))
    quats = np.stack([col(f"rot_{i}") for i in range(4)], axis=1)
    quats /= np.linalg.norm(quats, axis=1, keepdims=True) + 1e-12
    opacities = 1.0 / (1.0 + np.exp(-col("opacity")))
    # DC 項だけで色を作る。プレビュー用途では view-dependent 成分は不要。
    dc = np.stack([col(f"f_dc_{i}") for i in range(3)], axis=1)
    rgb = np.clip(0.5 + SH_C0 * dc, 0.0, 1.0)

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    t = lambda a: torch.from_numpy(np.ascontiguousarray(a)).float().to(dev)
    return t(means), t(quats), t(scales), t(opacities), t(rgb), dev


def render_splat_frame(splats, c2w, K, width, height, bg):
    import torch
    from gsplat.rendering import rasterization

    means, quats, scales, opacities, rgb, dev = splats
    viewmat = torch.from_numpy(np.linalg.inv(c2w)).float().to(dev)[None]
    Ks = torch.from_numpy(K).float().to(dev)[None]

    with torch.no_grad():
        colors, alphas, _ = rasterization(
            means=means, quats=quats, scales=scales, opacities=opacities,
            colors=rgb, viewmats=viewmat, Ks=Ks,
            width=width, height=height, sh_degree=None,
        )
    # backgrounds= 引数はgsplatのversionでshape要求が変わるため使わない。
    # 返ってきたalphaで自前に合成する方がversion差に強い。
    rendered = colors[0].clamp(0.0, 1.0)
    alpha = alphas[0].clamp(0.0, 1.0)
    frame = rendered * alpha + (bg / 255.0) * (1.0 - alpha)
    return (frame.cpu().numpy() * 255.0).astype(np.uint8)


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_ply", type=Path)
    ap.add_argument("--out-dir", type=Path, required=True, help="PNG と MP4 の出力先")
    ap.add_argument("--name", default="turntable", help="出力ファイル名の prefix")
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--fov", type=float, default=50.0)
    ap.add_argument("--elevation", type=float, default=20.0, help="仰角 (度)")
    ap.add_argument("--distance-scale", type=float, default=1.2)
    ap.add_argument("--up", choices=sorted(UP_VECTORS), default="-y",
                    help="world 上方向。既定は OpenCV 系の -y")
    ap.add_argument("--point-size", type=int, default=1, help="点群経路での点の半径 (px)")
    ap.add_argument("--max-points", type=int, default=2_000_000,
                    help="点群経路の点数上限。超えたらランダムに間引く")
    ap.add_argument("--bg", type=int, default=255, help="背景のグレー値 0-255")
    ap.add_argument("--thumbs", type=int, default=3, help="静止画として書き出す枚数")
    ap.add_argument("--force-mode", choices=["auto", "splat", "points"], default="auto")
    args = ap.parse_args()

    if not args.input_ply.is_file():
        print(f"ERROR: input not found: {args.input_ply}", file=sys.stderr)
        return 1

    vertex, names = load_ply(args.input_ply)
    mode = args.force_mode if args.force_mode != "auto" else ("splat" if is_splat(names) else "points")
    n = len(vertex.data)
    print(f"[render-ply-preview] {args.input_ply} : {n} 要素 / mode={mode}")

    points = xyz_of(vertex)
    center, radius = scene_frame(points)
    K = intrinsics(args.width, args.height, args.fov)
    c2ws = orbit_c2ws(center, radius, args.up, args.frames, args.fov,
                      args.elevation, args.distance_scale)

    if mode == "splat":
        splats = load_splats(vertex)
        if splats[-1] == "cpu":
            print("[render-ply-preview] WARNING: CUDA が見えていません。"
                  "container 内 (scripts/enter_agent_container.sh) で実行してください。",
                  file=sys.stderr)
        frames = [render_splat_frame(splats, c2w, K, args.width, args.height, args.bg)
                  for c2w in c2ws]
    else:
        colors = rgb_of(vertex, names, n)
        if n > args.max_points:
            # 数百万点をそのまま投影すると遅いだけで見た目は変わらない。
            idx = np.random.default_rng(0).choice(n, args.max_points, replace=False)
            points, colors = points[idx], colors[idx]
            print(f"[render-ply-preview] {n} -> {args.max_points} 点に間引き")
        frames = [render_points(points, colors, c2w, K, args.width, args.height,
                                args.point_size, args.bg)
                  for c2w in c2ws]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    video_path = args.out_dir / f"{args.name}.mp4"
    write_video_mp4(video_path, frames, args.fps)
    print(f"[render-ply-preview] 動画: {video_path} ({len(frames)} frames @ {args.fps}fps)")

    import imageio.v2 as imageio
    for i in range(min(args.thumbs, len(frames))):
        f = i * len(frames) // max(args.thumbs, 1)
        thumb = args.out_dir / f"{args.name}_{i:03d}.png"
        imageio.imwrite(thumb, frames[f])
        print(f"[render-ply-preview] 静止画: {thumb}")

    # 真っ黒 / 真っ白のまま気付かず貼るのを防ぐ。
    spread = float(np.std(np.stack(frames[: min(5, len(frames))])))
    if spread < 1.0:
        print("[render-ply-preview] WARNING: フレームがほぼ単色です。"
              "--up / --elevation / --distance-scale を見直してください。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
