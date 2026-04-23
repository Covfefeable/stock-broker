from datetime import datetime, timezone

from app.extensions import db


class IndexAsset(db.Model):
    __tablename__ = "index_assets"

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(32), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"), nullable=True, index=True)
    country_code = db.Column(db.String(8), nullable=False, index=True)
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

    __table_args__ = (
        db.UniqueConstraint("country_code", "ticker", name="uq_index_assets_country_ticker"),
    )

    country = db.relationship("Country")

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "countryCode": self.country_code,
        }
