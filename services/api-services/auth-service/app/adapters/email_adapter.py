import grpc
from proto import notifier_pb2, notifier_pb2_grpc

class EmailAdapter:
    def __init__(self):
        channel = grpc.insecure_channel('localhost:50051')
        self.stub = notifier_pb2_grpc.NotifierStub(channel)

    def send_email(self, to: str, subject: str, body: str):
        request = notifier_pb2.EmailRequest(
            to=to,
            subject=subject,
            message=body,
            html=body
        )
        response = self.stub.SendEmail(request)
        if not response.ok:
            raise Exception(f"Email failed: {response.error}")
