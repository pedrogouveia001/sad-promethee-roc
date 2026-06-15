"""
API Routes — Companies, Sectors, Indicators, Decision, Analysis, Recommendations.

All routes are registered as Flask Blueprints.
"""

from flask import Blueprint, jsonify, request

from models import db
from models.company import Company
from models.sector import Sector
from models.indicator import IndicatorDefinition
from models.indicator_history import IndicatorHistory
from models.price_history import PriceHistory
from models.decision_problem import DecisionProblem, DecisionCriteria, DecisionAlternative
from models.recommendation import GlobalValue, StatisticalResult
from services.promethee_engine import PROMETHEEEngine
from services.statistical_analyzer import StatisticalAnalyzer
from services.data_collector import DataCollector

api = Blueprint('api', __name__, url_prefix='/api')

promethee = PROMETHEEEngine()
analyzer = StatisticalAnalyzer()


# ═══════════════════════════════════════════════════════════════════════
# COMPANIES
# ═══════════════════════════════════════════════════════════════════════

@api.route('/companies')
def list_companies():
    """List all companies, optionally filtered by sector."""
    sector = request.args.get('sector')
    search = request.args.get('search', '')

    query = Company.query.filter_by(is_active=True)

    if sector:
        query = query.join(Sector).filter(Sector.name == sector)

    if search:
        query = query.filter(
            db.or_(
                Company.ticker.ilike(f'%{search}%'),
                Company.name.ilike(f'%{search}%'),
            )
        )

    companies = query.order_by(Company.ticker).all()
    return jsonify([c.to_dict(include_sector=True) for c in companies])


@api.route('/companies/<ticker>')
def get_company(ticker):
    """Get details for a specific company."""
    company = Company.query.filter_by(ticker=ticker.upper()).first_or_404()
    return jsonify(company.to_dict(include_sector=True))


@api.route('/companies/<ticker>/indicators')
def get_company_indicators(ticker):
    """Get current indicator values for a company."""
    company = Company.query.filter_by(ticker=ticker.upper()).first_or_404()

    # Get the most recent indicator values
    from sqlalchemy import func
    subq = db.session.query(
        IndicatorHistory.indicator_id,
        func.max(IndicatorHistory.period_date).label('max_date')
    ).filter_by(company_id=company.id).group_by(
        IndicatorHistory.indicator_id
    ).subquery()

    records = db.session.query(IndicatorHistory).join(
        subq,
        db.and_(
            IndicatorHistory.indicator_id == subq.c.indicator_id,
            IndicatorHistory.period_date == subq.c.max_date,
            IndicatorHistory.company_id == company.id,
        )
    ).all()

    indicators = {}
    for r in records:
        ind = IndicatorDefinition.query.get(r.indicator_id)
        if ind:
            indicators[ind.code] = {
                'name': ind.name,
                'value': r.value,
                'category': ind.category,
                'type': ind.default_type,
                'date': r.period_date.isoformat(),
            }

    return jsonify({
        'ticker': company.ticker,
        'name': company.name,
        'indicators': indicators,
    })


@api.route('/companies/<ticker>/prices')
def get_company_prices(ticker):
    """Get historical prices for a company."""
    company = Company.query.filter_by(ticker=ticker.upper()).first_or_404()
    limit = request.args.get('limit', 365, type=int)

    prices = PriceHistory.query.filter_by(
        company_id=company.id
    ).order_by(PriceHistory.date.desc()).limit(limit).all()

    return jsonify({
        'ticker': company.ticker,
        'prices': [p.to_dict() for p in reversed(prices)],
    })


# ═══════════════════════════════════════════════════════════════════════
# SECTORS
# ═══════════════════════════════════════════════════════════════════════

@api.route('/sectors')
def list_sectors():
    """List all sectors with company counts."""
    sectors = db.session.query(
        Sector.name,
        db.func.count(Company.id).label('count')
    ).outerjoin(Company).group_by(Sector.name).order_by(Sector.name).all()

    return jsonify([
        {'name': s.name, 'company_count': s.count}
        for s in sectors
    ])


@api.route('/sectors/<name>/companies')
def get_sector_companies(name):
    """Get all companies in a sector."""
    companies = Company.query.join(Sector).filter(
        Sector.name == name,
        Company.is_active == True,
    ).order_by(Company.ticker).all()

    return jsonify([c.to_dict() for c in companies])


# ═══════════════════════════════════════════════════════════════════════
# INDICATORS
# ═══════════════════════════════════════════════════════════════════════

@api.route('/indicators')
def list_indicators():
    """List all available indicator definitions grouped by category."""
    indicators = IndicatorDefinition.query.order_by(
        IndicatorDefinition.category, IndicatorDefinition.name
    ).all()

    # Group by category
    grouped = {}
    for ind in indicators:
        if ind.category not in grouped:
            grouped[ind.category] = []
        grouped[ind.category].append(ind.to_dict())

    return jsonify(grouped)


