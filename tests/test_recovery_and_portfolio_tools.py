import asyncio
import unittest
from unittest.mock import MagicMock, patch

from sahmk_mcp import server

PORTFOLIO_TOOLS = {
    "get_portfolios": ("List Portfolios", True, False),
    "get_portfolio": ("Get Portfolio", True, False),
    "create_portfolio": ("Create Portfolio", False, False),
    "get_portfolio_transactions": ("List Portfolio Transactions", True, False),
    "create_portfolio_transaction": ("Create Portfolio Transaction", False, False),
    "set_portfolio_holdings": ("Set Portfolio Holdings", False, True),
    "reverse_portfolio_transaction": ("Reverse Portfolio Transaction", False, True),
    "get_portfolio_summary": ("Get Portfolio Summary", True, False),
    "get_portfolio_performance": ("Get Portfolio Performance", True, False),
}


def _list_tools():
    lister = getattr(server.mcp, "list_tools", None) or server.mcp.get_tools
    tools = asyncio.run(lister())
    if isinstance(tools, dict):
        tools = list(tools.values())
    return {tool.name: tool for tool in tools}


class TestHistoricalIntervals(unittest.TestCase):
    @patch("sahmk_mcp.server._get_client")
    def test_accepts_canonical_and_alias_intervals(self, mock_get_client):
        client = MagicMock()
        client.historical.return_value.raw = {"symbol": "2222", "data": []}
        mock_get_client.return_value = client
        for interval in ("1min", "5min", "15min", "30min", "60min", "1d", "1w", "1mo", "30m", "60m", "1m"):
            server.get_historical(symbol="2222", interval=interval)
            self.assertEqual(client.historical.call_args.kwargs["interval"], interval)


class TestTradesRecovery(unittest.TestCase):
    @patch("sahmk_mcp.server._get_client")
    def test_passes_recovery_params_and_keeps_page(self, mock_get_client):
        client = MagicMock()
        client.trades.return_value.raw = {
            "symbol": "2222",
            "count": 1,
            "events": [{"trade_seq": 204506, "price": 26.6, "market_session": "REGULAR"}],
            "summary": {},
            "page": {"has_more": True, "next_cursor": "abc"},
        }
        mock_get_client.return_value = client

        result = server.get_trades(symbol="2222", limit=50, date="2026-11-22", after_seq=204505)

        client.trades.assert_called_once_with(
            "2222", limit=50, date="2026-11-22", after_seq=204505
        )
        self.assertEqual(result["page"]["next_cursor"], "abc")
        self.assertEqual(result["events"][0]["trade_seq"], 204506)

    @patch("sahmk_mcp.server._get_client")
    def test_cursor_is_passed(self, mock_get_client):
        client = MagicMock()
        client.trades.return_value.raw = {"symbol": "2222", "events": [], "summary": {}}
        mock_get_client.return_value = client
        server.get_trades(symbol="2222", date="2026-11-22", cursor=" abc ")
        client.trades.assert_called_once_with("2222", limit=None, date="2026-11-22", cursor="abc")

    def test_recovery_validation(self):
        cases = [
            ({"after_seq": 5}, "date"),
            ({"cursor": "abc"}, "date"),
            ({"date": "2026/11/22"}, "date"),
            ({"date": "2026-11-22", "after_seq": -1}, "after_seq"),
            ({"date": "2026-11-22", "after_seq": True}, "after_seq"),
        ]
        for kwargs, message in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, message):
                    server.get_trades(symbol="2222", **kwargs)


class TestPortfolioToolRegistry(unittest.TestCase):
    def test_tools_registered_with_hosted_annotations(self):
        tools = _list_tools()
        for name, (title, read_only, destructive) in PORTFOLIO_TOOLS.items():
            with self.subTest(tool=name):
                self.assertIn(name, tools)
                # Check the camelCase wire form clients receive.
                wire = tools[name].annotations.model_dump(by_alias=True, exclude_none=True)
                self.assertEqual(wire.get("title"), title)
                self.assertEqual(wire.get("readOnlyHint"), read_only)
                self.assertEqual(wire.get("idempotentHint"), read_only)
                self.assertEqual(wire.get("destructiveHint"), destructive)
                self.assertIs(wire.get("openWorldHint"), False)


