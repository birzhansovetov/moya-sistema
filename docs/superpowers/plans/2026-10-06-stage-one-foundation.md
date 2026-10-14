# Stage One Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working stage of «Моя система»: email access, profile, persistent tasks and calendar, and a truthful «Мой день» on desktop and phone.

**Architecture:** A React SPA on Cloudflare Pages calls `/api` through a Pages Function proxy to a FastAPI service on Render. FastAPI owns authentication, authorization and all personal data in Neon PostgreSQL. This stage has no sport or nutrition program UI until its materials are built in the next stage.

**Tech Stack:** Python, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Argon2id, React, TypeScript, Vite, React Router, TanStack Query, CSS Modules, Cloudflare Pages Functions.

**Spec:** `/Users/birzhansovetov/Downloads/CODEX_PERSONAL_PLATFORM.md`; approved decisions: `docs/architecture.md`.

**Текущее состояние (10 октября 2026):** задачи 1–18 реализованы локально в предыдущих этапах. Ниже сохранена историческая формулировка первого этапа; дополнение «Personal-use refinement» охватывает улучшения 19–21. Публикация отложена по просьбе пользователя.

## Global Constraints

- Russian interface; graphite background, lighter surfaces, readable light text and blue accent.
- Desktop sidebar; mobile bottom navigation with «Мой день», «Разделы», «Задачи», «Профиль».
- Verify 390 px and desktop layouts, keyboard focus, labels, loading and error states.
- Store personal data on the server, scoped to the authenticated user; never trust owner ID from a form.
- No fabricated personal progress, placeholder content presented as finished, mandatory AI, or paid service.
- Keep drafts on network failure and confirm persistence before showing success.
- No credentials or personal data in source, browser storage, logs or screenshots.

## Review Focus

- Tasks near local midnight render on the correct day for the user's time zone (Task 2 date tests).
- Completing one repeated occurrence leaves other dates incomplete (Task 2 recurrence tests).
- Two rapid submissions create only one task (Task 2 idempotency test, Task 4 UI disabled state).
- A second account cannot read, change or complete the first account's task (Tasks 1 and 2 access tests).
- A failed save keeps entered text and offers retry without a false success state (Task 4 UI test).

---

