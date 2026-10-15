from datetime import date
import pytest
from sqlalchemy.orm import Session
from app.assistant_learning import learning_coverage,checks_for_material,check_digest,prepared_example,next_actions,FORMATS
from app.assistant_content import materials_for_section
from app.models import ContentRevocation


def test_all_curriculum_chapters_have_explicit_checks():
    report=learning_coverage()
    assert set(report['courses'])=={'java','go','java-backend','english','kazakh','korean','turkish','spanish'}
    assert not report['uncovered_chapters'] and not report['orphans'] and not report['duplicate_main_prompts']
    assert report['checks']>250


def test_no_solution_in_public_projection_and_digest_changes(client):
    with Session(client.app.state.engine) as db:
        ref=materials_for_section('java',db=db,today=date(2026,10,16))[0]
        check=checks_for_material(ref,db=db,today=date(2026,10,16))[0]
        public=check.public()
        assert 'correct_option_id' not in public and 'explanation' not in public
        assert len({x['id'] for x in public['options']})==len(public['options'])
        old=check_digest(check)
        from dataclasses import replace
        assert check_digest(replace(check,explanation='changed'))!=old
        db.add(ContentRevocation(kind='study',item_id='java',version=ref['version'],reason='withdrawn',active=True));db.commit()
        with pytest.raises(Exception):checks_for_material(ref,db=db,today=date(2026,10,16))


def test_examples_and_actions_are_public(client):
    assert len(FORMATS)==5
    with Session(client.app.state.engine)as db:
        ref=materials_for_section('java',db=db,today=date(2026,10,16))[0]
        example=prepared_example(ref,db=db,today=date(2026,10,16))
        assert example and 'quiz' not in example
        for section in ['today','finance','nutrition','sport','java','auth']:
            actions=next_actions(section)
            assert actions and all(x['kind']=='route' and x['to'].startswith('/') and not x['to'].startswith('//')for x in actions)


def test_no_orphan_or_duplicate_checks():
    from app.assistant_learning import all_checks
    bank=all_checks()
    assert len({c.id for c in bank})==len(bank)
    for check in bank:
        assert len(check.options)>=3
        assert len({o['id']for o in check.options})==len(check.options)
        assert len({o['label']for o in check.options})==len(check.options)
        assert check.correct_option_id in [o['id']for o in check.options]
        assert check.explanation and check.review['source']
        assert date.fromisoformat(check.review['checked_at']) < date.fromisoformat(check.review['recheck_by'])
