import os

from locust import HttpUser, between, task


class ChatWidgetUser(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self) -> None:
        self.widget_origin = os.getenv("LOAD_WIDGET_ORIGIN", "http://localhost:3000")
        self.parent_origin = os.getenv("LOAD_PARENT_ORIGIN", "http://localhost:3000")
        response = self.client.post(
            "/api/session",
            headers={"Origin": self.widget_origin},
            json={"locale": "en", "parent_origin": self.parent_origin, "source": {}},
            name="POST /api/session",
        )
        response.raise_for_status()
        payload = response.json()
        self.session_id = payload["session_id"]
        self.token = payload["widget_token"]
        self.message_number = 0
        consent = self.client.post(
            f"/api/session/{self.session_id}/consent",
            headers=self.headers,
            json={
                "notice_version": "load-test-v1",
                "locale": "en",
                "cross_border_ack": True,
            },
            name="POST /consent",
        )
        consent.raise_for_status()

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Origin": self.widget_origin,
            "Authorization": f"Bearer {self.token}",
            "X-Widget-Origin": self.parent_origin,
        }

    @task
    def send_message_until_cap(self) -> None:
        self.message_number += 1
        with self.client.post(
            f"/api/session/{self.session_id}/message",
            headers=self.headers,
            json={"content": "I need to move auto parts from Laredo to Monterrey."},
            name="POST /message (SSE)",
            catch_response=True,
        ) as response:
            if response.status_code == 429:
                response.success()  # Expected when the configured per-session limit is exercised.
            elif response.status_code != 200:
                response.failure(f"unexpected status {response.status_code}")
        if self.message_number >= 21:
            self.stop(True)
