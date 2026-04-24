from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db


class Strategy(db.Model):
    __tablename__ = "strategies"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(64), nullable=False)
    source = db.Column(db.String(32), nullable=False, default="人工创建")
    status = db.Column(db.String(32), nullable=False, default="草稿", index=True)
    country_region = db.Column(db.String(64), nullable=False, index=True)
    asset_type = db.Column(db.String(16), nullable=True)
    asset_identifier = db.Column(db.String(64), nullable=True)
    asset_name = db.Column(db.String(255), nullable=True)
    strategy_config = db.Column(
        JSONB().with_variant(db.JSON(), "sqlite"),
        nullable=False,
        default=dict,
    )
    annual_return = db.Column(db.Numeric(10, 2), nullable=True)
    max_drawdown = db.Column(db.Numeric(10, 2), nullable=True)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="strategies")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "source": self.source,
            "status": self.status,
            "countryRegion": self.country_region,
            "assetType": self.asset_type,
            "assetIdentifier": self.asset_identifier,
            "assetName": self.asset_name,
            "strategyConfig": self.strategy_config or {},
            "annualReturn": f"{self.annual_return:.2f}%" if self.annual_return is not None else None,
            "drawdown": f"{self.max_drawdown:.2f}%" if self.max_drawdown is not None else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
