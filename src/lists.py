"""
Module de gestion des listes Voilà.ca

Les listes sont rendues côté serveur, donc on utilise Playwright pour les extraire.
Structure des URLs:
- /lists - Affiche toutes les listes
- /lists/{uuid} - Affiche une liste spécifique
"""

import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from decimal import Decimal
from html import escape

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from playwright._impl._errors import TimeoutError as PlaywrightTimeout

from .models import Product
from .exceptions import VoilaAPIError, VoilaAuthRequired, VoilaBrowserError


@dataclass
class ShoppingList:
    """Représente une liste de courses"""
    
    id: str
    name: str
    items: List['ShoppingListItem'] = field(default_factory=list)
    item_count: int = 0
    total_price: Optional[Decimal] = None
    sale_count: int = 0
    
    def format_summary(self) -> str:
        """Formate un résumé de la liste"""
        line = f"📋 {self.name} ({self.item_count} articles)"
        if self.total_price:
            line += f" — {self.total_price}$"
        if self.sale_count > 0:
            line += f" 🏷️ {self.sale_count} en solde"
        return line
    
    def format_detailed(self, show_prices: bool = True) -> str:
        """Formate la liste avec les articles"""
        lines = [f"📋 **{self.name}** ({self.item_count} articles)\n"]
        
        total = Decimal('0')
        for item in self.items:
            line = f"  • {item.product_name}"
            if item.quantity > 1:
                line += f" (x{item.quantity})"
            if show_prices and item.price:
                line += f" — {item.price}$"
                total += item.price * item.quantity
            if item.on_sale:
                line += " 🏷️"
            lines.append(line)
        
        if show_prices and total > 0:
            lines.append(f"\n💰 Total: {total}$")
        
        return "\n".join(lines)
    
    def format_telegram(self) -> str:
        """Formate la liste pour Telegram (HTML)"""
        lines = [f"<b>📋 {escape(self.name)}</b> ({self.item_count} articles)\n"]
        
        total = Decimal('0')
        for item in self.items:
            line = f"• <b>{escape(item.product_name)}</b>"
            if item.quantity > 1:
                line += f" (x{item.quantity})"
            if item.price:
                line += f" — {item.price}$"
                total += item.price * item.quantity
            if item.on_sale:
                line += " 🏷️"
            lines.append(line)
        
        if total > 0:
            lines.append(f"\n<b>💰 Total: {total}$</b>")
        
        return "\n".join(lines)
    
    def get_sale_items(self) -> List['ShoppingListItem']:
        """Retourne uniquement les articles en solde"""
        return [item for item in self.items if item.on_sale]


@dataclass 
class ShoppingListItem:
    """Représente un article dans une liste"""
    
    product_id: str
    product_name: str
    quantity: int = 1
    price: Optional[Decimal] = None
    on_sale: bool = False
    original_price: Optional[Decimal] = None
    size: Optional[str] = None
    brand: Optional[str] = None
    
    @classmethod
    def from_product_entity(cls, data: dict) -> 'ShoppingListItem':
        """Crée un ShoppingListItem depuis productEntities"""
        price_data = data.get('price', {})
        current = price_data.get('current', {})
        # Le prix original peut être dans 'was' ou 'original'
        original = price_data.get('original', price_data.get('was', {}))
        
        current_amount = current.get('amount')
        original_amount = original.get('amount')
        
        on_sale = False
        if current_amount and original_amount:
            try:
                on_sale = Decimal(original_amount) > Decimal(current_amount)
            except:
                pass
        
        return cls(
            product_id=data.get('id', ''),
            product_name=data.get('name', ''),
            quantity=1,  # Lists don't store quantity
            price=Decimal(current_amount) if current_amount else None,
            on_sale=on_sale,
            original_price=Decimal(original_amount) if original_amount else None,
            size=data.get('size', {}).get('value') if data.get('size') else None,
            brand=data.get('brand')
        )


