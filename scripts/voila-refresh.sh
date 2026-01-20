#!/bin/bash
#
# voila-refresh.sh - Rafraîchissement automatique de la session Voilà.ca
#
# Usage: ./voila-refresh.sh [--force]
#
# Ce script est conçu pour être exécuté via cron tous les 3 jours
# pour maintenir la session active (les cookies expirent après 7 jours).
#
# Cron recommandé:
#   0 6 */3 * * /home/echo/projects/voila-assistant/scripts/voila-refresh.sh
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${HOME}/.voila-refresh.log"
VOILA_CMD="${PROJECT_DIR}/voila"
MAX_LOG_SIZE=100000  # 100KB max log size

# Rotation du log si trop gros
if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null) -gt $MAX_LOG_SIZE ]; then
    mv "$LOG_FILE" "${LOG_FILE}.old"
fi

# Fonction de logging
log() {
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] $1" >> "$LOG_FILE"
    if [ "${VERBOSE:-}" = "1" ]; then
        echo "$1"
    fi
}

# Début
log "=== Début refresh session Voilà ==="

# Vérifier que le script voila existe
if [ ! -x "$VOILA_CMD" ]; then
    log "ERREUR: $VOILA_CMD non trouvé ou non exécutable"
    exit 1
fi

# Vérifier le status actuel
log "Vérification du status actuel..."
STATUS_OUTPUT=$("$VOILA_CMD" status 2>&1) || true
log "Status: $(echo "$STATUS_OUTPUT" | head -1)"

# Extraire les jours restants
DAYS_REMAINING=$(echo "$STATUS_OUTPUT" | grep -o '[0-9]*j restants' | grep -o '[0-9]*' || echo "?")
log "Jours restants avant refresh: $DAYS_REMAINING"

# Refresh seulement si nécessaire (moins de 5 jours) ou si --force
if [ "$1" = "--force" ] || [ "$DAYS_REMAINING" = "?" ] || [ "$DAYS_REMAINING" -lt 5 ]; then
    log "Exécution du refresh..."
    
    if "$VOILA_CMD" refresh --quiet; then
        log "✅ Refresh réussi"
        
        # Vérifier le nouveau status
        NEW_STATUS=$("$VOILA_CMD" status 2>&1) || true
        NEW_DAYS=$(echo "$NEW_STATUS" | grep -o '[0-9]*j restants' | grep -o '[0-9]*' || echo "?")
        log "Nouveaux jours restants: $NEW_DAYS"
        
        exit 0
    else
        log "❌ Échec du refresh"
        exit 1
    fi
else
    log "⏭️ Refresh non nécessaire ($DAYS_REMAINING jours restants >= 5)"
    exit 0
fi
