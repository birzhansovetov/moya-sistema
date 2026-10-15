"""Reviewed companion practice, public examples and allowlisted actions."""
from dataclasses import dataclass,asdict
from datetime import date
from importlib.resources import files
import hashlib,json
from typing import Literal
from fastapi import HTTPException
from app.assistant_content import resolve_material,_read,COURSES
from app.content_review import is_revoked
from app.study import course,LATEST_VERSIONS,normalize_answer
ExplainFormat = Literal['default','simple','example','steps','brief']
FORMATS = ('default','simple','example','steps','brief')
ROUTES={'today':'/','sections':'/sections','education':'/education','java':'/education/java','go':'/education/go','profession':'/profession','languages':'/languages',**{s:'/languages/'+s for s in ('english','kazakh','korean','turkish','spanish')},'health':'/health','sport':'/health/sport','nutrition':'/health/nutrition','calories':'/health/calories','finance':'/finance','reading':'/education/reading','personal':'/personal','tasks':'/tasks','calendar':'/calendar','profile':'/profile','onboarding':'/onboarding','auth':'/login'}

@dataclass(frozen=True)
class LearningCheck:
    id:str
    version:str
    materials:list[dict]
    chapter_title:str
    title:str
    prompt:str
    options:list[dict]
    correct_option_id:str
    explanation:str
    review:dict
    def public(self):
        return {k:getattr(self,k)for k in ('id','version','prompt','options','chapter_title')}


def all_checks():
    return tuple(LearningCheck(**x)for x in _read('assistant-learning-v1.json')['checks'])


def check_digest(check):
    return hashlib.sha256(json.dumps(asdict(check),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def checks_for_material(ref,*,db,today):
    resolve_material(ref['kind'],ref['id'],ref['version'],db=db,today=today)
    identity = {key: ref[key] for key in ('kind', 'id', 'version')}
    return tuple(c for c in all_checks()if identity in c.materials
        and date.fromisoformat(c.review['checked_at'])<=today<=date.fromisoformat(c.review['recheck_by'])
        and not is_revoked(db,'assistant_check',c.id,c.version))


def prepared_example(ref,*,db,today):
    resolve_material(ref['kind'],ref['id'],ref['version'],db=db,today=today)
    if ref['kind']=='lesson':
        cid,lid=ref['id'].split(':',1)
        l=next(x for x in course(cid,ref['version'])['lessons']if x['id']==lid)
        return l.get('example')or None
    if ref['kind']=='guide':
        return next(x for x in _read('guides.json')if x['id']==ref['id']).get('example')or None
    if ref['kind']=='recipe':
        return next(x for x in _read('recipes.json')['recipes']if x['id']==ref['id'])['steps'][0]
    return None


def public_step(ref,step_id,*,db,today):
    fragment=resolve_material(ref['kind'],ref['id'],ref['version'],db=db,today=today)
    if not step_id:return fragment
    from dataclasses import replace
    if ref['kind']=='recipe' and step_id.startswith('step-'):
        try:index=int(step_id[5:])
        except ValueError:raise HTTPException(422,'Неверный этап')
        recipe=next(x for x in _read('recipes.json')['recipes']if x['id']==ref['id'])
        if not 0<=index<len(recipe['steps']):raise HTTPException(422,'Неверный этап')
        return replace(fragment,text=f"Шаг {index+1} исходного рецепта: "+recipe['steps'][index])
    if ref['kind']=='exercise' and step_id in ('technique','sets','rest'):return fragment
    if ref['kind']=='lesson' and step_id in ('theory','example','vocabulary','practice','check'):return fragment
    raise HTTPException(422,'Неверный этап материала')


def next_actions(section,material=None):
    target=ROUTES[section]
    if material and material['kind']=='recipe':target+='#recipe-'+material['id']
    if material and material['kind']=='exercise':target+='#sport-library'
    return [{'id':'return_material','label':'Вернуться к материалу' if material else 'Открыть раздел','kind':'route','to':target}]


def learning_coverage():
    bank=all_checks();refs={(r['id'],r['version'])for c in bank for r in c.materials if r['kind']=='lesson'}
    uncovered=[];orphans=[];duplicates=[];courses={};known=set()
    for cid,version in LATEST_VERSIONS.items():
        c=course(cid,version);groups={}
        for lesson in c['lessons']:
            identity=(cid+':'+lesson['id'],version);known.add(identity)
            groups.setdefault(lesson.get('chapter')or lesson['id'],[]).append(identity)
            for check in bank:
                if any((r['id'],r['version'])==identity for r in check.materials):
                    if any(normalize_answer(check.prompt)==normalize_answer(q['prompt'])for q in lesson['quiz']):duplicates.append(check.id)
        uncovered.extend(cid+':'+chapter for chapter,items in groups.items()if not any(x in refs for x in items))
        courses[cid]={'chapters':len(groups),'mapped_lessons':sum((cid+':'+x['id'],version)in refs for x in c['lessons']),'total_lessons':len(c['lessons'])}
    orphans=[r['id']for c in bank for r in c.materials if r['kind']=='lesson'and(r['id'],r['version'])not in known]
    return {'checks':len(bank),'courses':courses,'uncovered_chapters':uncovered,'orphans':orphans,'duplicate_main_prompts':duplicates,'exercise_checks':sum(c.materials[0]['kind']=='exercise'for c in bank),'recipe_checks':sum(c.materials[0]['kind']=='recipe'for c in bank)}


def material_digest(ref, *, db, today):
    fragment=resolve_material(ref['kind'],ref['id'],ref['version'],db=db,today=today)
    return hashlib.sha256(json.dumps(asdict(fragment),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
