"""HTTP execution helpers for taxonomy resolver external calls."""

import requests

from .base import ExternalCall


USER_AGENT = 'garten-taxonomy-resolver/1.0'
REQUEST_TIMEOUT = 8


def execute_external_call(call: ExternalCall, headers=None, timeout=None):
    """Execute an :class:`ExternalCall` and return the HTTP response.

    ``ExternalCall`` intentionally only describes the request.  This helper is
    the central place that turns that description into a network request, so
    individual resolvers can stay focused on building calls and parsing
    responses.
    """
    request_headers = {'User-Agent': USER_AGENT}
    if headers:
        request_headers.update(headers)

    response = requests.get(
        call.url,
        params=call.query,
        headers=request_headers,
        timeout=REQUEST_TIMEOUT if timeout is None else timeout,
    )
    response.raise_for_status()
    return response


def fetch_response(call: ExternalCall, accept: str):
    return execute_external_call(call, headers={'Accept': accept})


def parse_json_response(response, logger=None):
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        if logger:
            logger.warning('taxonomy resolver non-json response from %s (status=%s)', response.url, response.status_code)
        return None


def fetch_json(call: ExternalCall, accept: str = 'application/json'):
    try:
        response = execute_external_call(call, headers={'Accept': accept})
    except requests.RequestException:
        return None
    return parse_json_response(response)


def fetch_text(call: ExternalCall, accept: str = 'text/html,application/xhtml+xml'):
    try:
        response = execute_external_call(call, headers={'Accept': accept})
    except requests.RequestException:
        return None
    return response.text or ''
