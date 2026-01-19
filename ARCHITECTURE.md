# Architecture - Voilà Assistant

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              VOILÀ ASSISTANT                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐                                                           │
│  │   USER      │                                                           │
│  │  (Telegram) │                                                           │
│  └──────┬──────┘                                                           │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        INTERFACE LAYER                               │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌────────────────┐  │   │
│  │  │ TelegramHandler │    │   CLI Handler   │    │  (Future API)  │  │   │
│  │  └────────┬────────┘    └────────┬────────┘    └───────┬────────┘  │   │
│  └───────────┼──────────────────────┼─────────────────────┼────────────┘   │
│              │                      │                     │                 │
│              └──────────────────────┼─────────────────────┘                 │
│                                     ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         CORE LAYER                                   │   │
│  │                                                                      │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │   │
│  │  │ ProductSearch│    │ CartManager  │    │ Authenticator│          │   │
│  │  │              │    │              │    │              │          │   │
│  │  │ - search()   │    │ - get_cart() │    │ - login()    │          │   │
│  │  │ - get_by_id()│    │ - add_item() │    │ - logout()   │          │   │
│  │  │              │    │ - remove()   │    │ - is_auth()  │          │   │
│  │  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │   │
│  │         │                   │                   │                   │   │
│  └─────────┼───────────────────┼───────────────────┼───────────────────┘   │
│            │                   │                   │                       │
│            └───────────────────┼───────────────────┘                       │
│                                ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      INFRASTRUCTURE LAYER                            │   │
│  │                                                                      │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │   │
│  │  │ VoilaClient  │    │SessionManager│    │BrowserClient │          │   │
│  │  │              │    │              │    │ (Playwright) │          │   │
│  │  │ - get()      │    │ - load()     │    │              │          │   │
│  │  │ - post()     │    │ - save()     │    │ - navigate() │          │   │
│  │  │ - cookies    │    │ - is_valid() │    │ - extract()  │          │   │
│  │  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │   │
│  │         │                   │                   │                   │   │
│  └─────────┼───────────────────┼───────────────────┼───────────────────┘   │
│            │                   │                   │                       │
│            ▼                   ▼                   ▼                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       EXTERNAL SERVICES                              │   │
│  │                                                                      │   │
│  │        voila.ca              ~/.secrets/           Chromium          │   │
│  │        (API REST)            voila-session.json    (Headless)        │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Composants

### Interface Layer

#### TelegramHandler
Gère les commandes Telegram `/voila`.

```python
# Commandes supportées
/voila recherche <terme>     # Recherche de produits
/voila ajouter <ref> [qty]   # Ajouter au panier
/voila panier                # Voir le panier
/voila vider                 # Vider le panier
/voila checkout              # Lien vers checkout
```

#### CLI Handler
Interface en ligne de commande pour tests et debug.

```bash
python -m src.search "lait 2%"
python -m src.cart show
python -m src.cart add <product_id>
```

### Core Layer

#### ProductSearch
Recherche de produits via browser + extraction JavaScript.

**Flux:**
1. Ouvrir `voila.ca/search?q=<query>` avec Playwright
2. Attendre le chargement
3. Extraire `window.__INITIAL_STATE__.data.products.productEntities`
4. Parser et retourner les produits

#### CartManager
Gestion du panier via API REST.

**Flux ajout:**
1. Charger cookies de session
2. POST `/api/cart/v1/carts/active/add-items`
3. Parser la réponse
4. Retourner le panier mis à jour

**Flux consultation:**
1. Charger cookies de session
2. GET `/api/cart/v1/carts/active`
3. Parser et retourner le panier

#### Authenticator
Gestion de l'authentification via browser.

**Flux login:**
1. Ouvrir `voila.ca/login` avec Playwright
2. Remplir email/password
3. Soumettre le formulaire
4. Gérer CAPTCHA si présent (intervention humaine)
5. Capturer les cookies
6. Sauvegarder via SessionManager

### Infrastructure Layer

#### VoilaClient
Client HTTP avec gestion des cookies et retry.

```python
class VoilaClient:
    BASE_URL = "https://voila.ca"
    
    def __init__(self, session_manager: SessionManager = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': '...',
            'Accept': 'application/json',
            'Accept-Language': 'fr-CA,fr;q=0.9,en;q=0.8'
        })
        if session_manager:
            self.session.cookies.update(session_manager.get_cookies())
    
    def get(self, endpoint: str) -> dict:
        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def post(self, endpoint: str, data: dict) -> dict:
        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()
```

#### SessionManager
Gestion des cookies de session.

```python
class SessionManager:
    def __init__(self, session_file: Path):
        self.session_file = session_file
        self.cookies = {}
    
    def load(self) -> bool:
        if self.session_file.exists():
            with open(self.session_file) as f:
                self.cookies = json.load(f)
            return True
        return False
    
    def save(self) -> None:
        with open(self.session_file, 'w') as f:
            json.dump(self.cookies, f)
    
    def is_valid(self) -> bool:
        # Vérifier si les cookies sont encore valides
        # (faire une requête test)
        pass
```

#### BrowserClient
Client Playwright pour les opérations nécessitant JavaScript.

```python
class BrowserClient:
    def __init__(self):
        self.playwright = None
        self.browser = None
    
    def __enter__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        return self
    
    def __exit__(self, *args):
        self.browser.close()
        self.playwright.stop()
    
    def extract_state(self, url: str) -> dict:
        page = self.browser.new_page()
        page.goto(url, wait_until="networkidle")
        state = page.evaluate("() => window.__INITIAL_STATE__")
        page.close()
        return state
```

## Modèles de données

### Product
```python
@dataclass
class Product:
    id: str
    name: str
    brand: Optional[str]
    size: Optional[str]
    price: Decimal
    currency: str = "CAD"
    unit_price: Optional[Decimal] = None
    unit_label: Optional[str] = None
    available: bool = True
    category: Optional[str] = None
```

### CartItem
```python
@dataclass
class CartItem:
    product_id: str
    product_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
```

### Cart
```python
@dataclass
class Cart:
    id: str
    items: List[CartItem]
    subtotal: Decimal
    currency: str = "CAD"
```

## Flux de données

### Recherche de produits
```
User Input → TelegramHandler → ProductSearch → BrowserClient → voila.ca
                                    ↓
                              List[Product]
                                    ↓
                            Format Telegram
                                    ↓
                              User Output
```

### Ajout au panier
```
User Input → TelegramHandler → CartManager → VoilaClient → /api/cart/...
                                    ↑              ↓
                            SessionManager    API Response
                                    ↓
                                  Cart
                                    ↓
                            Format Telegram
                                    ↓
                              User Output
```

## Sécurité

### Stockage des credentials
```
~/.secrets/
├── voila-session.json    # Cookies (chmod 600)
└── voila-credentials      # Email/password si nécessaire (chmod 600)
```

### Principes
1. **Jamais** de données de carte bancaire
2. Cookies en fichier local protégé
3. Validation humaine pour checkout
4. Logs sans données sensibles

## Configuration

### Variables d'environnement
```bash
VOILA_SESSION_FILE=~/.secrets/voila-session.json
VOILA_DEBUG=0              # 1 pour mode debug
VOILA_HEADLESS=1           # 0 pour voir le browser
VOILA_TIMEOUT=30           # Timeout en secondes
```

### Fichier .env
```ini
# .env (non versionné)
VOILA_SESSION_FILE=~/.secrets/voila-session.json
```
