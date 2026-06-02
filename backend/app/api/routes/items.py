from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.crud.item import create_item
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
