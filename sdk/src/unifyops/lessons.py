"""
Lessons Learned & Failure Intelligence Engine for UnifyOps SDK.
"""

import uuid
from typing import Dict, List, Optional
from unifyops.models import LessonLearned
from unifyops.store import KnowledgeStore


class LessonsEngine:
    """Engine for capturing, querying, and synthesizing plant operational lessons learned and incident intelligence."""

    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store
        self._lessons: Dict[str, LessonLearned] = {}

    def add_lesson(self, lesson: LessonLearned) -> str:
        """Add a new lesson learned entry."""
        if not lesson.id:
            lesson.id = str(uuid.uuid4())
        self._lessons[lesson.id] = lesson
        return lesson.id

    def search_lessons(self, query: str, equipment_tag: Optional[str] = None) -> List[LessonLearned]:
        """Search lessons by text query or equipment tag."""
        results: List[LessonLearned] = []
        q_lower = query.lower()
        tag_upper = equipment_tag.upper() if equipment_tag else None

        for lesson in self._lessons.values():
            if tag_upper and lesson.equipment_tag and lesson.equipment_tag.upper() != tag_upper:
                continue

            content = f"{lesson.title} {lesson.summary} {lesson.corrective_action}".lower()
            if not query or q_lower in content:
                results.append(lesson)

        return results

    def list_all(self) -> List[LessonLearned]:
        """List all lessons learned."""
        return list(self._lessons.values())
