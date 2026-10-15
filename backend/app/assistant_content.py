"""Allowlisted public material adapters. Never reads personal records."""
from dataclasses import dataclass
from datetime import date
from importlib.resources import files
import json
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.content_review import is_revoked, reviewed_variant
from app.study import course, latest_version
from app.sport import load_sport_catalog
from app.nutrition import load_recipes

SECTIONS = ('today','sections','education','java','go','profession','languages','english','kazakh','korean','turkish','spanish','health','sport','nutrition','calories','finance','reading','personal','tasks','calendar','profile','onboarding','auth')
COURSES = {'java':'java','go':'go','profession':'java-backend',**{s:s for s in ('english','kazakh','korean','turkish','spanish')}}

@dataclass(frozen=True)
class PublicExplanation:
    kind: str
    id: str
    version: str
    title: str
    text: str

@dataclass(frozen=True)
class AssistantTopic:
    id: str
    section: str
    label: str
    fallback: str
    links: tuple[dict, ...] = ()


def _read(name):
    return json.loads(files('app.content').joinpath(name).read_text(encoding='utf-8'))


def topics_for_section(section: str) -> tuple[AssistantTopic, ...]:
    if section not in SECTIONS:
        raise HTTPException(404, 'Раздел не найден')
    return tuple(AssistantTopic(x['id'],section,x['label'],x['fallback'],tuple(x['links']))
                 for x in _read('assistant-topics-v1.json') if x['section']==section)


def _public_items(section, today):
    # Each tuple: kind, ID, current version, title, authored text. Explicit projections only.
    if section in ('finance','reading','personal','sport'):
        for g in _read('guides.json'):
            if g['area']==section:
                yield ('guide',g['id'],str(g.get('version','v1')),g['title'], '\n'.join([g['intro'],*g['steps'],g['example']]))
    if section=='reading':
        for b in _read('book_suggestions.json'):
            yield ('book',b['id'],str(b.get('version','v1')),b['title'],f"{b['title']}. {b['author']}. {b['description']}")
    if section=='sport':
        cat=load_sport_catalog()
        for key,x in cat['exercises'].items():
            yield ('exercise',key,_read('exercises.json')['version'],x['name'], '\n'.join(x[k] for k in ('technique','common_errors','easier_version','substitution')))
    if section=='nutrition':
        cat=load_recipes()
        for x in cat['recipes']:
            if reviewed_variant('recipe',x,today):
                ingredients='; '.join(f"{cat['foods'][i['food_id']]['name']}: {i['grams']} г ({i['state']})" for i in x['ingredients'])
                yield ('recipe',x['id'],_read('recipes.json')['version'],x['name'],f"{x['name']}. Порций: {x['servings']}. {ingredients}. "+' '.join(x['steps']))
    if section in COURSES:
        c=course(COURSES[section],latest_version(COURSES[section]))
        for x in c['lessons']:
            # No examples/solutions/practice/check/quiz: theory only, not generated answers.
            text='\n'.join(x.get('explanation',[]))
            if text:
                yield ('lesson',c['id']+':'+x['id'],c['version'],x['title'],text)


def materials_for_section(section: str, *, db: Session, today: date) -> list[dict]:
    topics_for_section(section)
    return [dict(kind=k,id=i,version=v,title=t) for k,i,v,t,_ in _public_items(section,today)
            if not is_revoked(db,k,i,v)]


def resolve_material(kind: str, id: str, version: str, *, db: Session, today: date) -> PublicExplanation:
    for section in SECTIONS:
        for k,i,v,t,text in _public_items(section,today):
            if (k,i)==(kind,id):
                if v!=version:
                    raise HTTPException(409,'Материал обновлён. Выберите его заново.')
                # Existing course revocation uses course ID; check both levels.
                if is_revoked(db,k,i,v) or (k=='lesson' and is_revoked(db,'course',i.split(':')[0],v)):
                    raise HTTPException(404,'Материал недоступен')
                return PublicExplanation(k,i,v,t,text[:6000])
    raise HTTPException(404,'Материал не найден')
