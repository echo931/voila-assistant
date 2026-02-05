# Voilà Assistant Skill

Commandes d'épicerie sur Voilà.ca (IGA en ligne).

## Usage

All commands use `uv run` (no venv activation needed):

```bash
cd ~/projects/voila-assistant
uv run ./voila <command>
```

Or with alias:
```bash
alias voila="cd ~/projects/voila-assistant && uv run ./voila"
```

## Commands

### Search products
```bash
uv run ./voila search "lait 2%" -n 5
uv run ./voila search "bananes" -f telegram
```

### View cart
```bash
uv run ./voila cart
uv run ./voila cart -f telegram
```

### Add to cart
```bash
# Add first result for "lait 2%"
uv run ./voila add "lait 2%"

# Add second result, quantity 2
uv run ./voila add "pain" -i 1 -q 2
```

### Clear cart
```bash
uv run ./voila clear
```

### Browse categories
```bash
# ⚠️ First run: must use --refresh to populate cache (~2-3 min)
uv run ./voila categories --refresh

# After cache exists: instant
uv run ./voila categories              # List all categories
uv run ./voila categories --tree       # Show hierarchy
uv run ./voila browse dairy-eggs       # Browse products in category
uv run ./voila subcategories dairy-eggs # Show child categories
```

Cache: `~/.voila-categories.json` (refreshed nightly by cron)

## Output Formats

- `table` (default): ASCII table
- `telegram`: HTML formatted for Telegram
- `json`: Raw JSON

## Session

Session cookies stored at `~/.voila-session.json`. Persists cart between runs.

## Notes

- Browser automation via Playwright (headless Chromium)
- Each command takes 15-30 seconds (browser startup)
- Products added show in cart with full names
- Minimum order: $35 CAD

## Workflow Example

User: "Ajoute du lait et des bananes au panier"

1. `uv run ./voila add "lait 2%" -f telegram` → adds milk
2. `uv run ./voila add "bananes" -f telegram` → adds bananas
3. `uv run ./voila cart -f telegram` → show cart summary

User: "Qu'est-ce qui est dans mon panier?"

1. `uv run ./voila cart -f telegram`

User: "Vide mon panier"

1. `uv run ./voila clear`
