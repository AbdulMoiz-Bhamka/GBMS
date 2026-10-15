from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validation import normalize_email, normalize_required_text


class CompanyUserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    role_name: Literal["COMPANY_ADMIN", "SUB_ADMIN", "INVENTORY_USER"] = "COMPANY_ADMIN"

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
