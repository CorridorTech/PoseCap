# ADR-0015: Retire the destructive conversion after one field-proving release

**Status:** proposed
**Date:** 2026-07-17
**Deciders:** alexandremendoncaalvaro (maintainer)

## Context

[ADR-0014](0014-bind-via-compensated-pose-writes.md) selects non-destructive
binding as the character-setup architecture and deliberately leaves one
question open: what happens to the existing destructive conversion path
(rename, T-pose re-rest, reorient), which
[spec 0005](../specs/0005-non-destructive-character-binding.md) records as a
deferred maintainer decision. The destructive path is field-viable today —
the task 0033 fix hardened it with a geometric T-pose gate — and it is the
only setup flow shipped users have. The binding, once implemented, makes the
destructive path redundant for capture; keeping two parallel setup flows
indefinitely doubles the validation matrix (every skeleton family times two
paths) and keeps asset-mutation risk alive for anyone who picks the old
button.

## Decision

We will keep the destructive conversion shipped and unchanged as the
explicit fallback in the first tagged release that ships the
non-destructive binding, then retire it in the next tagged release.

Concretely: the destructive conversion remains available alongside the
binding in the binding's first tagged release (how the two surface in the
panel is the UX question spec 0005 keeps open). If no field report
requires the fallback while that release is the latest, the destructive
path is removed in the next tagged release — panel surface, converter
machinery, and its share of the validation matrix. A field report that
does require it re-opens this decision with the evidence attached.

## Consequences

* Shipped users lose nothing during the transition: the flow they know
  stays until the binding has real field evidence behind it.
* The validation matrix doubles for exactly one tagged release, then
  shrinks below today's size (one path, no mutation cases).
* Asset-mutation risk has a recorded end date instead of living
  indefinitely behind a second button.
* The removal release must migrate nothing: characters converted by the
  destructive path bind as SMPL-X-named armatures (spec 0005 edge case),
  and damaged assets follow the recorded re-import recovery story.
* Negative: users who prefer the old flow get one release of notice; the
  release notes for the binding release must state the retirement plan.

## Alternatives Considered

* Keep both paths indefinitely — rejected: permanent double validation
  matrix and permanent asset-mutation risk for no capability the binding
  does not provide.
* Remove the destructive path in the same release the binding ships —
  rejected: no field evidence yet that the binding covers every character
  the destructive path handles; a regression would leave users with no
  working setup flow.
* Hide the destructive path behind an advanced toggle immediately —
  rejected: hiding without evidence is the same bet as removal with an
  escape hatch nobody will find; the explicit fallback plus a recorded
  retirement date is honest about both the risk and the plan.
