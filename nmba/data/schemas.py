from datetime import date

from pydantic import BaseModel


class BillBase(BaseModel):
    name: str
    recipient: str
    due_day: int
    amount: float
    paid: bool = False


class BillCreate(BillBase):
    pass


class Bill(BillBase):
    id: int
    model_config = {"from_attributes": True}
