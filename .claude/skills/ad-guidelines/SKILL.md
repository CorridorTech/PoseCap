---
name: ad-guidelines
description: Draft or update `GUIDELINES.md` at the repo root — the project's full engineering reference. Layer 1 Constitution trinity member (alongside `WORKFLOW.md` universal philosophy and `AGENTS.md` distilled rules). Covers Clean Architecture binding, SOLID application, Object Calisthenics tier (loose / moderate / strict per Bay 2008), naming conventions, error handling, complexity discipline, API rules, performance standards, build system, static analysis, quality gates, testing strategy, git workflow, documentation, and security. Scan-first — reads language toolchain, existing test/lint/format config, and existing AGENTS.md sections, pre-fills every placeholder it can verify, then asks only the genuine gaps and preference questions. Use when the user wants to draft, scaffold, audit, or update engineering guidelines / code standards / coding conventions / SOLID adoption / Object Calisthenics / testing strategy / security policy / build conventions for the project. Skill is lazy — file only exists when the project needs engineering standards.
summary: Lazy lifecycle owner of `GUIDELINES.md` (Layer 1 Constitution, full engineering reference). Twelve sections — design principles, code standards, complexity, API, performance, build, static analysis, quality gates, testing, git, documentation, security. Pre-suggested defaults from canon + scan-first detection.
allowed-tools: Read, Write, Glob, Grep, Bash
---

# /ad-guidelines

Layer 1 Constitution trinity member. Lazy lifecycle owner of `GUIDELINES.md` at the repo root. Companion to `WORKFLOW.md` (universal engineering philosophy, kit-shipped) and `AGENTS.md` (distilled non-negotiable rules read every session).

`GUIDELINES.md` is the **full reference**; `AGENTS.md` is the **distilled summary**. Each AGENTS.md section that has detail points to the corresponding GUIDELINES.md section. The two never duplicate — `ad-drift` flags duplication as drift.

## Step 0 — Confirm regime

Run when the user wants to scope or update project-level engineering standards. Triggers:

- New project past `poc` profile that needs explicit standards.
- Existing project with engineering rules buried in `AGENTS.md` — extract and scale.
- Stack change (new language, new architecture) that needs a guidelines update.
- Object Calisthenics tier review.

Route elsewhere when:

- Scope is system structure (modules, dependencies, deployment) → `/ad-architecture`.
- Scope is product (target user, success metrics) → `/ad-prd`.
- Scope is a vocabulary question → `/ad-domain`.
- Scope is one binding decision (e.g., "pick error-handling library X") → `/ad-adr`.
- Scope is wiring the gates this file describes → `/ad-hooks`.

Skill excluded from `poc` profile — a spike does not need full engineering guidelines.

## Step 1 — Codebase-first scan

Before asking any preference question, look. The repo answers most fields.

### Language and toolchain

- `package.json` → JavaScript / TypeScript; read `engines`, `scripts`, `dependencies`, `devDependencies`.
- `Cargo.toml` → Rust; read `edition`, `dependencies`, `dev-dependencies`.
- `pyproject.toml` / `setup.cfg` / `requirements.txt` → Python; read version constraint, dependencies.
- `CMakeLists.txt` / `CMakePresets.json` / `vcpkg.json` → C / C++; read minimum version, presets.
- `go.mod` → Go; read `go` directive, dependencies.
- `Gemfile` → Ruby.
- `pom.xml` / `build.gradle` → Java / Kotlin.
- `composer.json` → PHP.

### Test framework

- JS/TS: `jest.config.*`, `vitest.config.*`, `playwright.config.*`, `mocharc*`, presence of `test/`, `tests/`, `*.test.*`, `*.spec.*`.
- Rust: `[dev-dependencies]` in `Cargo.toml` (`proptest`, `criterion`).
- Python: `pytest.ini`, `pyproject.toml` `[tool.pytest]`, `tox.ini`.
- C++: `catch2`, `gtest` references in `CMakeLists.txt` or `vcpkg.json`.
- Go: `_test.go` files, `testing` package usage.

### Lint and format

- JS/TS: `.eslintrc.*`, `.prettierrc.*`, `biome.json`.
- Rust: `.rustfmt.toml`, `clippy.toml`.
- Python: `.ruff.toml`, `pyproject.toml` `[tool.ruff]`, `.flake8`, `mypy.ini`, `pyrightconfig.json`.
- C++: `.clang-format`, `.clang-tidy`.
- Go: `gofmt` is implicit; `.golangci.yml` for linting.

