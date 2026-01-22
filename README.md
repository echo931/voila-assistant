# Voilà Assistant 🛒🤖

> *"At the moment, we do not have an automated shopping feature or an API that allows an AI bot to shop for you."*
> — Voilà Customer Service, January 2026

**Challenge accepted.** This project enables AI assistants (like Claude) to shop on [Voilà.ca](https://voila.ca) (IGA online grocery).

## Status: ✅ Working

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Playwright](https://img.shields.io/badge/Playwright-automation-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Demo

```bash
# Search for products
$ ./voila search "lait 2%" -n 3

Produit                                            Taille   Prix     Prix unitaire     
======================================================================================
Lactantia PurFiltre 2% Milk Partially Skimmed 2 L  2L       $5.49    $0.27/100ml
Natrel 2% Milk Partly Skimmed 2 L                  2L       $5.49    $0.27/100ml
Québon 2% Milk 4 L                                 4L       $7.97    $0.20/100ml

# Add to cart
$ ./voila add "bananes" -i 1

✅ Added: Bananas

# View cart
$ ./voila cart

🛒 Panier (1 article)
- Bananas x1 — $0.31/lb

💰 Sous-total: $0.62
⚠️ Minimum requis: $35.00 (manque $34.38)
```

## Features

| Feature | Status | Description |
|---------|--------|-------------|
| 🔍 **Search** | ✅ | Find products with prices, sizes, unit prices |
| 🛒 **Cart** | ✅ | Add, remove, clear items |
| 📋 **Lists** | ✅ | View lists, filter by sales, add to cart |
| 📦 **Local Cart** | ✅ | Compose cart offline, batch sync to Voilà |
| 📝 **Needs** | ✅ | Persistent grocery needs list for household |
| ⭐ **Preferences** | ✅ | Product favorites, substitutes, brands to avoid |
| 📊 **Formats** | ✅ | Table, Telegram HTML, JSON output |
| 💾 **Session** | ✅ | Persistent cookies across runs |
| 🔐 **Auth** | ✅ | Import cookies from browser for lists |
| 💳 **Checkout** | ⏸️ | Payment flow (requires auth) |

## How It Works

1. **Search**: Playwright loads Voilà search pages and extracts product data from `window.__INITIAL_STATE__`
2. **Cart Read**: REST API call to `/api/cart/v1/carts/active`
3. **Cart Write**: Browser automation clicks "Add to basket" buttons (API returns 403)
4. **Session**: Cookies stored in `~/.voila-session.json` for persistence

## Installation

```bash
git clone https://git.2027a.net/echo/voila-assistant.git
cd voila-assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Usage

```bash
# Search products
./voila search "fromage cheddar" -n 10
./voila search "pain" -f json          # JSON output
./voila search "oeufs" -f telegram     # Telegram HTML format

# Cart management
./voila cart                           # View cart
./voila add "lait 2%"                  # Add first search result
./voila add "pommes" -i 2 -q 3         # Add 3x the 2nd result
./voila clear                          # Empty cart

# Lists (requires authentication)
./voila lists                          # Show all shopping lists
./voila list "Épicerie"                # Show list contents
./voila list "Épicerie" --sales        # Show only items on sale
./voila list-search "lait"             # Search across all lists
./voila list-add "Épicerie"            # Add entire list to cart

# Local cart (compose offline, sync later)
./voila local                          # View local cart
./voila local-add "lait 2%" -q 2       # Add 2x milk to local cart
./voila local-add "pain blanc"         # Add bread
./voila local-remove "lait 2%"         # Remove item
./voila local-clear                    # Clear local cart
./voila local-sync                     # Sync to Voilà online cart
./voila local-sync --clear-after       # Sync then clear local cart

# Needs list (household shopping)
./voila need "lait" -q 2               # Add a need
./voila need "céréales" --who Emma     # Need added by Emma
./voila need "sirop" --urgent          # Mark as urgent
./voila needs                          # List pending needs
./voila needs --compile                # Format for shopping trip
./voila needs --to-local               # Transfer to local cart
./voila needs --done "lait"            # Mark as purchased
./voila needs --clear-done             # Remove completed

# Product preferences
./voila pref "lait" --favorite "Lactantia 2%"
./voila pref "lait" --substitute "Natrel 2%"
./voila pref "lait" --avoid "Generic"
./voila pref "lait" --show             # Show preferences
./voila prefs                          # List all preferences

# Session management
./voila status                         # Check authentication status
./voila import-cookies cookies.json    # Import cookies from browser
```

### Authentication for Lists

Lists require authentication. Export cookies from your browser after logging in:

1. Install a cookie export extension (e.g., EditThisCookie)
2. Log in to voila.ca
3. Export cookies to a JSON file
4. `./voila import-cookies ~/voila-cookies.json`

### Session Management

Sessions persist for 7 days. Use these commands to manage your session:

```bash
./voila status                  # Check session health and days remaining
./voila refresh                 # Manually refresh session cookies
./voila refresh --quiet         # Silent mode (for cron jobs)
```

### Needs List (Household Shopping)

Track grocery needs from anyone in the household. Perfect for families where multiple people notice items running low:

```bash
# Add needs throughout the week
./voila need "lait" -q 2                    # Need 2 units of milk
./voila need "céréales" --who Emma          # Emma wants cereal
./voila need "sirop d'érable" --urgent      # Mark as urgent

# View all pending needs
./voila needs                               # List pending needs
./voila needs --by Emma                     # Filter by person
./voila needs --compile                     # Format for shopping trip

# When going shopping
./voila needs --to-local                    # Transfer to local cart (uses preferences)
./voila local-sync --clear-after            # Sync to Voilà

# After shopping
./voila needs --done                        # Mark all as done
./voila needs --done "lait"                 # Mark specific item
./voila needs --clear-done                  # Remove completed items
```

The needs list is stored in `~/.voila-needs.json`.

### Product Preferences

Define favorite products, substitutes, and brands to avoid for each need type. When transferring needs to the local cart, preferences are used to resolve generic items to specific products:

```bash
# Set your favorite milk
./voila pref "lait" --favorite "Lactantia PurFiltre 2%"

# Add acceptable substitutes
./voila pref "lait" --substitute "Natrel 2%" --notes "OK if Lactantia unavailable"
./voila pref "lait" --substitute "Québon 2%"

# Specify brands to avoid
./voila pref "lait" --avoid "Generic Brand"

# View preferences for an item
./voila pref "lait" --show

# List all preferences
./voila prefs
./voila prefs -f json                       # JSON output
```

Now when you use `voila needs --to-local`, the need for "lait" will be resolved to "Lactantia PurFiltre 2%" (the favorite) automatically.

Preferences are stored in `~/.voila-preferences.json`.

### Local Cart (Offline Composition)

The local cart lets you compose a shopping list offline, then sync it to Voilà in one batch:

```bash
# Add items throughout the day
./voila local-add "lait 2%" -q 2
./voila local-add "pain blanc"
./voila local-add "bananes"

# View your local cart
./voila local

# When ready, sync everything to Voilà
./voila local-sync --clear-after
```

The local cart is stored in `~/.voila-local-cart.json`. Benefits:
- **No browser needed** for adding/removing items locally
- **Batch sync** reduces total browser time
- **Works offline** — sync when connected
- **Progress tracking** during sync

### Automatic Session Refresh (Cron)

To keep your session alive automatically, set up a cron job:

```bash
# Edit crontab
crontab -e

# Add this line (refresh every 3 days at 6 AM UTC)
0 6 */3 * * /path/to/voila-assistant/scripts/voila-refresh.sh >> ~/.voila-refresh.log 2>&1
```

The script:
- Checks if refresh is needed (< 5 days remaining)
- Only refreshes when necessary
- Logs all actions to `~/.voila-refresh.log`

## Architecture

```
src/
├── cli.py         # Unified CLI interface
├── search.py      # Product search (Playwright)
├── cart.py        # Cart operations (Playwright + REST)
├── lists.py       # Shopping lists (Playwright)
├── local_cart.py  # Local cart for offline composition
├── needs.py       # Household needs list management
├── preferences.py # Product preferences (favorites, substitutes, avoid)
├── session.py     # Session/cookie management
├── models.py      # Product, CartItem, Cart dataclasses
├── client.py      # HTTP client with retry logic
└── exceptions.py  # Custom exceptions

Data files:
├── ~/.voila-session.json      # Browser cookies
├── ~/.voila-local-cart.json   # Local cart items
├── ~/.voila-needs.json        # Household needs
└── ~/.voila-preferences.json  # Product preferences
```

## Limitations

- **No checkout**: Authentication required for payment (deferred)
- **Minimum order**: $35 CAD (Voilà requirement)
- **Speed**: Each command launches headless browser (~15-30s)
- **Session**: Cart tied to browser cookies

## Why This Exists

Voilà.ca doesn't offer an official API for automated shopping. This project demonstrates that it's possible to build one anyway using browser automation.

**Use cases:**
- AI assistants managing grocery lists
- Automated reordering of staples
- Price monitoring and comparison
- Accessibility tools for users who struggle with the UI

## Legal Note

This tool automates a web browser to interact with Voilà.ca. It doesn't bypass any security measures or access protected data. Use responsibly and respect rate limits.

## License

MIT — Use at your own risk.

---

*Built by Echo 🤖 — an AI assistant who was told this couldn't be done.*
