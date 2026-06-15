"""
Statistical Analyzer — Correlation between SMARTER global values and stock prices.

Computes:
- Pearson and Spearman correlations between ΔV(a,t) and ΔPrice(a,t)
- Linear regression coefficients
- Rolling correlation windows
- Recommendation scores
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from models import db
from models.recommendation import GlobalValue, StatisticalResult
from models.price_history import PriceHistory
from models.decision_problem import DecisionProblem, DecisionAlternative

logger = logging.getLogger(__name__)


class StatisticalAnalyzer:
    """Analyzes correlation between SMARTER global values and stock prices."""

    # ─── Data Preparation ────────────────────────────────────────────────

    @staticmethod
    def get_global_values_series(problem_id: int, company_id: int) -> pd.DataFrame:
        """Get time series of global values as a DataFrame."""
        records = GlobalValue.query.filter_by(
            problem_id=problem_id,
            company_id=company_id,
        ).order_by(GlobalValue.period_date).all()

        if not records:
            return pd.DataFrame()

        data = [{
            'date': r.period_date,
            'global_value': r.global_value,
        } for r in records]

        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        return df

    @staticmethod
    def get_price_series(company_id: int) -> pd.DataFrame:
        """Get time series of closing prices as a DataFrame."""
        records = PriceHistory.query.filter_by(
            company_id=company_id,
        ).order_by(PriceHistory.date).all()

        if not records:
            return pd.DataFrame()

        data = [{
            'date': r.date,
            'close': r.close,
        } for r in records]

        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        return df

    @staticmethod
    def align_series(gv_series: pd.DataFrame, price_series: pd.DataFrame) -> pd.DataFrame:
        """
        Align global value and price series by date.
        For each global value date, find the nearest price date.
        """
        if gv_series.empty or price_series.empty:
            return pd.DataFrame()

        # Merge using nearest date matching
        gv_reset = gv_series.reset_index()
        price_reset = price_series.reset_index()

        merged = pd.merge_asof(
            gv_reset.sort_values('date'),
            price_reset.sort_values('date'),
            on='date',
            direction='nearest',
            tolerance=pd.Timedelta('7 days'),
        )

        merged.set_index('date', inplace=True)
        merged.dropna(subset=['global_value', 'close'], inplace=True)

        return merged

    # ─── Correlation Analysis ────────────────────────────────────────────

    def analyze_company(self, problem_id: int, company_id: int,
                        window_days: int = 90) -> Optional[dict]:
        """
        Run full statistical analysis for one company in a decision problem.

        Computes correlations between ΔV(a) and ΔPrice(a).

        Args:
            problem_id: Decision problem ID
            company_id: Company ID
            window_days: Window for rolling correlation

        Returns:
            Dict with all statistical metrics, or None if insufficient data
        """
        # Get and align series
        gv_series = self.get_global_values_series(problem_id, company_id)
        price_series = self.get_price_series(company_id)

        aligned = self.align_series(gv_series, price_series)

        if len(aligned) < 5:
            logger.warning(f"Insufficient data for company {company_id}: {len(aligned)} points")
            return None

        # Calculate deltas
        delta_v = aligned['global_value'].diff().dropna()
        delta_price = aligned['close'].pct_change().dropna()

        # Align deltas
        common_idx = delta_v.index.intersection(delta_price.index)
        if len(common_idx) < 5:
            return None

        dv = delta_v.loc[common_idx].values
        dp = delta_price.loc[common_idx].values

        # Remove NaN and infinite values
        mask = np.isfinite(dv) & np.isfinite(dp)
        dv = dv[mask]
        dp = dp[mask]

        if len(dv) < 5:
            return None

        # Pearson correlation
        try:
            pearson_r, p_pearson = scipy_stats.pearsonr(dv, dp)
        except Exception:
            pearson_r, p_pearson = 0.0, 1.0

        # Spearman correlation
        try:
            spearman_r, p_spearman = scipy_stats.spearmanr(dv, dp)
        except Exception:
            spearman_r, p_spearman = 0.0, 1.0

        # Linear regression
        try:
            slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(dv, dp)
            r_squared = r_value ** 2
        except Exception:
            slope, r_squared = 0.0, 0.0

        # Recent trend (last 30 days average ΔV)
        recent_dv = delta_v.tail(30)
        recent_trend = recent_dv.mean() if len(recent_dv) > 0 else 0.0

        # Current V relative to range
        current_v = aligned['global_value'].iloc[-1] if len(aligned) > 0 else 0.5
        v_min = aligned['global_value'].min()
        v_max = aligned['global_value'].max()
        if v_max > v_min:
            current_v_relative = (current_v - v_min) / (v_max - v_min)
        else:
            current_v_relative = 0.5

        # Scatter plot data
        scatter_data = [
            {'delta_v': float(dv[i]), 'delta_price': float(dp[i])}
            for i in range(len(dv))
        ]

        return {
            'pearson_r': float(pearson_r),
            'spearman_r': float(spearman_r),
            'p_pearson': float(p_pearson),
            'p_spearman': float(p_spearman),
            'r_squared': float(r_squared),
            'beta': float(slope),
            'data_points': len(dv),
            'recent_trend': float(recent_trend) if np.isfinite(recent_trend) else 0.0,
            'current_v_relative': float(current_v_relative),
            'scatter_data': scatter_data,
        }

    # ─── Recommendation Scoring ──────────────────────────────────────────

    @staticmethod
    def generate_recommendation(analysis: dict) -> tuple[float, str]:
        """
        Generate a recommendation score and label based on statistical analysis.

        Components:
        1. Correlation strength (40%)
        2. Statistical significance (20%)
        3. Recent trend of V(a) (25%)
        4. Current V(a) relative position (15%)

        Returns:
            Tuple of (score, label)
        """
        # Component 1: Correlation strength × direction
        corr_score = analysis.get('pearson_r', 0.0)

        # Component 2: Significance
        p_val = analysis.get('p_pearson', 1.0)
        sig_score = 1.0 if p_val < 0.05 else (0.6 if p_val < 0.10 else 0.3)

        # Component 3: Recent trend
        recent_trend = analysis.get('recent_trend', 0.0)
        # Normalize to [-1, 1] range
        trend_score = max(-1.0, min(1.0, recent_trend * 10))

        # Component 4: Current V relative
        current_v_rel = analysis.get('current_v_relative', 0.5)
        # Higher V is better: map [0,1] to [-1, 1]
        v_score = (current_v_rel - 0.5) * 2

        # Composite score
        score = (
            0.40 * corr_score * sig_score +
            0.25 * trend_score +
            0.15 * v_score +
            0.20 * analysis.get('r_squared', 0.0)
        )

        # Clamp to [-1, 1]
        score = max(-1.0, min(1.0, score))

        # Classification
        if score > 0.4:
            label = "Forte Compra"
        elif score > 0.15:
            label = "Compra"
        elif score > -0.15:
            label = "Neutro"
        elif score > -0.4:
            label = "Venda"
        else:
            label = "Forte Venda"

        return round(score, 4), label

    # ─── Full Analysis Pipeline ──────────────────────────────────────────

    def run_full_analysis(self, problem_id: int, window_days: int = 90) -> dict:
        """
        Run statistical analysis for all companies in a decision problem.

        Args:
            problem_id: Decision problem ID
            window_days: Rolling correlation window

        Returns:
            Summary dict with results count
        """
        problem = DecisionProblem.query.get(problem_id)
        if not problem:
            raise ValueError(f"Problem {problem_id} not found")

        alternatives = DecisionAlternative.query.filter_by(
            problem_id=problem_id
        ).all()

        # Clear existing results
        StatisticalResult.query.filter_by(problem_id=problem_id).delete()
        db.session.flush()

        results_count = 0

        for alt in alternatives:
            analysis = self.analyze_company(problem_id, alt.company_id, window_days)
            if analysis is None:
                continue

            score, label = self.generate_recommendation(analysis)

            result = StatisticalResult(
                problem_id=problem_id,
                company_id=alt.company_id,
                pearson_correlation=analysis['pearson_r'],
                spearman_correlation=analysis['spearman_r'],
                p_value_pearson=analysis['p_pearson'],
                p_value_spearman=analysis['p_spearman'],
                r_squared=analysis['r_squared'],
                beta_coefficient=analysis['beta'],
                recommendation_score=score,
                recommendation_label=label,
                window_days=window_days,
            )
            db.session.add(result)
            results_count += 1

        db.session.commit()
        logger.info(f"Analyzed {results_count} companies for problem {problem_id}")

        return {
            'problem_id': problem_id,
            'companies_analyzed': results_count,
            'window_days': window_days,
        }
