"""
Tests for Supabase Client upgrade.
Tests are offline (no live API calls) — they verify method existence,
signatures, urllib migration, filter construction, and unconfigured behavior.
"""

import sys
import os
import inspect
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.logger import get_logger
from supabase.supabase_client import SupabaseClient, OPERATOR_MAP

log = get_logger("tests")

_passed = 0
_failed = 0


def run_test(name, func):
    global _passed, _failed
    try:
        func()
        print(f"  [PASS] {name}")
        _passed += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        _failed += 1


# ----------------------------------------------------------------------
# urllib migration — no requests dependency
# ----------------------------------------------------------------------

def test_no_requests_attribute():
    """Client must not have a 'requests' attribute."""
    client = SupabaseClient()
    assert not hasattr(client, "requests"), "Client should not have a 'requests' attribute"


def test_is_configured_false():
    """Without URL/keys, is_configured() must return False."""
    client = SupabaseClient(url="", anon_key="", service_key="")
    assert client.is_configured() is False


def test_is_configured_true():
    """With URL + anon key, is_configured() must return True."""
    client = SupabaseClient(url="https://example.supabase.co", anon_key="key123")
    assert client.is_configured() is True


def test_is_configured_service_key():
    """With URL + service key only, is_configured() must return True."""
    client = SupabaseClient(url="https://example.supabase.co", service_key="svc123")
    assert client.is_configured() is True


def test_unconfigured_returns_error():
    """Unconfigured requests must return an error dict, not crash."""
    client = SupabaseClient(url="", anon_key="")
    result = client.select("any_table")
    assert isinstance(result, dict)
    assert "error" in result


def test_request_method_exists():
    """_request method must exist and be callable."""
    client = SupabaseClient(url="https://x.supabase.co", anon_key="k")
    assert callable(getattr(client, "_request", None))


def test_request_all_method_exists():
    """_request_all pagination helper must exist."""
    client = SupabaseClient(url="https://x.supabase.co", anon_key="k")
    assert callable(getattr(client, "_request_all", None))


# ----------------------------------------------------------------------
# Advanced query operators
# ----------------------------------------------------------------------

def test_operator_map_has_all_ops():
    """OPERATOR_MAP must include all 11 operators."""
    expected = {"eq", "neq", "gt", "lt", "gte", "lte", "like", "ilike", "in", "is", "not"}
    assert expected.issubset(set(OPERATOR_MAP.keys())), \
        f"Missing operators: {expected - set(OPERATOR_MAP.keys())}"


def test_apply_filters_equality():
    """_apply_filters must produce eq. params for simple equality."""
    client = SupabaseClient(url="https://x.supabase.co", anon_key="k")
    params = {}
    client._apply_filters(params, filters={"name": "Alice"})
    assert params["name"] == "eq.Alice"


def test_apply_filters_list_uses_in():
    """List filter values must automatically use the 'in' operator."""
    client = SupabaseClient(url="https://x.supabase.co", anon_key="k")
    params = {}
    client._apply_filters(params, filters={"id": [1, 2, 3]})
    assert params["id"] == "in.1,2,3"


def test_apply_filters_advanced_operators():
    """Advanced operators must produce correct PostgREST filter syntax."""
    client = SupabaseClient(url="https://x.supabase.co", anon_key="k")
    params = {}
    client._apply_filters(params, operators={
        "age": {"op": "gt", "value": 18},
        "name": {"op": "like", "value": "A%"},
        "status": {"op": "in", "value": ["active", "pending"]},
    })
    assert params["age"] == "gt.18"
    assert params["name"] == "like.A%"
    assert params["status"] == "in.active,pending"


def test_apply_filters_all_operators():
    """Every supported operator must produce a valid filter."""
    client = SupabaseClient(url="https://x.supabase.co", anon_key="k")
    params = {}
    client._apply_filters(params, operators={
        "a": {"op": "neq", "value": 1},
        "b": {"op": "lt", "value": 5},
        "c": {"op": "gte", "value": 10},
        "d": {"op": "lte", "value": 20},
        "e": {"op": "ilike", "value": "test"},
        "f": {"op": "is", "value": "null"},
        "g": {"op": "not", "value": "true"},
    })
    assert params["a"] == "neq.1"
    assert params["b"] == "lt.5"
    assert params["c"] == "gte.10"
    assert params["d"] == "lte.20"
    assert params["e"] == "ilike.test"
    assert params["f"] == "is.null"
    assert params["g"] == "not.true"


