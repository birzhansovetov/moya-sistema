from itertools import product
from app.sport import SportAnswers, load_sport_catalog, select_program
from app.sport_coverage import audit_coverage


def test_all_advertised_combinations_have_complete_programs():
    c = load_sport_catalog()
    audit = audit_coverage(c['programs'], c['exercises'])
    assert not audit['unavailable_combinations']
    assert not audit['incompatible_exercises']
    assert not audit['incomplete_programs']


def test_returning_gym_two_days_forty_five_minutes_has_full_program():
    result = select_program(SportAnswers(goal='fat_loss_muscle_focus', level='returning',
        place='gym', equipment=['machines'], days_per_week=2,
        minutes_per_session=45, weekdays=[1,4]))
    assert result['program'] is not None, result['reasons']
    assert len(result['sessions']) == 2


def test_every_new_experience_goal_place_matches_with_appropriate_equipment():
    equipment = {'home':['bands','barbell','dumbbells'], 'outdoor':['low_bar','bench','bands'],
                 'gym':['machines','barbell','dumbbells','bench']}
    for level, goal, place, days in product(('returning','irregular','regular'),
            ('fat_loss_muscle_focus','maintain','strength_gain'), equipment, (2,3,4)):
        result = select_program(SportAnswers(goal=goal, level=level, place=place,
            equipment=equipment[place], days_per_week=days, minutes_per_session=60,
            weekdays={2:[1,4],3:[1,3,5],4:[1,2,4,6]}[days]))
        assert result['program'] is not None, (level,goal,place,days,result['reasons'])


def test_no_workout_repeats_an_exercise_id():
    c = load_sport_catalog()
    for program in c['programs']:
        for session in program['sessions']:
            ids = [work['exercise_id'] for work in session['work']]
            assert len(ids) == len(set(ids)), (program['id'],session['id'])


def test_every_supported_week_includes_all_five_movement_patterns():
    c = load_sport_catalog()
    for program in c['programs']:
        for days in program['supported_days']:
            patterns = {c['exercises'][w['exercise_id']]['movement_pattern']
                        for session in program['sessions'][:days] for w in session['work']}
            assert {'squat','hinge','push','pull','core'} <= patterns, (program['id'],days,patterns)
