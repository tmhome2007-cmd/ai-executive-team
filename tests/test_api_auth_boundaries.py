"""Malformed owner headers must fail closed without crashing the API."""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from config import config
from main import app, _failed_auth_attempts


class AuthBoundaryTests(unittest.TestCase):
    def test_non_ascii_guesses_are_rejected_and_owner_is_not_locked_out(self):
        key = "synthetic-owner-auth-boundary-1234567890"
        with (
            patch.object(config, "API_SECRET_KEY", key),
            patch.dict(_failed_auth_attempts, {}, clear=True),
        ):
            client = TestClient(app)
            for index in range(7):
                response = client.get(
                    "/system/health", headers={b"X-API-Key": b"\xffinvalid"}
                )
                self.assertEqual(response.status_code, 401 if index < 5 else 429)
            # Use a route that doesn't depend on live database/model health.
            response = client.get("/meeting-types", headers={"X-API-Key": key})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("testclient", _failed_auth_attempts)

    def test_every_operational_route_requires_owner_authentication(self):
        from fastapi.routing import APIRoute
        from main import verify_api_key

        public = {"/", "/favicon.ico"}
        client = TestClient(app)
        with (
            patch.object(
                config, "API_SECRET_KEY", "synthetic-route-audit-key-1234567890"
            ),
            patch.dict(_failed_auth_attempts, {}, clear=True),
        ):
            checked = 0
            for route in app.routes:
                if not isinstance(route, APIRoute) or route.path in public:
                    continue
                self.assertIn(
                    verify_api_key,
                    [item.call for item in route.dependant.dependencies],
                    route.path,
                )
                path = route.path
                for parameter in route.param_convertors:
                    path = path.replace("{" + parameter + "}", "1")
                for method in route.methods:
                    _failed_auth_attempts.clear()
                    response = client.request(method, path)
                    self.assertEqual(
                        response.status_code,
                        401,
                        (method, route.path, response.status_code),
                    )
                    checked += 1
            self.assertGreater(checked, 50)
            # FastAPI can retain included routers lazily; OpenAPI resolves their
            # effective paths. Exercise these too, including inherited auth.
            import re

            for path, operations in app.openapi()["paths"].items():
                if path in public:
                    continue
                for method in operations:
                    if method not in {"get", "post", "put", "patch", "delete"}:
                        continue
                    _failed_auth_attempts.clear()
                    response = client.request(
                        method.upper(), re.sub(r"\{[^}]+\}", "1", path)
                    )
                    self.assertEqual(
                        response.status_code, 401, (method, path, response.status_code)
                    )
