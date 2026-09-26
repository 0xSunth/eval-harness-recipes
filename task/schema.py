"""Target schema, section 3 of SPEC.md.

This module validates SHAPE, never CONTENT. A record with unit="kilogramme"
is accepted here: the invariants of section 5 are computed elsewhere and
reported, not enforced. A schema that rejects a wrong record replaces a
measurement with an exception.

Shape is strict: no type coercion ("yes" is not a bool) and no unknown keys.
A silently repaired output would be scored as correct and flatter the eval.
Validate raw model output with `Recipe.model_validate_json(...)`.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Ingredient(StrictModel):
    name: str
    quantity: Decimal | None
    unit: str | None
    unit_is_metric: bool
    preparation: str | None
    variant: str | None
    alternative: str | None
    component: str | None
    needs_manager_choice: bool


class Instruction(StrictModel):
    position: int
    text: str


class Recipe(StrictModel):
    servings: int | None
    prep_time_minutes: int | None
    cook_time_minutes: int | None
    ingredients: list[Ingredient]
    instructions: list[Instruction]
