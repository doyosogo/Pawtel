"""Small shared HTTPX client for real authenticated PostgreSQL API tests."""

import asyncio

import httpx

PASSWORD = "a correct ordinary passphrase"
EMAIL = "owner@example.com"


class API:
    def __init__(self, app, settings):
        self.settings = settings
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="https://api.example.com"
            if settings.session_cookie_secure
            else "http://testserver",
            headers={
                "X-PAWTEL-Request": "1",
                "Origin": settings.backend_cors_origins[0],
            },
        )

    def get(self, path, **kwargs):
        return asyncio.run(self.client.get("/api/v1/auth" + path, **kwargs))

    def post(self, path, data=None, **kwargs):
        return asyncio.run(
            self.client.post("/api/v1/auth" + path, json=data or {}, **kwargs)
        )

    def register(self, **overrides):
        return self.post(
            "/register",
            {
                "email": EMAIL,
                "display_name": "Owner",
                "password": PASSWORD,
                **overrides,
            },
        )

    def login(self, email=EMAIL, password=PASSWORD, **kwargs):
        return self.post("/login", {"email": email, "password": password}, **kwargs)

    def csrf(self):
        response = self.get("/csrf")
        assert response.status_code == 200
        return {"X-CSRF-Token": response.json()["csrf_token"]}
