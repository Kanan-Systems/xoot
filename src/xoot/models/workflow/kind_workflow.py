"""The workflow for one item kind: its states, defaults and transitions."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from xoot.models.fields import StateName
from xoot.models.workflow.category import Category
from xoot.models.workflow.state_spec import StateSpec

MAX_STATES = 64
REQUIRED_DEFAULTS = frozenset({Category.OPEN, Category.DONE, Category.DROPPED})


class KindWorkflow(BaseModel):
    """
    States for one item kind.

    Defaults name the state the system uses when it moves an item into a
    category (new items, completion, reopening, drops). When transitions is None any
    state may move to any other; otherwise only the listed moves are allowed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    states: tuple[StateSpec, ...] = Field(min_length=1, max_length=MAX_STATES)
    defaults: dict[Category, StateName]
    transitions: dict[StateName, tuple[StateName, ...]] | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Check names are unique and every reference names a real state."""
        categories = {spec.name: spec.category for spec in self.states}
        if len(categories) != len(self.states):
            raise ValueError("state names must be unique")
        missing = sorted(REQUIRED_DEFAULTS - self.defaults.keys())
        if missing:
            raise ValueError(f"missing default states for: {', '.join(missing)}")
        for category, state in self.defaults.items():
            if categories.get(state) != category:
                raise ValueError(
                    f"default {category} state {state!r} is not in the {category} category"
                )
        for source, targets in (self.transitions or {}).items():
            unknown = sorted({source, *targets} - categories.keys())
            if unknown:
                raise ValueError(f"transitions name unknown states: {unknown}")
        return self

    def category_of(self, state: str) -> Category | None:
        """
        Look up the category of a state.

        Args:
            - state (str): a state name.

        Returns:
            - category (Category | None): its category, or None if the state
              is not part of this workflow.
        """
        for spec in self.states:
            if spec.name == state:
                return spec.category
        return None

    def default_state(self, category: Category) -> str:
        """
        Return the state the system uses for a category.

        Args:
            - category (Category): open, done or dropped.

        Returns:
            - state (str): the configured default state.

        Raises:
            - KeyError: the category has no default.
        """
        return self.defaults[category]

    def allows(self, source: str, target: str) -> bool:
        """
        Tell whether a user-requested move between states is allowed.

        Args:
            - source (str): current state.
            - target (str): requested state.

        Returns:
            - allowed (bool): True when unrestricted, unchanged, or listed.
        """
        if self.transitions is None or source == target:
            return True
        return target in self.transitions.get(source, ())
