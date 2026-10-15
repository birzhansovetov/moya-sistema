# Mobile App Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Recommended execution: one implementer in this session, followed by an independent final review.

**Goal:** Перестроить все разделы «Моей системы» как единое мобильное приложение, перенести программирование в профессию и выделить книги.

**Architecture:** Сохранить React Router, TanStack Query, серверные API и собственные UI-компоненты. Заменить накопленные глобальные оформления едиными токенами и стилями компонентов; специализированные экраны используют одну оболочку. Перенос адресов выполняется через совместимые маршруты без смены ID данных.

**Tech Stack:** React 19, TypeScript, Vite, React Router 7, TanStack Query 5, CSS Modules, Vitest, существующий FastAPI.

**Spec:** `docs/superpowers/specs/2026-10-16-mobile-app-redesign-design.md` — подтверждена пользователем.

## Global Constraints

- Фон #F5F7FA, поверхности #FFFFFF, текст #17212B, основной акцент #246BFD; знак «МС».
- Размеры текста 16–17/14/28–34 px; отступы 4/8/12/16/24/32; радиусы 12/16/24; кнопки минимум 48 px.
- Общие Button, Input, Select, Dialog, Card; hover/focus/disabled/loading/error.
- Все существующие данные, ID, авторизация, прогресс, помощник и функциональность сохраняются.
- Нет декоративных стрелок, фиктивного прогресса, неработающих медиакнопок, новых платных услуг.
- Все экраны: 360/390/768/1440 px и настоящий масштаб браузера 200%; русский и казахский Ә Ғ Қ Ң Ө Ұ Ү Һ І.
- Персональный платный ИИ остаётся отдельной задачей; никакие данные анкеты не начинают передаваться провайдеру в рамках редизайна.

## Review Focus

1. Старые ссылки с query/hash: открывается тот же план или книга — тест в задаче 3.
2. Чтение назад и изменение шрифта: счётчик прочитанного не растёт — задача 6.
3. Переход между разделами во время тренировки: черновик и таймер сохраняются — задача 5.
4. Нет сети или разрешения на медиа: понятная ошибка без ложной отметки выполнения — задачи 4, 5, 7.
5. Клавиатура, длинные подписи, 200%: главное действие доступно, нижняя панель не закрывает форму — задачи 2, 9, 10.

## Файловые границы

- `frontend/src/theme.css`, `design-system.css`, `main.tsx`: токены, базовые стили, порядок подключения. Старые глобальные `redesign.css`, `awwwards.css`, `mobile-app.css`, `app-unified.css`, `app-experience.css` выводятся из подключения после переноса используемых правил, а не дополняются ещё одним слоем переопределений.
- `components/ui.tsx`, `Shell.tsx`, `Shell.module.css`: примитивы и оболочка; новые `Brand.tsx`, `AppIcon.tsx` — знак и единые иконки.
- `navigation.ts`, `App.tsx`, `studyTypes.ts`, `assistantSections.ts`: адреса и представление сфер; новые `Profession.tsx`, `Profession.module.css` — каталог программирования.
- `mediaCatalog.ts`, `components/MediaPlayer.tsx`, `docs/media-sources.md`: проверенные медиа и проигрыватель.
- Существующие страницы и CSS Modules сохраняют запросы/мутации; визуальные изменения локализуются в них.
- `components/PersonalBookLibrary.tsx`, новый `ReaderView.tsx`, `ReaderView.module.css`: библиотека файлов и режим чтения.
- Сервер изменяется только если проверка выявит необходимость сохранения действительно новых настроек или счётчика; это оформляется отдельной миграцией и контрактным тестом до изменения клиента. Базовый перенос не требует миграции.

### Task 1: Подготовить проверяемую исходную версию

**Files:** spec, этот plan, `docs/verification/2026-10-16-mobile-redesign.md`.
**Interfaces:** исходные API и routes → зафиксированная база для сравнения.

- [ ] Проверить AGENTS.md, состояние основного и релизного checkout; по using-git-worktrees выбрать изолированный checkout, включающий последние опубликованные изменения и schema. Не переносить чужие несвязанные правки.
- [ ] Зафиксировать список маршрутов, действующих тестов, существующих медиа и состояния тестового аккаунта без секретов. Открыть текущие главные экраны на телефоне/компьютере.
- [ ] Запустить `npm --prefix frontend test -- --run` и `npm --prefix frontend run build`; записать фактическую базу и существующие предупреждения.

