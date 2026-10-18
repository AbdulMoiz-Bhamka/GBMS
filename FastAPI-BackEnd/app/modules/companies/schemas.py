from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import COMPANY_CODE_PATTERN
from app.core.validation import normalize_email, normalize_required_text


class CompanyCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    company_name: str = Field(min_length=1, max_length=160)
    company_code: str = Field(min_length=2, max_length=30, pattern=COMPANY_CODE_PATTERN)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=400)

    @field_validator("company_name")
    @classmethod
    def company_name_not_blank(cls, value):
        return normalize_required_text(value, "Company name")

    @field_validator("company_code")
    @classmethod
    def company_code_normalized(cls, value):
        return value.upper()

    @field_validator("email")
    @classmethod
    def company_email_valid(cls, value):
        return normalize_email(value)

    @field_validator("phone", "address")
    @classmethod
    def optional_text_trimmed(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None


class CompanyUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    company_name: str | None = Field(default=None, min_length=1, max_length=160)
    company_code: str | None = Field(default=None, min_length=2, max_length=30, pattern=COMPANY_CODE_PATTERN)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=400)

    @field_validator("company_name")
    @classmethod
    def company_name_not_blank(cls, value):
        return normalize_required_text(value, "Company name") if value is not None else value

    @field_validator("company_code")
    @classmethod
    def company_code_normalized(cls, value):
        return value.upper() if value is not None else value

    @field_validator("email")
    @classmethod
    def company_email_valid(cls, value):
        return normalize_email(value)

    @field_validator("phone", "address")
    @classmethod
    def optional_text_trimmed(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None


class CompanyStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_status: Literal["ACTIVE", "INACTIVE"]
