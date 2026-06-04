from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    unit: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    data_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    min_value: Mapped[float | None]

    max_value: Mapped[float | None]

    asset_type_id: Mapped[int] = mapped_column(
        ForeignKey("asset_types.id"),
        nullable=False,
    )

    asset_type = relationship("AssetType")
