# RFC process

How substantial changes to Quadkit get proposed, discussed, decided, and
recorded. Deliberately lightweight: an RFC is a document plus a pull
request, nothing more.

## What needs an RFC

- New public API surfaces (distribution, top-level export, config section).
- Behavior changes that break any documented contract.
- Anything that changes what "supported" means
  ([support matrix](../reference/support-matrix.md)).

Bug fixes, docs corrections, internal refactors, and additive minor APIs go
straight to pull requests.

## Lifecycle

```text
draft (PR opened) → discussion → accepted | declined | deferred → implementation
```

1. **Draft** — copy the template below into
   `docs/governance/rfcs/NNNN-short-title.md` (next free number) and open a
   pull request containing only that file.
2. **Discussion** — happens on the PR. Stay technical; reference measured
   evidence over preference. The author keeps the document updated so it
   always reflects the current proposal.
3. **Decision** — a maintainer closes the loop by merging the PR
   (accepted), closing it (declined), or marking it deferred with a
   reopen condition. The merged document is the record — including the
   discarded alternatives.
4. **Implementation** — lands in follow-up PRs referencing the RFC number;
   the RFC itself is not edited afterwards except to mark it superseded.

## Review time and quorum

Small RFCs (one module, no compatibility risk): one maintainer approval,
open at least 3 days. Anything touching compatibility, packaging, or the
public repository boundary: two maintainer approvals, open at least 7 days.
Silence after the window means the author may ping for explicit review —
it does not mean acceptance.

## Template

```markdown
# RFC NNNN: <title>

- Status: draft
- Author: <you>
- Created: <YYYY-MM-DD>

## Summary

One paragraph: what changes for a user, in their terms.

## Motivation

The problem, with a concrete failure/awkwardness example that exists today.

## Proposal

The design, at the level of public API + behavior. Code sketches welcome.

## Alternatives considered

At least one, with the reason it loses.

## Compatibility

What existing users must do: nothing / rename / opt-in flag / migration.

## Unresolved questions

What you explicitly don't know yet.
```

Accepted RFCs moving from this page's template into
`docs/governance/rfcs/` happens when the first one is accepted — until
then, the template lives here.
