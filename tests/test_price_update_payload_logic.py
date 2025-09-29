import pytest
from unittest.mock import Mock

from wallapop_auto_adjust.wallapop_client import WallapopClient


@pytest.fixture()
def client():
    """Return a WallapopClient with network interactions mocked out."""

    client = WallapopClient()
    client._ensure_session = Mock()
    client.session = Mock()

    cookie_jar = Mock()
    cookie_jar.get = Mock(return_value="device-123")
    client.session.cookies = cookie_jar

    client._make_authenticated_request = Mock(
        return_value=Mock(status_code=204, text="")
    )
    return client


def test_payload_matches_har_structure(client):
    """The generated payload should match the structure observed in the Wallapop HAR capture."""

    mock_details = {
        "title": {"original": "Apple Pencil"},
        "description": {"original": "Second generation."},
        "taxonomy": [{"id": "123"}],
        "type_attributes": {
            "condition": {"value": "as_good_as_new"},
            "brand": {"value": "Apple"},
        },
        "location": {
            "latitude": 41.35,
            "longitude": 2.08,
            "approximated": False,
        },
        "shipping": {
            "user_allows_shipping": True,
            "max_weight_kg": 1,
        },
    }

    client.get_product_details = Mock(return_value=mock_details)

    result = client.update_product_price("item-123", 58.39)

    assert result is True
    client._make_authenticated_request.assert_called_once()

    call_args, call_kwargs = client._make_authenticated_request.call_args
    method, url = call_args[:2]
    payload = call_kwargs["json"]
    headers = call_kwargs["headers"]

    assert method == "PUT"
    assert "/api/v3/items/item-123" in url
    assert payload["category_leaf_id"] == "123"

    assert payload["attributes"]["title"] == "Apple Pencil"
    assert payload["attributes"]["condition"] == "good"
    assert payload["attributes"]["brand"] == "Apple"

    price = payload["price"]
    assert price["cash_amount"] == 58.39
    assert price["currency"] == "EUR"
    assert price["apply_discount"] is False

    assert payload["location"]["latitude"] == 41.35
    assert payload["delivery"]["allowed_by_user"] is True
    assert payload["delivery"]["max_weight_kg"] == 1

    assert headers["X-DeviceID"] == "device-123"
    assert headers["Accept"] == "application/vnd.upload-v2+json"


def test_condition_mapping_falls_back(client):
    """Conditions other than the special cases should pass through unchanged."""

    mock_details = {
        "title": "Product",
        "description": "Desc",
        "taxonomy": [{"id": "99"}],
        "type_attributes": {"condition": {"value": "has_given_it_all"}},
        "shipping": {},
        "location": {},
    }

    client.get_product_details = Mock(return_value=mock_details)

    client.update_product_price("item-abc", 10)

    _, call_kwargs = client._make_authenticated_request.call_args
    payload = call_kwargs["json"]

    assert payload["attributes"].get("condition") == "has_given_it_all"


def test_delivery_block_removed_when_empty(client):
    """The delivery block should be omitted if shipping data provides no useful info."""

    mock_details = {
        "title": "Product",
        "description": "Desc",
        "taxonomy": [{"id": "42"}],
        "type_attributes": {"condition": {"value": "good"}},
        "shipping": {},
        "location": {},
    }

    client.get_product_details = Mock(return_value=mock_details)

    client.update_product_price("item-empty", 99)

    _, call_kwargs = client._make_authenticated_request.call_args
    payload = call_kwargs["json"]

    assert "delivery" not in payload
