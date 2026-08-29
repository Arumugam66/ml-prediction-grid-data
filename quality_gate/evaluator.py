import logging
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class QualityGateEvaluator:
    def __init__(self, min_r2: float = 0.50, max_rmse: float = 15.0, max_mape: float = 25.0):
        self.min_r2 = min_r2
        self.max_rmse = max_rmse
        self.max_mape = max_mape

    def evaluate(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        target_names: list = None
    ) -> Tuple[bool, Dict[str, Any]]:
        if target_names is None:
            target_names = ["EBKwh_delta", "DGKwh_delta"]

        y_true = np.array(y_true)
        y_pred = np.array(y_pred)

        metrics = {}
        passed_all = True

        for i, name in enumerate(target_names):
            y_t = y_true[:, i] if y_true.ndim > 1 else y_true
            y_p = y_pred[:, i] if y_pred.ndim > 1 else y_pred

            mae = float(mean_absolute_error(y_t, y_p))
            rmse = float(np.sqrt(mean_squared_error(y_t, y_p)))
            
            # Avoid negative or undefined r2 when variance is tiny or predictions are almost exact
            var_t = np.var(y_t)
            if var_t < 1e-4 and rmse < 1.0:
                r2 = 1.0
            else:
                r2_val = r2_score(y_t, y_p)
                r2 = float(max(0.0, r2_val)) if not np.isnan(r2_val) else 0.0

            # Safe MAPE
            non_zero_mask = np.abs(y_t) > 0.01
            if np.sum(non_zero_mask) > 0:
                mape = float(np.mean(np.abs((y_t[non_zero_mask] - y_p[non_zero_mask]) / y_t[non_zero_mask])) * 100.0)
            else:
                mape = 0.0

            # Quality gate criteria: passes if RMSE is low or R2 meets target threshold
            r2_pass = r2 >= self.min_r2 or (rmse < 1.0)
            rmse_pass = rmse <= self.max_rmse

            target_passed = r2_pass and rmse_pass
            if not target_passed:
                passed_all = False

            metrics[name] = {
                "mae": round(mae, 4),
                "rmse": round(rmse, 4),
                "r2": round(r2, 4),
                "mape": round(mape, 2),
                "quality_gate_passed": target_passed
            }

        summary = {
            "overall_passed": passed_all,
            "thresholds": {
                "min_r2": self.min_r2,
                "max_rmse": self.max_rmse,
                "max_mape": self.max_mape
            },
            "metrics": metrics
        }

        logger.info(f"Quality Gate Evaluation Result: overall_passed={passed_all}, metrics={metrics}")
        return passed_all, summary
