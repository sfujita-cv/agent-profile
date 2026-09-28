---
name: code-review-etiquette
description: Produce focused, actionable code-review feedback for diffs, pull requests, or implementation changes. Use when reviewing code and deciding which findings are blocking, important, optional, or merely stylistic, with emphasis on evidence, impact, and minimal corrective action.
---

# Code review etiquette

## Review order

1. Correctness and regressions.
2. Data loss, security, concurrency, resource, and compatibility risks.
3. Missing validation or tests for changed behavior.
4. Maintainability issues that create concrete future failure modes.
5. Style only when it conflicts with repository conventions or obscures correctness.

## Finding format

For each material finding, include:

- severity or urgency;
- the concrete code path or condition that triggers it;
- why it matters to users, callers, data, performance, or operations;
- the smallest practical correction.

Prefer a question when repository intent is ambiguous instead of asserting a defect without evidence. Distinguish blocking findings from non-blocking suggestions. Do not flood the review with low-value nits that hide important issues.

Acknowledge sound design choices when they materially reduce risk, but keep the review centered on actionable information.

If no material issue is found, say so and state what was and was not validated.
