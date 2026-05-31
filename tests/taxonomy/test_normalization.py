import unittest

from app.taxonomy.resolvers.base import normalize_single_segment_slug, normalize_url_slug
from app.taxonomy.resolvers.naturadb import normalize_naturadb_slug


class SlugNormalizationTest(unittest.TestCase):
    def test_normalize_single_segment_slug_decodes_and_sanitizes_url_slug(self):
        self.assertEqual(
            normalize_single_segment_slug('/Rote%20Sonnenhut!!/?utm_source=test'),
            'rote-sonnenhut',
        )

    def test_normalize_url_slug_can_preserve_normalized_path_segments(self):
        self.assertEqual(
            normalize_url_slug(r'/Stauden%20Mix/Echinacea\Purpurea/?utm_source=test#section', allow_path=True),
            'stauden-mix/echinacea/purpurea',
        )

    def test_normalize_naturadb_slug_delegates_to_path_aware_slug_normalization(self):
        self.assertEqual(
            normalize_naturadb_slug(r'/pflanzen%20abc/Echinacea\Purpurea/?x=1'),
            'pflanzen-abc/echinacea/purpurea',
        )


if __name__ == '__main__':
    unittest.main()
