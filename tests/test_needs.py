"""Tests pour le module needs.py"""

import json
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from src.needs import NeedItem, NeedsManager


@pytest.fixture
def temp_needs_file():
    """Crée un fichier temporaire pour les tests"""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    yield Path(path)
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def needs_manager(temp_needs_file):
    """Crée un NeedsManager avec fichier temporaire"""
    return NeedsManager(needs_path=temp_needs_file)


class TestNeedItem:
    """Tests pour NeedItem"""
    
    def test_create_basic(self):
        """Test création basique"""
        need = NeedItem(id="test-1", item="lait")
        assert need.item == "lait"
        assert need.quantity == 1.0
        assert need.priority == "normal"
        assert need.status == "pending"
    
    def test_create_full(self):
        """Test création avec tous les champs"""
        need = NeedItem(
            id="test-2",
            item="céréales",
            quantity=2,
            unit="boîtes",
            priority="high",
            added_by="Emma",
            notes="Cheerios de préférence"
        )
        assert need.item == "céréales"
        assert need.quantity == 2
        assert need.unit == "boîtes"
        assert need.priority == "high"
        assert need.added_by == "Emma"
        assert need.notes == "Cheerios de préférence"
    
    def test_to_dict(self):
        """Test sérialisation"""
        need = NeedItem(id="test-3", item="pain", quantity=1, priority="low")
        d = need.to_dict()
        assert d["id"] == "test-3"
        assert d["item"] == "pain"
        assert d["priority"] == "low"
    
    def test_from_dict(self):
        """Test désérialisation"""
        data = {
            "id": "test-4",
            "item": "beurre",
            "quantity": 1,
            "priority": "urgent"
        }
        need = NeedItem.from_dict(data)
        assert need.id == "test-4"
        assert need.item == "beurre"
        assert need.priority == "urgent"
    
    def test_format_line_basic(self):
        """Test formatage ligne simple"""
        need = NeedItem(id="1", item="lait")
        line = need.format_line()
        assert "lait" in line
    
    def test_format_line_with_quantity(self):
        """Test formatage avec quantité"""
        need = NeedItem(id="1", item="lait", quantity=2, unit="L")
        line = need.format_line()
        assert "lait" in line
        assert "2" in line
        assert "L" in line
    
    def test_format_line_urgent(self):
        """Test formatage urgent"""
        need = NeedItem(id="1", item="lait", priority="urgent")
        line = need.format_line()
        assert "🔴" in line
    
    def test_format_line_with_meta(self):
        """Test formatage avec métadonnées"""
        need = NeedItem(id="1", item="céréales", added_by="Emma", notes="Cheerios")
        line = need.format_line(include_meta=True)
        assert "Emma" in line
        assert "Cheerios" in line


