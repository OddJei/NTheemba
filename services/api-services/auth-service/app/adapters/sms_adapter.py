import grpc
from proto import notifier_pb2, notifier_pb2_grpc

class SMSAdapter:
    def __init__(self):
        channel = grpc.insecure_channel('localhost:50051')
        self.stub = notifier_pb2_grpc.NotifierStub(channel)

    def send_sms(self, to: str, message: str):
        request = notifier_pb2.SMSRequest(to=to, message=message)
        response = self.stub.SendSMS(request)
        if not response.ok:
            raise Exception(f"SMS failed: {response.error}")
