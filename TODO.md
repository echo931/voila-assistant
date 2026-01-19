# TODO - Voilà Assistant

Liste des tâches détaillées pour le développement.

---

## Progression actuelle

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Infrastructure | ✅ Complété |
| 2 | Recherche | ✅ Complété |
| 3 | Panier | ✅ Complété |
| 4 | Authentification | ⏸️ Différé (fonctionne sans compte) |
| 5 | Telegram/Clawdbot | 🚧 En cours |
| 6 | Polish | 📋 Planifié |

---

## Phase 1: Infrastructure de base ✅

### 1.1 Setup environnement ✅
- [x] Créer structure de répertoires
- [x] Initialiser git
- [x] Créer README.md
- [x] Créer AGENTS.md
- [x] Créer requirements.txt
- [x] Setup venv dédié
- [x] Configurer .gitignore

### 1.2 Module client HTTP (`src/client.py`) ✅
- [x] Classe `VoilaClient` avec session requests
- [x] Headers par défaut (User-Agent, Accept, etc.)
- [x] Méthode pour charger/sauvegarder cookies
- [x] Gestion des erreurs HTTP
- [x] Retry automatique avec backoff

### 1.3 Module exceptions (`src/exceptions.py`) ✅
- [x] `VoilaError` (base)
- [x] `VoilaAPIError` (erreur API)
- [x] `VoilaAuthError` (erreur auth)
- [x] `VoilaSessionExpired` (session expirée)
- [x] `VoilaProductNotFound` (produit introuvable)
- [x] `VoilaBrowserError` (erreur browser)
- [x] `VoilaCartError` (erreur panier)

---

## Phase 2: Recherche de produits ✅

### 2.1 Module recherche (`src/search.py`) ✅
- [x] Classe `ProductSearch` avec Playwright
- [x] Extraction données via `window.__INITIAL_STATE__`
- [x] Méthode `search(query, max_results)`
- [x] Méthode `search_formatted()` avec formats (table, telegram, json)
- [x] CLI pour tests

### 2.2 Modèle Product (`src/models.py`) ✅
- [x] Dataclass `Product` avec tous les champs
- [x] Méthode `from_api_response()`
- [x] Méthode `to_dict()`
- [x] Formatters (table, markdown, telegram)
- [x] Dataclass `CartItem` et `Cart`

---

## Phase 3: Gestion du panier 🚧

### 3.1 Module panier (`src/cart.py`) ✅
- [x] Classe `CartManager` avec Playwright
- [x] Méthode `get_cart()` - récupérer panier actif
- [x] Méthode `add_item_by_search(query, index, quantity)`
- [x] Sauvegarde/chargement cookies de session
- [x] CLI pour tests

### 3.2 Améliorations panier ✅
- [x] Méthode `remove_item(product_id)` - via bouton "Decrease" du quick cart panel
- [x] Méthode `clear()` - itère remove_item sur tous les articles
- [x] **Résolution noms produits** - Cache via aria-labels + API REST
- [ ] Méthode `update_quantity(product_id, quantity)` - utiliser boutons "+/-" (optionnel)

### 3.3 Tests API panier
- [x] GET /api/cart/v1/carts/active fonctionne sans auth
- [x] POST add-items nécessite browser (anti-bot 403)
- [x] Structure du panier documentée

---

## Phase 4: Authentification 📋

### 4.1 Explorer le flow de login
- [ ] Identifier l'endpoint de login
- [ ] Documenter les champs requis
- [ ] Identifier si CAPTCHA est présent
- [ ] Documenter les cookies retournés

### 4.2 Module session (`src/session.py`)
- [ ] Classe `SessionManager`
- [ ] Charger cookies depuis fichier JSON
- [ ] Sauvegarder cookies vers fichier JSON
- [ ] Vérifier validité de session
- [ ] Refresh automatique si possible

### 4.3 Module auth (`src/auth.py`)
- [ ] Login via browser Playwright
- [ ] Capturer les cookies post-login
- [ ] Gérer CAPTCHA avec intervention humaine
- [ ] Sauvegarder session

---

## Phase 5: Intégration Telegram 📋

### 5.1 Module Telegram (`src/telegram.py`)
- [ ] Handler pour commandes `/voila`
- [ ] Sous-commande `recherche <terme>`
- [ ] Sous-commande `ajouter <produit>`
- [ ] Sous-commande `panier`
- [ ] Sous-commande `vider`
- [ ] Formatage des réponses

### 5.2 Intégration Clawdbot
- [ ] Créer skill Clawdbot pour Voilà
- [ ] Documenter les commandes
- [ ] Tester end-to-end

---

## Phase 6: Polish et robustesse 📋

### 6.1 Tests unitaires
- [ ] Tests pour `search.py`
- [ ] Tests pour `cart.py`
- [ ] Tests pour `session.py`
- [ ] Mocks pour les appels API

### 6.2 Gestion d'erreurs robuste
- [ ] Retry avec backoff exponentiel
- [ ] Logging structuré
- [ ] Alertes en cas d'erreur critique

### 6.3 Documentation
- [ ] Guide d'installation complet
- [ ] Exemples d'utilisation
- [ ] Troubleshooting

---

## Découvertes techniques (2026-01-19)

### Structure API Voilà
- **Recherche:** Page `/search?q=...` avec données dans `window.__INITIAL_STATE__.data.products.productEntities`
- **Panier (lecture):** `GET /api/cart/v1/carts/active` retourne le panier actif
- **Panier (écriture):** Nécessite browser automation (403 via API directe)
- **Seuil minimum:** $35.00 CAD pour checkout

### Structure du panier
```json
{
  "cartId": "uuid",
  "items": [
    {
      "productId": "uuid",
      "quantity": { "quantityInBasket": 1 },
      "totalPrices": {
        "regularPrice": { "currency": "CAD", "amount": "5.49" },
        "finalPrice": { "currency": "CAD", "amount": "5.49" }
      }
    }
  ],
  "totals": {
    "itemPriceAfterPromos": { "currency": "CAD", "amount": "10.98" }
  }
}
```

### Boutons d'ajout au panier
- Sélecteur: `button[aria-label*="to basket"]`
- Format aria-label: "Add {Product Name} to basket"

---

## Prochaine tâche

**→ 3.2 Améliorer la résolution des noms de produits dans le panier**

Options à évaluer:
1. Stocker les noms lors de l'ajout via `add_item_by_search()`
2. Créer un cache local productId → productName
3. Parser le HTML du panier (complexe, React)
