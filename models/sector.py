from datetime import datetime, timezone
from models import db


class Sector(db.Model):
    """B3 sector classification (Setor → Subsetor → Segmento)."""
    __tablename__ = 'sectors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subsector = db.Column(db.String(100))
    segment = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    companies = db.relationship('Company', backref='sector', lazy='dynamic')

    def __repr__(self):
        return f'<Sector {self.name}/{self.subsector}/{self.segment}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'subsector': self.subsector,
            'segment': self.segment,
        }
