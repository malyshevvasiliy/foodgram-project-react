from django.db.models import BooleanField, Case, Count, Value, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import (IsAuthenticated,
                                        IsAuthenticatedOrReadOnly,
                                        SAFE_METHODS)
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from api.filters import IngredientFilter, RecipeFilter
from api.paginator import CustomPageNumberPagination
from api.permissions import IsAdminOrReadOnly, IsAuthorOrReadOnly
from api.serializers import (IngredientSerializer, RecipeCreateSerializer,
                             RecipeListSerializer, RecipeSerializer,
                             SubscriptionSerializer, TagSerializer)
from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredients,
                            ShoppingCart, Tag)
from users.models import Subscription, User


class CustomUserViewSet(UserViewSet):
    """Viewset пользователя."""

    queryset = User.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]

    @action(detail=False, permission_classes=[IsAuthenticated])
    def subscriptions(self, request):
        """Список пользователей на которого подписан текущий пользователь."""
        queryset = User.objects.filter(following__user=request.user).annotate(
            recipes_count=Count("recipes"))
        paginator = CustomPageNumberPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = SubscriptionSerializer(
            paginated_queryset,
            many=True,
            context={
                "request": request,
                "format": self.format_kwarg,
                "view": self,
            },
        )
        return paginator.get_paginated_response(serializer.data)

    @action(
        methods=["post"],
        detail=True,
        permission_classes=[IsAuthenticated],
    )
    def subscribe(self, request, id):
        user = self.request.user
        author = get_object_or_404(User.objects.annotate(
            recipes_count=Count("recipes")), pk=id)
        if author == user:
            return Response(
                {"errors": "Вы не можете подписаться на себя."},
                status=status.HTTP_400_BAD_REQUEST
            )
        instance, created = Subscription.objects.get_or_create(
            user=user, author=author
        )
        if not created and instance:
            return Response(
                {"errors": "Вы уже были подписаны прежде"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SubscriptionSerializer(
            instance.author, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @subscribe.mapping.delete
    def delete_subscribe(self, request, id):
        user = self.request.user
        author = get_object_or_404(User, pk=id)
        subscription = Subscription.objects.filter(
            user=user,
            author=author)
        if not subscription.exists():
            return Response(
                {"errors": "Вы не были подписаны"},
                status=status.HTTP_400_BAD_REQUEST
            )
        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(ReadOnlyModelViewSet):
    """Viewset тега."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (IsAdminOrReadOnly,)


class IngredientViewSet(ReadOnlyModelViewSet):
    """Viewset ингредиента."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter


class RecipeViewSet(ModelViewSet):
    """Viewset рецепта."""

    permission_classes = (IsAuthorOrReadOnly,)
    pagination_class = CustomPageNumberPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_queryset(self):
        user_obj = self.request.user
        queryset = Recipe.objects.select_related(
            "author"
        ).prefetch_related("tags",
                           "ingredients"
                           )
        if user_obj.is_authenticated:
            return queryset.annotate(
                is_favorited=Case(
                    When(favorite__user=user_obj,
                         then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ), is_in_shopping_cart=Case(
                    When(shoppingcart__user=user_obj,
                         then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            )
        return queryset

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return RecipeSerializer
        return RecipeCreateSerializer

    def handle_action(self, request, pk, model_class):
        if request.method == "POST":
            data, status = self.create_recipe_user(request, pk, model_class)
        else:
            data, status = self.delete_recipe_user(request, pk, model_class)
        return data, status

    @action(methods=["post", "delete"], detail=True)
    def favorite(self, request, pk):
        """Действия с избранным: добавляем/удаляем рецепт."""
        data, status = self.handle_action(request, pk, Favorite)
        return Response(data, status=status)

    @action(methods=["post", "delete"], detail=True)
    def shopping_cart(self, request, pk):
        """Действия с корзиной: добавляем/удаляем рецепт."""
        data, status = self.handle_action(request, pk, ShoppingCart)
        return Response(data, status=status)

    @action(methods=["get"], detail=False,
            permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        """Выгружаем список продуктов из корзины (формат txt)."""
        ingredients = RecipeIngredients.objects.filter(
            recipe__shoppingcart__user=request.user
        ).values_list(
            "ingredient__name",
            "ingredient__measurement_unit",
            "amount"
        )
        shopping_result = {}
        for item in ingredients:
            name, measurement_unit, amount = item
            if name not in shopping_result:
                shopping_result[name] = {
                    "measurement_unit": measurement_unit,
                    "amount": amount,
                }
            else:
                shopping_result[name]["amount"] += amount
        output = ""
        for i, (name, data) in enumerate(shopping_result.items(), 1):
            output += (f"{i}. {name.capitalize()}: "
                       f"{data['amount']} {data['measurement_unit']}\n")
        response = HttpResponse(output, content_type="text/plain")
        response["Content-Disposition"] = "attachment; filename={0}".format(
            "Список_покупок.txt"
        )
        return response

    def create_recipe_user(self, request, pk, model):
        """Создание связи между рецептом и пользователем по id рецепта."""
        recipe = get_object_or_404(Recipe, id=pk)
        object_got, created = model.objects.get_or_create(recipe=recipe,
                                                          user=request.user)
        if not created:
            return (
                {"message": f"Уже есть рецепт с id = {pk}."},
                status.HTTP_400_BAD_REQUEST,
            )
        serializer = RecipeListSerializer(recipe,
                                          context={"request": request})
        return serializer.data, status.HTTP_201_CREATED

    def delete_recipe_user(self, request, pk, model):
        """Удаление связи рецепта и пользователем по id."""
        recipe = get_object_or_404(Recipe, id=pk)

        model_obj = get_object_or_404(model,
                                      user=request.user,
                                      recipe=recipe)

        model_obj.delete()
        return None, status.HTTP_204_NO_CONTENT
