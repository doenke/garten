from .url_templates import config_from_search_url_template


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
    """Compatibility wrapper for older callers.

    New resolver code uses ``TaxonomyResolver.build_config`` and
    ``config_from_search_url_template`` directly.
    """
    config = config_from_search_url_template(getattr(catalog, 'search_url_template', None), defaults)
    config['catalog_key'] = catalog.key
    return config
