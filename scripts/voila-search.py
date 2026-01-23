#!/home/echo/scripts/voila-venv/bin/python3
"""
Script de recherche de produits sur Voilà.ca
Extrait les produits, caractéristiques et prix via Playwright
"""

import json
import sys
import argparse
from urllib.parse import quote

def search_voila(query: str, max_results: int = 20) -> list:
    """
    Recherche des produits sur Voilà.ca
    
    Args:
        query: Terme de recherche
        max_results: Nombre max de résultats à retourner
    
    Returns:
        Liste de produits avec leurs détails
    """
    from playwright.sync_api import sync_playwright
    
    search_url = f"https://voila.ca/search?q={quote(query)}"
    print(f"🔍 Recherche: '{query}' sur Voilà.ca...", file=sys.stderr)
    
    products = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("⏳ Chargement de la page...", file=sys.stderr)
        try:
            page.goto(search_url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print(f"⚠️ Timeout, on continue quand même...", file=sys.stderr)
        
        # Attendre un peu pour les données dynamiques
        page.wait_for_timeout(2000)
        
        # Extraire les données
        print("📦 Extraction des données...", file=sys.stderr)
        data = page.evaluate('''
            () => {
                const state = window.__INITIAL_STATE__;
                if (!state || !state.data || !state.data.products || !state.data.products.productEntities) {
                    return { error: "No data found", debug: Object.keys(window).filter(k => k.startsWith('__')) };
                }
                
                const entities = state.data.products.productEntities;
                const products = [];
                
                for (const [id, product] of Object.entries(entities)) {
                    if (product && product.name && product.price) {
                        products.push({
                            id: id,
                            name: product.name,
                            brand: product.brand || null,
                            size: product.size ? product.size.value : null,
                            price: product.price.current ? product.price.current.amount : null,
                            currency: product.price.current ? product.price.current.currency : "CAD",
                            unit_price: product.price.unit && product.price.unit.current ? product.price.unit.current.amount : null,
                            unit_label: product.price.unit ? product.price.unit.label : null,
                            available: product.status === "AVAILABLE",
                            category: product.department || null
                        });
                    }
                }
                
                return { products: products, count: products.length };
            }
        ''')
        
        browser.close()
        
        if "error" in data:
            print(f"⚠️ {data['error']}", file=sys.stderr)
            if "debug" in data:
                print(f"   Variables globales: {data['debug']}", file=sys.stderr)
            return []
        
        products = data.get("products", [])
        print(f"✓ {len(products)} produits trouvés", file=sys.stderr)
        
    return products[:max_results]


def format_results(products: list, format_type: str = "table") -> str:
    """Formate les résultats pour affichage"""
    
    if not products:
        return "Aucun produit trouvé."
    
    if format_type == "json":
        return json.dumps(products, indent=2, ensure_ascii=False)
    
    elif format_type == "table":
        lines = []
        lines.append(f"{'Produit':<50} {'Taille':<8} {'Prix':<8} {'Prix unitaire':<18}")
        lines.append("=" * 86)
        
        for p in products:
            name = p.get('name', 'N/A')[:48]
            size = p.get('size', '-') or '-'
            price = f"${p.get('price', 'N/A')}" if p.get('price') else 'N/A'
            
            # Formater le prix unitaire avec son unité
            unit_price = p.get('unit_price', '')
            unit_label = p.get('unit_label', '')
            if unit_price and unit_label:
                # Convertir les labels en format lisible
                unit_text = unit_label.replace('fop.price.per.', '').replace('100gram', '100g').replace('100ml', '100ml').replace('each', 'unité')
                unit = f"${unit_price}/{unit_text}"
            elif unit_price:
                unit = f"${unit_price}"
            else:
                unit = '-'
            
            lines.append(f"{name:<50} {size:<8} {price:<8} {unit:<18}")
        
        lines.append("=" * 86)
        lines.append(f"Total: {len(products)} produits")
        
        return "\n".join(lines)
    
    elif format_type == "markdown":
        lines = []
        lines.append(f"## Résultats de recherche ({len(products)} produits)\n")
        lines.append("| Produit | Marque | Taille | Prix | Prix unitaire |")
        lines.append("|---------|--------|--------|------|---------------|")
        
        for p in products:
            name = p.get('name', 'N/A').replace('|', '/')
            brand = p.get('brand', '-') or '-'
            size = p.get('size', '-') or '-'
            price = f"${p.get('price', 'N/A')}" if p.get('price') else 'N/A'
            
            # Prix unitaire avec unité
            unit_price = p.get('unit_price', '')
            unit_label = p.get('unit_label', '')
            if unit_price and unit_label:
                unit_text = unit_label.replace('fop.price.per.', '').replace('100gram', '100g').replace('100ml', '100ml').replace('each', 'unité')
                unit = f"${unit_price}/{unit_text}"
            elif unit_price:
                unit = f"${unit_price}"
            else:
                unit = '-'
            
            lines.append(f"| {name} | {brand} | {size} | {price} | {unit} |")
        
        return "\n".join(lines)
    
    elif format_type == "telegram":
        # Format optimisé pour Telegram (HTML)
        lines = []
        lines.append(f"<b>🛒 Résultats Voilà ({len(products)} produits)</b>\n")
        
        for p in products[:15]:  # Limiter pour Telegram
            name = p.get('name', 'N/A')
            price = p.get('price', 'N/A')
            size = p.get('size', '')
            unit_price = p.get('unit_price', '')
            unit_label = p.get('unit_label', '')
            
            line = f"• <b>{name}</b>"
            if size:
                line += f" ({size})"
            line += f"\n   💰 ${price}"
            
            if unit_price and unit_label:
                unit_text = unit_label.replace('fop.price.per.', '').replace('100gram', '100g').replace('100ml', '100ml').replace('each', 'unité')
                line += f" — ${unit_price}/{unit_text}"
            elif unit_price:
                line += f" — ${unit_price}/unité"
            
            lines.append(line)
        
        if len(products) > 15:
            lines.append(f"\n<i>... et {len(products) - 15} autres produits</i>")
        
        return "\n".join(lines)
    
    else:
        # Simple list
        lines = []
        for p in products:
            name = p.get('name', 'N/A')
            price = f"${p.get('price', 'N/A')}" if p.get('price') else 'N/A'
            size = p.get('size', '') or ''
            brand = p.get('brand', '') or ''
            
            line = f"• {name}"
            if size:
                line += f" ({size})"
            line += f" - {price}"
            
            lines.append(line)
        
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Recherche de produits sur Voilà.ca",
        epilog="Exemples:\n  voila-search.py 'lait 2%%'\n  voila-search.py bananes -f json\n  voila-search.py pain -n 10 -f markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "query",
        help="Terme de recherche (ex: 'lait 2%%', 'pain', 'bananes')"
    )
    parser.add_argument(
        "-n", "--max-results",
        type=int,
        default=20,
        help="Nombre maximum de résultats (défaut: 20)"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["table", "json", "markdown", "list", "telegram"],
        default="table",
        help="Format de sortie (défaut: table)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Fichier de sortie (défaut: stdout)"
    )
    
    args = parser.parse_args()
    
    # Recherche
    products = search_voila(args.query, args.max_results)
    
    # Formatage
    output = format_results(products, args.format)
    
    # Sortie
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✓ Résultats sauvegardés dans {args.output}", file=sys.stderr)
    else:
        print(output)
    
    return 0 if products else 1


if __name__ == "__main__":
    sys.exit(main())
