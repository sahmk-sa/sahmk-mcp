import unittest
from unittest.mock import MagicMock, patch

from sahmk_mcp import server


class TestNewCuratedTools(unittest.TestCase):
    @patch("sahmk_mcp.server._get_client")
    def test_get_market_movers_gainers(self, mock_get_client):
        client = MagicMock()
        client.gainers.return_value.raw = {
            "index": "TASI",
            "count": 1,
            "gainers": [{"symbol": "2222"}],
        }
        mock_get_client.return_value = client

        result = server.get_market_movers("gainers", limit=10, index="TASI")

        self.assertEqual(
            result,
            {
                "type": "gainers",
                "index": "TASI",
                "count": 1,
                "items": [{"symbol": "2222"}],
            },
        )
        client.gainers.assert_called_once_with(limit=10, index="TASI")

    @patch("sahmk_mcp.server._get_client")
    def test_get_market_movers_volume(self, mock_get_client):
        client = MagicMock()
        client.volume_leaders.return_value.raw = {
            "index": "NOMU",
            "count": 2,
            "stocks": [{"symbol": "2222"}, {"symbol": "1120"}],
        }
        mock_get_client.return_value = client

        result = server.get_market_movers("volume", limit=5, index="NOMU")

        self.assertEqual(
            result,
            {
                "type": "volume",
                "index": "NOMU",
                "count": 2,
                "items": [{"symbol": "2222"}, {"symbol": "1120"}],
            },
        )
        client.volume_leaders.assert_called_once_with(limit=5, index="NOMU")

    def test_get_market_movers_invalid_type(self):
        with self.assertRaisesRegex(
            ValueError, "Must be one of: gainers, losers, volume, value"
        ):
            server.get_market_movers("unknown")

    def test_get_market_movers_invalid_limit(self):
        with self.assertRaisesRegex(ValueError, "Must be between 1 and 50"):
            server.get_market_movers("gainers", limit=0)

        with self.assertRaisesRegex(ValueError, "Must be between 1 and 50"):
            server.get_market_movers("gainers", limit=51)

        with self.assertRaisesRegex(ValueError, "Must be between 1 and 50"):
            server.get_market_movers("gainers", limit="10")

    @patch("sahmk_mcp.server._get_client")
    def test_get_sectors(self, mock_get_client):
        client = MagicMock()
        client.sectors.return_value.raw = {
            "index": "TASI",
            "count": 1,
            "sectors": [{"name": "Banks"}],
        }
        mock_get_client.return_value = client

        result = server.get_sectors(index="TASI")

        self.assertEqual(
            result,
            {"index": "TASI", "count": 1, "items": [{"name": "Banks"}]},
        )
        client.sectors.assert_called_once_with(index="TASI")

    @patch("sahmk_mcp.server._get_client")
    def test_get_financials(self, mock_get_client):
        client = MagicMock()
        client.financials.return_value.raw = {"symbol": "2222", "income_statements": []}
        mock_get_client.return_value = client

        result = server.get_financials("2222")

        self.assertEqual(result["symbol"], "2222")
        self.assertIn("income_statements", result)
        self.assertIn("balance_sheets", result)
        self.assertIn("cash_flows", result)
        client.financials.assert_called_once_with("2222")

    @patch("sahmk_mcp.server._get_client")
    def test_get_dividends(self, mock_get_client):
        client = MagicMock()
        client.dividends.return_value.raw = {"symbol": "2222", "history": []}
        mock_get_client.return_value = client

        result = server.get_dividends("2222")

        self.assertEqual(result["symbol"], "2222")
        self.assertIn("current_price", result)
        self.assertIn("trailing_12m_yield", result)
        self.assertIn("upcoming", result)
        self.assertIn("history", result)
        client.dividends.assert_called_once_with("2222")


if __name__ == "__main__":
    unittest.main()
