"""Report catalog gaps before a workout is offered to a user."""

from __future__ import annotations

from itertools import product

PATTERNS = {'squat', 'hinge', 'push', 'pull', 'core'}
EXPERIENCES = ('beginner', 'intermediate', 'regular')
PLACES = ('home', 'outdoor', 'gym')
GOALS = ('fat_loss_muscle_focus', 'maintain', 'strength_gain')
DAYS = (2, 3, 4)
REQUIRED = ('movement_pattern', 'places', 'required_equipment', 'experience',
            'technique', 'common_errors', 'easier_version', 'substitution', 'source')


def audit_coverage(programs: list[dict], exercises: dict[str, dict]) -> dict:
    missing, unknown, incompatible, incomplete = [], [], [], []
    available = []
    for exercise_id, exercise in exercises.items():
        if any(field not in exercise or (field != 'required_equipment' and not exercise[field]) for field in REQUIRED):
            missing.append(exercise_id)
        for option in exercise.get('alternatives', []):
            other = exercises.get(option['exercise_id'])
            if not other or not set(option.get('places', [])) <= set(other.get('places', [])) or not set(other.get('required_equipment', [])) <= set(option.get('required_equipment', [])):
                incompatible.append(f"{exercise_id}:{option['exercise_id']}")
    for program in programs:
        patterns = set()
        equipment = set(program.get('required_equipment', []))
        program_incompatible = False
        for session in program.get('sessions', []):
            for work in session.get('work', []):
                exercise = exercises.get(work['exercise_id'])
                if exercise is None:
                    unknown.append(f"{program['id']}:{work['exercise_id']}")
                    continue
                patterns.add(exercise.get('movement_pattern'))
                if program['place'] not in exercise.get('places', []) or not set(exercise.get('required_equipment', [])) <= equipment or program['level'] not in exercise.get('experience', []):
                    incompatible.append(f"{program['id']}:{work['exercise_id']}")
                    program_incompatible = True
        if not PATTERNS <= patterns:
            incomplete.append({'id': program['id'], 'missing_patterns': sorted(PATTERNS - patterns)})
            continue
        if program_incompatible:
            continue
        for days in program['supported_days']:
            week_patterns = {exercises[work['exercise_id']].get('movement_pattern')
                             for session in program['sessions'][:days] for work in session['work']
                             if work['exercise_id'] in exercises}
            if not PATTERNS <= week_patterns:
                incomplete.append({'id': program['id'], 'days': days,
                                   'missing_patterns': sorted(PATTERNS - week_patterns)})
                continue
            available.append({'id': program['id'], 'experience': program['level'], 'place': program['place'],
                              'goal': program['goal'], 'days': days, 'equipment': sorted(equipment),
                              'movement_patterns': sorted(week_patterns)})
    keys = {(item['experience'], item['place'], item['goal'], item['days']) for item in available}
    unavailable = [{'experience': experience, 'place': place, 'goal': goal, 'days': days}
                   for experience, place, goal, days in product(EXPERIENCES, PLACES, GOALS, DAYS)
                   if (experience, place, goal, days) not in keys]
    return {'missing_exercise_metadata': sorted(missing), 'unknown_exercises': sorted(unknown),
            'incompatible_exercises': sorted(set(incompatible)), 'incomplete_programs': incomplete,
            'available_combinations': available, 'unavailable_combinations': unavailable}
