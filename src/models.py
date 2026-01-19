"""
Modèles de données pour Voilà Assistant
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List
from html import escape


@dataclass
class Product:
    """Représente un produit Voilà"""
    
    id: str
    name: str
    brand: Optional[str] = None
    size: Optional[str] = None
    price: Optional[Decimal] = None
    currency: str = "CAD"
    unit_price: Optional[Decimal] = None
    unit_label: Optional[str] = None
    available: bool = True
    category: Optional[str] = None
    image_url: Optional[str] = None
    
    @classmethod
    def from_api_response(cls, data: dict) -> 'Product':
        """Crée un Product depuis la réponse API (productEntities)"""
        price_data = data.get('price', {})
        current_price = price_data.get('current', {})
        unit_data = price_data.get('unit', {})
        unit_current = unit_data.get('current', {})
        
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            brand=data.get('brand'),
            size=data.get('size', {}).get('value') if data.get('size') else None,
            price=Decimal(current_price.get('amount', '0')) if current_price.get('amount') else None,
            currency=current_price.get('currency', 'CAD'),
            unit_price=Decimal(unit_current.get('amount', '0')) if unit_current.get('amount') else None,
            unit_label=cls._clean_unit_label(unit_data.get('label')),
            available=data.get('status') == 'AVAILABLE',
            category=data.get('department'),
            image_url=data.get('images', [{}])[0].get('url') if data.get('images') else None
        )
    
    @staticmethod
    def _clean_unit_label(label: Optional[str]) -> Optional[str]:
        """Nettoie le label d'unité (fop.price.per.100gram -> 100g)"""
        if not label:
            return None
        return (label
            .replace('fop.price.per.', '')
            .replace('100gram', '100g')
            .replace('100ml', '100ml')
            .replace('each', 'unité'))
    
    def format_table_row(self, name_width: int = 50) -> str:
        """Formate le produit pour affichage en table"""
        name = self.name[:name_width-2] if len(self.name) > name_width else self.name
        size = self.size or '-'
        price = f"${self.price}" if self.price else 'N/A'
        unit = f"${self.unit_price}/{self.unit_label}" if self.unit_price and self.unit_label else '-'
        return f"{name:<{name_width}} {size:<8} {price:<8} {unit}"
    
    def format_telegram(self) -> str:
        """Formate le produit pour Telegram (HTML)"""
        line = f"• <b>{escape(self.name)}</b>"
        if self.size:
            line += f" ({self.size})"
        line += f"\n   💰 ${self.price}"
        if self.unit_price and self.unit_label:
            line += f" — ${self.unit_price}/{self.unit_label}"
        return line
    
    def to_dict(self) -> dict:
        """Convertit en dictionnaire"""
        return {
            'id': self.id,
            'name': self.name,
            'brand': self.brand,
            'size': self.size,
            'price': str(self.price) if self.price else None,
            'currency': self.currency,
            'unit_price': str(self.unit_price) if self.unit_price else None,
            'unit_label': self.unit_label,
            'available': self.available,
            'category': self.category
        }


@dataclass
class CartItem:
    """Représente un article dans le panier"""
    
    product_id: str
    product_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    
    @classmethod
    def from_api_response(cls, data: dict) -> 'CartItem':
        """Crée un CartItem depuis la réponse API"""
        return cls(
            product_id=data.get('productId', ''),
            product_name=data.get('productName', ''),
            quantity=data.get('quantity', 1),
            unit_price=Decimal(data.get('unitPrice', {}).get('amount', '0')),
            total_price=Decimal(data.get('totalPrice', {}).get('amount', '0'))
        )
    
    def format_line(self) -> str:
        """Formate l'article pour affichage"""
        return f"{self.quantity}x {self.product_name} - ${self.total_price}"


@dataclass
class Cart:
    """Représente le panier"""
    
    id: str
    items: List[CartItem] = field(default_factory=list)
    subtotal: Decimal = Decimal('0')
    currency: str = "CAD"
    minimum_threshold: Decimal = Decimal('35.00')
    
    @classmethod
    def from_api_response(cls, data: dict) -> 'Cart':
        """Crée un Cart depuis la réponse API"""
        items = [CartItem.from_api_response(item) for item in data.get('items', [])]
        totals = data.get('totals', {})
        subtotal_data = totals.get('subtotal', {})
        threshold_data = data.get('minimumCheckoutThreshold', {})
        
        return cls(
            id=data.get('basketId', ''),
            items=items,
            subtotal=Decimal(subtotal_data.get('amount', '0')),
            currency=subtotal_data.get('currency', 'CAD'),
            minimum_threshold=Decimal(threshold_data.get('amount', '35.00'))
        )
    
    @property
    def item_count(self) -> int:
        """Nombre total d'articles"""
        return sum(item.quantity for item in self.items)
    
    @property
    def is_above_minimum(self) -> bool:
        """Vérifie si le panier atteint le minimum"""
        return self.subtotal >= self.minimum_threshold
    
    def format_summary(self) -> str:
        """Formate le résumé du panier"""
        lines = [f"🛒 Panier ({self.item_count} articles)\n"]
        
        for item in self.items:
            lines.append(f"  • {item.format_line()}")
        
        lines.append(f"\n💰 Sous-total: ${self.subtotal}")
        
        if not self.is_above_minimum:
            remaining = self.minimum_threshold - self.subtotal
            lines.append(f"⚠️ Minimum requis: ${self.minimum_threshold} (manque ${remaining})")
        
        return "\n".join(lines)
    
    def format_telegram(self) -> str:
        """Formate le panier pour Telegram (HTML)"""
        lines = [f"<b>🛒 Panier ({self.item_count} articles)</b>\n"]
        
        for item in self.items:
            lines.append(f"• {item.quantity}x <b>{escape(item.product_name)}</b> — ${item.total_price}")
        
        lines.append(f"\n<b>💰 Sous-total: ${self.subtotal}</b>")
        
        if not self.is_above_minimum:
            remaining = self.minimum_threshold - self.subtotal
            lines.append(f"\n⚠️ <i>Minimum requis: ${self.minimum_threshold} (manque ${remaining})</i>")
        
        return "\n".join(lines)
