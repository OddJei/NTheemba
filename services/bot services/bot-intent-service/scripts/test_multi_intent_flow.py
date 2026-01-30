import asyncio
import json
from datetime import datetime

# Fake the minimal dependencies to run the intent logic without full backend/redis
from app.services.intent_service import service
from app.models.schemas import IntentRequest, IntentResponse
from app.core.config import get_settings

async def mock_multi_intent_test():
    settings = get_settings()
    
    # Check if Gemini is enabled; if not, we can only test the 'structure' but not meaningful parsing
    print(f"Gemini Enabled: {settings.gemini.enabled}")
    if not settings.gemini.api_key:
        print("WARNING: No INTENT_GEMINI_API_KEY found. Result will fallback to deterministic/unknown.")

    # 1. Construct a rich request
    # Simulating: "hey how are you?. i want 2 oranges, and 4 aooles deliverered at riverside afternoon i will use mtn to pay"
    # With context: Cart has 1 item already, User is 'Alice', History shows greeting.
    
    req_payload = {
        "event_id": "test-event-001",
        "session_id": "test-session-Alice",
        "raw_text": "i want 2 oranges, and 4 apples delivered at riverside afternoon i will use mtn to pay",
        "enriched_meta": {
            "user": {"first_name": "Alice"},
            "session_context": {
                "current_node": "browsing_aisle",
                "order_draft": {
                    "items": [{"name": "Banana", "qty": 6}]
                }
            },
            "previous_events": [
                {"from_user": True, "text": "Hi bot"},
                {"from_user": False, "text": "Hello Alice, welcome back!"}
            ]
        }
    }
    
    request = IntentRequest(**req_payload)
    print("\n--- Input Request ---")
    print(f"Text: {request.raw_text}")
    
    # 2. Run Resolution
    print("\n--- Resolving... ---")
    response = await service.resolve(request)
    
    # 3. Inspect Output
    print("\n--- Result ---")
    print(f"Primary Intent: {response.intent.id} ({response.intent.name})")
    
    print(f"\nCaught {len(response.intents)} total intents:")
    for idx, i in enumerate(response.intents):
        print(f"  {idx+1}. ID={i.id} Conf={i.confidence} Slots={i.slots}")
    
    print("\nDiagnostics:")
    print(json.dumps(response.diagnostics, indent=2))

if __name__ == "__main__":
    try:
        asyncio.run(mock_multi_intent_test())
    except Exception as e:
        print(f"Test failed: {e}")
