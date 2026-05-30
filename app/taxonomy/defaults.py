from copy import deepcopy
from dataclasses import dataclass


@dataclass(frozen=True)
class StaticDatabaseCatalog:
    key: str
    label: str
    record_url_template: str
    search_url_template: str | None = None
    icon_url: str | None = None
    enabled: bool = True


DATABASE_CATALOGS = (
    StaticDatabaseCatalog(
        key='wfo',
        label='WFO',
        record_url_template='https://www.worldfloraonline.org/taxon/{id}',
        search_url_template='https://www.worldfloraonline.org/search?query={q}',
        icon_url='https://www.worldfloraonline.org/favicon.ico',
    ),
    StaticDatabaseCatalog(
        key='powo_ipni',
        label='POWO/IPNI-LSID',
        record_url_template='https://powo.science.kew.org/taxon/{id}',
        search_url_template='https://powo.science.kew.org/results?q={q}',
        icon_url='https://powo.science.kew.org/img/powo-favicon.ico',
    ),
    StaticDatabaseCatalog(
        key='gbif',
        label='GBIF',
        record_url_template='https://www.gbif.org/species/{id}',
        search_url_template='https://www.gbif.org/species/search?q={q}',
        icon_url='https://www.gbif.org/favicon.ico',
    ),
    StaticDatabaseCatalog(
        key='floraweb',
        label='FloraWeb',
        record_url_template='https://www.floraweb.de/taxon/{id}',
        search_url_template='https://www.floraweb.de/php/taxoquery.php?taxname={q}',
        icon_url='https://www.floraweb.de/favicon.ico',
    ),
    StaticDatabaseCatalog(
        key='naturadb',
        label='NaturaDB',
        record_url_template='https://www.naturadb.de/pflanzen/{id}',
        search_url_template='https://www.naturadb.de/suche?query={q}',
        icon_url='https://www.naturadb.de/favicon.ico',
    ),
    StaticDatabaseCatalog(
        key='mein_schoener_garten',
        label='Mein schöner Garten',
        record_url_template='https://www.mein-schoener-garten.de/pflanzen/{id}',
        search_url_template='https://www.mein-schoener-garten.de/suche?search_api_fulltext={q}',
        icon_url='https://www.mein-schoener-garten.de/favicon.ico',
    ),
)

_DATABASE_CATALOGS_BY_KEY = {catalog.key: catalog for catalog in DATABASE_CATALOGS}


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


def get_database_catalog(key):
    return _DATABASE_CATALOGS_BY_KEY.get(key)


def iter_database_catalogs():
    return iter(DATABASE_CATALOGS)


def database_catalogs():
    return list(DATABASE_CATALOGS)
