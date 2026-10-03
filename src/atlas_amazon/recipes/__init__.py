"""Recipe-driven domain behavior: fields, limits, rules, weights, research priorities."""

from atlas_amazon.recipes.loader import RecipeError, available_recipes, load_recipe
from atlas_amazon.recipes.schema import (
    KEYWORD_SIGNALS,
    KNOWN_CHECKS,
    BackendSpec,
    FieldSpec,
    Recipe,
    RuleSpec,
)

__all__ = [
    "KEYWORD_SIGNALS",
    "KNOWN_CHECKS",
    "BackendSpec",
    "FieldSpec",
    "Recipe",
    "RecipeError",
    "RuleSpec",
    "available_recipes",
    "load_recipe",
]
