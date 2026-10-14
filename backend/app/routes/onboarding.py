"""Six-sphere survey with deterministic, previewable recommendations."""
import json
import hashlib
from datetime import timedelta
from importlib.resources import files
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth import AuthContext, get_current_user, require_csrf
from app.content_review import is_revoked, load_reviews, reviewed_variant
from app.db import get_db, utc_now
from app.models import MatchingPreview, MatchingStartResult, SportPlan, StudyPlan, User
from app.matching import match_survey
from app.local_ai import completed_week_progress
from app.preview_store import create_preview, load_preview, load_preview_any
from app.nutrition import NutritionPreferences, compatible_recipes
from app.routes.auth import user_info
from app.routes.study import PlanValues, preview_values
from app.sport import SportAnswers, select_program, load_sport_catalog
from app.study import course as study_course, fingerprint, lock_user
from app.tasks import local_date

router = APIRouter(prefix='/api/onboarding', tags=['onboarding'])
SURVEY_VERSION = 2

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')
class Health(Strict):
    sport: SportAnswers | None
    vegetarian: bool
    max_cooking_minutes: int = Field(ge=5, le=180)
    nutrition_goal: Literal['fat_loss','maintain','gain'] = 'maintain'
    allergies: list[Literal['gluten','milk','egg','fish']] = Field(default_factory=list)
class Education(Strict):
    track: Literal['java','go','reading','both','go-reading','none']
    reading_genres: list[Literal['classic','detective','horror','fiction','self_development']] = Field(min_length=1,max_length=5)
    minutes: Literal[15,30,45,60]
    weekdays: list[int] = Field(min_length=1,max_length=7)
class Profession(Strict):
    track: Literal['java-backend','none']
    minutes: Literal[15,30,45,60]
    weekdays: list[int] = Field(min_length=1,max_length=7)
class Languages(Strict):
    level: Literal['A2','B1','B2','none']
    goal: Literal['general','work','travel','project']
    minutes: Literal[15,30,45,60]
    weekdays: list[int] = Field(min_length=1,max_length=7)
class Finance(Strict):
    currency: Literal['KZT','USD','EUR','RUB']
    focus: Literal['record','review']
class Personal(Strict):
    focus: Literal['journal','habits','reading']
class Survey(Strict):
    health: Health
    education: Education
    profession: Profession
    languages: Languages
    finance: Finance
    personal: Personal
class StartSelection(Strict):
    preview_id: str
    selected: dict[str,str] = Field(default_factory=dict)
    skipped: list[str] = Field(default_factory=list)
    confirm_replace: bool = False
class RestoreRequest(Strict):
    kind: Literal['sport','study']
    plan_id: str
    confirm_progress: bool = False
class ResultRequest(Strict):
    preview_id: str

def study_values(course_id, level, minutes, weekdays, timezone, goal='general', version='v1'):
    return PlanValues(course_id=course_id, version=version, level=level, goal=goal, minutes=minutes,
                      weekdays=weekdays, start_date=local_date(timezone))

def choices(payload, timezone):
    return [
        study_values('go' if payload.education.track in ('go','go-reading') else 'java','beginner',payload.education.minutes,payload.education.weekdays,timezone,version='v2') if payload.education.track in ('java','go','both','go-reading') else None,
        study_values('java-backend','foundation',payload.profession.minutes,payload.profession.weekdays,timezone,version='v3') if payload.profession.track == 'java-backend' else None,
        study_values('english',payload.languages.level,payload.languages.minutes,payload.languages.weekdays,timezone,goal=payload.languages.goal,version='v2') if payload.languages.level != 'none' else None,
    ]

def study_match(value, fallback_title, fallback_route):
    if value is None: return {'status':'skipped','reason':'Маршрут пока не выбран.','material':{'title':fallback_title,'route':fallback_route}}
    try: data = preview_values(value)
    except HTTPException as error: return {'status':'unavailable','reason':str(error.detail)}
    return {'status':'matched','lesson_count':data['lesson_count'],'route':{'java':'/education/java','go':'/education/go','java-backend':'/profession','english':'/languages'}[value.course_id]}

