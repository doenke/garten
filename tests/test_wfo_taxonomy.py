import unittest
from unittest.mock import patch

from app import views


class WfoTaxonomyExtractionTest(unittest.TestCase):
    def test_extract_wfo_taxon_slug_returns_first_wfo_taxon_link(self):
        page_html = """
            <a href="/taxon/not-a-wfo-id">Ignore non-WFO taxon slug</a>
            <a href="https://www.worldfloraonline.org/taxon/wfo-4000029286">First WFO hit</a>
            <a href="/taxon/wfo-0000000002">Second WFO hit</a>
            <script>{"url":"\\/taxon\\/wfo-0000000003"}</script>
            <a href="%2Ftaxon%2Fwfo-0000000004">Encoded WFO hit</a>
        """

        self.assertEqual(views._extract_wfo_taxon_slug(page_html), 'wfo-4000029286')

    def test_extract_wfo_taxon_slug_supports_escaped_and_url_encoded_links(self):
        self.assertEqual(
            views._extract_wfo_taxon_slug('{"url":"\\/taxon\\/wfo-4000029286"}'),
            'wfo-4000029286',
        )
        self.assertEqual(
            views._extract_wfo_taxon_slug('%2Ftaxon%2Fwfo-4000029286'),
            'wfo-4000029286',
        )

    def test_wfo_taxonomy_id_returns_first_wfo_slug_without_name_matching(self):
        page_html = """
            <div class="not-result">
                <a href="/taxon/wfo-4000029286">A different plant name</a>
            </div>
            <a class="result" href="/taxon/wfo-0000000002">Requested Name</a>
        """

        with patch.object(views, '_search_page_html', return_value=page_html):
            self.assertEqual(views._wfo_taxonomy_id('Requested Name', {}), 'wfo-4000029286')


if __name__ == '__main__':
    unittest.main()
