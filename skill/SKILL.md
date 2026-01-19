# Voilà Assistant Skill

Commandes d'épicerie sur Voilà.ca (IGA en ligne).

## CLI Location

```
~/projects/voila-assistant/voila
```

## Commands

### Search products
```bash
~/projects/voila-assistant/voila search "lait 2%" -n 5
~/projects/voila-assistant/voila search "bananes" -f telegram
```

### View cart
```bash
~/projects/voila-assistant/voila cart
~/projects/voila-assistant/voila cart -f telegram
```

### Add to cart
```bash
# Add first result for "lait 2%"
~/projects/voila-assistant/voila add "lait 2%"

# Add second result, quantity 2
~/projects/voila-assistant/voila add "pain" -i 1 -q 2
```

### Clear cart
```bash
~/projects/voila-assistant/voila clear
```

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

1. `voila add "lait 2%" -f telegram` → adds milk
2. `voila add "bananes" -f telegram` → adds bananas
3. `voila cart -f telegram` → show cart summary

User: "Qu'est-ce qui est dans mon panier?"

1. `voila cart -f telegram`

User: "Vide mon panier"

1. `voila clear`
