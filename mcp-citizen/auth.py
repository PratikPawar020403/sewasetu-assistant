# -*- coding: utf-8 -*-
"""
Authentication module for the Citizen MCP Server.

Validates OAuth 2.1 JWT access tokens from the Sewa Setu portal using the
JWKS endpoint. Ensures the token has the 'citizen' scope.
"""

import json
import time
import logging

import jwt
import requests

logger = logging.getLogger(__name__)

# Cache the JWKS keys
_jwks_cache = {"keys": None, "fetched_at": 0}
JWKS_CACHE_TTL = 300  # 5 minutes


def fetch_jwks(portal_url):
    """Fetch the portal's JWKS keys."""
    now = time.time()
    if _jwks_cache["keys"] and (now - _jwks_cache["fetched_at"]) < JWKS_CACHE_TTL:
        return _jwks_cache["keys"]

    try:
        resp = requests.get(f"{portal_url}/.well-known/jwks.json", timeout=10)
        resp.raise_for_status()
        jwks = resp.json()
        _jwks_cache["keys"] = jwks
        _jwks_cache["fetched_at"] = now
        return jwks
    except Exception as e:
        logger.error("Failed to fetch JWKS: %s", e)
        if _jwks_cache["keys"]:
            return _jwks_cache["keys"]
        raise


def validate_token(token, portal_url, required_scope="citizen"):
    """Validate a JWT access token.

    Returns (claims, None) on success or (None, error_message) on failure.
    """
    try:
        jwks = fetch_jwks(portal_url)
    except Exception as e:
        return None, "Failed to fetch JWKS: %s" % str(e)

    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        key_data = None
        for k in jwks.get("keys", []):
            if k.get("kid") == kid:
                key_data = k
                break

        if not key_data:
            return None, "Unknown signing key (kid=%s)" % kid

        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))

        claims = jwt.decode(
            token, public_key, algorithms=["RS256"],
            options={"verify_aud": False, "verify_iss": False}
        )

        # Check scope
        if claims.get("scope") != required_scope:
            return None, "Token scope '%s' does not match required scope '%s'" % (
                claims.get("scope"), required_scope)

        return claims, None

    except jwt.ExpiredSignatureError:
        return None, "Token expired"
    except jwt.PyJWTError as e:
        return None, "Invalid token: %s" % str(e)
