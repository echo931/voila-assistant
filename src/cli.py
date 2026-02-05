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
from .local_cart import LocalCartManager
from .needs import NeedsManager
from .preferences import PreferencesManager
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


def cmd_categories(args):
    """Liste les catégories disponibles"""
    from .category_cache import CategoryCache
    
    cache = CategoryCache()
    fmt = _get_format(args)
    
    # Refresh cache if requested
    if args.refresh:
        depth = getattr(args, 'depth', 3)
        print(f"📂 Crawling de l'arbre (profondeur {depth})...", file=sys.stderr)
        print("   ⏳ Première sync lente (~2-3 min), refresh nocturne ensuite", file=sys.stderr)
        
        def on_progress(msg):
            print(f"  {msg}", file=sys.stderr)
        
        count = cache.refresh(on_progress=on_progress, max_depth=depth)
        print(f"✅ {count} catégories indexées", file=sys.stderr)
    
    # Cache is empty - show friendly message
    elif not cache.categories:
        print("📂 Cache vide — première sync requise", file=sys.stderr)
        print("   ⏳ Cette opération prend ~2-3 min (crawl complet de l'arbre Voilà)", file=sys.stderr)
        print("   🌙 Ensuite refresh automatique chaque nuit", file=sys.stderr)
        print("", file=sys.stderr)
        
        # Ask to proceed
        if fmt != "json":
            try:
                response = input("   Lancer maintenant? [O/n] ").strip().lower()
                if response in ('', 'o', 'y', 'oui', 'yes'):
                    depth = getattr(args, 'depth', 3)
                    print(f"\n📂 Crawling (profondeur {depth})...", file=sys.stderr)
                    
                    def on_progress(msg):
                        print(f"  {msg}", file=sys.stderr)
                    
                    count = cache.refresh(on_progress=on_progress, max_depth=depth)
                    print(f"✅ {count} catégories indexées", file=sys.stderr)
                else:
                    print("\n💡 Pour lancer plus tard: voila categories --refresh", file=sys.stderr)
                    return 0
            except (EOFError, KeyboardInterrupt):
                print("\n💡 Pour lancer plus tard: voila categories --refresh", file=sys.stderr)
                return 0
    
    if args.tree:
        # Show full tree
        print(f"\n📂 Arbre des catégories (màj: {cache.last_updated})\n")
        print(cache.format_tree())
        return 0
    
    # Flat list
    all_cats = cache.get_all_flat()
    
    if fmt == "json":
        data = [{"name": c.name, "slug": c.slug, "id": c.id, "path": c.path, "depth": d} 
                for c, d in all_cats]
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif fmt == "telegram":
        lines = ["<b>📂 Catégories Voilà</b>\n"]
        for cat, depth in all_cats:
            indent = "  " * depth
            lines.append(f"{indent}• <b>{cat.name}</b>")
        print("\n".join(lines))
    else:
        print(f"\n{'Catégorie':<40} {'Chemin':<50} {'ID'}")
        print("=" * 110)
        for cat, depth in all_cats:
            indent = "  " * depth
            name = f"{indent}{cat.name}"[:40]
            print(f"{name:<40} {cat.path:<50} {cat.id}")
        print(f"\nTotal: {len(all_cats)} catégories (màj: {cache.last_updated})")
        print("\n💡 Rafraîchir: voila categories --refresh")
        print("💡 Voir l'arbre: voila categories --tree")
    
    return 0


def cmd_subcategories(args):
    """Liste les sous-catégories d'une catégorie"""
    search = ProductSearch(headless=True)
    fmt = _get_format(args)
    
    print(f"📂 Récupération des sous-catégories de '{args.category}'...", file=sys.stderr)
    subcategories = search.get_subcategories(args.category)
    
    if not subcategories:
        print(f"Aucune sous-catégorie trouvée pour '{args.category}'")
        print("(La catégorie est peut-être au niveau le plus profond)")
        return 0
    
    if fmt == "json":
        print(json.dumps(subcategories, indent=2, ensure_ascii=False))
    elif fmt == "telegram":
        lines = [f"<b>📂 Sous-catégories de {args.category}</b>\n"]
        for cat in subcategories:
            lines.append(f"• <b>{cat['name']}</b> ({cat['full_path']})")
        print("\n".join(lines))
    else:
        print(f"\n{'Sous-catégorie':<35} {'Chemin complet':<45} {'ID'}")
        print("=" * 95)
        for cat in subcategories:
            print(f"{cat['name']:<35} {cat['full_path']:<45} {cat['id']}")
        print(f"\nTotal: {len(subcategories)} sous-catégories")
        print(f"\n💡 Pour parcourir: voila browse <chemin> --id <ID>")
    
    return 0


