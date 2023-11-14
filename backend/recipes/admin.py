from django.contrib.admin import ModelAdmin, TabularInline, register
from import_export.admin import ImportExportModelAdmin
from import_export.resources import ModelResource

from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredients,
                            ShoppingCart, Tag)


class RecipeIngredientInline(TabularInline):
    """Ингридиенты в рецептах."""

    model = RecipeIngredients
    extra = 0
    min_num = 1


@register(Recipe)
class RecipeAdmin(ModelAdmin):
    """Управление рецептами в админке."""

    inlines = [RecipeIngredientInline]

    list_display = ("id",
                    "name",
                    "author",
                    "text",
                    "cooking_time",
                    "pub_date")
    list_display_links = ("id",
                          "name",
                          "author",
                          "text",
                          "cooking_time",
                          "pub_date")
    search_fields = ("name",)
    list_filter = ("author", "tags")
    empty_value_display = "-пусто-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "author").prefetch_related("tags", "ingredients")


@register(Tag)
class TagAdmin(ModelAdmin):
    """Управление тегами в админке."""

    list_display = ("id", "name", "color", "slug")
    list_display_links = ("id", "name", "color", "slug")
    search_fields = ("name", "slug",)
    empty_value_display = "-пусто-"


class IngredientResource(ModelResource):
    """Необходим для импорта ингредиентов."""

    class Meta:
        model = Ingredient


@register(Ingredient)
class IngredientAdmin(ImportExportModelAdmin):
    """Управление ингредиентами в админке."""

    list_display = ("id", "name", "measurement_unit")
    list_display_links = ("id", "name", "measurement_unit")
    search_fields = ("name",)
    list_filter = ("measurement_unit",)
    empty_value_display = "-пусто-"
    resource_class = IngredientResource


@register(RecipeIngredients)
class RecipeIngredientsAdmin(ModelAdmin):
    """Управление ингредиентами в рецептах в админке."""

    list_display = ("id", "recipe", "ingredient", "amount")
    list_display_links = ("id", "recipe", "ingredient", "amount")
    list_filter = ("recipe", "ingredient")
    empty_value_display = "-пусто-"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "recipe").select_related("ingredient")


@register(Favorite)
class FavoriteAdmin(ModelAdmin):
    """Управление избранными рецептами в админке."""

    list_display = ("id", "user", "recipe")
    list_display_links = ("id", "user", "recipe")
    list_filter = ("user", "recipe")
    empty_value_display = "-пусто-"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "user").select_related("recipe")


@register(ShoppingCart)
class ShoppingCartAdmin(ModelAdmin):
    """Управление корзиной покупок в админке."""

    list_display = ("id", "user", "recipe")
    list_display_links = ("id", "user", "recipe")
    list_filter = ("user", "recipe")
    empty_value_display = "-пусто-"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "user").select_related("recipe")