@api.route('/indicators/<code>/bounds')
def get_indicator_bounds(code):
    """Get historical min/max for an indicator across all companies."""
    indicator = IndicatorDefinition.query.filter_by(code=code).first_or_404()
    min_val, max_val = promethee.get_historical_bounds(indicator.id)

    return jsonify({
        'code': code,
        'name': indicator.name,
        'min': min_val,
        'max': max_val,
    })


# ═══════════════════════════════════════════════════════════════════════
# DECISION (SMARTER)
# ═══════════════════════════════════════════════════════════════════════

@api.route('/decision', methods=['POST'])
def create_decision():
    """Create a new decision problem."""
    data = request.get_json()
    problem = DecisionProblem(
        name=data.get('name', 'Nova Análise'),
        description=data.get('description', ''),
    )
    db.session.add(problem)
    db.session.commit()
    return jsonify(problem.to_dict()), 201


@api.route('/decision/<int:problem_id>')
def get_decision(problem_id):
    """Get details of a decision problem."""
    problem = DecisionProblem.query.get_or_404(problem_id)
    return jsonify(problem.to_dict(include_details=True))


@api.route('/decision/<int:problem_id>/criteria', methods=['PUT'])
def update_criteria(problem_id):
    """
    Update criteria for a decision problem.

    Expects JSON body:
    {
        "criteria": [
            {"indicator_code": "trailing_pe", "rank": 1, "type": "cost"},
            {"indicator_code": "roe", "rank": 2, "type": "benefit"},
            ...
        ]
    }
    """
    problem = DecisionProblem.query.get_or_404(problem_id)
    data = request.get_json()
    criteria_list = data.get('criteria', [])

    # Clear existing criteria
    DecisionCriteria.query.filter_by(problem_id=problem_id).delete()
    db.session.flush()

    # Calculate ROC weights
    n = len(criteria_list)
    roc_weights = promethee.calculate_roc_weights(n)

    for i, crit_data in enumerate(criteria_list):
        indicator = IndicatorDefinition.query.filter_by(
            code=crit_data['indicator_code']
        ).first()
        if not indicator:
            continue

        criteria = DecisionCriteria(
            problem_id=problem_id,
            indicator_id=indicator.id,
            rank_position=crit_data.get('rank', i + 1),
            criteria_type=crit_data.get('type', indicator.default_type),
            roc_weight=roc_weights[i] if i < len(roc_weights) else 0,
        )
        db.session.add(criteria)

    db.session.commit()
    return jsonify(problem.to_dict(include_details=True))


@api.route('/decision/<int:problem_id>/alternatives', methods=['PUT'])
def update_alternatives(problem_id):
    """
    Update alternatives (companies) for a decision problem.

    Expects JSON body:
    {
        "tickers": ["PETR4", "VALE3", "ITUB4", ...]
    }
    """
    problem = DecisionProblem.query.get_or_404(problem_id)
    data = request.get_json()
    tickers = data.get('tickers', [])

    # Clear existing alternatives
    DecisionAlternative.query.filter_by(problem_id=problem_id).delete()
    db.session.flush()

    for ticker in tickers:
        company = Company.query.filter_by(ticker=ticker.upper()).first()
        if company:
            alt = DecisionAlternative(
                problem_id=problem_id,
                company_id=company.id,
            )
            db.session.add(alt)

    db.session.commit()
    return jsonify(problem.to_dict(include_details=True))


