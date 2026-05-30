import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.taxonomy import registry
from app.taxonomy import service as taxonomy_service
from app.taxonomy.resolvers.base import ExternalCall, ResolverResult, TaxonomyResolver


class DummyResolver(TaxonomyResolver):
    key = 'dummy'

    def build_config(self, catalog):
        return {'catalog_key': catalog.key, 'mode': 'dummy'}

    def debug_call(self, scientific_name, config):
        return ExternalCall(catalog=config['catalog_key'], url='https://example.test/lookup', query={'q': scientific_name})

    def resolve(self, scientific_name, config):
        return ResolverResult(config['catalog_key'], taxonomy_id=scientific_name.upper(), external_call=self.debug_call(scientific_name, config))


class TaxonomyRegistryTest(unittest.TestCase):
    def test_registry_can_register_and_lookup_resolver_by_catalog(self):
        resolver = DummyResolver()
        registry.register_resolver(resolver)
        catalog = SimpleNamespace(key='dummy')

        self.assertIs(registry.get_resolver_for_catalog(catalog), resolver)
        self.assertIn(resolver, list(registry.iter_resolvers()))

    def test_static_resolvers_are_registered(self):
        registered_keys = {resolver.key for resolver in registry.iter_resolvers()}

        self.assertTrue({
            'gbif',
            'powo_ipni',
            'wfo',
            'floraweb',
            'naturadb',
            'mein_schoener_garten',
            'botanikus',
        }.issubset(registered_keys))

    def test_service_resolves_catalog_through_registry(self):
        resolver = DummyResolver()
        catalog = SimpleNamespace(key='dummy')

        with patch.object(registry, 'get_resolver_for_catalog', return_value=resolver):
            result = taxonomy_service.resolve_for_catalog(catalog, 'phlox paniculata')

        self.assertEqual(result.catalog_key, 'dummy')
        self.assertEqual(result.taxonomy_id, 'PHLOX PANICULATA')
        self.assertEqual(result.external_call.request_url, 'https://example.test/lookup?q=phlox+paniculata')

    def test_unknown_catalog_is_unavailable(self):
        catalog = SimpleNamespace(key='unknown')

        with patch.object(registry, 'get_resolver_for_catalog', return_value=None):
            result = taxonomy_service.resolve_for_catalog(catalog, 'phlox paniculata')

        self.assertTrue(result.unavailable)
        self.assertIsNone(result.taxonomy_id)


class TaxonomyResolverConfigTest(unittest.TestCase):
    def test_html_resolver_build_config_uses_catalog_search_template_query_param(self):
        from app.taxonomy.resolvers.floraweb import FlorawebResolver

        catalog = SimpleNamespace(
            key='floraweb',
            search_url_template='https://www.floraweb.de/php/taxoquery.php?taxname={q}',
        )

        config = FlorawebResolver().build_config(catalog)

        self.assertEqual(config['catalog_key'], 'floraweb')
        self.assertEqual(config['mode'], 'floraweb_search')
        self.assertEqual(config['search_url'], 'https://www.floraweb.de/php/taxoquery.php')
        self.assertEqual(config['query_param'], 'taxname')
        self.assertEqual(config['search_url_template'], catalog.search_url_template)

    def test_api_resolver_build_config_keeps_defaults_and_search_template(self):
        from app.taxonomy.resolvers.gbif import GbifResolver

        catalog = SimpleNamespace(
            key='gbif',
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
