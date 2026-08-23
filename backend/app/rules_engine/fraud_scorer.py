"""
Fraud / Anomaly Scorer
Uses a lightweight scoring model (rule-based with scoring weights for POC,
can be swapped to LightGBM in production without code changes).
All inference is local — never calls cloud.
"""
import logging
import datetime
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class FraudScorer:
    """
    Behavioral anomaly scorer.
    POC: weighted rule-based scoring (deterministic, explainable).
    Production: swap score() to call a trained LightGBM model.
    """

    # Feature weights (tunable via config in production)
    FEATURE_WEIGHTS = {
        "resubmission_count_1h": 0.30,       # Strong signal
        "resubmission_count_24h": 0.15,
        "field_mismatch_rate": 0.25,          # OCR vs declared
        "application_hour_odd": 0.10,         # Apps at 1-4am
        "correction_count": 0.10,
        "channel_switches": 0.05,
        "doc_income_delta_pct": 0.05,
    }

    @classmethod
    def score(cls, features: Dict) -> Tuple[float, List[str], str]:
        """
        Returns (anomaly_score, top_features, decision).
        decision: PASS | MANUAL_REVIEW | REJECT
        """
        total = 0.0
        top_features = []

        # Resubmission in last hour (strong signal)
        resub_1h = features.get("resubmission_count_1h", 0)
        if resub_1h >= 3:
            contrib = cls.FEATURE_WEIGHTS["resubmission_count_1h"]
            total += contrib
            top_features.append(f"resubmission_1h={resub_1h}")

        # Resubmission in 24h
        resub_24h = features.get("resubmission_count_24h", 0)
        if resub_24h >= 5:
            contrib = cls.FEATURE_WEIGHTS["resubmission_count_24h"]
            total += contrib
            top_features.append(f"resubmission_24h={resub_24h}")

        # Field mismatch rate (OCR vs declared)
        mismatch_rate = features.get("field_mismatch_rate", 0.0)
        if mismatch_rate > 0.3:
            contrib = cls.FEATURE_WEIGHTS["field_mismatch_rate"] * min(mismatch_rate / 0.3, 1.0)
            total += contrib
            top_features.append(f"mismatch_rate={mismatch_rate:.2f}")

        # Odd hours (1am - 4am)
        hour = features.get("application_hour", 12)
        if 1 <= hour <= 4:
            contrib = cls.FEATURE_WEIGHTS["application_hour_odd"]
            total += contrib
            top_features.append(f"odd_hour={hour}")

        # Many corrections
        corrections = features.get("correction_count", 0)
        if corrections >= 5:
            contrib = cls.FEATURE_WEIGHTS["correction_count"] * min(corrections / 5, 1.0)
            total += contrib
            top_features.append(f"corrections={corrections}")

        # Many channel switches
        switches = features.get("channel_switches", 0)
        if switches >= 3:
            contrib = cls.FEATURE_WEIGHTS["channel_switches"]
            total += contrib
            top_features.append(f"channel_switches={switches}")

        # Large income delta between doc and declared
        income_delta = features.get("doc_income_delta_pct", 0.0)
        if income_delta > 0.30:
            contrib = cls.FEATURE_WEIGHTS["doc_income_delta_pct"] * min(income_delta / 0.30, 1.0)
            total += contrib
            top_features.append(f"income_delta={income_delta:.0%}")

        score = min(total, 1.0)

        from app.core.config import settings
        if score >= settings.FRAUD_SCORE_THRESHOLD_REJECT:
            decision = "REJECT"
        elif score >= settings.FRAUD_SCORE_THRESHOLD_REVIEW:
            decision = "MANUAL_REVIEW"
        else:
            decision = "PASS"

        return round(score, 4), top_features, decision

    @classmethod
    def build_features(cls, session_data: Dict, db_stats: Dict) -> Dict:
        """Build feature vector from session and DB stats."""
        return {
            "resubmission_count_1h": db_stats.get("resubmission_count_1h", 0),
            "resubmission_count_24h": db_stats.get("resubmission_count_24h", 0),
            "field_mismatch_rate": session_data.get("field_mismatch_rate", 0.0),
            "application_hour": datetime.datetime.utcnow().hour,
            "correction_count": len(session_data.get("correction_history", [])),
            "channel_switches": len(set(session_data.get("channel_history", []))),
            "doc_income_delta_pct": session_data.get("doc_income_delta_pct", 0.0),
        }
