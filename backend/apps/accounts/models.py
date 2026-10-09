from uuid import uuid4

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, display_name, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        normalized_email = self.normalize_email(email).strip().casefold()
        user = self.model(email=normalized_email, display_name=display_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, display_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", User.Roles.PARTICIPANT)
        return self._create_user(email, display_name, password, **extra_fields)

    def create_superuser(self, email, display_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Roles.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")
        return self._create_user(email, display_name, password, **extra_fields)


class User(AbstractUser):
    class Roles(models.TextChoices):
        PARTICIPANT = "participant", "Участник"
        ADMIN = "admin", "Администратор"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=80)
    role = models.CharField(max_length=16, choices=Roles.choices, default=Roles.PARTICIPANT)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]
    objects = UserManager()

    def __str__(self) -> str:
        return self.display_name
