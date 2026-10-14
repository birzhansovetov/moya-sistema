import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_go_course_is_complete_and_separate_from_existing_versions():
    from app.study import catalog, course, public_course
    go = json.loads((ROOT / 'backend/app/content/study-go-v1.json').read_text())
    assert course('go', 'v1') == go
    assert {item['id'] for item in catalog('v2')} == {'java', 'go', 'english', 'java-backend'}
    assert go['levels'] == ['beginner'] and len(go['lessons']) == 30
    assert len({lesson['id'] for lesson in go['lessons']}) == 30
    assert [lesson['id'] for lesson in go['lessons']] == [f'go-{n:02d}' for n in range(1, 31)]
    for lesson in go['lessons']:
        assert len(lesson['explanation']) >= 2
        assert len(' '.join(lesson['explanation'])) > 200
        assert lesson['example'].startswith('package main')
        assert lesson['practice'] and lesson['solution'] and lesson['retry_practice']
        assert len(lesson['rubric']) >= 3 and len(lesson['quiz']) >= 2
        assert all(q['answers'][0] in q['options'] for q in lesson['quiz'])
    assert 'answers' not in public_course(go)['lessons'][0]['quiz'][0]


def test_every_current_english_lesson_has_a_valid_grammar_or_review_block():
    from app.study import course, public_course
    english=course('english','v3')
    assert len(english['lessons']) == 27
    for lesson in english['lessons']:
        block=lesson['grammar']
        assert block['kind'] in {'grammar','topic_review'}, lesson['id']
        assert len(block['rule']) >= 45, lesson['id']
        assert len(block['table']['headers']) >= 2, lesson['id']
        assert all(len(row)==len(block['table']['headers']) for row in block['table']['rows']), lesson['id']
        assert len(block['examples']) >= 2, lesson['id']
        check=block['check']
        assert len(check['options']) >= 2 and len(check['explanation']) >= 20, lesson['id']
        assert check['answer'] in check['options'], lesson['id']
        assert 'answer' not in public_course(english)['lessons'][english['lessons'].index(lesson)]['grammar']['check'], lesson['id']


def test_grammar_check_does_not_expose_answer_or_create_attempt(client, mailbox):
    from test_spheres import sign_in
    csrf=sign_in(client,mailbox,'grammar@example.com')
    public=client.get('/api/study/courses/english?version=v3').json()
    check=public['lessons'][0]['grammar']['check']
    assert 'answer' not in check
    response=client.post('/api/study/grammar-check',headers={'X-CSRF-Token':csrf},json={'version':'v3','lesson_id':'en-a2-01','answer':'is study'})
    assert response.status_code==200
    assert response.json()['correct'] is False
    assert response.json()['explanation']
    state=client.get('/api/study/state/english').json()
    assert state['attempt_total']==0


def test_ready_courses_have_complete_original_lessons_and_audio():
    path = ROOT / 'backend/app/content/study-v1.json'
    assert path.exists(), 'Approved ready curricula are missing'
    courses = json.loads(path.read_text())
    assert {c['id'] for c in courses} == {'java', 'english', 'java-backend'}
    assert {c['id']: len(c['lessons']) for c in courses} == {'java': 12, 'english': 24, 'java-backend': 8}
    for course in courses:
        assert course['version'] == 'v1' and course['sources']
        ids = [l['id'] for l in course['lessons']]
        assert len(ids) == len(set(ids))
        for lesson in course['lessons']:
            assert len(lesson['explanation']) >= 2
            assert len(' '.join(lesson['explanation'])) > 200
            assert lesson['example'] and lesson['practice'] and lesson['solution']
            assert len(lesson['rubric']) >= 3
            assert len(lesson['quiz']) >= 2
            for q in lesson['quiz']:
                assert q['answers'] and q['explanation']
                assert all(a in q['options'] for a in q['answers'])
            if course['id'] == 'english':
                assert lesson['level'] in ('A2', 'B1', 'B2')
                assert len(lesson['reading'].split()) >= 65
                assert len(lesson['transcript'].split()) >= 40
                assert len(lesson['vocabulary']) >= 4
                assert lesson['speaking'] and any(q['skill'] == 'listening' for q in lesson['quiz'])
                audio = ROOT / 'frontend/public' / lesson['audio'].lstrip('/')
                assert audio.is_file() and audio.stat().st_size > 10000
    english = next(c for c in courses if c['id'] == 'english')
    assert all(sum(l['level'] == level for l in english['lessons']) == 8 for level in ('A2', 'B1', 'B2'))


