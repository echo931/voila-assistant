# Instructions pour Agents IA

Ce fichier contient les instructions pour les agents IA qui contribuent à ce projet.

## Contexte du projet

**Voilà Assistant** est un outil pour automatiser les commandes d'épicerie sur voila.ca (IGA Québec).

### Objectif
Permettre à l'utilisateur de:
1. Rechercher des produits par texte
2. Ajouter des produits au panier
3. Voir et modifier son panier
4. Obtenir un lien pour finaliser la commande

### Contraintes techniques
- Le code tourne sur une VM Linux (Debian) dans un datacenter
- Pas d'interface graphique (headless)
- Python 3.11+ avec Playwright pour le browser automation
- Les cookies de session doivent être persistés

## Structure du code

### Modules principaux

| Module | Responsabilité | Status |
|--------|---------------|--------|
| `src/search.py` | Recherche de produits | ✅ À migrer |
| `src/cart.py` | Gestion du panier | 🚧 À créer |
| `src/auth.py` | Login/authentification | 📋 Planifié |
| `src/session.py` | Gestion cookies | 📋 Planifié |
| `src/client.py` | Client HTTP commun | 🚧 À créer |
| `src/telegram.py` | Interface Telegram | 📋 Planifié |

### Conventions de code

```python
# Imports groupés et ordonnés
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict

# Docstrings pour toutes les fonctions publiques
def search_products(query: str, max_results: int = 20) -> List[Dict]:
    """
    Recherche des produits sur Voilà.ca
    
    Args:
        query: Terme de recherche
        max_results: Nombre max de résultats
    
    Returns:
        Liste de produits avec leurs détails
    
    Raises:
        VoilaAPIError: Si la requête échoue
    """
    pass

# Classes avec __init__ documenté
class VoilaClient:
    """Client pour l'API Voilà.ca"""
    
    BASE_URL = "https://voila.ca"
    
    def __init__(self, session_file: Optional[Path] = None):
        """
        Args:
            session_file: Chemin vers le fichier de session (cookies)
        """
        pass
```

### Gestion des erreurs

```python
# Exceptions custom dans src/exceptions.py
class VoilaError(Exception):
    """Erreur de base pour Voilà"""
    pass

class VoilaAPIError(VoilaError):
    """Erreur lors d'un appel API"""
    pass

class VoilaAuthError(VoilaError):
    """Erreur d'authentification"""
    pass

class VoilaSessionExpired(VoilaAuthError):
    """Session expirée, re-login nécessaire"""
    pass
```

## API Voilà découverte

### Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/cart/v1/carts/active` | GET | Récupérer le panier |
| `/api/cart/v1/carts/active/add-items` | POST | Ajouter au panier |
| `/search?q=<query>` | GET (browser) | Page de recherche |

### Structure des données

**Produit (dans __INITIAL_STATE__):**
```json
{
  "id": "uuid",
  "name": "Nom du produit",
  "brand": "Marque",
  "size": { "value": "2L" },
  "price": {
    "current": { "amount": "5.49", "currency": "CAD" },
    "unit": { "current": { "amount": "0.27" }, "label": "per 100ml" }
  },
  "status": "AVAILABLE"
}
```

**Ajout au panier:**
```json
POST /api/cart/v1/carts/active/add-items
[{
  "productId": "uuid",
  "quantity": 1,
  "meta": { "pageType": "API" }
}]
```

## Tâches types

### Tâche: Implémenter une fonction

1. Lire la spec dans TODO.md
2. Regarder les modules existants pour le style
3. Écrire le code avec docstrings
4. Écrire un test unitaire basique
5. Tester manuellement si possible

### Tâche: Corriger un bug

1. Reproduire le bug
2. Identifier la cause
3. Écrire un test qui échoue
4. Corriger le code
5. Vérifier que le test passe

### Tâche: Ajouter une fonctionnalité

1. Documenter la fonctionnalité dans TODO.md
2. Identifier les modules impactés
3. Implémenter en petits commits
4. Mettre à jour la documentation

## Tests

```bash
# Lancer tous les tests
python -m pytest tests/

# Test spécifique
python -m pytest tests/test_search.py -v

# Avec couverture
python -m pytest tests/ --cov=src
```

## Environnement

```bash
# Activer le venv
source ~/projects/voila-assistant/venv/bin/activate

# Variables d'environnement
export VOILA_DEBUG=1  # Mode debug
```

## Questions fréquentes

**Q: Comment accéder aux cookies de session?**
R: Les cookies sont stockés dans `~/.secrets/voila-session.json`. Utiliser `src/session.py` pour les charger.

**Q: Pourquoi utiliser Playwright plutôt que requests?**
R: Le site utilise JavaScript pour charger les données. Playwright permet d'exécuter le JS et d'extraire `__INITIAL_STATE__`.

**Q: Comment gérer les erreurs 403?**
R: Certaines pages sont protégées. Utiliser la page de recherche qui fonctionne, pas les pages produit individuelles.

## Contact

Ce projet est géré par Echo (assistant IA) pour Mathieu.
En cas de question, demander dans le chat Telegram.