def build_preview(payload, timezone):
    sport = select_program(payload.health.sport) if payload.health.sport else None
    sport_match = ({'status':'matched','title':sport['program']['title'],'route':'/health/sport'} if sport and sport['program'] else
                   {'status':'unavailable','reason':' '.join(sport['reasons']),'material':{'title':sport['material']['title'],'route':f"/health/sport#{sport['material']['id']}"}} if sport else {'status':'skipped','reason':'Тренировки пока не выбраны.','material':{'title':'Гайды по тренировкам','route':'/health/sport#sport-guides'}})
    recipes = compatible_recipes(NutritionPreferences(vegetarian=payload.health.vegetarian,
        allergies=payload.health.allergies,max_minutes=payload.health.max_cooking_minutes))
    recipe_list = [recipe for group in recipes.values() for recipe in group]
    if payload.health.nutrition_goal == 'gain':
        recipe_list.sort(key=lambda recipe: recipe['nutrition_per_serving']['kcal'] + recipe['nutrition_per_serving']['protein_g'] * 4, reverse=True)
    elif payload.health.nutrition_goal == 'fat_loss':
        recipe_list.sort(key=lambda recipe: recipe['nutrition_per_serving']['protein_g'] / max(recipe['nutrition_per_serving']['kcal'], 1), reverse=True)
    books = json.loads(files('app.content').joinpath('book_suggestions.json').read_text(encoding='utf-8'))
    book = (next((item for item in books if any(genre in item.get('genres', []) for genre in payload.education.reading_genres)), None)
            if payload.education.track in ('reading', 'both', 'go-reading') else None)
    education, backend, english = choices(payload, timezone)
    return {'areas':{
        'health':{'title':'Здоровье','sport':sport_match,'recipes':{'status':'matched' if recipe_list else 'unavailable','count':len(recipe_list),'example':recipe_list[0]['name'] if recipe_list else None,'route':'/health/nutrition'}},
        'education':{'title':'Обучение','study':study_match(education,'Готовые курсы Java и Go','/education'),'book':{'title':book['title'],'author':book['author'],'route':'/education/reading'} if book else None},
        'profession':{'title':'Профессия','study':study_match(backend,'Уроки Java backend','/profession')},
        'languages':{'title':'Языки','study':study_match(english,'Уроки английского A2–B2','/languages')},
        'finance':{'title':'Финансы','guide':{'title':'Учитывать расходы' if payload.finance.focus=='record' else 'Разбирать расходы за месяц','route':'/finance'}},
        'personal':{'title':'Личное','guide':{'title':{'journal':'Вести дневник','habits':'Работать с привычками','reading':'Размышлять о прочитанном'}[payload.personal.focus],'route':'/personal'}}}}

@router.get('')
def state(user:User=Depends(get_current_user)):
    return {'complete':user.onboarding_completed_at is not None,'answers':user.onboarding_answers,
            'survey_version':user.onboarding_version or SURVEY_VERSION,
            'needs_reconfirmation':user.onboarding_answers is not None and user.onboarding_version not in (None, SURVEY_VERSION)}
@router.post('/preview')
def preview(payload:Survey,request:Request,context:AuthContext=Depends(require_csrf),db:Session=Depends(get_db)):
    if not request.app.state.settings.shared_matching_enabled:
        return build_preview(payload,context.user.timezone)
    lock_user(db,context.user.id)
    cutoff=utc_now()-timedelta(hours=1)
    count=db.scalar(select(func.count()).select_from(MatchingPreview).where(MatchingPreview.user_id==context.user.id,
                                                                             MatchingPreview.created_at>=cutoff)) or 0
    if count>=20:
        raise HTTPException(429,'Слишком много предпросмотров. Повторите через час.',headers={'Retry-After':'3600'})
    matched=match_survey(payload,context.user.timezone,db)
    raw,snapshot=create_preview(db,context.user,payload.model_dump(mode='json'),matched)
    active_sport=db.scalar(select(SportPlan).where(SportPlan.user_id==context.user.id,SportPlan.active_key=='active'))
    active_studies=db.scalars(select(StudyPlan).where(StudyPlan.user_id==context.user.id,StudyPlan.active_slot.is_not(None))).all()
    existing={'health':active_sport.program_snapshot.get('title',active_sport.program_id)} if active_sport else {}
    for plan in active_studies:
        sphere='education' if plan.course_id in ('java','go') else 'profession' if plan.course_id=='java-backend' else 'languages'
        existing[sphere]=plan.course_id
    db.commit()
    return {'preview_id':raw,'expires_at':snapshot.expires_at.isoformat(),'areas':matched['areas'],
            'candidates_by_sphere':{sphere:items[:3] for sphere,items in matched['candidates_by_sphere'].items()},
            'candidate_counts':{sphere:len(items) for sphere,items in matched['candidates_by_sphere'].items()},
            'existing_plans':existing}


