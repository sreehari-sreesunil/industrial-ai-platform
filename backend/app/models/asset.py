from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"),
        nullable=False,
    )

    asset_type_id: Mapped[int] = mapped_column(
        ForeignKey("asset_types.id"),
        nullable=False,
    )

    facility = relationship("Facility")

    asset_type = relationship("AssetType")

    telemetry_records = relationship("TelemetryRecord")