### Hooks and CI

- `.husky/`, `lefthook.yml`, `.pre-commit-config.yaml`, `.githooks/` — pre-commit / pre-push toolchain.
- `.github/workflows/`, `.gitlab-ci.yml`, `.circleci/` — CI configuration.

### Existing standards

- Read `AGENTS.md` `## Code Style` and `## Architectural Principles` sections — these get extracted into GUIDELINES.md and replaced with pointers in AGENTS.md.
- Read `ARCHITECTURE.md` `## Source Tree` and `## Dependency Rules` — informs Clean Architecture §1.1.
- Read `doc/adr/` for binding decisions about error handling, naming, dependency injection — those are pre-existing decisions; carry them forward.
- Read `CONTEXT.md` if it exists — domain vocabulary the guidelines must respect.

### Canonical examples

For brownfield projects, identify candidate source files that future agents should imitate. Prefer one boundary example, one core/domain function, and one test. Record paths only, never pasted snippets. If no representative code exists, omit the section until the project has examples worth copying.

### Profile and project posture

Read `.claude/agentic-state.json` / `.agents/agentic-state.json` for the active profile. Profile affects strictness defaults (mature → strict Object Calisthenics by default; solo → loose by default).

Only after the scan produces no answer does the skill ask. Asking about something the repo already states wastes the user's attention.

## Step 2 — Pre-fill the template

Open `templates/guidelines.md`. Fill detected fields before any interview:

- **§2.1 Naming conventions** — fill the per-language convention table from the canonical conventions of the detected language (snake_case / PascalCase / camelCase / UPPER_SNAKE / kebab-case / file extensions).
- **§2.2 Error handling** — fill the idiom of the detected language (`std::expected` for C++, `Result<T, E>` for Rust, discriminated unions for TS, typed exceptions for Python, error returns for Go).
- **§2.5 Canonical examples** — when representative code exists, fill a small table of source-file paths for boundary code, core/domain logic, and tests. Confirm the picks with the user before writing; do not declare weak code canonical.
- **§6.1 Toolchain** — fill language + version, build system + version, source-of-truth config file.
- **§6.2 Dependency manager** — fill from detected manifest.
- **§7 Static analysis** — fill the linter, formatter, and naming-enforcement tools detected in the repo.
- **§8 Quality gates** — fill from `.husky/` / `lefthook.yml` / `.pre-commit-config.yaml` if present; otherwise mark as `<not yet wired — invoke /ad-hooks>`.
- **§9.2 Unit-test framework** — fill from detected framework.
- **§9.6 Tag taxonomy** — fill kit defaults; project can extend.
- **§10 Git workflow** — fill from kit pattern (`/ad-commit`, `/ad-pr`, `/ad-merge`), DCO sign-off.
- **§11.1 Document scope** — fill kit-standard table.
- **§12 Security** — fill from detected secret-scan presence; ask about boundaries.

Sections requiring user preference get asked. Sections that do not apply to the project (e.g., `§5 Performance Standards` for a CRUD app) get skipped — the skill omits them from the file, not left as `<TODO>`.

## Step 3 — Interview to fill preference questions

Ask **one question at a time**, in this order. Skip questions whose answers are obvious from the scan or earlier answers.

### 3.1 Project tradeoff statement

One sentence. The single explicit tradeoff that engineering decisions should reflect.

Suggest from project signals (e.g., a CLI tool → "portability over speed"; a runtime library → "reliability over throughput"; a web app → "time-to-interactive over server cost"). User confirms or supplies their own.

### 3.2 Object Calisthenics tier

Three-choice question. Default depends on profile (poc — N/A; solo — loose; team — moderate; mature — strict).

- **Loose** — Rule 6 (no abbreviations), Rule 7 (small entities, relaxed targets), Rule 1 (one level of indentation as guideline).
- **Moderate** — Loose + Rule 2 (no `else`), Rule 3 (wrap primitives), Rule 4 (first-class collections).
- **Strict** — All nine rules including Rule 5 (one dot per line / Law of Demeter), Rule 8 (≤2 instance vars), Rule 9 (no getters/setters).

