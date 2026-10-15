# Помощник во всех разделах — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Исполнение в текущей сессии рекомендуется; метод должен подтвердить пользователь.

**Goal:** Добавить доступную на всех страницах помощь по интерфейсу и публичным материалам без передачи личных данных бесплатному Gemini.

**Architecture:** Один реестр готовых тем и адаптеров публичного каталога, один серверный API и одна панель React. Облачный транспорт обобщается с сохранением StudyHelp и его лестницы подсказок. Личные данные не участвуют в разрешении темы или построении внешнего payload.

**Tech Stack:** Существующие FastAPI, SQLAlchemy/Alembic, PostgreSQL, React 19, React Router, TanStack Query, Vitest и общие UI-компоненты. Новые UI-библиотеки не устанавливать.

**Spec:** `docs/superpowers/specs/2026-10-15-section-assistant-design.md` — подтверждён пользователем.

## Global Constraints

- Существующий StudyHelp с последовательностью подсказок и проверкой принадлежности урока сохраняется.
- Внешний payload содержит только проверенный публичный фрагмент, тип объяснения и язык.
- Не допускаются свободный текст, поля личных записей или присланное клиентом содержимое. Неизвестные поля отвергаются.
- Публичная помощь авторизации возвращает готовую справку без вызова Gemini.
- Общая и учебная помощь делят облачный лимит аккаунта, глобальный лимит транспорта, блокировку, таймаут и кэш; новые имена событий должны помещаться в VARCHAR(24).
- Сохранить `CLOUD_AI_ENABLED` как общий выключатель. Добавить список разрешённых сфер для поэтапного включения.
- Не хранить текст личного запроса или ответа. Срок хранения служебных записей — 30 дней с очисткой существующей задачей.
- Использовать существующие Button, Dialog, Card и дизайн-токены. Без декоративных стрелок.
- На компьютере боковой Dialog, на телефоне Dialog на весь доступный экран.
- Проверить ширины 360, 390, 768, 1440 px и настоящий масштаб 200%.
- Помощник не меняет планы, записи, настройки или результаты занятий самостоятельно.

## Review Focus

1. Смена страницы во время ответа: старый результат не появляется в новом разделе — тест Task 5.
2. Совпадающие ID разных каталогов и отозванный материал после кэширования: ключ включает тип/версию, отзыв проверяется до кэша — Task 1/2.
3. Обход квоты между учебной и общей помощью, включая параллельные обращения: единый аккаунтный лимит и ограничение конкурентности — Task 2/3.
4. Повторная или чужая оценка и очистка на точной границе 30 дней: данные защищены, записи пользователя не удаляются — Task 4.
5. Узкий экран с клавиатурой, длинными подписями и открытым Dialog: закрытие доступно, фокус возвращается, горизонтальной прокрутки нет — Task 5/7.

---

### Task 1: Реестр тем и публичных материалов

**Files:** Create `backend/app/assistant_content.py`, `backend/app/content/assistant-topics-v1.json`, `backend/tests/test_assistant_content.py`. Read `content_review.py`, `study.py`, `study_help.py`, `routes/library.py`, `content/*.json`.

**Interfaces:** Produce immutable `PublicExplanation(kind: str, id: str, version: str, title: str, text: str)` and `AssistantTopic(id: str, section: str, label: str, fallback: str, links: tuple[dict, ...])`. Functions `topics_for_section(section: str) -> tuple[AssistantTopic, ...]` and `resolve_material(kind: str, id: str, version: str, *, db: Session, today: date) -> PublicExplanation`. Error: unknown/revoked ID → 404; changed version → 409.

- [ ] Write failing parameterized tests: every section has 3–5 nonempty topics; codes are `today, sections, education, java, go, profession, languages, english, kazakh, korean, turkish, spanish, health, sport, nutrition, calories, finance, reading, personal, tasks, calendar, profile, onboarding, auth`. Every internal link resolves to an existing route; no duplicate `(section,id)`.
- [ ] Write failing material tests for guide/exercise/recipe/book/lesson across all five languages. Assert quiz, answers, personal-book content and unsupported kinds cannot enter `PublicExplanation.text`; duplicate IDs across kinds remain distinct; version mismatch and revocation reject access.
- [ ] Run `cd backend && .venv/bin/pytest tests/test_assistant_content.py -q`; confirm failure comes from missing new behavior.
- [ ] Implement explicit adapters selecting allowed fields only. Lessons expose theory/examples/vocabulary, never quiz/check/solutions. Books expose public card metadata only. Check current review/revocation rules before use. For missing theory provide section topic rather than quiz text. Include checked date and version in static help; write fallback answers describing only actual functions.
- [ ] Run the same test file; all cases pass. Commit only this task's files: `feat: add public assistant topic registry`.

