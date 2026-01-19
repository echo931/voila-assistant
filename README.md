# Voilà Assistant

Assistant pour les commandes d'épicerie sur [Voilà.ca](https://voila.ca) (IGA en ligne).

## Status: MVP Fonctionnel ✅

## Fonctionnalités

- 🔍 **Recherche** de produits avec prix et détails
- 🛒 **Panier** - ajouter, supprimer, vider
- 📊 **Formats** - table, telegram (HTML), json
- 💾 **Session** persistante via cookies

## Installation

```bash
cd ~/projects/voila-assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Utilisation

```bash
# Recherche
./voila search "lait 2%" -n 5
./voila search "bananes" -f telegram

# Panier
./voila cart
./voila add "pain blanc"
./voila add "fromage" -i 2 -q 3  # 3x le 3ème résultat
./voila clear
```

## Architecture

```
src/
├── cli.py        # CLI unifié
├── search.py     # Recherche produits (Playwright)
├── cart.py       # Gestion panier (Playwright + REST API)
├── models.py     # Product, CartItem, Cart
├── client.py     # HTTP client avec retry
└── exceptions.py # Exceptions personnalisées
```

## Comment ça marche

1. **Recherche**: Playwright charge la page de recherche Voilà.ca et extrait les produits depuis `window.__INITIAL_STATE__`
2. **Panier**: 
   - Lecture via REST API (`/api/cart/v1/carts/active`)
   - Ajout via clics automatisés sur les boutons "Add to basket"
   - Suppression via boutons "Decrease quantity" dans le quick cart panel
3. **Cache noms**: Les noms de produits sont extraits des `aria-label` des boutons et cachés localement

## Limitations

- Pas d'authentification (checkout impossible)
- Session panier liée aux cookies (`~/.voila-session.json`)
- Chaque commande lance un browser headless (~15-30s)
- Minimum commande: 35$ CAD

## Voir aussi

- [TODO.md](TODO.md) - Tâches et progression
- [ARCHITECTURE.md](ARCHITECTURE.md) - Design détaillé
- [skill/SKILL.md](skill/SKILL.md) - Documentation Clawdbot
