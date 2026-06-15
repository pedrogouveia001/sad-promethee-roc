"""
Data Collector Service — Fetches financial data from brapi.dev and yfinance.

Handles:
- Listing all available B3 stocks
- Fetching current indicators (fundamentalist data)
- Fetching historical price data
- Rate limiting and fallback logic
"""

import logging
import time
from datetime import datetime, date, timezone
from typing import Optional

import requests

from models import db
from models.company import Company
from models.sector import Sector
from models.indicator import IndicatorDefinition
from models.indicator_history import IndicatorHistory
from models.price_history import PriceHistory

logger = logging.getLogger(__name__)


class DataCollector:
    """Collects financial data from brapi.dev (primary) and yfinance (fallback)."""

    def __init__(self, app=None):
        self.brapi_token = ''
        self.brapi_base_url = 'https://brapi.dev/api'
        self.rate_limit = 1.0
        self._last_request_time = 0
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.brapi_token = app.config.get('BRAPI_TOKEN', '')
        self.brapi_base_url = app.config.get('BRAPI_BASE_URL', 'https://brapi.dev/api')
        self.rate_limit = app.config.get('API_RATE_LIMIT_SECONDS', 1.0)

    # ─── Rate Limiting ───────────────────────────────────────────────────

    def _wait_for_rate_limit(self):
        """Enforce minimum delay between API requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    # ─── brapi.dev API Calls ─────────────────────────────────────────────

    def _brapi_get(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """Make a GET request to brapi.dev with rate limiting and error handling."""
        self._wait_for_rate_limit()

        url = f"{self.brapi_base_url}{endpoint}"
        headers = {}
        if self.brapi_token:
            headers['Authorization'] = f'Bearer {self.brapi_token}'

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"brapi HTTP error for {endpoint}: {e}")
            if e.response and e.response.status_code == 429:
                logger.warning("Rate limited by brapi.dev, waiting 60s...")
                time.sleep(60)
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"brapi request error for {endpoint}: {e}")
            return None

    # ─── List All Stocks ─────────────────────────────────────────────────

    def fetch_stock_list(self) -> list[dict]:
        """
        Fetch list of all available stocks from brapi.dev.

        Returns:
            List of stock dicts with ticker, name, sector info
        """
        all_stocks = []
        page = 1

        while True:
            data = self._brapi_get('/quote/list', params={
                'type': 'stock',
                'limit': 100,
                'page': page,
            })

            if not data or 'stocks' not in data:
                break

            stocks = data['stocks']
            if not stocks:
                break

            all_stocks.extend(stocks)
            page += 1

            # Safety limit
            if page > 20:
                break

        logger.info(f"Fetched {len(all_stocks)} stocks from brapi.dev")
        return all_stocks

    def sync_companies(self) -> int:
        """
        Sync the companies table with the latest stock list from brapi.dev.

        Returns:
            Number of companies synced
        """
        stocks = self.fetch_stock_list()
        count = 0

        for stock in stocks:
            ticker = stock.get('stock')
            if not ticker:
                continue

            # Only include common (ON/3) and preferred (PN/4) stocks
            # Skip BDRs, ETFs, Units, etc.
            last_char = ticker[-1] if ticker else ''
            if last_char not in ('3', '4', '5', '6', '11'):
                # Include ON(3), PN(4), PNA(5), PNB(6), UNIT(11)
                pass

            # Find or create sector
            sector_name = stock.get('sector', 'Outros')
            sector = Sector.query.filter_by(name=sector_name).first()
            if not sector and sector_name:
                sector = Sector(name=sector_name)
                db.session.add(sector)
                db.session.flush()

            # Find or create company
            company = Company.query.filter_by(ticker=ticker).first()
            if company:
                company.name = stock.get('name', company.name)
                company.logo_url = stock.get('logo', company.logo_url)
                if sector:
                    company.sector_id = sector.id
            else:
                company = Company(
                    ticker=ticker,
                    name=stock.get('name', ticker),
                    full_name=stock.get('name', ''),
                    sector_id=sector.id if sector else None,
                    logo_url=stock.get('logo'),
                    is_active=True,
                )
                db.session.add(company)

            count += 1

        db.session.commit()
        logger.info(f"Synced {count} companies")
        return count

    # ─── Fetch Indicators ────────────────────────────────────────────────

    def fetch_indicators(self, ticker: str) -> Optional[dict]:
        """
        Fetch current fundamental indicators for a ticker.

        Args:
            ticker: Stock ticker (e.g., 'PETR4')

        Returns:
            Dict with indicator values, or None on failure
        """
        data = self._brapi_get(f'/quote/{ticker}', params={
            'modules': 'defaultKeyStatistics,financialData,summaryProfile',
        })

        if not data or 'results' not in data or not data['results']:
            return None

        result = data['results'][0]

        # Extract indicators from nested API response
        indicators = {}
        financial_data = result.get('financialData', {})
        key_stats = result.get('defaultKeyStatistics', {})

        # Map API fields to our indicator codes
        field_mapping = {
            'trailingPE': ('trailing_pe', key_stats),
            'priceToBook': ('price_to_book', key_stats),
            'enterpriseToEbitda': ('ev_ebitda', key_stats),
            'priceToSalesTrailing12Months': ('price_to_sales', key_stats),
            'enterpriseToRevenue': ('ev_revenue', key_stats),
            'returnOnEquity': ('roe', financial_data),
            'returnOnAssets': ('roa', financial_data),
            'profitMargins': ('profit_margin', financial_data),
            'ebitdaMargins': ('ebitda_margin', financial_data),
            'operatingMargins': ('operating_margin', financial_data),
            'grossMargins': ('gross_margin', financial_data),
            'dividendYield': ('dividend_yield', key_stats),
            'payoutRatio': ('payout_ratio', key_stats),
            'debtToEquity': ('debt_to_equity', financial_data),
            'currentRatio': ('current_ratio', financial_data),
            'quickRatio': ('quick_ratio', financial_data),
            'revenueGrowth': ('revenue_growth', financial_data),
            'earningsGrowth': ('earnings_growth', financial_data),
        }

        for api_key, (our_code, source) in field_mapping.items():
            value = source.get(api_key)
            # Handle nested dict format from brapi (sometimes {raw: X, fmt: "Y"})
            if isinstance(value, dict):
                value = value.get('raw', value.get('fmt'))
            if value is not None:
                try:
                    indicators[our_code] = float(value)
                except (ValueError, TypeError):
                    pass

        # Also get current price
        indicators['_current_price'] = result.get('regularMarketPrice')
        indicators['_ticker'] = ticker

        return indicators

    def save_indicators(self, ticker: str, indicators: dict,
                        period_date: Optional[date] = None) -> int:
        """
        Save fetched indicator values to the indicator_history table.

        Args:
            ticker: Stock ticker
            indicators: Dict of {indicator_code: value}
            period_date: Date for this snapshot (default: today)

        Returns:
            Number of indicators saved
        """
        if period_date is None:
            period_date = date.today()

        company = Company.query.filter_by(ticker=ticker).first()
        if not company:
            logger.warning(f"Company {ticker} not found in database")
            return 0

        count = 0
        for code, value in indicators.items():
            if code.startswith('_'):
                continue  # Skip internal fields

            indicator_def = IndicatorDefinition.query.filter_by(code=code).first()
            if not indicator_def:
                continue

            # Upsert
            existing = IndicatorHistory.query.filter_by(
                company_id=company.id,
                indicator_id=indicator_def.id,
                period_date=period_date,
                period_type='current',
            ).first()

            if existing:
                existing.value = value
            else:
                history = IndicatorHistory(
                    company_id=company.id,
                    indicator_id=indicator_def.id,
                    value=value,
                    period_date=period_date,
                    period_type='current',
                )
                db.session.add(history)

            count += 1

        company.last_updated = datetime.now(timezone.utc)
        db.session.commit()
        return count

    # ─── Fetch Historical Prices ─────────────────────────────────────────

    def fetch_price_history(self, ticker: str, range_str: str = '5y') -> list[dict]:
        """
        Fetch historical price data from brapi.dev.

        Args:
            ticker: Stock ticker
            range_str: Time range ('1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'max')

        Returns:
            List of OHLCV dicts
        """
        data = self._brapi_get(f'/quote/{ticker}', params={
            'range': range_str,
            'interval': '1d',
        })

        if not data or 'results' not in data or not data['results']:
            return []

        result = data['results'][0]
        history = result.get('historicalDataPrice', [])
        return history

    def save_price_history(self, ticker: str, prices: list[dict]) -> int:
        """
        Save historical price data to the price_history table.

        Args:
            ticker: Stock ticker
            prices: List of OHLCV dicts from the API

        Returns:
            Number of prices saved
        """
        company = Company.query.filter_by(ticker=ticker).first()
        if not company:
            return 0

        count = 0
        for price in prices:
            ts = price.get('date')
            if not ts:
                continue

            # brapi returns Unix timestamp
            try:
                price_date = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            except (ValueError, OSError):
                continue

            close = price.get('close')
            if close is None:
                continue

            existing = PriceHistory.query.filter_by(
                company_id=company.id,
                date=price_date,
            ).first()

            if not existing:
                ph = PriceHistory(
                    company_id=company.id,
                    date=price_date,
                    open=price.get('open'),
                    high=price.get('high'),
                    low=price.get('low'),
                    close=close,
                    adj_close=price.get('adjustedClose', close),
                    volume=price.get('volume'),
                )
                db.session.add(ph)
                count += 1

        db.session.commit()
        logger.info(f"Saved {count} price records for {ticker}")
        return count

    # ─── yfinance Fallback ───────────────────────────────────────────────

    def fetch_indicators_yfinance(self, ticker: str) -> Optional[dict]:
        """
        Fallback: fetch indicators using yfinance.

        Args:
            ticker: Stock ticker (without .SA suffix)

        Returns:
            Dict of indicator values, or None
        """
        try:
            import yfinance as yf

            yf_ticker = yf.Ticker(f"{ticker}.SA")
            info = yf_ticker.info

            if not info or info.get('regularMarketPrice') is None:
                return None

            indicators = {}
            mapping = {
                'trailingPE': 'trailing_pe',
                'priceToBook': 'price_to_book',
                'enterpriseToEbitda': 'ev_ebitda',
                'priceToSalesTrailing12Months': 'price_to_sales',
                'enterpriseToRevenue': 'ev_revenue',
                'returnOnEquity': 'roe',
                'returnOnAssets': 'roa',
                'profitMargins': 'profit_margin',
                'ebitdaMargins': 'ebitda_margin',
                'operatingMargins': 'operating_margin',
                'grossMargins': 'gross_margin',
                'dividendYield': 'dividend_yield',
                'payoutRatio': 'payout_ratio',
                'debtToEquity': 'debt_to_equity',
                'currentRatio': 'current_ratio',
                'quickRatio': 'quick_ratio',
                'revenueGrowth': 'revenue_growth',
                'earningsGrowth': 'earnings_growth',
            }

            for api_key, our_code in mapping.items():
                value = info.get(api_key)
                if value is not None:
                    try:
                        indicators[our_code] = float(value)
                    except (ValueError, TypeError):
                        pass

            indicators['_current_price'] = info.get('regularMarketPrice')
            indicators['_ticker'] = ticker
            return indicators

        except Exception as e:
            logger.error(f"yfinance fallback failed for {ticker}: {e}")
            return None

    # ─── Full Collection Pipeline ────────────────────────────────────────

    def collect_all(self, tickers: list[str] = None, price_range: str = '5y') -> dict:
        """
        Run full data collection for all or specified tickers.

        Args:
            tickers: Optional list of tickers (default: all companies in DB)
            price_range: Price history range to fetch

        Returns:
            Summary dict with collection statistics
        """
        if tickers is None:
            companies = Company.query.filter_by(is_active=True).all()
            tickers = [c.ticker for c in companies]

        stats = {
            'total': len(tickers),
            'indicators_success': 0,
            'indicators_failed': 0,
            'prices_success': 0,
            'prices_failed': 0,
        }

        for i, ticker in enumerate(tickers):
            logger.info(f"Collecting [{i+1}/{len(tickers)}] {ticker}...")

            # Fetch indicators
            indicators = self.fetch_indicators(ticker)
            if indicators is None:
                # Fallback to yfinance
                indicators = self.fetch_indicators_yfinance(ticker)

            if indicators:
                saved = self.save_indicators(ticker, indicators)
                stats['indicators_success'] += 1
                logger.info(f"  {ticker}: {saved} indicators saved")
            else:
                stats['indicators_failed'] += 1
                logger.warning(f"  {ticker}: Failed to fetch indicators")

            # Fetch price history
            prices = self.fetch_price_history(ticker, price_range)
            if prices:
                saved = self.save_price_history(ticker, prices)
                stats['prices_success'] += 1
            else:
                stats['prices_failed'] += 1

        logger.info(f"Collection complete: {stats}")
        return stats
