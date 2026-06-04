from jose import jwt
from datetime import datetime, timedelta, timezone
secret = " super-secret-development-key\
payload={\sub\:\admin\,\exp\:datetime.now(timezone.utc)+timedelta(minutes=60)}
print(jwt.encode(payload, secret, algorithm=\HS256\))
