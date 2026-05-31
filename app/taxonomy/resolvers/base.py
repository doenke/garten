import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional
from urllib.parse import urlencode

import requests

from ..url_templates import config_from_search_url_template


USER_AGENT = 'garten-taxonomy-resolver/1.0'
REQUEST_TIMEOUT = 8


@dataclass
class ExternalCall:
    catalog: str
    url: str | None
    query: dict[str, str] = field(default_factory=dict)
    request_url: str | None = None

    def __post_init__(self):
        self.query = {str(key): str(value) for key, value in dict(self.query or {}).items()}
        if self.request_url is None and self.url:
            self.request_url = f"{self.url}?{urlencode(self.query)}" if self.query else self.url

    def to_dict(self):
        return {
            'catalog': self.catalog,
            'url': self.url,
            'query': dict(self.query or {}),
            'request_url': self.request_url,
        }


@dataclass(frozen=True)
class ResolverRequest:
    catalog_key: str
    scientific_name: str
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class ResolverResult:
    taxonomy_id: str | None
    confidence: float | None = None
    external_calls: list[ExternalCall] = field(default_factory=list)
    error: str | None = None

    @property
    def external_call(self) -> ExternalCall | None:
        return self.external_calls[0] if self.external_calls else None

    @property
    def unavailable(self) -> bool:
        return self.error == 'unavailable'


class TaxonomyResolver:
    key: str
    mode: str = None
    default_config_values: Mapping[str, Any] = {}

    def supports(self, catalog) -> bool:
        return getattr(catalog, 'key', None) == self.key

    def default_config(self) -> dict:
        defaults = deepcopy(self.default_config_values)
        defaults.setdefault('mode', self.mode or self.key)
        return defaults

    def build_config(self, catalog) -> dict:
        config = config_from_search_url_template(
            getattr(catalog, 'search_url_template', None),
            self.default_config(),
        )
        config['catalog_key'] = catalog.key
        return config

    def debug_call(self, scientific_name: str, config: dict) -> Optional[ExternalCall]:
        return self.external_call(ResolverRequest(config.get('catalog_key') or self.key, scientific_name, config))

    def resolve(self, scientific_name: str, config: dict) -> ResolverResult:
        catalog_key = config.get('catalog_key') or self.key
        request = ResolverRequest(catalog_key, scientific_name, config)
        call = self.external_call(request)
        return ResolverResult(
            taxonomy_id=self.suggest_id(request),
            external_calls=[call] if call else [],
        )

    def suggest_id(self, request: ResolverRequest) -> Optional[str]:
        raise NotImplementedError

    def external_call(self, request: ResolverRequest) -> Optional[ExternalCall]:
        return None


def fetch_response(call: ExternalCall, accept: str):
    response = requests.get(
        call.url,
        params=call.query,
        headers={'Accept': accept, 'User-Agent': USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response


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
        response = fetch_response(call, accept)
    except requests.RequestException:
        return None
    return parse_json_response(response)


def fetch_text(call: ExternalCall, accept: str = 'text/html,application/xhtml+xml'):
    try:
        response = fetch_response(call, accept)
    except requests.RequestException:
        return None
    return response.text or ''


def normalize_scientific_name_for_lookup(scientific_name):
    value = re.sub(r'\s+', ' ', (scientific_name or '').strip())
    if not value:
        return None

    # remove cultivar designations and marketing names in quotes
    value = re.sub(r'"[^"]+"', '', value)
    value = re.sub(r"'[^']+'", '', value)
    value = re.sub(r'\s+', ' ', value).strip(' ,;:-')

    tokens = value.split()
    if len(tokens) < 2:
        return value or None

    def _is_species_token(token):
        return bool(re.fullmatch(r'[a-z][a-z\-]*', token))

    selected = [tokens[0]]
    for token in tokens[1:]:
        cleaned = token.strip(' ,;()')
        if not cleaned:
            continue
        if cleaned.lower() in {'x', '×'} or _is_species_token(cleaned):
            selected.append(cleaned)
            continue
        break

    if len(selected) < 2:
        return ' '.join(tokens[:2])
    return ' '.join(selected)