def test_apply_filters_unsupported_op_skipped():
    """Unsupported operators must be skipped with a warning, not crash."""
    client = SupabaseClient(url="https://x.supabase.co", anon_key="k")
    params = {}
    client._apply_filters(params, operators={"col": {"op": "weird", "value": 1}})
    assert "col" not in params


def test_select_accepts_operators_param():
    """select() signature must include the operators parameter."""
    sig = inspect.signature(SupabaseClient.select)
    assert "operators" in sig.parameters


def test_update_accepts_operators_param():
    """update() signature must include the operators parameter."""
    sig = inspect.signature(SupabaseClient.update)
    assert "operators" in sig.parameters


def test_delete_accepts_operators_param():
    """delete() signature must include the operators parameter."""
    sig = inspect.signature(SupabaseClient.delete)
    assert "operators" in sig.parameters


# ----------------------------------------------------------------------
# Upsert support
# ----------------------------------------------------------------------

def test_upsert_method_exists():
    """upsert() method must exist."""
    client = SupabaseClient(url="https://x.supabase.co", anon_key="k")
    assert callable(getattr(client, "upsert", None))


def test_upsert_accepts_on_conflict():
    """upsert() signature must include on_conflict parameter."""
    sig = inspect.signature(SupabaseClient.upsert)
    assert "on_conflict" in sig.parameters


def test_upsert_unconfigured_returns_error():
    """upsert without configuration must return an error, not crash."""
    client = SupabaseClient(url="", anon_key="")
    result = client.upsert("table", {"id": 1, "name": "test"})
    assert isinstance(result, dict)
    assert "error" in result


# ----------------------------------------------------------------------
# Pagination support
# ----------------------------------------------------------------------

def test_select_all_method_exists():
    """select_all() method must exist."""
    client = SupabaseClient(url="https://x.supabase.co", anon_key="k")
    assert callable(getattr(client, "select_all", None))


def test_select_all_accepts_pagination_params():
    """select_all() must accept page_size and max_pages."""
    sig = inspect.signature(SupabaseClient.select_all)
    assert "page_size" in sig.parameters
    assert "max_pages" in sig.parameters


def test_select_all_unconfigured_returns_error():
    """select_all without configuration must return an error."""
    client = SupabaseClient(url="", anon_key="")
    result = client.select_all("table")
    assert isinstance(result, dict)
    assert "error" in result


# ----------------------------------------------------------------------
# Count support
# ----------------------------------------------------------------------

def test_count_method_exists():
    """count() method must exist."""
    client = SupabaseClient(url="https://x.supabase.co", anon_key="k")
    assert callable(getattr(client, "count", None))


def test_count_unconfigured_returns_error():
    """count without configuration must return an error."""
    client = SupabaseClient(url="", anon_key="")
    result = client.count("table")
    assert isinstance(result, dict)
    assert "error" in result


# ----------------------------------------------------------------------
# Backward compatibility — all original methods preserved
# ----------------------------------------------------------------------

def test_backward_compat_methods():
    """All original 16 methods must still exist."""
    client = SupabaseClient(url="https://x.supabase.co", anon_key="k")
    original_methods = [
        "is_configured", "select", "insert", "insert_batch", "update",
        "delete", "rpc", "sign_up", "sign_in", "sign_out", "get_user",
        "list_buckets", "create_bucket", "upload_file", "download_file",
        "test_connection",
    ]
    for method_name in original_methods:
        assert callable(getattr(client, method_name, None)), f"Missing: {method_name}"


def test_select_signature_backward_compat():
    """select() must keep filters, limit, order params (positional compat)."""
    sig = inspect.signature(SupabaseClient.select)
    for param in ("table", "columns", "filters", "limit", "order"):
        assert param in sig.parameters, f"select() missing param: {param}"


def test_insert_signature_unchanged():
    """insert() must keep (table, data, use_service_key) signature."""
    sig = inspect.signature(SupabaseClient.insert)
    for param in ("table", "data", "use_service_key"):
        assert param in sig.parameters


