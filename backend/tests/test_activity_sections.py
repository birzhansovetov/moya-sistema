import pytest
from app.routes.calendar import study_area

@pytest.mark.parametrize('course,expected', [('java','profession'),('go','profession'),('java-backend','profession'),('english','languages'),('kazakh','languages'),('korean','languages'),('turkish','languages'),('spanish','languages'),('unknown',None)])
def test_completed_course_belongs_to_its_visible_section(course,expected):
    assert study_area(course) == expected
