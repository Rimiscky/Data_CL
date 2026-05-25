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
        Exporte un dashboard HTML interactif avec filtres JS côté client.
        Les données brutes sont embarquées en JSON ; tous les graphiques
        se mettent à jour dynamiquement sans rechargement de page.
        """
        import json
        import math
        import pandas as pd

        filepath = self.output_dir / filename
        df = self.analyzer.df.copy()
        elec_col = self.analyzer._detect_elec_column()
        if not elec_col:
            self.logger.error("Colonne électricité non trouvée")
            return filepath

        def _safe(v):
            if v is None:
                return None
            try:
                f = float(v)
                return None if math.isnan(f) else round(f, 1)
            except (TypeError, ValueError):
                return None

        records = []
        for _, row in df.iterrows():
            dt_raw = row.get("datetime")
            dt_str = str(dt_raw)[:16] if pd.notna(dt_raw) else ""
            date_str = str(row.get("date", ""))[:10]
            records.append({
                "dt": dt_str,
                "date": date_str,
                "h": int(row["hour"]) if pd.notna(row.get("hour")) else 0,
                "dow": int(row["day_of_week"]) if pd.notna(row.get("day_of_week")) else 0,
                "mo": int(row["month"]) if pd.notna(row.get("month")) else 1,
                "we": bool(row.get("is_weekend", False)),
                "elec": _safe(row.get(elec_col)),
                "gas": _safe(row.get("gas_consumption_mw")),
                "tot": _safe(row.get("total_consumption_mw")),
            })

        dates = sorted({r["date"] for r in records if r["date"]})
        date_min = dates[0] if dates else ""
        date_max = dates[-1] if dates else ""
        data_json = json.dumps(records, ensure_ascii=False)

        # Inject Python values into a plain string (no f-string for JS body)
        html = (
            _DASHBOARD_HTML_TEMPLATE
            .replace("__DATA_JSON__", data_json)
            .replace("__DATE_MIN__", date_min)
            .replace("__DATE_MAX__", date_max)
        )

        filepath.write_text(html, encoding="utf-8")
        self.logger.info("Dashboard HTML interactif exporté: %s (%d lignes)", filepath, len(records))
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


# ---------------------------------------------------------------------------
# HTML template for the interactive dashboard (injected via str.replace)
# Placeholders: __DATA_JSON__  __DATE_MIN__  __DATE_MAX__
# ---------------------------------------------------------------------------
_DASHBOARD_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Consommation Énergétique — Île-de-France</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:#f0f2f5;color:#333;min-height:100vh}

/* ── Header ── */
.hdr{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:22px 40px;
     display:flex;align-items:center;gap:24px}
.back-btn{background:rgba(255,255,255,.15);color:#fff;border:none;border-radius:8px;
          padding:8px 16px;font-size:.85em;cursor:pointer;text-decoration:none;
          white-space:nowrap;transition:background .2s}
.back-btn:hover{background:rgba(255,255,255,.28)}
.hdr-text h1{font-size:1.55em;margin-bottom:3px}
.hdr-text p{opacity:.75;font-size:.88em}
.hdr-badge{margin-left:auto;background:rgba(255,255,255,.12);border-radius:20px;
           padding:6px 16px;font-size:.82em;white-space:nowrap}

/* ── Filter bar ── */
.fbar{background:#fff;border-bottom:1px solid #e0e3ea;padding:14px 40px;
      display:flex;flex-wrap:wrap;align-items:center;gap:20px;position:sticky;
      top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.fg{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.fg label{font-size:.78em;font-weight:700;text-transform:uppercase;
          letter-spacing:.8px;color:#888;white-space:nowrap}
.fg input[type=date]{border:1px solid #d0d5dd;border-radius:7px;padding:5px 9px;
                     font-size:.85em;color:#333;outline:none;cursor:pointer}
.fg input[type=date]:focus{border-color:#667eea}
.pills{display:flex;gap:5px;flex-wrap:wrap}
.pill{background:#f0f2f5;border:1px solid #e0e3ea;border-radius:20px;
      padding:4px 13px;font-size:.82em;cursor:pointer;transition:all .18s;
      color:#555;font-weight:500;white-space:nowrap}
.pill:hover{border-color:#667eea;color:#667eea}
.pill.active{background:#667eea;border-color:#667eea;color:#fff;font-weight:600}
.pill.active.danger{background:#e74c3c;border-color:#e74c3c}
.btn-reset{background:none;border:1px solid #ccc;border-radius:7px;padding:5px 12px;
           font-size:.82em;cursor:pointer;color:#666;transition:all .18s}
.btn-reset:hover{border-color:#e74c3c;color:#e74c3c}
.fbar-count{font-size:.82em;color:#888;white-space:nowrap;margin-left:auto}
.fbar-count strong{color:#1a1a2e}
.fbar-sep{width:1px;height:30px;background:#e0e3ea;flex-shrink:0}

/* ── KPI cards ── */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
      gap:15px;padding:22px 40px 10px}
.kpi{background:#fff;border-radius:12px;padding:20px 22px;
     box-shadow:0 2px 10px rgba(0,0,0,.07);border-top:4px solid #667eea}
.kpi.green{border-color:#2ca02c}
.kpi.orange{border-color:#ff7f0e}
.kpi.red{border-color:#d62728}
.kpi-val{font-size:1.8em;font-weight:700;color:#1a1a2e;line-height:1}
.kpi-label{font-size:.78em;color:#888;margin-top:6px;text-transform:uppercase;
           letter-spacing:.6px}
.kpi-delta{font-size:.78em;margin-top:4px;color:#aaa}

/* ── Charts ── */
.charts{padding:14px 40px 30px}
.chart-row{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:18px}
.chart-full{margin-bottom:18px}
.cc{background:#fff;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,.07);
    padding:16px;overflow:hidden}

/* ── Footer ── */
footer{text-align:center;padding:20px;color:#bbb;font-size:.78em}

/* ── No-data banner ── */
#nodata{display:none;margin:24px 40px;background:#fff8e1;border:1px solid #ffe082;
        border-radius:12px;padding:28px 32px;text-align:center}
#nodata .nd-icon{font-size:2.4em;margin-bottom:10px}
#nodata .nd-title{font-size:1.1em;font-weight:700;color:#795548;margin-bottom:6px}
#nodata .nd-sub{font-size:.88em;color:#a0856a;line-height:1.6}

/* ── Animations ── */
@keyframes fadeInUp{
  from{opacity:0;transform:translateY(18px)}
  to  {opacity:1;transform:translateY(0)}
}
@keyframes slideDown{
  from{opacity:0;transform:translateY(-12px)}
  to  {opacity:1;transform:translateY(0)}
}
@keyframes kpiBounce{
  0%  {transform:scale(1)}
  40% {transform:scale(1.06)}
  100%{transform:scale(1)}
}
@keyframes shimmer{
  0%  {background-position:200% center}
  100%{background-position:-200% center}
}

/* Chart containers: staggered fade-in on page load */
.cc{animation:fadeInUp .45s cubic-bezier(.22,.68,0,1.2) both}
.charts .chart-full:nth-child(1) .cc{animation-delay:.05s}
.charts .chart-row:nth-child(2) .cc:nth-child(1){animation-delay:.12s}
.charts .chart-row:nth-child(2) .cc:nth-child(2){animation-delay:.20s}
.charts .chart-full:nth-child(3) .cc{animation-delay:.28s}
.charts .chart-row:nth-child(4) .cc:nth-child(1){animation-delay:.36s}
.charts .chart-row:nth-child(4) .cc:nth-child(2){animation-delay:.44s}

/* No-data banner slide-in */
#nodata.visible{display:block;animation:slideDown .3s cubic-bezier(.22,.68,0,1.2)}

/* KPI cards */
.kpi{transition:box-shadow .2s,transform .2s}
.kpi:hover{transform:translateY(-3px);box-shadow:0 6px 20px rgba(0,0,0,.12)}
.kpi-val{transition:color .25s;display:inline-block}
.kpi-val.bounce{animation:kpiBounce .35s ease}

/* Charts-wrap fade when filters update */
#charts-wrap{transition:opacity .18s}
#charts-wrap.updating{opacity:.45}

/* Pills micro-interactions */
.pill{transition:all .18s cubic-bezier(.4,0,.2,1)}
.pill:active{transform:scale(.9)}
.pill.active{box-shadow:0 2px 8px rgba(102,126,234,.35)}

/* Filter bar: active-filter indicator */
.fbar.has-filters{border-bottom:2px solid #667eea}
.fbar-count strong{transition:color .2s}

/* KPI shimmer while loading */
.kpi.loading .kpi-val{
  background:linear-gradient(90deg,#f0f0f0 25%,#e0e0e0 50%,#f0f0f0 75%);
  background-size:400% auto;
  animation:shimmer .9s linear infinite;
  color:transparent;border-radius:4px;
}

@media(max-width:900px){
  .chart-row{grid-template-columns:1fr}
  .fbar{gap:12px}
  .hdr{flex-wrap:wrap}
  .kpis,.charts{padding-left:16px;padding-right:16px}
  .fbar{padding:12px 16px}
}
</style>
</head>
<body>

<!-- Header -->
<div class="hdr">
  <a href="index.html" class="back-btn">← Accueil</a>
  <div class="hdr-text">
    <h1>⚡ Consommation Énergétique</h1>
    <p>Île-de-France · Données ODRE · Disponible du __DATE_MIN__ au __DATE_MAX__</p>
  </div>
  <div class="hdr-badge" id="hdr-badge">— lignes</div>
</div>

<!-- Filter bar -->
<div class="fbar">
  <div class="fg">
    <label>Période</label>
    <input type="date" id="dateFrom" value="__DATE_MIN__">
    <span style="color:#bbb">→</span>
    <input type="date" id="dateTo" value="__DATE_MAX__">
  </div>
  <div class="fbar-sep"></div>
  <div class="fg">
    <label>Saison</label>
    <div class="pills" id="p-season">
      <button class="pill active" data-v="">Tout</button>
      <button class="pill" data-v="Printemps">🌸 Printemps</button>
      <button class="pill" data-v="Été">☀️ Été</button>
      <button class="pill" data-v="Automne">🍂 Automne</button>
      <button class="pill" data-v="Hiver">❄️ Hiver</button>
    </div>
  </div>
  <div class="fbar-sep"></div>
  <div class="fg">
    <label>Jour</label>
    <div class="pills" id="p-jour">
      <button class="pill active" data-v="">Tout</button>
      <button class="pill" data-v="semaine">Semaine</button>
      <button class="pill" data-v="weekend">Weekend</button>
    </div>
  </div>
  <div class="fbar-sep"></div>
  <div class="fg">
    <label>Heure</label>
    <div class="pills" id="p-heure">
      <button class="pill active" data-v="">Toutes</button>
      <button class="pill" data-v="pointe">Pointe (7h–21h)</button>
      <button class="pill" data-v="creuse">Creuse (22h–6h)</button>
    </div>
  </div>
  <div class="fbar-sep"></div>
  <button class="btn-reset" onclick="resetFilters()">↺ Réinitialiser</button>
  <span class="fbar-count" id="fbar-count"><strong>—</strong> / — lignes</span>
</div>

<!-- KPIs -->
<div class="kpis">
  <div class="kpi"         id="kpi-n"><div class="kpi-val">—</div><div class="kpi-label">Enregistrements</div></div>
  <div class="kpi green"   id="kpi-mean"><div class="kpi-val">—</div><div class="kpi-label">Moyenne élec (MW)</div></div>
  <div class="kpi orange"  id="kpi-max"><div class="kpi-val">—</div><div class="kpi-label">Pic max (MW)</div></div>
  <div class="kpi red"     id="kpi-min"><div class="kpi-val">—</div><div class="kpi-label">Min (MW)</div></div>
  <div class="kpi"         id="kpi-gas"><div class="kpi-val">—</div><div class="kpi-label">Moyenne gaz (MW)</div></div>
</div>

<!-- No-data banner -->
<div id="nodata">
  <div class="nd-icon">🔍</div>
  <div class="nd-title">Aucune donnée pour cette combinaison de filtres</div>
  <div class="nd-sub">
    Les données disponibles couvrent la période <strong>__DATE_MIN__</strong> → <strong>__DATE_MAX__</strong>
    (Printemps 2026 — mars uniquement).<br>
    Les filtres <em>Été</em>, <em>Automne</em> et <em>Hiver</em> ne correspondent à aucun enregistrement dans ce dataset.
  </div>
</div>

<!-- Charts -->
<div id="charts-wrap" class="charts">
  <!-- Série temporelle -->
  <div class="chart-full"><div class="cc"><div id="c-ts"></div></div></div>
  <!-- Profil 24h par saison -->
  <div class="chart-full"><div class="cc"><div id="c-season"></div></div></div>
  <!-- Profil horaire + Jour de semaine -->
  <div class="chart-row">
    <div class="cc"><div id="c-hour"></div></div>
    <div class="cc"><div id="c-dow"></div></div>
  </div>
  <!-- Box plots consommation par heure -->
  <div class="chart-full"><div class="cc"><div id="c-boxhour"></div></div></div>
  <!-- Heatmap Jour×Heure -->
  <div class="chart-full"><div class="cc"><div id="c-heat"></div></div></div>
  <!-- Heatmap calendrier Date×Heure -->
  <div class="chart-full"><div class="cc"><div id="c-calheat"></div></div></div>
  <!-- Semaine vs Weekend + Distribution -->
  <div class="chart-row">
    <div class="cc"><div id="c-cmp"></div></div>
    <div class="cc"><div id="c-hist"></div></div>
  </div>
</div>  <!-- /charts-wrap -->

<footer>Pipeline Data · Sources : ODRE · Mise à jour quotidienne via GitLab CI/CD</footer>

<script>
// ── Data ──────────────────────────────────────────────────────────────────
window.D = __DATA_JSON__;
const TOTAL = window.D.length;

// ── State ─────────────────────────────────────────────────────────────────
const S = {df:'__DATE_MIN__', dt:'__DATE_MAX__', season:'', jour:'', heure:''};

// ── Helpers ───────────────────────────────────────────────────────────────
const SEASON = mo => [3,4,5].includes(mo)?'Printemps':[6,7,8].includes(mo)?'Été':[9,10,11].includes(mo)?'Automne':'Hiver';
const mean = a => a.length ? a.reduce((x,y)=>x+y,0)/a.length : null;
const std  = a => { const m=mean(a); return a.length ? Math.sqrt(a.reduce((s,v)=>s+(v-m)**2,0)/a.length) : 0; };
const fmt  = v => v===null||isNaN(v) ? '—' : Math.round(v).toLocaleString('fr-FR');
const CFG  = {responsive:true, displayModeBar:false};
const LAY  = {template:'plotly_white', margin:{t:44,l:52,r:18,b:44}, font:{family:'Segoe UI,sans-serif',size:12}};
const DOW_NAMES = ['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'];
const C_BLUE='#667eea', C_GREEN='#2ca02c', C_ORG='#ff7f0e', C_RED='#d62728', C_PUR='#9467bd';

// ── Filtered data ─────────────────────────────────────────────────────────
function filtered() {
  return window.D.filter(d => {
    if (S.df && d.date < S.df) return false;
    if (S.dt && d.date > S.dt) return false;
    if (S.season && SEASON(d.mo) !== S.season) return false;
    if (S.jour === 'semaine' && d.we) return false;
    if (S.jour === 'weekend' && !d.we) return false;
    if (S.heure === 'pointe' && (d.h < 7 || d.h > 21)) return false;
    if (S.heure === 'creuse' && d.h >= 7 && d.h <= 21) return false;
    return true;
  });
}

// ── Animated counter ──────────────────────────────────────────────────────
const _kpiPrev = {};
function animCount(el, toVal, dur=520) {
  const from = _kpiPrev[el.id] || 0;
  _kpiPrev[el.id] = toVal;
  if (isNaN(toVal)) { el.textContent = '—'; return; }
  const start = performance.now();
  function tick(now) {
    const t = Math.min((now - start) / dur, 1);
    const ease = 1 - Math.pow(1 - t, 3);          // easeOutCubic
    el.textContent = Math.round(from + (toVal - from) * ease).toLocaleString('fr-FR');
    if (t < 1) requestAnimationFrame(tick);
    else {
      el.classList.remove('bounce');
      void el.offsetWidth;                          // force reflow
      el.classList.add('bounce');
    }
  }
  requestAnimationFrame(tick);
}

// ── KPIs ──────────────────────────────────────────────────────────────────
function setKpi(id, numVal, label) {
  const el   = document.getElementById(id);
  const valEl = el.querySelector('.kpi-val');
  valEl.id = valEl.id || (id + '_v');
  el.querySelector('.kpi-label').textContent = label;
  if (numVal === null || isNaN(numVal)) { valEl.textContent = '—'; _kpiPrev[valEl.id]=0; }
  else animCount(valEl, numVal);
}
function updateKPIs(F) {
  const vals = F.map(d=>d.elec).filter(v=>v!==null);
  const gas  = F.map(d=>d.gas).filter(v=>v!==null);
  const n = F.length;
  setKpi('kpi-n',    n,                                           'Enregistrements');
  setKpi('kpi-mean', vals.length ? mean(vals) : null,             'Moyenne élec (MW)');
  setKpi('kpi-max',  vals.length ? Math.max(...vals) : null,      'Pic max (MW)');
  setKpi('kpi-min',  vals.length ? Math.min(...vals) : null,      'Min (MW)');
  setKpi('kpi-gas',  gas.length  ? mean(gas)  : null,             'Moyenne gaz (MW)');
  document.getElementById('fbar-count').innerHTML =
    '<strong>'+n.toLocaleString('fr-FR')+'</strong> / '+TOTAL.toLocaleString('fr-FR')+' lignes';
  document.getElementById('hdr-badge').textContent = n.toLocaleString('fr-FR')+' enregistrements';
  // Highlight filter bar if any filter is active
  const active = S.season||S.jour||S.heure||S.df!=='__DATE_MIN__'||S.dt!=='__DATE_MAX__';
  document.querySelector('.fbar').classList.toggle('has-filters', !!active);
}

// ── Chart: Série temporelle ───────────────────────────────────────────────
function chartTS(F) {
  const sem = F.filter(d=>!d.we && d.elec!==null);
  const wkd = F.filter(d=>d.we  && d.elec!==null);
  const traces = [
    {x:sem.map(d=>d.dt), y:sem.map(d=>d.elec), mode:'lines+markers',
     name:'Semaine', line:{color:C_BLUE,width:1.5}, marker:{size:3}, opacity:.85},
    {x:wkd.map(d=>d.dt), y:wkd.map(d=>d.elec), mode:'markers',
     name:'Weekend', marker:{color:C_PUR,size:5}, opacity:.9},
  ];
  const layout = Object.assign({}, LAY, {
    title:'Consommation électrique dans le temps', height:320,
    xaxis:{title:'Date/Heure'}, yaxis:{title:'MW'}, hovermode:'x unified', showlegend:true
  });
  Plotly.react('c-ts', traces, layout, CFG);
}

// ── Chart: Profil horaire ─────────────────────────────────────────────────
function chartHour(F) {
  const byH = {};
  F.filter(d=>d.elec!==null).forEach(d => { (byH[d.h]=byH[d.h]||[]).push(d.elec); });
  const hours = Array.from({length:24},(_,i)=>i);
  const means = hours.map(h => mean(byH[h]||[]));
  const stds  = hours.map(h => std(byH[h]||[]));
  const upper = means.map((m,i)=>m!==null?m+stds[i]:null);
  const lower = means.map((m,i)=>m!==null?m-stds[i]:null);
  const traces = [
    {x:hours, y:upper, mode:'lines', line:{width:0}, showlegend:false, hoverinfo:'skip'},
    {x:hours, y:lower, mode:'lines', fill:'tonexty', fillcolor:'rgba(102,126,234,.15)',
     line:{width:0}, name:'±1σ'},
    {x:hours, y:means, mode:'lines+markers', name:'Moyenne',
     line:{color:C_BLUE,width:2.5}, marker:{size:5}},
  ];
  const layout = Object.assign({}, LAY, {
    title:'Profil de consommation horaire', height:300,
    xaxis:{title:'Heure',dtick:2}, yaxis:{title:'MW'}, hovermode:'x unified'
  });
  Plotly.react('c-hour', traces, layout, CFG);
}

// ── Chart: Jour de semaine ────────────────────────────────────────────────
function chartDow(F) {
  const byD = {};
  F.filter(d=>d.elec!==null).forEach(d => { (byD[d.dow]=byD[d.dow]||[]).push(d.elec); });
  const dows   = [0,1,2,3,4,5,6];
  const means  = dows.map(d => mean(byD[d]||[]));
  const stds   = dows.map(d => std(byD[d]||[]));
  const colors = dows.map(d => d>=5 ? C_PUR : C_BLUE);
  const traces = [{
    x: DOW_NAMES, y: means,
    error_y:{type:'data', array:stds, visible:true, color:'rgba(0,0,0,.25)'},
    type:'bar', marker:{color:colors},
    text: means.map(v=>v!==null?Math.round(v):''),
    textposition:'outside', hovertemplate:'%{x}<br>%{y:.0f} MW<extra></extra>'
  }];
  const layout = Object.assign({}, LAY, {
    title:'Profil par jour de la semaine', height:300,
    xaxis:{title:''}, yaxis:{title:'MW'}, showlegend:false
  });
  Plotly.react('c-dow', traces, layout, CFG);
}

// ── Chart: Heatmap Jour × Heure ───────────────────────────────────────────
function chartHeat(F) {
  const sums   = Array.from({length:7}, ()=>new Float64Array(24));
  const counts = Array.from({length:7}, ()=>new Int32Array(24));
  F.filter(d=>d.elec!==null).forEach(d => {
    sums[d.dow][d.h]   += d.elec;
    counts[d.dow][d.h] += 1;
  });
  const z = sums.map((row,dow) => Array.from({length:24},(_,h)=>
    counts[dow][h] > 0 ? Math.round(row[h]/counts[dow][h]) : null));
  const layout = Object.assign({}, LAY, {
    title:'Heatmap consommation — Jour × Heure (MW moyen)', height:300,
    xaxis:{title:'Heure', dtick:2,
           tickvals:[0,2,4,6,8,10,12,14,16,18,20,22],
           ticktext:['0h','2h','4h','6h','8h','10h','12h','14h','16h','18h','20h','22h']},
    yaxis:{title:''}
  });
  Plotly.react('c-heat', [{
    z, x:Array.from({length:24},(_,i)=>i), y:DOW_NAMES,
    type:'heatmap', colorscale:'YlOrRd', colorbar:{title:'MW'},
    hovertemplate:'%{y} %{x}h<br>%{z:.0f} MW<extra></extra>'
  }], layout, CFG);
}

// ── Chart: Profil 24h par saison ──────────────────────────────────────────
const SEASON_COLORS = {Printemps:'#4CAF50', Été:'#FF9800', Automne:'#8B4513', Hiver:'#2196F3'};
const SEASON_ORDER  = ['Printemps','Été','Automne','Hiver'];
function chartSeasonProfile(F) {
  const bySH = {};
  F.filter(d=>d.elec!==null).forEach(d => {
    const s = SEASON(d.mo);
    if (!bySH[s]) bySH[s] = {};
    (bySH[s][d.h] = bySH[s][d.h]||[]).push(d.elec);
  });
  const hours = Array.from({length:24},(_,i)=>i);
  const traces = SEASON_ORDER
    .filter(s => bySH[s] && Object.keys(bySH[s]).length)
    .map(s => ({
      x: hours,
      y: hours.map(h => mean(bySH[s][h]||[])),
      mode:'lines+markers', name:s,
      line:{color:SEASON_COLORS[s], width:2.5}, marker:{size:5},
      hovertemplate: s+' %{x}h : %{y:.0f} MW<extra></extra>'
    }));
  const layout = Object.assign({}, LAY, {
    title:'Profil de charge journalier moyen par saison', height:320,
    xaxis:{title:'Heure', dtick:2}, yaxis:{title:'MW moyen'},
    hovermode:'x unified', showlegend:true,
    legend:{orientation:'h', y:-0.18}
  });
  Plotly.react('c-season', traces.length ? traces : [], layout, CFG);
}

// ── Chart: Box plots consommation par heure ────────────────────────────────
function quartiles(arr) {
  if (!arr.length) return null;
  const s = [...arr].sort((a,b)=>a-b), n=s.length;
  const q1 = s[Math.floor(n*0.25)], q3 = s[Math.floor(n*0.75)];
  const med = n%2 ? s[Math.floor(n/2)] : (s[n/2-1]+s[n/2])/2;
  const iqr = q3-q1;
  const lo  = s.find(v=>v>=q1-1.5*iqr)??s[0];
  const hi  = [...s].reverse().find(v=>v<=q3+1.5*iqr)??s[n-1];
  return {q1, med, q3, lo, hi, avg:mean(arr)};
}
function chartBoxHour(F) {
  const byH = {};
  F.filter(d=>d.elec!==null).forEach(d => { (byH[d.h]=byH[d.h]||[]).push(d.elec); });
  const hours = Array.from({length:24},(_,i)=>i);
  const stats  = hours.map(h => quartiles(byH[h]||[]));
  const layout = Object.assign({}, LAY, {
    title:'Distribution de la consommation par heure (boîtes à moustaches)', height:340,
    xaxis:{title:'Heure', dtick:2}, yaxis:{title:'MW'}, showlegend:false
  });
  Plotly.react('c-boxhour', [{
    type:'box', x:hours,
    lowerfence: stats.map(s=>s?s.lo:null),
    q1:         stats.map(s=>s?s.q1:null),
    median:     stats.map(s=>s?s.med:null),
    q3:         stats.map(s=>s?s.q3:null),
    upperfence: stats.map(s=>s?s.hi:null),
    mean:       stats.map(s=>s?s.avg:null),
    boxmean: true,
    marker:{color:C_BLUE, opacity:.7},
    line:{color:C_BLUE},
    hovertemplate:'%{x}h — Médiane: %{median:.0f} MW<br>Q1: %{q1:.0f} · Q3: %{q3:.0f}<extra></extra>'
  }], layout, CFG);
}

// ── Chart: Heatmap calendrier Date × Heure ────────────────────────────────
function chartCalHeat(F) {
  const byDH = {};
  F.filter(d=>d.elec!==null).forEach(d => {
    if (!byDH[d.date]) byDH[d.date] = {};
    (byDH[d.date][d.h] = byDH[d.date][d.h]||[]).push(d.elec);
  });
  const dates = Object.keys(byDH).sort();
  const hours = Array.from({length:24},(_,i)=>i);
  const z = dates.map(dt => hours.map(h => {
    const v = byDH[dt][h]; return v?.length ? Math.round(mean(v)) : null;
  }));
  const layout = Object.assign({}, LAY, {
    title:'Heatmap calendrier — Date × Heure (MW moyen)',
    height: Math.max(320, dates.length*22+120),
    xaxis:{title:'Heure', dtick:2,
           tickvals:[0,2,4,6,8,10,12,14,16,18,20,22],
           ticktext:['0h','2h','4h','6h','8h','10h','12h','14h','16h','18h','20h','22h']},
    yaxis:{title:'', autorange:'reversed'}
  });
  Plotly.react('c-calheat', [{
    z, x:hours, y:dates, type:'heatmap', colorscale:'Viridis',
    colorbar:{title:'MW'},
    hovertemplate:'%{y} %{x}h<br>%{z:.0f} MW<extra></extra>'
  }], layout, CFG);
}

// ── Chart: Semaine vs Weekend ──────────────────────────────────────────────
function chartCmp(F) {
  const sem = F.filter(d=>!d.we&&d.elec!==null).map(d=>d.elec);
  const wkd = F.filter(d=>d.we &&d.elec!==null).map(d=>d.elec);
  const traces = [{
    x:['Semaine','Weekend'],
    y:[mean(sem), mean(wkd)],
    error_y:{type:'data', array:[std(sem),std(wkd)], visible:true},
    type:'bar', marker:{color:[C_BLUE,C_PUR]},
    text:[fmt(mean(sem)),fmt(mean(wkd))], textposition:'outside',
    hovertemplate:'%{x}<br>%{y:.0f} MW<extra></extra>'
  }];
  const layout = Object.assign({}, LAY, {
    title:'Semaine vs Weekend', height:300,
    xaxis:{title:''}, yaxis:{title:'MW moyen'}, showlegend:false
  });
  Plotly.react('c-cmp', traces, layout, CFG);
}

// ── Chart: Distribution ───────────────────────────────────────────────────
function chartHist(F) {
  const vals = F.filter(d=>d.elec!==null).map(d=>d.elec);
  const layout = Object.assign({}, LAY, {
    title:'Distribution de la consommation', height:300,
    xaxis:{title:'MW'}, yaxis:{title:'Fréquence'}, showlegend:false
  });
  if (!vals.length) { Plotly.react('c-hist',[],layout,CFG); return; }
  Plotly.react('c-hist', [{
    x:vals, type:'histogram', nbinsx:30,
    marker:{color:C_BLUE, opacity:.75, line:{color:'#fff',width:.5}}
  }], layout, CFG);
}

// ── Main update ───────────────────────────────────────────────────────────
function updateAll() {
  const F = filtered();
  updateKPIs(F);
  const empty = F.length === 0;
  const nd = document.getElementById('nodata');
  const cw = document.getElementById('charts-wrap');

  if (empty) {
    nd.style.display = '';             // let CSS class drive display
    nd.classList.add('visible');
    cw.style.display = 'none';
    return;
  }

  nd.classList.remove('visible');
  nd.style.display = '';              // CSS #nodata{display:none} takes over
  cw.style.display = 'block';

  // Brief shimmer while Plotly recalculates
  cw.classList.add('updating');
  requestAnimationFrame(() => {
    chartTS(F); chartSeasonProfile(F); chartHour(F); chartDow(F);
    chartBoxHour(F); chartHeat(F); chartCalHeat(F); chartCmp(F); chartHist(F);
    requestAnimationFrame(() => cw.classList.remove('updating'));
  });
}

// ── Events: date inputs ───────────────────────────────────────────────────
document.getElementById('dateFrom').addEventListener('change', e=>{S.df=e.target.value; updateAll();});
document.getElementById('dateTo').addEventListener('change',   e=>{S.dt=e.target.value; updateAll();});

// ── Events: pills ─────────────────────────────────────────────────────────
function wirePills(groupId, stateKey) {
  const group = document.getElementById(groupId);
  group.querySelectorAll('.pill').forEach(btn => {
    btn.addEventListener('click', () => {
      group.querySelectorAll('.pill').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      S[stateKey] = btn.dataset.v;
      updateAll();
    });
  });
}
wirePills('p-season', 'season');
wirePills('p-jour',   'jour');
wirePills('p-heure',  'heure');

// ── Reset ─────────────────────────────────────────────────────────────────
function resetFilters() {
  S.df='__DATE_MIN__'; S.dt='__DATE_MAX__'; S.season=''; S.jour=''; S.heure='';
  document.getElementById('dateFrom').value = '__DATE_MIN__';
  document.getElementById('dateTo').value   = '__DATE_MAX__';
  document.querySelectorAll('.pills .pill').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.pills .pill[data-v=""]').forEach(b=>b.classList.add('active'));
  updateAll();
}

// ── Init ──────────────────────────────────────────────────────────────────
updateAll();
</script>
</body>
</html>"""
