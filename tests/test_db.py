"""Tests for db.py using in-memory SQLite."""

import os
import tempfile
import pytest
from db import Database


@pytest.fixture
def db():
    """Create temporary file database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        yield Database(path)
    finally:
        for f in [path, f"{path}-wal", f"{path}-shm"]:
            if os.path.exists(f):
                os.unlink(f)


class TestSchema:
    def test_tables_created(self, db):
        tables = db.query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        table_names = {t["name"] for t in tables}
        assert "stock_prices" in table_names
        assert "watched_stocks" in table_names
        assert "predictions" in table_names
        assert "model_params" in table_names
        assert "telegram_messages" in table_names
        assert "pending_actions" in table_names

    def test_integrity(self, db):
        assert db.check_integrity() is True


class TestWatchlist:
    def test_add_stock(self, db):
        db.add_stock("005930", name="삼성전자", country="KR")
        stocks = db.get_watched_stocks()
        assert len(stocks) == 1
        assert stocks[0]["ticker"] == "005930"
        assert stocks[0]["name"] == "삼성전자"

    def test_remove_stock(self, db):
        db.add_stock("005930")
        db.remove_stock("005930")
        stocks = db.get_watched_stocks()
        assert len(stocks) == 0

    def test_filter_by_country(self, db):
        db.add_stock("005930", country="KR")
        db.add_stock("NVDA", country="US")
        kr = db.get_watched_stocks(country="KR")
        us = db.get_watched_stocks(country="US")
        assert len(kr) == 1
        assert len(us) == 1

    def test_duplicate_ignored(self, db):
        db.add_stock("005930")
        db.add_stock("005930")  # Should be ignored (INSERT OR IGNORE)
        stocks = db.get_watched_stocks()
        assert len(stocks) == 1


class TestPrices:
    def test_save_and_retrieve(self, db):
        db.save_stock_prices([{
            "timestamp": "2026-03-31T10:00:00",
            "ticker": "005930",
            "price": 54200,
            "volume": 1000000,
            "interval": "realtime",
        }])
        row = db.get_latest_price("005930")
        assert row is not None
        assert row["price"] == 54200

    def test_price_history(self, db):
        for i in range(5):
            db.save_stock_prices([{
                "timestamp": f"2026-03-{25+i}T10:00:00",
                "ticker": "005930",
                "price": 54000 + i * 100,
                "interval": "daily",
            }])
        history = db.get_price_history("005930", interval="daily", days=30)
        assert len(history) == 5


class TestTelegram:
    def test_save_and_retrieve_messages(self, db):
        db.save_message(1, "12345", "user", "삼전 얼마야?")
        db.save_message(2, "12345", "bot", "54,200원입니다")
        msgs = db.get_recent_messages("12345", limit=10)
        assert len(msgs) == 2

    def test_reply_tracking(self, db):
        db.save_message(1, "12345", "user", "hello", reply_to=None)
        db.save_message(2, "12345", "bot", "hi",
                        context_type="greeting", context_ref="1")
        msg = db.get_message_by_telegram_id(2)
        assert msg is not None
        assert msg["context_type"] == "greeting"


class TestPendingActions:
    def test_create_and_retrieve(self, db):
        db.create_pending_action("12345", "add_stock",
                                  {"ticker": "005930"}, "삼성전자 추가")
        action = db.get_pending_action("12345")
        assert action is not None
        assert action["action_type"] == "add_stock"

    def test_resolve(self, db):
        db.create_pending_action("12345", "add_stock",
                                  {"ticker": "005930"}, "test")
        action = db.get_pending_action("12345")
        db.resolve_pending_action(action["id"], "approved")
        # Should no longer be pending
        assert db.get_pending_action("12345") is None


class TestMaintenance:
    def test_table_counts(self, db):
        counts = db.table_counts()
        assert isinstance(counts, dict)
        assert "stock_prices" in counts
        assert counts["stock_prices"] == 0
