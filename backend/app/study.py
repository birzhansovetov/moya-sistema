"""Versioned authored curricula; deterministic assessment, no code execution or AI."""
import copy
import hashlib
import json
import unicodedata
from functools import lru_cache
from importlib.resources import files
from fastapi import HTTPException
from sqlalchemy import select
from app.models import StudyAttempt, StudyPlan, User


LATEST_VERSIONS = {'java': 'v2', 'go': 'v2', 'english': 'v3', 'java-backend': 'v3'}


def latest_version(course_id):
    if course_id not in LATEST_VERSIONS:
        raise HTTPException(404, 'Маршрут не найден')
    return LATEST_VERSIONS[course_id]


@lru_cache(maxsize=1)
def _extensions():
    return json.loads(files('app.content').joinpath('study-extensions-v1.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def _grammar_guides():
    return json.loads(files('app.content').joinpath('study-grammar-v1.json').read_text(encoding='utf-8'))


def catalog(version='v1'):
    if version not in ('v1', 'v2', 'v3', 'latest'):
        raise HTTPException(404, 'Версия материалов недоступна')
    effective = 'v3' if version == 'latest' else version
    current = json.loads(files('app.content').joinpath('study-v1.json').read_text(encoding='utf-8'))
    current.append(json.loads(files('app.content').joinpath('study-go-v1.json').read_text(encoding='utf-8')))
    if effective in ('v2', 'v3'):
        current[2] = json.loads(files('app.content').joinpath('study-backend-v2.json').read_text(encoding='utf-8'))
        for index, item in enumerate(current):
            if item['id'] == 'java-backend' and effective == 'v2':
                continue
            extension = _extensions().get(item['id'])
            if extension:
                item['version'] = extension['version']
                item['lessons'].extend(copy.deepcopy(extension['lessons']))
        if effective == 'v3':
            english = next(item for item in current if item['id'] == 'english')
            english['version'] = 'v3'
            for lesson in english['lessons']:
                guide = copy.deepcopy(_grammar_guides()[lesson['id']])
                question = next((q for q in lesson['quiz'] if q.get('skill') == 'grammar'), lesson['quiz'][0])
                guide['check'] = {'prompt': question['prompt'], 'options': question['options'],
                                  'answer': question['answers'][0], 'explanation': question['explanation']}
                lesson['grammar'] = guide
    return current


def course(course_id, version=None):
    selected_version = version or latest_version(course_id)
    item = next((c for c in catalog(selected_version) if c['id'] == course_id and c['version'] == selected_version), None)
    if not item:
        raise HTTPException(404, 'Маршрут не найден')
    return item


def public_course(item):
    result = copy.deepcopy(item)
    for lesson in result['lessons']:
        for q in lesson['quiz']:
            q.pop('answers')
            q.pop('explanation')
        if 'grammar' in lesson:
            lesson['grammar']['check'].pop('answer', None)
    return result


def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload.model_dump(mode='json', exclude={'create_key'}), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def lock_user(db, user_id):
    # Serialize plan replacement, submission and reviews for one account on PostgreSQL.
    db.execute(select(User.id).where(User.id == user_id).with_for_update()).scalar_one()


def replay(db, model, user_id, payload):
    old = db.scalar(select(model).where(model.user_id == user_id, model.create_key == payload.create_key))
    if old and old.fingerprint != fingerprint(payload):
        raise HTTPException(409, 'Этот запрос уже сохранён с другими данными. Обновите форму.')
    return old


def owned_plan(db, user_id, plan_id):
    item = db.get(StudyPlan, plan_id)
    if not item or item.user_id != user_id:
        raise HTTPException(404, 'План не найден')
    return item


def plan_view(item):
    if item is None:
        return None
    return {'id': item.id, 'course_id': item.course_id, 'version': item.version,
            **item.config, 'lesson_ids': item.lesson_ids, 'archived': item.active_slot is None,
            'created_at': item.created_at.isoformat()}


def attempts_for(db, user_id, plan_id):
    return db.scalars(select(StudyAttempt).where(StudyAttempt.user_id == user_id, StudyAttempt.plan_id == plan_id).order_by(StudyAttempt.created_at.desc(), StudyAttempt.id)).all()


def progress(plan, attempts):
    completed = [lid for lid in plan.lesson_ids if any(a.lesson_id == lid and a.passed for a in attempts)]
    return completed, next((lid for lid in plan.lesson_ids if lid not in completed), None)


def normalize_answer(value):
    return ' '.join(unicodedata.normalize('NFKC', value).replace('’', "'").strip().casefold().split())


def grade(lesson, payload):
    feedback = []
    for q, answer in zip(lesson['quiz'], payload.answers):
        correct = normalize_answer(answer) in {normalize_answer(a) for a in q['answers']}
        feedback.append({'prompt': q['prompt'], 'answer': answer, 'correct': correct,
                         'accepted': q['answers'], 'explanation': q['explanation']})
    score = sum(row['correct'] for row in feedback)
    return {'score': score, 'total': len(feedback), 'feedback': feedback,
            'passed': score == len(feedback) and all(payload.self_checks),
            'evidence': payload.evidence, 'self_checks': payload.self_checks,
            'portfolio_url': payload.portfolio_url,
            'assessment': 'Вопросы проверены автоматически. Практика, письмо и речь — самостоятельная оценка по критериям.'}


def attempt_view(item):
    return {'id': item.id, 'plan_id': item.plan_id, 'lesson_id': item.lesson_id,
            'date': item.date.isoformat(), 'snapshot': item.snapshot, **item.result}
