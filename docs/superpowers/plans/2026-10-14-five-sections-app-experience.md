# Five Sections App Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make diary, finances, English A2–B2, guided workouts, and books easier to use as one responsive app while preserving all existing personal records and plans.

**Architecture:** Work within the current React/Vite and FastAPI architecture. Keep static course and public-domain book content in project files, personal records in PostgreSQL, and personal book binaries in the already selected private object storage. Each task below is independently testable and can be released after its own checks; publish only after the full branch is verified.

**Tech Stack:** React 19, TypeScript, TanStack Query, FastAPI, SQLAlchemy, PostgreSQL/SQLite tests, Neon Object Storage, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-10-14-five-sections-app-experience-design.md`

## Global Constraints

- Preserve current routes, records, plans, progress, auth, CSRF protection and idempotent creation.
- Use the existing design tokens and shared control styles; support Russian and Kazakh labels, including Ә Ғ Қ Ң Ө Ұ Ү Һ І.
- No copying of proprietary UI, lessons, workout programs or books from reference apps.
- No public URLs for personal book files; all binary access checks the authenticated owner.
- A sport draft must never count as a completed workout; reading position must never count as a reading log.
- Validate 360, 390, 768 and 1440 px plus 200% zoom; avoid horizontal overflow and text clipping.
- Existing source checkout is dirty. Stage only files named for each task; use the clean deployment mirror for release commits. A prior automatic review rejected GitHub push; recheck explicit authorization before retrying it.

## Review Focus

- A diary entry with mood and activities but no prose saves and appears in calendar/history (Task 1 tests).
- Old diary entries with only the legacy `activity` still display correctly after schema migration (Task 1 tests).
- Finance totals never combine unlike currencies or invent a balance from missing accounts (Task 2 tests).
- A wrong grammar answer gives feedback without completing a lesson or overwriting the final attempt (Task 3 tests).
- A foreign user or malformed EPUB/FB2/PDF cannot download, render, or leave a partial personal book (Task 5 tests).

---

### Task 1: Daily diary and mood history

**Files:** Modify `backend/app/models.py`, `backend/app/routes/personal.py`, `frontend/src/personalTypes.ts`, `frontend/src/components/PersonalForm.tsx`, `frontend/src/pages/Personal.tsx`, `frontend/src/pages/Journal.module.css`; test `backend/tests/test_personal.py` and `frontend/src/personal.test.tsx` (create if absent). Include a forward-only migration through the project's existing schema initialization or migration path, and update backup serialization if it enumerates fields.

**Interfaces:** `PersonalEntry.activities: list[str]` in API, known codes from `activityNames`; legacy `activity: str` remains during transition. Calendar reads the same dated diary entries.

- [ ] Write failing API tests: mood + two activities + empty text saves; unknown activity rejects; legacy row without `activities` yields its old activity; other account cannot read; repeated create key returns one entry.
- [ ] Run `cd backend && .venv/bin/python -m pytest tests/test_personal.py -q`; confirm new assertions fail for missing list/validation.
- [ ] Add persisted activities and migration, update Pydantic validation/serialization/search and archive fields, and retain event/experiment behavior.
- [ ] Run the same API tests until pass.
- [ ] Write failing UI tests for mood-first quick entry, multi-select activities, optional note, dated history/calendar and edit of a legacy entry; run `cd frontend && npm test -- --run src/personal.test.tsx` and confirm failures.
- [ ] Implement the daily entry layout and compact history in the existing page/components; use existing controls and focus/error states.
- [ ] Run the UI tests, `npm run build`, and the existing calendar/backup tests; stage and commit only Task 1 files.

### Task 2: Finance overview and operation flow

**Files:** Modify `frontend/src/pages/Finance.tsx`, `frontend/src/pages/Finance.module.css`; test `frontend/src/finance.test.tsx`. Backend API is unchanged unless a test reveals a calculation defect.

**Interfaces:** Continue consuming `/finance/summary`, `/finance/incomes`, `/finance/expenses`, categories and existing `FinanceSettings`; no new accounts, transfers or budgets.

- [ ] Write failing UI tests: selected-month income, expense and difference are distinct; both add actions are visible; changing month updates figures; empty or failed data shows honest states; currency selection does not blend records.
- [ ] Run `cd frontend && npm test -- --run src/finance.test.tsx`; confirm the new assertions fail.
- [ ] Reorder the existing dashboard into month header, three summary figures, trend/categories, and combined operation history with two clear add actions. Keep guide/settings secondary and preserve editing/deletion.
- [ ] Run focused tests and `npm run build`; inspect 360 and 1440 px, then stage and commit only Task 2 files.

### Task 3: English grammar path across A2–B2

**Files:** Modify the English lesson catalog files discovered through `backend/app/study.py`, `frontend/src/components/StudyLesson.tsx`, `frontend/src/pages/Study.module.css`, and any matching lesson types; test `backend/tests/test_study_content.py`, `frontend/src/study.test.tsx` (or current lesson test file). Do not alter Java/Go lesson rendering.

**Interfaces:** Each English lesson has versioned grammar content `{rule, table, examples, check}` or explicitly uses `topic_review`; grammar check is local UI state and does not create a `StudyAttempt`. The existing final quiz and saved draft contract remain authoritative for progress.

- [ ] Write failing content tests: every A2/B1/B2 lesson has a valid grammar or topic-review block, table headers/rows align, check has one accepted answer and explanation, and existing lesson IDs/versions remain stable or have explicit migration.
- [ ] Run `cd backend && .venv/bin/python -m pytest tests/test_study_content.py -q`; confirm the missing blocks fail.
- [ ] Add authored grammar blocks in content files, with one clear rule, form table, contrasting examples and a check per topic; extend catalog validation/serialization only as required.
- [ ] Write failing UI tests: grammar check precedes words, wrong answer explains without saving a final attempt, long bilingual text wraps, Java/Go remain unchanged; run focused frontend test and confirm failures.
- [ ] Render the four-step English learning sequence using current study components; keep final attempts and draft storage intact.
- [ ] Run content coverage, focused UI tests, `npm run build`, and commit only Task 3 files.

### Task 4: Guided workout rest and completion

**Files:** Modify `frontend/src/pages/Sport.tsx`, `frontend/src/pages/Sport.css`, `frontend/src/sport.test.tsx`; backend unchanged unless exercise-level draft persistence needs a contract correction.

**Interfaces:** Existing `/health/sport/draft` stores actual sets/reps/weight. Rest countdown is transient UI state; completed workout is created only by existing finish endpoint.

- [ ] Add failing tests for starting/skipping rest after a set, timer cleanup on completion/navigation, draft restoration to first unfinished exercise, and no completed history row before «Завершить тренировку».
- [ ] Run `cd frontend && npm test -- --run src/sport.test.tsx`; confirm the new assertions fail.
- [ ] Complete the guided screen already implemented locally: clear set actions, rest timer controls and stable mobile layout; preserve technique/replacement, autosave and separate finish.
- [ ] Run focused sport tests and build; check mobile and desktop; stage and commit only Task 4 files. Do not duplicate the existing unpushed guided-workout commit in the mirror.

### Task 5: Catalog reader and private personal books

**Files:** Modify `backend/app/models.py`, `backend/app/routes/library.py`, `backend/app/routes/reading.py`, `backend/app/backup_archive.py`, `frontend/src/components/BookSuggestions.tsx`, `frontend/src/components/BookSuggestions.css`, `frontend/src/pages/Reading.tsx`, and reading types; create focused `backend/app/book_storage.py` and `frontend/src/components/BookReader.tsx` if needed; test `backend/tests/test_library.py`, `backend/tests/test_reading.py`, and matching frontend reading tests.

**Interfaces:** Authenticated upload/list/content/delete endpoints under `/api/reading/books` for per-user EPUB/FB2/PDF; binary body goes to private object storage, metadata/progress/bookmarks to DB. Existing `/api/library/books/{id}/read` and download remain for bundled EPUB. Define typed reader-location `{format, chapter, position}` for reflowable text and `{format:'pdf', page}` for PDF, scoped to owner and content checksum/version.

- [ ] Write failing backend tests for valid EPUB/FB2/PDF import, magic/structure mismatch, archive bombs and oversized files, duplicate/retry behavior, foreign-user access, missing object and rollback/cleanup after failed upload.
- [ ] Run `cd backend && .venv/bin/python -m pytest tests/test_library.py tests/test_reading.py -q`; confirm new assertions fail.
- [ ] Add object-store adapter/configuration and metadata migration; implement authenticated upload, range-safe content delivery, bookmark/location update, deletion cleanup and backup metadata. Ensure public catalog and personal objects never share an unrestricted endpoint.
- [ ] Write failing frontend tests for table of contents, resume position, bookmarks, theme/font controls, PDF page resume, upload progress/errors and manual-title fallback; run focused tests and confirm failures.
- [ ] Build the reader and personal-library controls, including explicit file picker and clear unsupported-format text. Keep logging a reading session separate from merely opening or moving through a book.
- [ ] Run backend reading/library/backup tests, frontend reading tests and build; verify two-account isolation and responsive reader; stage and commit only Task 5 files.

### Task 6: Integrated release gate

**Files:** Only fix files where the integrated check finds a concrete defect; update `README.md` with actual supported formats and deployment configuration.

**Interfaces:** Existing Cloudflare Pages `/api` proxy and Render backend; no new public storage URL.

- [ ] Run all backend tests, frontend tests, content coverage and frontend build; repair only failures caused by this plan.
- [ ] Open diary, finance, English, sport and reading in the browser at 360, 390, 768 and 1440 px and 200% zoom; check long Russian/Kazakh labels, overflow, loading/error states and keyboard focus. Fix defects in one bounded pass and recheck.
- [ ] Verify object storage and PostgreSQL migration against a non-production environment before enabling personal uploads publicly; if unavailable, ship the other completed sections while keeping upload disabled and report that limit.
- [ ] Check the exact GitHub remote and compare changed files with the authorized scope, push only after approval check, then verify the Cloudflare public route and API behavior. Report deployed versus local-only features separately.
