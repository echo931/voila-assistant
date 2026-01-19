# TODO - Voilà Assistant

Liste des tâches détaillées pour le développement.

---

## Phase 1: Infrastructure de base

### 1.1 Setup environnement
- [x] Créer structure de répertoires
- [x] Initialiser git
- [x] Créer README.md
- [x] Créer AGENTS.md
- [ ] Créer requirements.txt
- [ ] Setup venv dédié
- [ ] Configurer .gitignore

**Assignable à:** Agent basique  
**Complexité:** Faible  
**Temps estimé:** 30 min

### 1.2 Module client HTTP (`src/client.py`)
- [ ] Classe `VoilaClient` avec session requests
- [ ] Headers par défaut (User-Agent, Accept, etc.)
- [ ] Méthode pour charger/sauvegarder cookies
- [ ] Gestion des erreurs HTTP
- [ ] Retry automatique avec backoff

**Spec:**
```python
class VoilaClient:
    def __init__(self, session_file: Path = None)
    def get(self, endpoint: str) -> dict
    def post(self, endpoint: str, data: dict) -> dict
    def load_session(self, path: Path) -> bool
    def save_session(self, path: Path) -> None
```

**Assignable à:** Agent basique  
**Complexité:** Moyenne  
**Temps estimé:** 1h

### 1.3 Module exceptions (`src/exceptions.py`)
- [ ] `VoilaError` (base)
- [ ] `VoilaAPIError` (erreur API)
- [ ] `VoilaAuthError` (erreur auth)
- [ ] `VoilaSessionExpired` (session expirée)
- [ ] `VoilaProductNotFound` (produit introuvable)

**Assignable à:** Agent basique  
**Complexité:** Faible  
**Temps estimé:** 15 min

---

## Phase 2: Recherche de produits

### 2.1 Migrer script existant (`src/search.py`)
- [ ] Copier logique de `~/scripts/voila-search.py`
- [ ] Refactorer en classe `ProductSearch`
- [ ] Utiliser `VoilaClient` pour la session
- [ ] Ajouter méthode `search(query, max_results)`
- [ ] Ajouter méthode `get_product_by_id(product_id)`

**Spec:**
```python
class ProductSearch:
    def __init__(self, client: VoilaClient)
    def search(self, query: str, max_results: int = 20) -> List[Product]
    def get_product_by_id(self, product_id: str) -> Optional[Product]
```

**Dépendances:** 1.2  
**Assignable à:** Agent intermédiaire  
**Complexité:** Moyenne  
**Temps estimé:** 1.5h

### 2.2 Modèle Product (`src/models.py`)
- [ ] Dataclass `Product` avec tous les champs
- [ ] Méthode `from_api_response()` 
- [ ] Méthode `to_dict()`
- [ ] Formatters (table, markdown, telegram)

**Spec:**
```python
@dataclass
class Product:
    id: str
    name: str
    brand: Optional[str]
    size: Optional[str]
    price: Decimal
    unit_price: Optional[Decimal]
    unit_label: Optional[str]
    available: bool
    
    @classmethod
    def from_api_response(cls, data: dict) -> 'Product'
    
    def format_table_row(self) -> str
    def format_telegram(self) -> str
```

**Assignable à:** Agent basique  
**Complexité:** Faible  
**Temps estimé:** 45 min

---

## Phase 3: Gestion du panier

### 3.1 Module panier (`src/cart.py`)
- [ ] Classe `Cart` pour représenter le panier
- [ ] Classe `CartManager` pour les opérations
- [ ] Méthode `get_cart()` - récupérer panier actif
- [ ] Méthode `add_item(product_id, quantity)`
- [ ] Méthode `remove_item(product_id)`
- [ ] Méthode `update_quantity(product_id, quantity)`
- [ ] Méthode `clear()`

**Spec:**
```python
@dataclass
class CartItem:
    product_id: str
    product_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal

@dataclass  
class Cart:
    id: str
    items: List[CartItem]
    subtotal: Decimal
    
    def format_summary(self) -> str

class CartManager:
    def __init__(self, client: VoilaClient)
    def get_cart(self) -> Cart
    def add_item(self, product_id: str, quantity: int = 1) -> Cart
    def remove_item(self, product_id: str) -> Cart
    def update_quantity(self, product_id: str, quantity: int) -> Cart
    def clear(self) -> Cart
```

**Dépendances:** 1.2, 3.2  
**Assignable à:** Agent intermédiaire  
**Complexité:** Moyenne-Élevée  
**Temps estimé:** 2-3h

### 3.2 Tests API panier
- [ ] Tester GET /api/cart/v1/carts/active sans auth
- [ ] Tester POST add-items sans auth
- [ ] Documenter les headers requis
- [ ] Documenter les codes d'erreur

