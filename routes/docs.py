"""
Docs Integration Routes
=======================

Redirects /api/docs/ to the canonical docs page for the Quiz App on
docs.laurence.computer, and exposes /api/spec for the docs service.
"""

import os
import yaml
from flask import Blueprint, redirect, jsonify

bp = Blueprint('docs', __name__)

_DOCS_BASE = 'https://docs.laurence.computer/quiz-app'


@bp.route('/api/docs/')
@bp.route('/api/docs/<path:path>')
def docs_redirect(path=''):
    """Redirect to the canonical docs page for the Quiz App."""
    print(f'[DOCS_INTEGRATION] Redirecting /api/docs/{path}')
    if path in ('playground', 'playground/'):
        return redirect(f'{_DOCS_BASE}/playground')
    return redirect(f'{_DOCS_BASE}/')


@bp.route('/api/spec')
def api_spec():
    """Return the OpenAPI spec as JSON. Public endpoint for the docs service."""
    print('[DOCS_INTEGRATION] Serving /api/spec')
    spec_path = os.path.join(os.path.dirname(__file__), '..', 'openapi.yaml')
    spec_path = os.path.abspath(spec_path)
    if not os.path.exists(spec_path):
        return jsonify({'error': 'No OpenAPI spec found'}), 404
    try:
        with open(spec_path, 'r') as f:
            spec = yaml.safe_load(f)
        return jsonify(spec), 200
    except Exception as exc:
        print(f'[DOCS_INTEGRATION] Failed to load openapi.yaml: {exc}')
        return jsonify({'error': 'Failed to parse spec'}), 500
