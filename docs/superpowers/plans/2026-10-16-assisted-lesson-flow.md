# Помощь при прохождении занятий — план реализации пунктов 1–4

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Сохраняется выбранное пользователем самостоятельное исполнение в текущей сессии с независимым финальным ревью.

**Goal:** Связать объяснения помощника с текущим занятием, разрешённым следующим действием и отдельной проверкой понимания.

**Architecture:** Расширить существующие SectionAssistant/StudyHelp и общий облачный транспорт, сохранив контракты старых клиентов. Следующие действия и оценку дополнительных вопросов определяет приложение; Gemini получает только публичный материал, готовый пример, формат и тип подсказки. Личные результаты дополнительных проверок хранятся отдельно от основных занятий.

**Tech Stack:** Существующие React/TypeScript, общие UI-компоненты, FastAPI/Pydantic, SQLAlchemy/Alembic/PostgreSQL, JWT, pytest/Vitest, Gemini REST. Новые UI-библиотеки и платные сервисы не добавлять.

**Spec:** `docs/superpowers/specs/2026-10-16-assisted-lesson-flow-design.md` — подтверждён пользователем.

## Global Constraints

- Текущие планы, черновики, история и условия завершения сохраняются.
- Gemini не генерирует URL, команды или изменения состояния.
- Дополнительная проверка не завершает урок, тренировку или приготовление, не повышает учебный уровень и не создаёт фиктивную серию активности.
- Минимум один содержательный вопрос на главу; применимость к урокам задаётся явным списком. Проверка по главе подписывается названием главы.
- В интерфейсе нельзя обещать проверку там, где банк её не покрывает.
- Формат не отменяет лестницу учебных подсказок: намёк остаётся намёком даже «На примере» или «Пошагово».
- Ответы дополнительных проверок, plan ID, прогресс, параметры тела, финансовые записи и личные тексты не включаются во внешний payload и журналы провайдера.
- Служебное хранение дополнительных попыток — 30 дней; история основных занятий не зависит от них.
- Использовать общие Button, Dialog, Input/Select и токены, без декоративных стрелок.
- Проверить ширины 360, 390, 768, 1440 px и настоящий масштаб 200%.

## Review Focus

1. Двойной клик/повтор после сетевого сбоя: одна дополнительная попытка; другой вариант под тем же ключом отвергается — Task 3.
2. Изменение содержимого той же версии и отзыв после выдачи вопроса: старый токен не принимает ответ — Task 1/3.
3. Помощник поверх CookingMode: Escape/Tab закрывают только верхнюю панель, ингредиенты и текущий шаг не теряются — Task 5.
4. Два ответа по разным форматам/этапам приходят в обратном порядке: отображается только последний актуальный — Task 2/4.
5. Дополнительная проверка для архивного/чужого плана: нет записи в чужую или архивную историю; обычное чтение своего архива остаётся доступным — Task 3/5.

---

### Task 1: Реестр действий, готовых примеров и дополнительных вопросов

**Files:** Create `backend/app/assistant_learning.py`, `backend/app/content/assistant-learning-v1.json`, `backend/tests/test_assistant_learning_content.py`, `docs/verification/2026-10-16-assistant-learning-coverage.json`. Modify `backend/app/assistant_content.py` to expose explicitly allowed prepared examples. Read existing study catalogs, exercises, recipes, guides, book cards and revocation rules.

**Interfaces:** Produce `ExplainFormat = Literal['default','simple','example','steps','brief']`; default preserves legacy behavior. Produce `NextAction` with `id`, `label`, `kind: route|local`, and either allowlisted `to` or enumerated `handler`; no arbitrary URL or executable field. Produce immutable `LearningCheck` with ID/version, explicit material refs, chapter title if applicable, prompt, `{id,label}` options, correct_option_id, explanation, repeat/continue action IDs and review/source metadata. Functions: `checks_for_material(ref, *, db, today) -> tuple[LearningCheck,...]`, `prepared_example(ref, *, db, today) -> str|None`, `learning_coverage() -> dict`, `check_digest(check) -> str`.