### Task 2: Токены, общие компоненты, логотип и оболочка

**Files:** theme.css, design-system.css, main.tsx, components/ui.tsx, ui.test.tsx, Shell.tsx, Shell.module.css, Shell.test.tsx; create Brand.tsx, AppIcon.tsx; public/favicon.svg; index.html.
**Interfaces:** `Brand({compact?: boolean})`; `AppIcon({name: 'today'|'sections'|'tasks'|'profile'|'calendar'|'books'|'profession'|'languages'|'health'|'finance'|'personal', size?: number})`. Существующие API примитивов сохраняются.

- [ ] Дополнить Shell.test.tsx: видимы «Мой день», «Разделы», «Задачи», «Профиль»; активный пункт имеет aria-current; календарь доступен. ui.test.tsx: loading сохраняет подпись, Dialog возвращает focus, error связан с полем. Запустить адресно и подтвердить новые проверки до реализации.
- [ ] Реализовать токены, бренд, иконки и оболочку: нижняя панель на телефоне, боковая на широком экране. Insets safe-area; main имеет достаточный нижний padding, форма не скрывается клавиатурой. Прозрачность только навигации; reduced-motion и непрозрачный fallback.
- [ ] Удалить подключения старых глобальных визуальных слоёв после переноса нужных правил. Проверить NotoSans-Variable.ttf и OFL, все казахские символы и метрики fallback.
- [ ] Запустить `npm --prefix frontend test -- --run src/components/ui.test.tsx src/components/Shell.test.tsx`, сборку; осмотреть оболочку на 390/1440 px. Commit только файлов задачи.

### Task 3: Книги, профессия и совместимость ссылок

**Files:** App.tsx, studyTypes.ts, assistantSections.ts, pages/Education.tsx, Sections.tsx, Onboarding.tsx, Today.tsx, components/TodayNext.tsx, DevelopmentDay.tsx; create navigation.ts, pages/Profession.tsx, Profession.module.css, navigation.test.tsx; modify backend/app/local_ai.py only if presentation mapping is shared with progress.
**Interfaces:** `studyPaths.java='/profession/java'`, `go='/profession/go'`, `'java-backend'='/profession/backend'`; `/books` → ReadingPage; `/profession` → ProfessionPage. `legacyDestination(pathname: string, search: string, hash: string): string | null` сохраняет query/hash.

- [ ] Создать navigation.test.tsx: `/education/go?plan=p&lesson=l#study-lesson` → `/profession/go?plan=p&lesson=l#study-lesson`; `/education/reading?book=b` → `/books?book=b`; `/profession?plan=p` → `/profession/backend?plan=p`; неизвестный путь не образует цикл.
- [ ] Выполнить тест, реализовать маршруты и каталог Java/Go/Backend, обновить ссылки, подписи анкеты/помощника/разделов. Сохранить course_id, исторические сферы и API. Представлять Java/Go как профессию, не изменять старые записи.
- [ ] Обновить существующие spheres/languages/education-catalog тесты по реальному контракту; проверить сохранённый план и чтение. Повторить navigation.test.tsx и сборку; commit.

### Task 4: Проверенные фото, обложки и медиапроигрыватель

**Files:** create mediaCatalog.ts, components/MediaPlayer.tsx, MediaPlayer.test.tsx, docs/media-sources.md; existing public/images, public/audio.
**Interfaces:** `MediaAsset={id:string;kind:'image'|'audio'|'video';src:string;title:string;sourceUrl:string;rights:string;poster?:string;transcript?:string;language?:string}`; `MediaPlayer({asset: MediaAsset})`.

- [ ] Инвентаризировать имеющиеся файлы; подобрать официальные разрешённые встраивания и изображения с правами. Записать источник/лицензию/привязку к материалу. Не скачивать чужие ролики и не приписывать их нашим авторам.
- [ ] Тест MediaPlayer: error показывает «Не удалось загрузить запись» и исходную ссылку; нет autoplay; видео preload='none'; аудио имеет расшифровку; неизвестный источник не встраивается.
- [ ] Реализовать проигрыватель и каталог только реально доступных активов. Обложки без файла получают собственный типографический fallback. Проверить воспроизведение, внешний отказ, резервирование размеров и отсутствие автозапуска.
- [ ] Запустить MediaPlayer.test.tsx, сборку; commit. Непокрытые медиа перечислить в отчёте, не объявлять каталог полным.