def cmd_browse(args):
    """Parcourir une catégorie"""
    from .category_cache import CategoryCache
    
    search = ProductSearch(headless=True)
    fmt = _get_format(args)
    
    category_slug = args.category
    category_id = args.id
    
    # Try to find category in cache first (instant lookup)
    if not args.id:
        cache = CategoryCache()
        if cache.categories:
            found = cache.find(args.category)
            if found:
                category_slug = found.path
                category_id = found.id
                print(f"📂 Catégorie: {found.name} ({found.path})", file=sys.stderr)
            else:
                print(f"❌ Catégorie non trouvée dans le cache: {args.category}")
                print("💡 Rafraîchir le cache: voila categories --refresh")
                return 1
        else:
            # No cache, fall back to browser lookup for top-level
            if '/' in args.category:
                print(f"❌ Cache vide. Pour les chemins imbriqués, d'abord: voila categories --refresh")
                return 1
            
            print(f"📂 Recherche de la catégorie '{args.category}'...", file=sys.stderr)
            categories = search.get_categories()
            matching = [c for c in categories if c['slug'] == args.category or c['name'].lower() == args.category.lower()]
            if not matching:
                print(f"❌ Catégorie non trouvée: {args.category}")
                print("💡 Indexer les catégories: voila categories --refresh")
                return 1
            category_slug = matching[0]['slug']
            category_id = matching[0]['id']
            print(f"📂 Catégorie: {matching[0]['name']}", file=sys.stderr)
    else:
        print(f"📂 Catégorie: {args.category}", file=sys.stderr)
    
    print(f"🔍 Chargement des produits...", file=sys.stderr)
    
    # Get raw products for sorting
    products = search.browse_category(category_slug, category_id, args.limit)
    
    # Apply sorting if requested
    sort_key = getattr(args, 'sort', None)
    if sort_key and products:
        if sort_key == 'price':
            products.sort(key=lambda p: p.price if p.price else float('inf'))
        elif sort_key == 'price-desc':
            products.sort(key=lambda p: p.price if p.price else float('-inf'), reverse=True)
        elif sort_key == 'unit-price':
            products.sort(key=lambda p: p.unit_price if p.unit_price else float('inf'))
        elif sort_key == 'unit-price-desc':
            products.sort(key=lambda p: p.unit_price if p.unit_price else float('-inf'), reverse=True)
        elif sort_key == 'name':
            products.sort(key=lambda p: p.name.lower())
        print(f"📊 Trié par: {sort_key}", file=sys.stderr)
    
    # Format output
    if fmt == "json":
        print(json.dumps([p.to_dict() for p in products], indent=2, ensure_ascii=False))
    elif fmt == "telegram":
        print(search._format_telegram(products))
    else:
        print(search._format_table(products))
    
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
    
    quiet = getattr(args, 'quiet', False)
    
    if not quiet:
        print("🔄 Rafraîchissement de la session...", file=sys.stderr)
    
    session_mgr = SessionManager(session_file=args.session)
    
    # Refresh
    if session_mgr.refresh_session():
        # Status après
        status_after = session_mgr.validate_session(force=True)
        info = session_mgr.get_session_info()
        
        if not quiet:
            print("✅ Session rafraîchie!", file=sys.stderr)
            
            if status_after.authenticated:
                name = status_after.customer_name or status_after.email
                print(f"   • Connecté: {name}", file=sys.stderr)
            
            print(f"   • Cookies: {info['total_cookies']}", file=sys.stderr)
            days = info.get('days_remaining')
            if days is not None:
                print(f"   • Session valide: {days}j", file=sys.stderr)
        
        return 0
    else:
        if not quiet:
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


# =============================================================================
# PANIER LOCAL - Commandes
# =============================================================================

