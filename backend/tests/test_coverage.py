from app.coverage import build_report, compare_baseline, study_help_coverage


def test_study_help_coverage_names_missing_and_unreachable_questions():
    report = study_help_coverage([{"course_id": "java", "course_version": "v2", "lesson_id": "java-01", "question_index": 0},
                                  {"course_id": "java", "course_version": "v2", "lesson_id": "invented", "question_index": 0}])
    assert {"java", "go", "english", "java-backend"} <= set(report["courses"])
    assert report["courses"]["java"]["v2"]["questions_with_help"] == 1
    assert "java:v2:java-01:1" in report["missing"]
    assert "java:v2:invented:0" in report["unreachable"]


def test_coverage_report_has_no_unreachable_active_variants():
    report = build_report()
    assert report["profiles"] >= 100
    assert report["unreachable"] == {"sport": [], "recipe": [], "study": []}
    assert len(report['language_profiles']) == 16
    assert all(item['matched'] for item in report['language_profiles'])
    profiles = {(item['track'], item['language']): item for item in report['education_profiles']}
    assert len(profiles) == 18
    for level in ('A2', 'B1', 'B2'):
        assert profiles[('both', level)]['course'] == 'java'
        assert profiles[('go-reading', level)]['course'] == 'go'
        assert profiles[('reading', level)]['course'] is None
        assert profiles[('none', level)]['course'] is None
        assert all(profiles[(track, level)]['book'] for track in ('both', 'go-reading', 'reading'))
        assert all(not profiles[(track, level)]['book'] for track in ('java', 'go', 'none'))


def test_baseline_detects_unexpected_change():
    report = build_report()
    assert len(report['study_pairs']) == 9
    assert compare_baseline(report)
    changed = {**report, "signature": "different"}
    assert not compare_baseline(changed)
