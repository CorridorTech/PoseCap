# ADR-0018: Select binding path by bind pose

**Status:** accepted
**Date:** 2026-08-22
**Deciders:** Alê (maintainer)

## Context

Non-destructive binding must drive a character correctly without changing its
armature data, mesh, weights, or names. ADR-0017 selected one temporary,
normalized armature with `Copy Transforms` constraints for every bound stream.

A local qualification using a real Mixamo Y Bot in T-pose falsified that
universal path. The normalized intermediary drove its untouched mesh into a
visibly broken pose. Direct `PoseBinding` compensation on the same untouched
rig matched the legacy converted result within `1e-5`. The task-0033
70-degree non-T fixture still requires the intermediary because connected-bone
translation cannot be preserved through independent target-local rotations.

## Decision

We will select the non-destructive live writer from the measured bind pose:
use direct `PoseBinding` compensation when both shoulders measure as a T-pose,
and use the temporary chain-aware intermediary only when the bind pose needs
T-pose re-resting.

## Consequences

* Standard T-pose Mixamo characters use the path that matches the legacy
  visual result while leaving the artist asset untouched.
* Non-T and connected chains retain Blender-native evaluation where direct
  local rotations are insufficient.
* Capture startup performs a read-only shoulder-direction check before it
  creates any temporary runtime object.
* The E2E suite must keep one real local T-pose qualification and the
  synthetic non-T regression fixture.
* ADR-0017's universal-intermediary wording is superseded.

## Alternatives Considered

* Use the intermediary for every bind pose — rejected because the real Y Bot
  qualification reproduced the broken visual result.
* Use direct compensation for every bind pose — rejected because task-0033
  proves it cannot preserve connected-bone translation in a non-T bind.
* Change only `Copy Transforms` spaces — rejected because all tested owner and
  target space combinations diverged from the legacy result on the Y Bot.
