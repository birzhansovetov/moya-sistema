from datetime import date

from sqlalchemy import select

from app.models import Expense, ExpenseCategory, PersonalEntry, Task, TaskCompletion, User
from test_tasks import login


def test_streak_counts_saved_actions_and_waits_until_end_of_today(client, mailbox, monkeypatch):
    monkeypatch.setattr('app.routes.calendar.local_date', lambda timezone: date(2026, 10, 11))
    login(client, mailbox, 'first@example.com')
    with client.app.state.sessionmaker() as db:
        user = db.scalar(select(User).where(User.email == 'first@example.com'))
        task = Task(user_id=user.id, title='Готово', due_date=date(2026, 10, 9))
        db.add(task)
        db.flush()
        db.add(TaskCompletion(task_id=task.id, occurrence_date=date(2026, 10, 9)))
        db.add(PersonalEntry(user_id=user.id, kind='diary', title='Запись', date=date(2026, 10, 10),
                             create_key='diary-one', create_fingerprint='a'))
        db.add(PersonalEntry(user_id=user.id, kind='event', title='План', date=date(2026, 10, 11),
                             create_key='event-one', create_fingerprint='b'))
        db.commit()

    response = client.get('/api/calendar/streak')
    assert response.status_code == 200
    assert response.json()['current_streak'] == 2
    assert response.json()['today_active'] is False
    assert [day['date'] for day in response.json()['days'] if day['active']] == ['2026-10-09', '2026-10-10']

    with client.app.state.sessionmaker() as db:
        user = db.scalar(select(User).where(User.email == 'first@example.com'))
        category = ExpenseCategory(user_id=user.id, name='Еда', name_key='еда')
        db.add(category)
        db.flush()
        db.add(Expense(user_id=user.id, category_id=category.id, amount_minor=100, currency='KZT',
                       expense_date=date(2026, 10, 11), create_key='expense-one', create_fingerprint='c'))
        db.commit()
    result = client.get('/api/calendar/streak').json()
    assert result['current_streak'] == 3
    assert result['today_active'] is True


def test_streak_is_private_and_resets_after_missed_day(client, mailbox, monkeypatch):
    monkeypatch.setattr('app.routes.calendar.local_date', lambda timezone: date(2026, 10, 11))
    login(client, mailbox, 'first@example.com')
    with client.app.state.sessionmaker() as db:
        user = db.scalar(select(User).where(User.email == 'first@example.com'))
        db.add(PersonalEntry(user_id=user.id, kind='diary', title='Старое', date=date(2026, 10, 9),
                             create_key='diary-two', create_fingerprint='a'))
        db.commit()
    assert client.get('/api/calendar/streak').json()['current_streak'] == 0
    login(client, mailbox, 'second@example.com')
    result = client.get('/api/calendar/streak').json()
    assert result['current_streak'] == 0
    assert all(not day['active'] for day in result['days'])
