import unittest

from app.taxonomy.catalogs import DatabaseCatalogConfig
from app.taxonomy import registry
from app.taxonomy import resolvers  # noqa: F401 - import triggers static resolver registration
from app.taxonomy.resolvers.floraweb import FlorawebResolver
from app.taxonomy.resolvers.gbif import GbifResolver
from app.taxonomy.resolvers.mein_schoener_garten import MeinSchoenerGartenResolver
from app.taxonomy.resolvers.naturadb import NaturaDbResolver
from app.taxonomy.resolvers.passthrough import SearchQueryPassthroughResolver
from app.taxonomy.resolvers.powo import PowoResolver
from app.taxonomy.resolvers.wfo import WfoResolver


class TaxonomyRegistryTest(unittest.TestCase):
    def test_known_catalog_keys_get_expected_resolver(self):
        expected_resolvers = {
            'gbif': GbifResolver,
            'powo_ipni': PowoResolver,
            'wfo': WfoResolver,
            'floraweb': FlorawebResolver,
            'naturadb': NaturaDbResolver,
            'mein_schoener_garten': MeinSchoenerGartenResolver,
            'botanikus': SearchQueryPassthroughResolver,
        }

        for catalog_key, expected_resolver_class in expected_resolvers.items():
            with self.subTest(catalog_key=catalog_key):
                catalog = DatabaseCatalogConfig(
                    key=catalog_key,
                    label=catalog_key,
                    enabled=True,
                    record_url_template='https://example.test/{id}',
                )

                resolver = registry.get_resolver_for_catalog(catalog)

                self.assertIsInstance(resolver, expected_resolver_class)


class TaxonomyResolverConfigTest(unittest.TestCase):
    def test_html_resolver_build_config_uses_catalog_search_template_query_param(self):
        catalog = DatabaseCatalogConfig(
            key='floraweb',
            label='FloraWeb',
            enabled=True,
            record_url_template='https://example.test/{id}',
            search_url_template='https://www.floraweb.de/php/taxoquery.php?taxname={q}',
        )

        config = FlorawebResolver().build_config(catalog)

        self.assertEqual(config['catalog_key'], 'floraweb')
        self.assertEqual(config['mode'], 'floraweb_search')
        self.assertEqual(config['search_url'], 'https://www.floraweb.de/php/taxoquery.php')
        self.assertEqual(config['query_param'], 'taxname')
        self.assertEqual(config['search_url_template'], catalog.search_url_template)

    def test_api_resolver_build_config_keeps_defaults_and_search_template(self):
        catalog = DatabaseCatalogConfig(
            key='gbif',
            label='GBIF',
            enabled=True,
            record_url_template='https://example.test/{id}',
            search_url_template='https://www.gbif.org/species/search?q={q}',
        )

        config = GbifResolver().build_config(catalog)

        self.assertEqual(config['catalog_key'], 'gbif')
        self.assertEqual(config['mode'], 'gbif_species_match')
        self.assertEqual(config['prefer_statuses'], {'ACCEPTED'})
        self.assertEqual(config['kingdom'], 'Plantae')
        self.assertEqual(config['search_url_template'], catalog.search_url_template)


if __name__ == '__main__':
    unittest.main()
