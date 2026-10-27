from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validation import normalize_email, normalize_required_text

CompanyRole = Literal["SUB_ADMIN", "INVENTORY_USER", "WORKER"]


class CompanyUserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    role_name: Literal["COMPANY_ADMIN", "SUB_ADMIN", "INVENTORY_USER", "WORKER"] = "COMPANY_ADMIN"
    # None means no per-user grants were supplied. Company Admin access is
    # always role-based; for other roles, an explicit empty list is restrictive.
    permission_codes: list[str] | None = Field(default=None, max_length=20)

    @field_validator("full_name")
    @classmethod
    def full_name_not_blank(cls, value):
        return normalize_required_text(value, "Full name")

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        result = normalize_email(value)
        if result is None:
            raise ValueError("Enter a valid email address.")
        return result

    @field_validator("permission_codes")
    @classmethod
    def permission_codes_unique(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError("Do not select the same permission more than once.")
        return value


class CompanyUserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    username: str | None = Field(default=None, min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    role_name: CompanyRole | None = None
    permission_codes: list[str] | None = Field(default=None, max_length=20)

    @field_validator("username", "full_name")
    @classmethod
    def optional_text_not_blank(cls, value, info):
        if value is None:
            return None
        return normalize_required_text(value, info.field_name.replace("_", " ").title())

    @field_validator("email")
    @classmethod
    def optional_email_valid(cls, value):
        if value is None:
            return None
        result = normalize_email(value)
        if result is None:
            raise ValueError("Enter a valid email address.")
        return result

    @field_validator("permission_codes")
    @classmethod
    def optional_permission_codes_unique(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError("Do not select the same permission more than once.")
        return value


class CompanyUserStatusUpdate(BaseModel):
    account_status: Literal["ACTIVE", "INACTIVE"]
