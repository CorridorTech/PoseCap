# PoseCap — Domain Glossary

_Lazy artifact — only contains terms that have been resolved through grilling, spec
drafting, or explicit capture. Empty entries are worse than no entry; speculation
belongs elsewhere._

_Maintained by `/ad-domain`._

## Language

### Pose Backend

**Definition:** An independently installable PoseCap runtime that observes the selected
camera or video source and emits live pose frames through the common PoseCap stream.

_Avoid_: “mode”, because every backend preserves the same capture workflow; “model”,
because a backend also owns runtime and compatibility requirements; “engine”, when
referring to a specific backend, because the engine process is the shared execution
boundary.

**Related code:** [`core/src/posecap_core/ports.py:8`](core/src/posecap_core/ports.py),
[`addon/posecap_addon/engine_process.py:53`](addon/posecap_addon/engine_process.py).

## Relationships

## Flagged ambiguities
