from app.matching import match_survey
from app.routes.onboarding import Survey
from test_onboarding import answers
import pytest


@pytest.mark.parametrize('language', ['kazakh', 'korean', 'turkish', 'spanish'])
def test_new_language_is_a_reviewed_candidate(client, mailbox, language):
    from test_spheres import sign_in

    sign_in(client, mailbox, f'{language}-reviewed@example.com')
    payload = answers()
    payload['languages'].update(course_id=language, level='A1')
    with client.app.state.sessionmaker() as db:
        matched = match_survey(Survey.model_validate(payload), 'Asia/Almaty', db)
    assert matched['candidates_by_sphere']['languages'][0]['id'] == language


def test_full_sport_list_is_stable_and_has_digests(client, mailbox):
    from test_spheres import sign_in

    sign_in(client, mailbox, "matching@example.com")
    survey = Survey.model_validate(answers())
    with client.app.state.sessionmaker() as db:
        first = match_survey(survey, "Asia/Almaty", db)
        again = match_survey(survey, "Asia/Almaty", db)
    assert first["candidates_by_sphere"] == again["candidates_by_sphere"]
    for candidates in first["candidates_by_sphere"].values():
        for candidate in candidates:
            assert candidate["id"] and candidate["version"] and len(candidate["digest"]) == 64


def test_limitations_do_not_assign_sport(client, mailbox):
    from test_spheres import sign_in

    sign_in(client, mailbox, "limited@example.com")
    payload = answers()
    payload["health"]["sport"]["limitations"] = True
    with client.app.state.sessionmaker() as db:
        result = match_survey(Survey.model_validate(payload), "Asia/Almaty", db)
    assert result["candidates_by_sphere"]["health"] == []
    assert result["areas"]["health"]["sport"]["status"] == "unavailable"


@pytest.mark.parametrize("experience,equipment,minutes,days,weekdays", [
    ("returning", ["bands"], 45, 2, [1, 4]),
    ("irregular", ["bands"], 50, 2, [1, 4]),
    ("regular", ["barbell", "dumbbells"], 60, 4, [1, 2, 4, 6]),
])
def test_new_experience_has_reviewed_full_sport_choice(client, mailbox, experience, equipment, minutes, days, weekdays):
    from test_spheres import sign_in

    sign_in(client, mailbox, f"{experience}-matching@example.com")
    payload = answers()
    payload["health"]["sport"].update({
        "level": experience, "place": "home", "equipment": equipment,
        "days_per_week": days, "minutes_per_session": minutes, "weekdays": weekdays,
    })
    with client.app.state.sessionmaker() as db:
        result = match_survey(Survey.model_validate(payload), "Asia/Almaty", db)
    assert result["areas"]["health"]["sport"]["status"] == "matched"
    assert result["candidates_by_sphere"]["health"]
    if experience == "regular":
        assert all("regular" in item["id"] for item in result["candidates_by_sphere"]["health"])
