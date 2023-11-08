import re

from djoser.serializers import UserCreateSerializer, UserSerializer
from drf_extra_fields.fields import Base64ImageField

from recipes.models import Ingredient, Recipe, RecipeIngredients, Tag

from rest_framework.serializers import (ModelSerializer,
                                        PrimaryKeyRelatedField,
                                        SerializerMethodField,
                                        StringRelatedField, ValidationError)

from users.models import Subscription, User


class CustomUserCreateSerializer(UserCreateSerializer):
    """Кастомный сериализатор регистрации пользователей."""

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

    def create(self, validated_data):
        user = super().create(validated_data)
        user.set_password(validated_data['password'])
        user.save()
        return user


class CustomUserSerializer(UserSerializer):
    """Сериализатор отображения информации о пользователе."""

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


class SubscriptionSerializer(CustomUserSerializer):
    """Сериализатор подписки на других авторов."""

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
        )

    def validate_subscription(self, author):
        request = self.context["request"]

        subscription = Subscription.objects.filter(
            user=request.user, author=author
        )
        if request.method == "DELETE" and not subscription.exists():
            raise ValidationError("Подписка удалена.")

        if author == request.user:
            raise ValidationError("Вы не можете подписаться на себя.")

    def get_recipes(self, obj):
        """Список рецептов в подписке."""
        recipes_limit = self.context["request"].GET.get("recipes_limit")
        if recipes_limit:
            recipes = obj.recipes.all()[: int(recipes_limit)]
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


def user_authentication_required(func):
    """Описание."""
    def wrapper(self, obj):
        request = self.context.get("request")
        if not request or request.user.is_anonymous:
            return False
        return func(self, obj, request.user)

    return wrapper


class RecipeSerializer(ModelSerializer):
    """Сериализатор рецепта."""

    tags = TagSerializer(many=True)
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        source="recipeingredients", many=True, read_only=True
    )
    is_favorited = SerializerMethodField()
    is_in_shopping_cart = SerializerMethodField()
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

    @user_authentication_required
    def get_is_favorited(self, obj, user):
        """Является рецепт избранным для пользователя."""
        return obj.is_favorited(user)

    @user_authentication_required
    def get_is_in_shopping_cart(self, obj, user):
        """Находится рецепт в корзине пользователя."""
        return obj.is_in_shopping_cart(user)


class RecipeCreateSerializer(ModelSerializer):
    """Сериализатор создания и изменения рецепта."""

    image = Base64ImageField()
    ingredients = RecipeIngredientCreateSerializer(
        source="recipeingredients", many=True
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
        ingredients = validated_data.pop("recipeingredients")
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags)
        self.create_recipe_ingredient(recipe, ingredients)
        return recipe

    def update(self, instance, validated_data):
        """Обновляет рецепт, обновляя связанные теги и ингредиенты."""
        tags = validated_data.pop("tags")
        ingredients = validated_data.pop("recipeingredients")
        instance.ingredients.clear()
        instance.tags.clear()
        instance.tags.set(tags)
        self.create_recipe_ingredient(instance, ingredients)
        return super().update(instance, validated_data)

    def create_recipe_ingredient(self, recipe, ingredients):
        """Создает связи между рецептом и ингредиентами."""
        recipe_ingredients = []

        for ingredient in ingredients:
            ingredient = ingredient["id"]
            ingredient_amount = ingredient["amount"]
            recipe_ingredient = RecipeIngredients(
                recipe=recipe, ingredient=ingredient, amount=ingredient_amount
            )
            recipe_ingredients.append(recipe_ingredient)

        RecipeIngredients.objects.bulk_create(recipe_ingredients)
