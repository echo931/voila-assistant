"""
Module de gestion du panier Voilà.ca
"""

import json
from pathlib import Path
from typing import Optional, List
from urllib.parse import quote
from decimal import Decimal

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from playwright._impl._errors import TimeoutError as PlaywrightTimeout

from .models import Product, Cart, CartItem
from .exceptions import VoilaCartError, VoilaBrowserError, VoilaProductNotFound


class CartManager:
    """Gestion du panier Voilà.ca via browser automation"""
    
    BASE_URL = "https://voila.ca"
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def __init__(
        self, 
        headless: bool = True, 
        timeout: int = 20000,
        session_file: Optional[Path] = None
    ):
        """
        Initialise le gestionnaire de panier.
        
        Args:
            headless: True pour mode sans interface graphique
            timeout: Timeout en millisecondes pour les opérations
            session_file: Fichier pour sauvegarder/charger les cookies de session
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
            
            # Charger les cookies de session si disponibles
            if self.session_file and self.session_file.exists():
                self._load_cookies()
    
    def _load_cookies(self):
        """Charge les cookies depuis le fichier de session"""
        if not self.session_file or not self.session_file.exists():
            return
        
        try:
            with open(self.session_file) as f:
                cookies = json.load(f)
            self._context.add_cookies(cookies)
        except Exception:
            pass  # Ignore cookie loading errors
    
    def _save_cookies(self):
        """Sauvegarde les cookies vers le fichier de session"""
        if not self.session_file:
            return
        
        try:
            self.session_file.parent.mkdir(parents=True, exist_ok=True)
            cookies = self._context.cookies()
            with open(self.session_file, 'w') as f:
                json.dump(cookies, f, indent=2)
            self.session_file.chmod(0o600)
        except Exception:
            pass  # Ignore cookie saving errors
    
    def _navigate_to_search(self, query: str = ""):
        """Navigate vers une page qui a le panier initialisé"""
        url = f"{self.BASE_URL}/search?q={quote(query)}" if query else self.BASE_URL
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
        except PlaywrightTimeout:
            pass  # Continue anyway
        self._page.wait_for_timeout(2000)
    
    def _get_cart_state(self) -> dict:
        """Extrait l'état du panier depuis __INITIAL_STATE__"""
        return self._page.evaluate('''
            () => {
                const state = window.__INITIAL_STATE__;
                if (!state || !state.data) return { error: "No state" };
                
                // Le panier peut être dans basket ou cart selon la page
                const basket = state.data.basket || state.data.cart || {};
                
                // Récupérer les infos produits si disponibles
                const productEntities = state.data.products?.productEntities || {};
                
                // Transformer les items avec les noms des produits
                const items = (basket.items || []).map(item => {
                    const productInfo = productEntities[item.productId] || {};
                    return {
                        productId: item.productId,
                        productName: productInfo.name || item.productId,
                        quantity: item.quantity?.quantityInBasket || item.quantity || 1,
                        unitPrice: item.totalPrices?.finalUnitPrice?.amount || 
                                   item.totalPrices?.regularPrice?.amount || "0",
                        totalPrice: item.totalPrices?.finalPrice?.amount || 
                                    item.totalPrices?.regularPrice?.amount || "0",
                        currency: item.totalPrices?.finalPrice?.currency || "CAD"
                    };
                });
                
                return {
                    cartId: basket.basketId || basket.cartId,
                    items: items,
                    totals: basket.totals || {},
                    minimumCheckoutThreshold: basket.minimumCheckoutThreshold || 
                        basket.defaultCheckoutGroup?.minimumCheckoutThreshold || 
                        { amount: "35.00", currency: "CAD" }
                };
            }
        ''')
    
    def get_cart(self, force_refresh: bool = False) -> Cart:
        """
        Récupère le panier actif.
        
        Args:
            force_refresh: Force la navigation vers la page panier pour avoir les noms
        
        Returns:
            Objet Cart avec les articles actuels
        
        Raises:
            VoilaBrowserError: En cas d'erreur browser
        """
        try:
            self._ensure_browser()
            
            # Naviguer vers la page panier pour avoir les noms des produits
            if self._page.url == "about:blank" or force_refresh or "/cart" not in self._page.url:
                try:
                    self._page.goto(f"{self.BASE_URL}/cart", wait_until="domcontentloaded", timeout=self.timeout)
                except PlaywrightTimeout:
                    pass
                self._page.wait_for_timeout(2000)
            
            state = self._get_cart_state()
            
            if "error" in state:
                return Cart(id="", items=[], subtotal=Decimal('0'))
            
            # Convertir les items
            items = []
            for item in state.get('items', []):
                try:
                    qty = item.get('quantity', 1)
                    if isinstance(qty, dict):
                        qty = qty.get('quantityInBasket', 1)
                    
                    cart_item = CartItem(
                        product_id=item.get('productId', ''),
                        product_name=item.get('productName', item.get('productId', '')),
                        quantity=int(qty),
                        unit_price=Decimal(str(item.get('unitPrice', '0'))),
                        total_price=Decimal(str(item.get('totalPrice', '0')))
                    )
                    items.append(cart_item)
                except Exception:
                    continue
            
            # Calculer le sous-total
            totals = state.get('totals', {})
            subtotal_data = totals.get('itemPriceAfterPromos', totals.get('itemsRetailPrice', {}))
            subtotal = Decimal(str(subtotal_data.get('amount', '0')))
            
            threshold = state.get('minimumCheckoutThreshold', {})
            
            return Cart(
                id=state.get('cartId', ''),
                items=items,
                subtotal=subtotal,
                currency=subtotal_data.get('currency', 'CAD'),
                minimum_threshold=Decimal(str(threshold.get('amount', '35.00')))
            )
            
        except Exception as e:
            raise VoilaBrowserError(f"Erreur récupération panier: {e}")
    
    def add_item(self, product_id: str, quantity: int = 1) -> Cart:
        """
        Ajoute un produit au panier.
        
        Args:
            product_id: ID du produit à ajouter
            quantity: Quantité (défaut: 1)
        
        Returns:
            Panier mis à jour
        
        Raises:
            VoilaCartError: Si l'ajout échoue
            VoilaProductNotFound: Si le produit n'existe pas
        """
        try:
            self._ensure_browser()
            
            # Pour ajouter un produit, on doit soit:
            # 1. Cliquer sur le bouton "Ajouter" dans les résultats de recherche
            # 2. Utiliser l'API avec les bons tokens
            
            # Approche 1: Naviguer vers la recherche et cliquer
            # On cherche par ID si possible, sinon par la page produit
            
            # Essayer d'aller sur la page produit
            product_url = f"{self.BASE_URL}/products/{product_id}"
            
            try:
                self._page.goto(product_url, wait_until="domcontentloaded", timeout=self.timeout)
            except PlaywrightTimeout:
                pass
            
            self._page.wait_for_timeout(1500)
            
            # Chercher le bouton d'ajout au panier
            add_button = self._page.query_selector('[data-testid="add-to-cart-button"], button:has-text("Add"), button:has-text("Ajouter")')
            
            if not add_button:
                # Si page produit bloquée, on va chercher dans les résultats de recherche
                raise VoilaCartError("Page produit non accessible, utilisez add_item_by_search()")
            
            # Cliquer le nombre de fois nécessaire
            for _ in range(quantity):
                add_button.click()
                self._page.wait_for_timeout(500)
            
            self._save_cookies()
            return self.get_cart()
            
        except VoilaCartError:
            raise
        except Exception as e:
            raise VoilaBrowserError(f"Erreur ajout au panier: {e}")
    
    def add_item_by_search(self, query: str, product_index: int = 0, quantity: int = 1) -> Cart:
        """
        Ajoute un produit au panier via la page de recherche.
        
        Args:
            query: Terme de recherche (ex: "lait 2%")
            product_index: Index du produit dans les résultats (0 = premier)
            quantity: Quantité à ajouter
        
        Returns:
            Panier mis à jour
        
        Raises:
            VoilaCartError: Si l'ajout échoue
        """
        try:
            self._ensure_browser()
            self._navigate_to_search(query)
            
            # Attendre que les produits se chargent
            self._page.wait_for_timeout(3000)
            
            # Stratégie 1: Boutons "Add" avec aria-label contenant "to basket"
            add_buttons = self._page.query_selector_all('button[aria-label*="to basket"], button[aria-label*="au panier"]')
            
            if not add_buttons:
                # Stratégie 2: Chercher les product-card-container et leur bouton
                product_cards = self._page.query_selector_all('.product-card-container')
                if product_cards:
                    add_buttons = []
                    for card in product_cards:
                        btn = card.query_selector('button')
                        if btn:
                            add_buttons.append(btn)
            
            if not add_buttons:
                # Stratégie 3: Boutons avec texte "Add" ou "Ajouter"
                add_buttons = self._page.query_selector_all('button:has-text("Add"):not([aria-label*="Cart"]), button:has-text("Ajouter")')
                # Filtrer ceux qui ne sont pas dans le header
                add_buttons = [b for b in add_buttons if not b.evaluate('el => el.closest("header") !== null')]
            
            if not add_buttons or len(add_buttons) <= product_index:
                raise VoilaCartError(f"Aucun produit trouvé pour '{query}' (trouvé {len(add_buttons) if add_buttons else 0} boutons, index demandé: {product_index})")
            
            button = add_buttons[product_index]
            
            # Récupérer le nom du produit depuis l'aria-label pour le log
            aria_label = button.get_attribute('aria-label') or ""
            product_name = aria_label.replace("Add ", "").replace(" to basket", "").replace("Ajouter ", "").replace(" au panier", "")
            
            # Cliquer pour ajouter
            for i in range(quantity):
                button.click()
                self._page.wait_for_timeout(800)
            
            self._page.wait_for_timeout(1500)
            self._save_cookies()
            
            # Rafraîchir l'état du panier
            self._page.reload()
            self._page.wait_for_timeout(2000)
            
            return self.get_cart()
            
        except VoilaCartError:
            raise
        except Exception as e:
            raise VoilaBrowserError(f"Erreur ajout via recherche: {e}")
    
    def remove_item(self, product_id: str) -> Cart:
        """
        Supprime un produit du panier.
        
        Args:
            product_id: ID du produit à supprimer
        
        Returns:
            Panier mis à jour
        """
        try:
            self._ensure_browser()
            
            # Naviguer vers le panier
            self._page.goto(f"{self.BASE_URL}/cart", wait_until="domcontentloaded", timeout=self.timeout)
            self._page.wait_for_timeout(2000)
            
            # Chercher le produit et son bouton de suppression
            remove_button = self._page.query_selector(f'[data-product-id="{product_id}"] button[aria-label*="Remove"], [data-product-id="{product_id}"] button[aria-label*="Supprimer"]')
            
            if not remove_button:
                # Chercher par autre moyen
                cart_items = self._page.query_selector_all('[data-testid="cart-item"], .cart-item')
                for item in cart_items:
                    item_id = item.get_attribute('data-product-id')
                    if item_id == product_id:
                        remove_btn = item.query_selector('button[aria-label*="Remove"], button[aria-label*="Supprimer"], [data-testid="remove-button"]')
                        if remove_btn:
                            remove_button = remove_btn
                            break
            
            if remove_button:
                remove_button.click()
                self._page.wait_for_timeout(1000)
            
            self._save_cookies()
            return self.get_cart()
            
        except Exception as e:
            raise VoilaBrowserError(f"Erreur suppression: {e}")
    
    def update_quantity(self, product_id: str, quantity: int) -> Cart:
        """
        Met à jour la quantité d'un produit.
        
        Args:
            product_id: ID du produit
            quantity: Nouvelle quantité (0 = supprimer)
        
        Returns:
            Panier mis à jour
        """
        if quantity <= 0:
            return self.remove_item(product_id)
        
        # Pour l'instant, simplification: on supprime et on ré-ajoute
        # Une meilleure implémentation utiliserait les boutons +/-
        try:
            self._ensure_browser()
            
            # Naviguer vers le panier
            self._page.goto(f"{self.BASE_URL}/cart", wait_until="domcontentloaded", timeout=self.timeout)
            self._page.wait_for_timeout(2000)
            
            # Chercher le champ de quantité
            quantity_input = self._page.query_selector(f'[data-product-id="{product_id}"] input[type="number"], [data-product-id="{product_id}"] [data-testid="quantity-input"]')
            
            if quantity_input:
                quantity_input.fill(str(quantity))
                quantity_input.press("Enter")
                self._page.wait_for_timeout(1000)
            
            self._save_cookies()
            return self.get_cart()
            
        except Exception as e:
            raise VoilaBrowserError(f"Erreur mise à jour quantité: {e}")
    
    def clear(self) -> Cart:
        """
        Vide le panier.
        
        Returns:
            Panier vide
        """
        try:
            self._ensure_browser()
            
            # Naviguer vers le panier
            self._page.goto(f"{self.BASE_URL}/cart", wait_until="domcontentloaded", timeout=self.timeout)
            self._page.wait_for_timeout(2000)
            
            # Chercher le bouton "Vider le panier"
            clear_button = self._page.query_selector('button:has-text("Clear"), button:has-text("Vider"), [data-testid="clear-cart"]')
            
            if clear_button:
                clear_button.click()
                # Confirmer si dialog
                confirm = self._page.query_selector('button:has-text("Confirm"), button:has-text("Yes"), button:has-text("Oui")')
                if confirm:
                    confirm.click()
                self._page.wait_for_timeout(1000)
            else:
                # Supprimer un par un
                cart = self.get_cart()
                for item in cart.items:
                    self.remove_item(item.product_id)
            
            self._save_cookies()
            return self.get_cart()
            
        except Exception as e:
            raise VoilaBrowserError(f"Erreur vidage panier: {e}")
    
    def close(self):
        """Ferme le browser"""
        if self._browser:
            self._save_cookies()
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# CLI pour tests
def main():
    """Point d'entrée CLI pour tester le panier"""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Gestion du panier Voilà.ca")
    parser.add_argument("action", choices=["get", "add", "remove", "clear"], help="Action à effectuer")
    parser.add_argument("--query", "-q", help="Terme de recherche (pour add)")
    parser.add_argument("--product-id", "-p", help="ID du produit")
    parser.add_argument("--quantity", "-n", type=int, default=1, help="Quantité")
    parser.add_argument("--index", "-i", type=int, default=0, help="Index du produit dans les résultats")
    parser.add_argument("--session", "-s", default="~/.voila-session.json", help="Fichier de session")
    
    args = parser.parse_args()
    
    with CartManager(session_file=args.session) as cart_mgr:
        if args.action == "get":
            cart = cart_mgr.get_cart()
            print(cart.format_summary())
        
        elif args.action == "add":
            if args.query:
                cart = cart_mgr.add_item_by_search(args.query, args.index, args.quantity)
            elif args.product_id:
                cart = cart_mgr.add_item(args.product_id, args.quantity)
            else:
                print("Erreur: --query ou --product-id requis", file=sys.stderr)
                return 1
            print(cart.format_summary())
        
        elif args.action == "remove":
            if not args.product_id:
                print("Erreur: --product-id requis", file=sys.stderr)
                return 1
            cart = cart_mgr.remove_item(args.product_id)
            print(cart.format_summary())
        
        elif args.action == "clear":
            cart = cart_mgr.clear()
            print("Panier vidé.")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
