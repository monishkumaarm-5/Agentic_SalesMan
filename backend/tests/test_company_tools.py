"""
Tests for TOOLS/company_tools.py -- task 1.3 ("this is a company-specific
app, the local store and company website need to be shown"). Everything
here reads from config.py's COMPANY_NAME/COMPANY_WEBSITE/STORE_LOCATIONS,
so config is monkeypatched per test rather than touching the real
(placeholder) values.
"""
from TOOLS import company_tools as ct

FAKE_STORES = [
    {"name": "Trein T Nagar", "city": "Chennai", "address": "123 Usman Road"},
    {"name": "Trein Koramangala", "city": "Bengaluru", "address": "45 80 Feet Road"},
    {"name": "Trein Banjara Hills", "city": "Hyderabad", "address": "12 Road No. 3"},
]


def _configure(monkeypatch, **overrides):
    defaults = {
        "COMPANY_NAME": "Trein",
        "COMPANY_TAGLINE": "Every home, every device -- one store.",
        "COMPANY_WEBSITE": "https://www.trein.example.com",
        "COMPANY_SUPPORT_PHONE": "1800-000-0000",
        "STORE_LOCATIONS": FAKE_STORES,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setattr(ct.config, key, value, raising=False)


def test_get_company_info_reads_straight_from_config(monkeypatch):
    _configure(monkeypatch)
    info = ct.get_company_info()
    assert info == {
        "name": "Trein",
        "tagline": "Every home, every device -- one store.",
        "website": "https://www.trein.example.com",
        "support_phone": "1800-000-0000",
        "store_count": 3,
    }


def test_get_company_info_defaults_gracefully_when_config_is_missing_fields(monkeypatch):
    # Simulates a config.py that hasn't been rebranded/filled in yet --
    # never crash, just fall back to sane defaults.
    monkeypatch.delattr(ct.config, "COMPANY_NAME", raising=False)
    monkeypatch.delattr(ct.config, "COMPANY_TAGLINE", raising=False)
    monkeypatch.delattr(ct.config, "COMPANY_WEBSITE", raising=False)
    monkeypatch.delattr(ct.config, "COMPANY_SUPPORT_PHONE", raising=False)
    monkeypatch.delattr(ct.config, "STORE_LOCATIONS", raising=False)
    info = ct.get_company_info()
    assert info["name"] == "Trein"
    assert info["store_count"] == 0


def test_list_store_locations_returns_every_store_with_no_city_filter(monkeypatch):
    _configure(monkeypatch)
    assert ct.list_store_locations() == FAKE_STORES


def test_list_store_locations_filters_case_insensitively_by_city(monkeypatch):
    _configure(monkeypatch)
    result = ct.list_store_locations("chennai")
    assert [store["name"] for store in result] == ["Trein T Nagar"]


def test_list_store_locations_returns_empty_list_for_a_city_with_no_store(monkeypatch):
    _configure(monkeypatch)
    assert ct.list_store_locations("Mumbai") == []


def test_list_store_locations_treats_blank_city_as_no_filter(monkeypatch):
    _configure(monkeypatch)
    assert ct.list_store_locations("   ") == FAKE_STORES


def test_list_store_locations_returns_empty_list_when_none_configured(monkeypatch):
    _configure(monkeypatch, STORE_LOCATIONS=[])
    assert ct.list_store_locations() == []
    assert ct.list_store_locations("Chennai") == []
