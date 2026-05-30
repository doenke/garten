from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from .resolvers.base import ExternalCall, ResolverRequest, ResolverResult
from .resolvers.floraweb import FlorawebResolver
from .resolvers.gbif import GbifSpeciesMatchResolver
from .resolvers.mein_schoener_garten import MeinSchoenerGartenResolver
from .resolvers.naturadb import NaturadbResolver
from .resolvers.powo import PowoResolver
from .resolvers.wfo import WfoResolver


TAXONOMY_ID_RESOLVER_CONFIG = {
    'gbif': {
        'mode': 'gbif_species_match',
        'prefer_statuses': {'ACCEPTED'},
        'kingdom': 'Plantae',
    },
    'wfo': {
        'mode': 'wfo_search',
        'search_url': 'https://www.worldfloraonline.org/search',
        'query_param': 'query',
    },
    'powo_ipni': {
        'mode': 'powo_search',
        'accepted_only': True,
        'per_page': 5,
    },
    'floraweb': {
        'mode': 'floraweb_search',
        'search_url': 'https://www.floraweb.de/php/taxoquery.php',
        'query_param': 'taxname',
    },
    'botanikus': {
        'mode': 'search_query_passthrough',
    },
    'naturadb': {
        'mode': 'naturadb_search',
        'search_url': 'https://www.naturadb.de/suche',
        'query_param': 'query',
    },
    'mein_schoener_garten': {
        'mode': 'mein_schoener_garten_search',
        'search_url': 'https://www.mein-schoener-garten.de/suche',
        'query_param': 'search_api_fulltext',
    },
}


HTML_SEARCH_MODES = {'wfo_search', 'floraweb_search', 'naturadb_search', 'mein_schoener_garten_search'}
RESOLVERS_BY_MODE = {
    'gbif_species_match': GbifSpeciesMatchResolver(),
    'powo_search': PowoResolver(),
    'wfo_search': WfoResolver(),
    'floraweb_search': FlorawebResolver(),
    'naturadb_search': NaturadbResolver(),
    'mein_schoener_garten_search': MeinSchoenerGartenResolver(),
}


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
    resolver = dict(TAXONOMY_ID_RESOLVER_CONFIG.get(catalog.key) or {'mode': 'none'})
    if resolver.get('mode') not in HTML_SEARCH_MODES:
        return resolver

    template = (catalog.search_url_template or '').strip()
    if not template:
        return resolver

    parsed = urlsplit(template)
    if not parsed.scheme or not parsed.netloc:
        return resolver

    query_param = None
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if value == '{q}':
            query_param = key
            break

    if query_param:
        resolver['query_param'] = query_param
    resolver['search_url'] = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
    return resolver


def resolve_taxonomy_id_for_catalog(catalog_key, scientific_name, resolver=None):
    resolver = resolver or dict(TAXONOMY_ID_RESOLVER_CONFIG.get(catalog_key) or {'mode': 'none'})
    mode = resolver.get('mode')
    if mode == 'search_query_passthrough':
        return (scientific_name or '').strip() or None
    taxonomy_resolver = RESOLVERS_BY_MODE.get(mode)
    if not taxonomy_resolver:
        return None
    return taxonomy_resolver.suggest_id(ResolverRequest(catalog_key, scientific_name, resolver))


def resolve_for_catalog(catalog, scientific_name):
    resolver_config = resolver_config_for_catalog(catalog)
    mode = resolver_config.get('mode')
    if mode == 'none':
        return ResolverResult(catalog.key, unavailable=True)

    request = ResolverRequest(catalog.key, scientific_name, resolver_config)
    if mode == 'search_query_passthrough':
        return ResolverResult(
            catalog.key,
            taxonomy_id=(scientific_name or '').strip() or None,
            external_call=ExternalCall(catalog=catalog.key, url=None, query={'q': scientific_name}),
        )

    resolver = RESOLVERS_BY_MODE.get(mode)
    if not resolver:
        return ResolverResult(catalog.key, unavailable=True)

    return ResolverResult(
        catalog.key,
        taxonomy_id=resolver.suggest_id(request),
        external_call=resolver.external_call(request),
    )


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
    resolver = dict(TAXONOMY_ID_RESOLVER_CONFIG.get(catalog_key) or {'mode': 'none'})
    mode = resolver.get('mode')
    if mode == 'search_query_passthrough':
        return None
    taxonomy_resolver = RESOLVERS_BY_MODE.get(mode)
    if not taxonomy_resolver:
        return None
    request = ResolverRequest(catalog_key, '', resolver)
    call = taxonomy_resolver.external_call(request)
    return call.url if call else None
