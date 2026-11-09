from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReceiptItemInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    purchase_order_item_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    received_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)
    lot_number: str | None = Field(default=None, min_length=1, max_length=60)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("lot_number", "notes")
    @classmethod
    def blank_to_none(cls, value):
        return value.strip() or None if value is not None else None


class GoodsReceiptCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    purchase_order_id: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: UUID
    items: Annotated[list[ReceiptItemInput], Field(min_length=1, max_length=100)]

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value):
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def unique_purchase_order_lines(self):
        line_ids = [item.purchase_order_item_id for item in self.items]
        if len(line_ids) != len(set(line_ids)):
            raise ValueError("A purchase order line can only appear once per receipt.")
        return self
