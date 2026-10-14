# Shared Content and Personal Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse one reviewed content library for multiple users while making survey recommendations selectable, safe, repeatable and explicit about unsupported answers.

**Architecture:** Keep authored content in existing versioned JSON files and personal progress in PostgreSQL. A deterministic matcher produces all compatible variants; an authenticated 30-minute preview stores answers and variant hashes server-side. An opaque ID connects that preview to a locked, idempotent, all-or-nothing start transaction.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, React, TypeScript, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-10-11-shared-content-personal-matching-design.md`

## Global Constraints

- Keep the existing six spheres, FastAPI/React architecture, file-based common catalog and owner-scoped personal tables.
- Never rewrite `study-v1` or previously saved workout and lesson snapshots.
- Never assign a sports program when health limitations are marked; missing allergen or exercise safety metadata excludes the material.
- A user can choose any compatible variant from the full preview snapshot; display the first three initially.
- Preview lifetime is 30 minutes, with 20 previews per account per hour and `429` plus `Retry-After` above the limit.
- Start archives and creates all requested plans in one transaction under the user row lock; skipped spheres keep their active plans.
- Existing publication remains deferred. Do not connect paid APIs or import proprietary material.
- Until the new client and metadata are verified, keep `SHARED_MATCHING_ENABLED` off and keep the current onboarding request/response contract working; enable the new contract only with the new client.

## Review Focus

- A user submits the same opaque ID simultaneously from two tabs: both calls report one committed result and only one new plan set. Task 6 tests this.
- A recipe has an explicit empty allergen list versus no allergen field: only the reviewed explicit-empty record may match. Task 1 tests this.
- An unselected recipe changes after preview: a selected sport program still starts. Task 5 tests this.
- A user skips one sphere while replacing another: the skipped sphere's plan and history remain untouched. Task 6 tests this.
- A preview expires after a successful server commit but before the response reaches the browser: the state endpoint shows the resulting plans without a second creation. Tasks 6 and 8 test this.

## File map

- `backend/app/content_review.py`: metadata, canonical variant bytes/hash, due-date and safety validation.
- `backend/app/matching.py`: pure compatible-candidate lists, stable ordering, preview projection.
- `backend/app/preview_store.py`: opaque IDs, preview/result persistence and cleanup.
- `backend/app/routes/onboarding.py`: HTTP boundary, auth/CSRF, state, preview, start and restore.
- `backend/app/models.py`, `backend/migrations/versions/c416_survey_version.py` through `c419_plan_restore.py`: survey version, revocation/audit, preview/result and restoration metadata in successive migrations.
- `backend/app/content/*.json`: reviewed metadata for existing items without changing their authored lessons or plan meaning.
- `backend/app/content_admin.py`: authenticated operator command for revocation and audit.
- `backend/app/coverage.py`, `backend/app/content/coverage_baseline.json`: synthetic pairwise and typical-profile report.
- `frontend/src/pages/Onboarding.tsx`, `frontend/src/pages/Onboarding.css`: complete choices, skip controls and preview recovery.
- Existing sport/nutrition pages and archive code: revoked-material warnings, survey-version backup support.

### Task 1: Reviewed metadata and fail-closed eligibility

**Files:** `backend/app/content_review.py`, relevant `backend/app/content/*.json`, `backend/app/nutrition.py`, `backend/app/sport.py`, `backend/tests/test_content_review.py`, `backend/tests/test_nutrition_content.py`, `backend/tests/test_sport_content.py`.

**Interfaces:** Produce `reviewed_variant(kind: str, item: dict, today: date) -> bool` and `variant_digest(kind: str, item: dict, dependencies: dict) -> str`; later matching consumes both. Preserve current published lesson IDs and exercise IDs.

- [ ] Write failing tests for missing versus explicit-empty allergen lists, missing training safety conditions, expired safety review and changed dependent exercise/lesson hash. Assert rejected items never enter matching.
- [ ] Run `cd backend && .venv/bin/python -m pytest tests/test_content_review.py tests/test_nutrition_content.py tests/test_sport_content.py -q`; confirm the new assertions fail first.
- [ ] Add source/license/reviewer/checked-at/recheck-by metadata to existing catalog items in batches across 6–12 months; only use facts established by the current source files. Add the validator and make the two loaders exclude invalid safety items rather than guessing values.
- [ ] Run the same focused suite; expect pass. Commit only Task 1 files with `feat: validate reviewed content for matching`.

### Task 2: Versioned survey and archive compatibility

**Files:** `backend/app/models.py`, `backend/migrations/versions/c416_survey_version.py`, `backend/app/routes/onboarding.py`, `backend/app/backup_archive.py`, `backend/tests/test_onboarding.py`, `backend/tests/test_backup_api.py`, `backend/tests/test_backup_archive.py`.

**Interfaces:** Produce `SURVEY_VERSION = 1`; persist `User.onboarding_version` with answers and return it from `GET /api/onboarding`. Legacy non-null answers without version map to 1, while a future unknown version requires reconfirmation, never reinterpretation.

- [ ] Write failing migration/API/archive tests for a legacy account, current-version export/restore, and unknown version warning.
- [ ] Run `cd backend && .venv/bin/python -m pytest tests/test_onboarding.py tests/test_backup_api.py tests/test_backup_archive.py -q`; confirm new tests fail.
- [ ] Add version column/migration and archive profile field; update API serialization and strict archive validation without changing existing answers. Set `down_revision = 'c415_onboarding'`.
- [ ] Run focused tests and an upgrade/downgrade migration test on an isolated disposable database; expect pass without modifying the user's working database. Commit only Task 2 files with `feat: version onboarding answers`.

### Task 3: Revocations, audit and active-plan warnings

**Files:** `backend/app/models.py`, `backend/migrations/versions/c417_content_revocations.py`, `backend/app/content_admin.py`, `backend/app/content_review.py`, `backend/app/routes/sport.py`, `backend/app/routes/nutrition.py`, `backend/tests/test_content_review.py`, `backend/tests/test_sport.py`, `backend/tests/test_nutrition.py`.

**Interfaces:** Produce `is_revoked(db: Session, kind: str, item_id: str, version: str) -> bool`. Operator command `python -m app.content_admin revoke|restore --kind ... --id ... --version ... --reason ... --actor ...` records both directions; blank reason fails. Active plan/menu responses gain an explicit warning flag and reason; history stays intact.

- [ ] Write failing tests for revoke, restore, audit actor/time/reason, missing reason, immediate exclusion from new matching and warnings on already issued items.
- [ ] Run focused tests; verify the new cases fail.
- [ ] Add revocation and append-only audit tables in `c417_content_revocations.py` with `down_revision = 'c416_survey_version'`, command, lookup and response flags. Do not delete or mutate completed records.
- [ ] Run focused tests and migration round trip; expect pass. Commit Task 3 files with `feat: revoke unsafe catalog items with audit`.

### Task 4: Deterministic full candidate sets

**Files:** `backend/app/matching.py`, `backend/app/routes/onboarding.py`, `backend/app/sport.py`, `backend/app/nutrition.py`, `backend/tests/test_matching.py`, `backend/tests/test_onboarding.py`.

**Interfaces:** Produce `match_survey(survey: Survey, timezone: str, db: Session) -> MatchResult` with `areas`, `candidates_by_sphere` and `candidate_digests`. Each candidate contains kind, ID, version, digest, title and plain-language reason. Sport uses strict existing compatibility; recipes remain recommendations, not created plans. Order by named domain keys, then ID; no weighted score.

- [ ] Write failing tests for supported and unsupported goals, two users with different answers, deterministic ties, all compatible IDs including item four, and no fabricated study/profession route.
- [ ] Run `cd backend && .venv/bin/python -m pytest tests/test_matching.py tests/test_onboarding.py -q`; observe new failures.
- [ ] Implement the pure matcher using Task 1 review and Task 3 revocation checks; preserve existing `matched`/`unavailable`/`skipped` meanings and guides as non-program alternatives.
- [ ] Run focused tests; expect pass. Commit Task 4 files with `feat: enumerate compatible content choices`.

### Task 5: Persist a 30-minute preview behind an opaque ID

**Files:** `backend/app/preview_store.py`, `backend/app/models.py`, `backend/migrations/versions/c418_matching_preview.py`, `backend/app/routes/onboarding.py`, `backend/tests/test_onboarding.py`, `backend/tests/test_preview_store.py`.

**Interfaces:** `create_preview(db, user, survey, match) -> (raw_id, preview)` uses `secrets.token_urlsafe(32)` and stores only SHA-256 of the raw ID; `load_preview(db, user_id, raw_id)` checks owner/expiry. `POST /api/onboarding/preview` returns the raw ID and first three visible candidates per sphere plus a paged/full-list read keyed by that ID. Rate limit 20/account/hour with `Retry-After`.

- [ ] Write failing tests for unauthenticated/CSRF access, 20-versus-21 requests, 30-minute expiry, foreign owner, 256-bit ID, full list access and no raw ID or health codes in logs.
- [ ] Run focused tests; confirm failure.
- [ ] Implement preview/result tables in `c418_matching_preview.py` with `down_revision = 'c417_content_revocations'`; add preview persistence and rate accounting using the existing `AuthRateEvent` pattern without committing halfway through another transaction. Store canonical survey and every compatible candidate/hash in the preview row. Keep the existing preview response when the new flag is off.
- [ ] Run focused tests; expect pass. Commit Task 5 files with `feat: store authenticated matching previews`.

### Task 6: Atomic and idempotent plan start

**Files:** `backend/app/preview_store.py`, `backend/app/models.py`, `backend/app/routes/onboarding.py`, `backend/tests/test_onboarding.py`, `backend/tests/test_preview_store.py`.

**Interfaces:** `POST /api/onboarding/start` accepts `{preview_id, selected: {sphere: candidate_id}, skipped: string[], confirm_replace: boolean}`. It reads the stored answers, validates chosen variant digest and current eligibility, compares expected active IDs, then locks user and commits one result row unique on `(user_id, nonce)` with every plan change. A same-payload replay returns stored result; a different replay is `409`.

- [ ] Write failing tests for chosen ID outside snapshot, fourth candidate accepted, unrelated catalog edit accepted, selected dependent-content edit rejected, revocation, skip preservation, stale active plan, mid-transaction error, two simultaneous submissions and identical replay.
- [ ] Run focused tests; confirm failures.
- [ ] Move current start logic behind the validated preview when the new flag is on. Keep the old request contract under the default-off flag until Task 8. Keep archival, new plans, answers and result in one transaction; make uniqueness plus user lock prevent double creation. No intermediate commit from rate tracking or helper functions.
- [ ] Run focused tests; expect pass. Commit Task 6 files with `feat: start selected plans atomically`.

### Task 7: Seven-day restore and retention

**Files:** `backend/app/preview_store.py`, `backend/app/routes/onboarding.py`, `backend/app/models.py`, `backend/migrations/versions/c419_plan_restore.py`, `backend/app/cleanup.py`, `backend/tests/test_onboarding.py`, `backend/tests/test_cleanup.py`, `README.md`.

**Interfaces:** `POST /api/onboarding/restore` accepts the archived plan ID and explicit progress confirmation; only its owner, within seven days, and only if current review/revocation rules permit it. `python -m app.cleanup onboarding` deletes preview rows 24 hours after expiry and result rows after seven days, logs failure, and leaves plans/history untouched.

- [ ] Write failing tests for restore eligibility, new-progress confirmation, revoked old plan, transaction rollback, retention boundaries and cleanup failure log.
- [ ] Run focused tests; confirm failures.
- [ ] Add restore transition under user lock and archival timestamp in `c419_plan_restore.py` with `down_revision = 'c418_matching_preview'`; add cleanup command and document its free scheduled execution. Keep result rows sufficient for 30-minute replay.
- [ ] Run focused tests; expect pass. Commit Task 7 files with `feat: restore prior plans and expire previews`.

### Task 8: Clear mobile preview and selection

**Files:** `frontend/src/pages/Onboarding.tsx`, `frontend/src/pages/Onboarding.css`, `frontend/src/onboarding.test.tsx`, `frontend/src/api.ts` if error headers are needed.

**Interfaces:** The client sends survey only to preview, then `preview_id` plus selected IDs/skips to start. The results screen renders first three choices, «Показать весь список», reasons, `skipped` checkboxes and replacement confirmation. On expiry/`409`, it keeps in-form answers and requests a new preview; after uncertain network completion it calls `GET /api/onboarding` before retrying creation.

- [ ] Write failing UI tests for fourth-option selection, skip keeping another plan, 409 re-preview, 429 explanation, repeated click and lost start response; verify mobile overflow separately in a real browser at 390 and 1280 pixels.
- [ ] Run `cd frontend && npm test -- --run src/onboarding.test.tsx`; confirm new failures.
- [ ] Implement accessible radio and checkbox controls, explicit status copy and responsive layout. Do not change the other five sphere routes or course content.
- [ ] Run focused tests and `cd frontend && npm run build`; expect pass. Commit Task 8 files with `feat: let users choose compatible plans`.

### Task 9: Coverage gate, release switch and full verification

**Files:** `backend/app/coverage.py`, `backend/app/content/coverage_baseline.json`, `backend/tests/test_coverage.py`, `.github/workflows/check-content.yml`, `README.md`, `backend/app/config.py` or existing config module, `backend/tests/test_onboarding.py`.

**Interfaces:** `python -m app.coverage --check` compares synthetic pairwise plus named typical profiles with the committed baseline and reports unreachable catalog items. A `SHARED_MATCHING_ENABLED` setting gates the new UI/API until metadata backfill is verified; rollback keeps DB snapshots and revocations.

- [ ] Write failing tests for newly offered survey choice without content, unreachable item, expected baseline update and due-within-30-days review warning.
- [ ] Run focused tests; confirm failures.
- [ ] Implement coverage generator and baseline, create the required GitHub Actions coverage gate (this repo currently has no `.github` directory), and add safe default-off flag plus rollback instructions. Audit that all spec requirements have a test owner.
- [ ] Run `cd backend && .venv/bin/python -m pytest -q`, `cd frontend && npm test -- --run`, `cd frontend && npm run build`, `cd backend && .venv/bin/python -m app.coverage --check`, and `git diff --check`; record exact results. Commit Task 9 files with `test: gate shared catalog coverage`.
