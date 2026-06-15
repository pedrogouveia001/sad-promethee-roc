from datetime import datetime, timezone
from models import db


class DecisionProblem(db.Model):
    """A SMARTER decision problem configured by the user."""
    __tablename__ = 'decision_problems'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    criteria = db.relationship('DecisionCriteria', backref='problem',
                               lazy='dynamic', cascade='all, delete-orphan',
                               order_by='DecisionCriteria.rank_position')
    alternatives = db.relationship('DecisionAlternative', backref='problem',
                                   lazy='dynamic', cascade='all, delete-orphan')
    global_values = db.relationship('GlobalValue', backref='problem',
                                    lazy='dynamic', cascade='all, delete-orphan')
    statistical_results = db.relationship('StatisticalResult', backref='problem',
                                          lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<DecisionProblem {self.id}: {self.name}>'

    def to_dict(self, include_details=False):
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'criteria_count': self.criteria.count(),
            'alternatives_count': self.alternatives.count(),
        }
        if include_details:
            data['criteria'] = [c.to_dict() for c in self.criteria.order_by(DecisionCriteria.rank_position).all()]
            data['alternatives'] = [a.to_dict() for a in self.alternatives.all()]
        return data


class DecisionCriteria(db.Model):
    """A criterion in a SMARTER decision problem, with its rank and ROC weight."""
    __tablename__ = 'decision_criteria'

    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('decision_problems.id'), nullable=False)
    indicator_id = db.Column(db.Integer, db.ForeignKey('indicator_definitions.id'), nullable=False)
    rank_position = db.Column(db.Integer, nullable=False)  # 1 = most important
    criteria_type = db.Column(db.String(10), nullable=False)  # 'cost' or 'benefit'
    roc_weight = db.Column(db.Float)  # Calculated automatically

    # Relationship to get indicator details
    indicator = db.relationship('IndicatorDefinition', lazy='joined')

    __table_args__ = (
        db.UniqueConstraint('problem_id', 'indicator_id', name='uq_criteria_indicator'),
        db.UniqueConstraint('problem_id', 'rank_position', name='uq_criteria_rank'),
    )

    def __repr__(self):
        return f'<Criteria rank={self.rank_position} weight={self.roc_weight}>'

    def to_dict(self):
        return {
            'id': self.id,
            'indicator_id': self.indicator_id,
            'indicator': self.indicator.to_dict() if self.indicator else None,
            'rank_position': self.rank_position,
            'criteria_type': self.criteria_type,
            'roc_weight': self.roc_weight,
        }


class DecisionAlternative(db.Model):
    """An alternative (company) in a SMARTER decision problem."""
    __tablename__ = 'decision_alternatives'

    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('decision_problems.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)

    company = db.relationship('Company', lazy='joined')

    __table_args__ = (
        db.UniqueConstraint('problem_id', 'company_id', name='uq_alternative_company'),
    )

    def __repr__(self):
        return f'<Alternative company={self.company_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'company': self.company.to_dict() if self.company else None,
        }
