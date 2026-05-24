# Périmètre produit & potentiel commercial

## Ce que fait ce projet (périmètre actuel)

C'est une **plateforme de données énergétiques** pour la France, qui :

- Collecte automatiquement chaque jour les données de **consommation électrique** (ODRE), de **mix de production** (RTE : nucléaire, éolien, solaire...) et de **météo** (Open-Meteo)
- Croise ces données et les nettoie (ETL)
- Génère des **tableaux de bord HTML interactifs** et des dashboards Grafana
- Fait de la **prévision** (Prophet + ARIMA), du **clustering régional** (K-means) et de l'**analyse de corrélation** température/consommation
- S'auto-déploie chaque jour sur AWS EC2 via GitLab CI/CD

Couverture actuelle : **4 régions** (Île-de-France, Provence, Bretagne, Nouvelle-Aquitaine)

---

## Périmètre recommandé pour une vente

| Dimension | Périmètre |
|---|---|
| **Géographie** | France métropolitaine, extensible à d'autres pays via les mêmes API |
| **Énergie** | Électricité + gaz (ODRE), production multi-filières (RTE) |
| **Horizon temporel** | Historique (J-7 à J-365) + prévision J+7 |
| **Granularité** | Par demi-heure, par région, par filière |
| **Livrable** | Dashboard web + API REST + exports CSV/JSON |

**Hors périmètre aujourd'hui** (à préciser lors d'une vente) : prix de l'électricité, données de facturation individuelle, données ENEDIS compteur Linky.

---

## Problèmes résolus — Particuliers

| Problème | Comment ce projet y répond |
|---|---|
| "Quand consommer pour réduire ma facture ?" | Les courbes de consommation par heure et par saison permettent d'identifier les heures creuses réelles à l'échelle régionale |
| "Mon chauffage est-il vraiment impacté par la météo ?" | La corrélation température × consommation (dans `correlation_analysis.py`) visualise cet impact directement |
| "Y a-t-il du courant vert dans mon réseau en ce moment ?" | Le mix RTE (part solaire, éolien, nucléaire) par heure permet de savoir quand l'électricité est la plus "verte" |
| "Quand charger ma voiture électrique au meilleur moment ?" | Combiné aux prévisions Prophet, on peut prédire les pics et creux de consommation à J+1/J+7 |

**Modèle commercial possible :** application mobile grand public ou widget intégrable sur un comparateur d'énergie (type Hello Watt, Papernest).

---

## Problèmes résolus — Secteur public / institutionnel

| Acteur | Problème résolu |
|---|---|
| **Collectivités territoriales** | Suivre la consommation de leur région, comparer avec les voisins, alimenter leur bilan carbone |
| **Opérateurs de réseau** | Disposer d'un pipeline de gouvernance des données avec score qualité automatique (`quality.py`) |
| **Agences de transition énergétique** (ADEME, CEREMA) | Avoir un outil d'analyse régionale prêt à l'emploi sans développer leur propre ETL |
| **Bureaux d'études** | Croiser météo et consommation pour dimensionner des projets EnR ou des plans de sobriété |
| **Directions informatiques** | Un pipeline CI/CD clé-en-main, dockerisé, avec tests et monitoring Prometheus/Grafana |

**Modèle commercial possible :** SaaS B2G (Business-to-Government) avec abonnement annuel, ou prestation de déploiement sur infrastructure cliente.

---

## Ce qu'il faudrait ajouter pour le rendre vendable

1. **Interface utilisateur** : aujourd'hui c'est un dashboard HTML statique — il faudrait une vraie UI (React ou Streamlit) avec authentification
2. **Multi-tenant** : permettre à plusieurs clients d'avoir leurs données isolées
3. **API REST documentée** : FastAPI + Swagger pour que les clients intègrent les données dans leurs propres outils
4. **Prix de l'électricité** : coupler avec les données EPEX Spot ou EDF pour que les alertes aient un sens financier
5. **Alertes et notifications** : e-mail/SMS quand la consommation dépasse un seuil ou quand la part renouvelable est maximale

Le cœur technique (pipeline, ETL, prévision, gouvernance) est déjà solide — c'est l'habillage produit qui manque pour une commercialisation.
