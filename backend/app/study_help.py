"""Reviewed, immutable help for individual quiz questions."""

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from importlib.resources import files

from sqlalchemy.orm import Session

from app.content_review import is_revoked, reviewed_variant
from app.study import course, normalize_answer


@dataclass(frozen=True)
class HelpFragment:
    course_id: str
    version: str
    lesson_id: str
    question_index: int
    hint: str
    next_step: str
    explanation: str


def help_id(item: dict) -> str:
    return f"{item['course_id']}:{item['course_version']}:{item['lesson_id']}:{item['question_index']}"


def validate_help_catalog(items: list[dict]) -> None:
    seen: set[str] = set()
    for item in items:
        key = help_id(item)
        if key in seen:
            raise ValueError(f"duplicate help: {key}")
        seen.add(key)
        lesson = next((entry for entry in course(item['course_id'], item['course_version'])['lessons']
                       if entry['id'] == item['lesson_id']), None)
        index = item['question_index']
        if lesson is None or not isinstance(index, int) or index < 0 or index >= len(lesson['quiz']):
            raise ValueError(f"unknown question: {key}")
        if not reviewed_variant('study_help', item, date.fromisoformat(item['review']['checked_at'])):
            raise ValueError(f"invalid review: {key}")
        for field in ('hint', 'next_step', 'explanation'):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"missing {field}: {key}")
        hint = normalize_answer(item['hint'])
        if any(normalize_answer(answer) in hint for answer in lesson['quiz'][index]['answers']):
            raise ValueError(f"hint contains answer: {key}")


@lru_cache(maxsize=1)
def all_help() -> tuple[dict, ...]:
    items = json.loads(files('app.content').joinpath('study-help-v1.json').read_text(encoding='utf-8'))
    validate_help_catalog(items)
    return tuple(items)


def get_help_fragment(course_id: str, version: str, lesson_id: str, question_index: int,
                      *, today: date, db: Session | None = None) -> HelpFragment | None:
    key = f"{course_id}:{version}:{lesson_id}:{question_index}"
    item = next((entry for entry in all_help() if help_id(entry) == key), None)
    if item is None or not reviewed_variant('study_help', item, today):
        return None
    if db is not None and is_revoked(db, 'study_help', key, 'v1'):
        return None
    return HelpFragment(course_id, version, lesson_id, question_index,
                        item['hint'], item['next_step'], item['explanation'])
