"""
Clustering — Segmentation des régions par profil de consommation énergétique.
Utilise K-means pour identifier des profils distincts.
"""
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from src.utils.logger import get_logger


class ConsumptionClustering:
    """Clustérise les régions par profil de consommation."""

    def __init__(self, df: pd.DataFrame):
        """
        Initialise le clustériseur.

        Args:
            df: DataFrame avec au minimum datetime, region, consommation.

        Raises:
            ValueError: Si DataFrame vide ou sans région.
        """
        if df is None or df.empty:
            raise ValueError("DataFrame vide ou None")

        if "region" not in df.columns:
            raise ValueError("Colonne 'region' requise pour clustering")

        self.df = df.copy()
        self.logger = get_logger(self.__class__.__name__)
        self.scaler = StandardScaler()
        self.model = None
        self.clusters = None

        self.logger.info("ConsumptionClustering initialisé: %d lignes", len(df))

    def prepare_features(self) -> pd.DataFrame:
        """
        Prépare les features pour le clustering.

        Calcule des statistiques par région:
        - consommation moyenne, min, max, std
        - consommation de pointe (heure)
        - profil diurne vs nocturne
        """
        cons_col = self._find_column(
            ["elec_consumption_mw", "consommation_brute_electricite_rte", "total_consumption_mw"]
        )

        features = []

        for region in self.df["region"].unique():
            if pd.isna(region):
                continue

            region_data = self.df[self.df["region"] == region]

            if len(region_data) < 10:
                continue

            cons = region_data[cons_col]

            # Statistiques de base
            feat = {
                "region": region,
                "mean_consumption": cons.mean(),
                "min_consumption": cons.min(),
                "max_consumption": cons.max(),
                "std_consumption": cons.std(),
                "cv_consumption": cons.std() / cons.mean() if cons.mean() > 0 else 0,
            }

            # Profil horaire (si hour disponible)
            if "hour" in region_data.columns:
                hourly = region_data.groupby("hour")[cons_col].mean()
                day_hours = hourly[6:20]  # 6h-20h
                night_hours = pd.concat([hourly[0:6], hourly[20:24]])  # 0h-6h + 20h-24h

                feat["day_avg"] = float(day_hours.mean()) if len(day_hours) > 0 else 0
                feat["night_avg"] = float(night_hours.mean()) if len(night_hours) > 0 else 0
                feat["day_night_ratio"] = (
                    feat["day_avg"] / feat["night_avg"] if feat["night_avg"] > 0 else 1
                )
                feat["peak_hour"] = int(hourly.idxmax())

            # Profil saisonnier (si month disponible)
            if "month" in region_data.columns:
                winter_months = region_data[region_data["month"].isin([12, 1, 2])]
                summer_months = region_data[region_data["month"].isin([6, 7, 8])]

                feat["winter_avg"] = (
                    float(winter_months[cons_col].mean()) if len(winter_months) > 0 else 0
                )
                feat["summer_avg"] = (
                    float(summer_months[cons_col].mean()) if len(summer_months) > 0 else 0
                )
                feat["seasonality"] = (
                    feat["winter_avg"] / feat["summer_avg"]
                    if feat["summer_avg"] > 0
                    else 1
                )

            features.append(feat)

        features_df = pd.DataFrame(features)
        self.logger.info(
            "Features préparés: %d régions, %d variables", len(features_df), len(features_df.columns)
        )
        return features_df

    def fit_kmeans(self, n_clusters: int = 4, random_state: int = 42) -> KMeans:
        """
        Entraîne le modèle K-means.

        Args:
            n_clusters: Nombre de clusters.
            random_state: Graine aléatoire.

        Returns:
            Modèle KMeans entraîné.
        """
        features_df = self.prepare_features()

        if len(features_df) < n_clusters:
            self.logger.warning(
                "Pas assez de régions (%d) pour %d clusters", len(features_df), n_clusters
            )
            n_clusters = max(2, len(features_df) - 1)

        # Sélectionner les colonnes numériques (exclure region)
        numeric_cols = features_df.select_dtypes(include=[np.number]).columns.tolist()

        X = features_df[numeric_cols].fillna(0).values
        X_scaled = self.scaler.fit_transform(X)

        self.model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
        clusters = self.model.fit_predict(X_scaled)

        features_df["cluster"] = clusters
        self.clusters = features_df

        self.logger.info(
            "K-means entraîné: %d clusters, inertie=%.2f",
            n_clusters, self.model.inertia_,
        )

        return self.model

    def get_clusters(self) -> Dict[int, List[str]]:
        """
        Retourne les régions par cluster.

        Returns:
            Dict cluster_id → liste des régions.
        """
        if self.clusters is None:
            raise ValueError("Modèle non entraîné (appeler fit_kmeans d'abord)")

        result = {}
        for cluster_id in self.clusters["cluster"].unique():
            regions = self.clusters[self.clusters["cluster"] == cluster_id]["region"].tolist()
            result[int(cluster_id)] = regions

        return result

    def get_cluster_profiles(self) -> Dict[int, Dict]:
        """
        Retourne le profil moyen de chaque cluster.

        Returns:
            Dict cluster_id → statistiques moyennes.
        """
        if self.clusters is None:
            raise ValueError("Modèle non entraîné")

        result = {}

        for cluster_id in self.clusters["cluster"].unique():
            cluster_data = self.clusters[self.clusters["cluster"] == cluster_id]

            numeric_cols = cluster_data.select_dtypes(include=[np.number]).columns.tolist()
            numeric_cols.remove("cluster")

            profile = {}
            for col in numeric_cols:
                profile[col] = float(cluster_data[col].mean())

            result[int(cluster_id)] = profile

        return result

    def elbow_curve(self, max_clusters: int = 10) -> Dict[int, float]:
        """
        Calcule la courbe d'inertie pour choisir n_clusters optimal.

        Args:
            max_clusters: Nombre maximum de clusters à tester.

        Returns:
            Dict n_clusters → inertie.
        """
        features_df = self.prepare_features()

        numeric_cols = features_df.select_dtypes(include=[np.number]).columns.tolist()
        X = features_df[numeric_cols].fillna(0).values
        X_scaled = self.scaler.fit_transform(X)

        inertias = {}
        for k in range(2, min(max_clusters + 1, len(features_df))):
            km = KMeans(n_clusters=k, random_state=42, n_init=5)
            km.fit(X_scaled)
            inertias[k] = float(km.inertia_)

        self.logger.info("Courbe d'inertie calculée: %d points", len(inertias))
        return inertias

    def _find_column(self, candidates: list[str]) -> str:
        """Trouve la première colonne disponible."""
        for col in candidates:
            if col in self.df.columns:
                return col
        return None
