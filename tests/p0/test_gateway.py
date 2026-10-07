import os
import time

import httpx


def test_live_kong_route_and_rate_limit():
    """Exercise the checked-in Kong plugin, not a mock or FastAPI limiter."""
    with httpx.Client(base_url=os.environ["GATEWAY_URL"], timeout=10) as gateway:
        # First request proves the /api path reaches actual Uvicorn with auth enforced.
        response = gateway.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert "kong" in response.headers.get("via", "").lower()
        assert response.headers["x-ratelimit-limit-minute"] == "60"
        # Start well inside a fresh minute window so startup timing cannot flake the test.
        # Kong is new for every invocation; only this test sends requests to its proxy.
        remaining_seconds = 60 - (time.time() % 60)
        if remaining_seconds < 15:
            time.sleep(remaining_seconds + 0.1)
        response = gateway.get("/health")
        assert response.status_code == 200 and response.json()["status"] == "ok"
        remaining = int(response.headers["x-ratelimit-remaining-minute"])
        assert 0 <= remaining <= 59
        for _ in range(remaining):
            assert gateway.get("/health").status_code == 200
        blocked = gateway.get("/health")
        assert blocked.status_code == 429
        assert int(blocked.headers["retry-after"]) > 0
        # Limit is global across configured routes for this caller's IP.
        assert gateway.get("/api/v1/products/").status_code == 429
    with httpx.Client(base_url=os.environ["BACKEND_URL"], timeout=10) as backend:
        assert backend.get("/health").status_code == 200
