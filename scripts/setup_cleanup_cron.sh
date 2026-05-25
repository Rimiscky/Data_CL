#!/bin/bash
# ============================================================
# setup_cleanup_cron.sh — Installe cleanup_disk.sh sur EC2
# Usage : bash scripts/setup_cleanup_cron.sh
# ============================================================

EC2_IP="13.39.99.56"
EC2_USER="ubuntu"
PEM_KEY="${PEM_KEY:-$HOME/Downloads/Projet_Data_Engineering.pem}"
REMOTE_DIR="/home/ubuntu/Data_CL/scripts"
CRON_SCHEDULE="0 3 * * 0"   # Dimanche 3h UTC

echo "=== Installation du nettoyage disque sur EC2 $EC2_IP ==="

# 1. Copier le script sur l'EC2
echo "1. Transfert du script..."
scp -i "$PEM_KEY" \
    "$(dirname "$0")/cleanup_disk.sh" \
    "$EC2_USER@$EC2_IP:$REMOTE_DIR/cleanup_disk.sh"

# 2. Rendre exécutable + créer le fichier de log
echo "2. Permissions et log..."
ssh -i "$PEM_KEY" "$EC2_USER@$EC2_IP" << 'REMOTE'
chmod +x /home/ubuntu/Data_CL/scripts/cleanup_disk.sh
sudo touch /var/log/cleanup_disk.log
sudo chown ubuntu:ubuntu /var/log/cleanup_disk.log
echo "Script prêt."
REMOTE

# 3. Ajouter la crontab (sans doublon)
echo "3. Configuration cron ($CRON_SCHEDULE)..."
CRON_LINE="$CRON_SCHEDULE sudo bash $REMOTE_DIR/cleanup_disk.sh >> /var/log/cleanup_disk.log 2>&1"

ssh -i "$PEM_KEY" "$EC2_USER@$EC2_IP" "
    (crontab -l 2>/dev/null | grep -v 'cleanup_disk'; echo '$CRON_LINE') | crontab -
    echo 'Crontab installée :'
    crontab -l | grep cleanup_disk
"

# 4. Test dry-run
echo ""
echo "4. Test dry-run..."
ssh -i "$PEM_KEY" "$EC2_USER@$EC2_IP" \
    "sudo bash $REMOTE_DIR/cleanup_disk.sh --dry-run"

echo ""
echo "=== Installation terminée ==="
echo "Le nettoyage s'exécutera automatiquement : $CRON_SCHEDULE (dimanche 3h UTC)"
echo "Logs : /var/log/cleanup_disk.log"
echo ""
echo "Commandes utiles sur l'EC2 :"
echo "  Lancer maintenant : sudo bash $REMOTE_DIR/cleanup_disk.sh"
echo "  Suivre les logs   : tail -f /var/log/cleanup_disk.log"
echo "  Voir la crontab   : crontab -l"
