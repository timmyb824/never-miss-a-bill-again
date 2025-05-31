from sqlalchemy.orm import Session

from . import models, schemas


def get_bills(db: Session):
    return db.query(models.Bill).all()


def get_bill(db: Session, bill_id: int):
    return db.query(models.Bill).filter(models.Bill.id == bill_id).first()


def create_bill(db: Session, bill: schemas.BillCreate):
    db_bill = models.Bill(**bill.dict())
    db.add(db_bill)
    db.commit()
    db.refresh(db_bill)
    return db_bill


def delete_bill(db: Session, bill_id: int):
    bill = get_bill(db, bill_id)
    if bill:
        db.delete(bill)
        db.commit()
    return bill


def mark_bill_paid(db: Session, bill_id: int, paid: bool = True):
    bill = get_bill(db, bill_id)
    if bill:
        bill.paid = paid
        db.commit()
        db.refresh(bill)
    return bill
