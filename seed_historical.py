"""
Seed Historical Data — Generates realistic historical fundamental indicators
and price data for test tickers to allow instant local testing of PROMETHEE II
and statistical correlation modules without API key requirements.
"""

import os
import random
from datetime import date, timedelta, datetime
import numpy as np

from app import create_app
from models import db
from models.sector import Sector
from models.company import Company
from models.indicator import IndicatorDefinition, INDICATOR_SEED_DATA
from models.indicator_history import IndicatorHistory
from models.price_history import PriceHistory

def run_seeder():
    app = create_app('development')
    
    with app.app_context():
        print("Initializing database...")
        db.create_all()
        
        # 1. Seed indicator definitions
        print("Seeding indicator definitions...")
        for ind_data in INDICATOR_SEED_DATA:
            existing = IndicatorDefinition.query.filter_by(code=ind_data['code']).first()
            if not existing:
                indicator = IndicatorDefinition(**ind_data)
                db.session.add(indicator)
        db.session.commit()
        
        # 2. Define sectors and companies
        sectors_companies = {
            'Petróleo e Gás': [
                {'ticker': 'PETR4', 'name': 'Petrobras PN', 'base_price': 35.0},
            ],
            'Mineração': [
                {'ticker': 'VALE3', 'name': 'Vale ON', 'base_price': 70.0},
            ],
            'Financeiro': [
                {'ticker': 'ITUB4', 'name': 'Itaú Unibanco PN', 'base_price': 32.0},
                {'ticker': 'BBAS3', 'name': 'Banco do Brasil ON', 'base_price': 27.0},
                {'ticker': 'B3SA3', 'name': 'B3 ON', 'base_price': 11.5},
            ],
            'Consumo Cíclico': [
                {'ticker': 'MGLU3', 'name': 'Magazine Luiza ON', 'base_price': 3.50},
                {'ticker': 'RENT3', 'name': 'Localiza ON', 'base_price': 50.0},
            ],
            'Bens Industriais': [
                {'ticker': 'WEGE3', 'name': 'Weg ON', 'base_price': 42.0},
            ],
            'Consumo Não Cíclico': [
                {'ticker': 'ABEV3', 'name': 'Ambev ON', 'base_price': 12.0},
            ],
            'Siderurgia': [
                {'ticker': 'GGBR4', 'name': 'Gerdau PN', 'base_price': 22.0},
            ]
        }
        
        print("Seeding sectors and companies...")
        company_objects = []
        for sec_name, comps in sectors_companies.items():
            sector = Sector.query.filter_by(name=sec_name).first()
            if not sector:
                sector = Sector(name=sec_name)
                db.session.add(sector)
                db.session.flush()
                
            for comp in comps:
                existing_comp = Company.query.filter_by(ticker=comp['ticker']).first()
                if not existing_comp:
                    company = Company(
                        ticker=comp['ticker'],
                        name=comp['name'],
                        full_name=f"{comp['name']} S.A.",
                        sector_id=sector.id,
                        is_active=True
                    )
                    db.session.add(company)
                    db.session.flush()
                    company_objects.append((company, comp['base_price']))
                else:
                    company_objects.append((existing_comp, comp['base_price']))
                    
        db.session.commit()
        
        # 3. Generate Historical Periods (Quarterly, last 5 years)
        print("Generating historical data points...")
        start_year = 2021
        end_year = 2026
        quarters = [
            (3, 31),  # Q1
            (6, 30),  # Q2
            (9, 30),  # Q3
            (12, 31)  # Q4
        ]
        
        periods = []
        for year in range(start_year, end_year):
            for month, day in quarters:
                periods.append(date(year, month, day))
        # Add Q1 2026
        periods.append(date(2026, 3, 31))
        
        # Get all indicators from DB
        indicators = IndicatorDefinition.query.all()
        
        # Clear old history if seeding again
        print("Clearing old history...")
        IndicatorHistory.query.delete()
        PriceHistory.query.delete()
        db.session.commit()
        
        # 4. Populate IndicatorHistory and PriceHistory with correlated trends
        print("Generating correlated time series...")
        random.seed(42)
        np.random.seed(42)
        
        for company, base_price in company_objects:
            print(f"Generating data for {company.ticker}...")
            
            # Setup a random walk for the stock price
            price_trend = np.linspace(0.8, 1.3, len(periods)) + np.random.normal(0, 0.1, len(periods))
            prices = base_price * price_trend
            
            # Generate indicators and align them to the prices
            for idx, period_date in enumerate(periods):
                # Price for this date
                price_val = float(prices[idx])
                
                # Insert price history point
                ph = PriceHistory(
                    company_id=company.id,
                    date=period_date,
                    open=price_val * 0.99,
                    high=price_val * 1.02,
                    low=price_val * 0.98,
                    close=price_val,
                    adj_close=price_val,
                    volume=int(random.randint(100000, 5000000))
                )
                db.session.add(ph)
                
                # Indicators: create a correlation between financial performance and price
                # If price goes up, profitability (ROE, Margins) rises, and valuation (P/L, P/VP) expands
                perf_factor = price_trend[idx]  # relative performance
                
                for ind in indicators:
                    # Realistic baseline logic per indicator category
                    if ind.code == 'roe':
                        val = 0.15 * perf_factor + random.uniform(-0.02, 0.02)
                    elif ind.code == 'roa':
                        val = 0.08 * perf_factor + random.uniform(-0.01, 0.01)
                    elif ind.code == 'trailing_pe':
                        # Valuation multiples expand during stock rallies
                        val = 15.0 * perf_factor + random.uniform(-2, 2)
                        val = max(5.0, val)
                    elif ind.code == 'price_to_book':
                        val = 2.0 * perf_factor + random.uniform(-0.3, 0.3)
                        val = max(0.5, val)
                    elif ind.code == 'ev_ebitda':
                        val = 8.0 * perf_factor + random.uniform(-1, 1)
                        val = max(3.0, val)
                    elif ind.code == 'profit_margin':
                        val = 0.12 * perf_factor + random.uniform(-0.02, 0.02)
                    elif ind.code == 'ebitda_margin':
                        val = 0.25 * perf_factor + random.uniform(-0.03, 0.03)
                    elif ind.code == 'operating_margin':
                        val = 0.18 * perf_factor + random.uniform(-0.02, 0.02)
                    elif ind.code == 'gross_margin':
                        val = 0.40 + random.uniform(-0.05, 0.05)
                    elif ind.code == 'dividend_yield':
                        # Yield decreases if price rises unless payout changes
                        val = 0.06 / perf_factor + random.uniform(-0.01, 0.01)
                        val = max(0.0, val)
                    elif ind.code == 'payout_ratio':
                        val = 0.50 + random.uniform(-0.1, 0.1)
                    elif ind.code == 'debt_to_equity':
                        val = 1.2 / perf_factor + random.uniform(-0.1, 0.1)
                        val = max(0.1, val)
                    elif ind.code == 'current_ratio':
                        val = 1.5 * perf_factor + random.uniform(-0.1, 0.1)
                        val = max(0.5, val)
                    elif ind.code == 'quick_ratio':
                        val = 1.1 * perf_factor + random.uniform(-0.1, 0.1)
                        val = max(0.3, val)
                    elif ind.code == 'price_to_sales':
                        val = 1.8 * perf_factor + random.uniform(-0.2, 0.2)
                    elif ind.code == 'ev_revenue':
                        val = 2.2 * perf_factor + random.uniform(-0.2, 0.2)
                    elif ind.code == 'revenue_growth':
                        val = 0.08 + random.uniform(-0.04, 0.04)
                    elif ind.code == 'earnings_growth':
                        val = 0.10 + random.uniform(-0.05, 0.05)
                    else:
                        val = random.uniform(1.0, 10.0)
                        
                    hist = IndicatorHistory(
                        company_id=company.id,
                        indicator_id=ind.id,
                        value=float(val),
                        period_date=period_date,
                        period_type='current'
                    )
                    db.session.add(hist)
            
            # Update company status
            company.last_updated = datetime.now()
            
        db.session.commit()
        print("Database seeded with historical test data successfully!")

if __name__ == '__main__':
    run_seeder()
