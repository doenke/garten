import unittest
from unittest.mock import Mock, patch

from app.taxonomy.resolvers.base import ExternalCall
from app.taxonomy.resolvers.http import execute_external_call, fetch_json, fetch_text


class ExternalCallHttpExecutionTest(unittest.TestCase):
    def test_execute_external_call_uses_call_description_and_defaults(self):
        call = ExternalCall(catalog='gbif', url='https://example.test/api', query={'q': 'Phlox'})
        response = Mock()
        response.raise_for_status = Mock()

        with patch('app.taxonomy.resolvers.http.requests.get', return_value=response) as requests_get:
            result = execute_external_call(call, headers={'Accept': 'application/json'})

        self.assertIs(result, response)
        requests_get.assert_called_once_with(
            'https://example.test/api',
            params={'q': 'Phlox'},
            headers={'User-Agent': 'garten-taxonomy-resolver/1.0', 'Accept': 'application/json'},
            timeout=8,
        )
        response.raise_for_status.assert_called_once_with()

    def test_fetch_json_and_text_delegate_to_execute_external_call(self):
        call = ExternalCall(catalog='html_search', url='https://example.test/search', query={'q': 'Phlox'})
        json_response = Mock(content=b'{"ok": true}')
        json_response.json.return_value = {'ok': True}
        text_response = Mock(text='<html></html>')

        with patch('app.taxonomy.resolvers.http.execute_external_call', side_effect=[json_response, text_response]) as execute:
            self.assertEqual(fetch_json(call), {'ok': True})
            self.assertEqual(fetch_text(call), '<html></html>')

        self.assertEqual(execute.call_args_list[0].kwargs['headers'], {'Accept': 'application/json'})
        self.assertEqual(execute.call_args_list[1].kwargs['headers'], {'Accept': 'text/html,application/xhtml+xml'})


if __name__ == '__main__':
    unittest.main()
