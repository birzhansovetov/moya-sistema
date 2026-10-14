from fastapi.testclient import TestClient

from conftest import Mailbox
from test_tasks import create_task, login


def test_weekly_review_counts_real_actions_and_keeps_users_separate(client: TestClient, mailbox: Mailbox) -> None:
    csrf = login(client, mailbox, 'week-one@example.com')
    task_id = create_task(client, csrf).json()['id']
    assert client.post(
        f'/api/tasks/{task_id}/occurrences/2026-10-06/complete',
        json={'completed': True}, headers={'X-CSRF-Token': csrf},
    ).status_code == 200

    response = client.get('/api/calendar/weekly-review?end=2026-10-11')
    assert response.status_code == 200
    review = response.json()
    assert review['start'] == '2026-10-05'
    assert review['end'] == '2026-10-11'
    assert review['tasks'] == {'planned': 1, 'completed': 1}
    assert review['areas']['health'] == 0
    assert review['areas']['education'] == 0
    assert review['areas']['profession'] == 0
    assert review['areas']['languages'] == 0
    assert review['areas']['finance'] == 0
    assert review['areas']['personal'] == 0

    login(client, mailbox, 'week-two@example.com')
    other = client.get('/api/calendar/weekly-review?end=2026-10-11').json()
    assert other['tasks'] == {'planned': 0, 'completed': 0}
    assert all(count == 0 for count in other['areas'].values())


def test_weekly_review_rejects_future_week(client: TestClient, mailbox: Mailbox) -> None:
    login(client, mailbox, 'week@example.com')
    assert client.get('/api/calendar/weekly-review?end=2099-01-01').status_code == 422


def test_weekly_review_recommends_frequency_change_only_from_recorded_plan_progress(client, mailbox):
    from datetime import date
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models import SportPlan, User, WorkoutLog

    login(client, mailbox, 'training-review@example.com')
    with Session(client.app.state.engine) as db:
        user = db.scalar(select(User).where(User.email == 'training-review@example.com'))
        plan = SportPlan(user_id=user.id, program_id='sample', content_version='v1',
                         answers={'days_per_week': 3, 'weekdays': [1, 3, 5]},
                         program_snapshot={'title': 'Три тренировки', 'duration_weeks': 4,
                                           'sessions': [{'id': 'a'}, {'id': 'b'}, {'id': 'c'}]},
                         active_key='active', started_on=date(2026, 10, 5))
        db.add(plan)
        db.flush()
        db.add(WorkoutLog(user_id=user.id, plan_id=plan.id, workout_date=date(2026, 10, 5),
                          session_id='a', results=[], difficulty=7, note='private'))
        db.commit()
    review = client.get('/api/calendar/weekly-review?end=2026-10-11').json()
    assert review['training'] == {
        'plan_title': 'Три тренировки', 'planned': 3, 'completed': 1,
        'average_difficulty': 7, 'suggestion': 'review_frequency', 'suggested_days_per_week': 2,
        'reason': 'За неделю записана 1 из 3 запланированных тренировок. Можно попробовать 2 занятия в неделю.',
    }
    login(client, mailbox, 'training-review-other@example.com')
    assert client.get('/api/calendar/weekly-review?end=2026-10-11').json()['training'] is None


def test_weekly_review_counts_a_session_moved_within_the_same_week(client, mailbox):
    from datetime import date
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models import SportPlan, User, WorkoutLog

    login(client, mailbox, 'training-moved@example.com')
    with Session(client.app.state.engine) as db:
        user = db.scalar(select(User).where(User.email == 'training-moved@example.com'))
        plan = SportPlan(user_id=user.id, program_id='sample', content_version='v1',
                         answers={'days_per_week': 2, 'weekdays': [1, 4]},
                         program_snapshot={'title': 'Две тренировки', 'duration_weeks': 4,
                                           'sessions': [{'id': 'a'}, {'id': 'b'}]},
                         active_key='active', started_on=date(2026, 10, 5))
        db.add(plan)
        db.flush()
        for session, day in [('a', 6), ('b', 8)]:
            db.add(WorkoutLog(user_id=user.id, plan_id=plan.id, workout_date=date(2026, 10, day),
                              session_id=session, results=[], difficulty=8, note=''))
        db.commit()
    review = client.get('/api/calendar/weekly-review?end=2026-10-11').json()['training']
    assert review['completed'] == 2
    assert review['suggestion'] == 'keep'
    assert 'нагрузка ощущалась высокой' in review['reason']


def test_training_feedback_is_saved_per_plan_and_week_and_can_be_changed(client, mailbox):
    from datetime import date
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models import SportPlan, User

    csrf = login(client, mailbox, 'training-feedback@example.com')
    with Session(client.app.state.engine) as db:
        user = db.scalar(select(User).where(User.email == 'training-feedback@example.com'))
        db.add(SportPlan(user_id=user.id, program_id='sample', content_version='v1',
                         answers={'weekdays': [1, 4]},
                         program_snapshot={'title': 'Две тренировки', 'duration_weeks': 4,
                                           'sessions': [{'id': 'a'}, {'id': 'b'}]},
                         active_key='active', started_on=date(2026, 10, 5)))
        db.commit()
    url = '/api/calendar/weekly-review/feedback'
    headers = {'X-CSRF-Token': csrf}
    first = client.put(url, json={'end': '2026-10-11', 'rating': 'too_easy'}, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()['rating'] == 'too_easy'
    assert client.get('/api/calendar/weekly-review?end=2026-10-11').json()['training']['feedback'] == 'too_easy'
    changed = client.put(url, json={'end': '2026-10-11', 'rating': 'too_hard'}, headers=headers)
    assert changed.status_code == 200
    assert client.get('/api/calendar/weekly-review?end=2026-10-11').json()['training']['feedback'] == 'too_hard'
    with Session(client.app.state.engine) as db:
        from app.models import TrainingFeedback
        assert len(db.scalars(select(TrainingFeedback)).all()) == 1

    login(client, mailbox, 'training-feedback-other@example.com')
    assert client.get('/api/calendar/weekly-review?end=2026-10-11').json()['training'] is None
    assert client.put(url, json={'end': '2026-10-11', 'rating': 'fits'}, headers=headers).status_code == 403


def test_training_feedback_rejects_invalid_rating_or_week_without_active_plan(client, mailbox):
    csrf = login(client, mailbox, 'training-feedback-empty@example.com')
    headers = {'X-CSRF-Token': csrf}
    url = '/api/calendar/weekly-review/feedback'
    assert client.put(url, json={'end': '2026-10-11', 'rating': 'unsafe'}, headers=headers).status_code == 422
    assert client.put(url, json={'end': '2026-10-11', 'rating': 'fits'}, headers=headers).status_code == 404
    assert client.put(url, json={'end': '2099-01-01', 'rating': 'fits'}, headers=headers).status_code == 422
