"""Estimators with training-fold-specific imbalance handling."""

import numpy as np
from xgboost import XGBClassifier


class BalancedXGBClassifier(XGBClassifier):
    """Set XGBoost's positive-class weight from each fit's own labels."""

    def fit(self, X, y, **kwargs):
        labels = np.asarray(y)
        negatives = int(np.count_nonzero(labels == 0))
        positives = int(np.count_nonzero(labels == 1))
        if negatives + positives != len(labels) or not negatives or not positives:
            raise ValueError("XGBoost requires both non-null binary target classes.")
        self.set_params(scale_pos_weight=negatives / positives)
        return super().fit(X, y, **kwargs)
