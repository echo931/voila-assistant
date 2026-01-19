#!/usr/bin/env python3
"""
CLI unifié pour Voilà Assistant
"""

import argparse
import sys
from pathlib import Path

from .search import ProductSearch
from .cart import CartManager


DEFAULT_SESSION = Path("~/.voila-session.json").expanduser()


def cmd_search(args):
    """Recherche de produits"""
    search = ProductSearch(headless=True)
    
    if args.format == "telegram":
        result = search.search_formatted(args.query, args.limit, "telegram")
    elif args.format == "json":
        result = search.search_formatted(args.query, args.limit, "json")
    else:
        result = search.search_formatted(args.query, args.limit, "table")
    
    print(result)
    return 0


def cmd_cart(args):
    """Affiche le panier"""
    with CartManager(headless=True, session_file=args.session) as cart_mgr:
        cart = cart_mgr.get_cart()
        
        if args.format == "telegram":
            print(cart.format_telegram())
        else:
            print(cart.format_summary())
    
    return 0


def cmd_add(args):
    """Ajoute un produit au panier"""
    with CartManager(headless=True, session_file=args.session) as cart_mgr:
        print(f"🔍 Recherche: '{args.query}'...", file=sys.stderr)
        
        cart = cart_mgr.add_item_by_search(
            args.query, 
            product_index=args.index, 
            quantity=args.quantity
        )
        
        print(f"✅ Ajouté au panier!", file=sys.stderr)
        
        if args.format == "telegram":
            print(cart.format_telegram())
        else:
            print(cart.format_summary())
    
    return 0


def cmd_clear(args):
    """Vide le panier"""
    with CartManager(headless=True, session_file=args.session) as cart_mgr:
        cart = cart_mgr.clear()
        print("🗑️ Panier vidé!", file=sys.stderr)
        print(cart.format_summary())
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="voila",
        description="Assistant pour les commandes d'épicerie sur Voilà.ca"
    )
    parser.add_argument(
        "--session", "-s",
        default=str(DEFAULT_SESSION),
        help=f"Fichier de session (défaut: {DEFAULT_SESSION})"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["table", "telegram", "json"],
        default="table",
        help="Format de sortie"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")
    
    # search
    search_parser = subparsers.add_parser("search", help="Recherche de produits")
    search_parser.add_argument("query", help="Terme de recherche")
    search_parser.add_argument("-n", "--limit", type=int, default=10, help="Nombre max de résultats")
    search_parser.set_defaults(func=cmd_search)
    
    # cart
    cart_parser = subparsers.add_parser("cart", help="Affiche le panier")
    cart_parser.set_defaults(func=cmd_cart)
    
    # add
    add_parser = subparsers.add_parser("add", help="Ajoute un produit au panier")
    add_parser.add_argument("query", help="Terme de recherche du produit")
    add_parser.add_argument("-i", "--index", type=int, default=0, help="Index du produit (0 = premier)")
    add_parser.add_argument("-q", "--quantity", type=int, default=1, help="Quantité à ajouter")
    add_parser.set_defaults(func=cmd_add)
    
    # clear
    clear_parser = subparsers.add_parser("clear", help="Vide le panier")
    clear_parser.set_defaults(func=cmd_clear)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrompu.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"❌ Erreur: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
