# Roadmap : Assistant Épicerie Intelligent

> Vision : Un assistant qui gère l'épicerie de façon proactive, apprend les préférences, et optimise les achats.

## 🎯 Vue d'ensemble des fonctionnalités

### Phase 1 : Liste de besoins persistante ⬅️ **EN COURS**
### Phase 2 : Cache produits et intelligence prix
### Phase 3 : Intégration recettes (Mealie)
### Phase 4 : Feedback et apprentissage
### Phase 5 : Automatisation et suggestions proactives

---

## Phase 1 : Liste de besoins persistante

**Objectif** : Permettre à Mathieu et ses filles de signaler des besoins au fil du temps, qui seront compilés lors de la prochaine épicerie.

### Structure de données (`~/.voila-needs.json`)

```json
{
  "needs": [
    {
      "id": "uuid",
      "item": "lait",
      "quantity": 2,
      "unit": "L",
      "priority": "normal",
      "added_by": "Mathieu",
      "added_at": "2026-01-22T17:40:00Z",
      "notes": "2% de préférence",
      "status": "pending"
    }
  ],
  "preferences": {
    "lait": {
      "category": "produits-laitiers",
      "default_quantity": 2,
      "favorite": {
        "product_id": "abc123",
        "name": "Lactantia PurFiltre 2% 2L",
        "typical_price": 5.49
      },
      "substitutes": [
        {
          "product_id": "def456",
          "name": "Natrel 2% 2L",
          "typical_price": 5.49,
          "notes": "Acceptable"
        },
        {
          "product_id": "ghi789",
          "name": "Québon 2% 4L",
          "typical_price": 7.97,
          "notes": "Si besoin de plus"
        }
      ],
      "avoid": ["Marque X"],
      "constraints": {
        "must_be": ["2%"],
        "prefer": ["PurFiltre", "sans lactose si dispo"]
      }
    },
    "céréales": {
      "category": "petit-déjeuner",
      "favorites": [
        {"name": "Cheerios Miel & Noix", "notes": "Pour les filles"},
        {"name": "Granola Jordans", "notes": "Pour Mathieu"}
      ],
      "substitutes": [...]
    }
  },
  "household": {
    "members": ["Mathieu", "Fille1", "Fille2"],
    "default_servings": 4
  },
  "last_grocery": "2026-01-22",
  "settings": {
    "budget_target": null,
    "prefer_sales": true,
    "prefer_organic": false,
    "store": "voila"
  }
}
```

### Commandes CLI

```bash
# Ajouter un besoin
voila need "lait" -q 2                    # Ajoute "lait" x2
voila need "céréales" --who "Emma"        # Emma a demandé des céréales
voila need "sirop d'érable" --urgent      # Priorité haute

# Voir les besoins en attente
voila needs                               # Liste tous les besoins pending
voila needs --by Emma                     # Filtre par personne

# Gérer les préférences
voila pref "lait" --favorite "Lactantia PurFiltre 2%"
voila pref "lait" --substitute "Natrel 2%"
voila pref "lait" --avoid "Marque X"

# Compiler pour épicerie
voila needs --compile                     # Génère liste d'achat depuis besoins
voila needs --to-cart                     # Ajoute besoins résolus au panier local

# Marquer comme acheté
voila needs --done                        # Clear tous les besoins pending
voila need "lait" --done                  # Marque un item spécifique
```

### Intégration conversationnelle (via Telegram)

Mathieu ou filles peuvent dire :
- "On manque de lait"
- "Il faudrait racheter des céréales"  
- "Plus de sirop d'érable"
- "Emma veut des yogourts"

→ Echo parse et ajoute à la liste de besoins.

---

## Phase 2 : Cache produits et intelligence prix

**Objectif** : Construire une base de données locale des produits pour permettre comparaisons, substitutions intelligentes, et recherches rapides.

### Structure (`~/.voila-products-cache.json`)

```json
{
  "products": {
    "abc123": {
      "id": "abc123",
      "name": "Lactantia PurFiltre 2% Milk 2L",
      "brand": "Lactantia",
      "category": "produits-laitiers",
      "subcategory": "lait",
      "size": "2L",
      "price": 5.49,
      "price_per_unit": 0.27,
      "unit": "100ml",
      "is_organic": false,
      "tags": ["2%", "PurFiltre"],
      "last_seen": "2026-01-22",
      "price_history": [
        {"date": "2026-01-15", "price": 5.49},
        {"date": "2026-01-01", "price": 4.99, "on_sale": true}
      ]
    }
  },
  "categories": {
    "produits-laitiers": ["lait", "yogourt", "fromage", "crème"],
    "viandes": ["poulet", "boeuf", "porc", "agneau"],
    ...
  },
  "last_full_scan": null,
  "stats": {
    "total_products": 1523,
    "last_updated": "2026-01-22"
  }
}
```

