"""
Forecasting — Prédiction de la consommation d'énergie.
Utilise ARIMA et Prophet pour des prévisions multi-horizons.
"""
from datetime import timedelta
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from src.utils.logger import get_logger


class ConsumptionForecaster:
    """Effectue des prévisions de consommation énergétique."""

    def __init__(self, df: pd.DataFrame, target_column: Optional[str] = None):
        """
        Initialise le modèle de prévision.

        Args:
            df: DataFrame avec datetime et consommation.
            target_column: Nom de la colonne à prédire.

        Raises:
            ValueError: Si DataFrame vide ou sans datetime.
        """
        if df is None or df.empty:
            raise ValueError("DataFrame vide")

        if "datetime" not in df.columns:
            raise ValueError("Colonne 'datetime' requise")

        self.df = df.copy()
        self.df = self.df.sort_values("datetime").reset_index(drop=True)

        self.logger = get_logger(self.__class__.__name__)

        # Détecter la colonne cible
        if target_column is None:
            candidates = [
                "elec_consumption_mw",
                "consommation_brute_electricite_rte",
                "total_consumption_mw",
            ]
            target_column = next((c for c in candidates if c in df.columns), None)

        if target_column is None:
            raise ValueError("Colonne de consommation non trouvée")

        self.target_column = target_column
        self.logger.info("ConsumptionForecaster initialisé: %d lignes", len(df))

    def train_arima(self, order: Tuple[int, int, int] = (1, 1, 1)) -> Dict:
        """
        Entraîne un modèle ARIMA sur la consommation.

        Args:
            order: Tuple (p, d, q) pour ARIMA.

        Returns:
            Dict avec résumé du modèle.
        """
        try:
            from statsmodels.tsa.arima.model import ARIMA

            ts = self.df[self.target_column].dropna()

            model = ARIMA(ts, order=order)
            result = model.fit()

            self.logger.info(
                "ARIMA entraîné: AIC=%.1f, BIC=%.1f",
                result.aic, result.bic,
            )

            return {
                "type": "ARIMA",
                "order": order,
                "aic": float(result.aic),
                "bic": float(result.bic),
                "model": result,
            }

        except ImportError:
            self.logger.error("statsmodels non installé: pip install statsmodels")
            return {}
        except Exception as e:
            self.logger.error("Erreur ARIMA: %s", e)
            return {}

    def train_prophet(self) -> Dict:
        """
        Entraîne un modèle Prophet avec saisonnalité.

        Returns:
            Dict avec modèle Prophet et paramètres.
        """
        try:
            from prophet import Prophet

            # Préparer les données au format Prophet
            prophet_df = self.df[["datetime", self.target_column]].copy()
            prophet_df.columns = ["ds", "y"]
            prophet_df = prophet_df.dropna()

            # Ajouter les regresseurs saisonniers
            if "hour" in self.df.columns:
                prophet_df["hour"] = self.df["hour"]
            if "day_of_week" in self.df.columns:
                prophet_df["day_of_week"] = self.df["day_of_week"]

            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=True,
                seasonality_mode="additive",
                interval_width=0.95,
            )

            # Ajouter des regresseurs
            if "hour" in prophet_df.columns:
                model.add_regressor("hour")
            if "day_of_week" in prophet_df.columns:
                model.add_regressor("day_of_week")

            with open("/dev/null", "w") as devnull:
                import sys
                old_stdout = sys.stdout
                sys.stdout = devnull
                model.fit(prophet_df)
                sys.stdout = old_stdout

            self.logger.info("Prophet entraîné avec saisonnalités multiples")

            return {
                "type": "Prophet",
                "model": model,
                "training_data": prophet_df,
            }

        except ImportError:
            self.logger.error("prophet non installé: pip install prophet")
            return {}
        except Exception as e:
            self.logger.error("Erreur Prophet: %s", e)
            return {}

    def predict_arima(
        self, arima_result, periods: int = 7
    ) -> Optional[pd.DataFrame]:
        """
        Effectue des prévisions avec ARIMA.

        Args:
            arima_result: Résultat d'entraînement ARIMA.
            periods: Nombre de périodes à prédire.

        Returns:
            DataFrame avec prévisions ou None.
        """
        try:
            if not arima_result or "model" not in arima_result:
                return None

            model = arima_result["model"]
            forecast = model.get_forecast(steps=periods)
            forecast_df = forecast.conf_int()
            forecast_df.columns = ["lower_bound", "upper_bound"]
            forecast_df["forecast"] = forecast.predicted_mean

            self.logger.info("Prévision ARIMA: %d périodes", periods)
            return forecast_df

        except Exception as e:
            self.logger.error("Erreur prévision ARIMA: %s", e)
            return None

    def predict_prophet(
        self, prophet_result, periods: int = 7
    ) -> Optional[pd.DataFrame]:
        """
        Effectue des prévisions avec Prophet.

        Args:
            prophet_result: Résultat d'entraînement Prophet.
            periods: Nombre de jours à prédire.

        Returns:
            DataFrame avec prévisions ou None.
        """
        try:
            if not prophet_result or "model" not in prophet_result:
                return None

            model = prophet_result["model"]
            last_date = prophet_result["training_data"]["ds"].max()

            future_dates = pd.date_range(
                start=last_date + timedelta(hours=1),
                periods=periods * 24,
                freq="h",
            )
            future_df = pd.DataFrame({"ds": future_dates})

            # Remplir les regresseurs
            future_df["hour"] = future_df["ds"].dt.hour
            future_df["day_of_week"] = future_df["ds"].dt.dayofweek

            forecast = model.predict(future_df)

            result_df = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
            result_df.columns = ["datetime", "forecast", "lower_bound", "upper_bound"]

            self.logger.info("Prévision Prophet: %d périodes", periods)
            return result_df

        except Exception as e:
            self.logger.error("Erreur prévision Prophet: %s", e)
            return None

    def evaluate_model(self, actual: pd.Series, predicted: pd.Series) -> Dict:
        """
        Évalue les performances du modèle.

        Args:
            actual: Valeurs réelles.
            predicted: Valeurs prédites.

        Returns:
            Dict avec MAE, RMSE, MAPE, R².
        """
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

        mae = mean_absolute_error(actual, predicted)
        rmse = np.sqrt(mean_squared_error(actual, predicted))
        mape = np.mean(np.abs((actual - predicted) / actual)) * 100 if (actual != 0).all() else 0
        r2 = r2_score(actual, predicted)

        metrics = {
            "MAE": float(mae),
            "RMSE": float(rmse),
            "MAPE": float(mape),
            "R2": float(r2),
        }

        self.logger.info(
            "Évaluation: MAE=%.2f, RMSE=%.2f, MAPE=%.2f%%, R²=%.3f",
            mae, rmse, mape, r2,
        )

        return metrics
