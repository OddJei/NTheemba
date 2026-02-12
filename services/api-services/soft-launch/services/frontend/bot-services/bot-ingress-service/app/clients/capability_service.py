from typing import Any, Dict
import httpx
from ..core.config import Settings


async def fetch_capabilities(client: httpx.AsyncClient, settings: Settings, mode_name: str) -> Dict[str, Any]:
    """
    Fetch capabilities by mode name.

    Args:
        client: An instance of httpx.AsyncClient.
        settings: An instance of Settings.
        mode_name: The name of the mode to fetch capabilities for.

    Returns:
        A dictionary containing the capabilities for the given mode name.
    """
    url = f"{settings.capability_service_url}/capabilities/by-mode-name/{mode_name}"
    response = await client.get(url)
    response.raise_for_status()
    return response.json()