### Fonctionnalités

1. **Recherche locale rapide** (avant d'aller sur le web)
2. **Comparaison prix/poids** pour trouver le meilleur deal
3. **Détection des soldes** (prix inférieur à l'historique)
4. **Substitutions intelligentes** basées sur catégorie + contraintes

### Alimentation du cache

- Scraping progressif lors des recherches
- Option: scraping complet d'une catégorie
- Import depuis les listes Voilà existantes

---

## Phase 3 : Intégration recettes (Mealie)

**Objectif** : Connecter les recettes de Mathieu pour générer automatiquement les listes d'ingrédients.

### Intégration Mealie API

```python
class MealieClient:
    def __init__(self, base_url, api_token):
        ...
    
    def get_recipes(self) -> List[Recipe]
    def get_recipe(self, slug) -> Recipe
    def get_meal_plan(self, start, end) -> MealPlan
    def search_recipes(self, query) -> List[Recipe]
```

### Workflow

1. Mathieu planifie ses repas dans Mealie (ou demande à Echo)
2. Echo récupère le meal plan via API
3. Echo extrait les ingrédients de chaque recette
4. Echo mappe les ingrédients → produits Voilà (via préférences + cache)
5. Echo génère le panier

### Commandes

```bash
voila mealie-sync                         # Sync recettes depuis Mealie
voila mealie-plan --week                  # Voir le meal plan de la semaine
voila mealie-to-cart                      # Meal plan → panier
```

---

## Phase 4 : Feedback et apprentissage

**Objectif** : Améliorer les suggestions basées sur les retours de Mathieu.

### Types de feedback

1. **Sur les menus**
   - 👍 Ce repas était bon
   - 👎 On n'a pas aimé
   - ⭐ À refaire souvent
   - 🚫 Ne plus suggérer

2. **Sur les produits**
   - "Le yogourt Oikos était trop sucré"
   - "Les tomates n'étaient pas mûres"
   - "Excellent rapport qualité/prix"

3. **Sur les substitutions**
   - "Le remplacement était OK"
   - "Préférait l'original"

### Storage (`~/.voila-feedback.json`)

```json
{
  "menu_ratings": [...],
  "product_ratings": [...],
  "substitution_ratings": [...]
}
```

### Utilisation

- Ajuster les préférences automatiquement
- Éviter de re-suggérer les flops
- Prioriser les hits

---

## Phase 5 : Automatisation et suggestions proactives

**Objectif** : Echo devient proactif dans la gestion de l'épicerie.

### Fonctionnalités

1. **Rappels de réapprovisionnement**
   - "Ça fait 2 semaines depuis le dernier achat de lait, en avez-vous encore ?"
   
2. **Détection des patterns**
   - "Vous achetez des bananes chaque semaine"
   - → Ajouter automatiquement aux suggestions

3. **Alertes soldes**
   - "Les Cheerios sont en solde cette semaine (-20%)"

4. **Suggestion de menus**
   - Basée sur : saison, soldes, historique, ingrédients en stock

5. **Budget tracking**
   - "Ce mois-ci : 450$ en épicerie (vs 420$ le mois dernier)"

---

## 📊 Priorisation

| Phase | Effort | Impact | Priorité |
|-------|--------|--------|----------|
| 1. Besoins persistants | Moyen | Haut | **P0** |
| 2. Cache produits | Haut | Haut | P1 |
| 3. Mealie | Moyen | Moyen | P2 (quand homelab up) |
| 4. Feedback | Faible | Moyen | P2 |
| 5. Automatisation | Haut | Haut | P3 |

---

## 🔧 Architecture technique

```
~/.voila-session.json          # Auth cookies Voilà
~/.voila-local-cart.json       # Panier local (implémenté ✅)
~/.voila-needs.json            # Liste de besoins (Phase 1)
~/.voila-preferences.json      # Préférences produits (Phase 1)
~/.voila-products-cache.json   # Cache produits (Phase 2)
~/.voila-feedback.json         # Feedback (Phase 4)

~/projects/voila-assistant/
├── src/
│   ├── cli.py                 # CLI principal
│   ├── local_cart.py          # Panier local ✅
│   ├── needs.py               # Gestion besoins (Phase 1)
│   ├── preferences.py         # Préférences (Phase 1)
│   ├── products_cache.py      # Cache (Phase 2)
│   ├── mealie.py              # Intégration Mealie (Phase 3)
│   └── feedback.py            # Feedback (Phase 4)
```

---

## 📅 Timeline estimée

- **Phase 1** : 1-2 sessions de travail
- **Phase 2** : 2-3 sessions
- **Phase 3** : 1 session (quand Mealie dispo)
- **Phase 4** : 1 session
- **Phase 5** : Ongoing

---

*Document créé le 2026-01-22 par Echo*
