from dataclasses import dataclass, field
from typing import Mapping

from . import registry
from . import resolvers  # noqa: F401 - import triggers static resolver registration
from .resolvers.base import ExternalCall, ResolverResult


@dataclass(frozen=True)
class TaxonomySuggestion:
    scientific_name: str
    matches: Mapping[str, str] = field(default_factory=dict)
    unavailable_catalogs: list[str] = field(default_factory=list)
    external_calls: list[ExternalCall] = field(default_factory=list)

    @property
    def confidence(self):
        return 0.9 if self.matches else 0.0

    @property
    def note(self):
        return 'IDs werden katalogspezifisch ermittelt. Ohne Resolver gibt es keinen Vorschlag.'

    def to_response(self, *, trace_id, duration_ms):
        return {
            'ok': True,
            'scientific_name': self.scientific_name,
            'matches': dict(self.matches),
            'unavailable_catalogs': list(self.unavailable_catalogs),
            'confidence': self.confidence,
            'note': self.note,
            'debug': {
                'trace_id': trace_id,
                'duration_ms': duration_ms,
                'external_calls': [call.to_dict() for call in self.external_calls],
            },
        }


def resolver_config_for_catalog(catalog):
    taxonomy_resolver = registry.get_resolver_for_catalog(catalog)
    if not taxonomy_resolver:
        return {'catalog_key': catalog.key, 'mode': 'none'}
    return taxonomy_resolver.build_config(catalog)


def _resolver_for_key(catalog_key):
    for resolver in registry.iter_resolvers():
        if resolver.key == catalog_key:
            return resolver
    return None


def resolve_taxonomy_id_for_catalog(catalog_key, scientific_name, resolver=None):
    config = dict(resolver or {'catalog_key': catalog_key})
    config.setdefault('catalog_key', catalog_key)
    taxonomy_resolver = _resolver_for_key(catalog_key)
    if not taxonomy_resolver:
        return None
    return taxonomy_resolver.resolve(scientific_name, config).taxonomy_id


def resolve_for_catalog(catalog, scientific_name):
    taxonomy_resolver = registry.get_resolver_for_catalog(catalog)
    if not taxonomy_resolver:
        return ResolverResult(catalog.key, unavailable=True)

    resolver_config = taxonomy_resolver.build_config(catalog)
    return taxonomy_resolver.resolve(scientific_name, resolver_config)


def suggest_ids(scientific_name, catalogs):
    matches: dict[str, str] = {}
    unavailable: list[str] = []
    external_calls: list[ExternalCall] = []

    for catalog in catalogs:
        result = resolve_for_catalog(catalog, scientific_name)
        if result.unavailable:
            unavailable.append(catalog.key)
            continue
        if result.external_call:
            external_calls.append(result.external_call)
        if result.taxonomy_id:
            matches[catalog.key] = result.taxonomy_id

    return TaxonomySuggestion(
        scientific_name=scientific_name,
        matches=matches,
        unavailable_catalogs=unavailable,
        external_calls=external_calls,
    )


def external_resolver_endpoint(catalog_key):
    taxonomy_resolver = _resolver_for_key(catalog_key)
    if not taxonomy_resolver:
        return None
    if hasattr(taxonomy_resolver, 'default_config'):
        config = taxonomy_resolver.default_config()
    else:
        config = {'mode': getattr(taxonomy_resolver, 'mode', taxonomy_resolver.key)}
    config['catalog_key'] = catalog_key
    call = taxonomy_resolver.debug_call('', config)
    return call.url if call else None
