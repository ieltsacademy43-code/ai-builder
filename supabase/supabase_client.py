"""
Supabase client for AI Builder.
Integrates with Supabase REST API for database and storage operations.
"""

import json
from datetime import datetime
from core.logger import get_logger
from config.settings import get_config

log = get_logger("supabase")


class SupabaseClient:
    """Supabase REST API client for database operations."""

    def __init__(self, url=None, anon_key=None, service_key=None):
        self.config = get_config()
        self.url = (url or self.config.get("supabase.url", "")).rstrip("/")
        self.anon_key = anon_key or self.config.get("supabase.anon_key", "")
        self.service_key = service_key or self.config.get("supabase.service_key", "")

        try:
            import requests
            self.requests = requests
        except ImportError:
            self.requests = None
            log.warning("requests library not installed. Supabase features will be limited.")

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

    def _request(self, method, path, data=None, params=None, use_service_key=False):
        """Make an API request to Supabase."""
        if not self.is_configured():
            return {"error": "Supabase not configured. Set supabase.url and supabase.anon_key."}
        if not self.requests:
            return {"error": "requests library not installed. Run: pip install requests"}

        url = f"{self.url}{path}"
        headers = self._get_headers(use_service_key)

        try:
            response = self.requests.request(
                method,
                url,
                headers=headers,
                json=data,
                params=params,
                timeout=30,
            )

            if response.status_code in (200, 201):
                try:
                    return response.json()
                except ValueError:
                    return {"success": True, "data": response.text}
            elif response.status_code == 204:
                return {"success": True}
            else:
                error_msg = f"Supabase API error {response.status_code}: {response.text}"
                log.error(error_msg)
                return {"error": error_msg, "status_code": response.status_code}

        except Exception as e:
            log.error(f"Supabase API request failed: {e}")
            return {"error": str(e)}

    # --- Database (PostgREST) operations ---

    def select(self, table, columns="*", filters=None, limit=None, order=None):
        """
        Select records from a table.

        filters: dict of column -> value for equality filtering.
        order: string like "created_at.desc" or "name.asc".
        """
        path = f"/rest/v1/{table}"
        params = {"select": columns}

        if filters:
            for key, value in filters.items():
                params[key] = f"eq.{value}"

        if limit:
            params["limit"] = limit

        if order:
            params["order"] = order

        return self._request("GET", path, params=params)

    def insert(self, table, data, use_service_key=False):
        """Insert a record into a table."""
        path = f"/rest/v1/{table}"
        return self._request("POST", path, data=data, use_service_key=use_service_key)

    def insert_batch(self, table, records, use_service_key=False):
        """Insert multiple records into a table."""
        path = f"/rest/v1/{table}"
        return self._request("POST", path, data=records, use_service_key=use_service_key)

    def update(self, table, filters, data, use_service_key=True):
        """
        Update records in a table.

        filters: dict of column -> value for matching records to update.
        """
        path = f"/rest/v1/{table}"
        params = {}
        for key, value in filters.items():
            params[key] = f"eq.{value}"
        return self._request("PATCH", path, data=data, params=params,
                              use_service_key=use_service_key)

    def delete(self, table, filters, use_service_key=True):
        """Delete records from a table."""
        path = f"/rest/v1/{table}"
        params = {}
        for key, value in filters.items():
            params[key] = f"eq.{value}"
        return self._request("DELETE", path, params=params,
                              use_service_key=use_service_key)

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
        path = "/auth/v1/logout"
        headers = self._get_headers()
        headers["Authorization"] = f"Bearer {access_token}"
        if not self.requests:
            return {"error": "requests not installed"}
        try:
            response = self.requests.post(
                f"{self.url}{path}",
                headers=headers,
                timeout=30,
            )
            return {"success": response.status_code == 204}
        except Exception as e:
            return {"error": str(e)}

    def get_user(self, access_token):
        """Get user info from access token."""
        path = "/auth/v1/user"
        headers = self._get_headers()
        headers["Authorization"] = f"Bearer {access_token}"
        if not self.requests:
            return {"error": "requests not installed"}
        try:
            response = self.requests.get(f"{self.url}{path}", headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            return {"error": f"Status {response.status_code}: {response.text}"}
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
        if not self.requests or not self.is_configured():
            return {"error": "Not configured or requests not installed"}

        import mimetypes
        mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        if content is None:
            with open(file_path, "rb") as f:
                content = f.read()

        file_name = file_path.split("/")[-1]
        url = f"{self.url}/storage/v1/object/{bucket_name}/{file_name}"
        headers = self._get_headers(use_service_key=True)
        headers["Content-Type"] = mime

        try:
            response = self.requests.post(url, headers=headers, data=content, timeout=60)
            if response.status_code == 200:
                return {"success": True, "path": f"{bucket_name}/{file_name}"}
            return {"error": f"Upload failed: {response.status_code} {response.text}"}
        except Exception as e:
            return {"error": str(e)}

    def download_file(self, bucket_name, file_name, output_path=None):
        """Download a file from storage."""
        if not self.requests or not self.is_configured():
            return {"error": "Not configured or requests not installed"}

        url = f"{self.url}/storage/v1/object/{bucket_name}/{file_name}"
        headers = self._get_headers(use_service_key=True)

        try:
            response = self.requests.get(url, headers=headers, timeout=60)
            if response.status_code == 200:
                if output_path:
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    return {"success": True, "path": output_path}
                return {"success": True, "data": response.content}
            return {"error": f"Download failed: {response.status_code}"}
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