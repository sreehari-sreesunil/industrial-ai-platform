from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.crud.item import create_item, get_item_by_id, get_items
from app.db.session import get_db
from app.schemas.item import ItemCreate, ItemResponse

router = APIRouter(prefix="/items", tags=["items"])


@router.post("/", response_model=ItemResponse)
def create_item_endpoint(
    item: ItemCreate,
    db: Session = Depends(get_db),
) -> ItemResponse:
    created_item = create_item(db=db, item_data=item)

    return created_item


@router.get("/", response_model=list[ItemResponse])
def get_items_endpoint(
    db: Session = Depends(get_db),
) -> list[ItemResponse]:
    items = get_items(db=db)

    return items


@router.get("/{item_id}", response_model=ItemResponse)
def get_item_endpoint(
    item_id: int,
    db: Session = Depends(get_db),
) -> ItemResponse:
    item = get_item_by_id(db=db, item_id=item_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    return item
