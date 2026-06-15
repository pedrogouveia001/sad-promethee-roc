import json
from datetime import datetime, timezone
from models import db


class GlobalValue(db.Model):
    """Calculated SMARTER global value V(a, t) for each company/period."""
    __tablename__ = 'global_values'

    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('decision_problems.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    period_date = db.Column(db.Date, nullable=False)
    global_value = db.Column(db.Float, nullable=False)
    normalized_values_json = db.Column(db.Text)  # JSON: {indicator_code: normalized_value, ...}

    company = db.relationship('Company', lazy='joined')

    __table_args__ = (
        db.UniqueConstraint('problem_id', 'company_id', 'period_date', name='uq_global_value'),
        db.Index('idx_global_values_problem_date', 'problem_id', 'period_date'),
    )

    @property
    def normalized_values(self):
        if self.normalized_values_json:
            return json.loads(self.normalized_values_json)
        return {}

    @normalized_values.setter
    def normalized_values(self, value):
        self.normalized_values_json = json.dumps(value)

    def to_dict(self):
        return {
            'company_id': self.company_id,
            'ticker': self.company.ticker if self.company else None,
            'company_ticker': self.company.ticker if self.company else None,
            'period_date': self.period_date.isoformat(),
            'global_value': round(self.global_value, 6),
            'normalized_values': self.normalized_values,
        }


class StatisticalResult(db.Model):
    """Statistical analysis results: correlation between ΔV and ΔPrice."""
    __tablename__ = 'statistical_results'

    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('decision_problems.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)

    # Correlation metrics
    pearson_correlation = db.Column(db.Float)
    spearman_correlation = db.Column(db.Float)
    p_value_pearson = db.Column(db.Float)
    p_value_spearman = db.Column(db.Float)

    # Regression metrics
    r_squared = db.Column(db.Float)
    beta_coefficient = db.Column(db.Float)

    # Recommendation
    recommendation_score = db.Column(db.Float)
    recommendation_label = db.Column(db.String(20))  # "Forte Compra", "Compra", "Neutro", "Venda", "Forte Venda"

    # Metadata
    analysis_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    window_days = db.Column(db.Integer, default=90)

    company = db.relationship('Company', lazy='joined')

    __table_args__ = (
        db.UniqueConstraint('problem_id', 'company_id', name='uq_statistical_result'),
    )

    def to_dict(self):
        return {
            'company_id': self.company_id,
            'ticker': self.company.ticker if self.company else None,
            'company_ticker': self.company.ticker if self.company else None,
            'company_name': self.company.name if self.company else None,
            'pearson_correlation': round(self.pearson_correlation, 4) if self.pearson_correlation else None,
            'spearman_correlation': round(self.spearman_correlation, 4) if self.spearman_correlation else None,
            'p_value_pearson': self.p_value_pearson,
            'p_value_spearman': self.p_value_spearman,
            'r_squared': round(self.r_squared, 4) if self.r_squared else None,
            'beta_coefficient': round(self.beta_coefficient, 4) if self.beta_coefficient else None,
            'recommendation_score': round(self.recommendation_score, 4) if self.recommendation_score else None,
            'recommendation_label': self.recommendation_label,
            'analysis_date': self.analysis_date.isoformat() if self.analysis_date else None,
        }
