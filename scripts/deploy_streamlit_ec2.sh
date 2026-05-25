#!/bin/bash
# ============================================================
# deploy_streamlit_ec2.sh — Déploie et démarre Streamlit sur EC2
# Usage: bash scripts/deploy_streamlit_ec2.sh
# ============================================================

set -euo pipefail

EC2_IP="13.39.99.56"
EC2_USER="ubuntu"
PEM_KEY="${PEM_KEY:-$HOME/Downloads/Projet_Data_Engineering.pem}"
REMOTE_HOME="/home/ubuntu"

echo "=== Déploiement Streamlit sur EC2 $EC2_IP ==="

# 1. Copier app_streamlit.py + src/ sur l'EC2
echo "1. Transfert du code..."
scp -i "$PEM_KEY" app_streamlit.py "$EC2_USER@$EC2_IP:$REMOTE_HOME/"
scp -i "$PEM_KEY" -r src/ "$EC2_USER@$EC2_IP:$REMOTE_HOME/"

# 2. Installer les dépendances Python
echo "2. Installation des dépendances..."
ssh -i "$PEM_KEY" "$EC2_USER@$EC2_IP" "
  pip3 install --quiet --upgrade streamlit pandas plotly numpy scikit-learn statsmodels
  echo 'Packages installés.'
"

# 3. Créer le service systemd
echo "3. Configuration du service systemd..."
ssh -i "$PEM_KEY" "$EC2_USER@$EC2_IP" "sudo tee /etc/systemd/system/streamlit.service > /dev/null << 'SERVICE'
[Unit]
Description=Streamlit Energy Dashboard
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu
ExecStart=/usr/bin/python3 -m streamlit run /home/ubuntu/app_streamlit.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
Restart=on-failure
RestartSec=5
Environment=HOME=/home/ubuntu

[Install]
WantedBy=multi-user.target
SERVICE
"

# 4. Activer et démarrer le service
echo "4. Démarrage du service..."
ssh -i "$PEM_KEY" "$EC2_USER@$EC2_IP" "
  sudo systemctl daemon-reload
  sudo systemctl enable streamlit
  sudo systemctl restart streamlit
  sleep 3
  sudo systemctl status streamlit --no-pager | head -15
"

echo ""
echo "=== Déploiement terminé ==="
echo "Streamlit accessible sur : http://$EC2_IP:8501"
echo ""
echo "⚠️  Si le port 8501 n'est pas encore ouvert dans le Security Group AWS :"
echo "   AWS Console → EC2 → Security Groups → Inbound rules"
echo "   Ajouter : Type=TCP  Port=8501  Source=0.0.0.0/0"
echo ""
echo "Commandes utiles sur l'EC2 :"
echo "  Statut  : sudo systemctl status streamlit"
echo "  Logs    : sudo journalctl -u streamlit -f"
echo "  Restart : sudo systemctl restart streamlit"
