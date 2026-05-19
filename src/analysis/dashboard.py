"""
Générateur de dashboards interactifs pour la consommation énergétique IDF.
Utilise Plotly pour les graphiques interactifs et Bokeh pour le dashboard HTML.
"""
from pathlib import Path
from typing import Optional

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.analyzer import DataAnalyzer
from src.utils.logger import get_logger


class DashboardBuilder:
    """Construit des visualisations interactives à partir des données analysées."""

    # Palette de couleurs cohérente
    COLORS = {
        "primary": "#1f77b4",
        "secondary": "#ff7f0e",
        "accent": "#2ca02c",
        "danger": "#d62728",
        "weekend": "#9467bd",
        "weekday": "#17becf",
        "background": "#fafafa",
    }

    def __init__(self, analyzer: DataAnalyzer, output_dir: Optional[Path] = None):
        """
        Args:
            analyzer: Instance de DataAnalyzer avec les données chargées.
            output_dir: Répertoire de sortie pour les fichiers HTML.
        """
        self.analyzer = analyzer
        self.output_dir = Path(output_dir) if output_dir else Path("output/dashboards")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(self.__class__.__name__)
        self._figures: dict[str, go.Figure] = {}

    def build_hourly_profile(self) -> go.Figure:
        """Graphique du profil de consommation horaire moyen."""
        try:
            profile = self.analyzer.hourly_profile()
        except ValueError as e:
            self.logger.warning("Profil horaire impossible: %s", e)
            return self._empty_figure("Profil horaire indisponible")

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=profile["hour"],
            y=profile["mean_mw"],
            mode="lines+markers",
            name="Moyenne (MW)",
            line=dict(color=self.COLORS["primary"], width=3),
            marker=dict(size=6),
        ))

        fig.add_trace(go.Scatter(
            x=profile["hour"],
            y=profile["max_mw"],
            mode="lines",
            name="Max",
            line=dict(color=self.COLORS["danger"], width=1, dash="dash"),
        ))

        fig.add_trace(go.Scatter(
            x=profile["hour"],
            y=profile["min_mw"],
            mode="lines",
            name="Min",
            line=dict(color=self.COLORS["accent"], width=1, dash="dash"),
            fill="tonexty",
            fillcolor="rgba(44, 160, 44, 0.1)",
        ))

        fig.update_layout(
            title="Profil de consommation électrique horaire — Île-de-France",
            xaxis_title="Heure",
            yaxis_title="Consommation (MW)",
            xaxis=dict(dtick=1),
            template="plotly_white",
            hovermode="x unified",
        )

        self._figures["hourly_profile"] = fig
        self.logger.info("Graphique profil horaire créé")
        return fig

    def build_daily_consumption(self) -> go.Figure:
        """Graphique de la consommation journalière."""
        try:
            daily = self.analyzer.daily_consumption()
        except ValueError as e:
            self.logger.warning("Consommation journalière impossible: %s", e)
            return self._empty_figure("Consommation journalière indisponible")

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            subplot_titles=("Consommation totale par jour", "Pic de consommation"),
            vertical_spacing=0.12,
        )

        fig.add_trace(go.Bar(
            x=daily["date"],
            y=daily["total_mw"],
            name="Total (MW)",
            marker_color=self.COLORS["primary"],
            opacity=0.8,
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=daily["date"],
            y=daily["peak_mw"],
            mode="lines+markers",
            name="Pic (MW)",
            line=dict(color=self.COLORS["danger"], width=2),
            marker=dict(size=7),
        ), row=2, col=1)

        fig.update_layout(
            title="Consommation électrique journalière — Île-de-France",
            template="plotly_white",
            height=600,
            showlegend=True,
        )
        fig.update_yaxes(title_text="Total (MW)", row=1, col=1)
        fig.update_yaxes(title_text="Pic (MW)", row=2, col=1)

        self._figures["daily_consumption"] = fig
        self.logger.info("Graphique consommation journalière créé")
        return fig

    def build_weekday_comparison(self) -> go.Figure:
        """Comparaison semaine vs weekend."""
        try:
            comparison = self.analyzer.weekday_vs_weekend()
        except ValueError as e:
            self.logger.warning("Comparaison semaine/weekend impossible: %s", e)
            return self._empty_figure("Comparaison indisponible")

        fig = go.Figure()

        colors = [self.COLORS["weekday"], self.COLORS["weekend"]]

        fig.add_trace(go.Bar(
            x=comparison["type_jour"],
            y=comparison["mean_mw"],
            error_y=dict(type="data", array=comparison["std_mw"], visible=True),
            marker_color=colors,
            text=comparison["mean_mw"].round(0),
            textposition="outside",
        ))

        fig.update_layout(
            title="Consommation moyenne : Semaine vs Weekend — Île-de-France",
            yaxis_title="Consommation moyenne (MW)",
            template="plotly_white",
            showlegend=False,
        )

        self._figures["weekday_comparison"] = fig
        self.logger.info("Graphique semaine vs weekend créé")
        return fig

    def build_day_of_week_profile(self) -> go.Figure:
        """Profil par jour de la semaine."""
        try:
            profile = self.analyzer.day_of_week_profile()
        except ValueError as e:
            self.logger.warning("Profil jour de semaine impossible: %s", e)
            return self._empty_figure("Profil indisponible")

        fig = go.Figure()

        colors = [
            self.COLORS["weekday"] if dow < 5 else self.COLORS["weekend"]
            for dow in profile["day_of_week"]
        ]

        fig.add_trace(go.Bar(
            x=profile["day_name"],
            y=profile["mean_mw"],
            marker_color=colors,
            error_y=dict(type="data", array=profile["std_mw"], visible=True),
            text=profile["mean_mw"].round(0),
            textposition="outside",
        ))

        fig.update_layout(
            title="Consommation moyenne par jour de la semaine — Île-de-France",
            yaxis_title="Consommation moyenne (MW)",
            template="plotly_white",
            showlegend=False,
        )

        self._figures["day_of_week"] = fig
        self.logger.info("Graphique profil hebdomadaire créé")
        return fig

    def build_heatmap(self) -> go.Figure:
        """Heatmap consommation : jour x heure."""
        df = self.analyzer.df
        elec_col = self.analyzer._detect_elec_column()
        if not elec_col or "hour" not in df.columns or "date" not in df.columns:
            return self._empty_figure("Heatmap indisponible")

        pivot = df.pivot_table(
            values=elec_col, index="date", columns="hour", aggfunc="mean"
        )

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[f"{h}h" for h in pivot.columns],
            y=[str(d) for d in pivot.index],
            colorscale="YlOrRd",
            colorbar_title="MW",
            hovertemplate="Date: %{y}<br>Heure: %{x}<br>Consommation: %{z:.0f} MW<extra></extra>",
        ))

        fig.update_layout(
            title="Heatmap de consommation électrique (Jour × Heure) — Île-de-France",
            xaxis_title="Heure",
            yaxis_title="Date",
            template="plotly_white",
            height=500,
        )

        self._figures["heatmap"] = fig
        self.logger.info("Heatmap créée")
        return fig

    def build_anomalies_chart(self, z_threshold: float = 2.5) -> go.Figure:
        """Visualise les anomalies détectées."""
        df = self.analyzer.df
        elec_col = self.analyzer._detect_elec_column()
        if not elec_col or "datetime" not in df.columns:
            return self._empty_figure("Détection d'anomalies indisponible")

        anomalies = self.analyzer.detect_anomalies(z_threshold=z_threshold)

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=df["datetime"],
            y=df[elec_col],
            mode="lines",
            name="Consommation",
            line=dict(color=self.COLORS["primary"], width=1),
            opacity=0.6,
        ))

        if not anomalies.empty:
            fig.add_trace(go.Scatter(
                x=anomalies["datetime"],
                y=anomalies[elec_col],
                mode="markers",
                name=f"Anomalies (z>{z_threshold})",
                marker=dict(color=self.COLORS["danger"], size=10, symbol="x"),
            ))

        fig.update_layout(
            title=f"Détection d'anomalies (z-score > {z_threshold}) — Île-de-France",
            xaxis_title="Date/Heure",
            yaxis_title="Consommation (MW)",
            template="plotly_white",
            hovermode="x unified",
        )

        self._figures["anomalies"] = fig
        self.logger.info("Graphique anomalies créé (%d anomalies)", len(anomalies))
        return fig

    def build_rte_mix(self, rte_records: list) -> go.Figure:
        """Donut chart + barres du mix de génération RTE."""
        LABELS_FR = {
            "NUCLEAR": "Nucléaire", "WIND": "Éolien", "SOLAR": "Solaire",
            "HYDRO": "Hydraulique", "THERMAL": "Thermique", "BIOENERGY": "Bioénergie",
            "PUMPING": "Pompage", "EXCHANGE": "Échanges", "OTHER": "Autre",
            "FOSSIL_GAS": "Gaz", "FOSSIL_HARD_COAL": "Charbon", "FOSSIL_OIL": "Fioul",
            "WASTE": "Déchets",
        }
        COLORS_MIX = {
            "Nucléaire": "#f39c12", "Éolien": "#74b9ff", "Solaire": "#ffd32a",
            "Hydraulique": "#0652DD", "Thermique": "#e17055", "Bioénergie": "#00b894",
            "Gaz": "#fd79a8", "Charbon": "#636e72", "Fioul": "#b2bec3",
            "Pompage": "#a29bfe", "Déchets": "#55efc4", "Autre": "#95a5a6",
            "Échanges": "#dfe6e9",
        }

        totals = {}
        for record in rte_records:
            ptype = record.get("production_type", "OTHER")
            label = LABELS_FR.get(ptype, ptype.capitalize())
            values = record.get("values", [])
            total = sum(v.get("value", 0) or 0 for v in values)
            if total > 0:
                totals[label] = totals.get(label, 0) + total

        if not totals:
            return self._empty_figure("Données RTE indisponibles")

        labels = list(totals.keys())
        values = list(totals.values())
        colors = [COLORS_MIX.get(lbl, "#95a5a6") for lbl in labels]

        fig = go.Figure(data=go.Pie(
            labels=labels,
            values=values,
            hole=0.45,
            marker=dict(colors=colors),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>%{value:,.0f} MW·h<br>%{percent}<extra></extra>",
        ))

        fig.update_layout(
            title="Mix de génération électrique — France (RTE)",
            template="plotly_white",
            legend=dict(orientation="v", x=1.05),
            annotations=[dict(text="Mix<br>RTE", x=0.5, y=0.5, font_size=14, showarrow=False)],
        )

        self._figures["rte_mix"] = fig
        self.logger.info("Graphique mix RTE créé (%d filières)", len(totals))
        return fig

    def build_all(self) -> dict[str, go.Figure]:
        """Construit tous les graphiques disponibles."""
        self.build_hourly_profile()
        self.build_daily_consumption()
        self.build_weekday_comparison()
        self.build_day_of_week_profile()
        self.build_heatmap()
        self.build_anomalies_chart()
        self.logger.info("Tous les graphiques construits: %d", len(self._figures))
        return self._figures.copy()

    def export_html(self, filename: str = "dashboard_energy_idf.html") -> Path:
        """
        Exporte tous les graphiques dans un fichier HTML unique.

        Args:
            filename: Nom du fichier de sortie.

        Returns:
            Chemin du fichier HTML généré.
        """
        if not self._figures:
            self.build_all()

        filepath = self.output_dir / filename

        summary = self.analyzer.summary()

        html_parts = [
            "<!DOCTYPE html>",
            '<html lang="fr">',
            "<head>",
            '  <meta charset="UTF-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            "  <title>Dashboard Consommation Énergétique — Île-de-France</title>",
            '  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>',
            "  <style>",
            "    * { margin: 0; padding: 0; box-sizing: border-box; }",
            "    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;",
            "           background: #f0f2f5; color: #333; }",
            "    .header { background: linear-gradient(135deg, #1a1a2e, #16213e);",
            "              color: white; padding: 30px 40px; }",
            "    .header h1 { font-size: 1.8em; margin-bottom: 5px; }",
            "    .header p { opacity: 0.8; font-size: 0.95em; }",
            "    .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));",
            "               gap: 15px; padding: 20px 40px; }",
            "    .metric-card { background: white; border-radius: 10px; padding: 20px;",
            "                   box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }",
            "    .metric-card .value { font-size: 2em; font-weight: bold; color: #1f77b4; }",
            "    .metric-card .label { font-size: 0.85em; color: #666; margin-top: 5px; }",
            "    .charts { padding: 20px 40px; }",
            "    .chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px;",
            "                 margin-bottom: 20px; }",
            "    .chart-full { margin-bottom: 20px; }",
            "    .chart-container { background: white; border-radius: 10px;",
            "                       box-shadow: 0 2px 8px rgba(0,0,0,0.08);",
            "                       padding: 15px; overflow: hidden; }",
            "    @media (max-width: 900px) { .chart-row { grid-template-columns: 1fr; } }",
            "    .footer { text-align: center; padding: 20px; color: #999; font-size: 0.8em; }",
            "  </style>",
            "</head>",
            "<body>",
            '  <div class="header">',
            "    <h1>Dashboard Consommation Énergétique</h1>",
            "    <p>Île-de-France — Données ODRE (Open Data Réseaux Énergies)</p>",
            "  </div>",
        ]

        # Métriques en haut
        elec = summary.get("electricity", {})
        date_range = summary.get("date_range", {})
        html_parts.append('  <div class="metrics">')
        metrics = [
            (str(summary.get("total_records", 0)), "Enregistrements"),
            (date_range.get("start", "N/A")[:10], "Date début"),
            (date_range.get("end", "N/A")[:10], "Date fin"),
            (f"{elec.get('mean_mw', 0):,.0f}", "Moyenne (MW)"),
            (f"{elec.get('max_mw', 0):,.0f}", "Pic max (MW)"),
            (f"{elec.get('min_mw', 0):,.0f}", "Min (MW)"),
        ]
        for value, label in metrics:
            html_parts.append(
                f'    <div class="metric-card">'
                f'<div class="value">{value}</div>'
                f'<div class="label">{label}</div></div>'
            )
        html_parts.append("  </div>")

        # Graphiques
        html_parts.append('  <div class="charts">')

        chart_layout = [
            ("chart-full", ["daily_consumption"]),
            ("chart-row", ["hourly_profile", "rte_mix"]),
            ("chart-row", ["weekday_comparison", "day_of_week"]),
            ("chart-full", ["heatmap"]),
            ("chart-full", ["anomalies"]),
        ]

        div_id = 0
        js_parts = []

        for css_class, chart_keys in chart_layout:
            html_parts.append(f'    <div class="{css_class}">')
            for key in chart_keys:
                fig = self._figures.get(key)
                if fig:
                    chart_div = f"chart_{div_id}"
                    html_parts.append(
                        f'      <div class="chart-container">'
                        f'<div id="{chart_div}"></div></div>'
                    )
                    fig_json = fig.to_json()
                    js_parts.append(
                        f"    Plotly.newPlot('{chart_div}', "
                        f"{fig_json}.data, {fig_json}.layout, "
                        f"{{responsive: true}});"
                    )
                    div_id += 1
            html_parts.append("    </div>")

        html_parts.append("  </div>")

        # Footer
        html_parts.append(
            '  <div class="footer">'
            "Pipeline Data — Consommation Énergétique IDF"
            "</div>"
        )

        # Script Plotly
        html_parts.append("  <script>")
        html_parts.extend(js_parts)
        html_parts.append("  </script>")
        html_parts.append("</body>")
        html_parts.append("</html>")

        filepath.write_text("\n".join(html_parts), encoding="utf-8")
        self.logger.info("Dashboard HTML exporté: %s", filepath)
        return filepath

    def _empty_figure(self, message: str) -> go.Figure:
        """Crée un graphique vide avec un message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message, xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False, font=dict(size=16, color="gray"),
        )
        fig.update_layout(template="plotly_white", height=300)
        return fig
