---
name: pytorch-debugging
description: Diagnose PyTorch or ML pipeline failures including shape/device/dtype errors, NaN/Inf, CUDA OOM, silent numerical corruption, DataLoader problems, unexpected memory use, and performance regressions. Use when reproducing and narrowing a training, inference, or tensor-processing bug before applying a fix.
---

# PyTorch debugging

## Workflow

1. Reproduce the failure before editing code. Record the smallest command/input that reproduces it.
2. Separate observations from hypotheses.
3. Instrument the earliest suspicious boundary and inspect shape, dtype, device, min/max, finite ratio, and key semantic dimensions.
4. Test the cheapest discriminating hypothesis first.
5. Apply the smallest fix that explains the observation.
6. Re-run the original reproducer and the nearest relevant regression tests.

## Failure classes

For device or dtype mismatch, inspect tensor creation sites, implicit CPU constants, autocast boundaries, indexing tensors, and module/device movement.

For NaN/Inf, find the first non-finite tensor rather than only the final loss. Check normalization denominators, logarithms, divisions, exponentials, invalid masks, empty reductions, and mixed-precision overflow.

For CUDA OOM, distinguish allocated from reserved memory and expected model/input footprint from leaks. Check retained graphs, lists of tensors, accidental gradient tracking, duplicated model copies, large temporary tensors, attention/quadratic operations, and allocator fragmentation.

For performance regressions, separate warm-up from steady state and inspect synchronization, host-device transfers, Python loops, data loading, recompilation, cache misses, and I/O. Do not compare timings with different inputs or warm/cold conditions.

For DataLoader issues, test `num_workers=0` first, then worker initialization, picklability, shared memory, persistent workers, transforms, and deterministic seeding.

## Reporting

Include the reproducer, root cause, evidence that distinguished it from alternatives, the fix, and the exact post-fix validation. Mark expensive or unavailable checks as unrun.