@router.post('/preview/choices')
def preview_choices(payload:ResultRequest,request:Request,context:AuthContext=Depends(require_csrf),db:Session=Depends(get_db)):
    if not request.app.state.settings.shared_matching_enabled:
        raise HTTPException(404,'Предпросмотр недоступен')
    snapshot=load_preview(db,context.user.id,payload.preview_id)
    if snapshot is None:
        raise HTTPException(404,'Предпросмотр истёк или не найден')
    return {'candidates_by_sphere':snapshot.candidates}


@router.post('/assist')
def assist(payload: ResultRequest, request: Request, context: AuthContext = Depends(require_csrf),
           db: Session = Depends(get_db)):
    if not request.app.state.settings.shared_matching_enabled:
        raise HTTPException(404, 'Подбор недоступен')
    snapshot = load_preview(db, context.user.id, payload.preview_id)
    if snapshot is None:
        raise HTTPException(404, 'Предпросмотр истёк или не найден')
    settings = request.app.state.settings
    return request.app.state.preview_advisor.suggest(
        snapshot, enabled=settings.local_ai_enabled and settings.environment == 'development',
        model=settings.ollama_model,
        progress=completed_week_progress(db, context.user) if settings.local_ai_enabled and settings.environment == 'development' else None)


@router.post('/result')
def start_result(payload:ResultRequest,request:Request,context:AuthContext=Depends(require_csrf),db:Session=Depends(get_db)):
    if not request.app.state.settings.shared_matching_enabled:
        raise HTTPException(404,'Результат недоступен')
    snapshot=load_preview_any(db,context.user.id,payload.preview_id)
    if snapshot is None:
        return {'committed':False}
    prior=db.scalar(select(MatchingStartResult).where(MatchingStartResult.user_id==context.user.id,
                    MatchingStartResult.nonce_hash==snapshot.nonce_hash))
    return {'committed':prior is not None,'result':prior.response if prior else None}
