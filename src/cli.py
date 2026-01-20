#!/usr/bin/env python3
"""
CLI unifié pour Voilà Assistant

Commandes disponibles:
  search <terme>        Recherche de produits
  cart                  Affiche le panier
  add <terme>           Ajoute un produit au panier
  clear                 Vide le panier
  login                 Se connecter à un compte Voilà
  status                Vérifie le statut de connexion
  lists                 Affiche toutes les listes (auth requise)
  list <nom>            Affiche le contenu d'une liste
  list-search <terme>   Cherche dans toutes les listes
  list-add <nom>        Ajoute une liste entière au panier
  import-cookies        Importe des cookies depuis un fichier JSON
"""

import argparse
import json
import sys
from pathlib import Path

from .search import ProductSearch
from .cart import CartManager
from .lists import ListsManager, format_lists_summary, format_search_results
from .exceptions import VoilaAuthRequired


DEFAULT_SESSION = Path("~/.voila-session.json").expanduser()


def _get_format(args):
    """Retourne le format à utiliser (local ou global)"""
    return getattr(args, 'format', None) or 'table'


def cmd_search(args):
    """Recherche de produits"""
    search = ProductSearch(headless=True)
    fmt = _get_format(args)
    
    # Filter sales only if requested
    if args.sales:
        results = search.search(args.query, args.limit * 2)  # Get more to filter
        sale_results = [p for p in results if p.get('onSale', False)][:args.limit]
        
        if fmt == "json":
            print(json.dumps(sale_results, indent=2, default=str))
        else:
            # Re-format using ProductSearch
            print(f"🏷️ Produits en solde pour '{args.query}':\n")
            for p in sale_results:
                print(f"  • {p.get('name', 'N/A')} — ${p.get('price', 'N/A')}")
        return 0
    
    result = search.search_formatted(args.query, args.limit, fmt)
    print(result)
    return 0


def cmd_cart(args):
    """Affiche le panier"""
    fmt = _get_format(args)
    with CartManager(headless=True, session_file=args.session) as cart_mgr:
        cart = cart_mgr.get_cart()
        
        if fmt == "telegram":
            print(cart.format_telegram())
        elif fmt == "json":
            print(json.dumps([{
                'product_id': i.product_id,
                'product_name': i.product_name,
                'quantity': i.quantity,
                'total_price': str(i.total_price)
            } for i in cart.items], indent=2))
        else:
            print(cart.format_summary())
    
    return 0


def cmd_add(args):
    """Ajoute un produit au panier"""
    fmt = _get_format(args)
    with CartManager(headless=True, session_file=args.session) as cart_mgr:
        print(f"🔍 Recherche: '{args.query}'...", file=sys.stderr)
        
        cart = cart_mgr.add_item_by_search(
            args.query, 
            product_index=args.index, 
            quantity=args.quantity
        )
        
        print(f"✅ Ajouté au panier!", file=sys.stderr)
        
        if fmt == "telegram":
            print(cart.format_telegram())
        else:
            print(cart.format_summary())
    
    return 0


def cmd_clear(args):
    """Vide le panier"""
    fmt = _get_format(args)
    with CartManager(headless=True, session_file=args.session) as cart_mgr:
        cart = cart_mgr.clear()
        print("🗑️ Panier vidé!", file=sys.stderr)
        
        if fmt == "telegram":
            print(cart.format_telegram())
        else:
            print(cart.format_summary())
    
    return 0


def cmd_login(args):
    """Se connecter à un compte Voilà"""
    import os
    
    # Get credentials from args or environment
    email = args.email or os.environ.get('VOILA_EMAIL')
    password = args.password or os.environ.get('VOILA_PASSWORD')
    
    if not email or not password:
        print("❌ Email et mot de passe requis (--email/--password ou VOILA_EMAIL/VOILA_PASSWORD)", file=sys.stderr)
        print("\n💡 Le login automatique peut échouer dû au SSO Gigya.", file=sys.stderr)
        print("   Alternative: utilisez 'import-cookies' après login manuel.", file=sys.stderr)
        return 1
    
    print(f"🔐 Connexion à {email}...", file=sys.stderr)
    
    with CartManager(headless=True, session_file=args.session) as cart_mgr:
        if cart_mgr.login(email, password):
            print("✅ Connecté!", file=sys.stderr)
            return 0
        else:
            print("❌ Échec de connexion (SSO Gigya bloqué?)", file=sys.stderr)
            print("\n💡 Alternative: login manuel puis 'import-cookies'", file=sys.stderr)
            return 1


