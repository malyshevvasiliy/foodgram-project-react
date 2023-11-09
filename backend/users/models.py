from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db.models import (CASCADE, CharField, CheckConstraint, EmailField,
                              F, ForeignKey, Model, Q, UniqueConstraint)


class User(AbstractUser):
    """Модель пользователя."""

    email = EmailField(
        verbose_name="Адрес электронной почты",
        max_length=settings.MAX_LENGTH_EMAIL,
        unique=True,
    )
    username = CharField(
        verbose_name="Логин",
        max_length=settings.MAX_LENGTH_USERNAME,
        unique=True,
    )
    first_name = CharField(
        verbose_name="Имя",
        max_length=settings.MAX_LENGTH_USERNAME,
    )
    last_name = CharField(
        verbose_name="Фамилия",
        max_length=settings.MAX_LENGTH_USERNAME,
    )
    password = CharField(
        verbose_name="Пароль", max_length=settings.MAX_LENGTH_USERNAME
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "password", "first_name", "last_name"]

    class Meta:
        ordering = ["id"]
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.username


class Subscription(Model):
    """Модель подписки пользователей."""

    user = ForeignKey(
        User,
        on_delete=CASCADE,
        related_name="follower",
        verbose_name="Подписчик",
    )
    author = ForeignKey(
        User, on_delete=CASCADE, related_name="following", verbose_name="Автор"
    )

    class Meta:
        ordering = ["-id"]
        verbose_name = "Подписка"
        verbose_name_plural = "Подписки"

        constraints = [
            UniqueConstraint(
                fields=["user", "author"], name="Uniqueness_subscribers"
            ),
            CheckConstraint(
                check=~Q(user=F("author")),
                name="Restriction_subscription_yourself",
            ),
        ]

    def __str__(self) -> str:
        return f"Подписка {self.user.username} на {self.author.username}."
