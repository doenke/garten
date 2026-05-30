import unittest
from unittest.mock import patch

from app.taxonomy.resolvers.wfo import WfoResolver, extract_wfo_taxon_slug


class WfoTaxonomyExtractionTest(unittest.TestCase):
    def test_extract_wfo_taxon_slug_returns_first_wfo_taxon_link(self):
        page_html = """
            <a href="/taxon/not-a-wfo-id">Ignore non-WFO taxon slug</a>
            <a href="https://www.worldfloraonline.org/taxon/wfo-4000029286">First WFO hit</a>
            <a href="/taxon/wfo-0000000002">Second WFO hit</a>
            <script>{"url":"\\/taxon\\/wfo-0000000003"}</script>
            <a href="%2Ftaxon%2Fwfo-0000000004">Encoded WFO hit</a>
        """

        self.assertEqual(extract_wfo_taxon_slug(page_html), 'wfo-4000029286')

    def test_extract_wfo_taxon_slug_supports_escaped_and_url_encoded_links(self):
        self.assertEqual(
            extract_wfo_taxon_slug('{"url":"\\/taxon\\/wfo-4000029286"}'),
            'wfo-4000029286',
        )
        self.assertEqual(
            extract_wfo_taxon_slug('%2Ftaxon%2Fwfo-4000029286'),
            'wfo-4000029286',
        )

    def test_extract_wfo_taxon_slug_supports_json_escaped_result_links(self):
        page_html = r'''
            <a href=\"\/taxon\/wfo-4000029286\" class=\"result\"><h4 class=\"h4Results\"><strong><em>Phlox</em></strong></h4></a>
        '''

        self.assertEqual(extract_wfo_taxon_slug(page_html), 'wfo-4000029286')

    def test_extract_wfo_taxon_slug_prefers_search_result_links(self):
        page_html = """
            <div class="not-result">
                <a href="/taxon/wfo-4000029286">A different plant name</a>
            </div>
            <a class="result" href="/taxon/wfo-0000000002">Requested Name</a>
        """

        self.assertEqual(extract_wfo_taxon_slug(page_html), 'wfo-0000000002')


class WfoResolverTest(unittest.TestCase):
    def test_resolve_returns_first_search_result_slug_from_mocked_html_helper(self):
        page_html = """
            <div class="not-result">
                <a href="/taxon/wfo-4000029286">A different plant name</a>
            </div>
            <a class="result" href="/taxon/wfo-0000000002">Requested Name</a>
        """
        config = {
            'catalog_key': 'wfo',
            'search_url': 'https://www.worldfloraonline.org/search',
            'query_param': 'query',
        }

        with patch('app.taxonomy.resolvers.wfo.search_page_html', return_value=page_html) as search_page_html:
            result = WfoResolver().resolve('Requested Name', config)

        search_page_html.assert_called_once_with('Requested Name', config)
        self.assertEqual(result.taxonomy_id, 'wfo-0000000002')
        self.assertEqual(result.external_call.catalog, 'wfo')
        self.assertEqual(
            result.external_call.request_url,
            'https://www.worldfloraonline.org/search?query=Requested+Name',
        )

    def test_resolve_returns_no_taxonomy_id_when_html_helper_has_no_page(self):
        config = {
            'catalog_key': 'wfo',
            'search_url': 'https://www.worldfloraonline.org/search',
            'query_param': 'query',
        }

        with patch('app.taxonomy.resolvers.wfo.search_page_html', return_value=None):
            result = WfoResolver().resolve('Requested Name', config)

        self.assertIsNone(result.taxonomy_id)
        self.assertEqual(
            result.external_call.request_url,
            'https://www.worldfloraonline.org/search?query=Requested+Name',
        )


if __name__ == '__main__':
    unittest.main()
