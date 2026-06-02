from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.item import Item
from app.schemas.item import ItemCreate


def create_item(db: Session, item_data: ItemCreate) -> Item:
    item = Item(name=item_data.name)

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


def get_items(db: Session) -> list[Item]:
    statement = select(Item)

    result = db.execute(statement)

    return list(result.scalars().all())


def get_item_by_id(db: Session, item_id: int) -> Item | None:
    statement = select(Item).where(Item.id == item_id)

    result = db.execute(statement)

    return result.scalar_one_or_none()