- [ ] Write failing tests `test_all_curriculum_chapters_have_explicit_checks`, `test_no_orphan_or_duplicate_checks`, `test_checks_do_not_duplicate_main_quiz_prompts`, `test_no_solution_in_public_question_projection`, `test_action_registry_has_only_real_routes_and_handlers`, `test_revoked_parent_and_material_excluded`, `test_example_is_authored_and_contains_no_quiz_solution_fields`. All Java/Go/profession and five language courses are enumerated; missing `chapter` means a lesson-sized group with its lesson title, not a fabricated chapter.
- [ ] Run `cd backend && .venv/bin/python -m pytest tests/test_assistant_learning_content.py -q`; observe failures for missing behavior.
- [ ] Implement the typed registry and authored bank. Each chapter has a relevant additional question with explicit compatible lesson IDs; publish mapped/total lessons per course as well as chapter coverage. Do not claim coverage of an unmapped lesson. Sport/recipe/guide checks cover explicitly authored concepts, not universal unrelated fallback questions. For subjective diary/reading reflection use a separate ungraded prompt with no answer submission. No questions about a user's health, income or diary content.
- [ ] Resolve examples from course worked examples, existing guide examples, authored bank examples or canonical recipe steps. Never copy a user's code, book upload, quiz solution or private record. If no prepared example exists, expose `example_available=false`. Canonical check SHA-256 includes question, options, correct ID, explanation, mappings and version, and changes when content changes without a version bump.
- [ ] Run content tests, generate the coverage JSON, manually inspect every new bank item against its source and intended lesson/step. Require zero uncovered curriculum chapters and zero orphan checks; report other unmapped materials explicitly. Commit: `feat: add reviewed assistant learning actions and checks`.

### Task 2: Четыре формата в общем и учебном объяснении

**Files:** Modify `backend/app/cloud_ai.py`, `backend/app/routes/assistant.py`, `backend/app/routes/study_assist.py`, `backend/tests/test_cloud_ai.py`, `backend/tests/test_study_assist.py`, `backend/tests/test_assistant.py`. Create `backend/tests/test_assistant_formats.py`.

**Interfaces:** Extend explanation request schemas with `format: ExplainFormat = 'default'` and optional public `step_id` validated against the chosen material. Both response schemas add `format`, `example_available`, `next_actions`, and optional `check_available` without removing existing fields. `explain_public_fragment(..., format='default', prepared_example=None)` and `explain_catalog_fragment(..., format='default', prepared_example=None)` remain backwards compatible. Private study activity context is resolved separately on the server and never becomes a transport argument.

- [ ] Add failing tests `test_formats_have_distinct_cache_entries`, `test_legacy_requests_preserve_behavior`, `test_hint_format_cannot_skip_stage_or_reveal_exact_answer`, `test_example_missing_returns_honest_authored_fallback`, `test_step_is_public_and_in_range`, `test_format_payload_has_no_private_context`, `test_safe_newlines_allowed_but_control_characters_links_html_rejected`.
- [ ] Run focused cloud/study/assistant tests and observe the new failures.
- [ ] Implement fixed format instructions and bump the cloud prompt version. Cache identity includes format, step, source digest and prepared-example digest. Preserve the 20/hour shared account cloud budget, global transport limits, timeout and fallback. Allow newline/tab only as needed for plain-text lists, reject other controls and render as text, never HTML. «На примере» without a ready example returns original authored text with a clear unavailable-example notice; it does not ask Gemini to invent an example. «Коротко» retains source safety conditions; sport/nutrition still display reference-only notice and source access.
- [ ] Ensure next_actions are constructed from Task 1's registry after inference, independent of model output. Old `links` remain compatible. StudyHelp keeps owned plan/attempt validation and stage tokens; format changes cannot obtain a review token or bypass a saved attempt.
- [ ] Run new and existing focused tests; confirm each upstream payload fixture excludes answers, progress, plan IDs and private parameters. Commit: `feat: support safe explanation formats and next actions`.

### Task 3: Детерминированная дополнительная проверка и хранение

**Files:** Create `backend/app/assistant_checks.py`, `backend/tests/test_assistant_checks.py`, `backend/tests/test_assistant_check_retention.py`, Alembic-generated `backend/migrations/versions/<actual_revision>_assistant_checks.py`. Modify `backend/app/routes/assistant.py`, `backend/app/models.py`, `backend/app/cleanup.py`. The real revision is generated by Alembic at execution, not invented in the plan.

**Interfaces:** `POST /api/assistant/checks/issue` accepts `section`, `material:{kind,id,version}`, optional public `step_id`, optional owned study context `{plan_id,lesson_id}`. It returns `available`, public question `{id,version,prompt,options,chapter_title}`, and a signed token, or an explicit unavailable reason. No correct ID/explanation is returned yet. `POST /api/assistant/checks/answer` accepts only `{token,option_id}` and returns `{attempt_id,correct,explanation,next_actions,retry_available}`. New `AssistantCheckAttempt`: UUID, user FK cascade, issue_id unique per user, check ID/version/digest, public material identity, selected option ID, correctness, optional owned activity identifiers, created_at. No free text and no model invocation.

