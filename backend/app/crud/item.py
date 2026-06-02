from sqlalchemy.orm import Session

from app.models.item import Item
from app.schemas.item import ItemCreate


def create_item(db: Session, item_data: ItemCreate) -> Item:
    item = Item(name=item_data.name)

    db.add(item)
    db.commit()
    db.refresh(item)

    return item
