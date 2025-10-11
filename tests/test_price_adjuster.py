from datetime import datetime, timedelta

from wallapop_auto_adjust.config import ConfigManager
from wallapop_auto_adjust.price_adjuster import PriceAdjuster


def make_config(tmp_path, delay_days=1):
    cfg = ConfigManager(config_path=str(tmp_path / "products_config.json"))
    cfg.config = {"products": {}, "settings": {"delay_days": delay_days}}
    return cfg


def test_calculate_new_price_keep(tmp_path):
    cfg = make_config(tmp_path)
    pa = PriceAdjuster(wallapop_client=None, config_manager=cfg)

    assert pa.calculate_new_price(10.0, "keep") == 10.0


def test_calculate_new_price_multiplier_and_rounding(tmp_path):
    cfg = make_config(tmp_path)
    pa = PriceAdjuster(wallapop_client=None, config_manager=cfg)

    assert pa.calculate_new_price(10.0, 1.1) == 11.0
    assert pa.calculate_new_price(10.01, 1.005) == 10.06  # 10.06005 → 10.06


def test_calculate_new_price_minimum_floor(tmp_path):
    cfg = make_config(tmp_path)
    pa = PriceAdjuster(wallapop_client=None, config_manager=cfg)

    assert pa.calculate_new_price(1.2, 0.5) == 1.0  # below €1 floors to €1


def test_should_update_price_delay_not_met(tmp_path):
    cfg = make_config(tmp_path, delay_days=1)
    product_id = "p1"
    now_iso = datetime.now().astimezone().isoformat()
    cfg.config["products"][product_id] = {
        "name": "Test",
        "adjustment": "keep",
        "last_modified": now_iso,
    }

    pa = PriceAdjuster(wallapop_client=None, config_manager=cfg)
    assert pa.should_update_price(product_id) is False


def test_should_update_price_delay_met(tmp_path):
    cfg = make_config(tmp_path, delay_days=1)
    product_id = "p2"
    old_iso = (datetime.now().astimezone() - timedelta(days=2)).isoformat()
    cfg.config["products"][product_id] = {
        "name": "Test",
        "adjustment": "keep",
        "last_modified": old_iso,
    }

    pa = PriceAdjuster(wallapop_client=None, config_manager=cfg)
    assert pa.should_update_price(product_id) is True


def test_adjust_product_price_skips_reserved(tmp_path):
    cfg = make_config(tmp_path, delay_days=0)
    product_id = "pres"
    cfg.config["products"][product_id] = {
        "name": "Reserved Item",
        "adjustment": 0.9,
    }

    class DummyClient:
        def __init__(self):
            self.called = False

        def update_product_price(self, *_args, **_kwargs):
            self.called = True
            return True

    client = DummyClient()
    pa = PriceAdjuster(wallapop_client=client, config_manager=cfg)

    product = {
        "id": product_id,
        "name": "Reserved Item",
        "price": 10.0,
        "status": "reserved",
        "reserved": True,
        "flags": {"reserved": True},
    }

    result = pa.adjust_product_price(product)

    assert result is False
    assert client.called is False


def test_adjust_product_price_warns_on_unknown_flag(tmp_path, capsys, monkeypatch):
    cfg = make_config(tmp_path, delay_days=0)
    product_id = "pf"
    cfg.config["products"][product_id] = {
        "name": "Flagged Item",
        "adjustment": 0.9,
    }

    pa = PriceAdjuster(wallapop_client=None, config_manager=cfg)
    monkeypatch.setattr(
        pa,
        "get_user_adjustment",
        lambda *args, **kwargs: "keep",
        raising=False,
    )

    product = {
        "id": product_id,
        "name": "Flagged Item",
        "price": 12.0,
        "status": "available",
        "flags": {"mystery_flag": True},
    }

    pa.adjust_product_price(product)
    out = capsys.readouterr().out
    assert "mystery_flag" in out


def test_adjust_product_price_warns_on_unknown_status(tmp_path, capsys, monkeypatch):
    cfg = make_config(tmp_path, delay_days=0)
    product_id = "ps"
    cfg.config["products"][product_id] = {
        "name": "Status Item",
        "adjustment": 0.9,
    }

    pa = PriceAdjuster(wallapop_client=None, config_manager=cfg)
    monkeypatch.setattr(
        pa,
        "get_user_adjustment",
        lambda *args, **kwargs: "keep",
        raising=False,
    )

    product = {
        "id": product_id,
        "name": "Status Item",
        "price": 8.0,
        "status": "stalled",
        "flags": {},
    }

    pa.adjust_product_price(product)
    out = capsys.readouterr().out
    assert "stalled" in out
