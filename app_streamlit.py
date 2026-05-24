"""
Dashboard Streamlit — Consommation Énergétique France
Interface interactive multi-régions avec filtres temporels.
"""
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import sys
import os

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ── Configuration de la page ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Énergie France — Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Chemins ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
WAREHOUSE_DIR = BASE_DIR / "data" / "warehouse"
GOVERNANCE_DIR = BASE_DIR / "data" / "governance" / "quality"
RAW_RTE_DIR = BASE_DIR / "data" / "raw" / "rte"

REGION_LABELS = {
    "idf": "Île-de-France",
    "provence": "Provence-Alpes-Côte d'Azur",
    "bretagne": "Bretagne",
    "nouvelle-aquitaine": "Nouvelle-Aquitaine",
}

COLORS = {
    "primary": "#1f77b4",
    "secondary": "#ff7f0e",
    "accent": "#2ca02c",
    "danger": "#d62728",
    "weekend": "#9467bd",
    "weekday": "#17becf",
    "gas": "#e17055",
    "nuclear": "#f39c12",
    "wind": "#74b9ff",
    "solar": "#ffd32a",
    "hydro": "#0652DD",
    "bio": "#00b894",
}

# ── Chargement des données ─────────────────────────────────────────────────────

@st.cache_data(ttl=1800)
def load_warehouse(region: str) -> Optional[pd.DataFrame]:
    path = WAREHOUSE_DIR / f"energy_consumption_{region}" / "latest.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


@st.cache_data(ttl=1800)
def load_governance(region: str) -> Optional[dict]:
    path = GOVERNANCE_DIR / f"quality_energy_consumption_{region}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


@st.cache_data(ttl=1800)
def load_rte_raw() -> Optional[list]:
    files = sorted(RAW_RTE_DIR.glob("*.json"), reverse=True) if RAW_RTE_DIR.exists() else []
    if not files:
        return None
    try:
        return json.loads(files[0].read_text())
    except Exception:
        return None


RAW_METEO_DIR = BASE_DIR / "data" / "raw" / "meteo"


@st.cache_data(ttl=1800)
def load_merged_df(region: str) -> Optional[pd.DataFrame]:
    """Fusionne énergie + météo pour la région donnée."""
    energy_df = load_warehouse(region)
    if energy_df is None or energy_df.empty:
        return None

    # 1. Fichier dédié à la région (ancien format : meteo_{region}_*.csv)
    meteo_files = sorted(RAW_METEO_DIR.glob(f"meteo_{region}_*.csv"), reverse=True)
    if meteo_files:
        try:
            weather_df = pd.read_csv(meteo_files[0])
        except Exception:
            weather_df = None
    else:
        weather_df = None

    # 2. Fichier combiné toutes régions (nouveau format : meteo_regions_*.csv)
    if weather_df is None or weather_df.empty:
        combined_files = sorted(RAW_METEO_DIR.glob("meteo_regions_*.csv"), reverse=True)
        if not combined_files:
            return None
        try:
            df_all = pd.read_csv(combined_files[0])
            weather_df = df_all[df_all["region"] == region].drop(columns=["region"], errors="ignore").copy()
        except Exception:
            return None

    if weather_df is None or weather_df.empty:
        return None

    try:
        weather_df["datetime"] = pd.to_datetime(weather_df["datetime"], utc=True)
    except Exception:
        return None

    sys.path.insert(0, str(BASE_DIR))
    from src.etl.merger import DataMerger
    merger = DataMerger()
    try:
        merged = merger.merge_energy_weather(energy_df, weather_df)
        merged = merger.add_weather_categories(merged)
        return merged
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def run_prophet_forecast(region: str, horizon_days: int = 7) -> Optional[pd.DataFrame]:
    """Entraîne Prophet sur toutes les données disponibles et retourne les prévisions."""
    df = load_warehouse(region)
    if df is None or df.empty:
        return None

    # Prophet n'accepte pas les datetimes avec timezone — on strip l'info tz
    df = df.copy()
    df["datetime"] = df["datetime"].dt.tz_localize(None)

    try:
        import logging
        # Silencer les logs verbeux de cmdstanpy et prophet
        logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
        logging.getLogger("prophet").setLevel(logging.ERROR)

        sys.path.insert(0, str(BASE_DIR))
        from src.analysis.forecasting import ConsumptionForecaster
        forecaster = ConsumptionForecaster(df)
        prophet_result = forecaster.train_prophet()
        if not prophet_result:
            return None
        forecast_df = forecaster.predict_prophet(prophet_result, periods=horizon_days)
        return forecast_df
    except Exception:
        return None