def cmd_local(args):
    """Affiche le panier local"""
    fmt = _get_format(args)
    local_mgr = LocalCartManager()
    
    if fmt == "json":
        print(local_mgr.format_json())
    elif fmt == "telegram":
        print(local_mgr.format_telegram())
    else:
        print(local_mgr.format_summary())
    
    return 0


def cmd_local_add(args):
    """Ajoute un produit au panier local"""
    fmt = _get_format(args)
    local_mgr = LocalCartManager()
    
    item = local_mgr.add_item(args.query, args.quantity)
    
    print(f"✅ Ajouté: {item.query} ×{item.quantity}", file=sys.stderr)
    
    if fmt == "json":
        print(local_mgr.format_json())
    elif fmt == "telegram":
        print(local_mgr.format_telegram())
    else:
        print(local_mgr.format_summary())
    
    return 0


def cmd_local_remove(args):
    """Retire un produit du panier local"""
    fmt = _get_format(args)
    local_mgr = LocalCartManager()
    
    if local_mgr.remove_item(args.query):
        print(f"✅ Retiré: {args.query}", file=sys.stderr)
    else:
        print(f"⚠️ Non trouvé: {args.query}", file=sys.stderr)
    
    if fmt == "json":
        print(local_mgr.format_json())
    elif fmt == "telegram":
        print(local_mgr.format_telegram())
    else:
        print(local_mgr.format_summary())
    
    return 0


def cmd_local_clear(args):
    """Vide le panier local"""
    fmt = _get_format(args)
    local_mgr = LocalCartManager()
    
    local_mgr.clear()
    print("🗑️ Panier local vidé!", file=sys.stderr)
    
    if fmt == "json":
        print(local_mgr.format_json())
    elif fmt == "telegram":
        print(local_mgr.format_telegram())
    else:
        print(local_mgr.format_summary())
    
    return 0


def cmd_local_sync(args):
    """Synchronise le panier local vers le panier en ligne"""
    fmt = _get_format(args)
    local_mgr = LocalCartManager()
    
    if local_mgr.is_empty():
        print("⚠️ Panier local vide, rien à synchroniser", file=sys.stderr)
        return 0
    
    total = local_mgr.item_count()
    print(f"📤 Synchronisation de {total} produits vers Voilà...", file=sys.stderr)
    
    def progress(current, total, item_name):
        print(f"  [{current}/{total}] {item_name}...", file=sys.stderr)
    
    with CartManager(headless=True, session_file=args.session) as cart_mgr:
        result = local_mgr.sync_to_online(cart_mgr, progress_callback=progress)
        
        print("", file=sys.stderr)
        
        if result['total_errors'] == 0:
            print(f"✅ {result['message']}", file=sys.stderr)
        else:
            print(f"⚠️ {result['message']}", file=sys.stderr)
            for err in result['errors']:
                print(f"   • {err['product']}: {err['error']}", file=sys.stderr)
        
        # Vider le panier local après sync réussie si demandé
        if args.clear_after and result['total_added'] > 0:
            local_mgr.clear()
            print("🗑️ Panier local vidé après sync", file=sys.stderr)
        
        # Afficher le panier en ligne mis à jour
        if fmt == "json":
            print(json.dumps(result, indent=2))
        else:
            cart = cart_mgr.get_cart()
            print(f"\n{cart.format_summary()}")
    
    return 0 if result['total_errors'] == 0 else 1


# =============================================================================
# BESOINS (NEEDS) - Commandes
# =============================================================================

def cmd_need(args):
    """Ajoute un besoin à la liste"""
    fmt = _get_format(args)
    needs_mgr = NeedsManager()
    
    priority = "urgent" if args.urgent else "normal"
    
    need = needs_mgr.add_need(
        item=args.item,
        quantity=args.quantity,
        unit=args.unit,
        priority=priority,
        added_by=args.who,
        notes=args.notes
    )
    
    print(f"✅ Ajouté: {need.format_line()}", file=sys.stderr)
    
    if fmt == "json":
        print(json.dumps(need.to_dict(), indent=2, ensure_ascii=False))
    elif fmt == "telegram":
        print(needs_mgr.format_telegram())
    else:
        print(needs_mgr.format_summary())
    
    return 0


