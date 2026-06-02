from sqlalchemy.orm import Session

from app.crud.item import create_item, get_item_by_id, get_items
from app.models.item import Item
from app.schemas.item import ItemCreate


def create_item_service(
    db: Session,
    item_data: ItemCreate,
) -> Item:
    created_item = create_item(
        db=db,
        item_data=item_data,
    )

    return created_item


def get_items_service(db: Session) -> list[Item]:
    return get_items(db=db)


def get_item_by_id_service(
    db: Session,
    item_id: int,
) -> Item | None:
    return get_item_by_id(
        db=db,
        item_id=item_id,
    )
