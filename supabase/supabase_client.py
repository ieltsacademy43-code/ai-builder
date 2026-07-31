"""
Supabase client for AI Builder.
Integrates with Supabase REST API for database and storage operations.
Zero external dependencies — uses stdlib urllib for HTTP.
"""

import json
import urllib.request
import urllib.error
import urllib.parse
import time
import mimetypes
from datetime import datetime
from core.logger import get_logger
from config.settings import get_config

log = get_logger("supabase")


# PostgREST operator → URL filter syntax mapping
OPERATOR_MAP = {
    "eq": "eq",
    "neq": "neq",
    "gt": "gt",
    "lt": "lt",
    "gte": "gte",
    "lte": "lte",
    "like": "like",
    "ilike": "ilike",
    "in": "in",
    "is": "is",
    "not": "not",
}


class SupabaseClient:
    """Supabase REST API client for database operations."""

    def __init__(self, url=None, anon_key=None, service_key=None):
        self.config = get_config()
        self.url = (url or self.config.get("supabase.url", "")).rstrip("/")
        self.anon_key = anon_key or self.config.get("supabase.anon_key", "")
        self.service_key = service_key or self.config.get("supabase.service_key", "")

    def is_configured(self):
        """Check if Supabase is configured."""
        return bool(self.url and (self.anon_key or self.service_key))

    def _get_headers(self, use_service_key=False):
        """Build request headers."""
        key = self.service_key if use_service_key and self.service_key else self.anon_key
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method, path, data=None, params=None, use_service_key=False,
                 extra_headers=None, raw_body=None, timeout=30):
        """Make an API request to Supabase using urllib (zero dependencies).

        Retries on rate-limit (429) and server errors (5xx) with exponential
        backoff. Returns parsed JSON for 200/201, {"success": True} for 204,
        or {"error": ..., "status_code": ...} on failure.
        """
        if not self.is_configured():
            return {"error": "Supabase not configured. Set supabase.url and supabase.anon_key."}

        url = f"{self.url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"

        headers = self._get_headers(use_service_key)
        if extra_headers:
            headers.update(extra_headers)

        body = None
        if raw_body is not None:
            body = raw_body
        elif data is not None:
            body = json.dumps(data).encode("utf-8")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, data=body, method=method, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    status = response.status
                    content = response.read()

                    if status in (200, 201):
                        try:
                            return json.loads(content.decode("utf-8"))
                        except (ValueError, json.JSONDecodeError):
                            return {"success": True, "data": content.decode("utf-8", errors="replace")}
                    elif status == 204:
                        return {"success": True}
                    else:
                        error_msg = f"Supabase API error {status}: {content.decode('utf-8', errors='replace')}"
                        log.error(error_msg)
                        return {"error": error_msg, "status_code": status}

            except urllib.error.HTTPError as e:
                status = e.code
                body_text = ""
                try:
                    body_text = e.read().decode("utf-8", errors="replace")
                except Exception:
                    pass

                # Retry on rate-limit and 5xx server errors
                if status == 429 and attempt < max_retries - 1:
                    wait = min(2 ** attempt, 10)
                    log.warning(f"Rate limited (429), retrying in {wait}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(wait)
                    continue
                if 500 <= status < 600 and attempt < max_retries - 1:
                    wait = 2 ** attempt
                    log.warning(f"Server error {status}, retrying in {wait}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(wait)
                    continue

                error_msg = f"Supabase API error {status}: {body_text}"
                log.error(error_msg)
                return {"error": error_msg, "status_code": status}

            except urllib.error.URLError as e:
                log.error(f"Supabase connection failed: {e}")
                return {"error": str(e.reason)}
            except Exception as e:
                log.error(f"Supabase API request failed: {e}")
                return {"error": str(e)}

        return {"error": "Max retries exceeded"}

    def _request_all(self, table, columns="*", filters=None, operators=None,
                     order=None, page_size=1000, max_pages=50, use_service_key=False):
        """Paginate through all rows of a table using range headers.

        Returns a flat list of all rows, or {"error": ...} on failure.
        """
        all_rows = []
        offset = 0

        for page in range(1, max_pages + 1):
            path = f"/rest/v1/{table}"
            params = {"select": columns}
            self._apply_filters(params, filters, operators)
            if order:
                params["order"] = order

            # PostgREST pagination via Range header: "offset-limit"
            range_header = f"{offset}-{offset + page_size - 1}"
            result = self._request("GET", path, params=params,
                                   extra_headers={"Range": range_header},
                                   use_service_key=use_service_key)
            if isinstance(result, dict) and "error" in result:
                return result

            if not result:
                break

            all_rows.extend(result)
            # If we got fewer than page_size rows, we've reached the end
            if len(result) < page_size:
                break
            offset += page_size

        return all_rows

    def _apply_filters(self, params, filters=None, operators=None):
        """Apply equality filters and advanced operators to query params.

        filters: dict of column -> value (equality shorthand).
        operators: dict of column -> {"op": "gt", "value": 10}
                   supported ops: eq, neq, gt, lt, gte, lte, like, ilike, in, is, not.
        """
        if filters:
            for key, value in filters.items():
                if isinstance(value, list):
                    params[key] = f"in.{','.join(str(v) for v in value)}"
                else:
                    params[key] = f"eq.{value}"
        if operators:
            for column, spec in operators.items():
                op = spec.get("op", "eq")
                val = spec.get("value")
                if op not in OPERATOR_MAP:
                    log.warning(f"Unsupported operator '{op}' for column '{column}', skipping.")
                    continue
                op_str = OPERATOR_MAP[op]
                if op == "in" and isinstance(val, list):
                    params[column] = f"in.{','.join(str(v) for v in val)}"
                else:
                    params[column] = f"{op_str}.{val}"

    # --- Database (PostgREST) operations ---

    def select(self, table, columns="*", filters=None, operators=None,
               limit=None, order=None, use_service_key=False):
        """Select records from a table.

        filters: dict of column -> value for equality filtering.
                 If value is a list, uses 'in' operator automatically.
        operators: dict of column -> {"op": "<operator>", "value": <value>}
                   Supported ops: eq, neq, gt, lt, gte, lte, like, ilike, in, is, not.
        order: string like "created_at.desc" or "name.asc".
        """
        path = f"/rest/v1/{table}"
        params = {"select": columns}
        self._apply_filters(params, filters, operators)
        if limit:
            params["limit"] = limit
        if order:
            params["order"] = order
        return self._request("GET", path, params=params, use_service_key=use_service_key)

    def select_all(self, table, columns="*", filters=None, operators=None,
                   order=None, page_size=1000, max_pages=50, use_service_key=False):
        """Select ALL records from a table with automatic pagination.

        Returns a flat list of all matching rows.
        """
        return self._request_all(table, columns=columns, filters=filters,
                                  operators=operators, order=order,
                                  page_size=page_size, max_pages=max_pages,
                                  use_service_key=use_service_key)

    def insert(self, table, data, use_service_key=False):
        """Insert a record into a table."""
        path = f"/rest/v1/{table}"
        return self._request("POST", path, data=data, use_service_key=use_service_key)

    def insert_batch(self, table, records, use_service_key=False):
        """Insert multiple records into a table."""
        path = f"/rest/v1/{table}"
        return self._request("POST", path, data=records, use_service_key=use_service_key)

    def upsert(self, table, data, use_service_key=True, on_conflict=None):
        """Upsert (insert-or-update) records via PostgREST.

        Uses the Prefer: resolution=merge-duplicates header.
        on_conflict: optional comma-separated column(s) to target as conflict key.
        """
        path = f"/rest/v1/{table}"
        extra_headers = {"Prefer": "resolution=merge-duplicates"}
        if on_conflict:
            params = {"on_conflict": on_conflict}
        else:
            params = None
        # data can be a single dict or a list of dicts
        return self._request("POST", path, data=data, params=params,
                             use_service_key=use_service_key,
                             extra_headers=extra_headers)

    def update(self, table, filters, data, operators=None, use_service_key=True):
        """Update records in a table.

        filters: dict of column -> value for matching records to update.
        operators: optional advanced operators for finer-grained matching.
        """
        path = f"/rest/v1/{table}"
        params = {}
        self._apply_filters(params, filters, operators)
        return self._request("PATCH", path, data=data, params=params,
                             use_service_key=use_service_key)

    def delete(self, table, filters, operators=None, use_service_key=True):
        """Delete records from a table.

        filters: dict of column -> value for matching records to delete.
        operators: optional advanced operators for finer-grained matching.
        """
        path = f"/rest/v1/{table}"
        params = {}
        self._apply_filters(params, filters, operators)
        return self._request("DELETE", path, params=params,
                             use_service_key=use_service_key)

    def count(self, table, filters=None, operators=None, use_service_key=False):
        """Count records matching a query (returns {"count": N})."""
        path = f"/rest/v1/{table}"
        params = {"select": "count"}
        self._apply_filters(params, filters, operators)
        result = self._request("GET", path, params=params,
                               extra_headers={"Prefer": "count=exact"},
                               use_service_key=use_service_key)
        if isinstance(result, dict) and "error" in result:
            return result
        # PostgREST returns [{"count": N}] — extract the count
        if isinstance(result, list) and len(result) > 0:
            return {"count": result[0].get("count", 0)}
        return {"count": 0}

    def rpc(self, function_name, params=None, use_service_key=False):
        """Call a stored procedure (RPC)."""
        path = f"/rest/v1/rpc/{function_name}"
        return self._request("POST", path, data=params or {},
                             use_service_key=use_service_key)

    # --- Auth operations ---

    def sign_up(self, email, password):
        """Sign up a new user."""
        path = "/auth/v1/signup"
        return self._request("POST", path, data={"email": email, "password": password})

    def sign_in(self, email, password):
        """Sign in a user and get access token."""
        path = "/auth/v1/token"
        params = {"grant_type": "password"}
        return self._request("POST", path, data={"email": email, "password": password},
                             params=params)

    def sign_out(self, access_token):
        """Sign out a user."""
        if not self.is_configured():
            return {"error": "Not configured"}
        path = "/auth/v1/logout"
        headers = self._get_headers()
        headers["Authorization"] = f"Bearer {access_token}"
        try:
            req = urllib.request.Request(f"{self.url}{path}", method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                return {"success": response.status == 204}
        except urllib.error.HTTPError as e:
            return {"error": f"Status {e.code}: {e.read().decode('utf-8', errors='replace')}"}
        except Exception as e:
            return {"error": str(e)}

    def get_user(self, access_token):
        """Get user info from access token."""
        if not self.is_configured():
            return {"error": "Not configured"}
        path = "/auth/v1/user"
        headers = self._get_headers()
        headers["Authorization"] = f"Bearer {access_token}"
        try:
            req = urllib.request.Request(f"{self.url}{path}", method="GET", headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    return json.loads(response.read().decode("utf-8"))
                return {"error": f"Status {response.status}"}
        except urllib.error.HTTPError as e:
            return {"error": f"Status {e.code}: {e.read().decode('utf-8', errors='replace')}"}
        except Exception as e:
            return {"error": str(e)}

    # --- Storage operations ---

    def list_buckets(self):
        """List storage buckets."""
        path = "/storage/v1/bucket"
        return self._request("GET", path)

    def create_bucket(self, bucket_name, is_public=False):
        """Create a storage bucket."""
        path = "/storage/v1/bucket"
        data = {"name": bucket_name, "public": is_public}
        return self._request("POST", path, data=data, use_service_key=True)

    def upload_file(self, bucket_name, file_path, content=None):
        """Upload a file to storage."""
        if not self.is_configured():
            return {"error": "Not configured"}

        mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        if content is None:
            with open(file_path, "rb") as f:
                content = f.read()
        elif isinstance(content, str):
            content = content.encode("utf-8")

        file_name = file_path.split("/")[-1].split("\\")[-1]
        url = f"{self.url}/storage/v1/object/{bucket_name}/{file_name}"
        headers = self._get_headers(use_service_key=True)
        headers["Content-Type"] = mime

        try:
            req = urllib.request.Request(url, data=content, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=60) as response:
                if response.status == 200:
                    return {"success": True, "path": f"{bucket_name}/{file_name}"}
                return {"error": f"Upload failed: {response.status}"}
        except urllib.error.HTTPError as e:
            return {"error": f"Upload failed: {e.code} {e.read().decode('utf-8', errors='replace')}"}
        except Exception as e:
            return {"error": str(e)}

    def download_file(self, bucket_name, file_name, output_path=None):
        """Download a file from storage."""
        if not self.is_configured():
            return {"error": "Not configured"}

        url = f"{self.url}/storage/v1/object/{bucket_name}/{file_name}"
        headers = self._get_headers(use_service_key=True)

        try:
            req = urllib.request.Request(url, method="GET", headers=headers)
            with urllib.request.urlopen(req, timeout=60) as response:
                if response.status == 200:
                    data = response.read()
                    if output_path:
                        with open(output_path, "wb") as f:
                            f.write(data)
                        return {"success": True, "path": output_path}
                    return {"success": True, "data": data}
                return {"error": f"Download failed: {response.status}"}
        except urllib.error.HTTPError as e:
            return {"error": f"Download failed: {e.code}"}
        except Exception as e:
            return {"error": str(e)}

    def test_connection(self):
        """Test the Supabase connection."""
        if not self.is_configured():
            return {"connected": False, "error": "Not configured"}
        result = self.select("_dummy_test", limit=1)
        if "error" in result:
            # A 404 or table-not-found error means the connection works
            # but the test table doesn't exist — still connected
            if "404" in str(result.get("error", "")) or "PGRST" in str(result.get("error", "")):
                return {"connected": True, "message": "Connection successful."}
            return {"connected": False, "error": result["error"]}
        return {"connected": True, "message": "Connection successful."}