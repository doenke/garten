"""Helpers for deriving resolver configuration from catalog URL templates."""

from urllib.parse import parse_qsl, urlsplit, urlunsplit


def config_from_search_url_template(template, defaults):
    """Merge resolver defaults with a catalog search URL template.

    Search URL templates are stored as user-facing URLs such as
    ``https://example.org/search?q={q}``. Resolvers, however, need a request URL
    and a query parameter name. When the template contains a ``{q}`` query
    value, the helper stores the URL without its query string in ``search_url``
    and stores the matching parameter key in ``query_param``.
    """
    config = dict(defaults or {})
    template = (template or '').strip()
    if not template:
        return config

    config['search_url_template'] = template
    parsed = urlsplit(template)
    if not parsed.scheme or not parsed.netloc:
        return config

    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if value == '{q}':
            config['query_param'] = key
            break

    config['search_url'] = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
    return config