@router.post('/start')
def start(payload:Survey | StartSelection,request:Request,confirm_replace:bool=False,context:AuthContext=Depends(require_csrf),db:Session=Depends(get_db)):
    if request.app.state.settings.shared_matching_enabled:
        if not isinstance(payload,StartSelection):
            raise HTTPException(422,'Нужен сохранённый предпросмотр')
        try:
            return _start_selected(payload,context,db)
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
            db.rollback()
            snapshot=load_preview_any(db,context.user.id,payload.preview_id)
            canonical=json.dumps({'selected':payload.selected,'skipped':sorted(payload.skipped),'confirm_replace':payload.confirm_replace},
                                 sort_keys=True,separators=(',',':'),ensure_ascii=False)
            if snapshot:
                prior=db.scalar(select(MatchingStartResult).where(MatchingStartResult.user_id==context.user.id,
                            MatchingStartResult.nonce_hash==snapshot.nonce_hash))
                if prior and prior.payload_digest==hashlib.sha256(canonical.encode('utf-8')).hexdigest():
                    return prior.response
            raise
        except IntegrityError:
            db.rollback()
            snapshot=load_preview_any(db,context.user.id,payload.preview_id)
            if snapshot is None:
                raise HTTPException(409,'Предпросмотр изменился; повторите подбор') from None
            prior=db.scalar(select(MatchingStartResult).where(MatchingStartResult.user_id==context.user.id,
                         MatchingStartResult.nonce_hash==snapshot.nonce_hash))
            canonical=json.dumps({'selected':payload.selected,'skipped':sorted(payload.skipped),'confirm_replace':payload.confirm_replace},
                                 sort_keys=True,separators=(',',':'),ensure_ascii=False)
            if prior and prior.payload_digest==hashlib.sha256(canonical.encode('utf-8')).hexdigest():
                return prior.response
            raise HTTPException(409,'Предпросмотр уже обработан с другим выбором') from None
    if not isinstance(payload,Survey):
        raise HTTPException(422,'Нужна анкета')
    user=context.user
    lock_user(db,user.id)
    answers=payload.model_dump(mode='json')
    result=build_preview(payload,user.timezone)
    if user.onboarding_answers==answers and user.onboarding_completed_at:
        return {'status':'unchanged','user':user_info(user),**result}
    sport=select_program(payload.health.sport) if payload.health.sport else None
    active_sport=db.scalar(select(SportPlan).where(SportPlan.user_id==user.id,SportPlan.active_key=='active'))
    desired=[item for item in choices(payload,user.timezone) if item and study_match(item,'','')['status']=='matched']
    active_study={item.course_id:item for item in db.scalars(select(StudyPlan).where(StudyPlan.user_id==user.id,StudyPlan.active_slot.is_not(None))).all()}
    sport_same=bool(active_sport and sport and sport['program'] and active_sport.answers==payload.health.sport.model_dump()
                    and active_sport.program_id==sport['program']['id'])
    desired_by_course={item.course_id:item for item in desired}
    study_same={course for course,item in active_study.items() if course in desired_by_course
                and item.version==desired_by_course[course].version
                and {key:value for key,value in item.config.items() if key!='start_date'}==desired_by_course[course].model_dump(mode='json',exclude={'course_id','version','start_date'})}
    needs_replacement=(bool(active_sport) and not sport_same) or any(course not in study_same for course in active_study)
    if not confirm_replace and needs_replacement:
        raise HTTPException(409,'Планы уже есть. Подтвердите замену после просмотра подбора; история сохранится.')
    today=local_date(user.timezone)
    if active_sport and not sport_same:
        active_sport.active_key=None; active_sport.ended_on=today; active_sport.archived_at=utc_now(); db.flush()
    if sport and sport['program'] and not sport_same:
        db.add(SportPlan(user_id=user.id,program_id=sport['program']['id'],content_version=sport['version'],
                         answers=payload.health.sport.model_dump(),program_snapshot=sport['program'],active_key='active',started_on=today))
    for course,active in active_study.items():
        if course not in study_same:
            active.active_slot=None; active.archived_at=utc_now()
    if needs_replacement:
        db.flush()
    for value in desired:
        if value.course_id in study_same:
            continue
        data=preview_values(value)
        db.add(StudyPlan(user_id=user.id,course_id=value.course_id,version=value.version,active_slot=value.course_id,
                         config=value.model_dump(mode='json',exclude={'course_id','version'}),lesson_ids=data['lesson_ids'],
                         create_key=f'onboarding-{uuid4()}',fingerprint=fingerprint(value)))
    user.onboarding_answers=answers; user.onboarding_version=SURVEY_VERSION; user.onboarding_completed_at=utc_now(); user.finance_currency=payload.finance.currency
    db.commit()
    return {'status':'started','user':user_info(user),**result}


