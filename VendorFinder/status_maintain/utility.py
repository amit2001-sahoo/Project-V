from enum import Enum
from django.db import models

class BaseUserModel(models.Model):
    created_on = models.DateTimeField(auto_now_add=True)
    created_by = models.PositiveIntegerField(null=True)
    modified_on = models.DateTimeField(null=True, blank=True)
    modified_by = models.PositiveIntegerField(null=True)

    objects = models.Manager()

    class Meta:
        abstract = True

class BaseEnum(Enum):
    def __init__(self, code, description):
        self.CODE = code
        self.description = description

    @classmethod
    def get_enum_name(cls, code):
        for item in cls:
            if item.CODE == code:
                return item.description
        return None

    @classmethod
    def get_enum_id(cls, description):
        for item in cls:
            if item.description == description:
                return item.CODE
        return None

class UserType(BaseEnum):
    CUSTOMER = (5, "CUSTOMER")
    VENDOR = (10, "VENDOR")

class AttendanceStatus(BaseEnum):
    OPEN = (5, "OPEN")
    CLOSED = (10, "CLOSED")