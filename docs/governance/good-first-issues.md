# Good first issues

How to find (or, as a maintainer, create) contributions that are real,
small, and reviewable in one sitting.

## For contributors

Start with issues labelled **`good first issue`**. Every one of them has
three properties, enforced by the triager who applied the label:

1. **A bounded patch area** — usually one module plus its tests.
2. **A written acceptance check** — the test or command that proves the
   change works.
3. **A named reviewer** — the maintainer who will answer questions on the
   issue before you write code, not after.

Comment on the issue before starting (one line: "I'm on this"). Duplicate
work is the only failure mode worth avoiding. Setup is in
[development setup](../contributing/development.md); the public surfaces
you can touch are the five distributions under `core/` and `packages/`.

Other labels you'll meet:

| Label | Meaning |
| --- | --- |
| `good first issue` | The bounded, reviewed, newcomer-ready entry points above. |
| `help wanted` | Larger or more exploratory; design discussion expected first. |
| `docs` | Documentation-only; still executed/validated in CI like code. |
| `bug` / `regression` | A defect; `regression` means something that used to work broke. |
| `breaking` | Touches a stable contract; needs the [RFC process](rfc-process.md). |

## For maintainers

A `good first issue` is a promise. Before applying the label, write the
acceptance check into the issue body, name the patch area (paths), estimate
the diff honestly (if it's over ~150 lines, it's not first), and put your
own handle in the issue as the named reviewer. Remove the label from stale
entries quarterly — a graveyard of unworkable "easy" issues is worse than
none.
