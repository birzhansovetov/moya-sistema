# Learning Library Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supply checked, versioned lesson help and an actionable coverage report for Java, Go, English and Java backend.

**Architecture:** Keep authored content in project files. A separate help catalog maps course/version/lesson/question to hint, next step and full explanation; old course versions and saved attempts remain untouched. Coverage tooling reports missing help and unreachable entries before the AI interface is enabled.

**Tech Stack:** Python 3.14, FastAPI content loaders, JSON, pytest, existing CI coverage command.

**Spec:** `docs/superpowers/specs/2026-10-14-local-ai-learning-library-depth-design.md`

## Global Constraints

- Budget $0; do not add external AI or content services.
- Never rewrite saved attempts or existing v1/v2/v3 course files to change their meaning.
- Every new fragment is platform-authored or has documented reuse rights, source, reviewer and recheck date.
- Hints are staged: hint, next step, full explanation; the first stage must not contain the accepted quiz answer.
- Sport and nutrition remain later, separately enabled batches with strict safety metadata.

## Review Focus

- Missing lesson or question: return an explicit unavailable result, never another lesson's hint (Task 2).
- Historical course version: retrieve its matching help, not the latest version (Task 2).
- Hidden accepted answer in hint: content gate rejects it even with case or Unicode variation (Task 2).
- Revoked or expired content: no new help is offered; existing study history still loads (Task 2).
- Catalog extension without help: CI reports the new gap instead of silently counting the route complete (Task 1).

---

## File map

- `backend/app/content/study-help-v1.json`: immutable authored help fragments for selected lessons; each entry has `course_id`, `course_version`, `lesson_id`, `question_index`, `hint`, `next_step`, `explanation`, `review` and a stable ID `course_id:course_version:lesson_id:question_index`.
- `backend/app/study_help.py`: lookup and structural safety gate; `HelpFragment` is the shared contract for the AI plan.
- `backend/app/coverage.py`: existing synthetic coverage plus study-help coverage report.
- `backend/app/content/coverage_baseline.json`: reviewed expected report, updated only after inspecting changes.
- `backend/tests/test_study_help.py`, `backend/tests/test_coverage.py`: help and coverage regression tests.

### Task 1: Report concrete library gaps

**Files:** Modify `backend/app/coverage.py`; Test `backend/tests/test_coverage.py`; update `backend/app/content/coverage_baseline.json` after review.

**Interfaces:** Produces `study_help_coverage() -> dict` with per-course/version lesson count, questions with help, missing question keys, and unreachable help keys. Task 2 consumes its key format `course_id:version:lesson_id:question_index`.

- [ ] **Step 1: Write failing tests** for all four latest courses and a synthetic missing question; assert a missing key appears and an unused key is reported.
- [ ] **Step 2: Run** `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_coverage.py -q`; expect the new test to fail.
- [ ] **Step 3: Implement** `study_help_coverage() -> dict`; scan latest and historical course manifests without reading accounts; add the result to the existing coverage report.
- [ ] **Step 4: Run** the test and `PYTHONPATH=. .venv/bin/python -m app.coverage`; inspect the diff, then intentionally update the baseline using `--update` and verify `--check` passes.
- [ ] **Step 5: Commit only these files** with `feat: report study help coverage` if repository permissions allow; otherwise record the uncommitted state.

### Task 2: Add checked help fragments for first chapters

**Files:** Create `backend/app/content/study-help-v1.json`, `backend/app/study_help.py`, `backend/tests/test_study_help.py`; reuse the existing inline `reviewed_variant` checks in `backend/app/content_review.py` and its revocation lookup.

**Interfaces:** Produce `get_help_fragment(course_id: str, version: str, lesson_id: str, question_index: int, *, today: date) -> HelpFragment | None`, where `HelpFragment` contains `hint`, `next_step`, `explanation`, `lesson_id`, `version`, and `question_index`. The AI plan imports this function; a `None` result means no help may be generated.

- [ ] **Step 1: Write failing tests** for `java-01`, `go-01`, `en-a2-01`, `backend-01` at their current latest versions; assert the three distinct stages and correct version/question, including a historical-version lookup.
- [ ] **Step 2: Add failing tests** for absent, expired and revoked entries; assert the hint stage does not contain a normalized accepted answer, and a malformed entry fails catalog validation.
- [ ] **Step 3: Run** `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_study_help.py -q`; expect failures.
- [ ] **Step 4: Author** the first-chapter fragments in the new JSON with rights/review metadata. Implement `get_help_fragment` and validation using existing `app.content_review` rules; do not copy the full solution into `hint`.
- [ ] **Step 5: Run** `PYTHONPATH=. .venv/bin/pytest tests/test_study_help.py tests/test_study.py -q`, then `PYTHONPATH=. .venv/bin/python -m app.coverage --check`; inspect any baseline update before accepting it.
- [ ] **Step 6: Commit only this task's files** with `feat: add reviewed study help fragments` if repository permissions allow.

### Task 3: Extend the library by measured gaps

**Files:** Modify `backend/app/content/study-help-v1.json`; create a new versioned course extension file only if Task 1 finds an actual missing lesson; modify `backend/app/study.py` only to register that new version; Test `backend/tests/test_study_help.py`, `backend/tests/test_study_content.py`.

**Interfaces:** Preserve Task 2's lookup signature. New course versions must be registered in `LATEST_VERSIONS` and must not mutate earlier snapshots.

- [ ] **Step 1: Record** the exact missing question keys and first-chapter gaps from Task 1 in `docs/verification/2026-10-14-learning-help-coverage.md`; choose only gaps with an authored exercise and review metadata.
- [ ] **Step 2: Write failing content tests** for each selected gap: complete three-stage help, valid source/review fields, no accepted answer in hint, and no change in existing course fingerprints.
- [ ] **Step 3: Run** the targeted tests and confirm red.
- [ ] **Step 4: Author** the selected fragments; if a lesson itself is missing, add it in a new immutable version and update the version registry and links to that version.
- [ ] **Step 5: Run** content tests, full `backend/tests/test_study.py`, and `PYTHONPATH=. .venv/bin/python -m app.coverage --check`; update the baseline only after examining the added and unreachable keys.
- [ ] **Step 6: Commit this task's reviewed content** if repository permissions allow.

## Completion gate

Run `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_study_help.py tests/test_coverage.py tests/test_study.py -q` and `PYTHONPATH=. .venv/bin/python -m app.coverage --check`. The report must name any remaining uncovered routes; do not describe four full courses as covered after filling only their first chapters.
