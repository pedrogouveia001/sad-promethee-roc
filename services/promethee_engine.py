"""
PROMETHEE Engine — Core multicriteria decision analysis module.

Implements the PROMETHEE II complete ranking method with:
- ROC (Rank Order Centroid) weight calculation for criteria
- Linear Preference Function (Type V) with automatic period-based parameter p
- Calculation of leaving flow (Phi+), entering flow (Phi-), and net flow (Phi)
- Net flow Phi(a, t) saved as the global value across all historical periods
"""

import logging
from datetime import date
from typing import Optional

from sqlalchemy import func

from models import db
from models.indicator_history import IndicatorHistory
from models.decision_problem import DecisionProblem, DecisionCriteria, DecisionAlternative
from models.recommendation import GlobalValue

logger = logging.getLogger(__name__)


class PROMETHEEEngine:
    """Core PROMETHEE II multicriteria decision analysis engine with ROC weights."""

    # ─── ROC Weight Calculation ──────────────────────────────────────────

    @staticmethod
    def calculate_roc_weights(n: int) -> list[float]:
        """
        Calculate Rank Order Centroid (ROC) weights for N ranked criteria.

        Formula: w_i = (1/N) * Σ(1/j) for j = i to N

        Args:
            n: Number of criteria

        Returns:
            List of weights (sum = 1.0), ordered from rank 1 to N
        """
        if n <= 0:
            return []

        weights = []
        for i in range(1, n + 1):
            w_i = (1.0 / n) * sum(1.0 / j for j in range(i, n + 1))
            weights.append(w_i)

        return weights

    # ─── Normalization (for UI Display / Bounds) ─────────────────────────

    @staticmethod
    def normalize_value(value: float, min_hist: float, max_hist: float,
                         is_cost: bool) -> float:
        """
        Normalize a raw indicator value to [0, 1] using interval scale.
        Used primarily for UI visualization.
        """
        if max_hist == min_hist:
            return 0.5

        if is_cost:
            normalized = (max_hist - value) / (max_hist - min_hist)
        else:
            normalized = (value - min_hist) / (max_hist - min_hist)

        return max(0.0, min(1.0, normalized))

    # ─── Historical Bounds ───────────────────────────────────────────────

    @staticmethod
    def get_historical_bounds(indicator_id: int) -> tuple[Optional[float], Optional[float]]:
        """
        Get the global historical min and max for an indicator.
        """
        result = db.session.query(
            func.min(IndicatorHistory.value),
            func.max(IndicatorHistory.value)
        ).filter(
            IndicatorHistory.indicator_id == indicator_id,
            IndicatorHistory.value.isnot(None)
        ).first()

        if result and result[0] is not None:
            return result[0], result[1]
        return None, None

    # ─── Available Periods ───────────────────────────────────────────────

    @staticmethod
    def get_available_periods(company_ids: list[int]) -> list[date]:
        """
        Get all unique period dates for the given companies.
        """
        dates = db.session.query(
            IndicatorHistory.period_date
        ).filter(
            IndicatorHistory.company_id.in_(company_ids),
            IndicatorHistory.value.isnot(None)
        ).distinct().order_by(
            IndicatorHistory.period_date
        ).all()

        return [d[0] for d in dates]

    # ─── PROMETHEE II Calculation ───────────────────────────────────────

    def calculate_promethee_for_period(
        self,
        company_ids: list[int],
        period_date: date,
        criteria: list[DecisionCriteria],
        bounds_cache: dict
    ) -> dict[int, tuple[float, dict]]:
        """
        Calculate PROMETHEE II net flows for a list of companies in a specific period.

        Args:
            company_ids: List of company IDs
            period_date: Date of the period
            criteria: List of DecisionCriteria (ordered by rank)
            bounds_cache: Cache of historical bounds

        Returns:
            Dict of {company_id: (net_flow, {indicator_code: normalized_value})}
        """
        # 1. Fetch values for all companies in this period
        company_values = {}  # {company_id: {indicator_id: value}}
        for company_id in company_ids:
            company_values[company_id] = {}
            for criterion in criteria:
                record = IndicatorHistory.query.filter(
                    IndicatorHistory.company_id == company_id,
                    IndicatorHistory.indicator_id == criterion.indicator_id,
                    IndicatorHistory.period_date == period_date,
                    IndicatorHistory.value.isnot(None)
                ).first()
                if record:
                    company_values[company_id][criterion.indicator_id] = record.value

        # 2. Filter companies that have at least some data in this period
        active_companies = [c for c in company_ids if len(company_values[c]) > 0]
        m = len(active_companies)
        if m == 0:
            return {}

        # 3. Filter criteria that have data for at least one active company
        available_criteria = []
        for c in criteria:
            has_data = any(c.indicator_id in company_values[comp] for comp in active_companies)
            if has_data:
                available_criteria.append(c)

        n = len(available_criteria)
        if n == 0:
            return {c_id: (0.0, {}) for c_id in active_companies}

        # 4. Calculate ROC weights for the available criteria
        roc_weights = self.calculate_roc_weights(n)
        weights_dict = {criterion.indicator_id: roc_weights[i] for i, criterion in enumerate(available_criteria)}

        # 5. Compute pairwise preferences P_j(a, b) and global preference Pi(a, b)
        # Pi(a, b) = sum_j (w_j * P_j(a, b))
        pi = {a: {b: 0.0 for b in active_companies} for a in active_companies}

        for criterion in available_criteria:
            ind_id = criterion.indicator_id
            w_j = weights_dict[ind_id]
            is_cost = criterion.criteria_type == 'cost'

            # Extract values for this criterion in this period
            values = {c: company_values[c][ind_id] for c in active_companies if ind_id in company_values[c]}
            if len(values) < 2:
                continue

            # Linear preference parameter p_j = max_val - min_val in this period
            max_val = max(values.values())
            min_val = min(values.values())
            p_j = max_val - min_val

            # Compute pairwise preference P_j(a, b)
            for a in active_companies:
                for b in active_companies:
                    if a == b or ind_id not in company_values[a] or ind_id not in company_values[b]:
                        continue

                    val_a = company_values[a][ind_id]
                    val_b = company_values[b][ind_id]

                    # Difference
                    d = (val_a - val_b) if not is_cost else (val_b - val_a)

                    # Linear preference function (Type V)
                    if d <= 0:
                        preference = 0.0
                    else:
                        preference = d / p_j if p_j > 0 else 0.0

                    pi[a][b] += w_j * preference

        # 6. Calculate flows (leaving, entering, net)
        results = {}
        for a in active_companies:
            if m > 1:
                leaving_flow = sum(pi[a][b] for b in active_companies if b != a) / (m - 1)
                entering_flow = sum(pi[b][a] for b in active_companies if b != a) / (m - 1)
                net_flow = leaving_flow - entering_flow
            else:
                net_flow = 0.0

            # Generate normalized values for UI display
            norm_vals = {}
            for criterion in criteria:
                ind_id = criterion.indicator_id
                ind_code = criterion.indicator.code if criterion.indicator else str(ind_id)
                
                # Check if the company has value for this indicator
                if ind_id in company_values[a]:
                    raw_val = company_values[a][ind_id]
                    bounds = bounds_cache.get(ind_id)
                    if bounds and bounds[0] is not None:
                        min_hist, max_hist = bounds
                        norm_vals[ind_code] = round(self.normalize_value(raw_val, min_hist, max_hist, criterion.criteria_type == 'cost'), 6)

            results[a] = (net_flow, norm_vals)

        return results

    # ─── Full Calculation Pipeline ───────────────────────────────────────

    def run_full_calculation(self, problem_id: int) -> dict:
        """
        Run the complete PROMETHEE II calculation for a decision problem.
        Computes the Net Flow Phi(a, t) for all companies and periods.
        """
        problem = DecisionProblem.query.get(problem_id)
        if not problem:
            raise ValueError(f"Decision problem {problem_id} not found")

        criteria = DecisionCriteria.query.filter_by(
            problem_id=problem_id
        ).order_by(DecisionCriteria.rank_position).all()

        if not criteria:
            raise ValueError("No criteria defined for this problem")

        n = len(criteria)
        roc_weights = self.calculate_roc_weights(n)
        for i, criterion in enumerate(criteria):
            criterion.roc_weight = roc_weights[i]
        db.session.flush()

        alternatives = DecisionAlternative.query.filter_by(
            problem_id=problem_id
        ).all()
        company_ids = [a.company_id for a in alternatives]

        if not company_ids:
            raise ValueError("No alternatives selected for this problem")

        bounds_cache = {}
        for criterion in criteria:
            bounds_cache[criterion.indicator_id] = self.get_historical_bounds(criterion.indicator_id)

        all_periods = self.get_available_periods(company_ids)
        logger.info(f"Calculating PROMETHEE II Phi(a,t) for {len(company_ids)} companies × {len(all_periods)} periods")

        # Clear existing results
        GlobalValue.query.filter_by(problem_id=problem_id).delete()
        db.session.flush()

        total_calculated = 0
        for period in all_periods:
            period_results = self.calculate_promethee_for_period(
                company_ids, period, criteria, bounds_cache
            )
            for company_id, (net_flow, norm_vals) in period_results.items():
                global_val = GlobalValue(
                    problem_id=problem_id,
                    company_id=company_id,
                    period_date=period,
                    # We store the PROMETHEE Net Flow in the global_value field
                    global_value=net_flow,
                )
                global_val.normalized_values = norm_vals
                db.session.add(global_val)
                total_calculated += 1

        db.session.commit()
        logger.info(f"Calculated {total_calculated} PROMETHEE net flows for problem {problem_id}")

        return {
            'problem_id': problem_id,
            'companies': len(company_ids),
            'periods': len(all_periods),
            'total_calculated': total_calculated,
            'criteria_weights': {c.indicator.code: c.roc_weight for c in criteria},
            'method': 'PROMETHEE-II ROC'
        }
