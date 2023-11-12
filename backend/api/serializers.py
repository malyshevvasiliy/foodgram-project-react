import re

from djoser.serializers import UserCreateSerializer, UserSerializer
from drf_extra_fields.fields import Base64ImageField
from rest_framework.fields import BooleanField, IntegerField
from rest_framework.serializers import (ModelSerializer,
                                        PrimaryKeyRelatedField,
                                        SerializerMethodField,
                                        StringRelatedField, ValidationError)

from recipes.models import Ingredient, Recipe, RecipeIngredients, Tag
from users.models import User


class CustomUserCreateSerializer(UserCreateSerializer):
    """Сериализатор регистрации пользователей."""

    class Meta:
        model = User
        fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
            "password",

        )

    def validate_username(self, value):
        if value.lower() == "me":
            raise ValidationError('Имя пользователя "me" недопустимо.')

        if not re.match(r"^[\w.@+-]+$", value):
            raise ValidationError(
                "Имя пользователя должно содержать только буквы, цифры "
                "и следующие символы: @, ., +, -, _."
            )
        return value


class BaseUserSerializer(UserSerializer):
    """Сериализатор базовый."""

    is_subscribed = SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
            "is_subscribed",
        )

    def get_is_subscribed(self, obj):
        """Проверка подписки на просматриваемого пользователя."""
        request = self.context.get("request")
        if not request or request.user.is_anonymous:
            return False
        return obj.following.filter(user=request.user).exists()


class CustomUserSerializer(BaseUserSerializer):
    """Сериализатор информации о пользователе."""

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class SubscriptionSerializer(BaseUserSerializer):
    """Сериализатор подписки на других авторов."""

    recipes_count = IntegerField()
    recipes = SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
            "is_subscribed",
            "recipes",
            "recipes_count",
        )

    def get_recipes(self, obj):
        """Список рецептов в подписке."""
        recipes_limit = self.context["request"].GET.get("recipes_limit")
        if recipes_limit:
            recipes = obj.recipes.all()[:int(recipes_limit)]
        else:
            recipes = obj.recipes.all()
        return RecipeListSerializer(recipes, many=True, read_only=True).data


class TagSerializer(ModelSerializer):
    """Сериализатор тега."""

    class Meta:
        model = Tag
        fields = ("id", "name", "color", "slug")


class IngredientSerializer(ModelSerializer):
    """Сериализатор ингридиента."""

    class Meta:
        model = Ingredient
        fields = ("id", "name", "measurement_unit")


class RecipeIngredientSerializer(ModelSerializer):
    """Сериализатор состава ингридиентов в сохраненном рецепте."""

    id = PrimaryKeyRelatedField(source="ingredient.id", read_only=True)
    name = StringRelatedField(source="ingredient.name", read_only=True)
    measurement_unit = StringRelatedField(
        source="ingredient.measurement_unit", read_only=True
    )

    class Meta:
        model = RecipeIngredients
        fields = ("id", "name", "measurement_unit", "amount")


class RecipeIngredientCreateSerializer(ModelSerializer):
    """Сериализатор состава ингридиентов в создаваемом рецепте."""

    id = PrimaryKeyRelatedField(queryset=Ingredient.objects.all())

    class Meta:
        model = RecipeIngredients
        fields = ("id", "amount")


class RecipeListSerializer(ModelSerializer):
    """Сериализатор рецепта, для связки рецепта и пользователя."""

    class Meta:
        model = Recipe
        fields = ("id", "name", "image", "cooking_time")
        read_only_fields = ("__all__",)


class RecipeSerializer(ModelSerializer):
    """Сериализатор рецепта."""

    tags = TagSerializer(many=True)
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        source="recipeingredients", many=True, read_only=True
    )
    is_favorited = BooleanField(default=False)
    is_in_shopping_cart = BooleanField(default=False)
    image = SerializerMethodField()

    def get_image(self, obj):
        if obj.image:
            return obj.image.url
        return None

    class Meta:
        model = Recipe
        fields = (
            "id",
            "tags",
            "author",
            "ingredients",
            "is_favorited",
            "is_in_shopping_cart",
            "name",
            "image",
            "text",
            "cooking_time",
        )


class RecipeCreateSerializer(ModelSerializer):
    """Сериализатор создания и изменения рецепта."""

    image = Base64ImageField()
    ingredients = RecipeIngredientCreateSerializer(
        many=True
    )
    tags = PrimaryKeyRelatedField(many=True, queryset=Tag.objects.all())

    class Meta:
        model = Recipe
        fields = (
            "ingredients",
            "tags",
            "image",
            "name",
            "text",
            "cooking_time",
        )

    def to_representation(self, instance):
        serializer = RecipeSerializer(instance, context=self.context)
        return serializer.data

    def validate(self, data):
        """Валидность данных при создании или изменении рецепта."""
        initial_data = self.initial_data

        for field in ("tags", "ingredients", "name", "text", "cooking_time"):
            if not initial_data.get(field):
                raise ValidationError(f"Не заполнено поле `{field}`")

        ingredients = initial_data.get("ingredients")
        ingredients_set = set()
        for ingredient in ingredients:
            amount = int(ingredient.get("amount"))
            ingredient_id = ingredient.get("id")
            if not amount or not ingredient_id:
                raise ValidationError(
                    "Указать `amount` и `id` для ингредиента."
                )
            if not amount > 0:
                raise ValidationError("Количество ингредиента"
                                      "не может быть меньше 1.")
            if ingredient_id in ingredients_set:
                raise ValidationError("Необходимо исключить"
                                      "повторяющиеся ингредиенты.")
            ingredients_set.add(ingredient_id)
        return data

    def create(self, validated_data):
        """Создает новый рецепт, сохраняя связанные теги и ингредиенты."""
        validated_data["author"] = self.context["request"].user
        tags = validated_data.pop("tags")
        ingredients = validated_data.pop("ingredients")
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags)
        self.create_recipe_ingredient(recipe, ingredients)
        return recipe

    def update(self, instance, validated_data):
        """Обновляет рецепт, обновляя связанные теги и ингредиенты."""
        tags = validated_data.pop("tags")
        ingredients = validated_data.pop("ingredients")
        instance.tags.clear()
        instance.tags.set(tags)
        RecipeIngredients.objects.filter(recipe=instance).delete()
        self.create_recipe_ingredient(instance, ingredients)
        return super().update(instance, validated_data)

    def create_recipe_ingredient(self, recipe, ingredients):
        """Создает связи между рецептом и ингредиентами."""
        recipe_ingredients = []
        for ingredient in ingredients:
            recipe_ingredient = RecipeIngredients(
                recipe=recipe,
                ingredient=ingredient["id"],
                amount=ingredient["amount"]
            )
            recipe_ingredients.append(recipe_ingredient)

        RecipeIngredients.objects.bulk_create(recipe_ingredients)
