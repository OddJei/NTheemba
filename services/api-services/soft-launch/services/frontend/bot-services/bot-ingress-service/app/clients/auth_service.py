from typing import Any, Dict, Optional
import httpx
from ..core.config import Settings


async def lookup_user(client: httpx.AsyncClient, settings: Settings, phone: str, business_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Lookup a user by phone number, optionally filtered by business ID.

    Args:
        client: An instance of httpx.AsyncClient.
        settings: An instance of Settings.
        phone: The phone number to search for.
        business_id: An optional business ID to filter results by.

    Returns:
        A dictionary containing the user's details, or None if no user was found.
    """
    params = {"phone": phone}
    if business_id:
        params["business_id"] = business_id
    url = f"{settings.auth_service_url}/auth/users/lookup"
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise
