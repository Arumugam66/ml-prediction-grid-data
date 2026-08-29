import os
import json
import pickle
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

logger = logging.getLogger(__name__)

class ModelRegistryManager:
    def __init__(self, base_dir: str = "models_artifacts/xgboost"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def get_latest_version(self) -> Optional[str]:
        """Read latest.json to determine the active version string (e.g. 'v1')."""
        pointer_path = os.path.join(self.base_dir, "latest.json")
        if os.path.exists(pointer_path):
            with open(pointer_path, "r") as f:
                data = json.load(f)
                return data.get("active_version")
        return None

    def get_next_version_name(self) -> str:
        """Determine next version directory name (v1, v2, ...)."""
        latest = self.get_latest_version()
        if not latest:
            return "v1"
        try:
            v_num = int(latest.replace("v", ""))
            return f"v{v_num + 1}"
        except Exception:
            return "v1"

    def register_model_version(
        self,
        model_obj: Any,
        feature_list: List[str],
        metadata: Dict[str, Any],
        version_name: Optional[str] = None
    ) -> str:
        """Save trained model, feature list, and metadata to version dir and update latest.json."""
        if not version_name:
            version_name = self.get_next_version_name()

        version_dir = os.path.join(self.base_dir, version_name)
        os.makedirs(version_dir, exist_ok=True)

        # 1. Save model.pkl
        pkl_path = os.path.join(version_dir, "model.pkl")
        with open(pkl_path, "wb") as f:
            pickle.dump(model_obj, f)

        # 2. Save feature_list.json
        feature_path = os.path.join(version_dir, "feature_list.json")
        with open(feature_path, "w") as f:
            json.dump(feature_list, f, indent=2)

        # 3. Save metadata.json
        metadata["version"] = version_name
        metadata["saved_at"] = datetime.now().isoformat()
        metadata_path = os.path.join(version_dir, "metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # 4. Save model.json summary
        model_json_path = os.path.join(version_dir, "model.json")
        with open(model_json_path, "w") as f:
            json.dump({
                "architecture": "MultiOutputRegressor(XGBRegressor)",
                "target_variables": ["EBKwh_delta", "DGKwh_delta"],
                "n_features": len(feature_list),
                "model_file": "model.pkl"
            }, f, indent=2)

        # 5. Update latest.json active pointer
        pointer_path = os.path.join(self.base_dir, "latest.json")
        with open(pointer_path, "w") as f:
            json.dump({
                "active_version": version_name,
                "updated_at": datetime.now().isoformat()
            }, f, indent=2)

        logger.info(f"Registered model version '{version_name}' in {version_dir}")
        return version_name

    def load_active_model(self) -> Tuple[Any, List[str], Dict[str, Any], str]:
        """Load active model artifact, feature list, metadata based on latest.json."""
        latest_version = self.get_latest_version()
        if not latest_version:
            raise FileNotFoundError("No active version pointer found in models_artifacts/xgboost/latest.json")

        version_dir = os.path.join(self.base_dir, latest_version)
        pkl_path = os.path.join(version_dir, "model.pkl")
        feature_path = os.path.join(version_dir, "feature_list.json")
        metadata_path = os.path.join(version_dir, "metadata.json")

        if not os.path.exists(pkl_path):
            raise FileNotFoundError(f"Model file missing: {pkl_path}")

        with open(pkl_path, "rb") as f:
            model = pickle.load(f)

        with open(feature_path, "r") as f:
            features = json.load(f)

        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        return model, features, metadata, latest_version
