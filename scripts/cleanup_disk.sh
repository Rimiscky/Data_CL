#!/bin/bash
# ============================================================
# cleanup_disk.sh — Libération disque EC2
# Cible : Docker, logs, data/raw anciens, cache APT
#
# Installation cron (hebdomadaire, dimanche 3h UTC) :
#   bash scripts/setup_cleanup_cron.sh
#
# Exécution manuelle :
#   bash scripts/cleanup_disk.sh [--dry-run]
# ============================================================

set -euo pipefail

# ── Configuration ──────────────────────────────────────────
PROJECT_DIR="${PROJECT_DIR:-/home/ubuntu}"
LOG_FILE="/var/log/cleanup_disk.log"
RAW_RETENTION_DAYS="${RAW_RETENTION_DAYS:-7}"    # garder N jours de data/raw
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-14}"   # garder N jours de logs app
DRY_RUN=false

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

# ── Helpers ────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
run() {
    if $DRY_RUN; then
        log "[DRY-RUN] $*"
    else
        log "→ $*"
        eval "$*" 2>&1 | tee -a "$LOG_FILE" || true
    fi
}
disk_free() { df -h / | awk 'NR==2 {print $4 " libres (" $5 " utilisé)"}'; }

# ── Début ──────────────────────────────────────────────────
log "============================================"
log "Nettoyage disque démarré${DRY_RUN:+ (dry-run)}"
log "Espace avant : $(disk_free)"
log "============================================"

FREED_TOTAL=0

# ── 1. Docker ──────────────────────────────────────────────
log ""
log "--- 1/4 Docker ---"
if command -v docker &>/dev/null; then
    DOCKER_BEFORE=$(docker system df --format '{{.Size}}' 2>/dev/null | head -1 || echo "?")

    # Containers stoppés
    run "docker container prune -f"
    # Images non utilisées (dangling + sans tag)
    run "docker image prune -af"
    # Volumes orphelins
    run "docker volume prune -f"
    # Build cache (> 24h)
    run "docker builder prune -f --filter 'until=24h'"
    # Networks inutilisés
    run "docker network prune -f"

    DOCKER_AFTER=$(docker system df 2>/dev/null | tail -n +2 | awk '{sum+=$4} END {print sum " MiB récupérés"}' || echo "")
    log "Docker nettoyé. $DOCKER_AFTER"
else
    log "Docker non installé — ignoré"
fi

# ── 2. Logs système ────────────────────────────────────────
log ""
log "--- 2/4 Logs système & application ---"

# journald — garder 7 jours max et 200 MB max
run "journalctl --vacuum-time=7d --vacuum-size=200M"

# /var/log : rotation des logs > 30 jours (sans supprimer les fichiers actifs)
run "find /var/log -type f -name '*.gz' -mtime +30 -delete"
run "find /var/log -type f -name '*.1' -mtime +14 -delete"
run "find /var/log -type f -name '*.old' -mtime +14 -delete"

# Logs application pipeline
if [[ -d "$PROJECT_DIR/logs" ]]; then
    run "find '$PROJECT_DIR/logs' -type f -name '*.log' -mtime +$LOG_RETENTION_DAYS -delete"
    run "find '$PROJECT_DIR/logs' -type f -name '*.log.*' -mtime +$LOG_RETENTION_DAYS -delete"
    log "Logs app nettoyés (> $LOG_RETENTION_DAYS jours)"
fi

# Logs Airflow (si présents)
AIRFLOW_LOGS="/home/ubuntu/airflow/logs"
if [[ -d "$AIRFLOW_LOGS" ]]; then
    run "find '$AIRFLOW_LOGS' -type f -name '*.log' -mtime +$LOG_RETENTION_DAYS -delete"
    run "find '$AIRFLOW_LOGS' -type d -empty -mindepth 2 -delete"
    log "Logs Airflow nettoyés (> $LOG_RETENTION_DAYS jours)"
fi

# ── 3. Données brutes (data/raw/) ──────────────────────────
log ""
log "--- 3/4 Données brutes (data/raw/) ---"

for subdir in api meteo rte scraping; do
    TARGET="$PROJECT_DIR/data/raw/$subdir"
    if [[ -d "$TARGET" ]]; then
        COUNT=$(find "$TARGET" -type f -mtime +$RAW_RETENTION_DAYS | wc -l)
        log "Suppression de $COUNT fichier(s) dans $subdir (> $RAW_RETENTION_DAYS jours)"
        run "find '$TARGET' -type f -mtime +$RAW_RETENTION_DAYS -delete"
    fi
done

# Données warehouse : garder 30 jours sauf latest.csv
if [[ -d "$PROJECT_DIR/data/warehouse" ]]; then
    run "find '$PROJECT_DIR/data/warehouse' -type f ! -name 'latest.csv' -mtime +30 -delete"
    log "Warehouse nettoyé (> 30 jours, latest.csv conservé)"
fi

# Fichiers temporaires Python
run "find '$PROJECT_DIR' -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"
run "find '$PROJECT_DIR' -name '*.pyc' -delete 2>/dev/null || true"

# ── 4. Cache système (APT + pip) ───────────────────────────
log ""
log "--- 4/4 Cache APT & pip ---"

run "apt-get autoremove -y"
run "apt-get clean"
run "rm -rf /var/cache/apt/archives/*.deb"

# Cache pip global
run "pip3 cache purge 2>/dev/null || true"

# /tmp : fichiers > 7 jours
run "find /tmp -type f -mtime +7 -delete 2>/dev/null || true"
run "find /tmp -type d -empty -mindepth 1 -delete 2>/dev/null || true"

# ── Bilan ──────────────────────────────────────────────────
log ""
log "============================================"
log "Nettoyage terminé"
log "Espace après : $(disk_free)"
log "============================================"
