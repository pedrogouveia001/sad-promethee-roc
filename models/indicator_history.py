from datetime import datetime, timezone
from models import db


class IndicatorHistory(db.Model):
    """Historical values of financial indicators for each company/period."""
    __tablename__ = 'indicator_history'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    indicator_id = db.Column(db.Integer, db.ForeignKey('indicator_definitions.id'), nullable=False, index=True)
    value = db.Column(db.Float)
    period_date = db.Column(db.Date, nullable=False, index=True)
    period_type = db.Column(db.String(10), nullable=False)  # 'quarterly' or 'annual' or 'current'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('company_id', 'indicator_id', 'period_date', 'period_type',
                            name='uq_indicator_history'),
    )

    def __repr__(self):
        return f'<IndicatorHistory company={self.company_id} indicator={self.indicator_id} date={self.period_date}>'

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'indicator_id': self.indicator_id,
            'value': self.value,
            'period_date': self.period_date.isoformat(),
            'period_type': self.period_type,
        }
