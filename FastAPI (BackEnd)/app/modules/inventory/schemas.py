from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import SKU_PATTERN
from app.core.validation import normalize_required_text


class CompanyCategoryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    category_name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=300)

    @field_validator("category_name")
    @classmethod
    def category_name_not_blank(cls, value):
        return normalize_required_text(value, "Category name")


class ProductCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    sku: str = Field(min_length=1, max_length=60, pattern=SKU_PATTERN)
    product_name: str = Field(min_length=1, max_length=180)
    product_type: Literal["RAW_MATERIAL", "FINISHED_GOOD"]
    unit_id: int = Field(gt=0)
    category_id: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=1000)
    quantity_on_hand: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=3)
    reorder_level: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=3)

    @field_validator("product_name")
    @classmethod
    def product_name_not_blank(cls, value):
        return normalize_required_text(value, "Product name")

    @field_validator("sku")
    @classmethod
    def sku_normalized(cls, value):
        return value.upper()


class ProductUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    sku: str | None = Field(default=None, min_length=1, max_length=60, pattern=SKU_PATTERN)
    product_name: str | None = Field(default=None, min_length=1, max_length=180)
    product_type: Literal["RAW_MATERIAL", "FINISHED_GOOD"] | None = None
    unit_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=1000)
    quantity_on_hand: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=3)
    reorder_level: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=3)

    @field_validator("product_name")
    @classmethod
    def product_name_not_blank(cls, value):
        return normalize_required_text(value, "Product name") if value is not None else value

    @field_validator("sku")
    @classmethod
    def sku_normalized(cls, value):
        return value.upper() if value is not None else value


class ProductStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool
