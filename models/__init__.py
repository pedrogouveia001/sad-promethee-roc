from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.sector import Sector
from models.company import Company
from models.indicator import IndicatorDefinition
from models.indicator_history import IndicatorHistory
from models.price_history import PriceHistory
from models.decision_problem import DecisionProblem, DecisionCriteria, DecisionAlternative
from models.recommendation import GlobalValue, StatisticalResult

__all__ = [
    'db',
    'Sector',
    'Company',
    'IndicatorDefinition',
    'IndicatorHistory',
    'PriceHistory',
    'DecisionProblem',
    'DecisionCriteria',
    'DecisionAlternative',
    'GlobalValue',
    'StatisticalResult',
]
