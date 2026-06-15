from datetime import datetime, timezone
from models import db


class Company(db.Model):
    """Listed company on B3."""
    __tablename__ = 'companies'

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False, unique=True, index=True)
    name = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(300))
    sector_id = db.Column(db.Integer, db.ForeignKey('sectors.id'))
    logo_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    last_updated = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    indicator_history = db.relationship('IndicatorHistory', backref='company', lazy='dynamic')
    price_history = db.relationship('PriceHistory', backref='company', lazy='dynamic')

    def __repr__(self):
        return f'<Company {self.ticker} - {self.name}>'

    def to_dict(self, include_sector=False):
        data = {
            'id': self.id,
            'ticker': self.ticker,
            'name': self.name,
            'full_name': self.full_name,
            'logo_url': self.logo_url,
            'is_active': self.is_active,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
        }
        if include_sector and self.sector:
            data['sector'] = self.sector.to_dict()
        elif self.sector_id:
            data['sector_id'] = self.sector_id
        return data
