"""
Unit tests for Lessons Learned engine.
"""

from unifyops import UnifyOpsClient, LessonLearned


def test_lessons_learned_search():
    client = UnifyOpsClient(org_id="plant-delta")
    lesson = LessonLearned(
        id="L-001",
        title="Centrifugal Pump Impeller Cavitation",
        equipment_tag="P-204",
        category="Maintenance",
        summary="NPSH margin was insufficient causing impeller pitting.",
        corrective_action="Increase suction head pressure.",
        preventative_measure="Install continuous suction pressure monitoring transmitter.",
    )
    client.lessons.add_lesson(lesson)

    results = client.lessons.search_lessons(query="cavitation", equipment_tag="P-204")
    assert len(results) == 1
    assert results[0].title == "Centrifugal Pump Impeller Cavitation"
