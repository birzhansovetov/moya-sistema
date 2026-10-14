# Pilot: local lesson assistance (14 October 2026)

## Fixed gate

- 48 deterministic cases across Java, Go, English and Java backend pass. Cases cover valid hints, injected instructions, mismatched lesson/version/question/stage, answer leakage, malformed output, unavailable model, explanations, missing and expired authored content.
- The reviewed library currently covers the first two lessons of each route. Remaining gaps are tracked in `2026-10-14-learning-help-coverage.md`; missing help is not shown as an available button.
- Feedback stores request metadata and a boolean vote. It does not store learner answer text or generated text.
- Final review tightened the data boundary: free text reaches Ollama only on the explicit post-attempt review action; generic cached explanations omit attempt-specific error details. The model's unverified `next_step` field is never exposed as navigation or a lesson recommendation.

## Measured local pilot

- Device: Apple M2, **8 GB RAM**; free disk space: **65 GiB**.
- Installed Ollama model: `qwen3:4b-instruct`, tag ID `0edcdef34593`, underlying blob SHA-256 `85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9`, 4.0B parameters, Q4_K_M, 2.5 GB on disk.
- Four real, anonymous first-lesson hint requests returned: Java authored fallback in 17.77 s; Go local AI in 3.62 s; English local AI in 3.55 s; Java backend local AI in 5.26 s. Median ~4.44 s; p95 by nearest-rank 17.77 s. Overall fallback 1/4 (25%). The three warm requests had 0 fallbacks, but this tiny sample is insufficient for an enablement decision.
- Editorial spot check: the three model hints did not expose the accepted answer verbatim. The validator rejected the Java output and served the reviewed hint; the exact rejected model output is deliberately not logged.

## Decision

Keep `LOCAL_AI_STUDY_ROUTES` empty by default. The device has 8 GB RAM, below the provisional 16 GB threshold, and the four-request pilot is too small to establish the required fallback rate (<20%) or stable p95 under load. The reviewed authored ladder remains available with Ollama stopped. AI is not enabled for sport, nutrition or Kazakh. A larger warm pilot and human review are required before enabling any route.

## Interface check

- Chrome rendered the Java lesson with two authored help controls, saved lesson context and a read-only next-material action. No automatic plan replacement occurred in the UI test.
- Clicked the first hint in the running local site: the reviewed hint, “Следующий шаг”, source label and feedback controls rendered successfully. The local preview database already reported Alembic revision `c422_study_assist_feedback` when checked read-only.
- Tested viewport widths 360, 390, 768 and 1440 px: `documentElement.scrollWidth` equalled `innerWidth` at all four widths. Visually inspected 360 px; the header, cards and buttons fit and text wrapped.
- A true 200% browser zoom could not be confirmed through the connected browser control; it remains unverified. Long Russian text was observed in the Java lesson. A dedicated Kazakh string layout check remains open.
- The complete regression run after the final privacy changes passed: **236 backend tests and 117 frontend tests**. The production frontend build passed. Alembic reached `c422_study_assist_feedback` on a clean disposable SQLite database; no production database was migrated.

## Next content work

The report in `2026-10-14-learning-help-coverage.md` identifies 357 unanswered quiz questions. Expand those with independently reviewed authored text in batches, starting where help usage and “Не помогло” counts are highest. Do not synthesize unreviewed solutions into the catalog.
