import unittest
from unittest.mock import patch, MagicMock
from wb_api import WBClient

class TestWBClient(unittest.TestCase):
    @patch('requests.Session.get')
    def test_search_query_encoding(self, mock_get):
        # Mock the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "products": [
                    {
                        "id": 123,
                        "name": "Test Product",
                        "brand": "Test Brand",
                        "sizes": [{"price": {"product": 100000}}],
                        "reviewRating": 45,
                        "feedbacks": 100,
                        "supplier": "Test Supplier",
                        "supplierRating": 4.8,
                        "volume": 10
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        client = WBClient(token='test')
        results = client.search('джинсы')

        # Check if the query parameter is passed correctly without double encoding
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(kwargs['params']['query'], 'джинсы')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Test Product")

if __name__ == '__main__':
    unittest.main()
