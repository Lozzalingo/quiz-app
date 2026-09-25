"""
Auth client for Lozzalingo ecosystem services.
Copy this file into your service to validate JWTs from auth.laurence.computer.

Usage:
    from auth_client import require_auth, require_site_access, require_super_admin

    @app.route('/admin/dashboard')
    @require_auth
    def dashboard():
        return render_template('dashboard.html', user=g.auth_user)

    @app.route('/admin/settings')
    @require_site_access('fat-big-quiz', 'admin')
    def settings():
        ...

    @app.route('/super-admin')
    @require_super_admin
    def super_panel():
        ...

Environment variables:
    AUTH_SERVICE_URL  - Base URL of the auth service (default: https://auth.laurence.computer)
    AUTH_JWT_SECRET   - Shared JWT secret for HS256 verification (required in production)
"""
import os
import json
import hmac
import hashlib
import base64
import time
from functools import wraps
from flask import request, g, redirect, jsonify


AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'https://auth.laurence.computer')
JWT_SECRET = os.getenv('AUTH_JWT_SECRET', '')


def _b64_decode(data):
    """Decode base64url-encoded data with padding."""
    padding = 4 - len(data) % 4
    if padding != 4:
        data += '=' * padding
    return base64.urlsafe_b64decode(data)


def decode_jwt(token):
    """
    Decode and verify a JWT token (HS256).
    Returns the payload dict or None if invalid/expired.
    """
    if not JWT_SECRET:
        return None

    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None

        header_b64, payload_b64, signature_b64 = parts

        # Verify signature
        signing_input = f'{header_b64}.{payload_b64}'.encode('utf-8')
        expected_sig = hmac.new(
            JWT_SECRET.encode('utf-8'),
            signing_input,
            hashlib.sha256
        ).digest()
        actual_sig = _b64_decode(signature_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Decode header to confirm algorithm
        header = json.loads(_b64_decode(header_b64))
        if header.get('alg') != 'HS256':
            return None

        # Decode payload
        payload = json.loads(_b64_decode(payload_b64))

        # Check expiry
        exp = payload.get('exp')
        if exp and time.time() > exp:
            return None

        return payload

    except Exception:
        return None


def require_auth(f):
    """Decorator that requires a valid JWT token (cookie or Authorization header)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = (
            request.cookies.get('auth_token')
            or request.headers.get('Authorization', '').replace('Bearer ', '')
        )
        if not token:
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(f'{AUTH_SERVICE_URL}/login?redirect={request.url}')

        payload = decode_jwt(token)
        if not payload:
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Invalid or expired token'}), 401
            return redirect(f'{AUTH_SERVICE_URL}/login?redirect={request.url}')

        g.auth_user = payload
        return f(*args, **kwargs)
    return decorated


def require_site_access(site_id, min_role='viewer'):
    """
    Decorator that requires the user to have access to a specific site
    with at least the specified role.

    Role hierarchy: viewer < editor < admin < owner
    Super admins bypass all site access checks.
    """
    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            user = g.auth_user
            if user.get('is_super_admin'):
                return f(*args, **kwargs)

            access = next(
                (a for a in user.get('site_access', []) if a['site_id'] == site_id),
                None
            )
            if not access:
                return jsonify({'error': 'Access denied'}), 403

            roles = ['viewer', 'editor', 'admin', 'owner']
            if roles.index(access['role']) < roles.index(min_role):
                return jsonify({'error': 'Insufficient role'}), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def require_super_admin(f):
    """Decorator that requires the user to be a super admin."""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if not g.auth_user.get('is_super_admin'):
            return jsonify({'error': 'Super admin required'}), 403
        return f(*args, **kwargs)
    return decorated