### Task 2: Общий транспорт с неизменной учебной помощью

**Files:** Modify `backend/app/cloud_ai.py`, `backend/app/routes/study_assist.py`, `backend/app/config.py`, `backend/.env.example`, `backend/tests/test_cloud_ai.py`, `backend/tests/test_study_assist.py`. Create `backend/app/assistant_limits.py`, `backend/tests/test_assistant_limits.py`.

**Interfaces:** Consume `PublicExplanation`; produce `explain_public_fragment(fragment: PublicExplanation, *, fallback: str, api_key: str, model: str) -> dict` with `{source: authored|cloud_ai, text: str}`. Keep `explain_catalog_fragment(HelpFragment, stage, api_key, model)` compatible. Add `Settings.cloud_ai_sections: str` from `CLOUD_AI_SECTIONS`, default empty (general cloud help disabled until configured). Produce `reserve_cloud_call(db: Session, user: User, request: Request) -> None` for both authenticated routes.

- [ ] Add failing tests: public payload has only authored text/stage/language; injected instructions ignored by fixed system role; malformed JSON/links/oversized response/402/429/timeout use fallback. Assert review never reaches cloud and existing hint answer filter still runs.
- [ ] Add failing tests: shared cache/lock/global budget across wrappers; same ID in different kinds never shares output; cached material is revalidated upstream by resolver; cloud flag/section list honored; account events fit `AuthRateEvent.action` column. Mixed study/general requests exhaust one 20/hour account budget, not 40. Concurrent requests cannot bypass available reservation in PostgreSQL.
- [ ] Run `cd backend && .venv/bin/pytest tests/test_cloud_ai.py tests/test_study_assist.py tests/test_assistant_limits.py -q`; confirm new cases fail.
- [ ] Extract common transport/cache without duplicating global state. Preserve 12-second timeout, three uncached calls/min/process, single active provider call, 60-second error pause, 256-entry/24-hour cache and 600-character answer cap. Keep exact model/key behavior. Serialize account reservation using database-supported per-account locking in PostgreSQL; use equivalent test transaction behavior for SQLite. Maintain source/IP hourly limit 1000. A quota denial returns authored help without provider call; unauthorized requests still reject normally.
- [ ] Run focused tests and a real PostgreSQL integration test using isolated test records; inspect no sensitive values in captured logs. Commit: `refactor: share bounded cloud explanation transport`.

### Task 3: Общий API помощника

**Files:** Create `backend/app/routes/assistant.py`, `backend/tests/test_assistant.py`. Modify `backend/app/main.py`.

**Interfaces:** `GET /api/assistant/topics?section=...` → `{section,topics:[{id,label}],materials:[{kind,id,version,title}]}`. `POST /api/assistant/explain` accepts `section,topic_id,material:{kind,id,version}|null` only; response `{request_id: str|null,source,text,material:{kind,id,version,title}|null,links:[{label,to}],notice: str|null}`. Internal links come from registry, never from model. Material selectors return complete compatible list for that section; client filters title locally. Public `auth` exposes topics/fallback only, no material catalog, no request record.

- [ ] Write failing tests: unauthenticated non-auth section → 401, missing CSRF on authenticated POST → 403, extra field `answer_text` → 422, invalid section/topic/material pairing → 404, stale version → 409, revoked material rejected even after previous successful/cached reply. Assert choosing `auth` on any session never invokes cloud or creates a record.
- [ ] Write failing tests: every declared section returns a topic and authored response with flag off; permitted sections return `cloud_ai` through fake transport; non-permitted sections use fallback; no personal model/query required to build material text; links stay within allowlist.
- [ ] Run `cd backend && .venv/bin/pytest tests/test_assistant.py -q` and confirm failures.
- [ ] Implement strict Pydantic models (`extra='forbid'`), auth/CSRF dependency split, current content resolution and shared budget. For sport/nutrition/calories/finance set short authored notice about reference-only help. Do not accept course quiz/question/attempt IDs here; StudyHelp owns those operations.
- [ ] Run API, cloud and existing study tests; all pass. Commit: `feat: expose section assistant API`.

