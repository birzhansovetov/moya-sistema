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
    if payload.material:
        ref=payload.material
        # Pair membership checked independently of version so stale refs yield 409.
        refs=materials_for_section(payload.section,db=db,today=_today())
        if not any((x['kind'],x['id'])==(ref.kind,ref.id)for x in refs):
            raise HTTPException(404,'Материал недоступен в этом разделе')
        material=resolve_material(ref.kind,ref.id,ref.version,db=db,today=_today())
    fragment=material or PublicExplanation('help',topic.id,'v1',topic.label,topic.fallback)
    fallback=fragment.text
    result={'source':'authored','text':fallback}
    settings=request.app.state.settings
    enabled={s.strip()for s in settings.cloud_ai_sections.split(',')if s.strip()}
    if context and settings.cloud_ai_enabled and settings.gemini_api_key and payload.section in enabled:
        try:
            reserve_cloud_call(db,context.user,request)
            result=explain_public_fragment(fragment,fallback=fallback,api_key=settings.gemini_api_key,model=settings.gemini_model)
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
