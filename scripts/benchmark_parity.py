"""
scripts/benchmark_parity.py
Side-by-side performance and parity benchmark between DirectOdooBackend and BridgeOdooBackend.
"""

import os
import sys
from pathlib import Path

backend_dir = Path("zelix-copilot-backend").resolve()
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

bridge_dir = Path("packages/alamia-odoobridge/src").resolve()
if str(bridge_dir) not in sys.path:
    sys.path.insert(0, str(bridge_dir))

from adapters.odoo.zelix_odoo_adapter import ZelixOdooAdapter

api_key = os.getenv("ODOO_LIVE_TEST_API_KEY", "776c4ef9323d0b42585b89613448d4b9401801f0")
adapter = ZelixOdooAdapter(mode="dual", api_key=api_key)

# Warmup call
adapter.search("clinic", limit=1)
adapter.reset_parity_telemetry()

# Benchmark loop
for _ in range(10):
    adapter.search("clinic", limit=5)
    adapter.search("patient", limit=5)
    adapter.find_patient("Max")

summary = adapter.get_parity_telemetry()

print("Parity Benchmark Results:")
print("  Total Operations:", summary["total_operations"])
print("  Matched Operations:", summary["matched_operations"])
print("  Parity Rate:", f"{summary['parity_rate_pct']}%")
print("  Avg Direct Latency:", f"{summary['avg_direct_latency_ms']} ms")
print("  Avg Bridge Latency:", f"{summary['avg_bridge_latency_ms']} ms")
print("  Discrepancies:", summary["discrepancy_count"])
