def sport_module():
    from app import sport
    return sport


def answers(**overrides):
    sport = sport_module()
    values = {
        "goal": "fat_loss_muscle_focus",
        "level": "beginner",
        "place": "home",
        "equipment": [],
        "days_per_week": 2,
        "minutes_per_session": 35,
        "limitations": False,
        "weekdays": [1, 4],
    }
    values.update(overrides)
    return sport.SportAnswers(**values)


def test_complete_catalog_has_three_distinct_places_and_usable_guides():
    catalog = sport_module().load_sport_catalog()
    assert {item["place"] for item in catalog["programs"]} == {"home", "outdoor", "gym"}
    assert len({item["id"] for item in catalog["programs"]}) >= 15
    assert len(catalog["exercises"]) >= 10
    for program in catalog["programs"]:
        assert program["duration_weeks"] >= 4
        assert len(program["sessions"]) >= max(program["supported_days"])
        assert len(program["sources"]) >= 1
        for session in program["sessions"]:
            assert session["warmup"] and session["cooldown"]
            assert len(session["work"]) >= 4
            for item in session["work"]:
                assert item["sets"] >= 1 and item["rest_seconds"] >= 30
                assert item["exercise_id"] in catalog["exercises"]
    for exercise in catalog["exercises"].values():
        assert exercise["technique"] and exercise["common_errors"]
        assert exercise["easier_version"] and exercise["substitution"]
        assert exercise["source"].startswith("https://")


def test_match_selects_entire_program_for_each_supported_place():
    sport = sport_module()
    cases = [
        ("home", [], "fat_loss_home_beginner_v1"),
        ("outdoor", ["low_bar", "bench"], "fat_loss_outdoor_beginner_v1"),
        ("gym", ["machines"], "fat_loss_gym_beginner_v1"),
    ]
    for place, equipment, expected in cases:
        result = sport.select_program(answers(place=place, equipment=equipment, minutes_per_session=40))
        assert result["program"]["id"] == expected
        assert result["reasons"] == []
        assert len(result["sessions"]) == 2


def test_band_programs_add_home_and_outdoor_choices_with_taught_movements():
    sport = sport_module()
    catalog = sport.load_sport_catalog()
    assert len(catalog["programs"]) >= 8
    for place, equipment in (("home", ["bands"]), ("outdoor", ["bands", "bench"])):
        result = sport.select_program(answers(place=place, equipment=equipment, minutes_per_session=40))
        assert result["program"]["id"] == f"fat_loss_{place}_bands_beginner_v1"
        assert len(result["sessions"]) == 2
        ids = {work["exercise_id"] for session in result["sessions"] for work in session["work"]}
        assert "band_row" in ids and "band_chest_press" in ids
        assert all(catalog["exercises"][item]["source"].startswith("https://") for item in ids)
    assert sport.select_program(answers(place="outdoor", equipment=["bands"], minutes_per_session=40))["program"] is None


def test_intermediate_programs_match_place_equipment_and_have_real_progression():
    sport=sport_module()
    for place,equipment in (("home",["bands"]),("outdoor",["low_bar","bench"]),("gym",["machines"])):
        result=sport.select_program(answers(level="intermediate",place=place,equipment=equipment,minutes_per_session=50))
        program=result["program"]
        assert program and program["level"]=="intermediate" and program["place"]==place
        assert all(all(item["sets"]==3 for item in session["work"]) for session in result["sessions"])
        assert any("сопротивлен" in step for step in program["progression"])
    assert sport.select_program(answers(level="intermediate",place="home",equipment=[],minutes_per_session=50))["program"] is None


def test_match_respects_days_time_and_missing_equipment():
    sport = sport_module()
    assert len(sport.select_program(answers(days_per_week=3, weekdays=[1, 3, 5]))["sessions"]) == 3
    assert sport.select_program(answers(days_per_week=4, weekdays=[1, 2, 4, 6]))["program"] is None
    assert sport.select_program(answers(minutes_per_session=20))["program"] is None
    assert sport.select_program(answers(place="gym", equipment=["machines"], minutes_per_session=35))["program"]["min_minutes"] == 25
    missing = sport.select_program(answers(place="outdoor", equipment=["bench"]))
    assert missing["program"] is None
    assert any("оборуд" in reason.lower() for reason in missing["reasons"])


