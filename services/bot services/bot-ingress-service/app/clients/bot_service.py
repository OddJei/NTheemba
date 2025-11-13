from typing import Any, Dict, Optional
import httpx
from ..core.config import Settings


async def get_bot_by_phone(client: httpx.AsyncClient, settings: Settings, phone: str) -> Optional[Dict[str, Any]]:
    
    """
    Get a bot by phone number from the Bot Service

    Args:
        client: An instance of httpx.AsyncClient.
        settings: An instance of Settings.
        phone: The phone number to search for.

    Returns:
        A dictionary containing the bot's details(bot details, business details,owner details), or None if no bot was found.
    """
    url = f"{settings.bot_service_url}/bot/by-phone/{phone}"
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise
