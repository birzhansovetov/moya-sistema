from datetime import date as DateValue, timedelta
from typing import Literal
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth import AuthContext, get_current_user, require_csrf
from app.content_review import is_revoked
from app.db import get_db
from app.models import StudyPlan, StudyAttempt, StudyDraft, StudyReview, User
from app.tasks import local_date
from app.study import (catalog, course, public_course, fingerprint, lock_user, replay, owned_plan,
                       plan_view, attempts_for, progress, grade, attempt_view, normalize_answer)

router = APIRouter(prefix='/api/study', tags=['study'])


class PlanValues(BaseModel):
    course_id: str = Field(max_length=40)
    version: str = Field(default='v1',max_length=20)
    level: str = Field(max_length=20)
    goal: Literal['general','work','travel','project']
    minutes: Literal[15,30,45,60]
    weekdays: list[int] = Field(min_length=1,max_length=7)
    start_date: DateValue

    @model_validator(mode='after')
    def valid_days(self):
        if any(d not in range(7) for d in self.weekdays) or len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError('Выберите неповторяющиеся дни недели')
        self.weekdays = sorted(self.weekdays)
        return self


class PlanCreate(PlanValues):
    expected_plan_id: str | None
    create_key: str = Field(min_length=1,max_length=100)


class AttemptCreate(BaseModel):
    plan_id: str
    lesson_id: str = Field(max_length=60)
    date: DateValue
    answers: list[str] = Field(min_length=1,max_length=20)
    evidence: str = Field(min_length=20,max_length=20000)
    self_checks: list[bool] = Field(min_length=1,max_length=10)
    portfolio_url: str = Field(default='',max_length=2000)
    create_key: str = Field(min_length=1,max_length=100)
    expected_draft_revision: int | None = Field(default=None,ge=1)

    @model_validator(mode='after')
    def normalized(self):
        self.evidence = self.evidence.strip()
        self.portfolio_url = self.portfolio_url.strip()
        self.answers = [a.strip() for a in self.answers]
        if len(self.evidence) < 20 or any(len(a)>2000 for a in self.answers):
            raise ValueError('Опишите результат минимум в 20 символах')
        if self.portfolio_url:
            parsed = urlsplit(self.portfolio_url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Для портфолио укажите HTTPS-ссылку без логина и пароля')
        return self


class DraftValues(BaseModel):
    expected_revision: int | None = Field(default=None,ge=1)
    answers: list[str] = Field(min_length=1,max_length=20)
    evidence: str = Field(max_length=20000)
    self_checks: list[bool] = Field(min_length=1,max_length=10)
    date: DateValue
    portfolio_url: str = Field(default='',max_length=2000)
    create_key: str = Field(min_length=1,max_length=100)

    @model_validator(mode='after')
    def valid_strings(self):
        if any(len(a)>2000 for a in self.answers):
            raise ValueError('Ответ слишком длинный')
        return self


class ReviewCreate(BaseModel):
    course_id: str
    version: str = 'v1'
    card_id: str = Field(max_length=80)
    rating: Literal['again','remembered']
    expected_review_id: str | None
    create_key: str = Field(min_length=1,max_length=100)


class GrammarCheck(BaseModel):
    version: str = Field(max_length=20)
    lesson_id: str = Field(max_length=60)
    answer: str = Field(max_length=300)


def preview_values(payload):
    c = course(payload.course_id, payload.version)
    if payload.level not in c['levels']:
        raise HTTPException(422, 'Для этого уровня пока нет готового маршрута')
    levels = c['levels'][c['levels'].index(payload.level):]
    lessons = [l for l in c['lessons'] if l['level'] in levels]
    return {'course_id': c['id'], 'version': c['version'], **payload.model_dump(mode='json',exclude={'create_key','expected_plan_id'}),
            'lesson_ids': [l['id'] for l in lessons], 'lesson_count': len(lessons),
            'sessions_per_lesson': max(1, (lessons[0]['minutes'] + payload.minutes - 1)//payload.minutes),
            'reason': f'Начальный блок: {payload.level}. Выбрано дней в неделю: {len(payload.weekdays)}; окно занятия: {payload.minutes} мин. Короткое окно делит урок на чтение и практику. Цель меняет акцент задания; темы маршрута сохраняются.',
            'prerequisite': c['prerequisite']}


@router.get('/catalog')
def get_catalog(user: User = Depends(get_current_user)):
    return {'items': [{k:v for k,v in c.items() if k != 'lessons'} | {'lesson_count': len(c['lessons'])} for c in catalog('latest')]}


@router.get('/courses/{course_id}')
def get_course(course_id: str, version: str | None = None, user: User = Depends(get_current_user)):
    return public_course(course(course_id, version))


@router.post('/grammar-check')
def grammar_check(payload: GrammarCheck, context: AuthContext = Depends(require_csrf)):
    selected = course('english', payload.version)
    lesson = next((item for item in selected['lessons'] if item['id'] == payload.lesson_id), None)
    if not lesson or 'grammar' not in lesson:
        raise HTTPException(404, 'Упражнение не найдено')
    check = lesson['grammar']['check']
    if payload.answer not in check['options']:
        raise HTTPException(422, 'Выберите предложенный ответ')
    return {'correct': normalize_answer(payload.answer) == normalize_answer(check['answer']),
            'explanation': check['explanation']}


@router.post('/preview')
def preview(payload: PlanValues, context: AuthContext = Depends(require_csrf)):
    return preview_values(payload)


@router.post('/plans',status_code=201)
def create_plan(payload: PlanCreate, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    data = preview_values(payload)
    if is_revoked(db, 'study', payload.course_id, payload.version):
        raise HTTPException(422, 'Курс отозван и сейчас недоступен')
    lock_user(db, context.user.id)
    old = replay(db, StudyPlan, context.user.id, payload)
    if old:
        return plan_view(old)
    active = db.scalar(select(StudyPlan).where(StudyPlan.user_id == context.user.id, StudyPlan.active_slot == payload.course_id))
    if (active.id if active else None) != payload.expected_plan_id:
        raise HTTPException(409, 'Активный план изменился. Обновите страницу и заново проверьте замену.')
    if payload.start_date < local_date(context.user.timezone):
        raise HTTPException(422, 'Новый план начинается сегодня или позже')
    if active:
        active.active_slot = None
        db.flush()
    item = StudyPlan(user_id=context.user.id,course_id=payload.course_id,version=payload.version,active_slot=payload.course_id,
                     config=payload.model_dump(mode='json',exclude={'course_id','version','create_key','expected_plan_id'}),
                     lesson_ids=data['lesson_ids'],create_key=payload.create_key,fingerprint=fingerprint(payload))
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        old = replay(db, StudyPlan, context.user.id, payload)
        if old:
            return plan_view(old)
        raise HTTPException(409, 'План уже изменён другим запросом. Обновите страницу.') from None
    return plan_view(item)


@router.get('/state/{course_id}')
def state(course_id: str, plan_id: str | None = None, history_offset: int = Query(default=0,ge=0), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course(course_id)
    plans = db.scalars(select(StudyPlan).where(StudyPlan.user_id==user.id,StudyPlan.course_id==course_id).order_by(StudyPlan.created_at.desc(),StudyPlan.id)).all()
    active = next((p for p in plans if p.active_slot),None)
    selected = owned_plan(db,user.id,plan_id) if plan_id else active
    if selected and selected.course_id != course_id:
        raise HTTPException(404,'План не относится к этому разделу')
    attempts = attempts_for(db,user.id,selected.id) if selected else []
    completed,next_lesson = progress(selected,attempts) if selected else ([],None)
    pending_retry_lesson_id = next((a.lesson_id for a in attempts if not a.passed and a.lesson_id in selected.lesson_ids and a.lesson_id not in completed),None) if selected else None
    return {'active_plan':plan_view(active),'plan':plan_view(selected),'plans':[plan_view(p) for p in plans],
            'completed':completed,'next_lesson_id':next_lesson,'pending_retry_lesson_id':pending_retry_lesson_id,
            'attempts':[attempt_view(a) for a in attempts[history_offset:history_offset+20]],'attempt_total':len(attempts),'history_offset':history_offset}


@router.get('/weak-topics/{course_id}')
def weak_topics(course_id: str, plan_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course(course_id)
    plan = owned_plan(db, user.id, plan_id) if plan_id else db.scalar(select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.active_slot == course_id))
    if plan and plan.course_id != course_id:
        raise HTTPException(404, 'План не относится к этому разделу')
    if not plan:
        return {'items': []}
    latest = {}
    for attempt in attempts_for(db, user.id, plan.id):
        latest.setdefault(attempt.lesson_id, attempt)
    items = []
    for lesson_id in plan.lesson_ids:
        attempt = latest.get(lesson_id)
        if not attempt or attempt.passed:
            continue
        for question, feedback in zip(attempt.snapshot.get('quiz', []), attempt.result.get('feedback', [])):
            if not feedback['correct']:
                items.append({'lesson_id': lesson_id, 'lesson_title': attempt.snapshot['title'],
                              'skill': question.get('skill', 'Тема урока'), 'prompt': feedback['prompt'],
                              'explanation': feedback['explanation'], 'date': attempt.date.isoformat()})
    return {'items': items[:20]}


def draft_view(item:StudyDraft):
    return {'id':item.id,'plan_id':item.plan_id,'lesson_id':item.lesson_id,
            'content':item.content,'revision':item.revision,'updated_at':item.updated_at.isoformat()}


@router.get('/drafts/{course_id}')
def drafts(course_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    course(course_id)
    items=db.scalars(select(StudyDraft).join(StudyPlan).where(StudyDraft.user_id==user.id,StudyPlan.user_id==user.id,StudyPlan.course_id==course_id).order_by(StudyDraft.updated_at.desc())).all()
    return {'items':[draft_view(item) for item in items]}


@router.put('/drafts/{plan_id}/{lesson_id}')
def save_draft(plan_id:str,lesson_id:str,payload:DraftValues,context:AuthContext=Depends(require_csrf),db:Session=Depends(get_db)):
    lock_user(db,context.user.id)
    plan=owned_plan(db,context.user.id,plan_id)
    if plan.active_slot is None:
        raise HTTPException(409,'Архивный план доступен только для чтения')
    if lesson_id not in plan.lesson_ids:
        raise HTTPException(404,'Урок не входит в план')
    lesson=next(l for l in course(plan.course_id,plan.version)['lessons'] if l['id']==lesson_id)
    if len(payload.answers)!=len(lesson['quiz']) or len(payload.self_checks)!=len(lesson['rubric']):
        raise HTTPException(422,'Число ответов или критериев не совпадает с уроком')
    if db.scalar(select(StudyAttempt.id).where(StudyAttempt.user_id==context.user.id,StudyAttempt.create_key==payload.create_key)):
        raise HTTPException(409,'Результат с этим ключом уже сохранён')
    content=payload.model_dump(mode='json',exclude={'expected_revision'})
    item=db.scalar(select(StudyDraft).where(StudyDraft.user_id==context.user.id,StudyDraft.plan_id==plan_id,StudyDraft.lesson_id==lesson_id))
    if item:
        if item.content==content:
            return draft_view(item)
        if item.revision!=payload.expected_revision:
            raise HTTPException(409,'Черновик изменён в другом окне. Скопируйте свой текст и обновите страницу.')
        item.content=content
        item.revision+=1
    else:
        if payload.expected_revision is not None:
            raise HTTPException(409,'Черновик больше не найден. Обновите страницу.')
        item=StudyDraft(user_id=context.user.id,plan_id=plan_id,lesson_id=lesson_id,content=content,revision=1)
        db.add(item)
    db.commit()
    db.refresh(item)
    return draft_view(item)


@router.post('/attempts',status_code=201)
def submit(payload: AttemptCreate, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    lock_user(db,context.user.id)
    old = replay(db,StudyAttempt,context.user.id,payload)
    if old:
        return attempt_view(old)
    plan = owned_plan(db,context.user.id,payload.plan_id)
    if plan.active_slot is None:
        raise HTTPException(409,'План заменён. Откройте действующий план; черновик можно скопировать.')
    if payload.date > local_date(context.user.timezone) or payload.date.isoformat() < plan.config['start_date']:
        raise HTTPException(422,'Результат должен относиться к дате от начала плана до сегодня')
    lesson = next((l for l in course(plan.course_id,plan.version)['lessons'] if l['id']==payload.lesson_id and l['id'] in plan.lesson_ids),None)
    if not lesson:
        raise HTTPException(422,'Урок не входит в выбранный план')
    if len(payload.answers)!=len(lesson['quiz']) or len(payload.self_checks)!=len(lesson['rubric']):
        raise HTTPException(422,'Ответьте на каждый вопрос и проверьте критерии')
    draft=db.scalar(select(StudyDraft).where(StudyDraft.user_id==context.user.id,StudyDraft.plan_id==payload.plan_id,StudyDraft.lesson_id==payload.lesson_id))
    if (draft.revision if draft else None)!=payload.expected_draft_revision:
        raise HTTPException(409,'Черновик изменён в другом окне. Скопируйте свой текст и обновите страницу.')
    result = grade(lesson,payload)
    item = StudyAttempt(user_id=context.user.id,plan_id=plan.id,lesson_id=lesson['id'],date=payload.date,
                        snapshot=lesson,result=result,passed=result['passed'],create_key=payload.create_key,fingerprint=fingerprint(payload))
    db.add(item)
    if draft:
        db.execute(delete(StudyDraft).where(StudyDraft.id==draft.id,StudyDraft.revision==payload.expected_draft_revision))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        old = replay(db,StudyAttempt,context.user.id,payload)
        if old:return attempt_view(old)
        raise HTTPException(409,'Повторите сохранение') from None
    return attempt_view(item)


def learned_cards(db,user_id,course_id,version):
    c = course(course_id,version)
    rows = db.scalars(select(StudyAttempt).join(StudyPlan).where(StudyAttempt.user_id==user_id,StudyPlan.course_id==course_id,StudyPlan.version==version)).all()
    learned = {a.lesson_id for a in rows}
    return {v['id']:v for l in c['lessons'] if l['id'] in learned for v in l.get('vocabulary',[])}


def latest_reviews(db,user_id,course_id,version):
    rows = db.scalars(select(StudyReview).where(StudyReview.user_id==user_id,StudyReview.course_id==course_id,StudyReview.version==version).order_by(StudyReview.created_at.desc(),StudyReview.id)).all()
    result={}
    for r in rows: result.setdefault(r.card_id,r)
    return result


@router.get('/cards/{course_id}')
def cards(course_id: str, version: str = 'v1', user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    known = learned_cards(db,user.id,course_id,version)
    reviews = latest_reviews(db,user.id,course_id,version)
    today = local_date(user.timezone)
    return {'items':[{**v,'review_id':reviews[cid].id if cid in reviews else None,'due_date':reviews[cid].due_date.isoformat() if cid in reviews else today.isoformat()} for cid,v in known.items() if cid not in reviews or reviews[cid].due_date<=today], 'total_learned':len(known), 'today':today.isoformat()}


def review_view(r):
    return {'id':r.id,'card_id':r.card_id,'date':r.date.isoformat(),'due_date':r.due_date.isoformat(),'rating':r.rating,'streak':r.streak}


@router.post('/reviews',status_code=201)
def review(payload: ReviewCreate,context:AuthContext=Depends(require_csrf),db:Session=Depends(get_db)):
    lock_user(db,context.user.id)
    old=replay(db,StudyReview,context.user.id,payload)
    if old:return review_view(old)
    known=learned_cards(db,context.user.id,payload.course_id,payload.version)
    if payload.card_id not in known:raise HTTPException(422,'Сначала сохраните результат урока с этим словом')
    last=latest_reviews(db,context.user.id,payload.course_id,payload.version).get(payload.card_id)
    if (last.id if last else None)!=payload.expected_review_id:raise HTTPException(409,'Карточка уже изменена. Обновите повторение.')
    today=local_date(context.user.timezone)
    if last and last.due_date>today:raise HTTPException(422,'Эта карточка уже повторена сегодня')
    streak=(last.streak if last else 0)+1 if payload.rating=='remembered' else 0
    interval=[1,3,7,14,30][min(max(streak-1,0),4)]
    item=StudyReview(user_id=context.user.id,course_id=payload.course_id,version=payload.version,card_id=payload.card_id,
                     rating=payload.rating,streak=streak,date=today,due_date=today+timedelta(days=interval),create_key=payload.create_key,fingerprint=fingerprint(payload))
    db.add(item)
    try:db.commit()
    except IntegrityError:
        db.rollback()
        old=replay(db,StudyReview,context.user.id,payload)
        if old:return review_view(old)
        raise HTTPException(409,'Повторите сохранение') from None
    return review_view(item)


@router.get('/day')
def day(date:DateValue,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    plans=db.scalars(select(StudyPlan).where(StudyPlan.user_id==user.id,StudyPlan.active_slot.is_not(None))).all()
    items=[]
    for p in plans:
        if date.isoformat()<p.config['start_date'] or date.weekday() not in p.config['weekdays']:continue
        _,next_id=progress(p,attempts_for(db,user.id,p.id))
        if not next_id:continue
        c=course(p.course_id,p.version);l=next(l for l in c['lessons'] if l['id']==next_id)
        items.append({'course_id':c['id'],'course_title':c['title'],'plan_id':p.id,'lesson_id':next_id,'title':l['title'],'date':date.isoformat(),'minutes':p.config['minutes']})
    return {'items':items,'notice':'Текущий следующий шаг, а не исторический снимок плана. Дата будет подставлена в запись результата.'}


def diagnostic_questions():
    c=course('english')
    return [c['lessons'][i]['quiz'][0] for i in (0,1,6,9,10,13)]


@router.get('/diagnostic')
def diagnostic(user:User=Depends(get_current_user)):
    return {'questions':[{k:v for k,v in q.items() if k not in ('answers','explanation')} for q in diagnostic_questions()],
            'limitation':'Шесть вопросов дают только ориентир A2/B1 по отдельным темам. Устная речь, письмо и понимание естественной речи не оценены; B2 не присваивается.'}


class DiagnosticAnswers(BaseModel):
    answers:list[str]=Field(min_length=6,max_length=6)


@router.post('/diagnostic')
def check_diagnostic(payload:DiagnosticAnswers,context:AuthContext=Depends(require_csrf)):
    from app.study import normalize_answer
    questions=diagnostic_questions()
    score=sum(normalize_answer(a) in {normalize_answer(x) for x in q['answers']} for a,q in zip(payload.answers,questions))
    return {'score':score,'total':6,'level':'B1' if score>=5 else 'A2','below_scope':score<3,
            'feedback':[{'prompt':q['prompt'],'accepted':q['answers'],'explanation':q['explanation']} for q in questions],
            'message':'Это ориентир, не подтверждённый уровень. Если основы ещё затрудняют, перед A2 нужна подготовка A1; готового A1-маршрута здесь пока нет.' if score<3 else 'Начните с предложенного блока или измените его по своей оценке. План ещё не создан.'}
