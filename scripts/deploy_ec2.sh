#!/bin/bash
# ============================================================
# Script de déploiement EC2 — Data Engineering Dashboard
# Usage: bash scripts/deploy_ec2.sh
# ============================================================

EC2_IP="13.39.99.56"
EC2_USER="ubuntu"
PEM_KEY="$HOME/Downloads/Projet_Data_Engineering.pem"
LOCAL_DASHBOARDS="./output/dashboards"
REMOTE_WWW="/home/ubuntu/www"

echo "=== Déploiement vers EC2 $EC2_IP ==="

# 1. Créer les dossiers sur EC2
echo "1. Création des dossiers..."
ssh -i "$PEM_KEY" $EC2_USER@$EC2_IP "mkdir -p $REMOTE_WWW/dashboards"

# 2. Transfert des fichiers
echo "2. Transfert des dashboards..."
scp -i "$PEM_KEY" \
  "$LOCAL_DASHBOARDS/index.html" \
  "$LOCAL_DASHBOARDS/dashboard_energy_idf.html" \
  "$LOCAL_DASHBOARDS/dashboard_comparaison.html" \
  $EC2_USER@$EC2_IP:$REMOTE_WWW/dashboards/

# 3. Vérifier et relancer le serveur HTTP
echo "3. Vérification du serveur HTTP..."
ssh -i "$PEM_KEY" $EC2_USER@$EC2_IP << 'REMOTE'
  # Arrêter l'ancien serveur
  pkill -f "http.server 8080" 2>/dev/null || true
  sleep 1

  # Configurer démarrage automatique via crontab
  (crontab -l 2>/dev/null | grep -v "http.server"; echo "@reboot cd /home/ubuntu/www && nohup python3 -m http.server 8080 > /tmp/server.log 2>&1 &") | crontab -

  # Démarrer le serveur
  cd /home/ubuntu/www
  nohup python3 -m http.server 8080 > /tmp/server.log 2>&1 &
  sleep 2

  echo "Serveur HTTP démarré sur le port 8080"
  ps aux | grep http.server | grep -v grep
REMOTE

echo ""
echo "=== Déploiement terminé ! ==="
echo ""
echo "Accès aux dashboards :"
echo "  → Accueil    : http://$EC2_IP:8080/dashboards/"
echo "  → IDF        : http://$EC2_IP:8080/dashboards/dashboard_energy_idf.html"
echo "  → Comparaison: http://$EC2_IP:8080/dashboards/dashboard_comparaison.html"