def cmd_status(args):
    """Vérifie le statut de connexion avec détails de session"""
    from .session import SessionManager
    
    session_mgr = SessionManager(session_file=args.session)
    info = session_mgr.get_session_info()
    
    # Affichage principal
    if info['authenticated']:
        name = info.get('customer_name') or info.get('email') or 'Utilisateur'
        print(f"✅ Connecté en tant que {name}")
    else:
        print("❌ Non connecté (session anonyme)")
    
    # Détails de session
    print(f"\n📊 Session:")
    print(f"   • Cookies: {info['total_cookies']} total, {info['critical_cookies']} critiques")
    
    days = info.get('days_remaining')
    if days is not None:
        if days < 1:
            print(f"   • ⚠️ Session expire dans moins de 24h! Utilisez 'refresh'")
        elif days < 3:
            print(f"   • ⚠️ Session expire dans {days}j - pensez à 'refresh'")
        else:
            print(f"   • Session valide: {days}j restants")
    
    if info.get('last_activity'):
        print(f"   • Dernière activité: {info['last_activity'][:19]}")
    
    # Conseils
    if not info['authenticated']:
        print("\n💡 Pour accéder aux listes:")
        print("   1. Connectez-vous sur voila.ca dans votre navigateur")
        print("   2. Exportez vos cookies (extension EditThisCookie)")
        print("   3. ./voila import-cookies ~/cookies.json")
    
    return 0