def cmd_needs(args):
    """Liste les besoins ou effectue une action dessus"""
    fmt = _get_format(args)
    needs_mgr = NeedsManager()
    
    # Action: marquer fait
    if args.done:
        if args.done == "__all__":
            count = needs_mgr.mark_all_done()
            print(f"✅ {count} besoins marqués comme faits", file=sys.stderr)
        else:
            need = needs_mgr.mark_done(args.done)
            if need:
                print(f"✅ Marqué fait: {need.item}", file=sys.stderr)
            else:
                print(f"⚠️ Non trouvé: {args.done}", file=sys.stderr)
                return 1
    
    # Action: nettoyer les complétés
    elif args.clear_done:
        count = needs_mgr.clear_done()
        print(f"🗑️ {count} besoins complétés supprimés", file=sys.stderr)
    
    # Action: compiler pour épicerie
    elif args.compile:
        print(needs_mgr.compile_list())
        return 0
    
    # Action: transférer vers panier local
    elif args.to_local:
        local_mgr = LocalCartManager()
        items = needs_mgr.to_local_cart_items()
        
        if not items:
            print("⚠️ Aucun besoin à transférer", file=sys.stderr)
            return 0
        
        # Utiliser les préférences pour résoudre les besoins
        prefs_mgr = PreferencesManager()
        
        added = 0
        for item_data in items:
            query = prefs_mgr.resolve_need(item_data["query"])
            local_mgr.add_item(query, item_data["quantity"])
            added += 1
        
        print(f"✅ {added} besoins ajoutés au panier local", file=sys.stderr)
        print(local_mgr.format_summary())
        return 0
    
    # Action: supprimer un besoin
    elif args.remove:
        if needs_mgr.remove_need(args.remove):
            print(f"✅ Supprimé: {args.remove}", file=sys.stderr)
        else:
            print(f"⚠️ Non trouvé: {args.remove}", file=sys.stderr)
            return 1
    
    # Affichage par défaut: liste des besoins
    status = args.status if hasattr(args, 'status') and args.status else "pending"
    
    if fmt == "json":
        needs = needs_mgr.list_needs(status=status if status != "all" else None, by=args.by)
        print(json.dumps([n.to_dict() for n in needs], indent=2, ensure_ascii=False))
    elif fmt == "telegram":
        print(needs_mgr.format_telegram())
    else:
        print(needs_mgr.format_summary())
    
    return 0


# =============================================================================
# PRÉFÉRENCES - Commandes
# =============================================================================

def cmd_pref(args):
    """Gère les préférences pour un produit"""
    fmt = _get_format(args)
    prefs_mgr = PreferencesManager()
    
    # Action: définir le favori
    if args.favorite:
        pref = prefs_mgr.set_favorite(args.item, args.favorite)
        print(f"⭐ Favori pour '{args.item}': {args.favorite}", file=sys.stderr)
    
    # Action: ajouter un substitut
    elif args.substitute:
        pref = prefs_mgr.add_substitute(args.item, args.substitute, notes=args.notes)
        print(f"🔄 Substitut ajouté pour '{args.item}': {args.substitute}", file=sys.stderr)
    
    # Action: ajouter à éviter
    elif args.avoid:
        pref = prefs_mgr.add_avoid(args.item, args.avoid)
        print(f"🚫 Ajouté à éviter pour '{args.item}': {args.avoid}", file=sys.stderr)
    
    # Action: définir la catégorie
    elif args.category:
        pref = prefs_mgr.set_category(args.item, args.category)
        print(f"📁 Catégorie pour '{args.item}': {args.category}", file=sys.stderr)
    
    # Action: afficher les préférences
    elif args.show:
        pref = prefs_mgr.get_preference(args.item)
        if pref:
            if fmt == "json":
                print(json.dumps(pref.to_dict(), indent=2, ensure_ascii=False))
            else:
                print(f"📋 Préférences pour '{args.item}':\n")
                print(pref.format_summary())
        else:
            print(f"⚠️ Aucune préférence pour '{args.item}'", file=sys.stderr)
        return 0
    
    # Action: supprimer les préférences
    elif args.delete:
        if prefs_mgr.delete_preference(args.item):
            print(f"🗑️ Préférences supprimées pour '{args.item}'", file=sys.stderr)
        else:
            print(f"⚠️ Aucune préférence pour '{args.item}'", file=sys.stderr)
            return 1
        return 0
    
    else:
        # Afficher les préférences si aucune action
        pref = prefs_mgr.get_preference(args.item)
        if pref:
            if fmt == "json":
                print(json.dumps(pref.to_dict(), indent=2, ensure_ascii=False))
            else:
                print(f"📋 Préférences pour '{args.item}':\n")
                print(pref.format_summary())
        else:
            print(f"⚠️ Aucune préférence pour '{args.item}'", file=sys.stderr)
        return 0
    
    return 0


