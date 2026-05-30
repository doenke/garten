from .base import ExternalCall, ResolverResult, TaxonomyResolver


class SearchQueryPassthroughResolver(TaxonomyResolver):
    key = 'botanikus'
    mode = 'search_query_passthrough'

    def build_config(self, catalog):
        return {'catalog_key': catalog.key, 'mode': self.mode}

    def debug_call(self, scientific_name: str, config: dict):
        return ExternalCall(catalog=config.get('catalog_key') or self.key, url=None, query={'q': scientific_name})

    def resolve(self, scientific_name: str, config: dict):
        catalog_key = config.get('catalog_key') or self.key
        return ResolverResult(
            catalog_key,
            taxonomy_id=(scientific_name or '').strip() or None,
            external_call=self.debug_call(scientific_name, config),
        )

    def suggest_id(self, request):
        return (request.scientific_name or '').strip() or None
