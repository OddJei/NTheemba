"""Reply generator for custom bot."""


class ReplyGenerator:
    def format_reply(self, execution_result: dict) -> dict:
        return {"text": execution_result.get("reply", "")}
