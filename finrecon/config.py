from dataclasses import dataclass
from pathlib import Path
import os

@dataclass
class ReconciliationConfig:
    # Deterministic matching parameters
    date_window_deterministic_days: int = 10
    
    # Fuzzy matching parameters
    date_window_fuzzy_days: int = 5
    fuzzy_similarity_threshold: float = 0.80
    
    # Fee deduction parameters
    rounding_tolerance: float = 0.05
    min_expected_fee_rate: float = 0.012  # 1.2%
    max_expected_fee_rate: float = 0.045  # 4.5%
    fee_spike_threshold: float = 0.050    # 5.0% flags as anomaly
    
    # 1-to-N batch parameters
    batch_window_days: int = 4
    batch_rounding_tolerance: float = 0.15
    batch_max_combination_size: int = 8
    
    # Anomaly Sentinel parameters
    duplicate_time_window_seconds: int = 300  # 5 minutes
    aging_threshold_days: int = 30
    
    # Storage & paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    sample_data_dir: Path = Path(__file__).resolve().parent.parent / "data" / "samples"
    storage_dir: Path = Path(__file__).resolve().parent.parent / "storage_data"
    sqlite_db_path: Path = Path(__file__).resolve().parent.parent / "storage_data" / "finrecon_audit.db"

# Global default config instance
DEFAULT_CONFIG = ReconciliationConfig()