def test_backend_v2_extends_without_mutating_v1():
    old = json.loads((ROOT / 'backend/app/content/study-v1.json').read_text())[-1]
    new = json.loads((ROOT / 'backend/app/content/study-backend-v2.json').read_text())
    assert old['version'] == 'v1' and len(old['lessons']) == 8
    assert new['version'] == 'v2' and len(new['lessons']) == 12
    assert new['lessons'][:8] == old['lessons']
    assert len({lesson['id'] for lesson in new['lessons']}) == 12
    for lesson in new['lessons'][8:]:
        assert len(' '.join(lesson['explanation'])) > 200
        assert lesson['example'] and lesson['practice'] and lesson['solution']
        assert len(lesson['quiz']) >= 2 and len(lesson['rubric']) >= 3
        assert all(question['answers'][0] in question['options'] for question in lesson['quiz'])


def test_latest_routes_add_capstone_practice_without_mutating_old_plans():
    from app.study import course, latest_version

    expected = {'java': ('v2', 14), 'go': ('v2', 32), 'english': ('v3', 27), 'java-backend': ('v3', 14)}
    for course_id, (version, count) in expected.items():
        old_version = 'v2' if course_id == 'java-backend' else 'v1'
        old = course(course_id, old_version)
        latest = course(course_id, version)
        assert latest_version(course_id) == version
        assert len(latest['lessons']) == count
        if course_id == 'english':
            assert [item['id'] for item in latest['lessons'][:len(old['lessons'])]] == [item['id'] for item in old['lessons']]
        else:
            assert latest['lessons'][:len(old['lessons'])] == old['lessons']
        for lesson in latest['lessons'][len(old['lessons']):]:
            assert len(' '.join(lesson['explanation'])) > 200
            assert lesson['practice'] and lesson['solution'] and lesson['retry_practice']
            assert len(lesson['rubric']) >= 3 and len(lesson['quiz']) >= 2
            assert all(question['answers'][0] in question['options'] for question in lesson['quiz'])

    for lesson in course('english', 'v2')['lessons'][-3:]:
        assert len(lesson['reading'].split()) >= 65
        assert len(lesson['transcript'].split()) >= 40
        assert len(lesson['vocabulary']) >= 4
        assert any(question['skill'] == 'listening' for question in lesson['quiz'])
        audio = ROOT / 'frontend/public' / lesson['audio'].lstrip('/')
        assert audio.is_file() and audio.stat().st_size > 10000


def test_quiz_positions_do_not_reveal_the_key():
    courses=json.loads((ROOT/'backend/app/content/study-v1.json').read_text())
    for c in courses:
        positions={q['options'].index(q['answers'][0]) for l in c['lessons'] for q in l['quiz']}
        assert len(positions)>1, f"{c['id']}: answer position gives away every answer"
    english=next(c for c in courses if c['id']=='english')
    diagnostic=[english['lessons'][i]['quiz'][0] for i in (0,1,6,9,10,13)]
    assert sum(q['options'][0] in q['answers'] for q in diagnostic)<5, 'First-option guessing must not recommend B1'


def test_follow_up_practice_is_specific_and_java_checks_are_distinct():
    courses = json.loads((ROOT / 'backend/app/content/study-v1.json').read_text())
    for course in courses:
        prompts = []
        retries = []
        for lesson in course['lessons']:
            retry = lesson.get('retry_practice', '')
            assert len(retry) >= 40, lesson['id']
            retries.append(retry)
            if course['id'] in {'java', 'java-backend'}:
                question = lesson['quiz'][1]
                assert question['prompt'] not in {'Как проверить своё решение?', 'Что сохранить как свидетельство работы?'}
                assert len(question['options']) >= 3
                assert len(question['explanation']) >= 35
                prompts.append(question['prompt'])
        assert len(retries) == len(set(retries)), course['id']
        assert len(prompts) == len(set(prompts)), course['id']