### Task 4: Оценки, отчёт и очистка

**Files:** Modify `backend/app/models.py`, `backend/app/cleanup.py`, `backend/app/routes/assistant.py`, `backend/tests/test_cleanup.py`. Create `backend/migrations/versions/<generated_revision>_section_assistant.py` with actual Alembic-generated revision, `backend/tests/test_assistant_feedback.py`.

**Interfaces:** New `AssistantRequest` table with UUID id, user FK cascade, section/topic_id, nullable public material kind/id/version, source, prompt_version, model name, latency_ms, nullable helped, created_at. No text columns. `POST /api/assistant/feedback {request_id,helped}` → `{saved:true}`. Development/test-only `GET /api/assistant/report` returns aggregates by public topic/material, totals/source counts/helped counts/p50/p95; production 404. `cleanup_assistant(db: Session) -> int`; CLI area `assistant` alongside existing `onboarding`.

- [ ] Write failing tests: owner assessment saved once; repeated → 409, other user → 404, anonymous → 401. General responses have owned request IDs; public auth responses have null ID. No response text or personal fields persisted.
- [ ] Write failing retention tests: older than 30 days deleted, exact threshold/newer retained; user, plans, progress, diary and financial rows unchanged. Cleanup failure is logged without request content. Test report environment gate.
- [ ] Run `cd backend && .venv/bin/pytest tests/test_assistant_feedback.py tests/test_cleanup.py -q`; confirm failures.
- [ ] Implement model, migration, request metadata and cleanup. Preserve existing cleanup CLI behavior. Document daily cleanup invocation and wire it into actual hosting scheduler if available; if no scheduled job exists, report that deployment gap explicitly rather than claiming automatic retention.
- [ ] Verify migration upgrade on isolated PostgreSQL and downgrade on disposable schema; run focused tests. Commit: `feat: record assistant feedback with bounded retention`.

### Task 5: Одна адаптивная панель

**Files:** Create `frontend/src/components/SectionAssistant.tsx`, `SectionAssistant.module.css`, `SectionAssistant.test.tsx`, `frontend/src/assistantSections.ts`, `assistantSections.test.ts`. Modify `frontend/src/components/Shell.tsx`, `frontend/src/pages/Onboarding.tsx`, `frontend/src/pages/Auth.tsx`. Reuse `components/ui.tsx`.

**Interfaces:** `sectionForPath(pathname: string) -> SectionCode`; explicit exact route map plus `/languages/:courseId`. `SectionAssistant({section: SectionCode, initialMaterial?: {kind,id,version}, inline?: boolean})`. Shared context exposes `openAssistant({section,material?})`; provider owns one dialog, mounted once at app scope. Place trigger inside Shell/Onboarding/Auth, do not duplicate dialogs.

- [ ] Write failing tests: all App routes map to known sections, query/hash not sent; anonymous auth help uses only auth topics. Pane initially has 3–5 questions and no chat input. UI uses Button/Dialog/Card; source labels, notice, feedback and retries render.
- [ ] Write failing lifecycle test: deferred response for sport resolves after navigating finance; sport text remains absent. Closing/reopening and session logout clear response/material state; late requests cannot restore old content. Failed topic load leaves close/retry usable; revoked/stale selected material prompts refreshed selection.
- [ ] Write keyboard test: open, focused close control, Escape, focus restored to trigger; loading prevents duplicate requests while preserving button label/size; output uses live region. Feedback failures allow retry without losing answer.
- [ ] Run `cd frontend && npm test -- src/components/SectionAssistant.test.tsx src/assistantSections.test.ts`; confirm failures.
- [ ] Implement provider and panel using existing UI tokens, Grid/Flex/gap. No fixed content height, no decorative arrows. Mobile dialog uses dynamic viewport and safe area; bounded internal scrolling. Reset/invalidate async requests by section/session generation; cache key includes user/session for private endpoint results, never reuse previous user's request ID.
- [ ] Run focused frontend tests and `npm run typecheck`; all pass. Commit: `feat: add accessible section assistant panel`.