@api.route('/decision/<int:problem_id>/calculate', methods=['POST'])
def calculate_global_values(problem_id):
    """Run the PROMETHEE calculation for all companies × all periods."""
    try:
        result = promethee.run_full_calculation(problem_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@api.route('/decision/<int:problem_id>/results')
def get_decision_results(problem_id):
    """Get latest global values for all companies in a decision problem."""
    from sqlalchemy import func

    # Get the most recent global value for each company
    subq = db.session.query(
        GlobalValue.company_id,
        func.max(GlobalValue.period_date).label('max_date')
    ).filter_by(problem_id=problem_id).group_by(
        GlobalValue.company_id
    ).subquery()

    records = db.session.query(GlobalValue).join(
        subq,
        db.and_(
            GlobalValue.company_id == subq.c.company_id,
            GlobalValue.period_date == subq.c.max_date,
            GlobalValue.problem_id == problem_id,
        )
    ).order_by(GlobalValue.global_value.desc()).all()

    return jsonify({
        'problem_id': problem_id,
        'results': [r.to_dict() for r in records],
    })


@api.route('/decision/<int:problem_id>/results/timeseries')
def get_timeseries(problem_id):
    """Get global value time series for all companies."""
    ticker_filter = request.args.get('ticker')

    query = GlobalValue.query.filter_by(problem_id=problem_id)

    if ticker_filter:
        company = Company.query.filter_by(ticker=ticker_filter.upper()).first()
        if company:
            query = query.filter_by(company_id=company.id)

    records = query.order_by(GlobalValue.period_date).all()

    # Group by company
    series = {}
    for r in records:
        ticker = r.company.ticker if r.company else str(r.company_id)
        if ticker not in series:
            series[ticker] = []
        series[ticker].append({
            'date': r.period_date.isoformat(),
            'value': round(r.global_value, 6),
        })

    return jsonify({
        'problem_id': problem_id,
        'series': series,
    })


# ═══════════════════════════════════════════════════════════════════════
# ANALYSIS (Statistical)
# ═══════════════════════════════════════════════════════════════════════

@api.route('/analysis/<int:problem_id>/run', methods=['POST'])
def run_analysis(problem_id):
    """Run statistical analysis for all companies in a decision problem."""
    data = request.get_json() or {}
    window_days = data.get('window_days', 90)

    try:
        result = analyzer.run_full_analysis(problem_id, window_days)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@api.route('/analysis/<int:problem_id>/results')
def get_analysis_results(problem_id):
    """Get statistical analysis results."""
    results = StatisticalResult.query.filter_by(
        problem_id=problem_id
    ).order_by(StatisticalResult.recommendation_score.desc()).all()

    return jsonify({
        'problem_id': problem_id,
        'results': [r.to_dict() for r in results],
    })


@api.route('/analysis/<int:problem_id>/scatter/<ticker>')
def get_scatter_data(problem_id, ticker):
    """Get scatter plot data (ΔV vs ΔPrice) for a specific company."""
    company = Company.query.filter_by(ticker=ticker.upper()).first_or_404()

    analysis = analyzer.analyze_company(problem_id, company.id)
    if analysis is None:
        return jsonify({'error': 'Insufficient data'}), 400

    return jsonify({
        'ticker': ticker.upper(),
        'pearson_r': analysis['pearson_r'],
        'data_points': analysis['data_points'],
        'scatter': analysis['scatter_data'],
    })


# ═══════════════════════════════════════════════════════════════════════
# RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════════════════

@api.route('/recommendations/<int:problem_id>')
def get_recommendations(problem_id):
    """Get all recommendations for a decision problem, ranked by score."""
    results = StatisticalResult.query.filter_by(
        problem_id=problem_id
    ).order_by(StatisticalResult.recommendation_score.desc()).all()

    return jsonify({
        'problem_id': problem_id,
        'disclaimer': (
            'As recomendações são baseadas em modelos estatísticos e multicritério. '
            'NÃO constituem aconselhamento financeiro. O decisor é integralmente '
            'responsável por suas decisões de investimento.'
        ),
        'recommendations': [r.to_dict() for r in results],
    })


# ═══════════════════════════════════════════════════════════════════════
# SYSTEM
# ═══════════════════════════════════════════════════════════════════════

@api.route('/system/status')
def system_status():
    """Get system status and data summary."""
    company_count = Company.query.filter_by(is_active=True).count()
    indicator_count = IndicatorDefinition.query.count()
    history_count = IndicatorHistory.query.count()
    price_count = PriceHistory.query.count()
    problem_count = DecisionProblem.query.count()

    # Last collection date
    from sqlalchemy import func
    last_update = db.session.query(func.max(Company.last_updated)).scalar()

    return jsonify({
        'status': 'online',
        'companies': company_count,
        'indicators_defined': indicator_count,
        'indicator_records': history_count,
        'price_records': price_count,
        'decision_problems': problem_count,
        'last_data_update': last_update.isoformat() if last_update else None,
    })


@api.route('/system/collect', methods=['POST'])
def trigger_collection():
    """Manually trigger data collection for test tickers."""
    from flask import current_app

    collector = DataCollector(current_app)
    data = request.get_json() or {}
    tickers = data.get('tickers', current_app.config.get('FREE_TEST_TICKERS', []))

    # First sync companies
    collector.sync_companies()

    # Then collect data
    stats = collector.collect_all(tickers=tickers)
    return jsonify(stats)


@api.route('/system/seed', methods=['POST'])
def seed_database():
    """Seed the database with indicator definitions and initial data."""
    from models.indicator import INDICATOR_SEED_DATA

    count = 0
    for ind_data in INDICATOR_SEED_DATA:
        existing = IndicatorDefinition.query.filter_by(code=ind_data['code']).first()
        if not existing:
            indicator = IndicatorDefinition(**ind_data)
            db.session.add(indicator)
            count += 1

    db.session.commit()
    return jsonify({'seeded': count, 'total': len(INDICATOR_SEED_DATA)})
