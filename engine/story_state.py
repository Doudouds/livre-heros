from dataclasses import dataclass, field
from typing import Any


@dataclass
class StoryState:
    hero_type: str
    mandatory_location: str
    chosen_item: str
    seed: int
    arc_id: str = ""
    current_scene: str = ""
    current_act: int = 1
    story_progress: int = 0
    estimated_seconds: float = 0.0
    visited_locations: set[str] = field(default_factory=set)
    met_characters: set[str] = field(default_factory=set)
    allies: set[str] = field(default_factory=set)
    enemies: set[str] = field(default_factory=set)
    flags: set[str] = field(default_factory=set)
    inventory: set[str] = field(default_factory=set)
    previous_outcomes: list[dict[str, Any]] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    success_count: int = 0
    complication_count: int = 0
    failure_count: int = 0
    conclusion: str | None = None
