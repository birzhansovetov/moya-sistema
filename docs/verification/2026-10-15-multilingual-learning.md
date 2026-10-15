# Multilingual learning verification — 15 October 2026

## Scope

Four authored course catalogs were added: Kazakh, Korean, Turkish, and Spanish. Each has 48 lessons: 12 at each A1, A2, B1, and B2 level. Every lesson includes an explanation, grammar block, examples, vocabulary, reading, speaking prompt, practice, retry practice, and graded quiz. Existing English A2–B2 content and deep links remain available.

The onboarding survey selects one language and level. Starting a different language archives the previous active language plan while keeping lesson attempts and vocabulary history. The language selector explains this behavior.

## Checks

- Backend: `PYTHONPATH=. .../backend/.venv/bin/pytest -q` — 286 passed; focused `tests/test_study_content.py` rerun after the final content ordering assertion — 10 passed.
- Frontend: `npm test -- --run` — 132 passed.
- Frontend: `npm run build` — passed; Vite warned that the main JavaScript chunk exceeds 500 kB.
- Catalog audit: all 192 new lessons have grammar blocks and answer keys present in options. Correct answer positions vary within each course.
- Browser: language selector and Kazakh course checked at viewport widths 360, 390, 768, and 1440 px; no document-level horizontal overflow observed. Korean course and sport form inspected at narrow widths; Kazakh and Korean glyphs rendered. Actual 200% browser zoom could not be established through the available browser control, so it remains unverified.

## Editorial limits

The courses are platform-authored material with source attribution, but no native-speaker editorial review has been completed. The levels describe curriculum progression, not proof of CEFR proficiency. The lessons do not promise playable audio.

## Release status

This report describes local verification. It does not assert that the public Cloudflare site has been updated.