**Assignable à:** Agent intermédiaire  
**Complexité:** Moyenne  
**Temps estimé:** 1h

---

## Phase 4: Authentification

### 4.1 Explorer le flow de login
- [ ] Identifier l'endpoint de login
- [ ] Documenter les champs requis
- [ ] Identifier si CAPTCHA est présent
- [ ] Documenter les cookies retournés

**Assignable à:** Agent avancé (Echo)  
**Complexité:** Élevée  
**Temps estimé:** 2h

### 4.2 Module session (`src/session.py`)
- [ ] Classe `SessionManager`
- [ ] Charger cookies depuis fichier JSON
- [ ] Sauvegarder cookies vers fichier JSON
- [ ] Vérifier validité de session
- [ ] Refresh automatique si possible

**Spec:**
```python
class SessionManager:
    def __init__(self, session_file: Path)
    def load(self) -> bool
    def save(self) -> None
    def is_valid(self) -> bool
    def get_cookies(self) -> dict
    def set_cookies(self, cookies: dict) -> None
```

**Dépendances:** 4.1  
**Assignable à:** Agent intermédiaire  
**Complexité:** Moyenne  
**Temps estimé:** 1.5h

### 4.3 Module auth (`src/auth.py`)
- [ ] Login via browser Playwright
- [ ] Capturer les cookies post-login
- [ ] Gérer CAPTCHA avec intervention humaine
- [ ] Sauvegarder session

**Spec:**
```python
class Authenticator:
    def __init__(self, session_manager: SessionManager)
    def login_interactive(self, email: str, password: str) -> bool
    def logout(self) -> None
    def is_authenticated(self) -> bool
```

**Dépendances:** 4.1, 4.2  
**Assignable à:** Agent avancé (Echo)  
**Complexité:** Élevée  
**Temps estimé:** 3h

---

## Phase 5: Intégration Telegram

### 5.1 Module Telegram (`src/telegram.py`)
- [ ] Handler pour commandes `/voila`
- [ ] Sous-commande `recherche <terme>`
- [ ] Sous-commande `ajouter <produit>`
- [ ] Sous-commande `panier`
- [ ] Sous-commande `vider`
- [ ] Formatage des réponses

**Spec:**
```python
class VoilaTelegramHandler:
    def __init__(self, search: ProductSearch, cart: CartManager)
    async def handle_command(self, command: str, args: List[str]) -> str
    async def search(self, query: str) -> str
    async def add_to_cart(self, product_ref: str, quantity: int) -> str
    async def show_cart(self) -> str
    async def clear_cart(self) -> str
```

**Dépendances:** 2.1, 3.1  
**Assignable à:** Agent avancé (Echo)  
**Complexité:** Moyenne  
**Temps estimé:** 2h

### 5.2 Intégration Clawdbot
- [ ] Créer skill Clawdbot pour Voilà
- [ ] Documenter les commandes
- [ ] Tester end-to-end

**Dépendances:** 5.1  
**Assignable à:** Agent avancé (Echo)  
**Complexité:** Moyenne  
**Temps estimé:** 1.5h

---

## Phase 6: Polish et robustesse

### 6.1 Tests unitaires
- [ ] Tests pour `search.py`
- [ ] Tests pour `cart.py`
- [ ] Tests pour `session.py`
- [ ] Mocks pour les appels API

**Assignable à:** Agent basique  
**Complexité:** Moyenne  
**Temps estimé:** 2h

### 6.2 Gestion d'erreurs robuste
- [ ] Retry avec backoff exponentiel
- [ ] Logging structuré
- [ ] Alertes en cas d'erreur critique

**Assignable à:** Agent intermédiaire  
**Complexité:** Moyenne  
**Temps estimé:** 1.5h

### 6.3 Documentation
- [ ] Guide d'installation complet
- [ ] Exemples d'utilisation
- [ ] Troubleshooting

**Assignable à:** Agent basique  
**Complexité:** Faible  
**Temps estimé:** 1h

---

## Résumé par phase

| Phase | Description | Temps estimé | Status |
|-------|-------------|--------------|--------|
| 1 | Infrastructure | 2h | 🚧 En cours |
| 2 | Recherche | 2.5h | 📋 Planifié |
| 3 | Panier | 4h | 📋 Planifié |
| 4 | Authentification | 6.5h | 📋 Planifié |
| 5 | Telegram | 3.5h | 📋 Planifié |
| 6 | Polish | 4.5h | 📋 Planifié |
| **Total** | | **23h** | |

---

## Prochaine tâche à faire

**→ 1.2 Module client HTTP (`src/client.py`)**

C'est la fondation sur laquelle tout le reste repose.
