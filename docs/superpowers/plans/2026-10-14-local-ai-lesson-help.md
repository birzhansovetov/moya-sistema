# Local AI Lesson Help Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a learner request staged local help for a saved lesson, with checked fallbacks, quality signals and a confirmed next-material recommendation.

**Architecture:** FastAPI owns lesson/version lookup, staged access and output validation. Ollama receives only bounded current-lesson data; authored help from the companion library plan is always available as fallback. The frontend shows the source and never changes a study plan without the existing preview/confirmation path.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Ollama local HTTP, React/TypeScript/Vite, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-10-14-local-ai-learning-library-depth-design.md`

**Dependency:** `docs/superpowers/plans/2026-10-14-learning-library-depth.md` Task 2 provides `get_help_fragment(course_id, version, lesson_id, question_index, *, today)` and the three authored stages. Runtime work may be built alongside catalog work, but enabling it waits for that contract.

## Global Constraints

- Budget $0; use `qwen3:4b-instruct` via local Ollama only. Record actual digest and quantization before enabling a route.
- Preliminary supported machine: 16 GB RAM, 6 GB free disk; validate on the user's device. One model request at a time, immediate busy fallback, 45-second timeout, 20 requests/user/hour.
- Language follows interface: `ru` first; `kk` stays disabled until authored fragments and quality checks exist.
- No diary, finances, password, archive, unrelated account data or raw health data in model requests or logs.
- No execution or grading of user code; no plan change without the current preview/confirmation flow.
- Sport and nutrition AI are outside the first enablement; preserve their existing deterministic matching.

## Review Focus

- Instruction text inside a lesson or user answer: treated as data and cannot change the requested stage (Task 2).
- Old or foreign plan/lesson ID: reject before any model call and do not expose content (Task 1).
- Two simultaneous requests or 21st request in an hour: authored fallback appears and lessons remain usable (Task 2).
- Same generic explanation across users: cache only context-free output keyed by full version/model/prompt metadata (Task 2).
- A generated hint that contains the accepted answer: reject it and show authored hint (Task 2).

---

## File map

- `backend/app/study_assist.py`: request context, prompt version, Ollama call, cache, output checks and fallback; reuse `app.local_ai` connection pattern without enlarging that module.
- `backend/app/routes/study_assist.py`: owned-plan API for help, feedback and aggregate editor report.
- `backend/app/models.py`, `backend/migrations/versions/c422_study_assist_feedback.py`: metadata-only feedback and request metrics, based on the current `c421_workout_drafts` migration head.
- `backend/app/config.py`, `backend/.env.example`, `backend/app/main.py`: per-route enablement and router registration.
- `frontend/src/components/StudyHelp.tsx`, `frontend/src/components/StudyHelp.module.css`: staged, accessible help UI.
- `frontend/src/components/StudyLesson.tsx`: mount help beside the current quiz question.
- `frontend/src/studyTypes.ts`, `frontend/src/study.test.tsx`: request/response types and user-flow tests.
- `backend/tests/test_study_assist.py`: authorization, privacy, ladder, limits and fallback tests.

### Task 1: Owned lesson and stage contract

**Files:** Create `backend/app/routes/study_assist.py`, `backend/tests/test_study_assist.py`; Modify `backend/app/main.py`.

**Interfaces:** `POST /api/study/assist` accepts `{plan_id, lesson_id, question_index, stage: 'explain'|'hint'|'next_step'|'review', attempt_id?: string, answer_text?: string, include_answer?: bool, stage_token?: string}`. `answer_text` is at most 2,000 characters and is ignored unless `include_answer=true`. It returns `{source: 'authored'|'local_ai', stage, text, next_step, lesson_id, version, question_index, next_stage_token?}`. The server derives course/version/user from the owned plan; it never trusts client-supplied content or version. A 15-minute HS256 stage token bound to user, plan, lesson, question and next allowed stage proves ladder progress; `review` also requires an owned saved attempt.

- [ ] **Step 1: Write failing API tests** for own plan/current question, another user's plan, unknown question, historical plan version, and an archived plan. Assert foreign IDs return 404 before model invocation.
- [ ] **Step 2: Run** `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_study_assist.py -q`; expect red.
- [ ] **Step 3: Implement** the route and owned-plan lookup with existing `owned_plan`; use `get_help_fragment` for the authored result. Require an owned saved attempt before `review`; issue and validate HS256 stage tokens using the app secret and a purpose-specific claim, never an auth token.
- [ ] **Step 4: Run** the targeted tests and `backend/tests/test_study.py`; expect green.
- [ ] **Step 5: Commit task files** with `feat: add owned staged lesson help` if repository permissions allow.

### Task 2: Local model, validation, cache and resource limits

**Files:** Create `backend/app/study_assist.py`; Modify `backend/app/routes/study_assist.py`, `backend/app/config.py`, `backend/.env.example`; Test `backend/tests/test_study_assist.py`.

**Interfaces:** `assist_lesson(fragment: HelpFragment, *, stage: str, course_id: str, locale: str, attempt: StudyAttempt | None, model: str) -> AssistResult`. Output includes `source`, `text`, `next_step` and validated `lesson_id/version/question_index`. `PROMPT_VERSION` is a fixed string recorded with metrics. `LOCAL_AI_STUDY_ROUTES` is a comma-separated allowlist of course IDs; the existing `LOCAL_AI_ENABLED` remains the master switch.

- [ ] **Step 1: Write failing tests** for system/data role separation, 2,000-character user-answer limit, no unrelated fields in prompts, and an injected “ignore the rules” instruction in lesson text and submitted answer.
- [ ] **Step 2: Add failing tests** for malformed JSON, wrong lesson/version/question, wrong stage, answer leakage in `hint`, timeout, busy model, disabled route, `kk`, stale cache after version change, and 21st hourly request; assert an explicitly marked authored fallback.
- [ ] **Step 3: Run** the targeted tests; expect red.
- [ ] **Step 4: Implement** structured Ollama request and checks. Use one global nonblocking lock, 45-second timeout, an in-memory 24-hour cache only for generic `explain` requests keyed by course/lesson/version/question/error code/locale/prompt version/model digest, and the existing rate-limit pattern. Never cache user text or personalized responses.
- [ ] **Step 5: Run** `PYTHONPATH=. .venv/bin/pytest tests/test_study_assist.py tests/test_local_ai.py -q`; expect green.
- [ ] **Step 6: Commit task files** with `feat: constrain local lesson assistance` if repository permissions allow.

### Task 3: Accessible lesson flow

**Files:** Create `frontend/src/components/StudyHelp.tsx`, `frontend/src/components/StudyHelp.module.css`; Modify `frontend/src/components/StudyLesson.tsx`, `frontend/src/studyTypes.ts`, `frontend/src/study.test.tsx`.

**Interfaces:** `StudyHelp` receives `{planId, lessonId, questionIndex, attemptId?, archived}` and uses Task 1's API. Its stages are local controls backed by the server's `next_stage_token`; `review` appears only after an owned saved attempt. `source='authored'` renders “Готовое объяснение из урока”.

- [ ] **Step 1: Write failing UI tests** for hint → next step → review, explicit user-answer sharing, loading/disabled/error states, an authored fallback label, keyboard operation, and screen-reader status.
- [ ] **Step 2: Run** `cd frontend && npm test -- --run src/study.test.tsx`; expect red.
- [ ] **Step 3: Implement** the component and mount it by each question; preserve existing `details` solution and saved-attempt behavior. Keep button dimensions stable while loading and let long Russian text wrap without horizontal scroll.
- [ ] **Step 4: Run** targeted tests and `npm run build`; expect green.
- [ ] **Step 5: Check rendered UI** at 360, 390, 768 and 1440 px plus 200% zoom, including long Russian and Kazakh strings. Record what was actually checked.
- [ ] **Step 6: Commit task files** with `feat: show staged study help` if repository permissions allow.

### Task 4: Feedback, metrics and editorial report

**Files:** Modify `backend/app/models.py`, `backend/app/routes/study_assist.py`; Create `backend/migrations/versions/c422_study_assist_feedback.py`; Test `backend/tests/test_study_assist.py`; Modify `frontend/src/components/StudyHelp.tsx`, `frontend/src/study.test.tsx`.

**Interfaces:** `POST /api/study/assist/feedback` accepts `{request_id, helped: bool}` once per owned request. `GET /api/study/assist/report` is an owner-only local development endpoint returning aggregate counts by course/version/lesson/question/stage, fallback rate and p50/p95 latency. Stored fields: owner ID, content IDs/version, stage, helped, source, prompt version, model digest, latency and timestamp; never free answers or generated text.

- [ ] **Step 1: Write failing tests** for own/foreign feedback, duplicate rating, absence of free text in DB/logs, report authorization, aggregates and percentile calculations.
- [ ] **Step 2: Run** backend targeted tests; expect red.
- [ ] **Step 3: Implement** migration, metadata-only rows, endpoints and small report view; add “Помогло / Не помогло” controls with an accessible saved state.
- [ ] **Step 4: Run** backend and frontend targeted tests; expect green.
- [ ] **Step 5: Commit task files** with `feat: measure lesson help quality` if repository permissions allow.

### Task 5: Pilot quality gate and next material

**Files:** Create `backend/tests/fixtures/study_assist_cases.json`, `backend/tests/test_study_assist_quality.py`, `docs/verification/2026-10-14-study-assist-pilot.md`; Modify `backend/app/routes/study_assist.py`, `frontend/src/components/StudyHelp.tsx` only for defects found by the pilot.

**Interfaces:** The existing onboarding preview/start endpoints remain the only plan-replacement path. A “Посмотреть следующий материал” action may link to the next compatible lesson or preview; no new write endpoint creates a plan.

- [ ] **Step 1: Author at least 40 fixed cases** across four routes, including prompt injection, answer leakage, bad ID/version, absent/expired content, model failure and Russian wording.
- [ ] **Step 2: Run deterministic tests** and a measured Ollama pilot on the user's machine; record exact model digest/quantization, RAM/disk observations, p50/p95, fallback rate and editorial spoiler verdicts. Targets: 100% valid shown references, 100% non-spoiler hints, p50 ≤ 10 s, p95 ≤ 30 s, fallback < 20% on valid requests after warmup.
- [ ] **Step 3: Keep each course flag off** until its fixed cases and resource targets pass. If a target fails, retain authored help and document the measured limitation.
- [ ] **Step 4: Add a read-only next-material link** based on existing completed/next lesson state and catalog validation; write a failing frontend test first, then verify it never saves a plan automatically.
- [ ] **Step 5: Run** full backend study/local-AI tests, frontend study tests, `npm run build`, coverage check, and browser widths. Record results and unresolved gaps in the pilot document.

## Completion gate

All four learning routes expose reviewed authored help at the chosen pilot lessons. AI is enabled only for routes meeting the fixed-case and local resource targets. A user can continue studying with Ollama stopped. No generated content is published to the library, and no plan changes without confirmation.
