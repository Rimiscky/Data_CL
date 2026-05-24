"""
Dashboard croisé Énergie × Météo — Modulable par période.
Génère un dashboard HTML interactif avec filtres temporels via Plotly.
"""
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.utils.logger import get_logger


class CrossDashboardBuilder:
    """Dashboard croisé énergie/météo avec filtres par période."""

    COLORS = {
        "energy": "#1f77b4",
        "temp": "#ff7f0e",
        "humidity": "#2ca02c",
        "wind": "#9467bd",
        "rain": "#17becf",
        "weekend": "#d62728",
        "weekday": "#8c564b",
    }

    def __init__(
        self,
        df: pd.DataFrame,
        output_dir: Optional[Path] = None,
        region_label: str = "Île-de-France",
    ):
        """
        Args:
            df: DataFrame fusionné (énergie + météo).
            output_dir: Répertoire de sortie.
            region_label: Nom lisible de la région pour les titres.
        """
        if df is None or df.empty:
            raise ValueError("DataFrame ne peut pas être vide")
        self._df = df.copy()
        self.region_label = region_label
        self.output_dir = Path(output_dir) if output_dir else Path("output/dashboards")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(self.__class__.__name__)
        self._ensure_datetime()
        self._figures: dict[str, go.Figure] = {}

    def _ensure_datetime(self):
        if "datetime" in self._df.columns:
            self._df["datetime"] = pd.to_datetime(self._df["datetime"], utc=True)

    @property
    def df(self) -> pd.DataFrame:
        return self._df.copy()

    def _detect_elec_col(self) -> Optional[str]:
        for col in ["consommation_brute_electricite_rte", "elec_consumption_mw"]:
            if col in self._df.columns:
                return col
        return None

    def _filter_period(
        self, start: Optional[str] = None, end: Optional[str] = None
    ) -> pd.DataFrame:
        """Filtre le DataFrame par période."""
        df = self._df.copy()
        if "datetime" not in df.columns:
            return df
        if start:
            df = df[df["datetime"] >= pd.Timestamp(start, tz="UTC")]
        if end:
            df = df[df["datetime"] <= pd.Timestamp(end, tz="UTC")]
        return df

    def build_energy_vs_temperature(self) -> go.Figure:
        """Courbe croisée : consommation électrique vs température."""
        elec_col = self._detect_elec_col()
        if not elec_col or "temperature_2m" not in self._df.columns:
            return self._empty_figure("Données énergie/température manquantes")

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(
            go.Scatter(
                x=self._df["datetime"], y=self._df[elec_col],
                name="Consommation (MW)", mode="lines",
                line=dict(color=self.COLORS["energy"], width=2),
            ),
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=self._df["datetime"], y=self._df["temperature_2m"],
                name="Température (°C)", mode="lines",
                line=dict(color=self.COLORS["temp"], width=2, dash="dot"),
            ),
            secondary_y=True,
        )

        fig.update_layout(
            title="Consommation électrique vs Température — {self.region_label}",
            template="plotly_white",
            hovermode="x unified",
            xaxis=dict(
                rangeselector=dict(buttons=[
                    dict(count=1, label="1j", step="day", stepmode="backward"),
                    dict(count=3, label="3j", step="day", stepmode="backward"),
                    dict(count=7, label="1sem", step="day", stepmode="backward"),
                    dict(step="all", label="Tout"),
                ]),
                rangeslider=dict(visible=True),
                type="date",
            ),
        )
        fig.update_yaxes(title_text="Consommation (MW)", secondary_y=False)
        fig.update_yaxes(title_text="Température (°C)", secondary_y=True)

        self._figures["energy_vs_temp"] = fig
        return fig

    def build_scatter_temp_consumption(self) -> go.Figure:
        """Scatter plot : température vs consommation avec régression."""
        elec_col = self._detect_elec_col()
        if not elec_col or "temperature_2m" not in self._df.columns:
            return self._empty_figure("Données manquantes")

        df = self._df.dropna(subset=[elec_col, "temperature_2m"])

        # Couleur par période du jour
        colors = []
        if "hour" in df.columns:
            colors = df["hour"].apply(
                lambda h: "Nuit" if h < 6 else ("Matin" if h < 12 else ("Après-midi" if h < 18 else "Soir"))
            )
        else:
            colors = ["Données"] * len(df)

        fig = go.Figure()

        for period in colors.unique() if hasattr(colors, 'unique') else ["Données"]:
            mask = colors == period
            fig.add_trace(go.Scatter(
                x=df.loc[mask, "temperature_2m"],
                y=df.loc[mask, elec_col],
                mode="markers",
                name=period,
                marker=dict(size=5, opacity=0.6),
                hovertemplate="Temp: %{x:.1f}°C<br>Conso: %{y:.0f} MW<extra></extra>",
            ))

        # Ligne de tendance
        z = np.polyfit(df["temperature_2m"], df[elec_col], 2)
        p = np.poly1d(z)
        x_line = np.linspace(df["temperature_2m"].min(), df["temperature_2m"].max(), 100)
        fig.add_trace(go.Scatter(
            x=x_line, y=p(x_line),
            mode="lines", name="Tendance (poly2)",
            line=dict(color="red", width=2, dash="dash"),
        ))

        fig.update_layout(
            title="Corrélation Température → Consommation — {self.region_label}",
            xaxis_title="Température (°C)",
            yaxis_title="Consommation (MW)",
            template="plotly_white",
        )

        self._figures["scatter_temp_conso"] = fig
        return fig

    def build_weather_impact_bars(self) -> go.Figure:
        """Consommation moyenne par catégorie de température."""
        elec_col = self._detect_elec_col()
        if not elec_col or "temp_category" not in self._df.columns:
            return self._empty_figure("Catégories température manquantes")

        grouped = self._df.groupby("temp_category", observed=True)[elec_col].agg(
            ["mean", "std", "count"]
        ).reset_index()

        color_map = {
            "gel": "#08306b", "tres_froid": "#2171b5", "froid": "#6baed6",
            "frais": "#9ecae1", "doux": "#fdae6b", "chaud": "#e6550d",
            "canicule": "#a50f15",
        }
        colors = [color_map.get(str(c), "#999") for c in grouped["temp_category"]]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=grouped["temp_category"].astype(str),
            y=grouped["mean"],
            error_y=dict(type="data", array=grouped["std"], visible=True),
            marker_color=colors,
            text=[f"n={c}" for c in grouped["count"]],
            textposition="outside",
        ))

        fig.update_layout(
            title="Consommation moyenne par catégorie de température",
            xaxis_title="Catégorie de température",
            yaxis_title="Consommation moyenne (MW)",
            template="plotly_white",
        )

        self._figures["weather_impact"] = fig
        return fig

    def build_multivar_heatmap(self) -> go.Figure:
        """Heatmap de corrélation entre variables énergie et météo."""
        elec_col = self._detect_elec_col()
        meteo_cols = [
            c for c in [
                "temperature_2m", "apparent_temperature", "relative_humidity_2m",
                "wind_speed_10m", "precipitation", "cloud_cover", "surface_pressure",
            ] if c in self._df.columns
        ]

        if not elec_col or not meteo_cols:
            return self._empty_figure("Colonnes météo manquantes")

        cols = [elec_col] + meteo_cols
        corr = self._df[cols].corr()

        labels = {
            "consommation_brute_electricite_rte": "Conso Élec",
            "temperature_2m": "Température",
            "apparent_temperature": "Temp. ressentie",
            "relative_humidity_2m": "Humidité",
            "wind_speed_10m": "Vent",
            "precipitation": "Précipitations",
            "cloud_cover": "Couverture nuag.",
            "surface_pressure": "Pression",
        }
        display_labels = [labels.get(c, c) for c in cols]

        fig = go.Figure(data=go.Heatmap(
            z=corr.values,
            x=display_labels,
            y=display_labels,
            colorscale="RdBu_r",
            zmid=0,
            text=corr.values.round(2),
            texttemplate="%{text}",
            colorbar_title="Corrélation",
        ))

        fig.update_layout(
            title="Matrice de corrélation — Énergie × Météo",
            template="plotly_white",
            height=500,
        )

        self._figures["correlation_heatmap"] = fig
        return fig

    def build_wind_rain_analysis(self) -> go.Figure:
        """Analyse de l'impact vent + pluie sur la consommation."""
        elec_col = self._detect_elec_col()
        if not elec_col:
            return self._empty_figure("Colonne consommation manquante")

        fig = make_subplots(rows=1, cols=2, subplot_titles=(
            "Impact du vent", "Impact de la pluie",
        ))

        if "wind_category" in self._df.columns:
            wind_data = self._df.groupby("wind_category", observed=True)[elec_col].mean()
            fig.add_trace(go.Bar(
                x=wind_data.index.astype(str),
                y=wind_data.values,
                marker_color=self.COLORS["wind"],
                name="Vent",
            ), row=1, col=1)

        if "is_rainy" in self._df.columns:
            rain_data = self._df.groupby("is_rainy")[elec_col].mean()
            rain_labels = rain_data.index.map({True: "Pluie", False: "Sec"})
            fig.add_trace(go.Bar(
                x=rain_labels,
                y=rain_data.values,
                marker_color=[self.COLORS["rain"], "#aec7e8"],
                name="Pluie",
            ), row=1, col=2)

        fig.update_layout(
            title="Impact des conditions météo sur la consommation",
            template="plotly_white",
            showlegend=False,
        )

        self._figures["wind_rain"] = fig
        return fig

    def build_daily_overview(self) -> go.Figure:
        """Vue journalière avec météo + énergie (barres + lignes)."""
        elec_col = self._detect_elec_col()
        if not elec_col or "date" not in self._df.columns:
            return self._empty_figure("Données journalières manquantes")

        daily = self._df.groupby("date").agg({
            elec_col: "mean",
            **{c: "mean" for c in ["temperature_2m", "precipitation"]
               if c in self._df.columns},
        }).reset_index()

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            subplot_titles=("Consommation moyenne journalière", "Météo journalière"),
            vertical_spacing=0.12,
        )

        fig.add_trace(go.Bar(
            x=daily["date"], y=daily[elec_col],
            name="Conso (MW)", marker_color=self.COLORS["energy"],
        ), row=1, col=1)

        if "temperature_2m" in daily.columns:
            fig.add_trace(go.Scatter(
                x=daily["date"], y=daily["temperature_2m"],
                name="Température (°C)", mode="lines+markers",
                line=dict(color=self.COLORS["temp"], width=2),
            ), row=2, col=1)

        fig.update_layout(
            title="Vue journalière — Énergie × Météo",
            template="plotly_white", height=600,
            xaxis2=dict(
                rangeselector=dict(buttons=[
                    dict(count=3, label="3j", step="day", stepmode="backward"),
                    dict(count=7, label="1sem", step="day", stepmode="backward"),
                    dict(step="all", label="Tout"),
                ]),
            ),
        )

        self._figures["daily_overview"] = fig
        return fig

    def build_all(self) -> dict[str, go.Figure]:
        """Construit tous les graphiques."""
        self.build_energy_vs_temperature()
        self.build_scatter_temp_consumption()
        self.build_weather_impact_bars()
        self.build_multivar_heatmap()
        self.build_wind_rain_analysis()
        self.build_daily_overview()
        self.logger.info("Dashboard croisé: %d graphiques construits", len(self._figures))
        return self._figures.copy()

    def export_html(self, filename: str = "dashboard_cross_energy_meteo.html") -> Path:
        """Exporte le dashboard complet en HTML avec filtres interactifs."""
        if not self._figures:
            self.build_all()

        filepath = self.output_dir / filename

        # Calculer les statistiques
        elec_col = self._detect_elec_col()
        has_temp = "temperature_2m" in self._df.columns

        html_parts = [
            "<!DOCTYPE html>",
            '<html lang="fr">',
            "<head>",
            '  <meta charset="UTF-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            "  <title>Dashboard Énergie × Météo — Île-de-France</title>",
            '  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>',
            "  <style>",
            "    * { margin: 0; padding: 0; box-sizing: border-box; }",
            "    body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; }",
            "    .header { background: linear-gradient(135deg, #1a1a2e, #0f3460);",
            "              color: white; padding: 30px 40px; }",
            "    .header h1 { font-size: 1.8em; }",
            "    .header p { opacity: 0.8; margin-top: 5px; }",
            "    .filters { background: white; padding: 15px 40px;",
            "               border-bottom: 2px solid #e0e0e0; display: flex;",
            "               gap: 20px; align-items: center; flex-wrap: wrap; }",
            "    .filters label { font-weight: 600; font-size: 0.9em; }",
            "    .filters input, .filters select { padding: 6px 12px; border: 1px solid #ccc;",
            "                                       border-radius: 5px; font-size: 0.9em; }",
            "    .filters button { padding: 8px 20px; background: #1f77b4; color: white;",
            "                      border: none; border-radius: 5px; cursor: pointer; }",
            "    .filters button:hover { background: #155a8a; }",
            "    .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));",
            "               gap: 15px; padding: 20px 40px; }",
            "    .metric { background: white; border-radius: 10px; padding: 20px;",
            "              box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }",
            "    .metric .value { font-size: 1.8em; font-weight: bold; color: #1f77b4; }",
            "    .metric .label { font-size: 0.8em; color: #666; margin-top: 5px; }",
            "    .charts { padding: 20px 40px; }",
            "    .chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px;",
            "                 margin-bottom: 20px; }",
            "    .chart-full { margin-bottom: 20px; }",
            "    .chart-box { background: white; border-radius: 10px;",
            "                 box-shadow: 0 2px 8px rgba(0,0,0,0.08); padding: 15px; }",
            "    @media (max-width: 900px) { .chart-row { grid-template-columns: 1fr; } }",
            "    .footer { text-align: center; padding: 20px; color: #999; font-size: 0.8em; }",
            "    .governance { background: #f8f9fa; padding: 20px 40px; margin: 20px 40px;",
            "                  border-radius: 10px; border-left: 4px solid #1f77b4; }",
            "    .governance h3 { margin-bottom: 10px; }",
            "  </style>",
            "</head>",
            "<body>",
            '  <div class="header">',
            "    <h1>Dashboard Énergie &times; Météo</h1>",
            "    <p>Île-de-France — Croisement consommation énergétique et données météorologiques</p>",
            "  </div>",
        ]

        # Filtres par période
        date_min = str(self._df["datetime"].min())[:10] if "datetime" in self._df.columns else ""
        date_max = str(self._df["datetime"].max())[:10] if "datetime" in self._df.columns else ""
        html_parts.extend([
            '  <div class="filters">',
            '    <label>Période :</label>',
            f'    <input type="date" id="date-start" value="{date_min}">',
            '    <span>→</span>',
            f'    <input type="date" id="date-end" value="{date_max}">',
            '    <label>Affichage :</label>',
            '    <select id="view-mode">',
            '      <option value="all">Tous les graphiques</option>',
            '      <option value="energy">Énergie seule</option>',
            '      <option value="meteo">Météo seule</option>',
            '      <option value="cross">Croisement seul</option>',
            '    </select>',
            '    <button onclick="applyFilters()">Appliquer</button>',
            "  </div>",
        ])

        # Métriques
        html_parts.append('  <div class="metrics">')
        metrics = [
            (str(len(self._df)), "Enregistrements"),
            (date_min, "Date début"),
            (date_max, "Date fin"),
        ]
        if elec_col:
            metrics.append((f"{self._df[elec_col].mean():,.0f}", "Conso moy. (MW)"))
        if has_temp:
            metrics.append((f"{self._df['temperature_2m'].mean():,.1f}°C", "Temp. moyenne"))
        if "precipitation" in self._df.columns:
            metrics.append((f"{self._df['precipitation'].sum():,.1f}mm", "Précip. totales"))
        if has_temp and elec_col:
            corr = self._df["temperature_2m"].corr(self._df[elec_col])
            metrics.append((f"{corr:+.2f}", "Corrél. Temp/Conso"))

        for val, label in metrics:
            html_parts.append(
                f'    <div class="metric"><div class="value">{val}</div>'
                f'<div class="label">{label}</div></div>'
            )
        html_parts.append("  </div>")

        # Graphiques
        html_parts.append('  <div class="charts">')
        chart_layout = [
            ("chart-full", ["energy_vs_temp"], "cross"),
            ("chart-row", ["scatter_temp_conso", "weather_impact"], "cross"),
            ("chart-row", ["correlation_heatmap", "wind_rain"], "meteo"),
            ("chart-full", ["daily_overview"], "energy"),
        ]

        chart_id = 0
        for css_class, keys, category in chart_layout:
            html_parts.append(f'    <div class="{css_class}" data-category="{category}">')
            for key in keys:
                fig = self._figures.get(key)
                if fig:
                    div_id = f"cross_chart_{chart_id}"
                    html_parts.append(f'      <div class="chart-box"><div id="{div_id}"></div></div>')
                    chart_id += 1
            html_parts.append("    </div>")

        html_parts.append("  </div>")

        # Gouvernance
        html_parts.extend([
            '  <div class="governance">',
            "    <h3>Data Governance</h3>",
            "    <p><strong>Sources :</strong> API ODRE (énergie) + Open-Meteo (météo)</p>",
            "    <p><strong>Fusion :</strong> merge_asof sur datetime (tolérance 1h)</p>",
            f"    <p><strong>Enregistrements :</strong> {len(self._df)}</p>",
            f"    <p><strong>Colonnes :</strong> {len(self._df.columns)}</p>",
            "  </div>",
        ])

        # Footer
        html_parts.append('  <div class="footer">Pipeline Data — Énergie × Météo IDF</div>')

        # Script Plotly
        html_parts.append("  <script>")
        chart_id = 0
        for css_class, keys, category in chart_layout:
            for key in keys:
                fig = self._figures.get(key)
                if fig:
                    div_id = f"cross_chart_{chart_id}"
                    html_parts.append(
                        f"    Plotly.newPlot('{div_id}', "
                        f"{fig.to_json()}, "
                        f"{{responsive: true}});"
                    )
                    chart_id += 1

        # Filtre JavaScript côté client
        html_parts.extend([
            "    function applyFilters() {",
            "      var mode = document.getElementById('view-mode').value;",
            "      var sections = document.querySelectorAll('[data-category]');",
            "      sections.forEach(function(s) {",
            "        if (mode === 'all' || s.dataset.category === mode) {",
            "          s.style.display = '';",
            "        } else {",
            "          s.style.display = 'none';",
            "        }",
            "      });",
            "    }",
        ])

        html_parts.append("  </script>")
        html_parts.append("</body></html>")

        filepath.write_text("\n".join(html_parts), encoding="utf-8")
        self.logger.info("Dashboard croisé exporté: %s", filepath)
        return filepath

    def _empty_figure(self, message: str) -> go.Figure:
        fig = go.Figure()
        fig.add_annotation(
            text=message, xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False, font=dict(size=16, color="gray"),
        )
        fig.update_layout(template="plotly_white", height=300)
        return fig
