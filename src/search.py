"""
Module de recherche de produits sur Voilà.ca
"""

import sys
from typing import List, Optional
from urllib.parse import quote
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from .models import Product
from .exceptions import VoilaBrowserError


class ProductSearch:
    """Recherche de produits sur Voilà.ca via browser automation"""
    
    BASE_URL = "https://voila.ca"
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialise le moteur de recherche.
        
        Args:
            headless: True pour mode sans interface graphique
            timeout: Timeout en millisecondes
        """
        self.headless = headless
        self.timeout = timeout
    
    def search(self, query: str, max_results: int = 20) -> List[Product]:
        """
        Recherche des produits sur Voilà.ca
        
        Args:
            query: Terme de recherche (ex: "lait 2%", "bananes")
            max_results: Nombre maximum de résultats à retourner
        
        Returns:
            Liste de produits trouvés
        
        Raises:
            VoilaBrowserError: En cas d'erreur browser
        """
        search_url = f"{self.BASE_URL}/search?q={quote(query)}"
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(user_agent=self.DEFAULT_USER_AGENT)
                page = context.new_page()
                
                # Naviguer vers la page de recherche
                try:
                    page.goto(search_url, wait_until="networkidle", timeout=self.timeout)
                except PlaywrightTimeout:
                    # Continuer même si networkidle timeout
                    pass
                
                # Attendre un peu pour les données dynamiques
                page.wait_for_timeout(2000)
                
                # Extraire les données produits
                data = page.evaluate('''
                    () => {
                        const state = window.__INITIAL_STATE__;
                        if (!state || !state.data || !state.data.products || !state.data.products.productEntities) {
                            return { error: "No product data found" };
                        }
                        
                        const entities = state.data.products.productEntities;
                        const products = [];
                        
                        for (const [id, product] of Object.entries(entities)) {
                            if (product && product.name && product.price) {
                                // Pass the full nested structure for from_api_response
                                products.push({
                                    id: id,
                                    name: product.name,
                                    brand: product.brand || null,
                                    size: product.size || null,
                                    price: product.price || {},
                                    status: product.status || "AVAILABLE",
                                    department: product.department || null,
                                    images: product.images || []
                                });
                            }
                        }
                        
                        return { products: products };
                    }
                ''')
                
                browser.close()
                
                if "error" in data:
                    return []
                
                # Convertir en objets Product
                products = []
                for item in data.get("products", [])[:max_results]:
                    try:
                        product = Product.from_api_response(item)
                        products.append(product)
                    except Exception:
                        continue
                
                return products
                
        except Exception as e:
            raise VoilaBrowserError(f"Erreur lors de la recherche: {e}")
    
    def search_formatted(
        self, 
        query: str, 
        max_results: int = 20,
        format_type: str = "table"
    ) -> str:
        """
        Recherche et retourne les résultats formatés.
        
        Args:
            query: Terme de recherche
            max_results: Nombre max de résultats
            format_type: Format de sortie (table, telegram, json)
        
        Returns:
            Résultats formatés en string
        """
        products = self.search(query, max_results)
        
        if not products:
            return "Aucun produit trouvé."
        
        if format_type == "telegram":
            return self._format_telegram(products)
        elif format_type == "json":
            import json
            return json.dumps([p.to_dict() for p in products], indent=2, ensure_ascii=False)
        else:
            return self._format_table(products)
    
    def _format_table(self, products: List[Product]) -> str:
        """Formate les produits en table"""
        lines = []
        lines.append(f"{'Produit':<50} {'Taille':<8} {'Prix':<8} {'Prix unitaire':<18}")
        lines.append("=" * 86)
        
        for p in products:
            lines.append(p.format_table_row())
        
        lines.append("=" * 86)
        lines.append(f"Total: {len(products)} produits")
        
        return "\n".join(lines)
    
    def _format_telegram(self, products: List[Product]) -> str:
        """Formate les produits pour Telegram (HTML)"""
        lines = [f"<b>🛒 Résultats Voilà ({len(products)} produits)</b>\n"]
        
        for p in products[:15]:
            lines.append(p.format_telegram())
        
        if len(products) > 15:
            lines.append(f"\n<i>... et {len(products) - 15} autres produits</i>")
        
        return "\n".join(lines)

    def get_categories(self) -> List[dict]:
        """
        Récupère la liste des catégories disponibles.
        
        Returns:
            Liste de dicts avec 'name', 'slug', 'id', 'url'
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(user_agent=self.DEFAULT_USER_AGENT)
                page = context.new_page()
                
                page.goto(f"{self.BASE_URL}/categories", wait_until="domcontentloaded", timeout=self.timeout)
                page.wait_for_timeout(2000)
                
                # Extract category links
                categories = page.evaluate('''
                    () => {
                        const links = document.querySelectorAll('a[href*="/categories/"]');
                        const seen = new Set();
                        const results = [];
                        
                        for (const link of links) {
                            const href = link.getAttribute('href');
                            // Match /categories/slug/ID pattern
                            const match = href.match(/\\/categories\\/([^\\/]+)\\/([A-Z0-9]+)/);
                            if (match && !seen.has(match[2])) {
                                seen.add(match[2]);
                                const name = link.textContent?.trim() || match[1].replace(/-/g, ' ');
                                results.push({
                                    name: name,
                                    slug: match[1],
                                    id: match[2],
                                    url: href
                                });
                            }
                        }
                        return results;
                    }
                ''')
                
                browser.close()
                return categories
                
        except Exception as e:
            raise VoilaBrowserError(f"Erreur récupération catégories: {e}")

    def browse_category(
        self, 
        category_slug: str, 
        category_id: str, 
        max_results: int = 20
    ) -> List[Product]:
        """
        Browse products in a category.
        
        Args:
            category_slug: Category slug (e.g., 'dairy-eggs')
            category_id: Category ID (e.g., 'WEB1100610')
            max_results: Maximum products to return
            
        Returns:
            List of products in the category
        """
        category_url = f"{self.BASE_URL}/categories/{category_slug}/{category_id}"
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(user_agent=self.DEFAULT_USER_AGENT)
                page = context.new_page()
                
                try:
                    page.goto(category_url, wait_until="domcontentloaded", timeout=self.timeout)
                except PlaywrightTimeout:
                    pass
                
                # Wait for products to load
                page.wait_for_timeout(3000)
                
                page.wait_for_timeout(2000)
                
                # Extract product data (category pages have different structure than search)
                data = page.evaluate('''
                    () => {
                        const state = window.__INITIAL_STATE__;
                        if (!state || !state.data || !state.data.products || !state.data.products.productEntities) {
                            return { error: "No product data found" };
                        }
                        
                        const entities = state.data.products.productEntities;
                        const products = [];
                        
                        for (const [id, product] of Object.entries(entities)) {
                            if (product && product.name) {
                                // Category pages use different field names than search
                                const price = product.price?.current?.amount || product.price?.amount || 0;
                                const unitPrice = product.price?.unit?.current?.amount || product.comparisonPrice?.amount || null;
                                const unitLabel = product.price?.unit?.label || product.comparisonPrice?.unit || "";
                                const size = product.size?.value || product.packageSize || "";
                                const imageUrl = product.image?.src || product.images?.[0]?.url || null;
                                const inStock = product.available !== false && product.inventoryStatus !== "OUT_OF_STOCK";
                                
                                products.push({
                                    id: product.productId || id,
                                    name: product.name,
                                    brand: product.brand || "",
                                    price: parseFloat(price) || 0,
                                    unit_price: unitPrice ? parseFloat(unitPrice) : null,
                                    unit_price_label: unitLabel,
                                    size: size,
                                    image_url: imageUrl,
                                    in_stock: inStock,
                                    on_sale: !!product.offers?.length || !!product.price?.was,
                                    sale_price: product.price?.was?.amount ? parseFloat(product.price.was.amount) : null
                                });
                            }
                        }
                        
                        return { products };
                    }
                ''')
                
                browser.close()
                
                if "error" in data:
                    return []
                
                products = []
                for item in data.get("products", [])[:max_results]:
                    try:
                        from decimal import Decimal
                        product = Product(
                            id=item["id"],
                            name=item["name"],
                            brand=item.get("brand", ""),
                            price=Decimal(str(item["price"])) if item.get("price") else None,
                            unit_price=Decimal(str(item["unit_price"])) if item.get("unit_price") else None,
                            unit_label=item.get("unit_price_label", ""),
                            size=item.get("size", ""),
                            image_url=item.get("image_url"),
                            available=item.get("in_stock", True),
                        )
                        products.append(product)
                    except Exception as e:
                        continue
                
                return products
                
        except Exception as e:
            raise VoilaBrowserError(f"Erreur navigation catégorie: {e}")

    def browse_category_formatted(
        self,
        category_slug: str,
        category_id: str,
        max_results: int = 20,
        format_type: str = "table"
    ) -> str:
        """Browse category and return formatted results."""
        products = self.browse_category(category_slug, category_id, max_results)
        
        if format_type == "json":
            import json
            return json.dumps([p.__dict__ for p in products], indent=2, ensure_ascii=False)
        elif format_type == "telegram":
            return self._format_telegram(products)
        else:
            return self._format_table(products)


# CLI pour tests
def main():
    """Point d'entrée CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Recherche de produits sur Voilà.ca")
    parser.add_argument("query", help="Terme de recherche")
    parser.add_argument("-n", "--max-results", type=int, default=20)
    parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default="table")
    
    args = parser.parse_args()
    
    search = ProductSearch()
    print(f"🔍 Recherche: '{args.query}'...", file=sys.stderr)
    
    result = search.search_formatted(args.query, args.max_results, args.format)
    print(result)


if __name__ == "__main__":
    main()
