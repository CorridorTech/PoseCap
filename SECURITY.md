# Security Policy

Security reports need a private path so users can disclose vulnerabilities without
publishing an exploit, credential, or affected user's data before a fix exists.

## Supported code

Security fixes target `main` and the latest published PoseCap release. Reporters may
be asked to confirm a finding against the latest build when the affected code has
already changed.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/CorridorTech/PoseCap/security/advisories/new).
Do not open a public issue for a suspected vulnerability.

Include the affected build, impact, prerequisites, and the smallest safe reproduction.
Do not include passwords, session cookies, API tokens, licensed body-model assets, or
personal footage. If evidence contains sensitive material, describe it first and wait
for a maintainer to coordinate a safe transfer.

The maintainers will triage the report privately, establish affected versions and a
remediation, and coordinate disclosure with the reporter. Public disclosure waits
until users have a practical mitigation or fixed release.

## Security boundaries

Security-sensitive areas include credential handling for official model downloads,
archive extraction, installer/update integrity, subprocess execution, local TCP input,
support-bundle redaction, dependency provenance, and deserialization. Pose quality or
model accuracy without a security impact belongs in the bug-report form instead.
