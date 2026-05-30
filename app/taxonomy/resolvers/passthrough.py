from .base import ExternalCall, ResolverRequest, ResolverResult, TaxonomyResolver


class SearchQueryPassthroughResolver(TaxonomyResolver):
    key = 'botanikus'
    mode = 'search_query_passthrough'

    def external_call(self, request: ResolverRequest):
        return ExternalCall(catalog=request.catalog_key, url=None, query={'q': request.scientific_name})

    def resolve(self, scientific_name: str, config: dict):
        request = ResolverRequest(config.get('catalog_key') or self.key, scientific_name, config)
        call = self.external_call(request)
        return ResolverResult(
            taxonomy_id=(scientific_name or '').strip() or None,
            external_calls=[call],
        )

    def suggest_id(self, request):
        return (request.scientific_name or '').strip() or None
