from datetime import datetime, timezone
from models import db


class PriceHistory(db.Model):
    """Historical OHLCV price data for each company."""
    __tablename__ = 'price_history'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    open = db.Column(db.Float)
    high = db.Column(db.Float)
    low = db.Column(db.Float)
    close = db.Column(db.Float, nullable=False)
    adj_close = db.Column(db.Float)
    volume = db.Column(db.BigInteger)

    __table_args__ = (
        db.UniqueConstraint('company_id', 'date', name='uq_price_history'),
        db.Index('idx_price_company_date', 'company_id', 'date'),
    )

    def __repr__(self):
        return f'<PriceHistory {self.company_id} {self.date} close={self.close}>'

    def to_dict(self):
        return {
            'date': self.date.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'adj_close': self.adj_close,
            'volume': self.volume,
        }
