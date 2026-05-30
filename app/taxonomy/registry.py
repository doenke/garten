from urllib.parse import parse_qsl, urlsplit, urlunsplit


_RESOLVERS = []


def register_resolver(resolver):
    if not getattr(resolver, 'key', None):
        raise ValueError('Taxonomy resolver must define a stable key.')

    for index, registered in enumerate(_RESOLVERS):
        if registered.key == resolver.key:
            _RESOLVERS[index] = resolver
            return resolver
    _RESOLVERS.append(resolver)
    return resolver


def get_resolver_for_catalog(catalog):
    for resolver in _RESOLVERS:
        if resolver.supports(catalog):
            return resolver
    return None


def iter_resolvers():
    return iter(tuple(_RESOLVERS))


def build_html_search_config(catalog, defaults):
    config = dict(defaults or {})
    template = (getattr(catalog, 'search_url_template', None) or '').strip()
    if not template:
        config['catalog_key'] = catalog.key
        return config

    parsed = urlsplit(template)
    if not parsed.scheme or not parsed.netloc:
        config['catalog_key'] = catalog.key
        return config

    query_param = None
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if value == '{q}':
            query_param = key
            break

    if query_param:
        config['query_param'] = query_param
    config['search_url'] = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
    config['catalog_key'] = catalog.key
    return config
