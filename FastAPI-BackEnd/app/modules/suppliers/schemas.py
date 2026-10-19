from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import SUPPLIER_CODE_PATTERN
from app.core.validation import normalize_email, normalize_required_text


class SupplierFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    supplier_code: str = Field(min_length=2, max_length=40, pattern=SUPPLIER_CODE_PATTERN)
    supplier_name: str = Field(min_length=1, max_length=180)
    contact_person: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    alternate_phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=400)
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    tax_registration_number: str | None = Field(default=None, max_length=50)
    payment_terms: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("supplier_code")
    @classmethod
    def normalize_supplier_code(cls, value):
        return value.upper()

    @field_validator("supplier_name")
    @classmethod
    def validate_supplier_name(cls, value):
        return normalize_required_text(value, "Supplier name")

    @field_validator("email")
    @classmethod
    def validate_supplier_email(cls, value):
        return normalize_email(value)

    @field_validator(
        "contact_person", "phone", "alternate_phone", "address", "city",
        "country", "tax_registration_number", "payment_terms", "notes",
    )
    @classmethod
    def trim_optional_text(cls, value):
        if value is None:
            return None
        return value.strip() or None


class SupplierCreate(SupplierFields):
    pass


class SupplierUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    supplier_code: str | None = Field(default=None, min_length=2, max_length=40, pattern=SUPPLIER_CODE_PATTERN)
    supplier_name: str | None = Field(default=None, min_length=1, max_length=180)
    contact_person: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    alternate_phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=400)
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    tax_registration_number: str | None = Field(default=None, max_length=50)
    payment_terms: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("supplier_code")
    @classmethod
    def normalize_supplier_code(cls, value):
        return value.upper() if value is not None else None

    @field_validator("supplier_name")
    @classmethod
    def validate_supplier_name(cls, value):
        return normalize_required_text(value, "Supplier name") if value is not None else None

    @field_validator("email")
    @classmethod
    def validate_supplier_email(cls, value):
        return normalize_email(value)

    @field_validator(
        "contact_person", "phone", "alternate_phone", "address", "city",
        "country", "tax_registration_number", "payment_terms", "notes",
    )
    @classmethod
    def trim_optional_text(cls, value):
        if value is None:
            return None
        return value.strip() or None


class SupplierStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_status: Literal["ACTIVE", "INACTIVE"]
