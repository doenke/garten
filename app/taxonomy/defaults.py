"""Default configuration for taxonomy ID resolvers."""

from copy import deepcopy


TAXONOMY_ID_RESOLVER_CONFIG = {
    'gbif': {
        'mode': 'gbif_species_match',
        'prefer_statuses': {'ACCEPTED'},
        'kingdom': 'Plantae',
    },
    'powo_ipni': {
        'mode': 'powo_search',
        'accepted_only': True,
        'per_page': 5,
    },
    'wfo': {
        'mode': 'wfo_search',
        'search_url': 'https://www.worldfloraonline.org/search',
        'query_param': 'query',
    },
    'floraweb': {
        'mode': 'floraweb_search',
        'search_url': 'https://www.floraweb.de/php/taxoquery.php',
        'query_param': 'taxname',
    },
    'naturadb': {
        'mode': 'naturadb_search',
        'search_url': 'https://www.naturadb.de/suche',
        'query_param': 'query',
    },
    'mein_schoener_garten': {
        'mode': 'mein_schoener_garten_search',
        'search_url': 'https://www.mein-schoener-garten.de/suche',
        'query_param': 'search_api_fulltext',
    },
    'botanikus': {
        'mode': 'search_query_passthrough',
    },
}


def resolver_defaults(key):
    """Return an isolated copy of the default config for a resolver key."""
    return deepcopy(TAXONOMY_ID_RESOLVER_CONFIG.get(key) or {})
