import html
import re
from urllib.parse import unquote

import requests

from .base import ExternalCall, ResolverRequest, TaxonomyResolver, USER_AGENT


def html_decode_candidates(page_html):
    candidates = []

    def _append_candidate(candidate):
        if candidate is None:
            return
        candidate = str(candidate)
        if candidate not in candidates:
            candidates.append(candidate)

    _append_candidate(page_html or '')
    for candidate in list(candidates):
        _append_candidate(html.unescape(candidate))
    for candidate in list(candidates):
        _append_candidate(unquote(candidate))
    for candidate in list(candidates):
        _append_candidate(candidate.replace('\\/', '/').replace('\\"', '"').replace("\\'", "'"))
    for candidate in list(candidates):
        _append_candidate(html.unescape(candidate))
        _append_candidate(unquote(candidate))
    return candidates


def extract_search_page_taxonomy_id(page_html, patterns):
    for candidate_html in html_decode_candidates(page_html):
        first_match = None
        for pattern in patterns:
            for match in re.finditer(pattern, candidate_html, flags=re.IGNORECASE):
                if first_match is None or match.start() < first_match.start():
                    first_match = match
                break
        if not first_match:
            continue
        taxonomy_id = (first_match.group(1) or '').strip().strip('/').strip()
        if taxonomy_id:
            return taxonomy_id
    return None


def search_page_taxonomy_id(scientific_name, config, patterns):
    page_html = search_page_html(scientific_name, config)
    if page_html is None:
        return None
    return extract_search_page_taxonomy_id(page_html, patterns)


def search_page_html(scientific_name, config):
    search_url = (config.get('search_url') or '').strip()
    query_param = (config.get('query_param') or 'q').strip()
    if not search_url:
        return None
    try:
        response = requests.get(
            search_url,
            params={query_param: scientific_name},
            headers={'Accept': 'text/html,application/xhtml+xml', 'User-Agent': USER_AGENT},
            timeout=8,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None
    return response.text or ''


class HtmlSearchResolver(TaxonomyResolver):
    key = None
    mode = None
    patterns = []

    def external_call(self, request: ResolverRequest):
        query_param = request.config.get('query_param') or 'q'
        return ExternalCall(
            catalog=request.catalog_key,
            url=request.config.get('search_url'),
            query={query_param: request.scientific_name},
        )

    def suggest_id(self, request: ResolverRequest):
        return search_page_taxonomy_id(request.scientific_name, request.config, self.patterns)
