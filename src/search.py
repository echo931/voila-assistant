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

    def get_subcategories(self, category_path: str, category_id: str = None) -> List[dict]:
        """
        Get subcategories for a given category path. Works at any depth.
        
        Args:
            category_path: Category path like 'dairy-eggs' or 'dairy-eggs/milk'
            category_id: Optional ID if known (speeds up lookup)
            
        Returns:
            List of subcategories with name, slug, id, url, full_path
        """
        parts = category_path.strip('/').split('/')
        
        # If we have the ID, use it directly
        if category_id:
            current_url = f"{self.BASE_URL}/categories/{category_path}/{category_id}"
        else:
            # Find the category by navigating through the tree
            base_categories = self.get_categories()
            
            # Find first level
            current_url = None
            for cat in base_categories:
                if cat['slug'] == parts[0]:
                    current_url = f"{self.BASE_URL}/categories/{cat['slug']}/{cat['id']}"
                    break
            
            if not current_url:
                return []
            
            # Navigate deeper if needed
            for i, part in enumerate(parts[1:], 1):
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=self.headless)
                        page = browser.new_page()
                        page.goto(current_url, wait_until="domcontentloaded", timeout=self.timeout)
                        page.wait_for_timeout(2000)
                        
                        # Find the subcategory link that matches this part
                        current_path = '/'.join(parts[:i])
                        sub_info = page.evaluate(f'''
                            () => {{
                                const links = document.querySelectorAll('a[href*="/categories/"]');
                                for (const link of links) {{
                                    const href = link.getAttribute('href');
                                    // Look for pattern: /categories/.../part/ID
                                    const pattern = /\\/categories\\/{current_path}\\/({part})\\/([A-Z0-9]+)/;
                                    const match = href.match(pattern);
                                    if (match) {{
                                        return {{
                                            slug: match[1],
                                            id: match[2],
                                            url: href.split('?')[0]
                                        }};
                                    }}
                                }}
                                return null;
                            }}
                        ''')
                        browser.close()
                        
                        if sub_info:
                            current_url = f"{self.BASE_URL}{sub_info['url']}" if sub_info['url'].startswith('/') else sub_info['url']
                        else:
                            return []  # Path not found
                except Exception:
                    return []
        
        # Now fetch subcategories from the target URL
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(user_agent=self.DEFAULT_USER_AGENT)
                page = context.new_page()
                
                page.goto(current_url, wait_until="domcontentloaded", timeout=self.timeout)
                page.wait_for_timeout(2000)
                
                # Extract ALL subcategory links (any depth below current)
                base_path = category_path
                subcategories = page.evaluate(f'''
                    () => {{
                        const links = document.querySelectorAll('a[href*="/categories/"]');
                        const seen = new Set();
                        const results = [];
                        const basePath = "{base_path}";
                        
                        for (const link of links) {{
                            const href = link.getAttribute('href');
                            // Match any path that starts with basePath and has one more level
                            // Pattern: /categories/basePath/slug/ID
                            const escapedBase = basePath.replace(/\\//g, '\\\\/');
                            const pattern = new RegExp('/categories/' + escapedBase + '/([^/?]+)/([A-Z0-9]+)');
                            const match = href.match(pattern);
                            if (match && !seen.has(match[2])) {{
                                seen.add(match[2]);
                                const name = link.textContent?.trim() || match[1].replace(/-/g, ' ');
                                results.push({{
                                    name: name,
                                    slug: match[1],
                                    id: match[2],
                                    url: href.split('?')[0],
                                    full_path: basePath + '/' + match[1]
                                }});
                            }}
                        }}
                        return results;
                    }}
                ''')
                
                browser.close()
                return subcategories
                
        except Exception as e:
            raise VoilaBrowserError(f"Erreur récupération sous-catégories: {e}")

    def browse_category(
        self, 
        category_slug: str, 
        category_id: str, 
        max_results: int = 20
    ) -> List[Product]:
        """
        Browse products in a category.
        
        Args:
            category_slug: Category slug or path (e.g., 'dairy-eggs' or 'dairy-eggs/milk/flavoured-milk')
            category_id: Category ID (e.g., 'WEB1100610'), can be empty if slug is a full path
            max_results: Maximum products to return
            
        Returns:
            List of products in the category
        """
        # Handle nested paths like 'dairy-eggs/milk/flavoured-milk'
        if '/' in category_slug:
            category_url = f"{self.BASE_URL}/categories/{category_slug}/{category_id}" if category_id else None
            if not category_url:
                # Try to resolve the path
                parts = category_slug.split('/')
                # Build URL dynamically - we need the ID for each level
                # For now, just construct the URL and hope it works
                category_url = f"{self.BASE_URL}/categories/{category_slug}"
        else:
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
