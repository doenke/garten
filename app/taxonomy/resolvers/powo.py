import requests

from .base import ExternalCall, ResolverRequest, TaxonomyResolver, USER_AGENT, normalize_scientific_name_for_lookup, parse_json_response


class PowoResolver(TaxonomyResolver):
    key = 'powo_ipni'
    mode = 'powo_search'
    endpoint = 'https://powo.science.kew.org/api/2/search'

    def build_config(self, catalog):
        return {
            'catalog_key': catalog.key,
            'mode': self.mode,
            'accepted_only': True,
            'per_page': 5,
        }

    def external_call(self, request: ResolverRequest):
        params = {'q': request.scientific_name, 'perPage': request.config.get('per_page') or 5}
        if request.config.get('accepted_only', True):
            params['f'] = 'accepted:true'
        return ExternalCall(catalog=request.catalog_key, url=self.endpoint, query=params)

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
        results = payload.get('results') if isinstance(payload, dict) else None
        if not results:
            return None

        requested_name = normalize_scientific_name_for_lookup(request.scientific_name)
        requested_name = (requested_name or request.scientific_name or '').strip().lower()

        fallback_id = None
        for item in results:
            if not isinstance(item, dict):
                continue

            taxonomy_id = extract_powo_taxonomy_id(item.get('fqId') or item.get('id') or item.get('url'))
            if not taxonomy_id:
                continue
            if not fallback_id:
                fallback_id = taxonomy_id

            candidates = [item.get('name'), item.get('accepted_name'), item.get('species')]
            for candidate in candidates:
                normalized_candidate = normalize_scientific_name_for_lookup(candidate)
                normalized_candidate = (normalized_candidate or candidate or '').strip().lower()
                if normalized_candidate and normalized_candidate == requested_name:
                    return taxonomy_id

        return fallback_id


def extract_powo_taxonomy_id(raw_id):
    if not raw_id:
        return None
    raw_id = str(raw_id).strip()
    if not raw_id:
        return None
    if 'urn:lsid:ipni.org:names:' in raw_id:
        return raw_id
    if '/taxon/' in raw_id:
        return raw_id.rsplit('/taxon/', 1)[-1].strip('/')
    return raw_id


def powo_taxonomy_id(scientific_name, config):
    return PowoResolver().suggest_id(ResolverRequest('powo_ipni', scientific_name, config))
