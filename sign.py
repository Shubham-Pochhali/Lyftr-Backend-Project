import hmac, hashlib, os

secret = os.environ.get("WEBHOOK_SECRET", "testsecret")
body = b'{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'

sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
print(sig)
