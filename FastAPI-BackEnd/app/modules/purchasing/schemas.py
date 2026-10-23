from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PurchaseOrderStatus = Literal[
    "DRAFT", "SUBMITTED", "PARTIALLY_RECEIVED", "COMPLETED", "CANCELLED"
]


class PurchaseOrderItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)
    unit_cost: Decimal = Field(ge=0, max_digits=18, decimal_places=2)


class PurchaseOrderDraft(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    supplier_id: int = Field(gt=0)
    order_date: date = Field(default_factory=date.today)
    expected_delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    items: list[PurchaseOrderItemInput] = Field(min_length=1, max_length=100)

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value):
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.expected_delivery_date and self.expected_delivery_date < self.order_date:
            raise ValueError("Expected delivery date cannot be before the order date.")
        return self


class PurchaseOrderCancel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value):
        return value.strip() or None if value is not None else None