- [ ] Write failing tests for correct/wrong/unknown option, no answer leakage on issue, CSRF/auth, foreign/mismatched plan, read-only archived plan, revoked course/material/check, expired/tampered token, and content change under the same version. Issue token uses purpose `assistant-check`, owner, random issue_id, check/material identities, context fingerprint, current digest and **30-minute expiry**; it contains no correct option or private answer.
- [ ] Add failing tests `test_same_issue_same_answer_replays_one_result`, `test_same_issue_changed_answer_is_conflict`, `test_parallel_submissions_create_one_attempt`, `test_check_does_not_touch_main_progress_or_streak`, `test_retention_preserves_main_history`. Compare StudyAttempt/StudyReview/SportWorkout/Task/history counts and activity-series state before and after checks. Fresh retry requires a fresh issue token. At exactly 30 days retain; older records delete; user deletion cascades additional attempts.
- [ ] Run the new tests; observe failures. Implement server-only grading using Task 1's bank, strict schemas with extra fields forbidden, ownership locking and a unique `(user_id, issue_id)` database constraint. Replay after a client timeout returns the stored result for the same choice while the token is valid; conflicting choice returns 409. Expired/revoked/stale tokens reject before grading; historical records are not used to bypass current withdrawal.
- [ ] Generate/apply the additive migration on an isolated test schema, enable RLS and revoke anon/authenticated access. Include additional attempts in `cleanup_assistant`; update the existing daily pg_cron retention command at release. Do not add mini-checks to calendar activity or primary lesson results. Limit issue/answer requests with separate short event names fitting VARCHAR(24), e.g. 120/hour/account; issue/answer never consume Gemini quota.
- [ ] Run focused tests and PostgreSQL concurrency/migration/retention checks using disposable records only. Commit: `feat: add owned idempotent comprehension checks`.

### Task 4: Панель форматов, действий и мини-проверки

**Files:** Modify `frontend/src/components/SectionAssistant.tsx`, `SectionAssistant.module.css`, `SectionAssistant.test.tsx`, `StudyHelp.tsx`, `StudyHelp.cloud.test.tsx`. Create `frontend/src/components/AssistantCheck.tsx`, `AssistantCheck.test.tsx`, `frontend/src/assistantLearningTypes.ts`.

**Interfaces:** Shared TS types mirror Task 1–3. Provider context exposes `openAssistant({section,material,stepId?,contextKey?,studyContext?,handlers?})`, `isOpen`, and `closeAssistant()`. `handlers` maps enumerated local action IDs to callbacks; functions never serialize to API. `contextKey` is a local invalidation identity, never sent to Gemini. `AssistantCheck` consumes a public material and optional owned study context, and emits a registry-defined next action after server grading.

- [ ] Write failing tests: all four format buttons have selected/disabled/loading states; clicking formats cannot mix old text/new source/old next actions; late replies after route/query/hash/material/step/session changes are ignored. Missing example and unavailable check are labelled honestly. Test a deferred response arriving after a newer format result.
- [ ] Add failing tests: no correct answer before pressing «Проверить»; selection sends option ID only; network retry reuses the issued token; «Попробовать ещё» obtains a new token; correct/wrong responses show continue/repeat action; no completion API is called by these controls. Routes outside the allowlist and unknown local handlers are never executed; safe fallback is «Вернуться к материалу».
- [ ] Run frontend tests and observe failures. Implement compact format buttons, one primary next action plus optional repeat action, and the mini-check within the existing Dialog. Keep question/answer state scoped to identity; use generation cancellation on close/context changes. Clear an old response on a new format request rather than displaying mismatched text. Preserve focus restoration, Escape, live regions, stable loading dimensions and text wrapping.
- [ ] Extend StudyHelp format controls with the same shared types/UI components while preserving the hint ladder. Do not move its question/attempt fields into SectionAssistant's public explanation transport. Subjective reflection shows an authored prompt without textarea, submission or correctness label.
- [ ] Run focused tests, `npm run typecheck`, existing helper/UI tests. Commit: `feat: add guided assistant controls and comprehension panel`.

### Task 5: Встраивание в занятия и разрешённые следующие действия

**Files:** Modify `frontend/src/components/StudyLesson.tsx`, `CookingMode.tsx`, `frontend/src/pages/Study.tsx`, `Sport.tsx`, `Nutrition.tsx`, `frontend/src/components/Guides.tsx`, `BookSuggestions.tsx`. Create `frontend/src/components/AssistedActivity.test.tsx`. Modify `backend/app/assistant_learning.py` and focused API tests for server-side owned recommendations.

