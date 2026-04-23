import unittest
from unittest.mock import MagicMock, patch

from sahmk import SahmkError
from sahmk_mcp import server


class TestNewCuratedTools(unittest.TestCase):
    @patch("sahmk_mcp.server._get_client")
    def test_companies_list_serializes_query_params(self, mock_get_client):
        client = MagicMock()
        expected = {
            "results": [{"symbol": "2010", "name": "SABIC"}],
            "count": 1,
            "total": 1,
            "limit": 25,
            "offset": 50,
        }
        client.companies.return_value.raw = expected
        mock_get_client.return_value = client

        result = server.companies_list(
            search="sab",
            market="TASI",
            limit=25,
            offset=50,
        )

        self.assertEqual(result, expected)
        client.companies.assert_called_once_with(
            search="sab",
            market="TASI",
            limit=25,
            offset=50,
        )

    @patch("sahmk_mcp.server._get_client")
    def test_companies_list_normalizes_market_nomuc_alias(self, mock_get_client):
        client = MagicMock()
        client.companies.return_value.raw = {
            "results": [],
            "count": 0,
            "total": 0,
            "limit": 100,
            "offset": 0,
        }
        mock_get_client.return_value = client

        server.companies_list(market="nomuc")

        client.companies.assert_called_once_with(
            search=None,
            market="NOMU",
            limit=100,
            offset=0,
        )

    def test_companies_list_rejects_invalid_limit(self):
        with self.assertRaisesRegex(ValueError, "Invalid limit"):
            server.companies_list(limit=0)

        with self.assertRaisesRegex(ValueError, "Invalid limit"):
            server.companies_list(limit=-1)

    def test_companies_list_rejects_invalid_offset(self):
        with self.assertRaisesRegex(ValueError, "Invalid offset"):
            server.companies_list(offset=-1)

    def test_companies_list_rejects_invalid_market(self):
        with self.assertRaisesRegex(
            ValueError, "Invalid market: 'MAIN'. Must be one of: TASI, NOMU"
        ):
            server.companies_list(market="MAIN")

    @patch("sahmk_mcp.server._get_client")
    def test_companies_list_propagates_invalid_market_api_error(self, mock_get_client):
        client = MagicMock()
        error = SahmkError(
            "API error 400: invalid market",
            status_code=400,
            error_code="INVALID_MARKET",
        )
        response = MagicMock()
        response.json.return_value = {
            "error": {"code": "INVALID_MARKET", "message": "Invalid market"}
        }
        error.response = response
        client.companies.side_effect = error
        mock_get_client.return_value = client

        with self.assertRaises(SahmkError) as ctx:
            server.companies_list(market="NOMU")

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.error_code, "INVALID_MARKET")
        self.assertEqual(
            ctx.exception.response.json()["error"]["code"],
            "INVALID_MARKET",
        )

    @patch("sahmk_mcp.server._get_client")
    def test_companies_list_propagates_invalid_param_api_error(self, mock_get_client):
        client = MagicMock()
        error = SahmkError(
            "API error 400: invalid parameter",
            status_code=400,
            error_code="INVALID_PARAM",
        )
        response = MagicMock()
        response.json.return_value = {
            "error": {"code": "INVALID_PARAM", "message": "Invalid parameter"}
        }
        error.response = response
        client.companies.side_effect = error
        mock_get_client.return_value = client

        with self.assertRaises(SahmkError) as ctx:
            server.companies_list(limit=10, offset=0)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.error_code, "INVALID_PARAM")
        self.assertEqual(
            ctx.exception.response.json()["error"]["code"],
            "INVALID_PARAM",
        )

    @patch("sahmk_mcp.server._get_client")
    def test_companies_list_happy_path_response_passthrough(self, mock_get_client):
        client = MagicMock()
        expected = {
            "results": [{"symbol": "2222", "name": "Saudi Aramco"}],
            "count": 1,
            "total": 350,
            "limit": 100,
            "offset": 0,
        }
        client.companies.return_value.raw = expected
        mock_get_client.return_value = client

        result = server.companies_list(search="aramco")

        self.assertEqual(result, expected)

    @patch("sahmk_mcp.server._get_client")
    def test_companies_list_passthrough_when_sdk_returns_plain_dict(
        self, mock_get_client
    ):
        client = MagicMock()
        expected = {
            "results": [{"symbol": "1120", "name": "Al Rajhi Bank"}],
            "count": 1,
            "total": 350,
            "limit": 100,
            "offset": 0,
        }
        client.companies.return_value = expected
        mock_get_client.return_value = client

        result = server.companies_list(search="rajhi")

        self.assertEqual(result, expected)

    def test_ensure_sahmk_min_version_allows_supported_version(self):
        with patch("sahmk.__version__", "0.8.0"):
            server._ensure_sahmk_min_version()

    def test_ensure_sahmk_min_version_blocks_old_version(self):
        with patch("sahmk.__version__", "0.7.9"):
            with self.assertRaisesRegex(
                SahmkError,
                r"sahmk>=0\.8\.0 is required for symbol discovery and identifier-aware quote resolution",
            ):
                server._ensure_sahmk_min_version()

    @patch("sahmk_mcp.server._get_client")
    def test_get_quote_accepts_flexible_identifier(self, mock_get_client):
        client = MagicMock()
        client.quote.return_value.raw = {"symbol": "2222", "name": "أرامكو"}
        mock_get_client.return_value = client

        result = server.get_quote(identifier="أرامكو")

        self.assertEqual(result["symbol"], "2222")
        client.quote.assert_called_once_with("أرامكو")

    @patch("sahmk_mcp.server._get_client")
    def test_get_quote_accepts_legacy_symbol_key(self, mock_get_client):
        client = MagicMock()
        client.quote.return_value.raw = {"symbol": "2222"}
        mock_get_client.return_value = client

        result = server.get_quote(symbol="2222")

        self.assertEqual(result["symbol"], "2222")
        client.quote.assert_called_once_with("2222")

    @patch("sahmk_mcp.server._get_client")
    def test_get_quote_surfaces_ambiguity_with_candidates(self, mock_get_client):
        client = MagicMock()
        error = SahmkError(
            "API error 400: ambiguous identifier",
            status_code=400,
            error_code="AMBIGUOUS_IDENTIFIER",
        )
        response = MagicMock()
        response.json.return_value = {
            "error": {
                "code": "AMBIGUOUS_IDENTIFIER",
                "message": "ambiguous identifier",
                "details": {
                    "candidates": [
                        {"symbol": "2010", "name": "سابك"},
                        {"symbol": "2310", "name": "سبكيم"},
                    ]
                },
            }
        }
        error.response = response
        client.quote.side_effect = error
        mock_get_client.return_value = client

        with self.assertRaisesRegex(
            ValueError,
            "AMBIGUOUS_IDENTIFIER: 'ساب' matched multiple stocks",
        ):
            server.get_quote(identifier="ساب")

    @patch("sahmk_mcp.server._get_client")
    def test_get_quote_falls_back_to_batch_resolution(self, mock_get_client):
        client = MagicMock()
        client.quote.side_effect = SahmkError(
            "Unknown identifier '?': Stock symbol 'الراجحي' not found.",
            status_code=404,
            error_code="SYMBOL_NOT_FOUND",
        )
        client.quotes.return_value.raw = {
            "count": 1,
            "quotes": [{"symbol": "1120", "name": "الراجحي"}],
        }
        mock_get_client.return_value = client

        result = server.get_quote(identifier="الراجحي")

        self.assertEqual(result["symbol"], "1120")
        client.quote.assert_called_once_with("الراجحي")
        client.quotes.assert_called_once_with(["الراجحي"])

    @patch("sahmk_mcp.server._get_client")
    def test_get_quote_numeric_not_found_does_not_fallback_to_batch(
        self, mock_get_client
    ):
        client = MagicMock()
        client.quote.side_effect = SahmkError(
            "API error 404: Stock symbol '9999' not found.",
            status_code=404,
            error_code="SYMBOL_NOT_FOUND",
        )
        mock_get_client.return_value = client

        with self.assertRaises(SahmkError):
            server.get_quote(identifier="9999")

        client.quote.assert_called_once_with("9999")
        client.quotes.assert_not_called()

    @patch("sahmk_mcp.server._get_client")
    def test_get_quotes_accepts_flexible_identifiers(self, mock_get_client):
        client = MagicMock()
        client.quotes.return_value.raw = {"count": 2, "quotes": []}
        mock_get_client.return_value = client

        server.get_quotes(identifiers=["سابك", "كيان"])
        client.quotes.assert_called_once_with(["سابك", "كيان"])

    @patch("sahmk_mcp.server._get_client")
    def test_get_quotes_accepts_legacy_symbols_key(self, mock_get_client):
        client = MagicMock()
        client.quotes.return_value.raw = {"count": 2, "quotes": []}
        mock_get_client.return_value = client

        server.get_quotes(symbols=["2222", "1120"])
        client.quotes.assert_called_once_with(["2222", "1120"])

    def test_get_quotes_requires_identifiers(self):
        with self.assertRaisesRegex(ValueError, "At least one identifier is required"):
            server.get_quotes([])

    @patch("sahmk_mcp.server._get_client")
    def test_get_quotes_recovers_not_found_items_via_single_quote(self, mock_get_client):
        client = MagicMock()
        client.quotes.return_value.raw = {
            "quotes": [{"symbol": "1180", "name": "الأهلي"}],
            "count": 1,
            "resolution": {
                "requested_count": 4,
                "resolved_count": 1,
                "ambiguous": [],
                "not_found": [
                    {"input": "العثيم"},
                    {"input": "علم"},
                    {"input": "الإنماء"},
                ],
            },
        }

        def _quote_side_effect(value):
            if value == "علم":
                quote = MagicMock()
                quote.raw = {"symbol": "7203", "name": "علم"}
                return quote
            if value == "الإنماء":
                quote = MagicMock()
                quote.raw = {"symbol": "1150", "name": "الإنماء"}
                return quote
            raise SahmkError(
                f"API error 404: Stock symbol '{value}' not found.",
                status_code=404,
                error_code="SYMBOL_NOT_FOUND",
            )

        client.quote.side_effect = _quote_side_effect
        mock_get_client.return_value = client

        result = server.get_quotes(
            identifiers=["العثيم", "الأهلي", "علم", "الإنماء"]
        )

        self.assertEqual(result["count"], 3)
        self.assertEqual(result["resolution"]["resolved_count"], 3)
        self.assertEqual(result["resolution"]["not_found"], [{"input": "العثيم"}])
        symbols = {item["symbol"] for item in result["quotes"]}
        self.assertSetEqual(symbols, {"1180", "7203", "1150"})
        client.quotes.assert_called_once_with(["العثيم", "الأهلي", "علم", "الإنماء"])

    @patch("sahmk_mcp.server._get_client")
    def test_get_quotes_collects_ambiguous_fallback_items(self, mock_get_client):
        client = MagicMock()
        client.quotes.return_value.raw = {
            "quotes": [],
            "count": 0,
            "resolution": {
                "requested_count": 1,
                "resolved_count": 0,
                "ambiguous": [],
                "not_found": [{"input": "ساب"}],
            },
        }
        ambiguous_error = SahmkError(
            "API error 400: ambiguous identifier",
            status_code=400,
            error_code="AMBIGUOUS_IDENTIFIER",
        )
        response = MagicMock()
        response.json.return_value = {
            "error": {
                "code": "AMBIGUOUS_IDENTIFIER",
                "details": {
                    "candidates": [{"symbol": "2010"}, {"symbol": "2310"}],
                },
            }
        }
        ambiguous_error.response = response
        client.quote.side_effect = ambiguous_error
        mock_get_client.return_value = client

        result = server.get_quotes(identifiers=["ساب"])

        self.assertEqual(result["count"], 0)
        self.assertEqual(result["resolution"]["not_found"], [])
        self.assertEqual(
            result["resolution"]["ambiguous"],
            [{"input": "ساب", "candidates": ["2010", "2310"]}],
        )

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

        result = server.get_financials("أرامكو")

        self.assertEqual(result["symbol"], "2222")
        self.assertIn("income_statements", result)
        self.assertIn("balance_sheets", result)
        self.assertIn("cash_flows", result)
        client.financials.assert_called_once_with("أرامكو")

    @patch("sahmk_mcp.server._get_client")
    def test_get_dividends(self, mock_get_client):
        client = MagicMock()
        client.dividends.return_value.raw = {"symbol": "2222", "history": []}
        mock_get_client.return_value = client

        result = server.get_dividends("الراجحي")

        self.assertEqual(result["symbol"], "2222")
        self.assertIn("current_price", result)
        self.assertIn("trailing_12m_yield", result)
        self.assertIn("upcoming", result)
        self.assertIn("history", result)
        client.dividends.assert_called_once_with("الراجحي")


if __name__ == "__main__":
    unittest.main()