class ListsManager:
    """Gestion des listes Voilà.ca via browser automation"""
    
    BASE_URL = "https://voila.ca"
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def __init__(
        self,
        headless: bool = True,
        timeout: int = 20000,
        session_file: Optional[Path] = None
    ):
        """
        Initialise le gestionnaire de listes.
        
        Args:
            headless: Mode sans interface graphique
            timeout: Timeout en ms pour les opérations
            session_file: Fichier de cookies de session
        """
        self.headless = headless
        self.timeout = timeout
        self.session_file = Path(session_file).expanduser() if session_file else None
        
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._playwright = None
    
    def _ensure_browser(self):
        """S'assure que le browser est démarré"""
        if self._browser is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            self._context = self._browser.new_context(user_agent=self.DEFAULT_USER_AGENT)
            self._page = self._context.new_page()
            
            if self.session_file and self.session_file.exists():
                self._load_cookies()
    
    def _load_cookies(self):
        """Charge les cookies depuis le fichier de session"""
        if not self.session_file or not self.session_file.exists():
            return
        
        try:
            with open(self.session_file) as f:
                data = json.load(f)
            
            cookies = data.get('cookies', []) if isinstance(data, dict) else data
            self._context.add_cookies(cookies)
        except Exception:
            pass
    
    def is_authenticated(self) -> bool:
        """Vérifie si on est connecté"""
        self._ensure_browser()
        
        try:
            self._page.goto(f"{self.BASE_URL}/lists", wait_until="domcontentloaded", timeout=self.timeout)
            self._page.wait_for_timeout(3000)
            
            # Si on est redirigé vers login, pas connecté
            if 'login' in self._page.url.lower():
                return False
            
            # Vérifier dans le state
            customer = self._page.evaluate('''() => {
                const s = window.__INITIAL_STATE__;
                return s?.data?.customer?.details?.data?.email || null;
            }''')
            
            return customer is not None
            
        except Exception:
            return False
    
    def get_lists(self) -> List[ShoppingList]:
        """
        Récupère toutes les listes de l'utilisateur.
        
        Returns:
            Liste des ShoppingList
            
        Raises:
            VoilaAuthRequired: Si non authentifié
        """
        self._ensure_browser()
        
        try:
            self._page.goto(f"{self.BASE_URL}/lists", wait_until="domcontentloaded", timeout=self.timeout)
            self._page.wait_for_timeout(4000)
            
            # Vérifier si redirigé vers login
            if 'login' in self._page.url.lower():
                raise VoilaAuthRequired("Authentification requise pour accéder aux listes")
            
            # Extraire le texte de la page et les IDs des listes
            page_text = self._page.evaluate("() => document.body.innerText")
            
            list_ids = self._page.evaluate("""() => {
                const links = document.querySelectorAll('a[href*="/lists/"]');
                const ids = [];
                for (const link of links) {
                    const href = link.getAttribute('href');
                    const match = href.match(/\\/lists\\/([a-f0-9-]+)/);
                    if (match && ids.indexOf(match[1]) === -1) {
                        ids.push(match[1]);
                    }
                }
                return ids;
            }""")
            
            # Parser le texte en Python pour éviter les problèmes de regex JS
            pattern = r'([^\n]+)\nTotal\s*:\s*([\d\s,.]+)\s*\$\n(\d+)\s*articles?\n(\d+)\s*offres?'
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            
            lists_data = []
            for i, (name, total, count, sales) in enumerate(matches):
                name = name.strip()
                # Filtrer les faux positifs
                if len(name) > 1 and len(name) < 50 and 'Voilà' not in name and 'IGA' not in name:
                    # Nettoyer le total (enlever espaces et remplacer virgule par point)
                    total_clean = total.replace(' ', '').replace(',', '.').replace('\xa0', '')
                    lists_data.append({
                        'id': list_ids[i] if i < len(list_ids) else '',
                        'name': name,
                        'total': total_clean,
                        'item_count': int(count),
                        'sale_count': int(sales)
                    })
            
            result = []
            for ld in lists_data:
                # Convertir le total en Decimal de manière sécurisée
                total_price = None
                if ld.get('total'):
                    try:
                        total_price = Decimal(ld['total'])
                    except:
                        pass
                
                result.append(ShoppingList(
                    id=ld['id'],
                    name=ld['name'],
                    item_count=ld['item_count'],
                    total_price=total_price,
                    sale_count=ld.get('sale_count', 0)
                ))
            
            return result
            
        except VoilaAuthRequired:
            raise
        except Exception as e:
            raise VoilaBrowserError(f"Erreur récupération listes: {e}")
    
    def get_list(self, list_id: str) -> ShoppingList:
        """
        Récupère une liste spécifique avec ses articles.
        
        Args:
            list_id: UUID de la liste
            
        Returns:
            ShoppingList avec les articles
        """
        self._ensure_browser()
        
        try:
            self._page.goto(f"{self.BASE_URL}/lists/{list_id}", wait_until="domcontentloaded", timeout=self.timeout)
            self._page.wait_for_timeout(4000)
            
            if 'login' in self._page.url.lower():
                raise VoilaAuthRequired("Authentification requise")
            
            # Extraire les données depuis __INITIAL_STATE__
            data = self._page.evaluate('''() => {
                const s = window.__INITIAL_STATE__;
                if (!s || !s.data) return null;
                
                // Les produits sont dans products.productEntities
                const products = s.data.products?.productEntities || {};
                const productList = Object.values(products);
                
                // Extraire le nom de la liste depuis le titre de la page
                const title = document.title;
                const h1 = document.querySelector('h1');
                const name = h1?.innerText || title.replace(' | Voilà', '').trim() || 'Liste';
                
                return {
                    name: name,
                    products: productList.map(p => ({
                        id: p.id,
                        name: p.name,
                        brand: p.brand,
                        size: p.size?.value,
                        price_current: p.price?.current?.amount,
                        price_original: p.price?.original?.amount || p.price?.was?.amount
                    }))
                };
            }''')
            
            if not data:
                raise VoilaAPIError(f"Liste {list_id} non trouvée")
            
            items = []
            for p in data.get('products', []):
                current = p.get('price_current')
                original = p.get('price_original')
                on_sale = False
                if current and original:
                    try:
                        on_sale = Decimal(original) > Decimal(current)
                    except:
                        pass
                
                items.append(ShoppingListItem(
                    product_id=p['id'],
                    product_name=p['name'],
                    brand=p.get('brand'),
                    size=p.get('size'),
                    price=Decimal(current) if current else None,
                    original_price=Decimal(original) if original else None,
                    on_sale=on_sale
                ))
            
            return ShoppingList(
                id=list_id,
                name=data['name'],
                items=items,
                item_count=len(items),
                sale_count=len([i for i in items if i.on_sale])
            )
            
        except VoilaAuthRequired:
            raise
        except Exception as e:
            raise VoilaBrowserError(f"Erreur récupération liste: {e}")
    
    def get_list_by_name(self, name: str) -> Optional[ShoppingList]:
        """
        Récupère une liste par son nom.
        
        Args:
            name: Nom de la liste (insensible à la casse)
            
        Returns:
            ShoppingList ou None si non trouvée
        """
        lists = self.get_lists()
        name_lower = name.lower()
        
        for lst in lists:
            if lst.name.lower() == name_lower:
                return self.get_list(lst.id)
        
        return None
    
    def search_in_lists(self, query: str) -> List[Dict[str, Any]]:
        """
        Recherche un terme dans toutes les listes.
        
        Args:
            query: Terme de recherche
            
        Returns:
            Liste de résultats avec list_name, item
        """
        results = []
        query_lower = query.lower()
        
        for lst in self.get_lists():
            full_list = self.get_list(lst.id)
            for item in full_list.items:
                if query_lower in item.product_name.lower():
                    results.append({
                        'list_name': full_list.name,
                        'list_id': full_list.id,
                        'item': item
                    })
        
        return results
    
    def add_list_to_cart(self, list_id: str, cart_manager) -> Dict[str, Any]:
        """
        Ajoute tous les articles d'une liste au panier.
        
        Args:
            list_id: ID de la liste
            cart_manager: Instance de CartManager
            
        Returns:
            Résumé des articles ajoutés
        """
        shopping_list = self.get_list(list_id)
        added = []
        errors = []
        
        for item in shopping_list.items:
            try:
                # Utiliser la recherche pour ajouter
                cart_manager.add_item_by_search(
                    item.product_name,
                    quantity=item.quantity
                )
                added.append(item.product_name)
            except Exception as e:
                errors.append({
                    'product': item.product_name,
                    'error': str(e)
                })
        
        return {
            'list_name': shopping_list.name,
            'added': added,
            'errors': errors,
            'total_added': len(added),
            'total_errors': len(errors)
        }
    
    def close(self):
        """Ferme le browser"""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def format_lists_summary(lists: List[ShoppingList]) -> str:
    """Formate un résumé de toutes les listes"""
    if not lists:
        return "📋 Aucune liste trouvée"
    
    lines = ["📋 **Vos listes de courses**\n"]
    for i, lst in enumerate(lists, 1):
        line = f"{i}. {lst.name} ({lst.item_count} articles)"
        if lst.total_price:
            line += f" — {lst.total_price}$"
        if lst.sale_count > 0:
            line += f" 🏷️ {lst.sale_count}"
        lines.append(line)
    
    return "\n".join(lines)


def format_search_results(results: List[Dict]) -> str:
    """Formate les résultats de recherche dans les listes"""
    if not results:
        return "🔍 Aucun résultat trouvé"
    
    lines = [f"🔍 **{len(results)} résultat(s) trouvé(s)**\n"]
    
    current_list = None
    for r in results:
        if r['list_name'] != current_list:
            current_list = r['list_name']
            lines.append(f"\n📋 {current_list}:")
        
        item = r['item']
        line = f"  • {item.product_name}"
        if item.price:
            line += f" — {item.price}$"
        if item.on_sale:
            line += " 🏷️"
        lines.append(line)
    
    return "\n".join(lines)
