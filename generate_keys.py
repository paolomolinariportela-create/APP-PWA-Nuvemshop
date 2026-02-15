from pywebpush import WebPusher

# Gera chaves VAPID
private_key = WebPusher.generate_vapid_keys()[0]
public_key = WebPusher.generate_vapid_keys()[1]

print(f"VAPID_PRIVATE_KEY={private_key}")
print(f"VAPID_PUBLIC_KEY={public_key}")
print("Salve essas chaves no seu .env do Railway e local!")
