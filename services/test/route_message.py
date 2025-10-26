import requests

url = "http://127.0.0.1:5000/route_message"
data = {
    "receiver_phone": "260952675580",  # WhatsApp Business number
    "sender_phone": "260960977645",    # User sending the message
    "message_body": "1",  # Message text
    "message_id": "ABC123XYZ792"       # Unique WhatsApp message ID
}

response = requests.post(url, json=data)
print("Server Response:", response.json())
