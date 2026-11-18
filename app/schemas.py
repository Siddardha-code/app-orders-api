from datetime import datetime

from pydantic import BaseModel, Field


class OrderIn(BaseModel):
    item: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0, le=1000)


class OrderOut(BaseModel):
    id: int
    item: str
    quantity: int
    created_at: datetime