### Task 5: Спорт и здоровье

**Files:** pages/Sport.tsx, Sport.css, Health.tsx, Health.module.css; components/SportLibrary.tsx, SportLibrary.css; existing sport tests.
**Interfaces:** существующие workout draft/session mutations и таймер сохраняются; медиа по ID упражнения из Task 4.

- [ ] Расширить тесты спорта: подход/вес после смены упражнения и повторного открытия остаются; «Завершить тренировку» — единственный перевод в выполненное; ошибка видео не завершает упражнение.
- [ ] Перестроить обзор: фото, ближайшее занятие, основное действие, расписание, библиотека. Форму смены программы раскрывать отдельно; сохранить подтверждение замены.
- [ ] Перестроить рабочий экран занятия: одно упражнение, подходы/вес, таймер, техника, замена и явное состояние сохранения. При уходе таймер восстанавливается по deadline, а не по числу тиков.
- [ ] Запустить затронутые sport/frontend тесты; проверить реальный draft → resume → complete на тестовом аккаунте; commit.

### Task 6: Библиотека и чтение без отвлечений

**Files:** pages/Reading.tsx; components/BookSuggestions.tsx, BookSuggestions.css, PersonalBookLibrary.tsx, PersonalBookLibrary.module.css, ReadingLogForm.tsx; create ReaderView.tsx, ReaderView.module.css, reader-progress.test.ts; existing readingTypes.ts, reading.test.tsx; backend reading endpoints только при недостающем сохранении.
**Interfaces:** `ReaderView({title:string,children:ReactNode,onClose:()=>void})`; существующие ReaderState location/bookmarks и записи фактических страниц сохраняются.

- [ ] Тесты: resume открывает сохранённую позицию; назад/повторное открытие/смена шрифта не добавляют прочитанные страницы; запись бумажной страницы идемпотентна по существующему контракту; PDF показывает реальный номер, EPUB — процент/условный фрагмент без ложной печатной пагинации.
- [ ] Реализовать полки, крупные обложки, поиск и добавление своей книги. Выделить ReaderView; скрывать оболочку и помощника только на время чтения, восстанавливать их при закрытии.
- [ ] Реализовать светлую/тёмную/сепию, font-size, line-height, оглавление, закладки, сохранение настроек локально без содержимого книг. Счётчик основывается на существующих подтверждённых reading logs; позиция ридера не выдаётся за доказательство чтения.
- [ ] Выполнить reading и reader-progress тесты; открыть реальный EPUB/PDF из тестовой библиотеки, проверить выход/возврат и запись страниц; commit.

### Task 7: Языки и программирование

**Files:** pages/Languages.tsx, Languages.module.css, Study.tsx, Study.module.css, Profession.tsx; components/StudyLesson.tsx, StudyCards.tsx, EnglishVocabulary.tsx, StudyPlanForm.tsx; studyTypes.ts; existing language/study tests.
**Interfaces:** существующие Lesson/GrammarBlock/Word, API ответов и AssistantCheck; MediaPlayer из Task 4. Не менять смысл course_id/lesson_id.

- [ ] Добавить проверки: выбранный язык/уровень и предыдущие ответы сохраняются; открыть грамматику, слово и аудио с клавиатуры; неуспешное медиа не засчитывается как урок.
- [ ] Реализовать каталог языков, главы и следующий урок. В уроке — последовательные блоки объяснения/грамматики/примеров/аудирования/практики/словаря; длинные таблицы адаптируются внутри блока, не расширяют страницу.
- [ ] Увеличить карточки слов; произношение по разрешённой записи либо явно маркированному TTS, с честной недоступностью при отсутствии голоса. Добавить проверенные тематические видео в каталог и расшифровки аудио. Сохранять обозначение синтетических записей.
- [ ] Запустить language/study тесты и проверить уроки каждого из пяти языков, Java, Go, Backend на тестовом аккаунте; commit.

### Task 8: Мой день, финансы, дневник, питание

