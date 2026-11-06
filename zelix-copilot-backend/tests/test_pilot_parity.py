"""
tests/test_pilot_parity.py
Side-by-side parity verification test suite between DirectOdooBackend and BridgeOdooBackend.
Covers the 5 parity dimensions specified in the ZelixVet Controlled Integration Pilot Plan.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from adapters.odoo.zelix_odoo_adapter import ZelixOdooAdapter
from adapters.odoo.direct_backend import DirectOdooBackend
from adapters.odoo.bridge_backend import BridgeOdooBackend
from adapters.odoo.comparator import ParityComparator


@pytest.fixture
def mock_odoo_responses():
    """Mock dataset mimicking VetCairn Odoo 19 database."""
    patients = [
        {
            "id": 1,
            "name": "Bella",
            "identifier": "PAT-000001",
            "species_id": [1, "Canine"],
            "breed_id": [2, "Labrador Retriever"],
            "clinic_id": [3, "Downtown Vet Clinic"],
            "notes": "Healthy active adult",
        },
        {
            "id": 2,
            "name": "Max",
            "identifier": "PAT-000002",
            "species_id": [1, "Canine"],
            "breed_id": [4, "German Shepherd"],
            "clinic_id": [3, "Downtown Vet Clinic"],
            "notes": "History of acute gastroenteritis",
        },
    ]

    hms_patients = [
        {
            "id": 10,
            "name": "John Doe",
            "mrn": "MRN-10023",
            "chronic_conditions": "Hypertension",
        }
    ]

    appointments = [
        {
            "id": 101,
            "name": "APT-00101",
            "patient_id": [1, "Bella"],
            "start_datetime": "2026-11-06 10:00:00",
            "end_datetime": "2026-11-06 10:30:00",
            "state": "confirmed",
        }
    ]

    vaccinations = [
        {
            "id": 501,
            "name": "Rabies Booster",
            "patient_id": [1, "Bella"],
            "date": "2026-05-10",
        }
    ]

    users = [
        {
            "id": 2,
            "name": "Dr. Sarah Adams",
            "login": "sarah.adams@zelixvet.com",
            "email": "sarah.adams@zelixvet.com",
        }
    ]

    return {
        "patients": patients,
        "hms_patients": hms_patients,
        "appointments": appointments,
        "vaccinations": vaccinations,
        "users": users,
    }


# ==============================================================================
# Dimension 1: Read Operations Parity
# ==============================================================================

def test_parity_find_patient(mock_odoo_responses):
    """Assert find_patient produces identical normalized patient profiles across both backends."""
    comparator = ParityComparator()
    adapter = ZelixOdooAdapter(mode="dual", comparator=comparator)

    with patch.object(adapter.direct, "models") as mock_direct_models, \
         patch.object(adapter.bridge.client, "search_read") as mock_bridge_search:

        # Setup Direct mock
        mock_direct_models.execute_kw.return_value = [mock_odoo_responses["patients"][0]]
        # Setup Bridge mock
        mock_bridge_search.return_value = [mock_odoo_responses["patients"][0]]

        # Search for Bella
        patient = adapter.find_patient("Bella")

        assert patient is not None
        assert patient["id"] == 1
        assert patient["name"] == "Bella"
        assert patient["identifier"] == "PAT-000001"
        assert patient["species"] == "Canine"
        assert patient["breed"] == "Labrador Retriever"
        assert patient["clinic_id"] == 3

        # Check telemetry
        summary = adapter.get_parity_telemetry()
        assert summary["total_operations"] == 1
        assert summary["matched_operations"] == 1
        assert summary["parity_rate_pct"] == 100.0
        assert summary["discrepancy_count"] == 0


def test_parity_search_read(mock_odoo_responses):
    """Assert search queries return identical record sets and counts across both backends."""
    comparator = ParityComparator()
    adapter = ZelixOdooAdapter(mode="dual", comparator=comparator)

    with patch.object(adapter.direct, "models") as mock_direct_models, \
         patch.object(adapter.bridge.client, "search_read") as mock_bridge_search:

        mock_direct_models.execute_kw.return_value = mock_odoo_responses["appointments"]
        mock_bridge_search.return_value = mock_odoo_responses["appointments"]

        appts = adapter.search("appointment", {"patient_id": 1})
        assert len(appts) == 1
        assert appts[0]["id"] == 101
        assert appts[0]["name"] == "APT-00101"

        summary = adapter.get_parity_telemetry()
        assert summary["matched_operations"] == 1
        assert summary["parity_rate_pct"] == 100.0


def test_parity_get_record(mock_odoo_responses):
    """Assert single record reads produce identical dictionary payloads."""
    comparator = ParityComparator()
    adapter = ZelixOdooAdapter(mode="dual", comparator=comparator)

    with patch.object(adapter.direct, "models") as mock_direct_models, \
         patch.object(adapter.bridge.client, "read") as mock_bridge_read:

        mock_direct_models.execute_kw.return_value = [mock_odoo_responses["patients"][1]]
        mock_bridge_read.return_value = [mock_odoo_responses["patients"][1]]

        patient = adapter.get("patient", "2")
        assert patient is not None
        assert patient["id"] == 2
        assert patient["name"] == "Max"

        summary = adapter.get_parity_telemetry()
        assert summary["matched_operations"] == 1
        assert summary["parity_rate_pct"] == 100.0


def test_parity_relationships(mock_odoo_responses):
    """Assert relationship lookups (vaccinations, encounters) maintain parity."""
    comparator = ParityComparator()
    adapter = ZelixOdooAdapter(mode="dual", comparator=comparator)

    with patch.object(adapter.direct, "models") as mock_direct_models, \
         patch.object(adapter.bridge.client, "search_read") as mock_bridge_search:

        mock_direct_models.execute_kw.return_value = mock_odoo_responses["vaccinations"]
        mock_bridge_search.return_value = mock_odoo_responses["vaccinations"]

        vax = adapter.relationships("patient", "1", "vaccinations")
        assert len(vax) == 1
        assert vax[0]["name"] == "Rabies Booster"

        summary = adapter.get_parity_telemetry()
        assert summary["matched_operations"] == 1
        assert summary["parity_rate_pct"] == 100.0


# ==============================================================================
# Dimension 2: Write Operations & Contract Parity
# ==============================================================================

def test_parity_create_and_update_contract():
    """Assert create and update return standard schema contracts in both direct and bridge modes."""
    adapter = ZelixOdooAdapter(mode="dual", shadow_writes=True)

    with patch.object(adapter.direct, "models") as mock_direct_models, \
         patch.object(adapter.bridge.client, "create") as mock_bridge_create, \
         patch.object(adapter.bridge.client, "write") as mock_bridge_write:

        mock_direct_models.execute_kw.side_effect = [888, True]
        mock_bridge_create.return_value = 888
        mock_bridge_write.return_value = True

        create_res = adapter.create("patient", {"name": "Charlie", "species_id": 1})
        assert create_res == {"id": 888, "status": "created", "model": "vet.patient"}

        update_res = adapter.update("patient", "888", {"name": "Charlie Brown"})
        assert update_res == {"id": 888, "status": "updated", "model": "vet.patient"}

        summary = adapter.get_parity_telemetry()
        assert summary["matched_operations"] == 2
        assert summary["parity_rate_pct"] == 100.0


# ==============================================================================
# Dimension 3: Mode Switching & Telemetry Collection
# ==============================================================================

def test_adapter_mode_switching():
    """Verify clean switching between direct, bridge, and dual modes."""
    adapter = ZelixOdooAdapter(mode="direct")
    assert adapter.mode == "direct"

    adapter.set_mode("bridge")
    assert adapter.mode == "bridge"

    adapter.set_mode("dual")
    assert adapter.mode == "dual"

    with pytest.raises(ValueError) as exc:
        adapter.set_mode("invalid_mode")
    assert "Invalid mode" in str(exc.value)


def test_discrepancy_detection_and_logging():
    """Verify comparator catches and logs output mismatches in shadow mode."""
    comparator = ParityComparator()
    adapter = ZelixOdooAdapter(mode="dual", comparator=comparator)

    with patch.object(adapter.direct, "models") as mock_direct_models, \
         patch.object(adapter.bridge.client, "search_read") as mock_bridge_search:

        # Direct returns 2 items, Bridge returns 1 item
        mock_direct_models.execute_kw.return_value = [{"id": 1}, {"id": 2}]
        mock_bridge_search.return_value = [{"id": 1}]

        results = adapter.search("patient")
        # Direct result is preserved for caller safety
        assert len(results) == 2

        # Telemetry records discrepancy
        summary = adapter.get_parity_telemetry()
        assert summary["total_operations"] == 1
        assert summary["matched_operations"] == 0
        assert summary["parity_rate_pct"] == 0.0
        assert summary["discrepancy_count"] == 1
        assert "Count mismatch" in summary["recent_discrepancies"][0]["reason"]


# ==============================================================================
# Dimension 4: Role Permissions
# ==============================================================================

def test_permissions_consistency():
    """Verify permissions method returns expected healthcare rights across both backends."""
    adapter_direct = ZelixOdooAdapter(mode="direct")
    adapter_bridge = ZelixOdooAdapter(mode="bridge")

    direct_perms = adapter_direct.permissions("2")
    bridge_perms = adapter_bridge.permissions("2")

    assert direct_perms == bridge_perms
    assert "patients.read" in direct_perms
    assert "prescriptions.write" in direct_perms


# ==============================================================================
# Dimension 5: Live Integration Parity (Executed when live Odoo is reachable)
# ==============================================================================

LIVE_TEST_KEY = os.getenv("ODOO_LIVE_TEST_API_KEY")

@pytest.mark.skipif(not LIVE_TEST_KEY, reason="Live Odoo API key not supplied via ODOO_LIVE_TEST_API_KEY")
def test_live_pilot_read_parity():
    """Verify 100% data parity against real running Odoo 19 database."""
    adapter = ZelixOdooAdapter(mode="dual", api_key=LIVE_TEST_KEY)

    # 1. Search clinics
    clinics = adapter.search("clinic", limit=5)
    assert len(clinics) > 0

    # 2. Search patients
    patients = adapter.search("patient", limit=5)
    assert len(patients) > 0

    # 3. Read specific patient
    pt_id = patients[0]["id"]
    pt = adapter.get("patient", str(pt_id))
    assert pt is not None
    assert pt["id"] == pt_id

    # 4. Identity check
    ident = adapter.identity(str(pt.get("write_uid", [2])[0] if isinstance(pt.get("write_uid"), (list, tuple)) else 2))
    assert ident is not None
    assert "id" in ident

    # Verify telemetry shows 100% parity
    summary = adapter.get_parity_telemetry()
    assert summary["total_operations"] >= 4
    assert summary["matched_operations"] == summary["total_operations"]
    assert summary["parity_rate_pct"] == 100.0
    assert summary["discrepancy_count"] == 0