**Interfaces:** Study local handlers open example/practice/check by changing the existing lesson step and scrolling/focusing its existing section. Sport handlers return to current technique/sets/timer; existing `exerciseIndex`, `restUntil`, actual results and draft store remain the sole state owners. Cooking handlers show ingredients or advance the existing `step`, keeping portions/checked ingredients. Book handler opens the existing public reader; route actions for other sections open existing screens only.

- [ ] Write failing integration tests: explanation→practice→check in Java, Go/profession and each of five languages; returned actions cannot select another user's plan; archived context stays readable and cannot record a check against the archive. After a normal saved main attempt, next-lesson recommendation uses existing server progress and never marks the new lesson completed.
- [ ] Write failing timer/draft tests: open/close helper while rest timer runs; completed sets and remaining time persist; no workout completion request occurs. Cooking test: checked ingredients, portions and current step survive helper close, format changes and mini-check. «Следующий шаг» uses the existing step callback and cannot advance past the last step automatically.
- [ ] Write failing nested-modal keyboard test: CookingMode's document-level Escape/Tab handler does not intercept the top helper; Escape closes only helper and restores focus inside cooking. While helper is open, background cooking is not presented as a second active modal. Mark the cooking handler inactive via provider `isOpen`/defaultPrevented/target checks; keep cooking mounted.
- [ ] Run integration tests and observe failures. Wire controls beside current rule/question/active exercise/cooking step. Create local context identity from actual lesson/step/portion changes without serializing private values. Resolve server recommendations from owned plans; restrict server responses to registry IDs/allowlisted routes. Unsupported context uses return-to-material, not a fabricated personalized action.
- [ ] Wire general guide/book/finance/diary/calendar/tasks/profile/auth actions to real existing screens or active callbacks. No free text/record creation, no automatic budget or health changes. Cooking explanations explicitly describe source portions; changed quantities remain displayed by CookingMode, not recomputed by model.
- [ ] Run integration and existing study/sport/cooking/reading tests, then commit: `feat: guide users through existing activity steps`.

### Task 6: Ревью, проверка и публикация

**Files:** Create `docs/verification/2026-10-16-assisted-lesson-flow.md` and screenshots under `docs/verification/assets/assisted-lesson-flow/`. Update the Task 1 coverage report and actual deployment/retention configuration documentation.

- [ ] Run full backend tests, frontend tests and TypeScript/Vite build. Review exact privacy fixtures, coverage report and bank contents. Obtain one independent final code review; reproduce consequential findings with failing tests, fix and rerun the whole affected suite.
- [ ] Browser-check each format, next action, correct/wrong answer, unavailable question/example, retry and stale context. Use an isolated test account with an active lesson, workout draft/timer and cooking state. Check all five languages, Java/Go/profession, sport, recipe and general-section route actions. Check 360/390/768/1440 px and real 200% zoom; long Russian/Kazakh captions, keyboard, nested modal and bottom navigation. Report exact surfaces, not blanket claims about every possible state.
- [ ] Reuse the existing isolated release checkout; verify current origin/main and preserve unrelated primary changes. Apply the tested additive migration before new code writes attempts; update daily retention to cover both helper metadata and additional attempts. Publish backend, verify health/old helper compatibility, then frontend to existing `moya-sistema.pages.dev`. No billing or credential changes.
- [ ] On the primary public host verify a real `source=cloud_ai` response in a selected format, an actual supported next-step transition, and correct/wrong mini-check cycle. Confirm main progress/streak unchanged until normal completion; public auth helper remains authored. Verify cleanup scheduling, remove only disposable QA records, restore zoom/viewport, save screenshots and report.
- [ ] Rollback with previous frontend/backend deployment; leave additive attempt table intact. Existing cloud switches retain authored assistance. Do not drop personal records as part of application rollback. Commit verification documentation and synchronize only conflict-free targeted source files to the primary workspace.

## Self-review

Spec mapping: next steps (Tasks 1/4/5), all formats and safe examples (1/2/4), embedded context/draft preservation (4/5), deterministic checks and coverage (1/3/4), privacy/limits/storage (2/3), accessibility/real publication (5/6). Each Review Focus has a named failing test or exact browser check. Shared formats/action/check fields are defined before consumption. No automatic completion, arbitrary model links, personal cloud analysis or fabricated question coverage is introduced.