**Files:** pages/Today.tsx, Today.css, Sections.tsx, Sections.module.css, Finance.tsx, Finance.module.css, Personal.tsx, Journal.module.css, Nutrition.tsx, Nutrition.css; components/TodayNext.tsx, AnalyticsPanel.tsx, PersonalForm.tsx, CookingMode.tsx, ExpenseForm.tsx, IncomeForm.tsx.
**Interfaces:** существующие Query keys/mutations и структуры API; обновлённые пути Task 3 и медиа Task 4.

- [ ] Закрепить регрессионными тестами доход/расход/баланс, дневник настроение+активности, пересчёт рецепта на две порции и сохранение шага готовки. Проверить нулевые/отрицательные значения согласно существующему контракту, не менять расчёты ради оформления.
- [ ] Перестроить мой день вокруг следующего действия; аналитику раскрывать отдельно. Разделы — короткие плитки. Финансы — баланс/операции/анализ; дневник — настроение/активности/текст; питание — фото/порции/граммы/готовка. Калькулятор остаётся отдельным экраном.
- [ ] Проверить реальные сохранения на тестовом аккаунте и соответствующие Vitest; commit.

### Task 9: Анкета, авторизация, задачи, календарь и профиль

**Files:** pages/Auth.tsx, Auth.module.css, Onboarding.tsx, Onboarding.css, Tasks.tsx, Calendar.tsx, Profile.tsx, ProfileBackup.tsx; components/TaskDialog.tsx, TaskForm.tsx; existing auth/onboarding/task tests.
**Interfaces:** существующие авторизация/CSRF/email confirmation, survey version, preview/start, backup остаются без изменения контракта.

- [ ] Проверить существующими/дополненными тестами: ошибка подтверждения email с действием повторной регистрации, загрузка кнопки без потери подписи, повтор submit без дубликата, сохранение ответов при возврате на шаг анкеты.
- [ ] Применить систему ко всем формам и спискам. Длинные русские/казахские заголовки переносятся; ошибки связаны с полями; диалоги управляются клавиатурой. Календарь на телефоне имеет список выбранного дня.
- [ ] Запустить auth/onboarding/task тесты, сборку; проверить форму с открытой мобильной клавиатурой насколько позволяет браузерная среда, ограничение явно записать; commit.

### Task 10: Сквозная проверка, исправления и релиз

**Files:** docs/verification/2026-10-16-mobile-redesign.md, screenshots under docs/verification/assets/mobile-redesign; DESIGN.md и .impeccable/design.json по workflow Impeccable.
**Interfaces:** полный результат Tasks 1–9 → проверенный релиз и список подтверждений.

- [ ] Запустить все frontend тесты, TypeScript/build и backend тесты затронутых контрактов; проверить diff на секреты, непреднамеренные изменения и недостающие маршруты.
- [ ] Открыть каждый экран на 360/390/768/1440 px; проверить настоящий zoom 200%, длинный русский/казахский, focus, reduced-motion, ошибки сети, размеры изображений, горизонтальную прокрутку. Сохранить валидные снимки и матрицу результатов. Проверки выполняются через доступный browser tool, не подменяются одним HTTP 200.
- [ ] Одной пачкой исправить найденные проблемы; повторить затронутые проверки. Провести независимую итоговую проверку согласно Impeccable и verification-before-completion; обновить дизайн-документацию, зафиксировать оставшиеся ограничения.
- [ ] Опубликовать согласованный релиз на существующем Cloudflare Pages после проверки. Backend публиковать только при реальном изменении API; не трогать DATABASE_URL и реальные данные.
- [ ] Проверить публичные вход/регистрацию, оболочку и защищённые маршруты с тестовой сессией, legacy deep links, медиа, сохранение/возврат прогресса; удалить только созданные тестовые записи. В отчёте указать URL/commit и фактически проверенные экраны. Не объявлять медиапокрытие полным при пропусках.

## Исполнение и остановки

Рекомендуется выполнение одним исполнителем в текущем чате: оболочка, маршруты и разделы тесно связаны. Порядок 1→2→3→4→5→6→7→8→9→10. Каждый этап сохраняет работающее приложение. Доступ к тестовой сессии, внешним медиа или публикации запрашивается только при действительном отсутствии доступа. Отсутствие разрешённого ролика отражается как отсутствие медиа, а не обходится копированием закрытого контента.