def test_update_signature_backward_compat():
    """update() must keep (table, filters, data, use_service_key) — operators is optional."""
    sig = inspect.signature(SupabaseClient.update)
    for param in ("table", "filters", "data", "use_service_key"):
        assert param in sig.parameters


def test_delete_signature_backward_compat():
    """delete() must keep (table, filters, use_service_key) — operators is optional."""
    sig = inspect.signature(SupabaseClient.delete)
    for param in ("table", "filters", "use_service_key"):
        assert param in sig.parameters


# ----------------------------------------------------------------------
# Retry / timeout handling
# ----------------------------------------------------------------------

def test_request_accepts_timeout():
    """_request must accept a timeout parameter."""
    sig = inspect.signature(SupabaseClient._request)
    assert "timeout" in sig.parameters


def test_request_accepts_extra_headers():
    """_request must accept extra_headers for Prefer headers (upsert/count)."""
    sig = inspect.signature(SupabaseClient._request)
    assert "extra_headers" in sig.parameters


def test_get_headers_service_key():
    """_get_headers must use service key when requested."""
    client = SupabaseClient(url="https://x.supabase.co",
                           anon_key="anon123", service_key="svc456")
    headers = client._get_headers(use_service_key=True)
    assert headers["apikey"] == "svc456"
    assert headers["Authorization"] == "Bearer svc456"


def test_get_headers_anon_key_default():
    """_get_headers must use anon key by default."""
    client = SupabaseClient(url="https://x.supabase.co",
                           anon_key="anon123", service_key="svc456")
    headers = client._get_headers()
    assert headers["apikey"] == "anon123"


def run_all_tests():
    print("\n--- Supabase Client Upgrade Tests ---\n")

    # urllib migration
    run_test("No requests attribute", test_no_requests_attribute)
    run_test("is_configured false", test_is_configured_false)
    run_test("is_configured true (anon)", test_is_configured_true)
    run_test("is_configured true (service)", test_is_configured_service_key)
    run_test("Unconfigured returns error", test_unconfigured_returns_error)
    run_test("_request method exists", test_request_method_exists)
    run_test("_request_all pagination helper exists", test_request_all_method_exists)

    # Advanced query operators
    run_test("OPERATOR_MAP has all 11 ops", test_operator_map_has_all_ops)
    run_test("Equality filter produces eq.", test_apply_filters_equality)
    run_test("List filter uses in operator", test_apply_filters_list_uses_in)
    run_test("Advanced operators (gt, like, in)", test_apply_filters_advanced_operators)
    run_test("All 11 operators produce valid filters", test_apply_filters_all_operators)
    run_test("Unsupported operator skipped", test_apply_filters_unsupported_op_skipped)
    run_test("select() accepts operators", test_select_accepts_operators_param)
    run_test("update() accepts operators", test_update_accepts_operators_param)
    run_test("delete() accepts operators", test_delete_accepts_operators_param)

    # Upsert
    run_test("upsert() method exists", test_upsert_method_exists)
    run_test("upsert() accepts on_conflict", test_upsert_accepts_on_conflict)
    run_test("upsert() unconfigured returns error", test_upsert_unconfigured_returns_error)

    # Pagination
    run_test("select_all() method exists", test_select_all_method_exists)
    run_test("select_all() accepts pagination params", test_select_all_accepts_pagination_params)
    run_test("select_all() unconfigured returns error", test_select_all_unconfigured_returns_error)

    # Count
    run_test("count() method exists", test_count_method_exists)
    run_test("count() unconfigured returns error", test_count_unconfigured_returns_error)

    # Backward compatibility
    run_test("All 16 original methods preserved", test_backward_compat_methods)
    run_test("select() signature backward compat", test_select_signature_backward_compat)
    run_test("insert() signature unchanged", test_insert_signature_unchanged)
    run_test("update() signature backward compat", test_update_signature_backward_compat)
    run_test("delete() signature backward compat", test_delete_signature_backward_compat)

    # Retry / timeout
    run_test("_request accepts timeout", test_request_accepts_timeout)
    run_test("_request accepts extra_headers", test_request_accepts_extra_headers)
    run_test("_get_headers service key", test_get_headers_service_key)
    run_test("_get_headers anon key default", test_get_headers_anon_key_default)

    print(f"\n  Results: {_passed} passed, {_failed} failed")
    print("-" * 50)
    return _failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)