def cmd_prefs(args):
    """Liste toutes les préférences"""
    fmt = _get_format(args)
    prefs_mgr = PreferencesManager()
    
    if fmt == "json":
        prefs = prefs_mgr.list_all_preferences()
        print(json.dumps({k: v.to_dict() for k, v in prefs.items()}, indent=2, ensure_ascii=False))
    elif fmt == "telegram":
        print(prefs_mgr.format_telegram())
    else:
        print(prefs_mgr.format_all_preferences())
    
    return 0


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
  
  --- Panier local ---
  voila local                         Voir le panier local
  voila local-add "lait 2%" -q 2      Ajouter au panier local
  voila local-remove "lait 2%"        Retirer du panier local
  voila local-clear                   Vider le panier local
  voila local-sync --clear-after      Sync vers panier en ligne
  
  --- Besoins ---
  voila need "lait" -q 2              Ajouter un besoin
  voila need "céréales" --who Emma    Besoin ajouté par Emma
  voila needs                         Liste des besoins
  voila needs --compile               Liste formatée pour épicerie
  voila needs --to-local              Transférer vers panier local
  voila needs --done lait             Marquer un besoin comme fait
  
  --- Préférences ---
  voila pref "lait" --favorite "Lactantia 2%"
  voila pref "lait" --substitute "Natrel 2%"
  voila pref "lait" --avoid "Marque X"
  voila pref "lait" --show            Voir préférences
  voila prefs                         Liste toutes les préférences
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
    
    # categories
    cat_parser = subparsers.add_parser("categories", help="Liste les catégories (depuis cache)")
    cat_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    cat_parser.add_argument("--refresh", action="store_true", help="Recrawler l'arbre (~1-2 min)")
    cat_parser.add_argument("--tree", action="store_true", help="Afficher en arbre hiérarchique")
    cat_parser.add_argument("--depth", type=int, default=2, help="Profondeur max de crawl (défaut: 2)")
    cat_parser.set_defaults(func=cmd_categories)
    
    # subcategories
    subcat_parser = subparsers.add_parser("subcategories", help="Liste les sous-catégories")
    subcat_parser.add_argument("category", help="Chemin de la catégorie (ex: dairy-eggs ou dairy-eggs/milk)")
    subcat_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    subcat_parser.set_defaults(func=cmd_subcategories)
    
    # browse
    browse_parser = subparsers.add_parser("browse", help="Parcourir une catégorie")
    browse_parser.add_argument("category", help="Slug ou chemin (ex: dairy-eggs ou dairy-eggs/milk/flavoured-milk)")
    browse_parser.add_argument("--id", help="ID de la catégorie (requis pour chemins profonds)")
    browse_parser.add_argument("-n", "--limit", type=int, default=50, help="Nombre max de résultats (défaut: 50)")
    browse_parser.add_argument("-s", "--sort", choices=["price", "price-desc", "unit-price", "unit-price-desc", "name"], 
                              help="Trier les résultats (price=moins cher, unit-price=meilleur rapport)")
    browse_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    browse_parser.set_defaults(func=cmd_browse)
    
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
    refresh_parser.add_argument("-q", "--quiet", action="store_true", help="Mode silencieux (pour cron)")
    refresh_parser.set_defaults(func=cmd_refresh)
    
    # ==========================================================================
    # BESOINS (NEEDS) - Subparsers
    # ==========================================================================
    
    # need (add a need)
    need_parser = subparsers.add_parser("need", help="Ajoute un besoin à la liste")
    need_parser.add_argument("item", help="Article à ajouter (ex: 'lait', 'céréales')")
    need_parser.add_argument("-q", "--quantity", type=float, default=1.0, help="Quantité (défaut: 1)")
    need_parser.add_argument("-u", "--unit", help="Unité (ex: L, kg, boîtes)")
    need_parser.add_argument("--who", default="Mathieu", help="Qui ajoute ce besoin (défaut: Mathieu)")
    need_parser.add_argument("--urgent", action="store_true", help="Marquer comme urgent")
    need_parser.add_argument("--notes", help="Notes additionnelles")
    need_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    need_parser.set_defaults(func=cmd_need)
    
    # needs (list/manage needs)
    needs_parser = subparsers.add_parser("needs", help="Liste et gère les besoins")
    needs_parser.add_argument("--by", help="Filtrer par personne")
    needs_parser.add_argument("--status", choices=["pending", "done", "all"], default="pending",
                              help="Filtrer par statut (défaut: pending)")
    needs_parser.add_argument("--compile", action="store_true", help="Compiler la liste pour l'épicerie")
    needs_parser.add_argument("--to-local", action="store_true", help="Transférer vers panier local")
    needs_parser.add_argument("--done", nargs="?", const="__all__", metavar="ITEM",
                              help="Marquer fait (un item ou tous)")
    needs_parser.add_argument("--clear-done", action="store_true", help="Supprimer les besoins complétés")
    needs_parser.add_argument("--remove", metavar="ITEM", help="Supprimer un besoin")
    needs_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    needs_parser.set_defaults(func=cmd_needs)
    
    # ==========================================================================
    # PRÉFÉRENCES - Subparsers
    # ==========================================================================
    
    # pref (manage one preference)
    pref_parser = subparsers.add_parser("pref", help="Gère les préférences pour un produit")
    pref_parser.add_argument("item", help="Nom du besoin (ex: 'lait', 'céréales')")
    pref_parser.add_argument("--favorite", metavar="PRODUIT", help="Définir le produit favori")
    pref_parser.add_argument("--substitute", metavar="PRODUIT", help="Ajouter un substitut")
    pref_parser.add_argument("--avoid", metavar="MARQUE", help="Ajouter une marque à éviter")
    pref_parser.add_argument("--category", help="Définir la catégorie")
    pref_parser.add_argument("--notes", help="Notes pour le substitut")
    pref_parser.add_argument("--show", action="store_true", help="Afficher les préférences")
    pref_parser.add_argument("--delete", action="store_true", help="Supprimer les préférences")
    pref_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    pref_parser.set_defaults(func=cmd_pref)
    
    # prefs (list all preferences)
    prefs_parser = subparsers.add_parser("prefs", help="Liste toutes les préférences")
    prefs_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    prefs_parser.set_defaults(func=cmd_prefs)
    
    # ==========================================================================
    # PANIER LOCAL - Subparsers
    # ==========================================================================
    
    # local (show local cart)
    local_parser = subparsers.add_parser("local", help="Affiche le panier local")
    local_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    local_parser.set_defaults(func=cmd_local)
    
    # local-add
    local_add_parser = subparsers.add_parser("local-add", help="Ajoute un produit au panier local")
    local_add_parser.add_argument("query", help="Produit à ajouter")
    local_add_parser.add_argument("-q", "--quantity", type=int, default=1, help="Quantité (défaut: 1)")
    local_add_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    local_add_parser.set_defaults(func=cmd_local_add)
    
    # local-remove
    local_remove_parser = subparsers.add_parser("local-remove", help="Retire un produit du panier local")
    local_remove_parser.add_argument("query", help="Produit à retirer")
    local_remove_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    local_remove_parser.set_defaults(func=cmd_local_remove)
    
    # local-clear
    local_clear_parser = subparsers.add_parser("local-clear", help="Vide le panier local")
    local_clear_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    local_clear_parser.set_defaults(func=cmd_local_clear)
    
    # local-sync
    local_sync_parser = subparsers.add_parser("local-sync", help="Synchronise le panier local vers Voilà")
    local_sync_parser.add_argument("--clear-after", "-c", action="store_true", 
                                    help="Vider le panier local après sync réussie")
    local_sync_parser.add_argument("-f", "--format", choices=["table", "telegram", "json"], default=None)
    local_sync_parser.set_defaults(func=cmd_local_sync)
    
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
