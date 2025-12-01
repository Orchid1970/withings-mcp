import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

WITHINGS_API_BASE = "https://wbsapi.withings.net"


class WithingsAPIError(RuntimeError):
    """Raised when the Withings API responds with a non-zero status."""


class WithingsClient:
    """
    Lightweight Withings API client supporting measurement, activity, and sleep endpoints.
    Requires an OAuth access token that already has scopes:
      - user.metrics
      - user.activity
      - user.sleepevents
    """

    def __init__(self, access_token: str, timeout: float = 30.0) -> None:
        self.access_token = access_token
        self._client = httpx.Client(timeout=timeout)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------
    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST helper that injects the access token, parses the response, and
        raises WithingsAPIError if the API returns a non-zero status.
        """
        data = {
            "access_token": self.access_token,
            **payload,
        }
        response = self._client.post(f"{WITHINGS_API_BASE}{path}", data=data)
        response.raise_for_status()
        body = response.json()
        if body.get("status") != 0:
            raise WithingsAPIError(
                f"Withings API error {body.get('status')}: {body.get('error')}"
            )
        return body["body"]

    # -------------------------------------------------------------------------
    # Measurement groups (existing functionality)
    # -------------------------------------------------------------------------
    def get_measures(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Wrapper around /measure?action=getmeas to retrieve measurement groups.
        Accepts kwargs such as startdate, enddate, meastype, etc.
        """
        return self._post("/measure", {"action": "getmeas", **kwargs})

    # -------------------------------------------------------------------------
    # Activity (steps, distance, calories, intensity zones, etc.)
    # -------------------------------------------------------------------------
    def get_daily_activity(
        self,
        startdateymd: str,
        enddateymd: str,
        data_fields: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch daily activity summaries between startdateymd and enddateymd (YYYY-MM-DD).
        Requires scope user.activity.
        """
        if data_fields is None:
            data_fields = ",".join(
                [
                    "steps",
                    "distance",
                    "calories",
                    "totalcalories",
                    "soft",
                    "moderate",
                    "intense",
                    "active",
                    "hr_average",
                    "hr_min",
                    "hr_max",
                ]
            )

        body = self._post(
            "/v2/measure",
            {
                "action": "getactivity",
                "startdateymd": startdateymd,
                "enddateymd": enddateymd,
                "data_fields": data_fields,
            },
        )
        return body.get("activities", [])

    # -------------------------------------------------------------------------
    # Sleep summaries (aggregated sleep metrics)
    # -------------------------------------------------------------------------
    def get_sleep_summary(
        self,
        startdateymd: str,
        enddateymd: str,
        data_fields: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch sleep summary series (per-night aggregated metrics).
        Requires scope user.sleepevents.
        """
        if data_fields is None:
            data_fields = ",".join(
                [
                    "sleep_score",
                    "total_sleep_time",
                    "total_timeinbed",
                    "deepsleepduration",
                    "lightsleepduration",
                    "remsleepduration",
                    "wakeupduration",
                    "wakeupcount",
                    "wasoduration",
                    "efficiency",
                    "avg_wakeup_latency",
                ]
            )

        body = self._post(
            "/v2/sleep",
            {
                "action": "getsummary",
                "startdateymd": startdateymd,
                "enddateymd": enddateymd,
                "data_fields": data_fields,
            },
        )
        return body.get("series", [])

    # -------------------------------------------------------------------------
    # Sleep events (raw timelines)
    # -------------------------------------------------------------------------
    def get_sleep_events(
        self,
        startdate: int,
        enddate: int,
    ) -> List[Dict[str, Any]]:
        """
        Fetch raw sleep event data between unix timestamps.
        Event types (per Withings):
         1 = got in bed
         2 = fell asleep
         3 = woke up
         4 = got out of bed
         5 = manually entered asleep period start
        Requires scope user.sleepevents.
        """
        body = self._post(
            "/v2/sleep",
            {
                "action": "getsleep",
                "startdate": startdate,
                "enddate": enddate,
            },
        )
        return body.get("series", [])


# -------------------------------------------------------------------------
# Legacy workflow helpers (placeholders until the new ingestion path lands)
# -------------------------------------------------------------------------
async def sync_user(user_id: str) -> None:
    """
    Placeholder async helper to preserve import compatibility with workflows.
    Extend this function to perform actual ingestion & persistence for a single user.
    """
    logger.info("sync_user placeholder called for user_id=%s (no-op)", user_id)


async def sync_all_users() -> None:
    """
    Placeholder async helper for bulk synchronization. Implement as needed.
    """
    logger.info("sync_all_users placeholder called (no-op)")
