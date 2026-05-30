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


if __name__ == '__main__':
    unittest.main()
