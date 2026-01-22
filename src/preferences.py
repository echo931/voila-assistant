"""
Module de gestion des préférences produits pour Voilà Assistant.

Permet de définir des produits favoris, substituts et marques à éviter
pour chaque type de besoin, facilitant la résolution automatique lors
de l'épicerie.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field


DEFAULT_PREFERENCES_PATH = Path("~/.voila-preferences.json").expanduser()


@dataclass
class ProductRef:
    """Référence à un produit spécifique"""
    name: str
    product_id: Optional[str] = None
    typical_price: Optional[float] = None
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = {"name": self.name}
        if self.product_id:
            d["product_id"] = self.product_id
        if self.typical_price is not None:
            d["typical_price"] = self.typical_price
        if self.notes:
            d["notes"] = self.notes
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductRef":
        if isinstance(data, str):
            return cls(name=data)
        return cls(
            name=data.get("name", ""),
            product_id=data.get("product_id"),
            typical_price=data.get("typical_price"),
            notes=data.get("notes")
        )


@dataclass
class ProductPreference:
    """Préférences pour un type de besoin"""
    category: Optional[str] = None
    favorite: Optional[ProductRef] = None
    substitutes: List[ProductRef] = field(default_factory=list)
    avoid: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    default_quantity: Optional[float] = None
    default_unit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = {}
        if self.category:
            d["category"] = self.category
        if self.favorite:
            d["favorite"] = self.favorite.to_dict()
        if self.substitutes:
            d["substitutes"] = [s.to_dict() for s in self.substitutes]
        if self.avoid:
            d["avoid"] = self.avoid
        if self.constraints:
            d["constraints"] = self.constraints
        if self.default_quantity is not None:
            d["default_quantity"] = self.default_quantity
        if self.default_unit:
            d["default_unit"] = self.default_unit
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductPreference":
        favorite = None
        if data.get("favorite"):
            favorite = ProductRef.from_dict(data["favorite"])
        
        substitutes = []
        for sub in data.get("substitutes", []):
            substitutes.append(ProductRef.from_dict(sub))
        
        return cls(
            category=data.get("category"),
            favorite=favorite,
            substitutes=substitutes,
            avoid=data.get("avoid", []),
            constraints=data.get("constraints", {}),
            default_quantity=data.get("default_quantity"),
            default_unit=data.get("default_unit")
        )
    
    def format_summary(self) -> str:
        """Formate les préférences en texte lisible"""
        lines = []
        
        if self.category:
            lines.append(f"Catégorie: {self.category}")
        
        if self.favorite:
            price_str = ""
            if self.favorite.typical_price:
                price_str = f" (~${self.favorite.typical_price:.2f})"
            lines.append(f"⭐ Favori: {self.favorite.name}{price_str}")
        
        if self.substitutes:
            lines.append("🔄 Substituts:")
            for sub in self.substitutes:
                notes = f" — {sub.notes}" if sub.notes else ""
                lines.append(f"   • {sub.name}{notes}")
        
        if self.avoid:
            lines.append(f"🚫 Éviter: {', '.join(self.avoid)}")
        
        if self.constraints:
            constraints_str = ", ".join(f"{k}: {v}" for k, v in self.constraints.items())
            lines.append(f"📋 Contraintes: {constraints_str}")
        
        return "\n".join(lines) if lines else "Aucune préférence définie"


class PreferencesManager:
    """
    Gestionnaire des préférences produits.
    
    Permet de définir et récupérer les préférences pour chaque type
    de besoin, avec favoris, substituts et marques à éviter.
    """
    
    def __init__(self, prefs_path: Optional[Path] = None):
        """
        Initialise le gestionnaire.
        
        Args:
            prefs_path: Chemin vers le fichier JSON des préférences
        """
        self.prefs_path = Path(prefs_path or DEFAULT_PREFERENCES_PATH).expanduser()
        self._data: Optional[Dict[str, Any]] = None
    
    @property
    def data(self) -> Dict[str, Any]:
        """Charge les données depuis le fichier si nécessaire"""
        if self._data is None:
            self._data = self._load()
        return self._data
    
    def _load(self) -> Dict[str, Any]:
        """Charge les données depuis le fichier JSON"""
        if self.prefs_path.exists():
            try:
                with open(self.prefs_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, KeyError):
                pass
        return {
            "preferences": {},
            "household": {
                "members": ["Mathieu"],
                "default_servings": 4
            },
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    
    def _save(self) -> None:
        """Sauvegarde les données vers le fichier JSON"""
        self.data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.prefs_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.prefs_path, 'w') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def _normalize_key(self, need_name: str) -> str:
        """Normalise le nom du besoin en clé"""
        return need_name.strip().lower()
    
    def get_preference(self, need_name: str) -> Optional[ProductPreference]:
        """
        Retourne les préférences pour un besoin donné.
        
        Args:
            need_name: Nom du besoin (ex: "lait", "céréales")
            
        Returns:
            ProductPreference ou None si aucune préférence définie
        """
        key = self._normalize_key(need_name)
        pref_data = self.data.get("preferences", {}).get(key)
        
        if pref_data:
            return ProductPreference.from_dict(pref_data)
        return None
    
    def _ensure_preference(self, need_name: str) -> ProductPreference:
        """S'assure qu'une préférence existe et la retourne"""
        key = self._normalize_key(need_name)
        
        if "preferences" not in self.data:
            self.data["preferences"] = {}
        
        if key not in self.data["preferences"]:
            self.data["preferences"][key] = {}
        
        return ProductPreference.from_dict(self.data["preferences"][key])
    
    def _save_preference(self, need_name: str, pref: ProductPreference) -> None:
        """Sauvegarde une préférence"""
        key = self._normalize_key(need_name)
        self.data["preferences"][key] = pref.to_dict()
        self._save()
    
    def set_favorite(
        self,
        need_name: str,
        product_name: str,
        product_id: Optional[str] = None,
        price: Optional[float] = None
    ) -> ProductPreference:
        """
        Définit le produit favori pour un besoin.
        
        Args:
            need_name: Nom du besoin
            product_name: Nom du produit favori
            product_id: ID Voilà du produit (optionnel)
            price: Prix typique (optionnel)
            
        Returns:
            La préférence mise à jour
        """
        pref = self._ensure_preference(need_name)
        pref.favorite = ProductRef(
            name=product_name,
            product_id=product_id,
            typical_price=price
        )
        self._save_preference(need_name, pref)
        return pref
    
    def add_substitute(
        self,
        need_name: str,
        product_name: str,
        product_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> ProductPreference:
        """
        Ajoute un produit substitut pour un besoin.
        
        Args:
            need_name: Nom du besoin
            product_name: Nom du produit substitut
            product_id: ID Voilà du produit (optionnel)
            notes: Notes sur ce substitut (optionnel)
            
        Returns:
            La préférence mise à jour
        """
        pref = self._ensure_preference(need_name)
        
        # Vérifier si le substitut existe déjà
        for sub in pref.substitutes:
            if sub.name.lower() == product_name.lower():
                # Mettre à jour
                sub.product_id = product_id or sub.product_id
                sub.notes = notes or sub.notes
                self._save_preference(need_name, pref)
                return pref
        
        # Ajouter nouveau substitut
        pref.substitutes.append(ProductRef(
            name=product_name,
            product_id=product_id,
            notes=notes
        ))
        self._save_preference(need_name, pref)
        return pref
    
    def remove_substitute(self, need_name: str, product_name: str) -> bool:
        """
        Retire un substitut.
        
        Returns:
            True si retiré, False si non trouvé
        """
        pref = self.get_preference(need_name)
        if not pref:
            return False
        
        name_lower = product_name.lower()
        for i, sub in enumerate(pref.substitutes):
            if sub.name.lower() == name_lower:
                del pref.substitutes[i]
                self._save_preference(need_name, pref)
                return True
        
        return False
    
    def add_avoid(self, need_name: str, brand_or_product: str) -> ProductPreference:
        """
        Ajoute une marque/produit à éviter pour un besoin.
        
        Args:
            need_name: Nom du besoin
            brand_or_product: Marque ou produit à éviter
            
        Returns:
            La préférence mise à jour
        """
        pref = self._ensure_preference(need_name)
        
        # Vérifier si déjà présent
        brand_lower = brand_or_product.lower()
        if not any(a.lower() == brand_lower for a in pref.avoid):
            pref.avoid.append(brand_or_product)
            self._save_preference(need_name, pref)
        
        return pref
    
    def remove_avoid(self, need_name: str, brand_or_product: str) -> bool:
        """
        Retire une marque/produit de la liste à éviter.
        
        Returns:
            True si retiré, False si non trouvé
        """
        pref = self.get_preference(need_name)
        if not pref:
            return False
        
        brand_lower = brand_or_product.lower()
        for i, avoid in enumerate(pref.avoid):
            if avoid.lower() == brand_lower:
                del pref.avoid[i]
                self._save_preference(need_name, pref)
                return True
        
        return False
    
    def set_category(self, need_name: str, category: str) -> ProductPreference:
        """Définit la catégorie pour un besoin"""
        pref = self._ensure_preference(need_name)
        pref.category = category
        self._save_preference(need_name, pref)
        return pref
    
    def set_constraint(self, need_name: str, key: str, value: Any) -> ProductPreference:
        """Ajoute une contrainte pour un besoin"""
        pref = self._ensure_preference(need_name)
        pref.constraints[key] = value
        self._save_preference(need_name, pref)
        return pref
    
    def resolve_need(self, need_name: str) -> Optional[str]:
        """
        Résout un besoin en terme de recherche produit.
        
        Retourne le favori s'il existe, sinon le premier substitut,
        sinon le nom du besoin lui-même.
        
        Args:
            need_name: Nom du besoin
            
        Returns:
            Terme de recherche à utiliser pour ce besoin
        """
        pref = self.get_preference(need_name)
        
        if pref:
            if pref.favorite:
                return pref.favorite.name
            if pref.substitutes:
                return pref.substitutes[0].name
        
        # Retourner le nom du besoin tel quel
        return need_name
    
    def list_all_preferences(self) -> Dict[str, ProductPreference]:
        """
        Liste toutes les préférences définies.
        
        Returns:
            Dict {need_name: ProductPreference}
        """
        prefs = {}
        for key, data in self.data.get("preferences", {}).items():
            prefs[key] = ProductPreference.from_dict(data)
        return prefs
    
    def delete_preference(self, need_name: str) -> bool:
        """
        Supprime toutes les préférences pour un besoin.
        
        Returns:
            True si supprimé, False si non trouvé
        """
        key = self._normalize_key(need_name)
        if key in self.data.get("preferences", {}):
            del self.data["preferences"][key]
            self._save()
            return True
        return False
    
    # =========================================================================
    # Gestion du foyer (household)
    # =========================================================================
    
    def get_household_members(self) -> List[str]:
        """Retourne la liste des membres du foyer"""
        return self.data.get("household", {}).get("members", ["Mathieu"])
    
    def add_household_member(self, name: str) -> List[str]:
        """Ajoute un membre au foyer"""
        if "household" not in self.data:
            self.data["household"] = {"members": [], "default_servings": 4}
        
        if name not in self.data["household"]["members"]:
            self.data["household"]["members"].append(name)
            self._save()
        
        return self.data["household"]["members"]
    
    def remove_household_member(self, name: str) -> bool:
        """Retire un membre du foyer"""
        members = self.data.get("household", {}).get("members", [])
        name_lower = name.lower()
        
        for i, member in enumerate(members):
            if member.lower() == name_lower:
                del members[i]
                self._save()
                return True
        
        return False
    
    def get_default_servings(self) -> int:
        """Retourne le nombre de portions par défaut"""
        return self.data.get("household", {}).get("default_servings", 4)
    
    def set_default_servings(self, servings: int) -> None:
        """Définit le nombre de portions par défaut"""
        if "household" not in self.data:
            self.data["household"] = {"members": ["Mathieu"], "default_servings": servings}
        else:
            self.data["household"]["default_servings"] = servings
        self._save()
    
    # =========================================================================
    # Formatage
    # =========================================================================
    
    def format_all_preferences(self) -> str:
        """Formate toutes les préférences pour affichage"""
        prefs = self.list_all_preferences()
        
        if not prefs:
            return "📋 Aucune préférence définie"
        
        lines = [f"📋 Préférences produits ({len(prefs)} items)", ""]
        
        for name, pref in sorted(prefs.items()):
            lines.append(f"▸ {name.capitalize()}")
            
            if pref.favorite:
                lines.append(f"  ⭐ {pref.favorite.name}")
            
            if pref.substitutes:
                subs = ", ".join(s.name for s in pref.substitutes[:2])
                if len(pref.substitutes) > 2:
                    subs += f" (+{len(pref.substitutes) - 2})"
                lines.append(f"  🔄 {subs}")
            
            if pref.avoid:
                lines.append(f"  🚫 {', '.join(pref.avoid)}")
            
            lines.append("")
        
        return "\n".join(lines).rstrip()
    
    def format_telegram(self) -> str:
        """Formate les préférences pour Telegram (HTML)"""
        prefs = self.list_all_preferences()
        
        if not prefs:
            return "📋 <b>Aucune préférence définie</b>"
        
        lines = [f"📋 <b>Préférences produits</b> ({len(prefs)} items)\n"]
        
        for name, pref in sorted(prefs.items()):
            line = f"<b>{name.capitalize()}</b>"
            if pref.favorite:
                line += f" → {pref.favorite.name}"
            lines.append(line)
        
        return "\n".join(lines)