def cmd_import_cookies(args):
    """Importe des cookies depuis un fichier JSON"""
    from .session import SessionManager
    
    import_path = Path(args.file).expanduser()
    
    if not import_path.exists():
        print(f"❌ Fichier non trouvé: {import_path}", file=sys.stderr)
        return 1
    
    try:
        session_mgr = SessionManager(session_file=args.session)
        count, message = session_mgr.import_cookies(import_path)
        
        print(f"✅ {message}", file=sys.stderr)
        
        # Valider la session
        status = session_mgr.validate_session(force=True)
        
        if status.authenticated:
            name = status.customer_name or status.email
            print(f"✅ Session valide - connecté en tant que {name}", file=sys.stderr)
        else:
            print("⚠️ Cookies importés mais session non authentifiée", file=sys.stderr)
            print("   Les fonctionnalités de base fonctionneront.", file=sys.stderr)
        
        return 0
        
    except json.JSONDecodeError:
        print("❌ Le fichier n'est pas un JSON valide", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Erreur: {e}", file=sys.stderr)
        return 1


def cmd_refresh(args):
    """Rafraîchit la session en accédant au site"""
    from .session import SessionManager
    
    print("🔄 Rafraîchissement de la session...", file=sys.stderr)
    
    session_mgr = SessionManager(session_file=args.session)
    
    # Status avant
    status_before = session_mgr.validate_session()
    
    # Refresh
    if session_mgr.refresh_session():
        # Status après
        status_after = session_mgr.validate_session(force=True)
        
        print("✅ Session rafraîchie!", file=sys.stderr)
        
        if status_after.authenticated:
            name = status_after.customer_name or status_after.email
            print(f"   • Connecté: {name}", file=sys.stderr)
        
        # Afficher les cookies mis à jour
        info = session_mgr.get_session_info()
        print(f"   • Cookies: {info['total_cookies']}", file=sys.stderr)
        if info.get('earliest_expiry'):
            print(f"   • Prochaine expiration: {info['earliest_expiry'][:10]}", file=sys.stderr)
        
        return 0
    else:
        print("❌ Échec du rafraîchissement", file=sys.stderr)
        return 1


def cmd_lists(args):
    """Affiche toutes les listes"""
    fmt = _get_format(args)
    lists_mgr = ListsManager(session_file=args.session)
    
    try:
        lists = lists_mgr.get_lists()
        
        if fmt == "json":
            print(json.dumps([{
                'id': l.id,
                'name': l.name,
                'item_count': l.item_count
            } for l in lists], indent=2))
        elif fmt == "telegram":
            if not lists:
                print("📋 Aucune liste trouvée")
            else:
                lines = ["<b>📋 Vos listes de courses</b>\n"]
                for i, lst in enumerate(lists, 1):
                    lines.append(f"{i}. <b>{lst.name}</b> ({lst.item_count} articles)")
                print("\n".join(lines))
        else:
            print(format_lists_summary(lists))
        
        return 0
        
    except VoilaAuthRequired:
        print("❌ Authentification requise pour accéder aux listes", file=sys.stderr)
        print("\n💡 Utilisez 'login' ou 'import-cookies' pour vous connecter", file=sys.stderr)
        return 1


def cmd_list(args):
    """Affiche le contenu d'une liste"""
    fmt = _get_format(args)
    lists_mgr = ListsManager(session_file=args.session)
    
    try:
        lst = lists_mgr.get_list_by_name(args.name)
        
        if not lst:
            print(f"❌ Liste '{args.name}' non trouvée", file=sys.stderr)
            return 1
        
        # Filter sales only if requested
        if args.sales:
            sale_items = lst.get_sale_items()
            if not sale_items:
                print(f"📋 Aucun article en solde dans '{lst.name}'")
                return 0
            
            if fmt == "json":
                print(json.dumps([{
                    'product_id': i.product_id,
                    'product_name': i.product_name,
                    'price': str(i.price) if i.price else None,
                    'original_price': str(i.original_price) if i.original_price else None
                } for i in sale_items], indent=2))
            else:
                lines = [f"🏷️ Articles en solde dans '{lst.name}':\n"]
                for item in sale_items:
                    line = f"  • {item.product_name}"
                    if item.price and item.original_price:
                        line += f" — ${item.price} (était ${item.original_price})"
                    lines.append(line)
                print("\n".join(lines))
            return 0
        
        if fmt == "json":
            print(json.dumps({
                'id': lst.id,
                'name': lst.name,
                'items': [{
                    'product_id': i.product_id,
                    'product_name': i.product_name,
                    'quantity': i.quantity,
                    'price': str(i.price) if i.price else None,
                    'on_sale': i.on_sale
                } for i in lst.items]
            }, indent=2))
        elif fmt == "telegram":
            print(lst.format_telegram())
        else:
            print(lst.format_detailed())
        
        return 0
        
    except VoilaAuthRequired:
        print("❌ Authentification requise", file=sys.stderr)
        return 1


def cmd_list_search(args):
    """Recherche dans toutes les listes"""
    fmt = _get_format(args)
    lists_mgr = ListsManager(session_file=args.session)
    
    try:
        results = lists_mgr.search_in_lists(args.query)
        
        if fmt == "json":
            print(json.dumps([{
                'list_name': r['list_name'],
                'list_id': r['list_id'],
                'product_name': r['item'].product_name,
                'price': str(r['item'].price) if r['item'].price else None,
                'on_sale': r['item'].on_sale
            } for r in results], indent=2))
        else:
            print(format_search_results(results))
        
        return 0
        
    except VoilaAuthRequired:
        print("❌ Authentification requise", file=sys.stderr)
        return 1


def cmd_list_add(args):
    """Ajoute tous les articles d'une liste au panier"""
    fmt = _get_format(args)
    lists_mgr = ListsManager(session_file=args.session)
    
    try:
        lst = lists_mgr.get_list_by_name(args.name)
        
        if not lst:
            print(f"❌ Liste '{args.name}' non trouvée", file=sys.stderr)
            return 1
        
        print(f"📋 Ajout de '{lst.name}' ({lst.item_count} articles) au panier...", file=sys.stderr)
        
        with CartManager(headless=True, session_file=args.session) as cart_mgr:
            result = lists_mgr.add_list_to_cart(lst.id, cart_mgr)
            
            if fmt == "json":
                print(json.dumps(result, indent=2))
            else:
                print(f"\n✅ {result['total_added']} articles ajoutés")
                if result['errors']:
                    print(f"⚠️ {result['total_errors']} erreurs:")
                    for err in result['errors']:
                        print(f"   • {err['product']}: {err['error']}")
                
                # Show updated cart
                cart = cart_mgr.get_cart()
                print(f"\n{cart.format_summary()}")
        
        return 0
        
    except VoilaAuthRequired:
        print("❌ Authentification requise", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(
        prog="voila",
        description="Assistant pour les commandes d'épicerie sur Voilà.ca",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  voila search "lait 2%"              Recherche de produits
  voila add "pain blanc" -q 2         Ajouter 2 pains au panier
  voila cart                          Voir le panier
  voila lists                         Voir toutes les listes (auth requise)
  voila list "Épicerie" --sales       Articles en solde de la liste
  voila list-add "Épicerie"           Ajouter toute la liste au panier
        """
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
    search_parser.add_argument("--sales", action="store_true", help="Afficher seulement les produits en solde")
    search_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    search_parser.set_defaults(func=cmd_search)
    
    # cart
    cart_parser = subparsers.add_parser("cart", help="Affiche le panier")
    cart_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    cart_parser.set_defaults(func=cmd_cart)
    
    # add
    add_parser = subparsers.add_parser("add", help="Ajoute un produit au panier")
    add_parser.add_argument("query", help="Terme de recherche du produit")
    add_parser.add_argument("-i", "--index", type=int, default=0, help="Index du produit (0 = premier)")
    add_parser.add_argument("-q", "--quantity", type=int, default=1, help="Quantité à ajouter")
    add_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    add_parser.set_defaults(func=cmd_add)
    
    # clear
    clear_parser = subparsers.add_parser("clear", help="Vide le panier")
    clear_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    clear_parser.set_defaults(func=cmd_clear)
    
    # login
    login_parser = subparsers.add_parser("login", help="Se connecter à un compte Voilà")
    login_parser.add_argument("--email", "-e", help="Email du compte (ou VOILA_EMAIL)")
    login_parser.add_argument("--password", "-p", help="Mot de passe (ou VOILA_PASSWORD)")
    login_parser.set_defaults(func=cmd_login)
    
    # status
    status_parser = subparsers.add_parser("status", help="Vérifie le statut de connexion")
    status_parser.set_defaults(func=cmd_status)
    
    # import-cookies
    import_parser = subparsers.add_parser("import-cookies", help="Importe des cookies depuis un fichier")
    import_parser.add_argument("file", help="Fichier JSON contenant les cookies")
    import_parser.set_defaults(func=cmd_import_cookies)
    
    # lists (show all lists)
    lists_parser = subparsers.add_parser("lists", help="Affiche toutes les listes (auth requise)")
    lists_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    lists_parser.set_defaults(func=cmd_lists)
    
    # list <name> (show one list)
    list_parser = subparsers.add_parser("list", help="Affiche le contenu d'une liste")
    list_parser.add_argument("name", help="Nom de la liste")
    list_parser.add_argument("--sales", action="store_true", help="Afficher seulement les articles en solde")
    list_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    list_parser.set_defaults(func=cmd_list)
    
    # list-search <query>
    list_search_parser = subparsers.add_parser("list-search", help="Recherche dans toutes les listes")
    list_search_parser.add_argument("query", help="Terme de recherche")
    list_search_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    list_search_parser.set_defaults(func=cmd_list_search)
    
    # list-add <name>
    list_add_parser = subparsers.add_parser("list-add", help="Ajoute une liste entière au panier")
    list_add_parser.add_argument("name", help="Nom de la liste")
    list_add_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    list_add_parser.set_defaults(func=cmd_list_add)
    
    # refresh
    refresh_parser = subparsers.add_parser("refresh", help="Rafraîchit la session (renouvelle les cookies)")
    refresh_parser.set_defaults(func=cmd_refresh)
    
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
