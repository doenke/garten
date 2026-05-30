import re

from .html_search import html_decode_candidates, search_page_html


WFO_TAXON_PATTERNS = [
    r'/taxon/(wfo-[A-Za-z0-9\-]+)',
    r'worldfloraonline\.org/taxon/(wfo-[A-Za-z0-9\-]+)',
    r'\\/taxon\\/(wfo-[A-Za-z0-9\-]+)',
    r'worldfloraonline\\.org\\/taxon\\/(wfo-[A-Za-z0-9\-]+)',
    r'%2[fF]taxon%2[fF](wfo-[A-Za-z0-9\-]+)',
]

WFO_RESULT_TAXON_PATTERNS = [
    r'<a\b(?=[^>]*\bclass=["\\\']?[^>"\\\']*\bresult\b)(?=[^>]*\bhref=["\\\']?(?:https?://(?:www\.)?worldfloraonline\.org)?/taxon/(wfo-[A-Za-z0-9\-]+))[^>]*>',
    r'<a\b(?=[^>]*\bhref=["\\\']?(?:https?://(?:www\.)?worldfloraonline\.org)?/taxon/(wfo-[A-Za-z0-9\-]+))(?=[^>]*\bclass=["\\\']?[^>"\\\']*\bresult\b)[^>]*>',
]


def first_wfo_pattern_match(candidate_html, patterns):
    first_match = None
    for pattern in patterns:
        for match in re.finditer(pattern, candidate_html, flags=re.IGNORECASE):
            if first_match is None or match.start() < first_match.start():
                first_match = match
            break
    return first_match.group(1) if first_match else None


def extract_wfo_taxon_slug(page_html):
    candidates = html_decode_candidates(page_html)
    for candidate_html in candidates:
        result_slug = first_wfo_pattern_match(candidate_html, WFO_RESULT_TAXON_PATTERNS)
        if result_slug:
            return result_slug
    for candidate_html in candidates:
        fallback_slug = first_wfo_pattern_match(candidate_html, WFO_TAXON_PATTERNS)
        if fallback_slug:
            return fallback_slug
    return None


class WfoResolver:
    mode = 'wfo_search'

    def external_call(self, request):
        from .html_search import HtmlSearchResolver

        return HtmlSearchResolver().external_call(request)

    def suggest_id(self, request):
        page_html = search_page_html(request.scientific_name, request.config)
        if page_html is None:
            return None
        return extract_wfo_taxon_slug(page_html)


def wfo_taxonomy_id(scientific_name, config):
    from .base import ResolverRequest

    return WfoResolver().suggest_id(ResolverRequest('wfo', scientific_name, config))