When the host exposes `AskUserQuestion`, render as a multi-choice card with the three tiers and a one-line description each.

### 3.3 Complexity caps

Confirm or override defaults:

- Cognitive complexity per function: default 15.
- Function size: default ~50 lines target / 100 hard.
- File size: default ~200 lines target.
- Max indentation depth: default 3.

If the detected language has a community-standard tool that enforces a different cap (e.g., `clippy::cognitive_complexity` default 25), surface the conflict and let the user choose.

### 3.4 Performance standards (skip if N/A)

Ask: does this project have a perf budget?

- If no → skip §5 entirely.
- If yes → ask for the hot-path rules (allocation policy, math constraint, memory locality, alignment), profiling baseline location, regression threshold.

### 3.5 Security posture

Ask the boundary questions:

- Untrusted input sources (file formats, network, user data)?
- Secret-handling pattern (env vars, vault, secret manager)?
- Dependency-audit tool (already detected from CI/hooks scan, confirm).

### 3.6 Documentation extensions

Default: reference `WORKFLOW.md §2` + `ad-philosophy`. Ask only if the project needs project-specific extensions (e.g., Doxygen-style public-API docs, OpenAPI spec, ADR cadence rule).

### 3.7 Canonical examples confirmation

If Step 1 found candidate examples, present the paths and ask whether each should be treated as canonical. Keep at most one row per pattern unless two variants are genuinely necessary. If the user cannot endorse an example, omit the section; bad exemplars are worse than no exemplars.

## Step 4 — AGENTS.md reciprocity

After writing `GUIDELINES.md`, the kit's `ad-bootstrap` skill writes AGENTS.md sections that point to GUIDELINES.md sections instead of duplicating content. Example:

```markdown
## Code Standards

See [`GUIDELINES.md`](GUIDELINES.md) §2 for the full reference. Non-negotiable subset:

- `<language-specific naming line>`
- `<error-handling pattern line>`
- `<no commented-out code, no orphan TODO line>`
```

If the user is invoking `/ad-guidelines` on a project that already has detailed `AGENTS.md` engineering sections, the skill offers to:

1. Extract those sections into `GUIDELINES.md`.
2. Replace them with pointer-style stubs in `AGENTS.md`.

The user confirms before the AGENTS.md rewrite. The skill never modifies AGENTS.md silently.

## Step 5 — Write the file

Path: `GUIDELINES.md` at repo root. Use the template at `templates/guidelines.md`.

Sections the user skipped do not land in the file. Sections that were fully pre-filled land verbatim. Sections requiring user preference land with the user's answer.

Stop after writing. Print a one-line summary: "Wrote GUIDELINES.md with N sections. AGENTS.md update? (y/n)".

## Step 6 — Editing guidance for later turns

- Object Calisthenics tier change → update §3.1 checked rules; never delete the rule list (audit trail).
- Adding a new language to the project → expand §2.1 naming table with a per-language row; do not rewrite existing rows.
- New static-analysis tool → add a row to §7; reference the config file path.
- Canonical example change → update §2.5 to point at the new source file; do not paste code into GUIDELINES.md.
- Perf budget change → update §5; never delete the previous budget without recording the rationale.
- Documentation extensions → append to §11.1 table.

Never rewrite existing prose — append rationale paragraphs where decisions evolve.

## Output contract

- Primary output: `GUIDELINES.md` at the repo root.
- Side-effect (optional, user-confirmed): `AGENTS.md` engineering sections rewritten as pointer stubs to `GUIDELINES.md`.
- No dates inside narrative prose; the file is project-state, not a decision-record artifact (per WORKFLOW §2 rule #2).

## Next

- After writing `GUIDELINES.md`: invoke `/ad-hooks` to wire the quality gates this file describes (`team` and `mature` profiles).
- After writing `GUIDELINES.md`: invoke `/ad-bootstrap` to refresh `AGENTS.md` with pointer-style sections.
- When a binding decision arises that the guidelines do not yet cover (e.g., picking a specific error-handling library, naming an exception hierarchy): `/ad-adr`.
- Periodic drift check: `/ad-drift` flags AGENTS sections that duplicate GUIDELINES sections, and GUIDELINES sections whose claims do not match the code (e.g., naming convention says snake_case but half the codebase is camelCase).
