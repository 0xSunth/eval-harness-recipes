import json

import pytest
from pydantic import ValidationError

from task.schema import Ingredient, Recipe


def validate(data: dict) -> Recipe:
    """Validate like in production: raw JSON text, JSON mode."""
    return Recipe.model_validate_json(json.dumps(data))


@pytest.fixture
def valid_recipe_data() -> dict:
    return {
        "servings": 4,
        "prep_time_minutes": None,
        "cook_time_minutes": 20,
        "ingredients": [
            {
                "name": "flour",
                "quantity": 250,
                "unit": "g",
                "unit_is_metric": True,
                "preparation": None,
                "variant": None,
                "alternative": None,
                "component": None,
                "needs_manager_choice": False,
            }
        ],
        "instructions": [{"position": 1, "text": "Mix the flour"}],
    }


def test_valid_recipe_is_accepted(valid_recipe_data):
    validate(valid_recipe_data)


@pytest.mark.parametrize("field", list(Recipe.model_fields))
def test_recipe_key_is_required(valid_recipe_data, field):
    del valid_recipe_data[field]
    with pytest.raises(ValidationError):
        validate(valid_recipe_data)


@pytest.mark.parametrize("field", list(Ingredient.model_fields))
def test_ingredient_key_is_required(valid_recipe_data, field):
    del valid_recipe_data["ingredients"][0][field]
    with pytest.raises(ValidationError):
        validate(valid_recipe_data)


def test_schema_does_not_judge_content(valid_recipe_data):
    valid_recipe_data["ingredients"][0]["unit"] = "kilogramme"
    valid_recipe_data["servings"] = -2
    valid_recipe_data["instructions"] = [
        {"position": 3, "text": ""},
        {"position": 3, "text": "Duplicate position"},
    ]
    validate(valid_recipe_data)


@pytest.mark.parametrize("quantity", [250, 1.5, "250", "1.5"])
def test_quantity_accepts_number_or_numeric_string(valid_recipe_data, quantity):
    valid_recipe_data["ingredients"][0]["quantity"] = quantity
    validate(valid_recipe_data)


@pytest.mark.parametrize("quantity", ["1,5", "abc", "", True])
def test_quantity_rejects_non_numeric_values(valid_recipe_data, quantity):
    valid_recipe_data["ingredients"][0]["quantity"] = quantity
    with pytest.raises(ValidationError):
        validate(valid_recipe_data)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        pytest.param("unit_is_metric", "yes", id="bool-as-string"),
        pytest.param("unit_is_metric", 1, id="bool-as-int"),
        pytest.param("name", 5, id="str-as-int"),
    ],
)
def test_ingredient_wrong_type_is_rejected(valid_recipe_data, field, bad_value):
    valid_recipe_data["ingredients"][0][field] = bad_value
    with pytest.raises(ValidationError):
        validate(valid_recipe_data)


@pytest.mark.parametrize("bad_value", ["2", 2.0], ids=["as-string", "as-float"])
def test_position_must_be_an_integer(valid_recipe_data, bad_value):
    valid_recipe_data["instructions"][0]["position"] = bad_value
    with pytest.raises(ValidationError):
        validate(valid_recipe_data)


def test_unknown_key_is_rejected(valid_recipe_data):
    valid_recipe_data["ingredients"][0]["notes"] = "organic"
    with pytest.raises(ValidationError, match="Extra inputs"):
        validate(valid_recipe_data)