def test_four_day_split_matches_gym_and_barbell_home_with_real_sessions():
    sport = sport_module()
    cases = (("gym", ["machines"], "gym"), ("home", ["barbell", "dumbbells"], "home"))
    for place, equipment, slug in cases:
        result = sport.select_program(answers(place=place, equipment=equipment, days_per_week=4,
            minutes_per_session=60, weekdays=[1, 2, 4, 6]))
        assert result["program"]["id"] == f"fat_loss_{slug}_beginner_split_v1"
        assert [session["id"] for session in result["sessions"]] == ["PUSH", "PULL", "LEGS", "UPPER"]
        assert all(session["estimated_minutes"] <= 60 for session in result["sessions"])
        if place == "home":
            assert "floor_press" not in {work["exercise_id"] for session in result["sessions"] for work in session["work"]}
    unavailable = sport.select_program(answers(place="home", equipment=[], days_per_week=4,
        minutes_per_session=60, weekdays=[1, 2, 4, 6]))
    assert unavailable["program"] is None
    assert "штанга" in " ".join(unavailable["reasons"]).lower()


def test_outdoor_four_day_programs_split_upper_and_lower_work():
    sport = sport_module()
    for goal in ('fat_loss_muscle_focus', 'maintain', 'strength_gain'):
        for level in ('beginner', 'intermediate'):
            selected = sport.select_program(answers(goal=goal, level=level, place='outdoor',
                equipment=['low_bar', 'bench', 'bands'], days_per_week=4,
                minutes_per_session=90, weekdays=[1, 2, 4, 6]))
            program = selected['program']
            assert program is not None, (goal, level, selected['reasons'])
            assert len(selected['sessions']) == 4
            assert all(session['estimated_minutes'] <= program['min_minutes'] for session in selected['sessions'])
            assert set(program['required_equipment']) <= {'low_bar', 'bench', 'bands'}
            upper = {item['exercise_id'] for item in selected['sessions'][0]['work']}
            lower = {item['exercise_id'] for item in selected['sessions'][1]['work']}
            assert {'supported_row', 'incline_pushup'} <= upper
            assert {'bodyweight_squat', 'step_up'} <= lower


def test_intermediate_gym_split_retains_barbell_lifts_from_supplied_plan():
    sport = sport_module()
    selected = sport.select_program(answers(place="gym", equipment=["machines"], level="intermediate",
        days_per_week=4, minutes_per_session=60, weekdays=[1, 2, 4, 6]))
    sessions = {item["id"]: item for item in selected["sessions"]}
    assert sessions["PUSH"]["work"][0]["exercise_id"] == "barbell_bench_press"
    assert sessions["LEGS"]["work"][0]["exercise_id"] == "barbell_squat"


def test_short_programs_are_selected_for_each_place_without_replacing_full_programs():
    sport = sport_module()
    for place, equipment in (("home", []), ("outdoor", ["low_bar", "bench"]), ("gym", ["machines"])):
        short = sport.select_program(answers(place=place, equipment=equipment, minutes_per_session=25))
        full = sport.select_program(answers(place=place, equipment=equipment, minutes_per_session=45))
        assert short["program"]["min_minutes"] == 25
        assert full["program"]["min_minutes"] >= 35
        assert len(short["sessions"]) == 2
        assert all(session["estimated_minutes"] <= 25 for session in short["sessions"])


def test_match_requires_rest_day_between_strength_sessions():
    sport = sport_module()
    assert sport.select_program(answers(weekdays=[1, 2]))["program"] is None
    assert sport.select_program(answers(weekdays=[1, 7]))["program"] is None
    assert sport.select_program(answers(weekdays=[1, 3]))["program"] is not None


