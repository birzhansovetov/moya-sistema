from app.matching import match_survey
from app.routes.onboarding import Survey
from test_onboarding import answers


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
