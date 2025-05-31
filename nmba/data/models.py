from sqlalchemy import Column, Integer, String, Date, Boolean, Numeric
from .database import Base


class Bill(Base):
    __tablename__ = "bills"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    recipient = Column(String, nullable=False)
    due_day = Column(Integer, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    paid = Column(Boolean, default=False)

class Config(Base):
    __tablename__ = "config"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)
