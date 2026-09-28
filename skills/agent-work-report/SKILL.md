---
name: agent-work-report
description: Produce a reproducible engineering work report after implementation, debugging, benchmarking, or validation. Use when summarizing completed agent work so another engineer can reproduce the change, distinguish executed from unexecuted checks, and understand evidence, risks, and remaining work.
---

# Agent work report

## Required sections

Write a compact report containing:

1. **Summary**: what changed and why.
2. **Changed surface**: important files/modules and externally visible behavior.
3. **Validation**: exact commands that were actually executed and their relevant results.
4. **Evidence**: tests, logs, measurements, screenshots, generated artifacts, or before/after comparisons that support the conclusion.
5. **Not run / remaining**: checks not executed, why, and the risk they leave.

## Reproducibility

Do not rewrite an intended command as if it was executed. Preserve relevant flags, working directory, environment/profile, input identifiers, and hardware when they materially affect the result.

For performance results, record at least the input, hardware, software/config profile, warm/cold condition, number of repetitions, and the statistic reported. Avoid mixing setup time with steady-state runtime unless the product metric intentionally includes both.

For visual/quality results, identify the exact input and output artifact and explain what criterion was inspected rather than saying only that it "looks good".
