"""
Transformer — Nettoyage, normalisation et enrichissement des données
de consommation énergétique Île-de-France.
"""
from typing import Optional

import pandas as pd

from src.utils.logger import get_logger


class Transformer:
    """
    Transforme les données brutes en données propres et analysables.

    Pipeline de transformation :
        1. Nettoyage des colonnes
        2. Conversion des types
        3. Gestion des valeurs manquantes
        4. Enrichissement temporel
        5. Calcul d'indicateurs dérivés
        6. Validation finale
    """

    # Mapping de renommage des colonnes ODRE → noms normalisés
    COLUMN_MAPPING = {
        "date_heure": "datetime",
        "code_insee_region": "region_code",
        "region": "region_name",
        "consommation_brute_electricite_mw": "elec_consumption_mw",
        "consommation_brute_gaz_mw": "gas_consumption_mw",
        "consommation_brute_totale_mw": "total_consumption_mw",
    }

    def __init__(self, df: pd.DataFrame):
        """
        Args:
            df: DataFrame brut à transformer.

        Raises:
            ValueError: Si le DataFrame est vide.
        """
        if df is None or df.empty:
            raise ValueError("DataFrame vide ou None fourni au Transformer")

        self.df = df.copy()
        self.logger = get_logger(self.__class__.__name__)
        self._initial_rows = len(df)
        self.logger.info(
            "Transformer initialisé: %d lignes, %d colonnes",
            len(df), len(df.columns),
        )

    def rename_columns(self) -> "Transformer":
        """Renomme les colonnes selon le mapping normalisé."""
        existing_mappings = {
            k: v for k, v in self.COLUMN_MAPPING.items() if k in self.df.columns
        }
        self.df = self.df.rename(columns=existing_mappings)
        self.logger.info("Colonnes renommées: %s", list(existing_mappings.keys()))
        return self

    def convert_datetime(self, column: str = "datetime") -> "Transformer":
        """
        Convertit une colonne en datetime avec gestion des erreurs.

        Args:
            column: Nom de la colonne à convertir.
        """
        if column not in self.df.columns:
            self.logger.warning("Colonne '%s' absente, conversion ignorée", column)
            return self

        try:
            self.df[column] = pd.to_datetime(self.df[column], utc=True, errors="coerce")
            invalid_count = self.df[column].isna().sum()
            if invalid_count > 0:
                self.logger.warning(
                    "%d valeurs datetime invalides détectées", invalid_count
                )
            self.logger.info("Colonne '%s' convertie en datetime", column)
        except Exception as e:
            self.logger.error("Erreur conversion datetime: %s", e)
            raise

        return self

    def handle_missing_values(
        self,
        strategy: str = "drop",
        fill_value: Optional[float] = None,
        subset: Optional[list[str]] = None,
    ) -> "Transformer":
        """
        Gère les valeurs manquantes.

        Args:
            strategy: 'drop', 'fill_zero', 'fill_mean', 'fill_median', 'fill_value'.
            fill_value: Valeur de remplacement si strategy='fill_value'.
            subset: Colonnes ciblées (None = toutes).
        """
        before = len(self.df)
        missing_before = self.df.isna().sum().sum()

        if strategy == "drop":
            self.df = self.df.dropna(subset=subset)
        elif strategy == "fill_zero":
            cols = subset or self.df.select_dtypes(include="number").columns
            self.df[cols] = self.df[cols].fillna(0)
        elif strategy == "fill_mean":
            cols = subset or self.df.select_dtypes(include="number").columns
            self.df[cols] = self.df[cols].fillna(self.df[cols].mean())
        elif strategy == "fill_median":
            cols = subset or self.df.select_dtypes(include="number").columns
            self.df[cols] = self.df[cols].fillna(self.df[cols].median())
        elif strategy == "fill_value":
            if fill_value is None:
                raise ValueError("fill_value requis pour strategy='fill_value'")
            cols = subset or self.df.columns.tolist()
            self.df[cols] = self.df[cols].fillna(fill_value)
        else:
            raise ValueError(f"Stratégie inconnue: {strategy}")

        after = len(self.df)
        missing_after = self.df.isna().sum().sum()
        self.logger.info(
            "Missing values: %d → %d | Lignes: %d → %d (stratégie: %s)",
            missing_before, missing_after, before, after, strategy,
        )
        return self

    def enrich_temporal(self, datetime_col: str = "datetime") -> "Transformer":
        """
        Ajoute des colonnes temporelles dérivées.

        Args:
            datetime_col: Colonne datetime source.
        """
        if datetime_col not in self.df.columns:
            self.logger.warning("Colonne '%s' absente, enrichissement ignoré", datetime_col)
            return self

        try:
            dt = self.df[datetime_col]
            self.df["year"] = dt.dt.year
            self.df["month"] = dt.dt.month
            self.df["day"] = dt.dt.day
            self.df["hour"] = dt.dt.hour
            self.df["day_of_week"] = dt.dt.dayofweek  # 0=Lundi
            self.df["is_weekend"] = dt.dt.dayofweek.isin([5, 6])
            self.df["quarter"] = dt.dt.quarter

            self.logger.info("Enrichissement temporel ajouté: 7 colonnes")
        except Exception as e:
            self.logger.error("Erreur enrichissement temporel: %s", e)
            raise

        return self

    def compute_derived_metrics(self) -> "Transformer":
        """Calcule des indicateurs dérivés métier."""
        try:
            # Consommation totale si absente
            elec_col = "elec_consumption_mw"
            gas_col = "gas_consumption_mw"
            total_col = "total_consumption_mw"

            if elec_col in self.df.columns and gas_col in self.df.columns:
                if total_col not in self.df.columns:
                    self.df[total_col] = self.df[elec_col] + self.df[gas_col]
                    self.logger.info("Colonne '%s' calculée", total_col)

                # Ratio électricité / total
                self.df["elec_ratio"] = (
                    self.df[elec_col] / self.df[total_col].replace(0, float("nan"))
                ).round(4)

                # Variation par rapport à la ligne précédente (tri par datetime)
                if "datetime" in self.df.columns:
                    self.df = self.df.sort_values("datetime")
                    self.df["elec_change_mw"] = self.df[elec_col].diff()
                    self.df["elec_change_pct"] = (
                        self.df[elec_col].pct_change() * 100
                    ).round(2)

                self.logger.info("Métriques dérivées calculées")
            else:
                self.logger.warning(
                    "Colonnes '%s' ou '%s' absentes, métriques non calculées",
                    elec_col, gas_col,
                )
        except Exception as e:
            self.logger.error("Erreur calcul métriques: %s", e)
            raise

        return self

    def filter_outliers(
        self, column: str, lower_quantile: float = 0.01, upper_quantile: float = 0.99
    ) -> "Transformer":
        """
        Filtre les outliers par quantiles.

        Args:
            column: Colonne cible.
            lower_quantile: Seuil inférieur.
            upper_quantile: Seuil supérieur.
        """
        if column not in self.df.columns:
            self.logger.warning("Colonne '%s' absente, filtrage ignoré", column)
            return self

        before = len(self.df)
        lower = self.df[column].quantile(lower_quantile)
        upper = self.df[column].quantile(upper_quantile)
        self.df = self.df[
            (self.df[column] >= lower) & (self.df[column] <= upper)
        ]
        removed = before - len(self.df)
        self.logger.info(
            "Outliers filtrés sur '%s': %d lignes supprimées [%.2f, %.2f]",
            column, removed, lower, upper,
        )
        return self

    def validate(self) -> "Transformer":
        """Validation finale des données transformées."""
        issues = []

        if self.df.empty:
            issues.append("DataFrame vide après transformation")

        null_pct = (self.df.isna().sum() / len(self.df) * 100).round(2)
        high_null_cols = null_pct[null_pct > 50].index.tolist()
        if high_null_cols:
            issues.append(f"Colonnes avec >50% de nulls: {high_null_cols}")

        dup_count = self.df.duplicated().sum()
        if dup_count > 0:
            issues.append(f"{dup_count} doublons détectés")
            self.df = self.df.drop_duplicates()

        if issues:
            for issue in issues:
                self.logger.warning("VALIDATION: %s", issue)
        else:
            self.logger.info("VALIDATION: OK")

        final_rows = len(self.df)
        self.logger.info(
            "Transformation terminée: %d → %d lignes (%.1f%% conservées)",
            self._initial_rows, final_rows,
            (final_rows / self._initial_rows * 100) if self._initial_rows > 0 else 0,
        )
        return self

    def get_result(self) -> pd.DataFrame:
        """Retourne le DataFrame transformé."""
        return self.df.copy()

    def run_full_pipeline(self) -> pd.DataFrame:
        """
        Exécute le pipeline de transformation complet (chaîné).

        Returns:
            DataFrame transformé et validé.
        """
        return (
            self.rename_columns()
            .convert_datetime()
            .handle_missing_values(strategy="fill_zero")
            .enrich_temporal()
            .compute_derived_metrics()
            .validate()
            .get_result()
        )
