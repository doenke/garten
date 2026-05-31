from urllib.parse import quote

from .base import ExternalCall, ResolverRequest, TaxonomyResolver, fetch_json, normalize_scientific_name_for_lookup


class GermanWikipediaResolver(TaxonomyResolver):
    key = 'wikipedia_de'
    mode = 'wikipedia_search'
    default_config_values = {
        'mode': 'wikipedia_search',
        'search_url': 'https://de.wikipedia.org/w/api.php',
        'api_url': 'https://de.wikipedia.org/w/api.php',
        'query_param': 'srsearch',
    }

    def external_call(self, request: ResolverRequest):
        return ExternalCall(
            catalog=request.catalog_key,
            url=request.config.get('api_url') or self.default_config_values['api_url'],
            query={
                'action': 'query',
                'list': 'search',
                'srsearch': request.scientific_name,
                'utf8': '1',
                'format': 'json',
            },
        )

    def suggest_id(self, request: ResolverRequest):
        search_terms = [(request.scientific_name or '').strip()]
        normalized = normalize_scientific_name_for_lookup(request.scientific_name)
        if normalized and normalized not in search_terms:
            search_terms.append(normalized)

        for term in search_terms:
            if not term:
                continue
            call = self.external_call(ResolverRequest(request.catalog_key, term, request.config))
            data = fetch_json(call)
            results = data.get('query', {}).get('search', []) if isinstance(data, dict) else []
            for item in results:
                title = (item.get('title') or '').strip()
                if title:
                    return quote(title.replace(' ', '_'), safe=':_()-,.%')
        return None
