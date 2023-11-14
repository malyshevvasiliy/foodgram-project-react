from django.contrib.admin import ModelAdmin, register
from django.contrib.auth.admin import UserAdmin

from .models import Subscription, User


@register(User)
class UserAdmin(UserAdmin):
    """Управление пользователями в админке."""

    fieldset = ("id", "username", "email", "first_name", "last_name")
    list_display = ("id", "username", "email", "first_name", "last_name")
    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
    )
    list_filter = (
        "username",
        "email",
    )
    empty_value_display = "-пусто-"


@register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    """Управление подписками в админке."""

    list_display = ("id", "user", "author")
    list_display_links = ("id", "user", "author")
    list_filter = ("user", "author")
    empty_value_display = "-пусто-"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "user").select_related("author")
