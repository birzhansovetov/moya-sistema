"""Contextual help accepts public IDs only; personal data never enters inference."""
from dataclasses import asdict
from datetime import datetime, timezone
from time import monotonic
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.assistant_content import PublicExplanation,topics_for_section,materials_for_section,resolve_material
from app.assistant_learning import ExplainFormat,prepared_example,public_step,next_actions,checks_for_material
from app.assistant_limits import reserve_cloud_call
from app.auth import get_auth_context,require_csrf,get_current_user
from app.cloud_ai import explain_public_fragment,PROMPT_VERSION
from app.db import get_db
from app.models import AssistantRequest,User

router=APIRouter(prefix='/api/assistant',tags=['assistant'])

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')
class MaterialRef(Strict):
    kind: Literal['guide','exercise','recipe','book','lesson']
    id: str=Field(min_length=1,max_length=120)
    version: str=Field(min_length=1,max_length=40)
class ExplainRequest(Strict):
    section: str=Field(min_length=1,max_length=24)
    topic_id: str=Field(min_length=1,max_length=60)
    material: MaterialRef | None=None
    format: ExplainFormat="default"
    step_id: str | None=Field(default=None,max_length=40)
class FeedbackRequest(Strict):
    request_id: str=Field(max_length=36)
    helped: bool


def _today():
    return datetime.now(timezone.utc).date()

@router.get('/topics')
def topics(section: str, request: Request, db: Session=Depends(get_db)):
    values=topics_for_section(section)
    if section!='auth':get_auth_context(request,db)
    return {'section':section,'topics':[{'id':x.id,'label':x.label}for x in values],
            'materials':[] if section=='auth' else materials_for_section(section,db=db,today=_today())}

@router.post('/explain')
def explain(payload: ExplainRequest,request: Request,db: Session=Depends(get_db)):
    started=monotonic()
    topic=next((x for x in topics_for_section(payload.section)if x.id==payload.topic_id),None)
    if not topic:raise HTTPException(404,'Вопрос не найден')
    context=None
    if payload.section!='auth':
        context=get_auth_context(request,db)
        require_csrf(request,context,db)
    elif payload.material:
        raise HTTPException(404,'Материал недоступен')
    material=None
    if payload.step_id and not payload.material:raise HTTPException(422,"Для этапа нужен материал")
    if payload.material:
        ref=payload.material
        # Pair membership checked independently of version so stale refs yield 409.
        refs=materials_for_section(payload.section,db=db,today=_today())
        if not any((x['kind'],x['id'])==(ref.kind,ref.id)for x in refs):
            raise HTTPException(404,'Материал недоступен в этом разделе')
        material=public_step(ref.model_dump(),payload.step_id,db=db,today=_today())
    fragment=material or PublicExplanation('help',topic.id,'v1',topic.label,topic.fallback)
    example=prepared_example(payload.material.model_dump(),db=db,today=_today()) if payload.material else None
    fallback=example if payload.format=="example" and example else fragment.text
    result={'source':'authored','text':fallback}
    settings=request.app.state.settings
    enabled={s.strip()for s in settings.cloud_ai_sections.split(',')if s.strip()}
    if context and settings.cloud_ai_enabled and settings.gemini_api_key and payload.section in enabled:
        try:
            reserve_cloud_call(db,context.user,request)
            result=explain_public_fragment(fragment,fallback=fallback,api_key=settings.gemini_api_key,model=settings.gemini_model,format=payload.format,prepared_example=example)
        except HTTPException as error:
            if error.status_code!=429:raise
            db.rollback()
    metric=None
    if context:
        metric=AssistantRequest(user_id=context.user.id,section=payload.section,topic_id=topic.id,
            material_kind=material.kind if material else None,material_id=material.id if material else None,
            material_version=material.version if material else None,source=result['source'],prompt_version=PROMPT_VERSION,
            model=settings.gemini_model if result['source']=='cloud_ai' else '',latency_ms=round((monotonic()-started)*1000))
        db.add(metric);db.commit()
    return {'request_id':metric.id if metric else None,'source':result['source'],'text':result['text'],
            'material':{k:v for k,v in asdict(material).items()if k!='text'} if material else None,
            'format':payload.format,'example_available':bool(example),
            'check_available':bool(checks_for_material(payload.material.model_dump(),db=db,today=_today())) if payload.material else False,
            'next_actions':next_actions(payload.section,payload.material.model_dump() if payload.material else None),
            'links':topic.links,'notice':'Справочная помощь. Не является индивидуальной медицинской или финансовой рекомендацией.' if payload.section in ('sport','nutrition','calories','finance')else None}

@router.post('/feedback')
def feedback(payload: FeedbackRequest,request: Request,db: Session=Depends(get_db)):
    context=get_auth_context(request,db);require_csrf(request,context,db)
    item=db.scalar(select(AssistantRequest).where(AssistantRequest.id==payload.request_id).with_for_update())
    if not item or item.user_id!=context.user.id:raise HTTPException(404,'Запрос не найден')
    if item.helped is not None:raise HTTPException(409,'Оценка уже сохранена')
    item.helped=payload.helped;db.commit()
    return {'saved':True}