def _start_selected(payload:StartSelection,context:AuthContext,db:Session) -> dict:
    user=context.user
    lock_user(db,user.id)
    snapshot=load_preview_any(db,user.id,payload.preview_id)
    if snapshot is None:
        raise HTTPException(404,'Предпросмотр не найден')
    canonical=json.dumps({'selected':payload.selected,'skipped':sorted(payload.skipped),'confirm_replace':payload.confirm_replace},
                         sort_keys=True,separators=(',',':'),ensure_ascii=False)
    digest=hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    prior=db.scalar(select(MatchingStartResult).where(MatchingStartResult.user_id==user.id,MatchingStartResult.nonce_hash==snapshot.nonce_hash))
    if prior:
        if prior.payload_digest!=digest:
            raise HTTPException(409,'Предпросмотр уже запущен с другим выбором')
        return prior.response
    if snapshot.expires_at<=utc_now():
        raise HTTPException(409,'Предпросмотр истёк; обновите подбор')
    answers_digest=hashlib.sha256(json.dumps(snapshot.answers,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest()
    if answers_digest!=snapshot.answers_digest:
        raise HTTPException(409,'Снимок анкеты изменился; обновите подбор')
    spheres={'health','education','profession','languages','finance','personal'}
    if not set(payload.selected)<=spheres or not set(payload.skipped)<=spheres or set(payload.selected)&set(payload.skipped):
        raise HTTPException(422,'Неизвестная или повторная сфера')
    for sphere,item_id in payload.selected.items():
        if item_id not in {item['id'] for item in snapshot.candidates.get(sphere,[])}:
            raise HTTPException(409,'Выбранного материала нет в сохранённом списке')
    survey=Survey.model_validate(snapshot.answers)
    current=match_survey(survey,user.timezone,db)
    for sphere,item_id in payload.selected.items():
        before=next(item for item in snapshot.candidates[sphere] if item['id']==item_id)
        now=next((item for item in current['candidates_by_sphere'].get(sphere,[]) if item['id']==item_id),None)
        if now is None or now['version']!=before['version'] or now['digest']!=before['digest']:
            raise HTTPException(409,'Материал изменился или отозван; обновите подбор')
    active_sport=db.scalar(select(SportPlan).where(SportPlan.user_id==user.id,SportPlan.active_key=='active'))
    active_studies={p.course_id:p for p in db.scalars(select(StudyPlan).where(StudyPlan.user_id==user.id,StudyPlan.active_slot.is_not(None))).all()}
    if (active_sport.id if active_sport else None)!=snapshot.expected_active['sport'] or {k:v.id for k,v in active_studies.items()}!=snapshot.expected_active['study']:
        raise HTTPException(409,'Планы изменились после предпросмотра; обновите подбор')
    replacement=bool((active_sport and 'health' in payload.selected) or any(s in payload.selected and any(p.course_id in ({'java','go'} if s=='education' else {'java-backend'} if s=='profession' else {'english'}) for p in active_studies.values()) for s in ('education','profession','languages')))
    if replacement and not payload.confirm_replace:
        raise HTTPException(409,'Подтвердите замену существующего плана')
    today=local_date(user.timezone)
    created={}
    if 'health' in payload.selected:
        chosen=next(p for p in load_sport_catalog()['programs'] if p['id']==payload.selected['health'])
        if active_sport:
            active_sport.active_key=None; active_sport.ended_on=today; active_sport.archived_at=utc_now(); db.flush()
        plan=SportPlan(user_id=user.id,program_id=chosen['id'],content_version=load_sport_catalog()['version'],
            answers=survey.health.sport.model_dump(),program_snapshot=chosen,active_key='active',started_on=today)
        db.add(plan); db.flush(); created['health']=plan.id
    study_by_sphere=dict(zip(('education','profession','languages'),choices(survey,user.timezone)))
    for sphere in ('education','profession','languages'):
        if sphere not in payload.selected:
            continue
        value=study_by_sphere[sphere]
        if value is None or value.course_id!=payload.selected[sphere]:
            raise HTTPException(409,'Курс больше не соответствует анкете')
        sphere_courses={'education':{'java','go'},'profession':{'java-backend'},'languages':{'english'}}[sphere]
        for active in active_studies.values():
            if active.course_id in sphere_courses:
                active.active_slot=None; active.archived_at=utc_now()
        db.flush()
        data=preview_values(value)
        plan=StudyPlan(user_id=user.id,course_id=value.course_id,version=value.version,active_slot=value.course_id,
            config=value.model_dump(mode='json',exclude={'course_id','version'}),lesson_ids=data['lesson_ids'],
            create_key=f'onboarding-{uuid4()}',fingerprint=fingerprint(value))
        db.add(plan); db.flush(); created[sphere]=plan.id
    user.onboarding_answers=snapshot.answers
    user.onboarding_version=snapshot.survey_version
    user.onboarding_completed_at=utc_now()
    if 'finance' not in payload.skipped:
        user.finance_currency=survey.finance.currency
    response={'status':'started','created':created,'skipped':sorted(payload.skipped),'survey_version':snapshot.survey_version}
    db.add(MatchingStartResult(user_id=user.id,nonce_hash=snapshot.nonce_hash,payload_digest=digest,response=response))
    db.commit()
    return response


@router.post('/restore')
def restore(payload:RestoreRequest,request:Request,context:AuthContext=Depends(require_csrf),db:Session=Depends(get_db)):
    if not request.app.state.settings.shared_matching_enabled:
        raise HTTPException(404,'Восстановление недоступно')
    user=context.user
    lock_user(db,user.id)
    now=utc_now()
    if payload.kind=='sport':
        old=db.get(SportPlan,payload.plan_id)
        if old is None or old.user_id!=user.id or old.archived_at is None or old.archived_at<now-timedelta(days=7):
            raise HTTPException(404,'Архивный план недоступен')
        if is_revoked(db,'sport',old.program_id,old.content_version):
            raise HTTPException(409,'Программа отозвана и не может быть восстановлена')
        catalog=load_sport_catalog()
        current_variant=next((p for p in catalog['programs'] if p['id']==old.program_id),None)
        if old.content_version!=catalog['version'] or current_variant is None or old.program_snapshot!=current_variant or not reviewed_variant('sport',current_variant,local_date(user.timezone)):
            raise HTTPException(409,'Программа больше не проходит проверку каталога')
        active=db.scalar(select(SportPlan).where(SportPlan.user_id==user.id,SportPlan.active_key=='active'))
        if active and not payload.confirm_progress:
            raise HTTPException(409,'Подтвердите замену текущего плана и сохранение его прогресса')
        if active:
            active.active_key=None; active.ended_on=local_date(user.timezone); active.archived_at=now; db.flush()
        old.active_key='active'; old.ended_on=None; old.archived_at=None
    else:
        old=db.get(StudyPlan,payload.plan_id)
        if old is None or old.user_id!=user.id or old.archived_at is None or old.archived_at<now-timedelta(days=7):
            raise HTTPException(404,'Архивный курс недоступен')
        if is_revoked(db,'study',old.course_id,old.version):
            raise HTTPException(409,'Курс отозван и не может быть восстановлен')
        try:
            course=study_course(old.course_id,old.version)
        except HTTPException:
            raise HTTPException(409,'Курс больше не доступен') from None
        review=load_reviews()['study'].get(f'{old.course_id}:{old.version}',{}).get('review')
        if course is None or not reviewed_variant('study',{**course,'review':review},local_date(user.timezone)):
            raise HTTPException(409,'Курс больше не проходит проверку каталога')
        active=db.scalar(select(StudyPlan).where(StudyPlan.user_id==user.id,StudyPlan.active_slot==old.course_id))
        if active and not payload.confirm_progress:
            raise HTTPException(409,'Подтвердите замену текущего курса и сохранение его прогресса')
        if active:
            active.active_slot=None; active.archived_at=now; db.flush()
        old.active_slot=old.course_id; old.archived_at=None
    db.commit()
    return {'status':'restored','kind':payload.kind,'plan_id':payload.plan_id}


@router.get('/archive')
def restorable_archive(request:Request,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not request.app.state.settings.shared_matching_enabled:
        raise HTTPException(404,'Архив недоступен')
    cutoff=utc_now()-timedelta(days=7)
    sports=db.scalars(select(SportPlan).where(SportPlan.user_id==user.id,SportPlan.archived_at>=cutoff)).all()
    studies=db.scalars(select(StudyPlan).where(StudyPlan.user_id==user.id,StudyPlan.archived_at>=cutoff)).all()
    return {'items':[
        *({'kind':'sport','plan_id':p.id,'title':p.program_snapshot.get('title',p.program_id),'archived_at':p.archived_at.isoformat()} for p in sports),
        *({'kind':'study','plan_id':p.id,'title':p.course_id,'archived_at':p.archived_at.isoformat()} for p in studies),
    ]}
