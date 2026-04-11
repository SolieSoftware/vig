"""
Betfair Exchange API client.

Uses interactive (username/password) login — no SSL certificate required.
Fetches EPL MATCH_ODDS and OVER_UNDER_25 markets with best available back prices.
"""
import time
from typing import List, Optional

import httpx
from pydantic import BaseModel

from vig import config

BETFAIR_LOGIN_URL = "https://identitysso-cert.betfair.com/api/certlogin"
BETFAIR_API_BASE = "https://api.betfair.com/exchange/betting/rest/v1.0"
BETFAIR_CERT = ("~/.vig_certs/betfair.crt", "~/.vig_certs/betfair.pem")

EPL_COMPETITION_ID = "10932509"
FOOTBALL_EVENT_TYPE_ID = "1"
MARKET_TYPES = ["MATCH_ODDS", "OVER_UNDER_25"]


class BetfairUnavailable(Exception):
    pass


class BetfairRunner(BaseModel):
    selection_id: int
    name: str
    best_back_price: Optional[float] = None


class BetfairMarket(BaseModel):
    market_id: str
    market_type: str
    event_name: str
    runners: List[BetfairRunner]


class _SessionManager:
    def __init__(self):
        self._token: Optional[str] = None
        self._token_time: float = 0

    def _login(self) -> str:
        if not config.BETFAIR_USERNAME or not config.BETFAIR_PASSWORD:
            raise BetfairUnavailable("BETFAIR_USERNAME/PASSWORD not set in .env")
        if not config.BETFAIR_API_KEY:
            raise BetfairUnavailable("BETFAIR_API_KEY not set in .env")

        from pathlib import Path
        cert_crt = Path("~/projects/vig/.certs/betfair.crt").expanduser()
        cert_pem = Path("~/projects/vig/.certs/betfair.pem").expanduser()
        if not cert_crt.exists() or not cert_pem.exists():
            raise BetfairUnavailable("Betfair SSL cert not found at ~/projects/vig/.certs/")

        with httpx.Client(cert=(str(cert_crt), str(cert_pem)), timeout=10) as client:
            resp = client.post(
                BETFAIR_LOGIN_URL,
                data={"username": config.BETFAIR_USERNAME, "password": config.BETFAIR_PASSWORD},
                headers={
                    "X-Application": config.BETFAIR_API_KEY,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
        if resp.status_code != 200:
            raise BetfairUnavailable(f"Login HTTP error: {resp.status_code} — {resp.text[:300]}")

        try:
            data = resp.json()
        except Exception:
            raise BetfairUnavailable(f"Login returned non-JSON: {resp.text[:400]}")

        if data.get("loginStatus") != "SUCCESS":
            raise BetfairUnavailable(f"Login failed: {data.get('loginStatus', 'unknown')}")

        return data["sessionToken"]

    def token(self) -> str:
        # Refresh every 3 hours (tokens last ~4 hours)
        if self._token is None or (time.time() - self._token_time) > 10800:
            self._token = self._login()
            self._token_time = time.time()
        return self._token

    def force_refresh(self) -> None:
        self._token = None

    def headers(self) -> dict:
        return {
            "X-Application": config.BETFAIR_API_KEY,
            "X-Authentication": self.token(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }


_session = _SessionManager()


def _post(endpoint: str, body: dict) -> list:
    url = f"{BETFAIR_API_BASE}/{endpoint}/"
    try:
        resp = httpx.post(url, headers=_session.headers(), json=body, timeout=15)
    except httpx.RequestError as e:
        raise BetfairUnavailable(f"Network error: {e}") from e

    if resp.status_code == 401:
        _session.force_refresh()
        try:
            resp = httpx.post(url, headers=_session.headers(), json=body, timeout=15)
        except httpx.RequestError as e:
            raise BetfairUnavailable(f"Network error on retry: {e}") from e

    if resp.status_code != 200:
        raise BetfairUnavailable(f"API error {resp.status_code}: {resp.text[:200]}")

    return resp.json()


def get_epl_markets() -> List[BetfairMarket]:
    """Fetch EPL markets with best available back prices."""

    # Step 1: market catalogue — runner names, event names, market types
    catalogue = _post("listMarketCatalogue", {
        "filter": {
            "eventTypeIds": [FOOTBALL_EVENT_TYPE_ID],
            "competitionIds": [EPL_COMPETITION_ID],
            "marketTypeCodes": MARKET_TYPES,
            "inPlayOnly": False,
        },
        "marketProjection": ["RUNNER_DESCRIPTION", "EVENT", "MARKET_DESCRIPTION"],
        "maxResults": "200",
        "sort": "FIRST_TO_START",
    })

    if not catalogue:
        return []

    market_info = {}
    for m in catalogue:
        market_id = m["marketId"]
        event_name = m.get("event", {}).get("name", "Unknown")
        market_type = m.get("description", {}).get("marketType", "")
        runners = [
            BetfairRunner(
                selection_id=r["selectionId"],
                name=r["runnerName"],
            )
            for r in m.get("runners", [])
            if r.get("sortPriority", 99) <= 3
        ]
        market_info[market_id] = {
            "event_name": event_name,
            "market_type": market_type,
            "runners": runners,
        }

    if not market_info:
        return []

    # Step 2: best available back prices
    books = _post("listMarketBook", {
        "marketIds": list(market_info.keys()),
        "priceProjection": {
            "priceData": ["EX_BEST_OFFERS"],
            "exBestOffersOverrides": {"bestPricesDepth": 1},
        },
    })

    markets = []
    for book in books:
        market_id = book["marketId"]
        if market_id not in market_info:
            continue

        info = market_info[market_id]
        runner_map = {r.selection_id: r for r in info["runners"]}

        updated_runners = []
        for rb in book.get("runners", []):
            sel_id = rb["selectionId"]
            if sel_id not in runner_map:
                continue
            available = rb.get("ex", {}).get("availableToBack", [])
            best_back = available[0].get("price") if available else None
            r = runner_map[sel_id]
            updated_runners.append(BetfairRunner(
                selection_id=sel_id,
                name=r.name,
                best_back_price=best_back,
            ))

        markets.append(BetfairMarket(
            market_id=market_id,
            market_type=info["market_type"],
            event_name=info["event_name"],
            runners=updated_runners,
        ))

    return markets
