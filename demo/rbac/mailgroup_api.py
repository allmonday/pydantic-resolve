"""Mock third-party mail group API.

In production, this would call an external service (e.g. Microsoft Graph,
Google Admin SDK, or an internal directory service) to resolve user → group
membership.

For the demo, we use an in-memory mapping.
"""

from __future__ import annotations

# user_id → list of mail groups (simulating external API response)
_USER_GROUPS: dict[int, list[dict]] = {
    1: [{"id": 1, "name": "engineering-all", "email": "eng-all@acme.com"}],
    2: [
        {"id": 1, "name": "engineering-all", "email": "eng-all@acme.com"},
        {"id": 3, "name": "eng-leads", "email": "eng-leads@acme.com"},
    ],
    3: [{"id": 2, "name": "marketing-all", "email": "mkt-all@acme.com"}],
    4: [{"id": 2, "name": "marketing-all", "email": "mkt-all@acme.com"}],
}


async def get_mail_groups_by_user(user_id: int) -> list[dict]:
    """Mock: call third-party API to get user's mail groups.

    In production: HTTP call to external directory service.
    """
    return _USER_GROUPS.get(user_id, [])
