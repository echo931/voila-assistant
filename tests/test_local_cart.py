"""
Tests pour le module local_cart.
"""

import json
import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from local_cart import LocalCartManager, LocalCart, LocalCartItem


class TestLocalCartItem:
    """Tests pour LocalCartItem"""
    
    def test_create_basic(self):
        item = LocalCartItem(query="lait 2%")
        assert item.query == "lait 2%"
        assert item.quantity == 1
        assert item.product_id is None
        assert item.resolved_name is None
    
    def test_create_with_quantity(self):
        item = LocalCartItem(query="pain", quantity=3)
        assert item.quantity == 3
    
    def test_to_dict(self):
        item = LocalCartItem(query="bananes", quantity=2, product_id="abc123")
        d = item.to_dict()
        assert d["query"] == "bananes"
        assert d["quantity"] == 2
        assert d["product_id"] == "abc123"
    
    def test_from_dict(self):
        d = {"query": "pommes", "quantity": 5, "product_id": "xyz", "resolved_name": "Pommes Gala"}
        item = LocalCartItem.from_dict(d)
        assert item.query == "pommes"
        assert item.quantity == 5
        assert item.product_id == "xyz"
        assert item.resolved_name == "Pommes Gala"


class TestLocalCart:
    """Tests pour LocalCart"""
    
    def test_create_empty(self):
        cart = LocalCart()
        assert cart.items == []
        assert cart.created_at is not None
        assert cart.updated_at is not None
    
    def test_to_dict(self):
        cart = LocalCart(items=[LocalCartItem(query="test")])
        d = cart.to_dict()
        assert "items" in d
        assert len(d["items"]) == 1
        assert d["items"][0]["query"] == "test"
    
    def test_from_dict(self):
        d = {
            "items": [{"query": "lait", "quantity": 2}],
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00"
        }
        cart = LocalCart.from_dict(d)
        assert len(cart.items) == 1
        assert cart.items[0].query == "lait"


class TestLocalCartManager:
    """Tests pour LocalCartManager"""
    
    @pytest.fixture
    def temp_cart_file(self):
        """Crée un fichier temporaire pour le panier"""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test-cart.json"
    
    def test_create_manager(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        assert mgr.cart_path == temp_cart_file
    
    def test_empty_cart(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        assert mgr.is_empty()
        assert mgr.item_count() == 0
    
    def test_add_item(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        item = mgr.add_item("lait 2%", quantity=2)
        
        assert item.query == "lait 2%"
        assert item.quantity == 2
        assert not mgr.is_empty()
        assert mgr.item_count() == 1
    
    def test_add_item_increments_quantity(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        mgr.add_item("lait", quantity=1)
        mgr.add_item("lait", quantity=2)  # Same item, should add quantity
        
        assert mgr.item_count() == 1
        assert mgr.total_quantity() == 3
    
    def test_add_item_case_insensitive(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        mgr.add_item("Lait")
        mgr.add_item("LAIT")
        mgr.add_item("lait")
        
        assert mgr.item_count() == 1
        assert mgr.total_quantity() == 3
    
    def test_remove_item(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        mgr.add_item("lait")
        mgr.add_item("pain")
        
        assert mgr.remove_item("lait")
        assert mgr.item_count() == 1
        assert mgr.list_items()[0].query == "pain"
    
    def test_remove_item_not_found(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        mgr.add_item("lait")
        
        assert not mgr.remove_item("inexistant")
        assert mgr.item_count() == 1
    
    def test_clear(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        mgr.add_item("lait")
        mgr.add_item("pain")
        mgr.add_item("beurre")
        
        mgr.clear()
        assert mgr.is_empty()
        assert mgr.item_count() == 0
    
    def test_persistence(self, temp_cart_file):
        # Create and add items
        mgr1 = LocalCartManager(cart_path=temp_cart_file)
        mgr1.add_item("lait", quantity=2)
        mgr1.add_item("pain")
        
        # Create new manager pointing to same file
        mgr2 = LocalCartManager(cart_path=temp_cart_file)
        
        assert mgr2.item_count() == 2
        items = mgr2.list_items()
        assert items[0].query == "lait"
        assert items[0].quantity == 2
    
    def test_total_quantity(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        mgr.add_item("lait", quantity=2)
        mgr.add_item("pain", quantity=3)
        mgr.add_item("beurre", quantity=1)
        
        assert mgr.total_quantity() == 6
        assert mgr.item_count() == 3
    
    def test_format_summary_empty(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        summary = mgr.format_summary()
        assert "vide" in summary.lower()
    
    def test_format_summary_with_items(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        mgr.add_item("lait 2%", quantity=2)
        mgr.add_item("pain blanc")
        
        summary = mgr.format_summary()
        assert "lait 2%" in summary
        assert "×2" in summary
        assert "pain blanc" in summary
    
    def test_format_telegram(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        mgr.add_item("lait", quantity=2)
        
        html = mgr.format_telegram()
        assert "<b>" in html
        assert "lait" in html
    
    def test_format_json(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        mgr.add_item("lait")
        
        json_str = mgr.format_json()
        data = json.loads(json_str)
        assert "items" in data
        assert len(data["items"]) == 1


class TestLocalCartSync:
    """Tests pour la synchronisation (mocked)"""
    
    @pytest.fixture
    def temp_cart_file(self):
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test-cart.json"
    
    def test_sync_empty_cart(self, temp_cart_file):
        mgr = LocalCartManager(cart_path=temp_cart_file)
        result = mgr.sync_to_online(None)  # No cart manager needed for empty
        
        assert result["total_added"] == 0
        assert "vide" in result["message"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