def test_match_never_silently_ignores_goal_level_or_limitations():
    sport = sport_module()
    assert sport.select_program(answers(goal="strength_gain"))["program"] is None
    assert sport.select_program(answers(level="intermediate", place="home", equipment=["bands"], minutes_per_session=50))["program"]["level"] == "intermediate"
    assert sport.select_program(answers(level="intermediate", place="home", equipment=[], minutes_per_session=50))["program"] is None
    blocked = sport.select_program(answers(limitations=True))
    assert blocked["program"] is None
    assert any("огранич" in reason.lower() for reason in blocked["reasons"])


def test_maintain_and_strength_routes_match_goal_and_equipment():
    sport = sport_module()
    for goal in ("maintain", "strength_gain"):
        for place, equipment in (("home", ["barbell", "dumbbells"]), ("outdoor", ["low_bar", "bench"]), ("gym", ["machines"])):
            for level in ("beginner", "intermediate"):
                result = sport.select_program(answers(goal=goal, place=place, equipment=equipment,
                    level=level, minutes_per_session=60))
                assert result["program"] is not None, (goal, place, level)
                assert result["program"]["goal"] == goal
                assert result["program"]["level"] == level
                assert len(result["sessions"]) == 2
    assert sport.select_program(answers(goal="strength_gain", level="intermediate", equipment=[]))["program"] is None


def test_four_day_goal_routes_cover_home_and_gym():
    sport = sport_module()
    for goal in ("maintain", "strength_gain"):
        for place, equipment in (("home", ["barbell", "dumbbells"]), ("gym", ["machines"])):
            for level in ("beginner", "intermediate"):
                result = sport.select_program(answers(goal=goal, place=place, equipment=equipment,
                    level=level, days_per_week=4, minutes_per_session=60, weekdays=[1, 2, 4, 6]))
                assert result["program"] is not None, (goal, place, level)
                assert len(result["sessions"]) == 4
                if place == "gym":
                    exercise_ids = {work["exercise_id"] for session in result["sessions"] for work in session["work"]}
                    assert not any(exercise_id.startswith(("barbell_", "dumbbell_", "incline_dumbbell_")) for exercise_id in exercise_ids)


def test_three_day_home_goal_routes_use_three_distinct_sessions():
    sport = sport_module()
    for goal in ("maintain", "strength_gain"):
        for level in ("beginner", "intermediate"):
            result = sport.select_program(answers(goal=goal, place="home", level=level,
                equipment=["barbell", "dumbbells"], days_per_week=3, minutes_per_session=60,
                weekdays=[1, 3, 5]))
            assert result["program"] is not None, (goal, level)
            assert len({session["id"] for session in result["sessions"]}) == 3


def test_full_home_routes_cover_two_three_and_four_days_for_eight_weeks():
    sport = sport_module()
    catalog = sport.load_sport_catalog()
    routes = [item for item in catalog["programs"] if item.get("series") == "home_progressive_8w"]
    assert {tuple(item["supported_days"]) for item in routes} == {(2,), (3,), (4,)}
    assert all(item["duration_weeks"] == 8 and len(item["progression"]) == 8 for item in routes)
    assert all(len(item["sessions"]) == item["supported_days"][0] for item in routes)
    assert all(len({entry["exercise_id"] for session in item["sessions"] for entry in session["work"]}) >= 6 for item in routes)
    for days, weekdays in ((2, [1, 4]), (3, [1, 3, 5]), (4, [1, 2, 4, 6])):
        result = sport.select_program(answers(level="intermediate", place="home", equipment=["barbell", "dumbbells"],
            days_per_week=days, minutes_per_session=60, weekdays=weekdays))
        assert result["program"] is not None
        assert result["program"]["series"] == "home_progressive_8w"


def test_every_valid_sport_choice_has_a_program_or_a_ready_material():
    sport = sport_module()
    for goal in ("fat_loss_muscle_focus", "maintain", "strength_gain"):
        for level in ("beginner", "intermediate"):
            for place, equipment in (("home", []), ("outdoor", []), ("outdoor", ["low_bar", "bench"]), ("gym", ["machines"])):
                for minutes in (10, 25, 45):
                    for weekdays in ([1], [1, 2], [1, 4], [1, 3, 5]):
                        for limitations in (False, True):
                            selected = sport.select_program(answers(goal=goal, level=level, place=place, equipment=equipment,
                                minutes_per_session=minutes, days_per_week=len(weekdays), weekdays=weekdays, limitations=limitations))
                            if selected["program"] is None:
                                assert selected["material"]["area"] == "sport"
                                assert selected["material"]["steps"] and selected["material"]["sources"]
                            else:
                                assert selected["program"]["sessions"]


