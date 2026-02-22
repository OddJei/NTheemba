import inspect
from app.helpers import service_helpers

print("Imported service_helpers module")

for name in [
    "get_service_token",
    "get_user_by_phone",
    "get_business_by_phone",
    "get_business_by_id",
    "deliver",
]:
    fn = getattr(service_helpers, name, None)
    print(name, "exists:" , fn is not None, "callable:", callable(fn))
    if fn is not None:
        try:
            print("  signature:", inspect.signature(fn))
        except Exception as e:
            print("  signature unavailable:", e)
