from dataclasses import dataclass
from typing import Dict
import os
import json


@dataclass
class SchedulingConfig:
    productivity: Dict[str, int]
    minimums: Dict[str, int]


def load_scheduling_config() -> SchedulingConfig:
    """Load scheduling configuration from env JSON or defaults.
    Env var STAFF_SCHEDULING_PRODUCTIVITY_JSON can contain:
    {
      "productivity": {"Manager": 100, ...},
      "minimums": {"Manager": 1, ...}
    }
    """
    default_productivity = {
        "Manager": 100,
        "Chef": 15,
        "Server": 12,
        "Dishwasher": 35,
    }
    default_minimums = {
        "Manager": 1,
        "Chef": 1,
        "Server": 2,
        "Dishwasher": 1,
    }
    raw = os.getenv("STAFF_SCHEDULING_PRODUCTIVITY_JSON")
    if not raw:
        return SchedulingConfig(productivity=default_productivity, minimums=default_minimums)
    try:
        parsed = json.loads(raw)
        prod = parsed.get("productivity") or {}
        mins = parsed.get("minimums") or {}
        # Merge with defaults
        merged_prod = {**default_productivity, **prod}
        merged_mins = {**default_minimums, **mins}
        return SchedulingConfig(productivity=merged_prod, minimums=merged_mins)
    except Exception:
        # Fallback to defaults on parse error
        return SchedulingConfig(productivity=default_productivity, minimums=default_minimums)