def test_exercise_metadata_and_program_coverage_are_explicit():
    from app.sport_coverage import audit_coverage
    catalog = sport_module().load_sport_catalog()
    report = audit_coverage(catalog['programs'], catalog['exercises'])
    assert report['missing_exercise_metadata'] == []
    assert report['unknown_exercises'] == []
    excluded = {item['id'] for item in report['incomplete_programs']}
    excluded.update(item.split(':')[0] for item in report['incompatible_exercises'] if ':' in item)
    assert all(item['id'] not in excluded for item in report['available_combinations'])
    assert report['available_combinations']
    assert report['unavailable_combinations']


def test_home_without_equipment_has_real_pull_or_explicit_gap():
    from app.sport_coverage import audit_coverage
    catalog = sport_module().load_sport_catalog()
    report = audit_coverage(catalog['programs'], catalog['exercises'])
    no_equipment = [item for item in report['available_combinations'] if item['place'] == 'home' and not item['equipment']]
    assert all('pull' in item['movement_patterns'] for item in no_equipment)


def test_regular_experience_has_distinct_full_programs_for_each_place():
    sport = sport_module()
    for place, equipment in (
        ('home', ['barbell', 'dumbbells']),
        ('outdoor', ['low_bar', 'bench', 'bands']),
        ('gym', ['machines']),
    ):
        selected = sport.select_program(answers(level='regular', place=place, equipment=equipment,
                                                 days_per_week=4, minutes_per_session=60,
                                                 weekdays=[1, 2, 4, 6]))
        assert selected['program'] is not None
        assert selected['program']['level'] == 'regular'
        assert selected['program']['place'] == place
        assert len(selected['sessions']) == 4


def test_regular_with_limitations_never_gets_universal_program():
    selected = sport_module().select_program(answers(level='regular', place='gym', equipment=['machines'],
                                               days_per_week=4, minutes_per_session=60,
                                               weekdays=[1, 2, 4, 6], limitations=True))
    assert selected['program'] is None
    assert selected['material']['id'] == 'sport-limitations'


def test_regular_routes_cover_all_three_goals_without_unavailable_equipment():
    sport = sport_module()
    for goal in ('fat_loss_muscle_focus', 'maintain', 'strength_gain'):
        for place, equipment in (('home', ['barbell', 'dumbbells']),
                                 ('outdoor', ['low_bar', 'bench', 'bands']),
                                 ('gym', ['machines'])):
            selected = sport.select_program(answers(goal=goal, level='regular', place=place,
                equipment=equipment, days_per_week=4, minutes_per_session=60,
                weekdays=[1, 2, 4, 6]))
            assert selected['program'] is not None, (goal, place, selected['reasons'])
            assert selected['program']['goal'] == goal


def test_regular_has_complete_two_and_three_day_routes():
    sport = sport_module()
    for days, weekdays in ((2, [1, 4]), (3, [1, 3, 5])):
        for goal in ('fat_loss_muscle_focus', 'maintain', 'strength_gain'):
            for place, equipment in (('home', ['barbell', 'dumbbells']),
                                     ('outdoor', ['low_bar', 'bench', 'bands']),
                                     ('gym', ['machines'])):
                selected = sport.select_program(answers(goal=goal, level='regular', place=place,
                    equipment=equipment, days_per_week=days, minutes_per_session=60,
                    weekdays=weekdays))
                assert selected['program'] is not None, (days, goal, place, selected['reasons'])
                assert len(selected['sessions']) == days


def test_new_experience_never_offers_incomplete_legacy_program():
    selected = sport_module().select_program(answers(level='returning', place='home',
        equipment=[], days_per_week=2, minutes_per_session=35, weekdays=[1, 4]))
    assert selected['program'] is None
    assert selected['reasons']