def filter_by_period(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    mask = (df["datetime"].dt.date >= start) & (df["datetime"].dt.date <= end)
    return df[mask].copy()


def detect_elec_col(df: pd.DataFrame) -> Optional[str]:
    for col in ["consommation_brute_electricite_rte", "elec_consumption_mw", "electricity_mw"]:
        if col in df.columns:
            return col
    return None


PLOTLY_CONFIG = {
    "toImageButtonOptions": {"format": "png", "scale": 2},
    "displaylogo": False,
    "modeBarButtonsToAdd": ["downloadImage"],
}


def pchart(fig: go.Figure, key: str = "", **kwargs) -> None:
    """Wrapper st.plotly_chart avec config PNG systématique."""
    cfg = {**PLOTLY_CONFIG, "toImageButtonOptions": {**PLOTLY_CONFIG["toImageButtonOptions"], "filename": key or "energie_france"}}
    st.plotly_chart(fig, use_container_width=True, config=cfg, **kwargs)


def df_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def available_regions() -> list[str]:
    """Retourne les régions qui ont un fichier latest.csv dans le warehouse."""
    return [
        region for region in REGION_LABELS
        if (WAREHOUSE_DIR / f"energy_consumption_{region}" / "latest.csv").exists()
    ]


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚡ Énergie France")
    st.markdown("---")

    regions_ok = available_regions()
    all_regions = list(REGION_LABELS.keys())

    def format_region(k: str) -> str:
        return REGION_LABELS[k] if k in regions_ok else f"{REGION_LABELS[k]} (données manquantes)"

    selected_region = st.selectbox(
        "Région",
        options=all_regions,
        format_func=format_region,
        index=0,
    )

    if selected_region not in regions_ok:
        st.warning(
            f"Pas de données pour cette région. "
            f"Lancez le pipeline :\n```\npython scripts/ingest.py\n```"
        )
        st.stop()

    # Charger les données ici pour connaître la plage réelle
    _df_probe = load_warehouse(selected_region)
    if _df_probe is not None and not _df_probe.empty:
        _data_max = _df_probe["datetime"].dt.date.max()
        _data_min = _df_probe["datetime"].dt.date.min()
    else:
        _data_max = date.today()
        _data_min = date.today() - timedelta(days=30)

    st.markdown("**Période**")
    period_preset = st.radio(
        "Période",
        ["7 jours", "30 jours", "90 jours", "Tout", "Personnalisée"],
        label_visibility="collapsed",
    )

    if period_preset == "7 jours":
        date_start = _data_max - timedelta(days=7)
        date_end = _data_max
    elif period_preset == "30 jours":
        date_start = _data_max - timedelta(days=30)
        date_end = _data_max
    elif period_preset == "90 jours":
        date_start = _data_max - timedelta(days=90)
        date_end = _data_max
    elif period_preset == "Tout":
        date_start, date_end = _data_min, _data_max
    else:
        date_start = st.date_input("Début", _data_max - timedelta(days=30))
        date_end = st.date_input("Fin", _data_max)

    st.markdown("---")
    st.markdown("**Alerte consommation**")
    alert_threshold = st.number_input(
        "Seuil (MW) — 0 = désactivé",
        min_value=0,
        value=0,
        step=500,
        help="Affiche une ligne rouge sur les graphiques et un avertissement si la consommation dépasse ce seuil.",
    )

    st.markdown("---")
    st.markdown("**Exporter**")
    # Le bouton est rendu ici mais df n'est pas encore filtré — on utilise _df_probe
    # et on refiltre inline pour éviter de déplacer le chargement principal.
    _export_df = _df_probe.copy() if _df_probe is not None else pd.DataFrame()
    if not _export_df.empty:
        _mask = (
            (_export_df["datetime"].dt.date >= date_start)
            & (_export_df["datetime"].dt.date <= date_end)
        )
        _export_df = _export_df[_mask]
    st.download_button(
        label="Télécharger les données (CSV)",
        data=df_to_csv(_export_df) if not _export_df.empty else b"",
        file_name=f"energie_{selected_region}_{date_start}_{date_end}.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=_export_df.empty,
    )
    st.markdown("---")
    st.markdown(
        "<small style='color:#888'>Données : ODRE · RTE · Open-Meteo<br>"
        "Mis à jour quotidiennement à 6h UTC</small>",
        unsafe_allow_html=True,
    )

# ── Chargement ─────────────────────────────────────────────────────────────────

df_full = load_warehouse(selected_region)
gov = load_governance(selected_region)
rte_raw = load_rte_raw()

if df_full is None:
    st.error(
        f"Aucune donnée disponible pour **{REGION_LABELS[selected_region]}**. "
        "Lancez d'abord le pipeline : `python scripts/run_full_pipeline.py`"
    )
    st.stop()

df = filter_by_period(df_full, date_start, date_end)
elec_col = detect_elec_col(df)

if df.empty:
    st.warning("Aucune donnée sur la période sélectionnée. Essayez une plage plus large.")
    st.stop()

# ── Bannière alerte seuil ──────────────────────────────────────────────────────

if alert_threshold > 0 and elec_col:
    peaks_above = df[df[elec_col] > alert_threshold]
    if not peaks_above.empty:
        peak_max = peaks_above[elec_col].max()
        pct = len(peaks_above) / len(df) * 100
        st.warning(
            f"**{len(peaks_above):,} relevés ({pct:.1f}%) dépassent le seuil de {alert_threshold:,} MW** "
            f"— pic max enregistré : **{peak_max:,.0f} MW**"
        )
    else:
        st.success(f"Aucun relevé ne dépasse le seuil de {alert_threshold:,} MW sur la période.")

# ── Onglets ────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Vue d'ensemble",
    "Consommation",
    "Météo × Énergie",
    "Mix de production",
    "Gouvernance",
    "Prévisions",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Vue d'ensemble
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    st.markdown(f"### {REGION_LABELS[selected_region]} — Vue d'ensemble")
    st.caption(f"Du {date_start.strftime('%d/%m/%Y')} au {date_end.strftime('%d/%m/%Y')}")

    # KPIs avec delta vs période précédente
    period_len = (date_end - date_start).days or 1
    prev_start = date_start - timedelta(days=period_len)
    prev_end = date_start - timedelta(days=1)
    df_prev = filter_by_period(df_full, prev_start, prev_end)

    def kpi_delta(current_val, prev_val):
        if prev_val and prev_val != 0:
            return round((current_val - prev_val) / abs(prev_val) * 100, 1)
        return None

    # Ligne 1 — métriques électricité (3 colonnes, plus d'espace)
    col1, col2, col3 = st.columns(3)

    if elec_col:
        mean_now = df[elec_col].mean()
        peak_now = df[elec_col].max()
        min_now  = df[elec_col].min()
        mean_prev = df_prev[elec_col].mean() if not df_prev.empty else None
        peak_prev = df_prev[elec_col].max() if not df_prev.empty else None

        delta_mean = kpi_delta(mean_now, mean_prev)
        delta_peak = kpi_delta(peak_now, peak_prev)

        col1.metric(
            "Consommation moy.",
            f"{mean_now:,.0f} MW",
            delta=f"{delta_mean:+.1f}% vs préc." if delta_mean else None,
            delta_color="inverse",
            help="Consommation électrique moyenne sur la période",
        )
        col2.metric(
            "Pic de consommation",
            f"{peak_now:,.0f} MW",
            delta=f"{delta_peak:+.1f}% vs préc." if delta_peak else None,
            delta_color="inverse",
            help="Consommation maximale enregistrée sur la période",
        )
        col3.metric(
            "Minimum",
            f"{min_now:,.0f} MW",
            help="Consommation minimale enregistrée sur la période",
        )

    st.markdown("")  # espace vertical

    # Ligne 2 — gaz + compteurs (4 colonnes)
    col4, col5, col6, col7 = st.columns(4)

    if "consommation_brute_gaz_totale" in df.columns:
        mean_gas = df["consommation_brute_gaz_totale"].mean()
        prev_gas = df_prev["consommation_brute_gaz_totale"].mean() if not df_prev.empty else None
        delta_gas = kpi_delta(mean_gas, prev_gas)
        col4.metric(
            "Gaz moyen",
            f"{mean_gas:,.0f} MWh",
            delta=f"{delta_gas:+.1f}% vs préc." if delta_gas else None,
            delta_color="inverse",
        )

    col5.metric("Enregistrements", f"{len(df):,}")
    col6.metric("Jours couverts", f"{df['date'].nunique() if 'date' in df.columns else '—'}")

    if elec_col:
        variation = df[elec_col].std() / df[elec_col].mean() * 100
        col7.metric("Variabilité", f"{variation:.1f}%", help="Coefficient de variation (σ/μ)")

    # Score qualité
    st.markdown("---")
    if gov:
        score = gov.get("score", 0)
        color = "#2ca02c" if score >= 80 else ("#ff7f0e" if score >= 60 else "#d62728")
        col_score, col_rules = st.columns([1, 2])
        with col_score:
            st.markdown(f"**Score qualité des données**")
            st.markdown(
                f"<div style='font-size:3em;font-weight:bold;color:{color}'>{score:.0f}%</div>",
                unsafe_allow_html=True,
            )
            ts = gov.get("timestamp", "")[:10]
            st.caption(f"Calculé le {ts}")
        with col_rules:
            st.markdown("**Règles de gouvernance**")
            for rule in gov.get("rules", []):
                icon = "✅" if rule["passed"] else ("⚠️" if rule["severity"] == "warning" else "❌")
                st.markdown(f"{icon} **{rule['description']}** — {rule['details']}")
    else:
        st.info("Score de qualité non disponible. Lancez `python scripts/run_governance.py`.")

    # Aperçu de la série temporelle
    st.markdown("---")
    st.markdown("**Série temporelle — Consommation électrique**")
    if elec_col and "datetime" in df.columns:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["datetime"], y=df[elec_col],
            mode="lines", name="Électricité (MW)",
            line=dict(color=COLORS["primary"], width=1.5),
        ))
        if "consommation_brute_gaz_totale" in df.columns:
            fig.add_trace(go.Scatter(
                x=df["datetime"], y=df["consommation_brute_gaz_totale"],
                mode="lines", name="Gaz (MWh)",
                line=dict(color=COLORS["gas"], width=1.5, dash="dot"),
                yaxis="y2",
            ))
        fig.update_layout(
            template="plotly_white",
            height=350,
            hovermode="x unified",
            margin=dict(t=20, b=40),
            yaxis=dict(title="Électricité (MW)"),
            yaxis2=dict(title="Gaz (MWh)", overlaying="y", side="right"),
            legend=dict(orientation="h", y=1.05),
            xaxis=dict(
                rangeselector=dict(buttons=[
                    dict(count=1, label="1j", step="day", stepmode="backward"),
                    dict(count=7, label="7j", step="day", stepmode="backward"),
                    dict(step="all", label="Tout"),
                ]),
                rangeslider=dict(visible=False),
            ),
        )
        if alert_threshold > 0:
            fig.add_hline(
                y=alert_threshold,
                line=dict(color="red", width=2, dash="dash"),
                annotation_text=f"Seuil {alert_threshold:,} MW",
                annotation_position="top left",
                annotation=dict(font=dict(color="red", size=12)),
            )
        pchart(fig, key="serie_temporelle_overview")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Consommation
