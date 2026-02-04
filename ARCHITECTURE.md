# Architecture

## Overview

```mermaid
graph TB
    subgraph Interface
        User[User<br/>CLI / Telegram / AI Agent]
        CLI[cli.py<br/>Commands: search, cart, add, lists, needs, prefs]
    end

    subgraph Core[Core Modules]
        search[search.py]
        cart[cart.py]
        lists[lists.py]
        needs[needs.py]
        local_cart[local_cart.py]
        prefs[preferences.py]
        session[session.py]
    end

    subgraph Infra[Infrastructure]
        PW[Playwright<br/>Chromium]
        HTTP[requests<br/>HTTP client]
        JSON[JSON files]
    end

    subgraph External[External Services]
        Voila[voila.ca<br/>REST API + Web pages]
        Files[Local Files<br/>~/.voila-*.json]
    end

    User --> CLI
    CLI --> search & cart & lists & needs & local_cart & prefs
    search & cart & lists --> PW
    cart --> HTTP
    needs & local_cart & prefs & session --> JSON
    PW --> Voila
    HTTP --> Voila
    JSON --> Files
```

## Data Flow

### Product Search

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant search.py
    participant Playwright
    participant voila.ca

    User->>CLI: ./voila search "lait"
    CLI->>search.py: search(query)
    search.py->>Playwright: Launch browser
    Playwright->>voila.ca: GET /search?q=lait
    voila.ca-->>Playwright: HTML + __INITIAL_STATE__
    Playwright-->>search.py: Extract JS state
    search.py-->>CLI: List[Product]
    CLI-->>User: Formatted table
```

### Cart Operations

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant cart.py
    participant Playwright
    participant API

    Note over User,API: Cart Read (API works)
    User->>CLI: ./voila cart
    CLI->>cart.py: get_cart()
    cart.py->>API: GET /api/cart/v1/carts/active
    API-->>cart.py: Cart JSON
    cart.py-->>User: Cart display

    Note over User,API: Cart Write (API blocked, use browser)
    User->>CLI: ./voila add "bananes"
    CLI->>cart.py: add_item()
    cart.py->>Playwright: Click "Add to basket"
    Playwright-->>cart.py: Success
    cart.py-->>User: ✅ Added
```

### Why Playwright for Writes?

The Voilà REST API returns 403 for cart modification endpoints. Browser automation
is required to interact with the cart through the normal UI flow.

## Key Technical Discoveries

### API Endpoints

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/search?q=<query>` | GET (browser) | Returns page with `__INITIAL_STATE__` |
| `/api/cart/v1/carts/active` | GET | Returns cart JSON |
| `/api/cart/v1/carts/active/add-items` | POST | Returns 403 (blocked) |
| `/lists` | GET (browser) | Shopping lists (server-rendered) |

### State Extraction

Product data is embedded in pages as `window.__INITIAL_STATE__`:

```javascript
window.__INITIAL_STATE__ = {
  data: {
    products: {
      productEntities: {
        "product-uuid": {
          id: "uuid",
          name: "Product Name",
          brand: "Brand",
          price: { current: { amount: "5.49" } },
          // ...
        }
      }
    }
  }
}
```

### Authentication

- SSO via Gigya (voila.login-seconnecter.ca)
- Anti-bot protection blocks headless login
- Solution: Import cookies from authenticated browser session
- Session cookies valid ~7 days, can be refreshed

### Critical Cookies

| Cookie | Purpose |
|--------|---------|
| `global_sid` | Session ID |
| `userId` | User identifier |
| `VISITORID` | Visitor tracking |
| `userEmail` | Email (when authenticated) |

## Data Models

### Product
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
    available: bool = True
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

### NeedItem
```python
@dataclass
class NeedItem:
    id: str
    item: str
    quantity: int
    unit: Optional[str]
    priority: str  # "low", "normal", "urgent"
    added_by: Optional[str]
    added_at: datetime
    notes: Optional[str]
    status: str  # "pending", "done"
```

## Security Considerations

1. **No payment data**: Checkout is manual (link provided)
2. **Local cookie storage**: `~/.voila-session.json` (chmod 600)
3. **No credential storage**: Import cookies, don't store passwords
4. **Minimal scraping**: Respect rate limits, use sparingly

## Configuration

### Environment Variables

```bash
VOILA_DEBUG=1          # Enable debug logging
VOILA_HEADLESS=1       # Run browser headless (default)
VOILA_TIMEOUT=30       # Request timeout in seconds
```

### File Locations

```
~/.voila-session.json       # Auth cookies
~/.voila-local-cart.json    # Offline cart
~/.voila-needs.json         # Household needs
~/.voila-preferences.json   # Product preferences
```
