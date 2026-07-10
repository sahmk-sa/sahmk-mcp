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
        with patch("sahmk.__version__", "0.11.0"):
            server._ensure_sahmk_min_version()

    def test_ensure_sahmk_min_version_blocks_old_version(self):
        with patch("sahmk.__version__", "0.10.9"):
            with self.assertRaisesRegex(
                SahmkError,
                r"sahmk>=0\.11\.0 is required for MCP-SDK compatibility",
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
    def test_get_quote_allows_equivalent_identifier_and_symbol(self, mock_get_client):
        client = MagicMock()
        client.quote.return_value.raw = {"symbol": "2222"}
        mock_get_client.return_value = client

        result = server.get_quote(identifier="٢٢٢٢", symbol="2222")

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
    def test_get_company_falls_back_to_batch_resolution(self, mock_get_client):
        client = MagicMock()

        def _company_side_effect(value):
            if value == "أرامكو":
                raise SahmkError(
                    "Unknown identifier '?': Stock symbol 'أرامكو' not found.",
                    status_code=404,
                    error_code="INVALID_SYMBOL",
                )
            company = MagicMock()
            company.raw = {"symbol": "2222", "name": "أرامكو السعودية"}
            return company

        client.company.side_effect = _company_side_effect
        client.quotes.return_value.raw = {
            "quotes": [{"symbol": "2222", "name": "شركة الزيت العربية السعودية"}],
            "count": 1,
            "resolution": {
                "requested_count": 1,
                "resolved_count": 1,
                "ambiguous": [],
                "not_found": [],
            },
        }
        mock_get_client.return_value = client

        result = server.get_company(identifier="أرامكو")

        self.assertEqual(result["symbol"], "2222")
        self.assertEqual(client.company.call_count, 2)
        client.company.assert_any_call("أرامكو")
        client.company.assert_any_call("2222")
        client.quotes.assert_called_once_with(["أرامكو"])

    @patch("sahmk_mcp.server._get_client")
    def test_get_company_numeric_not_found_does_not_resolve(self, mock_get_client):
        client = MagicMock()
        client.company.side_effect = SahmkError(
            "API error 404: Stock symbol '9999' not found.",
            status_code=404,
            error_code="SYMBOL_NOT_FOUND",
        )
        mock_get_client.return_value = client

        with self.assertRaises(SahmkError):
            server.get_company(identifier="9999")

        client.company.assert_called_once_with("9999")
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

    @patch("sahmk_mcp.server._get_client")
    def test_get_quotes_allows_equivalent_identifiers_and_symbols(
        self, mock_get_client
    ):
        client = MagicMock()
        client.quotes.return_value.raw = {"count": 2, "quotes": []}
        mock_get_client.return_value = client

        server.get_quotes(identifiers=["٢٢٢٢", "1120"], symbols=["2222", "1120"])

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

        result = server.get_financials(symbol="2222")

        self.assertEqual(result["symbol"], "2222")
        self.assertIn("income_statements", result)
        self.assertIn("balance_sheets", result)
        self.assertIn("cash_flows", result)
        self.assertNotIn("meta", result)
        client.financials.assert_called_once_with("2222")

    @patch("sahmk_mcp.server._get_client")
    def test_get_financials_strips_meta_if_backend_returns_it(self, mock_get_client):
        client = MagicMock()
        client.financials.return_value.raw = {
            "symbol": "2222",
            "income_statements": [],
            "meta": {"period": "quarterly"},
        }
        mock_get_client.return_value = client

        result = server.get_financials(symbol="2222")

        self.assertNotIn("meta", result)

    @patch("sahmk_mcp.server._get_client")
    def test_get_financials_optional_params_passthrough_period_precedence(
        self, mock_get_client
    ):
        client = MagicMock()
        client.financials.return_value.raw = {"symbol": "1120"}
        mock_get_client.return_value = client

        server.get_financials(
            symbol="1120",
            type="statements",
            period="quarterly",
            statement_period="annual",
            history="5y",
            metrics="extended",
            result="raw",
            include_partial=False,
        )

        client.financials.assert_called_once_with(
            "1120",
            type="statements",
            statement_period="quarterly",
            history="5y",
            metrics="extended",
            result="raw",
            include_partial=False,
        )

    @patch("sahmk_mcp.server._get_client")
    def test_get_financials_normalizes_arabic_indic_digits(self, mock_get_client):
        client = MagicMock()
        client.financials.return_value.raw = {"symbol": "2222", "income_statements": []}
        mock_get_client.return_value = client

        result = server.get_financials(symbol="٢٢٢٢")

        self.assertEqual(result["symbol"], "2222")
        client.financials.assert_called_once_with("2222")

    @patch("sahmk_mcp.server._get_client")
    def test_get_financials_falls_back_to_identifier_resolution(self, mock_get_client):
        client = MagicMock()

        def _financials_side_effect(value, **kwargs):
            if value == "أرامكو":
                raise SahmkError(
                    "Unknown identifier '?': Stock symbol 'أرامكو' not found.",
                    status_code=404,
                    error_code="INVALID_SYMBOL",
                )
            financials = MagicMock()
            financials.raw = {"symbol": "2222", "income_statements": []}
            return financials

        client.financials.side_effect = _financials_side_effect
        client.quotes.return_value.raw = {
            "quotes": [{"symbol": "2222", "name": "شركة الزيت العربية السعودية"}],
            "count": 1,
            "resolution": {
                "requested_count": 1,
                "resolved_count": 1,
                "ambiguous": [],
                "not_found": [],
            },
        }
        mock_get_client.return_value = client

        result = server.get_financials(symbol="أرامكو")

        self.assertEqual(result["symbol"], "2222")
        self.assertEqual(client.financials.call_count, 2)
        client.financials.assert_any_call("أرامكو")
        client.financials.assert_any_call("2222")
        client.quotes.assert_called_once_with(["أرامكو"])

    @patch("sahmk_mcp.server._get_client")
    def test_get_financials_falls_back_on_invalid_symbol_error_code(self, mock_get_client):
        client = MagicMock()

        def _financials_side_effect(value, **kwargs):
            if value == "الراجحي":
                raise SahmkError(
                    "API error 404: invalid symbol input.",
                    status_code=404,
                    error_code="INVALID_SYMBOL",
                )
            financials = MagicMock()
            financials.raw = {"symbol": "1120", "income_statements": []}
            return financials

        client.financials.side_effect = _financials_side_effect
        client.quotes.return_value.raw = {
            "quotes": [{"symbol": "1120", "name": "مصرف الراجحي"}],
            "count": 1,
            "resolution": {
                "requested_count": 1,
                "resolved_count": 1,
                "ambiguous": [],
                "not_found": [],
            },
        }
        mock_get_client.return_value = client

        result = server.get_financials(symbol="الراجحي")

        self.assertEqual(result["symbol"], "1120")
        self.assertEqual(client.financials.call_count, 2)
        client.financials.assert_any_call("الراجحي")
        client.financials.assert_any_call("1120")
        client.quotes.assert_called_once_with(["الراجحي"])

    @patch("sahmk_mcp.server._get_client")
    def test_get_financials_falls_back_via_companies_when_quotes_unknown(
        self, mock_get_client
    ):
        client = MagicMock()

        def _financials_side_effect(value, **kwargs):
            if value == "الحبيب":
                raise SahmkError(
                    "Unknown identifier '?': Stock symbol 'الحبيب' not found.",
                    status_code=404,
                    error_code="SYMBOL_NOT_FOUND",
                )
            financials = MagicMock()
            financials.raw = {"symbol": "4013", "income_statements": []}
            return financials

        client.financials.side_effect = _financials_side_effect
        client.quotes.side_effect = SahmkError(
            "Unknown identifier '?': Stock symbol 'الحبيب' not found.",
            status_code=404,
            error_code="SYMBOL_NOT_FOUND",
        )
        client.companies.return_value.raw = {
            "results": [
                {
                    "symbol": "4013",
                    "name": "د. سليمان الحبيب",
                    "name_en": "Dr. Sulaiman Al Habib",
                }
            ],
            "count": 1,
            "total": 1,
            "limit": 10,
            "offset": 0,
        }
        mock_get_client.return_value = client

        result = server.get_financials(symbol="الحبيب")

        self.assertEqual(result["symbol"], "4013")
        self.assertEqual(client.financials.call_count, 2)
        client.financials.assert_any_call("الحبيب")
        client.financials.assert_any_call("4013")
        client.quotes.assert_called_once_with(["الحبيب"])
        client.companies.assert_called_once_with(search="الحبيب", limit=10, offset=0)

    @patch("sahmk_mcp.server._get_client")
    def test_get_ratios_defaults(self, mock_get_client):
        client = MagicMock()
        client.get_ratios.return_value.raw = {"symbol": "1120", "ratios": {"roe": 0.15}}
        mock_get_client.return_value = client

        result = server.get_ratios(symbol="1120")

        self.assertEqual(result["symbol"], "1120")
        self.assertIn("ratios", result)
        self.assertIn("meta", result)
        client.get_ratios.assert_called_once_with(
            "1120",
            history="latest",
            period="annual",
            metrics="core",
        )

    @patch("sahmk_mcp.server._get_client")
    def test_get_ratios_filters_meta_to_customer_facing_fields(self, mock_get_client):
        client = MagicMock()
        client.get_ratios.return_value.raw = {
            "symbol": "1120",
            "ratios": [],
            "meta": {
                "period": "annual",
                "metrics": "core",
                "warnings": [],
                "applied_profile": "internal_profile",
                "plan": "pro",
                "source": "debug",
            },
        }
        mock_get_client.return_value = client

        result = server.get_ratios(symbol="1120")

        self.assertEqual(
            result["meta"],
            {"period": "annual", "metrics": "core", "warnings": []},
        )

    @patch("sahmk_mcp.server._get_client")
    def test_get_ratios_params(self, mock_get_client):
        client = MagicMock()
        client.get_ratios.return_value.raw = {"symbol": "1120", "ratios": {}, "meta": {}}
        mock_get_client.return_value = client

        server.get_ratios(
            symbol="1120",
            history="5y",
            period="quarterly",
            metrics="extended",
        )

        client.get_ratios.assert_called_once_with(
            "1120",
            history="5y",
            period="quarterly",
            metrics="extended",
        )

    @patch("sahmk_mcp.server._get_client")
    def test_get_ratios_falls_back_to_identifier_resolution(self, mock_get_client):
        client = MagicMock()

        def _get_ratios_side_effect(value, **kwargs):
            if value == "أرامكو":
                raise SahmkError(
                    "Unknown identifier '?': Stock symbol 'أرامكو' not found.",
                    status_code=404,
                    error_code="INVALID_SYMBOL",
                )
            ratios = MagicMock()
            ratios.raw = {"symbol": "2222", "ratios": {}, "meta": {}}
            return ratios

        client.get_ratios.side_effect = _get_ratios_side_effect
        client.quotes.return_value.raw = {
            "quotes": [{"symbol": "2222", "name": "شركة الزيت العربية السعودية"}],
            "count": 1,
            "resolution": {
                "requested_count": 1,
                "resolved_count": 1,
                "ambiguous": [],
                "not_found": [],
            },
        }
        mock_get_client.return_value = client

        result = server.get_ratios(symbol="أرامكو")

        self.assertEqual(result["symbol"], "2222")
        self.assertEqual(client.get_ratios.call_count, 2)
        client.get_ratios.assert_any_call(
            "أرامكو",
            history="latest",
            period="annual",
            metrics="core",
        )
        client.get_ratios.assert_any_call(
            "2222",
            history="latest",
            period="annual",
            metrics="core",
        )
        client.quotes.assert_called_once_with(["أرامكو"])

    @patch("sahmk_mcp.server._get_client")
    def test_get_ratios_falls_back_to_ratios_method(self, mock_get_client):
        client = MagicMock()
        del client.get_ratios
        client.ratios.return_value.raw = {"symbol": "1120", "ratios": [], "meta": {}}
        mock_get_client.return_value = client

        result = server.get_ratios(symbol="1120")

        self.assertEqual(result["symbol"], "1120")
        client.ratios.assert_called_once_with(
            "1120",
            history="latest",
            period="annual",
            metrics="core",
        )

    @patch("sahmk_mcp.server._get_client")
    def test_compare_symbols_list_symbols(self, mock_get_client):
        client = MagicMock()
        client.compare_symbols.return_value.raw = {
            "results": [{"symbol": "1120"}, {"symbol": "1180"}],
            "count": 2,
        }
        mock_get_client.return_value = client

        result = server.compare_symbols(symbols=["1120", "1180", "1010"])

        self.assertEqual(result["count"], 2)
        self.assertIn("results", result)
        self.assertIn("meta", result)
        client.compare_symbols.assert_called_once_with(
            ["1120", "1180", "1010"],
            metrics="core",
        )

    @patch("sahmk_mcp.server._get_client")
    def test_compare_symbols_filters_meta_to_customer_facing_fields(self, mock_get_client):
        client = MagicMock()
        client.compare_symbols.return_value.raw = {
            "results": [{"symbol": "1120"}],
            "count": 1,
            "meta": {
                "period": "quarterly",
                "metrics": "extended",
                "warnings": ["limited_history"],
                "applied_profile": "internal_profile",
                "plan": "pro",
                "source": {"trace_id": "123"},
            },
        }
        mock_get_client.return_value = client

        result = server.compare_symbols(symbols=["1120"])

        self.assertEqual(
            result["meta"],
            {
                "period": "quarterly",
                "metrics": "extended",
                "warnings": ["limited_history"],
            },
        )

    @patch("sahmk_mcp.server._get_client")
    def test_compare_symbols_comma_string_symbols(self, mock_get_client):
        client = MagicMock()
        client.compare_symbols.return_value.raw = {
            "results": [{"symbol": "1120"}, {"symbol": "1180"}, {"symbol": "1010"}],
            "count": 3,
        }
        mock_get_client.return_value = client

        server.compare_symbols(symbols="1120, 1180,1010")

        client.compare_symbols.assert_called_once_with(
            ["1120", "1180", "1010"],
            metrics="core",
        )

    @patch("sahmk_mcp.server._get_client")
    def test_compare_symbols_falls_back_to_identifier_resolution(self, mock_get_client):
        client = MagicMock()
        first_error = SahmkError(
            "Unknown identifier '?': Stock symbol 'أرامكو' not found.",
            status_code=404,
            error_code="INVALID_SYMBOL",
        )

        def _compare_side_effect(symbols, metrics="core"):
            if symbols == ["أرامكو", "1180"]:
                raise first_error
            return MagicMock(
                raw={
                    "results": [{"symbol": "2222"}, {"symbol": "1180"}],
                    "count": 2,
                }
            )

        client.compare_symbols.side_effect = _compare_side_effect
        client.quotes.return_value.raw = {
            "quotes": [{"symbol": "2222", "name": "شركة الزيت العربية السعودية"}],
            "count": 1,
            "resolution": {
                "requested_count": 1,
                "resolved_count": 1,
                "ambiguous": [],
                "not_found": [],
            },
        }
        mock_get_client.return_value = client

        result = server.compare_symbols(symbols=["أرامكو", "1180"])

        self.assertEqual(result["count"], 2)
        self.assertEqual(client.compare_symbols.call_count, 2)
        client.compare_symbols.assert_any_call(["أرامكو", "1180"], metrics="core")
        client.compare_symbols.assert_any_call(["2222", "1180"], metrics="core")
        client.quotes.assert_called_once_with(["أرامكو"])

    @patch("sahmk_mcp.server._get_client")
    def test_compare_symbols_falls_back_to_compare_method(self, mock_get_client):
        client = MagicMock()
        del client.compare_symbols
        client.compare.return_value.raw = {
            "results": [{"symbol": "1120"}, {"symbol": "1180"}],
            "count": 2,
        }
        mock_get_client.return_value = client

        result = server.compare_symbols(symbols=["1120", "1180"])

        self.assertEqual(result["count"], 2)
        client.compare.assert_called_once_with(["1120", "1180"], metrics="core")

    @patch("sahmk_mcp.server._get_client")
    def test_get_ratios_dynamic_ratio_keys_do_not_crash(self, mock_get_client):
        client = MagicMock()
        client.get_ratios.return_value.raw = {
            "symbol": "1120",
            "ratios": {
                "operating_margin": 0.24,
                "banking_specific_coverage": 1.8,
                "custom_sector_key_v2": {"trend": [1.1, 1.2]},
            },
        }
        mock_get_client.return_value = client

        result = server.get_ratios(symbol="1120")

        self.assertEqual(result["ratios"]["banking_specific_coverage"], 1.8)
        self.assertIn("custom_sector_key_v2", result["ratios"])

    @patch("sahmk_mcp.server._get_client")
    def test_analytics_plan_limit_error_passthrough(self, mock_get_client):
        client = MagicMock()
        plan_limit_error = SahmkError(
            "API error 402: plan limit exceeded",
            status_code=402,
            error_code="PLAN_LIMIT",
        )
        client.get_ratios.side_effect = plan_limit_error
        mock_get_client.return_value = client

        with self.assertRaises(SahmkError) as ctx:
            server.get_ratios(symbol="1120")

        self.assertEqual(ctx.exception.status_code, 402)
        self.assertEqual(ctx.exception.error_code, "PLAN_LIMIT")

    @patch("sahmk_mcp.server._get_client")
    def test_compare_symbols_error_passthrough(self, mock_get_client):
        client = MagicMock()
        api_error = SahmkError(
            "API error 400: invalid metrics",
            status_code=400,
            error_code="INVALID_PARAM",
        )
        client.compare_symbols.side_effect = api_error
        mock_get_client.return_value = client

        with self.assertRaises(SahmkError) as ctx:
            server.compare_symbols(symbols=["1120", "1180"], metrics="bad")

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.error_code, "INVALID_PARAM")

    @patch("sahmk_mcp.server._get_client")
    def test_get_dividends(self, mock_get_client):
        client = MagicMock()
        client.dividends.return_value.raw = {"symbol": "2222", "history": []}
        mock_get_client.return_value = client

        result = server.get_dividends(symbol="1120")

        self.assertEqual(result["symbol"], "2222")
        self.assertIn("current_price", result)
        self.assertIn("trailing_12m_yield", result)
        self.assertIn("upcoming", result)
        self.assertIn("history", result)
        client.dividends.assert_called_once_with("1120")

    @patch("sahmk_mcp.server._get_client")
    def test_get_dividends_falls_back_to_identifier_resolution(self, mock_get_client):
        client = MagicMock()

        def _dividends_side_effect(value):
            if value == "أرامكو":
                raise SahmkError(
                    "Unknown identifier '?': Stock symbol 'أرامكو' not found.",
                    status_code=404,
                    error_code="INVALID_SYMBOL",
                )
            dividends = MagicMock()
            dividends.raw = {"symbol": "2222", "history": []}
            return dividends

        client.dividends.side_effect = _dividends_side_effect
        client.quotes.return_value.raw = {
            "quotes": [{"symbol": "2222", "name": "شركة الزيت العربية السعودية"}],
            "count": 1,
            "resolution": {
                "requested_count": 1,
                "resolved_count": 1,
                "ambiguous": [],
                "not_found": [],
            },
        }
        mock_get_client.return_value = client

        result = server.get_dividends(symbol="أرامكو")

        self.assertEqual(result["symbol"], "2222")
        self.assertEqual(client.dividends.call_count, 2)
        client.dividends.assert_any_call("أرامكو")
        client.dividends.assert_any_call("2222")
        client.quotes.assert_called_once_with(["أرامكو"])

    @patch("sahmk_mcp.server._get_client")
    def test_get_historical_accepts_intraday_interval(self, mock_get_client):
        client = MagicMock()
        client.historical.return_value.raw = {"symbol": "1120", "historical": []}
        mock_get_client.return_value = client

        result = server.get_historical(
            symbol="1120",
            from_date="2026-01-01",
            to_date="2026-01-31",
            interval="60m",
        )

        self.assertEqual(result["symbol"], "1120")
        client.historical.assert_called_once_with(
            "1120",
            from_date="2026-01-01",
            to_date="2026-01-31",
            interval="60m",
        )

    @patch("sahmk_mcp.server._get_client")
    def test_get_historical_falls_back_to_identifier_resolution(self, mock_get_client):
        client = MagicMock()

        def _historical_side_effect(value, **kwargs):
            if value == "أرامكو":
                raise SahmkError(
                    "Unknown identifier '?': Stock symbol 'أرامكو' not found.",
                    status_code=404,
                    error_code="INVALID_SYMBOL",
                )
            historical = MagicMock()
            historical.raw = {"symbol": "2222", "historical": []}
            return historical

        client.historical.side_effect = _historical_side_effect
        client.quotes.return_value.raw = {
            "quotes": [{"symbol": "2222", "name": "شركة الزيت العربية السعودية"}],
            "count": 1,
            "resolution": {
                "requested_count": 1,
                "resolved_count": 1,
                "ambiguous": [],
                "not_found": [],
            },
        }
        mock_get_client.return_value = client

        result = server.get_historical(symbol="أرامكو", interval="1d")

        self.assertEqual(result["symbol"], "2222")
        self.assertEqual(client.historical.call_count, 2)
        client.historical.assert_any_call(
            "أرامكو", from_date=None, to_date=None, interval="1d"
        )
        client.historical.assert_any_call(
            "2222", from_date=None, to_date=None, interval="1d"
        )
        client.quotes.assert_called_once_with(["أرامكو"])

    def test_get_historical_rejects_invalid_interval(self):
        with self.assertRaisesRegex(
            ValueError,
            "Must be one of: '1d' \\(daily\\), '1w' \\(weekly\\), '1m' \\(monthly\\), '30m' \\(30-minute\\), or '60m' \\(60-minute\\)",
        ):
            server.get_historical(symbol="1120", interval="15m")


if __name__ == "__main__":
    unittest.main()
