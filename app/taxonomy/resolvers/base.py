import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol
from urllib.parse import urlencode


USER_AGENT = 'garten-taxonomy-resolver/1.0'


@dataclass(frozen=True)
class ExternalCall:
    catalog: str
    url: Optional[str]
    query: Mapping[str, Any] = field(default_factory=dict)

    @property
    def request_url(self):
        if self.url and self.query:
            return f"{self.url}?{urlencode(self.query)}"
        return self.url

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


@dataclass(frozen=True)
class ResolverResult:
    catalog_key: str
    taxonomy_id: Optional[str] = None
    external_call: Optional[ExternalCall] = None
    unavailable: bool = False


class TaxonomyResolver(Protocol):
    mode: str

    def suggest_id(self, request: ResolverRequest) -> Optional[str]:
        ...

    def external_call(self, request: ResolverRequest) -> Optional[ExternalCall]:
        ...


def parse_json_response(response, logger=None):
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        if logger:
            logger.warning('taxonomy resolver non-json response from %s (status=%s)', response.url, response.status_code)
        return None


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
