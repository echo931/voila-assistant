"""
Module de gestion du panier local pour Voilà Assistant.

Permet de composer un panier localement avant de le synchroniser
vers le panier en ligne Voilà.ca.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field


DEFAULT_LOCAL_CART_PATH = Path("~/.voila-local-cart.json").expanduser()


@dataclass
class LocalCartItem:
    """Un item dans le panier local"""
    query: str
    quantity: int = 1
    product_id: Optional[str] = None
    resolved_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LocalCartItem":
        return cls(
            query=data.get("query", ""),
            quantity=data.get("quantity", 1),
            product_id=data.get("product_id"),
            resolved_name=data.get("resolved_name")
        )


@dataclass
class LocalCart:
    """Panier local avec persistance JSON"""
    items: List[LocalCartItem] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LocalCart":
        items = [LocalCartItem.from_dict(i) for i in data.get("items", [])]
        return cls(
            items=items,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )


class LocalCartManager:
    """
    Gestionnaire du panier local.
    
    Permet d'ajouter/retirer des produits localement puis de synchroniser
    vers le panier en ligne Voilà.
    """
    
    def __init__(self, cart_path: Optional[Path] = None):
        """
        Initialise le gestionnaire.
        
        Args:
            cart_path: Chemin vers le fichier JSON du panier local
        """
        self.cart_path = Path(cart_path or DEFAULT_LOCAL_CART_PATH).expanduser()
        self._cart: Optional[LocalCart] = None
    
    @property
    def cart(self) -> LocalCart:
        """Charge le panier depuis le fichier si nécessaire"""
        if self._cart is None:
            self._cart = self.load()
        return self._cart
    
    def load(self) -> LocalCart:
        """Charge le panier depuis le fichier JSON"""
        if self.cart_path.exists():
            try:
                with open(self.cart_path) as f:
                    data = json.load(f)
                return LocalCart.from_dict(data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"⚠️ Erreur lecture panier local: {e}", file=sys.stderr)
                return LocalCart()
        return LocalCart()
    
    def save(self) -> None:
        """Sauvegarde le panier vers le fichier JSON"""
        self.cart.updated_at = datetime.now(timezone.utc).isoformat()
        self.cart_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cart_path, 'w') as f:
            json.dump(self.cart.to_dict(), f, indent=2, ensure_ascii=False)
    
    def add_item(self, query: str, quantity: int = 1) -> LocalCartItem:
        """
        Ajoute un item au panier local.
        
        Si l'item existe déjà (même query), augmente la quantité.
        
        Args:
            query: Terme de recherche du produit
            quantity: Quantité à ajouter
            
        Returns:
            L'item ajouté ou mis à jour
        """
        # Normaliser la query
        query_lower = query.strip().lower()
        
        # Chercher si le produit existe déjà
        for item in self.cart.items:
            if item.query.lower() == query_lower:
                item.quantity += quantity
                self.save()
                return item
        
        # Nouveau produit
        item = LocalCartItem(query=query.strip(), quantity=quantity)
        self.cart.items.append(item)
        self.save()
        return item
    
    def remove_item(self, query: str) -> bool:
        """
        Retire un item du panier local.
        
        Args:
            query: Terme de recherche du produit à retirer
            
        Returns:
            True si l'item a été retiré, False si non trouvé
        """
        query_lower = query.strip().lower()
        
        for i, item in enumerate(self.cart.items):
            if item.query.lower() == query_lower:
                del self.cart.items[i]
                self.save()
                return True
        
        return False
    
    def clear(self) -> None:
        """Vide le panier local"""
        self.cart.items.clear()
        self.save()
    
    def list_items(self) -> List[LocalCartItem]:
        """Retourne la liste des items du panier"""
        return self.cart.items.copy()
    
    def is_empty(self) -> bool:
        """Retourne True si le panier est vide"""
        return len(self.cart.items) == 0
    
    def item_count(self) -> int:
        """Retourne le nombre d'items distincts"""
        return len(self.cart.items)
    
    def total_quantity(self) -> int:
        """Retourne la quantité totale (somme des quantités)"""
        return sum(item.quantity for item in self.cart.items)
    
    def resolve_products(self, search_engine) -> Dict[str, Any]:
        """
        Pré-résout les queries en product_ids via recherche.
        
        Args:
            search_engine: Instance de ProductSearch
            
        Returns:
            Dict avec 'resolved' et 'errors'
        """
        from .search import ProductSearch
        
        resolved = 0
        errors = []
        
        for item in self.cart.items:
            if item.product_id:
                # Déjà résolu
                resolved += 1
                continue
            
            try:
                results = search_engine.search(item.query, max_results=1)
                if results:
                    product = results[0]
                    item.product_id = product.get('id') or product.get('product_id')
                    item.resolved_name = product.get('name')
                    resolved += 1
                else:
                    errors.append({
                        "query": item.query,
                        "error": "Aucun produit trouvé"
                    })
            except Exception as e:
                errors.append({
                    "query": item.query,
                    "error": str(e)
                })
        
        self.save()
        
        return {
            "resolved": resolved,
            "total": len(self.cart.items),
            "errors": errors
        }
    
    def sync_to_online(
        self, 
        cart_manager,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Synchronise le panier local vers le panier en ligne Voilà.
        
        Args:
            cart_manager: Instance de CartManager (browser)
            progress_callback: Fonction(current, total, item_name) pour progression
            
        Returns:
            Dict avec statistiques de sync
        """
        if self.is_empty():
            return {
                "total_added": 0,
                "total_errors": 0,
                "errors": [],
                "message": "Panier local vide"
            }
        
        added = 0
        errors = []
        total = len(self.cart.items)
        
        for i, item in enumerate(self.cart.items):
            if progress_callback:
                progress_callback(i + 1, total, item.query)
            
            try:
                # Utiliser add_item_by_search du CartManager
                cart_manager.add_item_by_search(
                    item.query,
                    product_index=0,
                    quantity=item.quantity
                )
                added += 1
                
            except Exception as e:
                errors.append({
                    "product": item.query,
                    "quantity": item.quantity,
                    "error": str(e)
                })
        
        return {
            "total_added": added,
            "total_errors": len(errors),
            "errors": errors,
            "message": f"{added}/{total} produits ajoutés au panier en ligne"
        }
    
    def format_summary(self) -> str:
        """Formate le panier local en texte lisible"""
        if self.is_empty():
            return "🛒 Panier local vide"
        
        lines = [
            f"🛒 Panier local ({self.item_count()} articles, {self.total_quantity()} unités)",
            ""
        ]
        
        for i, item in enumerate(self.cart.items, 1):
            qty_str = f" ×{item.quantity}" if item.quantity > 1 else ""
            resolved = ""
            if item.resolved_name:
                resolved = f" → {item.resolved_name}"
            elif item.product_id:
                resolved = f" [ID: {item.product_id[:8]}...]"
            
            lines.append(f"  {i}. {item.query}{qty_str}{resolved}")
        
        return "\n".join(lines)
    
    def format_telegram(self) -> str:
        """Formate le panier local pour Telegram (HTML)"""
        if self.is_empty():
            return "🛒 <b>Panier local vide</b>"
        
        lines = [
            f"🛒 <b>Panier local</b> ({self.item_count()} articles)",
            ""
        ]
        
        for i, item in enumerate(self.cart.items, 1):
            qty_str = f" ×{item.quantity}" if item.quantity > 1 else ""
            name = item.resolved_name or item.query
            lines.append(f"  {i}. {name}{qty_str}")
        
        return "\n".join(lines)
    
    def format_json(self) -> str:
        """Retourne le panier au format JSON"""
        return json.dumps(self.cart.to_dict(), indent=2, ensure_ascii=False)
