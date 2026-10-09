"""Independent issuer, audience and access-token validation."""
import time
from jose import JWTError, jwt
from app.config import settings
from deployment.jwks import JWKSCache, KID

cache = JWKSCache(settings.OIDC_ISSUER, settings.OIDC_CA_FILE,
                  settings.OIDC_JWKS_TTL, settings.OIDC_JWKS_REFRESH_INTERVAL)


def decode_oidc_access_token(token):
    try:
        if not isinstance(token, str) or len(token) > 16384:
            raise JWTError("Invalid token")
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if (header.get("alg") != "RS256" or header.get("typ") != "JWT" or
                not isinstance(kid, str) or not KID.fullmatch(kid)):
            raise JWTError("Unsupported JWT header")
        key = cache.key(kid)
        payload = jwt.decode(token, key, algorithms=["RS256"], issuer=settings.OIDC_ISSUER,
            audience=settings.OIDC_AUDIENCE, options={"require_exp": True,
                "require_iat": True, "require_sub": True, "require_aud": True,
                "require_iss": True, "verify_at_hash": False})
        sub = payload.get("sub")
        if (payload.get("typ") != "Bearer" or payload.get("azp") != settings.OIDC_CLIENT_ID or
                not isinstance(sub, str) or not sub.strip() or len(sub) > 255 or
                any(ord(c) < 32 for c in sub) or not isinstance(payload.get("iat"), int) or
                isinstance(payload["iat"], bool) or payload["iat"] > time.time() + 5 or
                not isinstance(payload.get("exp"), int) or isinstance(payload["exp"], bool) or
                payload["exp"] <= payload["iat"] or payload["exp"]-payload["iat"] > 300):
            raise JWTError("Invalid access-token semantics")
        return payload
    except (ValueError, KeyError, TypeError, OverflowError, AttributeError) as exc:
        raise JWTError("Malformed access token") from exc
