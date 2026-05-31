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
