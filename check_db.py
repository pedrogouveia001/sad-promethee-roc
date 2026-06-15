import os
from app import create_app
from models import db
from models.company import Company
from models.indicator_history import IndicatorHistory
from models.price_history import PriceHistory
from models.recommendation import GlobalValue, StatisticalResult
from models.decision_problem import DecisionProblem, DecisionAlternative

app = create_app('development')
with app.app_context():
    print("=== DATABASE DIAGNOSTICS ===")
    
    companies = Company.query.all()
    print(f"Total Companies: {len(companies)}")
    for c in companies[:3]:
        print(f" - {c.ticker}: {c.name}")
        
    prices = PriceHistory.query.count()
    print(f"Total PriceHistory records: {prices}")
    
    ind_history = IndicatorHistory.query.count()
    print(f"Total IndicatorHistory records: {ind_history}")
    
    problems = DecisionProblem.query.all()
    print(f"Total Decision Problems: {len(problems)}")
    for p in problems:
        alts = DecisionAlternative.query.filter_by(problem_id=p.id).count()
        gvs = GlobalValue.query.filter_by(problem_id=p.id).count()
        stats = StatisticalResult.query.filter_by(problem_id=p.id).count()
        print(f" - Problem {p.id}: {p.name}")
        print(f"   * Alternatives count: {alts}")
        print(f"   * Global values count: {gvs}")
        print(f"   * Statistical results count: {stats}")
        
        # Check first few global values
        first_gvs = GlobalValue.query.filter_by(problem_id=p.id).limit(5).all()
        for gv in first_gvs:
            print(f"     GlobalValue: {gv.company.ticker if gv.company else gv.company_id} on {gv.period_date} = {gv.global_value}")
            
        # Check stats results
        first_stats = StatisticalResult.query.filter_by(problem_id=p.id).all()
        print(f"   * StatisticalResult Details:")
        for s in first_stats:
            print(f"     {s.company.ticker}: Pearson={s.pearson_correlation}, P-value={s.p_value_pearson}, Score={s.recommendation_score}, Label={s.recommendation_label}")