class TestPortfolioTools(unittest.TestCase):
    def setUp(self):
        patcher = patch("sahmk_mcp.server._get_client")
        self.addCleanup(patcher.stop)
        self.client = MagicMock()
        patcher.start().return_value = self.client

    def test_reads(self):
        server.get_portfolios(workspace_id=3)
        self.client.portfolios.assert_called_once_with(workspace_id=3)
        server.get_portfolio(portfolio_id=7)
        self.client.portfolio.assert_called_once_with(7)
        server.get_portfolio_transactions(portfolio_id=7)
        self.client.portfolio_transactions.assert_called_once_with(7)
        server.get_portfolio_summary(portfolio_id=7)
        self.client.portfolio_summary.assert_called_once_with(7)
        server.get_portfolio_performance(portfolio_id=7, days=90)
        self.client.portfolio_performance.assert_called_once_with(7, days=90)

    def test_create_portfolio(self):
        server.create_portfolio(name="Core", description="Long term")
        self.client.create_portfolio.assert_called_once_with(
            "Core", description="Long term", workspace=None, metadata=None
        )
        with self.assertRaisesRegex(ValueError, "name is required"):
            server.create_portfolio(name="  ")

    def test_single_transaction(self):
        server.create_portfolio_transaction(
            portfolio_id=7,
            transaction_type="buy",
            amount_sar=2660,
            symbol="٢٢٢٢",
            quantity=100,
            unit_price_sar=26.6,
            idempotency_key="k1",
        )
        args, kwargs = self.client.create_portfolio_transaction.call_args
        self.assertEqual(args, (7, "buy", 2660))
        self.assertEqual(kwargs["symbol"], "2222")
        self.assertEqual(kwargs["idempotency_key"], "k1")

    def test_single_transaction_requires_type_and_amount(self):
        with self.assertRaisesRegex(ValueError, "transaction_type is required"):
            server.create_portfolio_transaction(portfolio_id=7, amount_sar=1)
        with self.assertRaisesRegex(ValueError, "amount_sar is required"):
            server.create_portfolio_transaction(portfolio_id=7, transaction_type="deposit")

    def test_batch_transactions(self):
        txs = [
            {"transaction_type": "DEPOSIT", "amount_sar": 1000},
            {"transaction_type": "fee", "amount_sar": 5},
        ]
        server.create_portfolio_transaction(
            portfolio_id=7, transactions=txs, batch_idempotency_key=" b1 "
        )
        self.client.create_portfolio_transactions.assert_called_once_with(
            7,
            [
                {"transaction_type": "deposit", "amount_sar": 1000},
                {"transaction_type": "fee", "amount_sar": 5},
            ],
            "b1",
        )

    def test_batch_rejects_mixed_fields_and_missing_key(self):
        txs = [{"transaction_type": "deposit", "amount_sar": 1}]
        with self.assertRaisesRegex(ValueError, "cannot include single-transaction fields"):
            server.create_portfolio_transaction(
                portfolio_id=7, transactions=txs, batch_idempotency_key="b", notes="x"
            )
        with self.assertRaisesRegex(ValueError, "batch_idempotency_key is required"):
            server.create_portfolio_transaction(portfolio_id=7, transactions=txs)
        with self.assertRaisesRegex(ValueError, "transaction_type"):
            server.create_portfolio_transaction(
                portfolio_id=7,
                transactions=[{"transaction_type": "gift", "amount_sar": 1}],
                batch_idempotency_key="b",
            )

    def test_set_holdings_dry_run_and_apply(self):
        holdings = [{"symbol": "2222", "quantity": 100, "avg_cost_sar": 26.0}]
        server.set_portfolio_holdings(
            portfolio_id=7, scope="partial", cash_policy="auto_fund", holdings=holdings
        )
        self.client.set_portfolio_holdings.assert_called_with(
            7, holdings, "partial", "auto_fund",
            dry_run=True, plan_token=None, expected_latest_transaction_id=None,
        )
        server.set_portfolio_holdings(
            portfolio_id=7, scope="partial", cash_policy="auto_fund", holdings=holdings,
            dry_run=False, plan_token="t", expected_latest_transaction_id=12,
        )
        self.client.set_portfolio_holdings.assert_called_with(
            7, holdings, "partial", "auto_fund",
            dry_run=False, plan_token="t", expected_latest_transaction_id=12,
        )

    def test_set_holdings_validation(self):
        with self.assertRaisesRegex(ValueError, "plan_token"):
            server.set_portfolio_holdings(
                portfolio_id=7, scope="full", cash_policy="require_cash", holdings=[], dry_run=False
            )
        with self.assertRaisesRegex(ValueError, "avg_cost_sar"):
            server.set_portfolio_holdings(
                portfolio_id=7, scope="full", cash_policy="require_cash",
                holdings=[{"symbol": "2222", "quantity": 1}],
            )

    def test_reverse(self):
        server.reverse_portfolio_transaction(portfolio_id=7, transaction_id=9, notes="typo")
        self.client.reverse_portfolio_transaction.assert_called_once_with(
            7, 9, notes="typo", metadata=None
        )

    def test_ids_must_be_positive_ints(self):
        for bad in (0, -1, True):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "portfolio_id"):
                    server.get_portfolio(portfolio_id=bad)


if __name__ == "__main__":
    unittest.main()
