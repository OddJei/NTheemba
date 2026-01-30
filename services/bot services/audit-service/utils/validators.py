def validate_event_shape(event: dict) -> bool:
    required = ['service', 'event_type', 'payload']
    for k in required:
        if k not in event:
            return False
    return True
