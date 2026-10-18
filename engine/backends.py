from typing import Protocol


class InputBackend(Protocol):
    def bind_choices(self, callback):
        """callback(0) pour gauche, callback(1) pour droite."""
        ...


class DisplayBackend(Protocol):
    def show_scene(self, scene):
        ...

    def show_outcome(self, outcome):
        ...