@router.get('/report')
def report(request: Request,user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    if request.app.state.settings.environment not in ('development','test'):raise HTTPException(404,'Отчёт недоступен')
    rows=db.scalars(select(AssistantRequest).where(AssistantRequest.user_id==user.id)).all()
    groups={}
    for row in rows:
        key=(row.section,row.topic_id,row.material_kind,row.material_id,row.material_version)
        groups.setdefault(key,[]).append(row)
    def percentile(values,p):return sorted(values)[round((len(values)-1)*p)]
    return {'total':len(rows),'groups':[{'section':k[0],'topic_id':k[1],'material_kind':k[2],'material_id':k[3],'material_version':k[4],
        'total':len(v),'fallback_count':sum(x.source=='authored'for x in v),'helped':sum(x.helped is True for x in v),
        'not_helped':sum(x.helped is False for x in v),'p50_ms':percentile([x.latency_ms for x in v],.5),'p95_ms':percentile([x.latency_ms for x in v],.95)}for k,v in groups.items()]}

class StudyContext(Strict):
    plan_id: str=Field(max_length=36)
    lesson_id: str=Field(max_length=60)
class CheckIssue(Strict):
    section: str=Field(max_length=24)
    material: MaterialRef
    step_id: str | None=Field(default=None,max_length=40)
    study_context: StudyContext | None=None
class CheckAnswer(Strict):
    token: str=Field(max_length=4000)
    option_id: str=Field(max_length=40)


def _check_context(db,user,activity,ref):
    if activity:
        from app.study import owned_plan
        plan=owned_plan(db,user.id,activity['plan_id'])
        if plan.archived_at or activity['lesson_id'] not in plan.lesson_ids or ref!={'kind':'lesson','id':plan.course_id+':'+activity['lesson_id'],'version':plan.version}:
            raise HTTPException(409,'Контекст занятия изменился')

@router.post('/checks/issue')
def issue_check(payload:CheckIssue,request:Request,db:Session=Depends(get_db)):
    import jwt,uuid
    from datetime import timedelta
    from app.db import utc_now
    from app.assistant_learning import check_digest,material_digest
    from app.rate_limit import enforce,record
    context=get_auth_context(request,db);require_csrf(request,context,db)
    enforce(db,request,'check_issue',context.user.id,account_limit=120,source_limit=1000,minutes=60)
    ref=payload.material.model_dump()
    if ref not in [{k:r[k]for k in ('kind','id','version')}for r in materials_for_section(payload.section,db=db,today=_today())]:
        raise HTTPException(409,'Материал обновлён или недоступен')
    public_step(ref,payload.step_id,db=db,today=_today())
    activity=payload.study_context.model_dump() if payload.study_context else None
    _check_context(db,context.user,activity,ref)
    checks=checks_for_material(ref,db=db,today=_today())
    record(db,request,'check_issue',context.user.id)
    if not checks:return {'available':False,'reason':'Дополнительный вопрос для этого материала пока не подготовлен.'}
    check=checks[0]
    token=jwt.encode({'purpose':'assistant-check','sub':context.user.id,'issue':str(uuid.uuid4()),'check':check.id,'version':check.version,'digest':check_digest(check),'source_digest':material_digest(ref,db=db,today=_today()),'material':ref,'activity':activity,'section':payload.section,'exp':utc_now()+timedelta(minutes=30)},request.app.state.settings.jwt_secret,algorithm='HS256')
    return {'available':True,'question':check.public(),'token':token}

@router.post('/checks/answer')
def answer_check(payload:CheckAnswer,request:Request,db:Session=Depends(get_db)):
    import jwt
    from app.models import AssistantCheckAttempt
    from app.assistant_learning import check_digest,material_digest
    context=get_auth_context(request,db);require_csrf(request,context,db)
    try:
        claim=jwt.decode(payload.token,request.app.state.settings.jwt_secret,algorithms=['HS256'])
        if claim['purpose']!='assistant-check' or claim['sub']!=context.user.id:raise ValueError()
        ref=claim['material'];_check_context(db,context.user,claim.get('activity'),ref)
        check=next((c for c in checks_for_material(ref,db=db,today=_today())if c.id==claim['check'] and c.version==claim['version']),None)
        if not check or check_digest(check)!=claim['digest'] or material_digest(ref,db=db,today=_today())!=claim['source_digest']:raise HTTPException(409,'Вопрос обновлён или отозван')
    except (jwt.PyJWTError,ValueError,KeyError,TypeError):raise HTTPException(409,'Проверка устарела. Откройте новый вопрос.')
    if payload.option_id not in [o['id']for o in check.options]:raise HTTPException(422,'Неизвестный вариант ответа')
    item=db.scalar(select(AssistantCheckAttempt).where(AssistantCheckAttempt.user_id==context.user.id,AssistantCheckAttempt.issue_id==claim['issue']))
    if item and item.option_id!=payload.option_id:raise HTTPException(409,'Этот ответ уже сохранён')
    if not item:
        from app.rate_limit import enforce,record
        enforce(db,request,'check_answer',context.user.id,account_limit=120,source_limit=1000,minutes=60)
        record(db,request,'check_answer',context.user.id)
        # record commits; lock the owner again before the uniqueness decision.
        db.scalar(select(User).where(User.id==context.user.id).with_for_update())
        db.expire_all()
        _check_context(db,context.user,claim.get('activity'),ref)
        item=db.scalar(select(AssistantCheckAttempt).where(AssistantCheckAttempt.user_id==context.user.id,AssistantCheckAttempt.issue_id==claim['issue']))
        if item and item.option_id!=payload.option_id:raise HTTPException(409,'Этот ответ уже сохранён')
        if not item:
            item=AssistantCheckAttempt(user_id=context.user.id,issue_id=claim['issue'],check_id=check.id,check_version=check.version,digest=claim['digest'],material=ref,option_id=payload.option_id,correct=payload.option_id==check.correct_option_id,activity=claim.get('activity'))
            db.add(item);db.commit()
    return {'attempt_id':item.id,'correct':item.correct,'explanation':check.explanation,'next_actions':[{**action,'label':'Продолжить занятие' if item.correct else 'Повторить материал'} for action in next_actions(claim['section'],ref)],'retry_available':True}
