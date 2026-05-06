"""
iNaturalist API v1 client
Docs: https://api.inaturalist.org/v1/docs/
"""
import json
import urllib.request
import urllib.parse
import urllib.error

BASE_URL = "https://api.inaturalist.org/v1"


class INaturalistAPI:
    def __init__(self):
        self.token = None
        self.username = None

    def login(self, username, password, app_id, app_secret):
        """
        OAuth2 password grant to get JWT token.
        app_id / app_secret: register at https://www.inaturalist.org/oauth/applications
        """
        url = "https://www.inaturalist.org/oauth/token"
        payload = urllib.parse.urlencode({
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "password",
            "username": username,
            "password": password,
        }).encode()
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                access_token = data.get("access_token")
                if not access_token:
                    return False, "Kein Access Token erhalten."
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            return False, f"HTTP {e.code}: {body}"
        except Exception as e:
            return False, str(e)

        # Exchange OAuth token for JWT
        jwt_url = f"{BASE_URL}/users/api_token"
        req2 = urllib.request.Request(jwt_url)
        req2.add_header("Authorization", f"Bearer {access_token}")
        try:
            with urllib.request.urlopen(req2, timeout=15) as resp:
                data2 = json.loads(resp.read())
                self.token = data2.get("api_token")
                self.username = username
                if self.token:
                    return True, "Login erfolgreich."
                return False, "JWT Token nicht erhalten."
        except Exception as e:
            return False, str(e)

    def get_observations(self, params, progress_callback=None):
        """
        Fetch observations from iNaturalist API.
        params: dict with filter parameters
        Returns list of observation dicts.
        """
        all_results = []
        per_page = 200
        page = 1
        total = None

        while True:
            query = dict(params)
            query["per_page"] = per_page
            query["page"] = page
            query["order"] = "desc"
            query["order_by"] = "created_at"

            url = f"{BASE_URL}/observations?" + urllib.parse.urlencode(query, doseq=True)
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            if self.token:
                req.add_header("Authorization", self.token)

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read())
            except urllib.error.HTTPError as e:
                raise Exception(f"API Fehler {e.code}: {e.read().decode()}")
            except Exception as e:
                raise Exception(f"Verbindungsfehler: {e}")

            results = data.get("results", [])
            if total is None:
                total = data.get("total_results", 0)

            all_results.extend(results)

            if progress_callback:
                progress_callback(len(all_results), total)

            if len(results) < per_page or len(all_results) >= min(total, 10000):
                break
            page += 1

        return all_results, total

    def get_taxa(self, query):
        """Search for taxa by name."""
        url = f"{BASE_URL}/taxa?" + urllib.parse.urlencode({"q": query, "per_page": 20})
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data.get("results", [])