### Task 6: Объяснения конкретных материалов

**Files:** Modify `frontend/src/components/Guides.tsx`, `frontend/src/pages/Sport.tsx`, `Nutrition.tsx`, `Study.tsx`, `Reading.tsx`, `Languages.tsx`, `Education.tsx`. Create `frontend/src/components/AssistantMaterialButton.tsx`, `AssistantMaterialButton.test.tsx`.

**Interfaces:** `AssistantMaterialButton({section,material:{kind,id,version}})` consumes provider's `openAssistant`. It carries IDs only, never text, DOM content, recipe quantities, selected personal plan, body measurements or book upload IDs.

- [ ] Write failing tests for guide/exercise/recipe/book/lesson triggers; capture outbound JSON and assert only contract fields. Check all five language theory screens. Quiz state/answers remain handled only by StudyHelp; personal book has general reader help instead of material transmission.
- [ ] Run `cd frontend && npm test -- src/components/AssistantMaterialButton.test.tsx`; confirm failures.
- [ ] Insert compact «Объяснить» actions beside supported public materials; default panel offers searchable material list when no material was chosen. For finance/calories/diary/dashboard use section help without reading records. Do not add a second floating button or obscure workout controls/mobile navigation.
- [ ] Run new tests plus existing StudyHelp, sport, nutrition and reading tests. Commit: `feat: connect catalog materials to assistant`.

### Task 7: Полная проверка и публикация

**Files:** Create `docs/verification/2026-10-15-section-assistant.md`, screenshot assets under `docs/verification/assets/section-assistant/`. Update `.env.example`/deployment instructions with actual configured sections and cleanup scheduling evidence.

- [ ] Run full backend `.venv/bin/pytest -q`, frontend `npm test` and `npm run build`; record current counts and failures. Confirm no secrets in diff or client bundle. Obtain final independent code review under executing-plans workflow and fix consequential findings.
- [ ] Browser-check every declared section and all five languages with a disposable account. Check 360/390/768/1440 px and real browser zoom 200% across unique panel layouts (topic list, material selection, answer, error). Test long Russian/Kazakh labels, focus, Escape, horizontal overflow, keyboard/safe-area behavior and workout controls. Save screenshots and list exact tested combinations; do not present viewport resize as real zoom.
- [ ] Test real provider call locally using public material only. Apply migration before code that writes the new table. Deploy backend with general sections initially empty; verify health, auth and existing StudyHelp. Deploy frontend; enable reviewed section allowlist in Render while retaining existing `CLOUD_AI_ENABLED=true`. No key rotation/billing changes.
- [ ] Publish to existing `moya-sistema.pages.dev`, not a new project. Use verified release checkout/current production branch; preserve unrelated dirty workspace changes. Confirm Render/Cloudflare success and public assets, authenticated assistant API and actual UI label `Объяснение ИИ · Gemini` with `source=cloud_ai`. Auth page remains authored without external request. One actual provider reply plus per-section adapter/API tests prove different layers; report these separately.
- [ ] Verify scheduled retention task or clearly document hosting blocker. Remove only disposable QA records, reset viewport/zoom, close temporary tabs. Commit verification report: `docs: verify section assistant release`.
- [ ] Rollback: clear `CLOUD_AI_SECTIONS` to retain authored help immediately; global cloud flag disables study cloud too. For code regression redeploy previous frontend/backend. Leave additive table intact during application rollback; never drop user data to roll back UI.

## Self-review

Spec coverage: registry/content/privacy (Tasks 1–3); common limits and flags (2–3); feedback and 30-day retention (4); every route and mobile/accessibility (5); selected material actions (6); actual publication, safe rollback and exact verification claims (7). Five Review Focus conditions have named tests/checks in owning tasks. Shared types and response fields are defined before consumption. No new free chat, personal analysis, autonomous plan changes or paid API assumptions.