### Task 1: Accounts, sessions and profile API

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/models.py`, `backend/app/auth.py`, `backend/app/mail.py`, `backend/app/main.py`, `backend/app/routes/auth.py`, `backend/app/routes/profile.py`, `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/versions/0001_initial.py`
- Test: `backend/tests/test_auth.py`, `backend/tests/conftest.py`

**Interfaces:**
- Produces: `create_app() -> FastAPI`, `get_current_user()` dependency, `/api/auth/*` and `/api/profile`, `User` and `Session` models.
- Consumes: `DATABASE_URL`, `JWT_SECRET`, Gmail OAuth settings from backend environment; a test mail sender is injected only in tests.

- [ ] Write tests for registration, one-time verification, login, refresh rotation, immediate logout, password reset, profile persistence and two-account isolation.
- [ ] Run the targeted suite and confirm the missing feature causes failure.
- [ ] Implement models, migrations, Argon2id, signed access JWT, hashed refresh tokens, `HttpOnly` cookies, CSRF validation, mail adapter and routes.
- [ ] Run the targeted and full backend suites; confirm all tests pass.
- [ ] Commit the self-contained account API.

### Task 2: Tasks, occurrences and calendar API

**Files:**
- Create: `backend/app/tasks.py`, `backend/app/routes/tasks.py`, `backend/app/routes/calendar.py`, `backend/migrations/versions/0002_tasks.py`
- Modify: `backend/app/models.py`, `backend/app/main.py`
- Test: `backend/tests/test_tasks.py`, `backend/tests/test_calendar.py`

**Interfaces:**
- Consumes: `get_current_user()` and user-scoped database session from Task 1.
- Produces: `/api/tasks`, `/api/task-occurrences`, `/api/calendar`; local-date occurrence calculation and separate completion records per recurrence date.

- [ ] Write tests for task CRUD, priorities, subtasks, daily/weekly/weekday recurrence, per-date completion, missed days, move/delete, idempotency and access isolation.
- [ ] Run the targeted suite and confirm failure for missing task API.
- [ ] Implement task models, migrations, recurrence calculation and user-scoped routes.
- [ ] Run the targeted and full backend suites; confirm all tests pass.
- [ ] Commit the tasks and calendar API.

### Task 3: Responsive application shell and account screens

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/auth.tsx`, `frontend/src/styles.css`, `frontend/src/pages/Auth.tsx`, `frontend/src/pages/Profile.tsx`, `frontend/src/components/Shell.tsx`
- Test: `frontend/src/auth.test.tsx`

**Interfaces:**
- Consumes: Task 1 auth/profile API and CSRF token response.
- Produces: authenticated React shell, registration/verification/login/reset/profile flows and API client with credentialed same-origin requests.

- [ ] Write a UI test for failed sign-in retaining input and displaying a recoverable error.
- [ ] Run the targeted test and confirm it fails for the missing screen.
- [ ] Implement the shell and account screens with explicit loading, empty, error and focus states.
- [ ] Run the UI test, TypeScript check and production build.
- [ ] Commit the usable account UI.

### Task 4: Tasks, calendar, «Мой день» and deployment contract

**Files:**
- Create: `frontend/src/pages/Tasks.tsx`, `frontend/src/pages/Calendar.tsx`, `frontend/src/pages/Today.tsx`, `frontend/src/pages/Sections.tsx`, `frontend/src/components/TaskForm.tsx`, `frontend/functions/api/[[path]].ts`, `frontend/src/tasks.test.tsx`, `README.md`, `backend/.env.example`, `frontend/.env.example`
- Modify: `frontend/src/App.tsx`, `frontend/src/styles.css`, `docs/architecture.md`

**Interfaces:**
- Consumes: Task 2 task/calendar API and Task 3 shell/API client.
- Produces: real task views (today, week, list, board), calendar, truthful weekly progress, idempotent create and deployable Pages proxy.

- [ ] Write UI tests for create, completion, failed save with retained draft and truthful empty/progress states.
- [ ] Run the targeted test and confirm missing behavior fails.
- [ ] Implement task views, calendar, day view, Pages proxy and deployment documentation.
- [ ] Run backend tests, frontend tests, TypeScript check and build; inspect desktop and 390 px rendering and keyboard operation.
- [ ] Commit the first-stage app and report any integration that needs live provider credentials.

---

## Stage Two Extension: Health with Ready Materials

Tasks 1–4 above were implemented and committed in the first stage. This section extends the same plan rather than creating a replacement. The binding design is the «Следующий этап: здоровье» section of `docs/architecture.md`. Execute tasks 5–10 inline through `superpowers:executing-plans`.

**Goal:** Make «Здоровье» a working sphere with selectable prepared sport programs and a nutrition path with sourced recipes, calculation, menus, purchases and journals. Plans stay inside Health; Tasks stays separate.

**Review focus:** A second account cannot read a plan or log; a plan change retains previous completions; unsupported restrictions yield no program/menu; portion changes alter nutrition and purchases consistently; «Мой день» never duplicates a plan action as a task.

### Task 5: Six-sphere navigation and preferences

**Files:** Modify `frontend/src/pages/Sections.tsx`, `frontend/src/App.tsx`, `backend/app/models.py`, `backend/app/routes/profile.py`; create `frontend/src/pages/Health.tsx`, migration and focused UI/API tests.

**Interfaces:** Produces `/sections` with exactly six top-level spheres and `/health` linking to sport/nutrition. `GET/PATCH /api/profile/spheres` returns `hidden_spheres`, separate from task section tags. Only Health is marked available until later stages.

- [x] Write tests that six cards appear, Health opens its own page, unsupported spheres do not route to task filters, hiding a sphere persists per account, and legacy task-section preferences still work.
- [x] Run focused tests and confirm failures from missing navigation/API.
- [x] Add the migration, API and UI; show accurate availability and keep existing task categories intact.
- [x] Run backend/frontend suites, typecheck and build; commit.

### Task 6: Versioned sport library and deterministic matching

**Files:** Create `backend/app/content/exercises.json`, `backend/app/content/sport_programs.json`, `backend/app/sport.py`, `backend/tests/test_sport_content.py`; modify `backend/pyproject.toml` for bundled content.

**Interfaces:** `load_sport_catalog() -> dict` validates identifiers, sources and complete sessions; `select_program(answers: SportAnswers) -> MatchResult` returns one compatible whole program or explicit reasons for no match. Supports the first goal (weight reduction with emphasis on retaining muscle) at home without equipment, outdoors and in the gym for supported beginner schedules; no medical restriction is silently ignored.

- [x] Write tests for each supported place, exercise instructions, source links, exact day/time matching, unavailable goal, missing equipment and restrictions.
- [x] Run focused tests and observe missing library/matcher failures.
- [x] Author complete program files with warm-up, work, rest and finish; implement loader and matching rules without arbitrary fallback.
- [x] Run focused and full backend tests; commit.

### Task 7: Sport plans, history and usable pages

**Files:** Modify `backend/app/models.py`, `backend/app/main.py`, `frontend/src/App.tsx`, `frontend/src/pages/Health.tsx`; create `backend/app/routes/sport.py`, migration, `backend/tests/test_sport.py`, `frontend/src/pages/Sport.tsx`, UI tests.

**Interfaces:** `GET /api/health/sport/catalog`, `GET/PUT /api/health/sport/plan`, `GET/POST /api/health/sport/workouts`. Replacing an existing plan requires explicit confirmation and closes the old plan without deleting its workout history. Sport page owns questionnaire, selection explanation, weekly plan, exercise guides and completion journal.

- [x] Write two-account, replacement-history, workout-validation and UI tests (including failed save retaining the questionnaire).
- [x] Run tests and confirm expected missing behavior.
- [x] Implement user-scoped models/API and the Sport page; do not create task copies.
- [x] Run backend/frontend suites, typecheck and build; commit.

### Task 8: Calorie estimate and sourced recipe library

**Files:** Create `backend/app/nutrition.py`, `backend/app/content/foods.json`, `backend/app/content/recipes.json`, `backend/app/routes/nutrition.py`, `backend/tests/test_nutrition_content.py`; modify `backend/app/main.py`.

**Interfaces:** `estimate_nutrition(answers: NutritionAnswers) -> Estimate` uses documented Mifflin–St Jeor inputs and FAO/WHO/UNU activity classes and states limits; `load_recipes()` computes totals from sourced ingredient records with raw/cooked state. `GET /api/health/nutrition/recipes` and `POST /api/health/nutrition/estimate` expose verified results without requiring paid APIs at runtime.

- [x] Write tests for formula inputs, adult/special-state bounds, portion arithmetic, ingredient source and raw/cooked unit consistency; confirm failures.
- [x] Import and check ingredient values from USDA FoodData Central into versioned files, author complete recipes with method, duration, servings and source identifiers.
- [x] Implement pure calculations and read-only routes; run focused and full backend tests; commit.

### Task 9: Nutrition profile, menu, purchases and actual logs

**Files:** Modify `backend/app/models.py`, `backend/app/routes/nutrition.py`; create migration and `backend/tests/test_nutrition.py`.

**Interfaces:** `GET/PUT /api/health/nutrition/profile`, `GET/POST/PATCH /api/health/nutrition/menu`, `GET/POST /api/health/nutrition/food-log`, `GET/POST /api/health/nutrition/weight-log`. Menus use only compatible recipes; changes to servings or dish recalculate day totals and a grocery list grouped by ingredient and preparation state. Consumed food and weights are independent of the menu and keep numeric snapshots for history.

- [x] Write tests for compatible seven-day menu, no-match, replacement/portion totals, shopping quantities, user isolation, historical snapshots and failed validation; confirm failures.
- [x] Implement models and migrations, deterministic menu selection, user-scoped routes and idempotent log creation.
- [x] Run focused and full backend suites; commit.

### Task 10: Nutrition UI and direct «Мой день» actions

**Files:** Create `frontend/src/pages/Nutrition.tsx`, `frontend/src/healthTypes.ts`, focused UI tests; modify `frontend/src/App.tsx`, `frontend/src/pages/Health.tsx`, `frontend/src/pages/Today.tsx`, `frontend/src/styles.css`, `README.md`.

**Interfaces:** Nutrition page has questionnaire and estimate explanation, recipe library, seven-day menu, editable servings and substitutions, purchase list, eaten log and weight history. «Мой день» reads training and meal plan entries for the selected date directly; these do not change task counts.

- [x] Write UI tests for estimate loading/error, saved profile, recipe/portion change, no-compatible-menu and direct plan actions on «Мой день»; confirm failures.
- [x] Implement the responsive flows with labels, keyboard access, draft retention and truthful save status.
- [x] Run all backend/frontend tests, typecheck and build; inspect desktop and 390 px rendering, then commit and report any live-provider limits.


## Stage Three Extension: Finance — approved 2026-10-10

Continue the existing architecture and plan. The user approved the proposed Finance scope with «сделай». Existing Health and task functionality remain the regression baseline. No new services or dependencies.

**Goal:** Private manual expense tracking with editable categories, currency setting, day/week/month totals and monthly category analysis. Income, budgets, bank sync and exchange-rate conversion are outside this stage.

**Review focus:** decimal money is exact; currencies never mix; user-local dates determine today/week; another account cannot access expenses/categories; retrying a failed save cannot duplicate an expense; edit/delete/restore refresh totals; failed writes preserve drafts; changing display currency never rewrites existing entries.

### Task 11: Private finance API and migration

**Files:** Create `backend/app/routes/finance.py`, `backend/tests/test_finance.py`, `backend/migrations/versions/b36a10f1_finance.py`; modify `backend/app/models.py`, `backend/app/main.py`.

**Interfaces:** `/api/finance/settings` GET/PATCH for preferred currency (initial KZT); `/categories` GET/POST and `/categories/{id}` PATCH for per-user seeded/editable categories; `/expenses` GET/POST and `/expenses/{id}` PATCH/DELETE plus POST `/restore`; `/summary?month=YYYY-MM&currency=...`. Prefix is `/api/finance`. Expense amounts travel as decimal strings and are stored in integer hundredths. Supported initial currencies KZT/USD/EUR/RUB/GBP each use two decimal places. Every expense retains its own currency. History supports date range, category, search, pagination and deleted-state filtering. Deletion is reversible through the deleted-records view. Create requests carry an idempotency key. Aggregate SQL queries always scope by user, currency and period.

- [x] Write API tests for exact amounts, local date/week/month boundaries, categories, currency separation, CRUD/restore, retry, invalid amounts/inputs, cross-account isolation and CSRF.
- [x] Run `cd backend && .venv/bin/python -m pytest tests/test_finance.py -q --tb=short`; expected: missing route failures.
- [x] Implement models, routes and Alembic migration with existing auth/session conventions.
- [x] Run full backend suite and migration upgrade/downgrade on a disposable local database; expected: all pass; commit.

### Task 12: Finance workspace and integration

**Files:** Create `frontend/src/pages/Finance.tsx`, `frontend/src/financeTypes.ts`, `frontend/src/components/ExpenseForm.tsx`, `frontend/src/pages/Finance.module.css`, `frontend/src/finance.test.tsx`; modify `frontend/src/App.tsx`, `frontend/src/pages/Sections.tsx`, `frontend/src/spheres.test.tsx`, `README.md`.

**Interfaces:** `/finance` opens from the Finance sphere. Show quick amount/category entry with local date, optional comment and currency, three real totals, month/category chart, filterable/paged history with editing and reversible deletion, editable categories, preferred-currency setting. No mock expenses. Server sums are the authority. The form preserves its idempotency key on failed retries and its values on failure; only success clears it. Pending requests disable duplicate submits. History filters and summary scope are clearly labeled. Categories and expenses never route through Tasks.

- [x] Write UI tests for failed create retaining amount/key, successful save and edit, delete/restore, currency selection, monthly category totals and Finance navigation.
- [x] Run focused UI tests; expected: missing page/behavior failures.
- [x] Implement responsive page and existing router integration, including loading, empty and recoverable error states.
- [x] Run backend and frontend suites, typecheck/build, inspect desktop and 390 px and keyboard interaction. Expected: passing checks and no overflow. Commit and report verified scope/provider limits.

## Stage Four Extension: Personal life and reading — requested 2026-10-10

Continue the existing architecture and staged plan following «делай». Learning languages, human languages/levels and professional direction are pending a separate content-selection answer; do not infer those choices. Independently implement the already specified personal/reading workflows. No new providers, dependencies, storage services or AI.

### Task 13: Private personal journal and events

**Files:** `backend/app/models.py`, `backend/app/routes/personal.py`, new migration, `backend/tests/test_personal.py`; `frontend/src/pages/Personal.tsx`, `frontend/src/personalTypes.ts`, `frontend/src/personal.test.tsx`, router/Sections integration.

**Interfaces:** `/api/personal/entries` GET/POST, `/{id}` GET/PATCH/DELETE, `/{id}/restore` POST. Kind diary/event/experiment; diary date required, other kinds may be unscheduled ideas; title/body/mood/activity/completed/impression. User-scoped history, search, kind/deleted/date filters, pagination. Explicit dates, idempotent creation, recoverable removal, drafts preserved on failures. Ready authored guides for daily reflection, weekly reflection and trying a hobby; no invented feelings. Calendar integration in Task15 excludes diary text entirely.

- [x] Write privacy/CSRF/date/idempotency/edit/delete/restore and filter tests; run to RED.
- [x] Implement model, migration and API; run backend suite and disposable migration roundtrip.
- [x] Write UI draft/error/retry/edit/restore tests; run to RED, then build responsive working page and integration.
- [x] Run frontend suite, typecheck/build; commit and ledger.

### Task 14: Books and reading journal

**Files:** reading models/routes/migration/tests; `frontend/src/pages/Reading.tsx`, reading types/tests, education landing and router integration.

**Interfaces:** `/api/reading/books` GET/POST/PATCH/DELETE/restore with title/author/optional cover URL/page count/current page/status/start/end dates/daily page target/final impression; `/books/{id}/logs` GET/POST/PATCH/DELETE/restore with local date/optional page or chapter/free text/six optional reflection fields. Keep page-progress history; latest dated active page log determines current page. No automatic feelings. User-scoped idempotency and drafts. Ready reading guide and sourced suggestions, no full copyrighted texts.

- [x] Write API privacy/validation/idempotency/reading progress history and recovery tests; confirm RED, implement and run backend suite/migrations.
- [x] Write frontend free-text-only save, failed draft and progress tests; confirm RED, implement books/reading journal with search/history and next page target.
- [x] Run frontend suite, typecheck/build; commit and ledger.

### Task 15: Guides and daily/calendar integration

**Files:** versioned guide/suggestion content and authenticated route; generic guide UI; Calendar/Today pages and tests; README and verification report.

**Interfaces:** `/api/library/guides?area=personal|reading|finance`; authored step-by-step materials, examples and self-check criteria. `/api/calendar` adds `personal_items` for dated active event/experiment records; never exposes diary/mood/impressions there. Today uses the same events and direct reading links; task counts remain task-only. Reading next step computed from stored page/target and explicit reading status. Finance guide explains accurate entry/monthly review within expense-only scope.

- [x] Write integration tests for date-scoped event links and diary exclusion plus daily reading steps; observe RED, then implement.
- [x] Verify complete backend/frontend suites, production build, desktop/390px and keyboard flow using disposable account; commit.
- [x] One fresh final review for this extension, fix Important/Critical findings with RED→GREEN, document scope/provider limits.


## Approved continuation — Java, English A2 to B2, Java backend (10 October 2026)

Same stack, static versioned authored materials and private server progress. Selection is inside the site: level, goal, days and time. English A2/B1/B2 are practice stages, not automatic CEFR certification. No code execution, AI grading or new external provider. Audio is bundled from locally synthesized original scripts, labelled synthetic. All core lesson text, examples, exercises, answers and rubrics are inside the site. Own subjects/material uploads remain outside this selected-route extension.

### Task 16: Authored curricula and working audio

**Files:** versioned course JSON, frontend/public/audio/study-v1, content validation tests and provenance.
**Interfaces:** courses java, english, java-backend; stable lesson/card IDs, version; explanation/example/practice/solution/rubric/quiz; English adds original reading, vocabulary, audio/transcript/listening question and speaking prompt. Twelve Java lessons, 24 English lessons (8 per A2/B1/B2), eight backend project lessons. Explain limitations and prerequisites.

- [x] Content tests first: complete teaching flow, answer keys, unique IDs, local audio files, all three stages; observe RED.
- [x] Author materials and local audio; verify content and audibility, relevant primary references. Expected: complete internally usable lessons, no external core dependencies.
- [x] Commit and record content verification.

### Task 17: Plans, assessment, history and spaced vocabulary API

**Files:** study models/migration/service/routes/tests.
**Interfaces:** authenticated catalog; preview/create plan with expected active plan ID and idempotency; area-scoped active plan, archive retains history; immutable attempt snapshots, server-checked answers and explicit self-assessment/evidence; persisted cards/reviews with due dates and stale-write guards; daily next step by user's selected weekdays/date. Unknown level diagnostic gives limited A2/B1 guidance, never B2 certification. Private history and portfolio evidence are server-owned. Study never creates Tasks.

- [x] API tests RED: privacy/CSRF, scoring variants and failure practice, normalized retries/conflicts, replacement retains historical content, timezone/dates, due cards and stale review, separate plans.
- [x] Implement and migration roundtrip on disposable SQLite; full backend suite. Expected: server persistence, no forged scores/owners, old lesson snapshots stable.
- [x] Commit and ledger.

### Task 18: Learning interfaces, personalization and daily integration

**Files:** Study page/components/types/CSS, Education/Sections/App/Today, frontend tests, docs/report.
**Interfaces:** /education/java, /languages, /profession. Questionnaire → preview → explicit confirm; overview, lesson reader, audio, vocab cards, quiz/evidence/self-check, errors retained, history/plan switch, portfolio links; My Day direct date/plan/lesson links and separate task counts.

- [x] UI tests RED: preview vs activation, wrong-answer explanations, failure drafts and same retry key, stale plan links, vocabulary review, date links.
- [x] Implement responsive pages; full frontend suite and build. Expected: core lesson complete within site and confirmations only after saved results.
- [x] Browser verify desktop/390px, audio playback, refresh persistence with fake account, no overflow; one fresh final review and one RED→GREEN fix pass for Important/Critical findings.
- [x] Record limits, update existing docs and commit.

## Personal-use refinement — approved 10 October 2026

The user chose to improve all three existing areas before any publication: daily use, ready materials, and mobile usability. Keep the agreed stack, private server data, separate Tasks, and free local content. Do not publish or connect new services in this extension.

### Task 19: Daily navigation and compact mobile lessons

**Interfaces:** «Мой день» gives direct date navigation and links to its real plan/task sections; the mobile study outline selects a lesson without pushing the reader below a long scroll. Desktop retains the full outline. Dates and plan IDs in direct lesson links remain unchanged.

- [x] Add focused UI behavior tests for date navigation and mobile lesson selection; observe RED.
- [x] Implement the existing-page controls and responsive styling; verify keyboard use and 390/1280 px rendering.
- [x] Run frontend regression and build; commit.

### Task 20: Recoverable study drafts

**Interfaces:** The current study form can save an unfinished draft privately through FastAPI, reload it on another visit/device, and clearly show whether it is saved. Draft data stays on the server, scoped to user, plan and lesson. A successful attempt removes its draft; a failed attempt does not. Archived plans permit reading an old draft but no new draft write. No browser storage of personal text.

- [x] Add API tests for save/reload, ownership, validation, archived plan, and clearing only after confirmed attempt; observe RED.
- [x] Implement model, migration and routes; migration roundtrip on disposable database.
- [x] Add UI tests for save/reload and failed save retaining text; observe RED, implement.
- [x] Run backend/frontend regressions and build; commit.

### Task 21: More useful ready practice and accurate documentation

**Interfaces:** Replace repeated generic Java and Java-backend check questions with distinct lesson-specific questions and feedback. Wrong answers direct learners to a concrete retry exercise from the authored lesson. Keep published attempt snapshots immutable. Update README and existing plan status to reflect actual six-sphere local scope and current limits.

- [x] Add content/feedback tests that reject repeated generic checks and confirm wrong-answer follow-up is visible; observe RED.
- [x] Author lesson-specific checks and retry prompts inside the existing versioned content file; implement feedback UI.
- [x] Run complete suites, build, content validation and browser checks; one independent final review, fix Important/Critical with RED→GREEN, report limits and commit.

## Personal-use readiness continuation — 10 October 2026

The user requested an audit of all six spheres, more useful health materials, a manual encrypted backup in Profile, and publication only after local improvements. The six-sphere route audit at 390 px and 1280 px found no horizontal overflow or missing headings. The existing stack and file-based authored materials remain in place.

### Task 22: Fill short-session and quick-meal gaps

**Interfaces:** Keep existing sport match and nutrition recipe/menu APIs. Add three complete 25-minute beginner strength programs for home, outdoors, and gym; choose the longest available program within the user's time and equipment. Add sourced, fully specified recipes so a 30-minute preference includes lunch and a gluten-free breakfast. Keep archived plan and menu snapshots intact.

- [x] Add focused matching and compatibility tests; observe failures on the previous catalog.
- [x] Add six-program catalog and expanded recipe library; retain existing long-program choices at 40–45 minutes.
- [x] Run complete backend and frontend suites and production build. No changes to live providers.

### Task 23: Encrypted manual backup and restore

**Spec:** `docs/architecture.md`, «Дополнение: личный зашифрованный архив». The user approved replacement after downloading a safety copy, encryption with the login password used at export, and the written design. Keep the existing stack and plan. Maximum archive and decrypted payload: 8 MiB each. Exclude credentials, sessions, tokens, auth events and the restore-marker table. A previously exported archive still needs its original password after a password change. Never persist plaintext archives or passwords.

**Review focus:** A one-byte change to the file must fail before deletion; a changed account password must not make a valid old archive appear corrupt; a new expense added after preview must block restore until a new safety copy is downloaded; a foreign account's records must remain untouched; a failed insert must restore all prior rows and leave the marker unused. Tests for these cases belong to Tasks 23a/23b.

#### Task 23a: Archive codec and complete personal snapshot

**Files:** create `backend/app/backup_archive.py`, `backend/tests/test_backup_archive.py`; modify `backend/pyproject.toml` to add `cryptography>=43,<52`.

**Interfaces:** `snapshot_user(db: Session, user: User) -> dict` exports exactly the 18 personal model types and safe user settings from the architecture addendum; `validate_snapshot(value: object, email: str) -> dict` validates version, whitelist, column types, unique IDs/keys, account email and all task/plan/category/book foreign references; `seal_snapshot(snapshot: dict, password: str) -> bytes` and `open_snapshot(archive: bytes, password: str) -> dict` use magic/version + random 16-byte salt + 12-byte nonce, scrypt (`n=2**15,r=8,p=1`, 32-byte key), AES-256-GCM and authenticated header. Preserve dates/datetimes and JSON snapshots. SHA-256 is for file/state fingerprints, never a password key.

- [x] Write focused tests for all personal tables, two-account isolation, roundtrip, old-password decrypt after reset, tampering/wrong password/unknown version/oversize, malformed/duplicate/cross-linked rows, and absence of secrets. Run `.venv/bin/python -m pytest -q tests/test_backup_archive.py`; expected RED on missing module.
- [x] Implement minimal codec and snapshot/validation with explicit model whitelist and dependency order; run targeted test to GREEN. Reject compressed or nested archives and unknown fields; never run archive-supplied code.
- [x] Run full backend suite and commit this self-contained codec.

#### Task 23b: Authenticated preview, safety copy and transactional replacement

**Files:** create `backend/app/routes/backup.py`, migration `backend/migrations/versions/c414_backup.py` (down revision `c413_study_drafts`), `backend/tests/test_backup_api.py`; modify `backend/app/models.py`, `backend/app/main.py`, `backend/pyproject.toml` (`python-multipart>=0.0.12,<1` for bounded file upload).

**Interfaces:** `POST /api/profile/backup/export` accepts current password in JSON and returns binary archive. `POST /preview` accepts multipart file and archive password, returns counts, created_at and 10-minute signed preview token tied to session, SHA-256 file and canonical current-state digest. `POST /safety-copy` accepts preview token + current password and returns a fresh encrypted archive plus a 10-minute restore token in `X-Restore-Token`; output is uncached. `POST /restore` accepts multipart file, archive password, current password and restore token. It revalidates everything, checks state digest and unused token ID, then deletes/reinserts only that user's personal rows in one transaction. Remap `user_id` to current account; retain IDs and links. Exclude auth tables. A used token is stored in `BackupUse` in the same transaction. All four writes require CSRF; all endpoints require authentication. Size and malformed-file errors are bounded, and password/tamper failures have the same public message.

- [x] Write API tests for auth/CSRF, export/preview with no mutation, mandatory safety-copy step, full restore of two users' diverse data, changed current state, old-password archive after password reset, wrong current password, bad version/size/link, reused token and forced mid-transaction rollback. Run `.venv/bin/python -m pytest -q tests/test_backup_api.py`; expected RED on missing routes/model.
- [x] Implement routes, token signing/consumption and migration; run targeted test to GREEN. Check multipart size before reading more than 8 MiB and validate all rows before deletion. No response or log contains passwords or plaintext archive.
- [x] Run full backend suite and disposable Alembic upgrade/rollback test; commit API and migration.

#### Task 23c: Profile controls and end-to-end local verification

**Files:** modify `frontend/src/pages/Profile.tsx`, `frontend/src/api.ts` if needed, `frontend/src/styles.css` or existing Profile styles; create `frontend/src/profile-backup.test.tsx`; update `README.md` and `docs/verification/2026-10-10-readiness.md`.

**Interfaces:** Profile has separate download and restore flows. Download asks for current password and saves a `.moya-backup` file via a temporary object URL. Restore keeps the selected file only in component memory, previews section counts/date, downloads current safety copy, asks the user to confirm it was saved, then enables replacement. If the account password changed, the user enters both the old archive password and current account password. Busy/error states preserve the selected file and never claim success before the server confirms. On success invalidate/refresh all personal queries and clear password/file state; do not put archive or password in local/session storage.

- [x] Write UI tests for download, preview, safety-copy gating, changed-password fields, failure preserving retry data and success refresh; run `npm test -- --run profile-backup.test.tsx`; observed RED before implementation.
- [x] Implement Profile UI and binary/multipart API helpers; focused tests and all frontend tests passed, and `npm run build` passed.
- [x] Exercise the complete API roundtrip with two disposable local accounts and inspect Profile at 390/1280 px. Run full backend suite (`79 passed`), frontend suite (`65 passed`)/build and `git diff --check`; update verification report. Fresh whole-branch review found concurrency and upload-size gaps; fixed and retested. A browser roundtrip using a real password and PostgreSQL concurrency remain deployment checks.

### Task 24: Publication readiness and free-provider verification

After Task 23, verify current production configuration and limits for Neon Free, Cloudflare Pages, Render Free and Gmail API against official docs. Check that Gmail OAuth for this personal account can send mail durably beyond External/Testing's 7-day refresh-token limit. Connect the user's repository and service accounts only through user-controlled sign-in and secret entry; no key or password appears in chat or git. Then deploy on free plans and verify the public Pages URL, API proxy, migrations, email verification/login/reset, archive roundtrip, reload persistence and second-account isolation. If no remote/accounts or a durable $0 Gmail configuration is available, report the exact blocker; do not claim deployment from a local build or HTTP 200 alone. No domain purchase or paid service is authorized.

## Stage Five Extension: Complete materials and clearer interface — approved in conversation

**Spec:** `docs/architecture.md`, «Расширение материалов и интерфейса». Reuse the six spheres, FastAPI/React architecture, versioned authored files and private progress tables. The user requested comparable app functionality and full materials inside the platform, including interface improvements. External products are behavioral references only. Do not import proprietary course text, images, branding or paid APIs. Publication remains deferred.

**Review focus:** Every visible next step opens an authored in-site material; any unavailable route or incompatible option is explicit. Material swaps preserve personal history. «Питание» stays recipe-only, calculator separate. «Задачи» remains independent of plans. All six spheres remain navigable, with simple default screens and secondary controls collapsed.

### Task 25: Recipe discovery

**Files:** `frontend/src/pages/Nutrition.tsx`, `frontend/src/pages/Nutrition.css`, `frontend/src/nutrition.test.tsx`, recipe library and content tests.

- [x] Add tests for meal-category selection, text search by recipe/ingredient, deep links, portion arithmetic and no-result state; observed RED.
- [x] Implement compact category and search controls over the existing sourced recipe library. Grams and portions remain inside recipes; menu, shopping and food logs remain off the page.
- [x] Focused frontend/backend tests and build pass. The catalog loader returns 25 recipes.

### Task 26: Sport exercise alternatives

**Files:** sport catalog/selection and workout UI, focused backend/frontend tests.

- [x] Define and test explicit compatible alternatives by exercise, place and equipment; unsupported swaps remain unavailable and do not silently rewrite the whole plan.
- [x] Offer a local per-session replacement control, preserve the saved program and completed workout snapshots, and validate recorded exercise against the chosen compatible option. Three checked lower-body alternatives are available across home, outdoor and gym plans.
- [x] Sport suites and responsive route inspection pass.

### Task 27: Study and profession practice

**Files:** versioned `study-v1.json`, study loader and page, focused content/UI tests.

- [x] Audit the existing finite v1 curriculum: 12 Java, 24 English A2–B2 and 8 Java backend lessons already contain original explanations, examples, practice, checks, specific retry prompts and source lists. No third-party course content was copied.
- [x] Surface failed-practice retry before secondary history; existing vocabulary review remains in its own tab, using private review/attempt records. Preserve course completion history and avoid certification claims.
- [x] Content loader tests, backend/frontend suites and build pass.

**Ruling:** The proposed new lesson writing was scoped as gap filling. The audited v1 lessons already satisfy the finite starter route, and changing their meaning in place would violate immutable course versions. Further breadth belongs in a new v2 course version with its own authored material; this extension improves access to the existing complete lessons and reports their limits honestly.

### Task 28: Finance and personal guidance

**Files:** finance/personal pages, existing guides content, focused tests.

- [x] Add simple same-currency month comparison and largest-category explanation from existing expense data; no exchange conversion or financial recommendation.
- [x] Add an original change-of-plan guide and a direct path to personal guides; preserve diary privacy and existing entries.
- [x] Both pages' tests and responsive layout pass.

### Task 29: Unified six-sphere UI and whole-product verification

- [x] Keep existing current-plan/next-step/materials hierarchy across six spheres; new recipe discovery, retry and monthly insight sit before secondary history and settings. All routes remain.
- [x] Check 390 px and 1280 px headings and horizontal overflow on main routes; targeted UI tests cover deep links, empty states and errors. Saved progress persists through existing API tests.
- [x] Complete one independent final review; fix the reported stale/paginated study retry issue with backend and frontend regression tests. Fresh backend import sees all 25 recipes; full suites, typecheck and build pass. The already running preview API retains its cached 10-recipe catalog until restarted, so live preview of all 25 remains to verify after that restart. Publication remains deferred.
