# TODO - Voilà Assistant

Liste des tâches détaillées pour le développement.

---

## Progression actuelle

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Infrastructure | ✅ Complété |
| 2 | Recherche | ✅ Complété |
| 3 | Panier | ✅ Complété |
| 4 | Listes de courses | ✅ Complété |
| 5 | Session persistante | ✅ Complété |
| 6 | CLI + Skill | ✅ Complété |
| 7 | Refresh automatique | 📋 À faire |
| 8 | Notifications | 📋 À faire |

**MVP atteint le 2026-01-19** - Fonctionnalités de base opérationnelles.
**Listes ajoutées le 2026-01-20** - Support complet des listes de courses.
**Session persistante le 2026-01-20** - Cookies convertis en persistants.

---

## Phase 7: Refresh automatique de session 📋

### Objectif
Maintenir la session active automatiquement pour éviter la ré-authentification manuelle.

### 7.1 Commande refresh améliorée ✅
- [x] `./voila refresh` - rafraîchit manuellement les cookies
- [x] Merge des nouveaux cookies avec existants
- [x] Affichage du status post-refresh

### 7.2 Cron job pour refresh automatique ✅
**Priorité: Haute** - Évite l'expiration de session sans intervention

- [x] Script `scripts/voila-refresh.sh` autonome
  - Lance `./voila refresh --quiet`
  - Log le résultat dans `~/.voila-refresh.log`
  - Exit code 0 si succès, 1 si échec
  - Smart refresh: ne rafraîchit que si < 5 jours restants
  
- [x] Documentation cron dans README
  ```bash
  # Refresh tous les 3 jours (avant expiration des 7 jours)
  0 6 */3 * * /home/echo/projects/voila-assistant/scripts/voila-refresh.sh
  ```

- [x] Option `--quiet` pour refresh sans output (pour cron)
  ```bash
  ./voila refresh --quiet  # Retourne seulement exit code
  ```

### 7.3 Refresh intelligent (optionnel)
- [ ] Refresh automatique avant chaque commande si session < 2 jours
- [ ] Flag `--no-auto-refresh` pour désactiver
- [ ] Cache le résultat pour éviter refresh multiple

---

## Phase 8: Notifications d'expiration 📋

### Objectif
Alerter l'utilisateur quand la session approche de l'expiration.

### 8.1 Alertes dans le CLI
**Priorité: Moyenne**

- [ ] Afficher warning si session < 3 jours dans toutes les commandes
  ```
  ⚠️ Session expire dans 2j - pensez à './voila refresh'
  ```
- [ ] Option `--no-warnings` pour désactiver

### 8.2 Notifications via Clawdbot (optionnel)
**Priorité: Basse** - Nécessite intégration Clawdbot

- [ ] Heartbeat check de la session
- [ ] Notification Telegram/Discord si session < 24h
- [ ] Exemple de configuration HEARTBEAT.md

---

## Phase 9: Mode daemon (optionnel, basse priorité) 📋

### Objectif
Réutiliser le browser entre commandes pour accélérer les opérations.

### ⚠️ Considérations
- **RAM**: Chromium headless ~150-300MB permanent
- **Complexité**: Gestion du cycle de vie du daemon
- **Bénéfice**: ~15-20s économisés par commande

### 9.1 Architecture proposée
```
voila-daemon (processus background)
├── Browser Playwright partagé
├── Socket UNIX pour communication
└── Auto-shutdown après 30min inactivité
```

### 9.2 Implémentation (si nécessaire)
- [ ] `./voila daemon start` - démarre le daemon
- [ ] `./voila daemon stop` - arrête le daemon
- [ ] `./voila daemon status` - état du daemon
- [ ] Fallback automatique si daemon non disponible
- [ ] Timeout configurable pour auto-shutdown

### 9.3 Décision
**Reporter** - Le coût en RAM (~200MB) n'est probablement pas justifié.
Le temps de démarrage (15-30s) est acceptable pour usage occasionnel.
À reconsidérer si utilisation intensive.

---

## Tâches complétées récemment

### 2026-01-20: Listes de courses
- [x] Module `src/lists.py` - ListsManager avec Playwright
- [x] Extraction des listes via parsing HTML de `/lists`
- [x] Extraction des produits via `__INITIAL_STATE__`
- [x] Commande `./voila lists` - afficher toutes les listes
- [x] Commande `./voila list <nom>` - contenu d'une liste
- [x] Commande `./voila list <nom> --sales` - articles en solde
- [x] Commande `./voila list-search <terme>` - recherche dans listes
- [x] Commande `./voila list-add <nom>` - ajouter liste au panier

### 2026-01-20: Session persistante
- [x] Module `src/session.py` - SessionManager amélioré
- [x] Conversion session cookies → persistent (7 jours)
- [x] Validation auth via Playwright + `__INITIAL_STATE__`
- [x] Suivi expiration cookies critiques
- [x] Commande `./voila status` améliorée
- [x] Commande `./voila refresh` - renouveler cookies
- [x] Commande `./voila import-cookies` améliorée

---

## Découvertes techniques

### Structure API Voilà (2026-01-19)
- **Recherche:** `/search?q=...` → `__INITIAL_STATE__.data.products.productEntities`
- **Panier (lecture):** `GET /api/cart/v1/carts/active`
- **Panier (écriture):** Browser automation (API retourne 403)
- **Seuil minimum:** $35.00 CAD

### Authentification (2026-01-20)
- **SSO:** Gigya via `voila.login-seconnecter.ca`
- **Protection:** Anti-bot bloque login headless
- **Solution:** Import cookies depuis navigateur connecté
- **Données customer:** `__INITIAL_STATE__.data.customer.details.data`
- **Endpoint API customer:** N'existe pas (404 sur `/api/customer/v1/current`)

### Listes (2026-01-20)
- **URL:** `/lists` (toutes), `/lists/{uuid}` (une liste)
- **Données:** Server-side rendered, pas d'API REST
- **Extraction:** Parsing HTML + `__INITIAL_STATE__.data.products`
- **Prix original:** `price.original.amount` (pas `price.was`)

### Cookies critiques
| Cookie | Durée | Rôle |
|--------|-------|------|
| `global_sid` | Session → 7j | Session ID |
| `userId` | Session → 7j | User ID |
| `VISITORID` | 1 an | Visitor tracking |
| `userEmail` | Session → 7j | Email (si auth) |

---

## Prochaine tâche recommandée

**→ Phase 7.2: Cron job pour refresh automatique**

1. Créer `scripts/voila-refresh.sh`
2. Ajouter option `--quiet` au refresh
3. Documenter setup cron dans README
4. Tester sur quelques jours

Temps estimé: 30-45 minutes
