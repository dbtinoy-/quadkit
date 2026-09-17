# Adoption metrics

What the project measures to know whether adoption is working, where each
number comes from, and the one hard rule.

## The hard rule

**The public framework contains no telemetry.** No install hooks, no
runtime reporting, no opt-out flags — there is nothing to opt out of.
Usage of Quadkit on your machines is not observable by the project, and
that will not change by default; any future opt-in diagnostics would go
through the [RFC process](rfc-process.md) first.

## What is measured instead

All metrics come from the project's own CI fixtures and from public
package indexes — sources that observe the project, not the user:

| Metric | Source | Cadence |
| --- | --- | --- |
| Installation success rate | The wheel-only verification environment installs all five distributions on every PR (and on 3.11/3.12/3.13 in the preview matrix) | Every PR |
| Time to first successful route | `app_boot_ms` + `first_request_ms` in [performance budgets](../reference/performance-budgets.md) | Every PR |
| Time to first passing test | Starter-template suites run from the exported tree; wall-clock visible in job logs | Every PR |
| Documentation accuracy | `check_public_docs.py` gates link validity, distribution claims, and snippet sync across all pages | Every PR |
| CLI command completion | `cli_version_ms` / `cli_project_generation_ms` budgets exercise the real console script | Every PR |
| Example suites passing | All seven starter templates + getting-started examples, executed wheel-only | Every PR |
| Package download trends | Public index statistics (published distributions only) | Reviewed monthly by maintainers |

## How the numbers are used

A regression in any fixture metric is treated like a regression in
adoption itself — investigated in the same release window. Download
trends inform roadmap ordering (see [roadmap](roadmap.md)) and never gate
individual changes. Nothing on this page is collected from end users or
their deployments.
