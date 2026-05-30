import re
from urllib.parse import unquote

from .html_search import HtmlSearchResolver, search_page_taxonomy_id


class MeinSchoenerGartenResolver(HtmlSearchResolver):
    key = 'mein_schoener_garten'
    mode = 'mein_schoener_garten_search'
    default_config_values = {
        'mode': 'mein_schoener_garten_search',
        'search_url': 'https://www.mein-schoener-garten.de/suche',
        'query_param': 'search_api_fulltext',
    }

    patterns = [
        r'https?://(?:www\.)?mein-schoener-garten\.de/pflanzen/([^"\'\s\?#/&]+)',
        r'/pflanzen/([^"\'\s\?#/&]+)',
        r'\/pflanzen\/([^\"\s\?#/&]+)',
        r'%2Fpflanzen%2F([^%\s\?#/&]+)',
    ]

    def suggest_id(self, request):
        raw_slug = search_page_taxonomy_id(request.scientific_name, request.config, self.patterns)
        if not raw_slug:
            return None
        slug = unquote(raw_slug).strip().strip('/').lower()
        slug = re.sub(r'[^a-z0-9\-]+', '-', slug)
        slug = re.sub(r'-{2,}', '-', slug).strip('-')
        return slug or None


def mein_schoener_garten_taxonomy_id(scientific_name, config):
    from .base import ResolverRequest

    return MeinSchoenerGartenResolver().suggest_id(ResolverRequest('mein_schoener_garten', scientific_name, config))