# ══════════════════════════════════════════════════════════════════════════════

with tab2:
    st.markdown("### Analyse de la consommation")

    if not elec_col:
        st.warning("Colonne de consommation électrique introuvable dans les données.")
        st.stop()

    row1_col1, row1_col2 = st.columns(2)

    # Profil horaire
    with row1_col1:
        st.markdown("**Profil horaire moyen**")
        if "hour" in df.columns:
            profile = df.groupby("hour")[elec_col].agg(["mean", "max", "min"]).reset_index()
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=profile["hour"], y=profile["mean"],
                mode="lines+markers", name="Moyenne",
                line=dict(color=COLORS["primary"], width=3), marker=dict(size=6),
            ))
            fig.add_trace(go.Scatter(
                x=profile["hour"], y=profile["max"],
                mode="lines", name="Max",
                line=dict(color=COLORS["danger"], width=1, dash="dash"),
            ))
            fig.add_trace(go.Scatter(
                x=profile["hour"], y=profile["min"],
                mode="lines", name="Min",
                line=dict(color=COLORS["accent"], width=1, dash="dash"),
                fill="tonexty", fillcolor="rgba(44,160,44,0.08)",
            ))
            fig.update_layout(
                template="plotly_white", height=320,
                xaxis_title="Heure", yaxis_title="MW",
                xaxis=dict(dtick=2), hovermode="x unified",
                margin=dict(t=10, b=40), legend=dict(orientation="h", y=1.05),
            )
            if alert_threshold > 0:
                fig.add_hline(
                    y=alert_threshold,
                    line=dict(color="red", width=2, dash="dash"),
                    annotation_text=f"Seuil {alert_threshold:,} MW",
                    annotation_position="top left",
                    annotation=dict(font=dict(color="red", size=11)),
                )
            pchart(fig, key="profil_horaire")
        else:
            st.info("Colonne 'hour' absente.")

    # Profil par jour de la semaine
    with row1_col2:
        st.markdown("**Consommation par jour de la semaine**")
        if "day_of_week" in df.columns:
            day_names = {0: "Lun", 1: "Mar", 2: "Mer", 3: "Jeu", 4: "Ven", 5: "Sam", 6: "Dim"}
            dow = df.groupby("day_of_week")[elec_col].agg(["mean", "std"]).reset_index()
            dow["day_name"] = dow["day_of_week"].map(day_names)
            colors_bar = [
                COLORS["weekend"] if d >= 5 else COLORS["weekday"]
                for d in dow["day_of_week"]
            ]
            fig = go.Figure(go.Bar(
                x=dow["day_name"], y=dow["mean"],
                error_y=dict(type="data", array=dow["std"], visible=True),
                marker_color=colors_bar,
                text=dow["mean"].round(0), textposition="outside",
            ))
            fig.update_layout(
                template="plotly_white", height=320,
                yaxis_title="MW moyen", showlegend=False,
                margin=dict(t=10, b=40),
            )
            pchart(fig, key="profil_semaine")
        else:
            st.info("Colonne 'day_of_week' absente.")

    # Consommation journalière
    st.markdown("**Consommation journalière**")
    if "date" in df.columns:
        daily = df.groupby("date")[elec_col].agg(["sum", "max"]).reset_index()
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            subplot_titles=("Total (MW)", "Pic (MW)"),
                            vertical_spacing=0.1)
        fig.add_trace(go.Bar(
            x=daily["date"], y=daily["sum"], name="Total",
            marker_color=COLORS["primary"], opacity=0.8,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=daily["date"], y=daily["max"], name="Pic",
            mode="lines+markers", line=dict(color=COLORS["danger"], width=2),
            marker=dict(size=5),
        ), row=2, col=1)
        fig.update_layout(
            template="plotly_white", height=400,
            showlegend=True, hovermode="x unified",
            margin=dict(t=30, b=40),
        )
        fig.update_yaxes(title_text="Total (MW)", row=1, col=1)
        fig.update_yaxes(title_text="Pic (MW)", row=2, col=1)
        if alert_threshold > 0:
            fig.add_hline(
                y=alert_threshold,
                row=2, col=1,
                line=dict(color="red", width=2, dash="dash"),
                annotation_text=f"Seuil {alert_threshold:,} MW",
                annotation_position="top left",
                annotation=dict(font=dict(color="red", size=11)),
            )
        pchart(fig, key="consommation_journaliere")

    # Heatmap
    st.markdown("**Heatmap consommation (Jour × Heure)**")
    if "hour" in df.columns and "date" in df.columns:
        pivot = df.pivot_table(values=elec_col, index="date", columns="hour", aggfunc="mean")
        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[f"{h}h" for h in pivot.columns],
            y=[str(d) for d in pivot.index],
            colorscale="YlOrRd",
            colorbar_title="MW",
            hovertemplate="Date: %{y}<br>Heure: %{x}<br>%{z:.0f} MW<extra></extra>",
        ))
        fig.update_layout(
            template="plotly_white", height=420,
            xaxis_title="Heure", yaxis_title="Date",
            margin=dict(t=10, b=40),
        )
        pchart(fig, key="heatmap_conso")

    # Anomalies
    st.markdown("**Détection d'anomalies (z-score)**")
    z_threshold = st.slider("Seuil z-score", min_value=1.5, max_value=4.0, value=2.5, step=0.1)
    if "datetime" in df.columns:
        series = df[elec_col].dropna()
        z_scores = (series - series.mean()).abs() / series.std()
        anomalies = df.loc[z_scores[z_scores > z_threshold].index]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["datetime"], y=df[elec_col],
            mode="lines", name="Consommation",
            line=dict(color=COLORS["primary"], width=1), opacity=0.6,
        ))
        if not anomalies.empty:
            fig.add_trace(go.Scatter(
                x=anomalies["datetime"], y=anomalies[elec_col],
                mode="markers", name=f"Anomalies ({len(anomalies)})",
                marker=dict(color=COLORS["danger"], size=10, symbol="x"),
            ))
        fig.update_layout(
            template="plotly_white", height=320,
            hovermode="x unified", margin=dict(t=10, b=40),
            xaxis_title="Date/Heure", yaxis_title="MW",
        )
        pchart(fig, key="anomalies")
        if not anomalies.empty:
            st.caption(f"{len(anomalies)} anomalie(s) détectée(s) sur {len(df)} enregistrements.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Météo × Énergie
# ══════════════════════════════════════════════════════════════════════════════

with tab3:
    st.markdown("### Météo × Énergie")
    st.caption(f"Corrélation entre conditions météorologiques et consommation — {REGION_LABELS[selected_region]}")

    df_merged = load_merged_df(selected_region)

    if df_merged is None:
        st.info(
            "Données météo non disponibles pour cette région. "
            "Lancez l'ingestion : `python scripts/ingest.py`"
        )
    else:
        # Filtrer par période
        df_mx = filter_by_period(df_merged, date_start, date_end)
        if df_mx.empty:
            st.warning("Aucune donnée fusionnée sur la période sélectionnée.")
        else:
            elec_mx = detect_elec_col(df_mx)

            # ── KPIs météo ──────────────────────────────────────────────────
            k1, k2, k3, k4 = st.columns(4)
            if "temperature_2m" in df_mx.columns:
                k1.metric("Température moyenne", f"{df_mx['temperature_2m'].mean():.1f} °C")
                k2.metric("Temp. min / max", f"{df_mx['temperature_2m'].min():.1f} / {df_mx['temperature_2m'].max():.1f} °C")
            if elec_mx and "temperature_2m" in df_mx.columns:
                corr = df_mx["temperature_2m"].corr(df_mx[elec_mx])
                k3.metric("Corrélation Temp → Conso", f"{corr:+.2f}")
            if "is_rainy" in df_mx.columns:
                pct_rain = df_mx["is_rainy"].mean() * 100
                k4.metric("Jours de pluie", f"{pct_rain:.0f}%")

            st.markdown("---")

            sys.path.insert(0, str(BASE_DIR))
            from src.analysis.cross_dashboard import CrossDashboardBuilder
            builder = CrossDashboardBuilder(df_mx, region_label=REGION_LABELS[selected_region])

            # ── Graphique 1 : double-axe énergie + température ───────────────
            st.markdown("**Consommation électrique vs Température**")
            fig_et = builder.build_energy_vs_temperature()
            fig_et.update_layout(height=380, margin=dict(t=20, b=40))
            pchart(fig_et, key="meteo_energie_temp")

            # ── Graphiques 2 + 3 côte à côte ────────────────────────────────
            col_sc, col_bar = st.columns(2)

            with col_sc:
                st.markdown("**Scatter : Température → Consommation**")
                fig_sc = builder.build_scatter_temp_consumption()
                fig_sc.update_layout(height=380, margin=dict(t=20, b=40))
                pchart(fig_sc, key="scatter_temp_conso")

            with col_bar:
                st.markdown("**Impact par catégorie de température**")
                fig_wb = builder.build_weather_impact_bars()
                fig_wb.update_layout(height=380, margin=dict(t=20, b=40))
                pchart(fig_wb, key="impact_temperature")

            # ── Graphique 4 : matrice de corrélation ─────────────────────────
            st.markdown("**Matrice de corrélation — Énergie × Variables météo**")
            fig_hm = builder.build_multivar_heatmap()
            fig_hm.update_layout(height=460, margin=dict(t=20, b=40))
            pchart(fig_hm, key="correlation_meteo")

            # ── Graphique 5 : vent + pluie ────────────────────────────────────
            wind_ok = "wind_category" in df_mx.columns
            rain_ok = "is_rainy" in df_mx.columns
            if wind_ok or rain_ok:
                st.markdown("**Impact vent & précipitations sur la consommation**")
                fig_wr = builder.build_wind_rain_analysis()
                fig_wr.update_layout(height=320, margin=dict(t=20, b=40))
                pchart(fig_wr, key="impact_vent_pluie")

            # ── Graphique 6 : vue journalière ─────────────────────────────────
            st.markdown("**Vue journalière — Consommation & Météo**")
            fig_do = builder.build_daily_overview()
            fig_do.update_layout(height=480, margin=dict(t=20, b=40))
            pchart(fig_do, key="vue_journaliere_meteo")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Mix de production RTE
# ══════════════════════════════════════════════════════════════════════════════

with tab4:  # Mix de production
    st.markdown("### Mix de génération électrique — France (RTE)")

    LABELS_FR = {
        "NUCLEAR": "Nucléaire", "WIND": "Éolien", "SOLAR": "Solaire",
        "HYDRO": "Hydraulique", "THERMAL": "Thermique", "BIOENERGY": "Bioénergie",
        "PUMPING": "Pompage", "EXCHANGE": "Échanges", "OTHER": "Autre",
        "FOSSIL_GAS": "Gaz", "FOSSIL_HARD_COAL": "Charbon", "FOSSIL_OIL": "Fioul",
        "WASTE": "Déchets",
    }
    COLORS_MIX = {
        "Nucléaire": COLORS["nuclear"], "Éolien": COLORS["wind"],
        "Solaire": COLORS["solar"], "Hydraulique": COLORS["hydro"],
        "Thermique": "#e17055", "Bioénergie": COLORS["bio"],
        "Gaz": "#fd79a8", "Charbon": "#636e72", "Fioul": "#b2bec3",
        "Pompage": "#a29bfe", "Déchets": "#55efc4", "Autre": "#95a5a6",
        "Échanges": "#dfe6e9",
    }

    if rte_raw is None:
        st.info(
            "Données RTE non disponibles. Configurez votre `RTE_API_KEY` "
            "et relancez `python scripts/ingest.py`."
        )
    else:
        records = rte_raw if isinstance(rte_raw, list) else rte_raw.get("generation_mix", [])
        totals: dict = {}
        for record in records:
            ptype = record.get("production_type", "OTHER")
            label = LABELS_FR.get(ptype, ptype.capitalize())
            values = record.get("values", [])
            total = sum(v.get("value", 0) or 0 for v in values)
            if total > 0:
                totals[label] = totals.get(label, 0) + total

        if not totals:
            st.warning("Données RTE présentes mais aucune valeur exploitable.")
        else:
            labels = list(totals.keys())
            values_mix = list(totals.values())
            colors_list = [COLORS_MIX.get(lbl, "#95a5a6") for lbl in labels]

            col_donut, col_bar = st.columns(2)

            with col_donut:
                st.markdown("**Répartition globale**")
                fig = go.Figure(data=go.Pie(
                    labels=labels, values=values_mix, hole=0.45,
                    marker=dict(colors=colors_list),
                    textinfo="label+percent",
                    hovertemplate="<b>%{label}</b><br>%{value:,.0f} MW·h<br>%{percent}<extra></extra>",
                ))
                fig.update_layout(
                    template="plotly_white", height=400,
                    annotations=[dict(text="Mix<br>RTE", x=0.5, y=0.5, font_size=14, showarrow=False)],
                    margin=dict(t=10, b=10),
                )
                pchart(fig, key="mix_rte_donut")

            with col_bar:
                st.markdown("**Détail par filière**")
                sorted_items = sorted(zip(labels, values_mix), key=lambda x: x[1], reverse=True)
                s_labels, s_values = zip(*sorted_items)
                s_colors = [COLORS_MIX.get(lbl, "#95a5a6") for lbl in s_labels]
                fig = go.Figure(go.Bar(
                    x=list(s_values), y=list(s_labels),
                    orientation="h",
                    marker_color=s_colors,
                    text=[f"{v:,.0f}" for v in s_values],
                    textposition="outside",
                ))
                fig.update_layout(
                    template="plotly_white", height=400,
                    xaxis_title="MW·h", yaxis=dict(autorange="reversed"),
                    margin=dict(t=10, b=40, r=80),
                )
                pchart(fig, key="mix_rte_barres")

            # Part renouvelable
            renouvelable = ["Éolien", "Solaire", "Hydraulique", "Bioénergie"]
            total_all = sum(values_mix)
            total_renew = sum(totals.get(r, 0) for r in renouvelable)
            pct_renew = (total_renew / total_all * 100) if total_all > 0 else 0
            pct_nuc = (totals.get("Nucléaire", 0) / total_all * 100) if total_all > 0 else 0

            st.markdown("---")
            k1, k2, k3 = st.columns(3)
            k1.metric("Part renouvelable", f"{pct_renew:.1f}%")
            k2.metric("Part nucléaire", f"{pct_nuc:.1f}%")
            k3.metric("Filières", len(totals))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Gouvernance
# ══════════════════════════════════════════════════════════════════════════════

with tab5:
    st.markdown("### Gouvernance & qualité des données")

    if not gov:
        st.info("Rapport de gouvernance non disponible. Lancez `python scripts/run_governance.py`.")
    else:
        score = gov.get("score", 0)
        color = "#2ca02c" if score >= 80 else ("#ff7f0e" if score >= 60 else "#d62728")

        col_gauge, col_info = st.columns([1, 2])

        with col_gauge:
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=score,
                title={"text": "Score qualité"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": color},
                    "steps": [
                        {"range": [0, 60], "color": "#ffeaea"},
                        {"range": [60, 80], "color": "#fff3e0"},
                        {"range": [80, 100], "color": "#e8f5e9"},
                    ],
                    "threshold": {
                        "line": {"color": "#333", "width": 2},
                        "thickness": 0.75,
                        "value": score,
                    },
                },
                number={"suffix": "%"},
            ))
            fig.update_layout(height=280, margin=dict(t=30, b=0))
            pchart(fig, key="qualite_score")

        with col_info:
            st.markdown(f"**Dataset :** `{gov.get('dataset_name', '—')}`")
            st.markdown(f"**Lignes :** {gov.get('total_rows', '—'):,}")
            st.markdown(f"**Colonnes :** {gov.get('total_columns', '—')}")
            st.markdown(f"**Calculé le :** {gov.get('timestamp', '—')[:10]}")
            status = "✅ Conforme" if gov.get("passed") else "❌ Non conforme"
            st.markdown(f"**Statut :** {status}")

        st.markdown("---")
        st.markdown("**Détail des règles**")

        for rule in gov.get("rules", []):
            sev = rule.get("severity", "info")
            if rule["passed"]:
                icon, bg = "✅", "#e8f5e9"
            elif sev == "warning":
                icon, bg = "⚠️", "#fff3e0"
            else:
                icon, bg = "❌", "#ffeaea"

            st.markdown(
                f"<div style='background:{bg};padding:10px 14px;border-radius:6px;margin-bottom:6px'>"
                f"{icon} <b>{rule['description']}</b><br>"
                f"<small style='color:#555'>{rule['details']}</small>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # Aperçu des données brutes
    st.markdown("---")
    st.markdown("**Aperçu des données (50 dernières lignes)**")
    cols_to_show = [c for c in [
        "datetime", "region_name", "consommation_brute_electricite_rte",
        "consommation_brute_gaz_totale", "hour", "day_of_week", "is_weekend",
    ] if c in df.columns]
    st.dataframe(
        df[cols_to_show].tail(50).reset_index(drop=True),
        use_container_width=True,
        height=300,
    )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — Prévisions Prophet
# ══════════════════════════════════════════════════════════════════════════════

with tab6:
    # ── Sélecteur d'horizon ───────────────────────────────────────────────────
    ctrl_col, _, info_col = st.columns([1, 2, 1])
    with ctrl_col:
        horizon_days = st.select_slider(
            "Horizon de prévision",
            options=[3, 7, 14],
            value=7,
            format_func=lambda x: f"J+{x}",
        )
    with info_col:
        st.caption(f"IC 95% · Prophet · {REGION_LABELS[selected_region]}")

    st.markdown(f"### Prévisions de consommation — J+{horizon_days}")

    with st.spinner(f"Calcul des prévisions J+{horizon_days}… (30–60 s la première fois)"):
        forecast_df = run_prophet_forecast(selected_region, horizon_days=horizon_days)

    if forecast_df is None:
        st.error(
            "Impossible de générer les prévisions. "
            "Vérifiez que `prophet` est installé : `pip install prophet`"
        )
    else:
        # ── KPIs prévisions ───────────────────────────────────────────────────
        fc_mean = forecast_df["forecast"].mean()
        fc_peak = forecast_df["forecast"].max()
        fc_min  = forecast_df["forecast"].min()
        fc_peak_dt = forecast_df.loc[forecast_df["forecast"].idxmax(), "datetime"]

        # Comparer la moyenne prévue vs la dernière semaine réelle
        last_week_mean = df_full[elec_col].mean() if elec_col else None
        delta_vs_hist = (
            f"{((fc_mean - last_week_mean) / last_week_mean * 100):+.1f}% vs historique"
            if last_week_mean else None
        )

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Consommation prévue moyenne", f"{fc_mean:,.0f} MW", delta=delta_vs_hist, delta_color="inverse")
        k2.metric("Pic prévu", f"{fc_peak:,.0f} MW")
        k3.metric("Minimum prévu", f"{fc_min:,.0f} MW")
        k4.metric("Heure du pic", pd.Timestamp(fc_peak_dt).strftime("%d/%m %Hh"))

        st.markdown("---")

        # ── Graphique principal : historique + prévisions ────────────────────
        st.markdown(f"**Historique récent + prévisions J+{horizon_days}**")

        # Historique = 2× l'horizon pour avoir du contexte proportionnel
        hist_cutoff = df_full["datetime"].max() - pd.Timedelta(days=horizon_days * 2)
        df_hist = df_full[df_full["datetime"] >= hist_cutoff].copy() if elec_col else pd.DataFrame()

        fig = go.Figure()

        # Bande de confiance (remplissage entre lower et upper)
        fig.add_trace(go.Scatter(
            x=pd.concat([forecast_df["datetime"], forecast_df["datetime"].iloc[::-1]]),
            y=pd.concat([forecast_df["upper_bound"], forecast_df["lower_bound"].iloc[::-1]]),
            fill="toself",
            fillcolor="rgba(31, 119, 180, 0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            name="IC 95%",
            showlegend=True,
            hoverinfo="skip",
        ))

        # Courbe de prévision
        fig.add_trace(go.Scatter(
            x=forecast_df["datetime"],
            y=forecast_df["forecast"],
            mode="lines",
            name="Prévision Prophet",
            line=dict(color=COLORS["secondary"], width=2.5, dash="dot"),
        ))

        # Historique réel
        if not df_hist.empty and elec_col:
            fig.add_trace(go.Scatter(
                x=df_hist["datetime"],
                y=df_hist[elec_col],
                mode="lines",
                name="Historique réel",
                line=dict(color=COLORS["primary"], width=1.5),
            ))

        # Ligne verticale "aujourd'hui"
        last_real = df_full["datetime"].max()
        fig.add_vline(
            x=last_real.timestamp() * 1000,
            line=dict(color="#aaa", width=1, dash="dash"),
            annotation_text="Fin données",
            annotation_position="top left",
        )

        fig.update_layout(
            template="plotly_white",
            height=420,
            hovermode="x unified",
            margin=dict(t=20, b=40),
            xaxis_title="Date / Heure",
            yaxis_title="Consommation (MW)",
            legend=dict(orientation="h", y=1.05),
            xaxis=dict(
                rangeselector=dict(buttons=[
                    dict(count=3, label="3j", step="day", stepmode="backward"),
                    dict(count=7, label="7j", step="day", stepmode="backward"),
                    dict(step="all", label="Tout"),
                ]),
            ),
        )
        pchart(fig, key="previsions_prophet")

        # ── Résumé journalier des prévisions ─────────────────────────────────
        st.markdown("**Synthèse journalière des prévisions**")

        forecast_df["date_fc"] = pd.to_datetime(forecast_df["datetime"]).dt.date
        daily_fc = forecast_df.groupby("date_fc").agg(
            moy=("forecast", "mean"),
            pic=("forecast", "max"),
            mini=("forecast", "min"),
            ic_haut=("upper_bound", "mean"),
            ic_bas=("lower_bound", "mean"),
        ).reset_index()

        # Mettre en forme pour l'affichage
        daily_fc_display = daily_fc.copy()
        daily_fc_display.columns = ["Date", "Moy (MW)", "Pic (MW)", "Min (MW)", "IC haut", "IC bas"]
        for col_name in ["Moy (MW)", "Pic (MW)", "Min (MW)", "IC haut", "IC bas"]:
            daily_fc_display[col_name] = daily_fc_display[col_name].round(0).astype(int)

        st.dataframe(daily_fc_display, use_container_width=True, hide_index=True)
        st.download_button(
            label="Télécharger les prévisions (CSV)",
            data=df_to_csv(daily_fc_display),
            file_name=f"previsions_{selected_region}_J{horizon_days}.csv",
            mime="text/csv",
        )

        # ── Profil horaire moyen prévu ────────────────────────────────────────
        st.markdown(f"**Profil horaire moyen prévu (sur {horizon_days} jours)**")

        forecast_df["hour_fc"] = pd.to_datetime(forecast_df["datetime"]).dt.hour
        hourly_fc = forecast_df.groupby("hour_fc").agg(
            moy=("forecast", "mean"),
            ic_haut=("upper_bound", "mean"),
            ic_bas=("lower_bound", "mean"),
        ).reset_index()

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=pd.concat([hourly_fc["hour_fc"], hourly_fc["hour_fc"].iloc[::-1]]),
            y=pd.concat([hourly_fc["ic_haut"], hourly_fc["ic_bas"].iloc[::-1]]),
            fill="toself",
            fillcolor="rgba(255, 127, 14, 0.12)",
            line=dict(color="rgba(255,255,255,0)"),
            name="IC 95%",
            hoverinfo="skip",
        ))
        fig2.add_trace(go.Scatter(
            x=hourly_fc["hour_fc"],
            y=hourly_fc["moy"],
            mode="lines+markers",
            name="Prévision moyenne",
            line=dict(color=COLORS["secondary"], width=3),
            marker=dict(size=6),
        ))
        fig2.update_layout(
            template="plotly_white",
            height=300,
            xaxis_title="Heure",
            yaxis_title="MW",
            xaxis=dict(dtick=2),
            hovermode="x unified",
            margin=dict(t=10, b=40),
            legend=dict(orientation="h", y=1.05),
        )
        pchart(fig2, key="previsions_profil_horaire")

        st.caption(
            f"Modèle Prophet J+{horizon_days} · saisonnalités journalière, hebdomadaire et annuelle. "
            "Les prévisions sont indicatives et dépendent de la quantité d'historique disponible."
        )
