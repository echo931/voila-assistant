"""Tests pour le module preferences.py"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from src.preferences import ProductRef, ProductPreference, PreferencesManager


@pytest.fixture
def temp_prefs_file():
    """Crée un fichier temporaire pour les tests"""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    yield Path(path)
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def prefs_manager(temp_prefs_file):
    """Crée un PreferencesManager avec fichier temporaire"""
    return PreferencesManager(prefs_path=temp_prefs_file)


class TestProductRef:
    """Tests pour ProductRef"""
    
    def test_create_basic(self):
        """Test création basique"""
        ref = ProductRef(name="Lactantia 2%")
        assert ref.name == "Lactantia 2%"
        assert ref.product_id is None
        assert ref.typical_price is None
    
    def test_create_full(self):
        """Test création complète"""
        ref = ProductRef(
            name="Lactantia PurFiltre 2%",
            product_id="abc123",
            typical_price=5.49,
            notes="Le meilleur"
        )
        assert ref.name == "Lactantia PurFiltre 2%"
        assert ref.product_id == "abc123"
        assert ref.typical_price == 5.49
        assert ref.notes == "Le meilleur"
    
    def test_to_dict(self):
        """Test sérialisation"""
        ref = ProductRef(name="Test", product_id="123", typical_price=4.99)
        d = ref.to_dict()
        assert d["name"] == "Test"
        assert d["product_id"] == "123"
        assert d["typical_price"] == 4.99
    
    def test_to_dict_minimal(self):
        """Test sérialisation minimale (pas de champs vides)"""
        ref = ProductRef(name="Test")
        d = ref.to_dict()
        assert d == {"name": "Test"}
        assert "product_id" not in d
    
    def test_from_dict(self):
        """Test désérialisation"""
        data = {"name": "Test", "product_id": "xyz", "typical_price": 3.99}
        ref = ProductRef.from_dict(data)
        assert ref.name == "Test"
        assert ref.product_id == "xyz"
        assert ref.typical_price == 3.99
    
    def test_from_dict_string(self):
        """Test désérialisation depuis string simple"""
        ref = ProductRef.from_dict("Natrel 2%")
        assert ref.name == "Natrel 2%"
        assert ref.product_id is None


class TestProductPreference:
    """Tests pour ProductPreference"""
    
    def test_create_empty(self):
        """Test création vide"""
        pref = ProductPreference()
        assert pref.favorite is None
        assert pref.substitutes == []
        assert pref.avoid == []
        assert pref.constraints == {}
    
    def test_create_full(self):
        """Test création complète"""
        pref = ProductPreference(
            category="produits-laitiers",
            favorite=ProductRef(name="Lactantia 2%"),
            substitutes=[ProductRef(name="Natrel 2%")],
            avoid=["Marque X"],
            constraints={"must_be": ["2%"]}
        )
        assert pref.category == "produits-laitiers"
        assert pref.favorite.name == "Lactantia 2%"
        assert len(pref.substitutes) == 1
        assert "Marque X" in pref.avoid
    
    def test_to_dict(self):
        """Test sérialisation"""
        pref = ProductPreference(
            favorite=ProductRef(name="Test"),
            avoid=["Bad"]
        )
        d = pref.to_dict()
        assert d["favorite"]["name"] == "Test"
        assert d["avoid"] == ["Bad"]
    
    def test_from_dict(self):
        """Test désérialisation"""
        data = {
            "category": "test",
            "favorite": {"name": "Fav"},
            "substitutes": [{"name": "Sub1"}, {"name": "Sub2"}],
            "avoid": ["Bad1", "Bad2"]
        }
        pref = ProductPreference.from_dict(data)
        assert pref.category == "test"
        assert pref.favorite.name == "Fav"
        assert len(pref.substitutes) == 2
        assert len(pref.avoid) == 2
    
    def test_format_summary(self):
        """Test formatage"""
        pref = ProductPreference(
            category="produits-laitiers",
            favorite=ProductRef(name="Lactantia", typical_price=5.49),
            substitutes=[ProductRef(name="Natrel", notes="OK")],
            avoid=["Marque X"]
        )
        summary = pref.format_summary()
        assert "Lactantia" in summary
        assert "5.49" in summary
        assert "Natrel" in summary
        assert "Marque X" in summary


class TestPreferencesManager:
    """Tests pour PreferencesManager"""
    
    def test_set_favorite(self, prefs_manager):
        """Test définir un favori"""
        pref = prefs_manager.set_favorite("lait", "Lactantia 2%")
        
        assert pref.favorite is not None
        assert pref.favorite.name == "Lactantia 2%"
    
    def test_set_favorite_with_details(self, prefs_manager):
        """Test définir un favori avec détails"""
        pref = prefs_manager.set_favorite(
            "lait",
            "Lactantia PurFiltre 2%",
            product_id="abc123",
            price=5.49
        )
        
        assert pref.favorite.name == "Lactantia PurFiltre 2%"
        assert pref.favorite.product_id == "abc123"
        assert pref.favorite.typical_price == 5.49
    
    def test_add_substitute(self, prefs_manager):
        """Test ajouter un substitut"""
        prefs_manager.add_substitute("lait", "Natrel 2%")
        prefs_manager.add_substitute("lait", "Québon 2%", notes="Si besoin de plus")
        
        pref = prefs_manager.get_preference("lait")
        assert len(pref.substitutes) == 2
        assert pref.substitutes[0].name == "Natrel 2%"
        assert pref.substitutes[1].notes == "Si besoin de plus"
    
    def test_add_substitute_update_existing(self, prefs_manager):
        """Test que l'ajout d'un substitut existant le met à jour"""
        prefs_manager.add_substitute("lait", "Natrel 2%")
        prefs_manager.add_substitute("lait", "Natrel 2%", notes="Nouveau notes")
        
        pref = prefs_manager.get_preference("lait")
        assert len(pref.substitutes) == 1
        assert pref.substitutes[0].notes == "Nouveau notes"
    
    def test_remove_substitute(self, prefs_manager):
        """Test retirer un substitut"""
        prefs_manager.add_substitute("lait", "Natrel 2%")
        prefs_manager.add_substitute("lait", "Québon 2%")
        
        result = prefs_manager.remove_substitute("lait", "Natrel 2%")
        assert result is True
        
        pref = prefs_manager.get_preference("lait")
        assert len(pref.substitutes) == 1
        assert pref.substitutes[0].name == "Québon 2%"
    
    def test_add_avoid(self, prefs_manager):
        """Test ajouter une marque à éviter"""
        prefs_manager.add_avoid("lait", "Marque X")
        prefs_manager.add_avoid("lait", "Marque Y")
        
        pref = prefs_manager.get_preference("lait")
        assert "Marque X" in pref.avoid
        assert "Marque Y" in pref.avoid
    
    def test_add_avoid_no_duplicates(self, prefs_manager):
        """Test pas de doublons dans avoid"""
        prefs_manager.add_avoid("lait", "Marque X")
        prefs_manager.add_avoid("lait", "MARQUE X")  # Case different
        
        pref = prefs_manager.get_preference("lait")
        assert len(pref.avoid) == 1
    
    def test_remove_avoid(self, prefs_manager):
        """Test retirer une marque à éviter"""
        prefs_manager.add_avoid("lait", "Marque X")
        prefs_manager.add_avoid("lait", "Marque Y")
        
        result = prefs_manager.remove_avoid("lait", "Marque X")
        assert result is True
        
        pref = prefs_manager.get_preference("lait")
        assert "Marque X" not in pref.avoid
        assert "Marque Y" in pref.avoid
    
    def test_set_category(self, prefs_manager):
        """Test définir la catégorie"""
        prefs_manager.set_category("lait", "produits-laitiers")
        
        pref = prefs_manager.get_preference("lait")
        assert pref.category == "produits-laitiers"
    
    def test_set_constraint(self, prefs_manager):
        """Test ajouter une contrainte"""
        prefs_manager.set_constraint("lait", "must_be", ["2%"])
        prefs_manager.set_constraint("lait", "prefer", "PurFiltre")
        
        pref = prefs_manager.get_preference("lait")
        assert pref.constraints["must_be"] == ["2%"]
        assert pref.constraints["prefer"] == "PurFiltre"
    
    def test_get_preference_not_found(self, prefs_manager):
        """Test préférence inexistante"""
        pref = prefs_manager.get_preference("inexistant")
        assert pref is None
    
    def test_resolve_need_with_favorite(self, prefs_manager):
        """Test résolution avec favori"""
        prefs_manager.set_favorite("lait", "Lactantia PurFiltre 2%")
        
        result = prefs_manager.resolve_need("lait")
        assert result == "Lactantia PurFiltre 2%"
    
    def test_resolve_need_with_substitute(self, prefs_manager):
        """Test résolution avec substitut (pas de favori)"""
        prefs_manager.add_substitute("lait", "Natrel 2%")
        
        result = prefs_manager.resolve_need("lait")
        assert result == "Natrel 2%"
    
    def test_resolve_need_fallback(self, prefs_manager):
        """Test résolution sans préférence"""
        result = prefs_manager.resolve_need("beurre")
        assert result == "beurre"
    
    def test_list_all_preferences(self, prefs_manager):
        """Test liste de toutes les préférences"""
        prefs_manager.set_favorite("lait", "Lactantia")
        prefs_manager.set_favorite("pain", "Bon Matin")
        prefs_manager.add_avoid("céréales", "Generic")
        
        all_prefs = prefs_manager.list_all_preferences()
        
        assert "lait" in all_prefs
        assert "pain" in all_prefs
        assert "céréales" in all_prefs
        assert len(all_prefs) == 3
    
    def test_delete_preference(self, prefs_manager):
        """Test suppression de préférence"""
        prefs_manager.set_favorite("lait", "Lactantia")
        
        result = prefs_manager.delete_preference("lait")
        assert result is True
        
        pref = prefs_manager.get_preference("lait")
        assert pref is None
    
    def test_delete_preference_not_found(self, prefs_manager):
        """Test suppression préférence inexistante"""
        result = prefs_manager.delete_preference("inexistant")
        assert result is False
    
    def test_case_insensitive_keys(self, prefs_manager):
        """Test que les clés sont case-insensitive"""
        prefs_manager.set_favorite("Lait", "Lactantia")
        
        pref = prefs_manager.get_preference("lait")
        assert pref is not None
        
        pref = prefs_manager.get_preference("LAIT")
        assert pref is not None
    
    def test_persistence(self, temp_prefs_file):
        """Test persistance entre instances"""
        # Première instance
        mgr1 = PreferencesManager(prefs_path=temp_prefs_file)
        mgr1.set_favorite("lait", "Lactantia")
        mgr1.add_substitute("lait", "Natrel")
        mgr1.add_avoid("lait", "Marque X")
        
        # Nouvelle instance
        mgr2 = PreferencesManager(prefs_path=temp_prefs_file)
        pref = mgr2.get_preference("lait")
        
        assert pref.favorite.name == "Lactantia"
        assert len(pref.substitutes) == 1
        assert "Marque X" in pref.avoid
    
    # =========================================================================
    # Tests household
    # =========================================================================
    
    def test_get_household_members(self, prefs_manager):
        """Test récupération membres du foyer"""
        members = prefs_manager.get_household_members()
        assert "Mathieu" in members  # Default
    
    def test_add_household_member(self, prefs_manager):
        """Test ajout membre"""
        prefs_manager.add_household_member("Emma")
        prefs_manager.add_household_member("Léa")
        
        members = prefs_manager.get_household_members()
        assert "Emma" in members
        assert "Léa" in members
    
    def test_add_household_member_no_duplicates(self, prefs_manager):
        """Test pas de doublons membres"""
        prefs_manager.add_household_member("Emma")
        prefs_manager.add_household_member("Emma")
        
        members = prefs_manager.get_household_members()
        assert members.count("Emma") == 1
    
    def test_remove_household_member(self, prefs_manager):
        """Test suppression membre"""
        prefs_manager.add_household_member("Emma")
        
        result = prefs_manager.remove_household_member("Emma")
        assert result is True
        
        members = prefs_manager.get_household_members()
        assert "Emma" not in members
    
    def test_get_default_servings(self, prefs_manager):
        """Test portions par défaut"""
        servings = prefs_manager.get_default_servings()
        assert servings == 4  # Default
    
    def test_set_default_servings(self, prefs_manager):
        """Test modifier portions"""
        prefs_manager.set_default_servings(6)
        
        servings = prefs_manager.get_default_servings()
        assert servings == 6
    
    # =========================================================================
    # Tests formatage
    # =========================================================================
    
    def test_format_all_preferences_empty(self, prefs_manager):
        """Test formatage sans préférences"""
        output = prefs_manager.format_all_preferences()
        assert "Aucune préférence" in output
    
    def test_format_all_preferences(self, prefs_manager):
        """Test formatage avec préférences"""
        prefs_manager.set_favorite("lait", "Lactantia")
        prefs_manager.add_avoid("pain", "Generic")
        
        output = prefs_manager.format_all_preferences()
        assert "lait" in output.lower()
        assert "Lactantia" in output
        assert "pain" in output.lower()
    
    def test_format_telegram(self, prefs_manager):
        """Test formatage Telegram"""
        prefs_manager.set_favorite("lait", "Lactantia")
        
        output = prefs_manager.format_telegram()
        assert "<b>" in output  # HTML formatting
        assert "Lait" in output
        assert "Lactantia" in output
