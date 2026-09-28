---
name: python-cv-implementation
description: Implement or review Python computer-vision, 3D geometry, image-processing, NumPy, OpenCV, or PyTorch code where tensor/image shapes, coordinate systems, camera conventions, units, dtype, device, or numerical behavior are correctness-critical. Use for new CV/3D implementation, refactors, geometry conversions, camera math, image pipelines, and related tests.
---

# Python / CV / 3D implementation

## Workflow

1. Read the project instructions, nearby implementation, call sites, and tests before editing.
2. Write down the data contract for every changed boundary: shape, axis order, dtype, device, value range, coordinate frame, handedness, units, and batch semantics.
3. Preserve existing public APIs and conventions unless the task explicitly requires a change.
4. Implement the smallest coherent change.
5. Validate with synthetic cases first, then project data when available.

## Invariants to check

- Distinguish `HWC` / `CHW` / `NCHW` explicitly.
- Distinguish RGB / BGR and integer / normalized floating ranges.
- Keep NumPy and PyTorch conversions explicit about contiguous layout, dtype, and device.
- For cameras, identify whether transforms are world-to-camera or camera-to-world before composing or inverting them.
- State pixel-center convention, normalized-coordinate convention, and intrinsic scaling when resizing/cropping images.
- Keep metric and scale-ambiguous geometry separate; never silently mix units.
- For homogeneous coordinates, verify divide-by-depth behavior and invalid/behind-camera points.
- Check NaN/Inf and degenerate geometry at normalization, inversion, triangulation, projection, and SVD/eigendecomposition boundaries.

## Testing

Prefer tiny deterministic tests that isolate geometry before expensive end-to-end runs. Useful cases include identity camera, pure translation, known rotation, planar points, points on optical axis, resize/crop intrinsic updates, empty input, single-element input, and CPU/GPU parity where relevant.

Report any convention that remains inferred rather than confirmed from the repository.