class TestNeedsManager:
    """Tests pour NeedsManager"""
    
    def test_add_need_basic(self, needs_manager):
        """Test ajout basique"""
        need = needs_manager.add_need("lait")
        assert need.item == "lait"
        assert need.quantity == 1.0
        
        # Vérifier persistance
        needs = needs_manager.list_needs()
        assert len(needs) == 1
        assert needs[0].item == "lait"
    
    def test_add_need_with_options(self, needs_manager):
        """Test ajout avec options"""
        need = needs_manager.add_need(
            item="céréales",
            quantity=2,
            unit="boîtes",
            priority="high",
            added_by="Emma",
            notes="Cheerios SVP"
        )
        assert need.item == "céréales"
        assert need.quantity == 2
        assert need.unit == "boîtes"
        assert need.priority == "high"
        assert need.added_by == "Emma"
        assert need.notes == "Cheerios SVP"
    
    def test_add_need_increment_quantity(self, needs_manager):
        """Test que l'ajout du même item incrémente la quantité"""
        needs_manager.add_need("lait", quantity=1)
        need = needs_manager.add_need("lait", quantity=2)
        
        assert need.quantity == 3  # 1 + 2
        
        needs = needs_manager.list_needs()
        assert len(needs) == 1
    
    def test_add_need_increment_priority(self, needs_manager):
        """Test que la priorité monte mais ne descend pas"""
        needs_manager.add_need("lait", priority="normal")
        need = needs_manager.add_need("lait", priority="urgent")
        
        assert need.priority == "urgent"
        
        # La priorité ne doit pas descendre
        need = needs_manager.add_need("lait", priority="low")
        assert need.priority == "urgent"
    
    def test_remove_need(self, needs_manager):
        """Test suppression"""
        needs_manager.add_need("lait")
        needs_manager.add_need("pain")
        
        result = needs_manager.remove_need("lait")
        assert result is True
        
        needs = needs_manager.list_needs()
        assert len(needs) == 1
        assert needs[0].item == "pain"
    
    def test_remove_need_not_found(self, needs_manager):
        """Test suppression item inexistant"""
        result = needs_manager.remove_need("inexistant")
        assert result is False
    
    def test_list_needs_by_status(self, needs_manager):
        """Test filtrage par statut"""
        needs_manager.add_need("lait")
        needs_manager.add_need("pain")
        needs_manager.mark_done("lait")
        
        pending = needs_manager.list_needs(status="pending")
        assert len(pending) == 1
        assert pending[0].item == "pain"
        
        done = needs_manager.list_needs(status="done")
        assert len(done) == 1
        assert done[0].item == "lait"
    
    def test_list_needs_by_person(self, needs_manager):
        """Test filtrage par personne"""
        needs_manager.add_need("lait", added_by="Mathieu")
        needs_manager.add_need("céréales", added_by="Emma")
        
        emma_needs = needs_manager.list_needs(by="Emma")
        assert len(emma_needs) == 1
        assert emma_needs[0].item == "céréales"
    
    def test_mark_done(self, needs_manager):
        """Test marquer comme fait"""
        needs_manager.add_need("lait")
        
        need = needs_manager.mark_done("lait")
        assert need is not None
        assert need.status == "done"
    
    def test_mark_done_not_found(self, needs_manager):
        """Test marquer item inexistant"""
        result = needs_manager.mark_done("inexistant")
        assert result is None
    
    def test_mark_all_done(self, needs_manager):
        """Test marquer tous comme faits"""
        needs_manager.add_need("lait")
        needs_manager.add_need("pain")
        needs_manager.add_need("beurre")
        
        count = needs_manager.mark_all_done()
        assert count == 3
        
        pending = needs_manager.list_needs(status="pending")
        assert len(pending) == 0
        
        done = needs_manager.list_needs(status="done")
        assert len(done) == 3
    
    def test_clear_done(self, needs_manager):
        """Test nettoyer les complétés"""
        needs_manager.add_need("lait")
        needs_manager.add_need("pain")
        needs_manager.mark_done("lait")
        
        count = needs_manager.clear_done()
        assert count == 1
        
        needs = needs_manager.list_needs(status=None)  # Tous les statuts
        assert len(needs) == 1
        assert needs[0].item == "pain"
    
    def test_get_by_id(self, needs_manager):
        """Test récupération par ID"""
        need = needs_manager.add_need("lait")
        
        found = needs_manager.get_by_id(need.id)
        assert found is not None
        assert found.item == "lait"
    
    def test_get_by_item(self, needs_manager):
        """Test récupération par nom"""
        needs_manager.add_need("lait")
        
        found = needs_manager.get_by_item("lait")
        assert found is not None
        
        found = needs_manager.get_by_item("LAIT")  # Case insensitive
        assert found is not None
    
    def test_compile_list(self, needs_manager):
        """Test compilation de liste"""
        needs_manager.add_need("sirop", priority="urgent")
        needs_manager.add_need("lait")
        needs_manager.add_need("pain", priority="low")
        
        compiled = needs_manager.compile_list()
        
        assert "Liste d'épicerie" in compiled
        assert "URGENT" in compiled
        assert "sirop" in compiled
        assert "lait" in compiled
        assert "pain" in compiled
    
    def test_compile_list_empty(self, needs_manager):
        """Test compilation liste vide"""
        compiled = needs_manager.compile_list()
        assert "Aucun besoin" in compiled
    
    def test_to_local_cart_items(self, needs_manager):
        """Test conversion vers panier local"""
        needs_manager.add_need("lait", quantity=2)
        needs_manager.add_need("pain")
        
        items = needs_manager.to_local_cart_items()
        
        assert len(items) == 2
        assert any(i["query"] == "lait" and i["quantity"] == 2 for i in items)
        assert any(i["query"] == "pain" and i["quantity"] == 1 for i in items)
    
    def test_persistence(self, temp_needs_file):
        """Test que les données persistent entre instances"""
        # Première instance
        mgr1 = NeedsManager(needs_path=temp_needs_file)
        mgr1.add_need("lait")
        mgr1.add_need("pain")
        
        # Nouvelle instance
        mgr2 = NeedsManager(needs_path=temp_needs_file)
        needs = mgr2.list_needs()
        
        assert len(needs) == 2
        items = [n.item for n in needs]
        assert "lait" in items
        assert "pain" in items
    
    def test_priority_ordering(self, needs_manager):
        """Test que les besoins sont triés par priorité"""
        needs_manager.add_need("low_item", priority="low")
        needs_manager.add_need("normal_item", priority="normal")
        needs_manager.add_need("urgent_item", priority="urgent")
        needs_manager.add_need("high_item", priority="high")
        
        needs = needs_manager.list_needs()
        
        # urgent > high > normal > low
        assert needs[0].item == "urgent_item"
        assert needs[1].item == "high_item"
        assert needs[2].item == "normal_item"
        assert needs[3].item == "low_item"
