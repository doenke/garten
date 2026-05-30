import requests

from .base import ExternalCall, ResolverRequest, TaxonomyResolver, USER_AGENT, parse_json_response


class GbifResolver(TaxonomyResolver):
    key = 'gbif'
    mode = 'gbif_species_match'
    endpoint = 'https://api.gbif.org/v1/species/match'
    default_config_values = {
        'mode': 'gbif_species_match',
        'prefer_statuses': {'ACCEPTED'},
        'kingdom': 'Plantae',
    }

    def external_call(self, request: ResolverRequest):
        return ExternalCall(
            catalog=request.catalog_key,
            url=self.endpoint,
            query={
                'name': request.scientific_name,
                'verbose': 'true',
                'kingdom': request.config.get('kingdom') or 'Plantae',
            },
        )

    def suggest_id(self, request: ResolverRequest):
        call = self.external_call(request)
        try:
            response = requests.get(
                self.endpoint,
                params=call.query,
                headers={'Accept': 'application/json', 'User-Agent': USER_AGENT},
                timeout=8,
            )
            response.raise_for_status()
        except requests.RequestException:
            return None

        payload = parse_json_response(response)
        if payload is None:
            return None
        usage_key = payload.get('usageKey')
        if not usage_key:
            return None

        prefer_statuses = request.config.get('prefer_statuses') or {'ACCEPTED'}
        status = (payload.get('status') or '').upper()
        if prefer_statuses and status and status not in prefer_statuses:
            accepted_key = payload.get('acceptedUsageKey')
            if accepted_key:
                return str(accepted_key)
        return str(usage_key)


def gbif_species_match_id(scientific_name, config):
    return GbifResolver().suggest_id(ResolverRequest('gbif', scientific_name, config))


GbifSpeciesMatchResolver = GbifResolver
