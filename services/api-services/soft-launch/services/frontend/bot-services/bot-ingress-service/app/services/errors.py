class IngressError(Exception):
    pass


class PayloadValidationError(IngressError):
    def __init__(self, validation_error: str):
        super().__init__(validation_error)
        self.validation_error = validation_error


class BotNotFoundError(IngressError):
    def __init__(self, phone: str):
        super().__init__(f"Bot not found for phone {phone}")
        self.phone = phone
