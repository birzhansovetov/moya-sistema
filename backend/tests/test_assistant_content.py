from datetime import date
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.assistant_content import SECTIONS, topics_for_section, materials_for_section, resolve_material
from app.models import ContentRevocation


def test_every_section_has_short_help():
    assert len(SECTIONS) == 24
    for section in SECTIONS:
        items = topics_for_section(section)
        assert 3 <= len(items) <= 5
        assert len({x.id for x in items}) == len(items)
        assert all(x.fallback and x.label for x in items)


@pytest.mark.parametrize('section', ['sport','nutrition','finance','reading','java','go','profession','english','kazakh','korean','turkish','spanish'])
def test_materials_are_current_public_and_not_quizzes(client, section):
    with Session(client.app.state.engine) as db:
        items = materials_for_section(section, db=db, today=date(2026,10,15))
        assert items
        ref = items[0]
        material = resolve_material(ref['kind'],ref['id'],ref['version'],db=db,today=date(2026,10,15))
        assert material.text and material.title
        assert '"answers"' not in material.text and '"quiz"' not in material.text
        with pytest.raises(HTTPException) as caught:
            resolve_material(ref['kind'],ref['id'],'stale',db=db,today=date(2026,10,15))
        assert caught.value.status_code == 409
        db.add(ContentRevocation(kind=ref['kind'],item_id=ref['id'],version=ref['version'],reason='test',active=True))
        db.commit()
        with pytest.raises(HTTPException) as caught:
            resolve_material(ref['kind'],ref['id'],ref['version'],db=db,today=date(2026,10,15))
        assert caught.value.status_code == 404


def test_no_private_or_unknown_material(client):
    with Session(client.app.state.engine) as db:
        for kind in ['personal_book','diary','quiz','attempt','answer']:
            with pytest.raises(HTTPException):
                resolve_material(kind,'anything','v1',db=db,today=date(2026,10,15))
