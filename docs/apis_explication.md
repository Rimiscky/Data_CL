# Documentation des APIs — Data_CL Pipeline

Ce document explique ligne par ligne le fonctionnement de chaque client API du projet.

---

## Sommaire

1. [APIClient — Client HTTP de base](#1-apiclient--client-http-de-base)
2. [RTEClient — API RTE OAuth2](#2-rteclient--api-rte-oauth2)
3. [ODREClient — API Open Data Réseaux Énergies](#3-odreclient--api-open-data-réseaux-énergies)
4. [MeteoClient — API Open-Meteo](#4-meteoclient--api-open-meteo)
5. [MeteoFranceClient — API Météo-Concept](#5-meteofrance-client--api-météo-concept)
6. [WebScraper — Scraping HTML](#6-webscraper--scraping-html)
7. [Configuration centralisée (settings.py)](#7-configuration-centralisée-settingspy)
8. [Vue d'ensemble — Comment les APIs s'articulent](#8-vue-densemble--comment-les-apis-sarticulent)

---

## 1. APIClient — Client HTTP de base

**Fichier :** `src/ingestion/api_client.py`

C'est la **classe mère** dont héritent `ODREClient` et `MeteoClient`. Elle centralise la logique commune à tous les appels HTTP : retries, timeouts, logs.

```python
import time
from typing import Any, Optional
import requests
from src.utils.logger import get_logger
```
> Imports : `time` pour les pauses entre retries, `requests` pour les appels HTTP, `get_logger` pour les logs standardisés.

---

### Constructeur `__init__`

```python
def __init__(
    self,
    base_url: str,
    timeout: int = 30,
    max_retries: int = 3,
    retry_delay: int = 2,
):
```
> Paramètres configurables à l'instanciation. Les valeurs par défaut viennent de `settings.py`.

```python
    self.base_url = base_url.rstrip("/")
```
> Supprime le `/` final de l'URL de base pour éviter les doubles slashes lors de la construction d'URL (ex: `https://api.com//endpoint`).

```python
    self.session = requests.Session()
```
> Crée une session HTTP persistante. Une `Session` réutilise les connexions TCP entre les requêtes (keep-alive), ce qui est plus rapide que de créer une connexion à chaque appel.

```python
    self.logger = get_logger(self.__class__.__name__)
```
> Crée un logger nommé d'après la classe concrète (ex: `ODREClient`), pas `APIClient`, ce qui permet de distinguer les logs par client dans les fichiers de log.

---

### Méthode `_build_url`

```python
def _build_url(self, endpoint: str) -> str:
    return f"{self.base_url}/{endpoint.lstrip('/')}"
```
> Construit l'URL complète. `lstrip('/')` supprime un éventuel `/` en début d'endpoint pour que `_build_url("/records")` et `_build_url("records")` donnent le même résultat.

---

### Méthode `get` (avec retry automatique)

```python
def get(self, endpoint: str, params: Optional[dict] = None) -> dict[str, Any]:
```
> Effectue un GET HTTP. `params` est un dictionnaire qui sera encodé automatiquement en query string par `requests` (ex: `{"limit": 10}` → `?limit=10`).

```python
    url = self._build_url(endpoint)
    last_exception = None
```
> Construit l'URL complète et initialise la variable qui stocke la dernière exception pour la relancer à la fin si toutes les tentatives échouent.

```python
    for attempt in range(1, self.max_retries + 1):
```
> Boucle de 1 à `max_retries` inclus (par défaut : 1, 2, 3).

```python
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
```
> `raise_for_status()` lève une `HTTPError` si le code HTTP est 4xx ou 5xx. Sans cela, `requests` retournerait quand même la réponse sans erreur.

```python
        except requests.exceptions.HTTPError as e:
            if response.status_code < 500:
                raise
```
> Les erreurs **4xx** (ex: 401 Unauthorized, 404 Not Found) sont des erreurs **client** : retenter ne changera rien. On lève immédiatement. Les erreurs **5xx** (serveur) peuvent être temporaires, donc on retente.

```python
        if attempt < self.max_retries:
            wait = self.retry_delay * attempt
            time.sleep(wait)
```
> Délai croissant entre les retries : 2s, 4s, 6s. Ce backoff progressif évite de surcharger un serveur déjà en difficulté.

```python
    raise last_exception
```
> Si toutes les tentatives ont échoué, on propage la dernière exception capturée.

---

### Méthodes `close`, `__enter__`, `__exit__`

```python
def close(self):
    self.session.close()
```
> Libère la connexion HTTP. Important en production pour éviter les fuites de ressources.

```python
def __enter__(self):
    return self

def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()
    return False
```
> Implémente le protocole **context manager** pour utiliser la classe avec `with` :
> ```python
> with ODREClient() as client:
>     data = client.fetch_consumption()
> ```
> `return False` signifie que les exceptions ne sont pas supprimées.

---

## 2. RTEClient — API RTE OAuth2

**Fichier :** `src/ingestion/rte_client.py`

Récupère les données de **génération d'électricité en temps réel** par filière (nucléaire, éolien, solaire, hydraulique…) depuis l'API officielle de RTE.

**Authentification :** OAuth2 `client_credentials` (token Bearer).

```python
RTE_TOKEN_URL = "https://digital.iservices.rte-france.com/token/oauth/"
RTE_API_BASE = "https://digital.iservices.rte-france.com/open_api/actual_generation/v1"
PARIS_TZ = ZoneInfo("Europe/Paris")
```
> URLs constantes de l'API RTE et fuseau horaire Paris utilisé pour construire les dates de requête.

---

### Constructeur `__init__`

```python
def __init__(self, oauth_token: str = ""):
    self.oauth_token = oauth_token or os.getenv("RTE_API_KEY", "")
```
> Lit la clé OAuth2 en priorité depuis le paramètre, sinon depuis la variable d'environnement `RTE_API_KEY`. Cette clé est le **token Base64** encodé `client_id:client_secret`.

```python
    self._access_token: Optional[str] = None
    self._token_expiry: Optional[datetime] = None
```
> Cache du token OAuth2. Évite de demander un nouveau token à chaque appel API.

---

### Méthode `_get_access_token`

```python
def _get_access_token(self) -> str:
    if self._access_token and self._token_expiry and datetime.now(timezone.utc) < self._token_expiry:
        return self._access_token
```
> Vérifie si le token en cache est encore valide. Si oui, le retourne directement sans faire de requête réseau.

```python
    response = requests.post(
        RTE_TOKEN_URL,
        headers={
            "Authorization": f"Basic {self.oauth_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},
        timeout=REQUEST_TIMEOUT,
    )
```
> Appel OAuth2 standard. Le header `Authorization: Basic <token_base64>` identifie l'application. `grant_type: client_credentials` indique qu'on s'authentifie en machine-to-machine (pas d'utilisateur).

```python
    self._access_token = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))
    self._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
```
> Stocke le token et sa date d'expiration. On retranche **60 secondes** à la durée de vie pour renouveler avant expiration réelle (marge de sécurité réseau).

---

### Méthode `fetch_actual_generation`

```python
if not self.oauth_token:
    self.logger.warning("RTE_API_KEY non configuré, ingestion RTE ignorée")
    return []
```
> Fail silencieux si la clé n'est pas configurée. Retourne une liste vide pour ne pas bloquer le reste du pipeline.

```python
    def _midnight(d: "date") -> str:
        dt = datetime(d.year, d.month, d.day, tzinfo=PARIS_TZ)
        s = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        return s[:-2] + ":" + s[-2:]
```
> Formate une date en ISO8601 avec fuseau horaire au format `+02:00` (avec les deux-points). L'API RTE **exige** ce format exact ; sans le `:`, elle retourne une erreur 400.

```python
    if end_date is None or start_date is None:
        today = datetime.now(PARIS_TZ).date()
        yesterday = today - timedelta(days=1)
```
> Par défaut, récupère les données de **la veille** (minuit à minuit heure de Paris).

```python
    response = self.session.get(
        f"{RTE_API_BASE}/actual_generations_per_production_type",
        headers={"Authorization": f"Bearer {token}"},
        params={"start_date": start_date, "end_date": end_date},
        timeout=REQUEST_TIMEOUT,
    )
    records = data.get("actual_generations_per_production_type", [])
```
> Appelle l'endpoint RTE et extrait le tableau de génération. La clé `actual_generations_per_production_type` contient une entrée par filière (nucléaire, éolien, etc.), chacune avec ses valeurs horodatées.

---

## 3. ODREClient — API Open Data Réseaux Énergies

**Fichier :** `src/ingestion/odre_client.py`

Hérite de `APIClient`. Récupère les données de **consommation énergétique quotidienne** par région depuis la plateforme open data ODRE.

**URL de base :** `https://odre.opendatasoft.com/api/explore/v2.1`

**Authentification :** Aucune (open data public).

---

### Constructeur `__init__`

```python
def __init__(self, dataset=ODRE_DATASET, region=ODRE_REGION, rows_limit=ODRE_ROWS_LIMIT):
    super().__init__(base_url=ODRE_BASE_URL, timeout=REQUEST_TIMEOUT, ...)
```
> Appelle le constructeur parent (`APIClient`) avec les paramètres ODRE. Par défaut : dataset `consommation-quotidienne-brute-regionale`, région `Île-de-France`, limite 100 lignes.

---

### Méthode `fetch_consumption`

```python
endpoint = f"catalog/datasets/{self.dataset}/records"
params = {
    "where": f'region="{self.region}"',
    "limit": limit or self.rows_limit,
    "offset": offset,
    "order_by": order_by,
}
```
> Construit la requête ODRE. Le filtre `where` utilise la **syntaxe OGC** : la valeur string doit être entre guillemets (`"Île-de-France"`) pour que l'API l'interprète correctement.

```python
    total = data.get("total_count", 0)
    records = data.get("results", [])
```
> L'API ODRE retourne `total_count` (nombre total de résultats disponibles) et `results` (la page courante). Utile pour savoir combien de pages restent.

---

### Méthode `fetch_all_consumption` (pagination automatique)

```python
while offset < max_records:
    batch_size = min(self.rows_limit, max_records - offset)
    data = self.fetch_consumption(limit=batch_size, offset=offset)
    records = data.get("results", [])

    if not records:
        break

    all_records.extend(records)
    offset += len(records)
```
> Boucle de pagination. À chaque itération :
> - `batch_size` : taille de la page (ajustée pour ne pas dépasser `max_records`)
> - `offset += len(records)` : avance du nombre **réel** retourné, pas du `batch_size` (la dernière page peut être partielle)
> - `if not records: break` : stoppe si l'API ne retourne plus rien (fin des données)

---

### Méthode `for_region` (factory)

```python
@classmethod
def for_region(cls, region_key: str, max_records: int = 1000):
    if region_key not in REGION_ODRE_NAMES:
        raise ValueError(f"Région inconnue: {region_key}")
    region_name = REGION_ODRE_NAMES[region_key]
    return cls(region=region_name)
```
> **Méthode de fabrique** : permet de créer un client en utilisant les clés internes du projet (`'idf'`) plutôt que les noms exacts de l'API (`'Île-de-France'`). La table `REGION_ODRE_NAMES` fait la traduction.

---

## 4. MeteoClient — API Open-Meteo

**Fichier :** `src/ingestion/meteo_client.py`

Hérite de `APIClient`. Récupère les données **météo historiques horaires** (température, humidité, vent…) pour une ou plusieurs régions.

**URL de base :** `https://archive-api.open-meteo.com/v1`

**Authentification :** Aucune (gratuit, sans clé API).

---

### Variables météo disponibles

```python
HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "wind_speed_10m",
    "cloud_cover",
    "surface_pressure",
]
```
> Liste des variables horaires demandées par défaut. Ce sont les noms exacts attendus par l'API Open-Meteo.

---

### Constructeur `__init__`

```python
def __init__(self, latitude=IDF_LATITUDE, longitude=IDF_LONGITUDE, region=None):
    ...
    if region and region in REGION_COORDINATES:
        latitude, longitude = REGION_COORDINATES[region]
```
> Par défaut, utilise les coordonnées de Paris (IDF). Si une `region` est fournie, remplace les coordonnées par celles de la région depuis `REGION_COORDINATES`.

---

### Méthode `fetch_weather`

```python
params = {
    "latitude": self.latitude,
    "longitude": self.longitude,
    "start_date": start_date.isoformat(),
    "end_date": end_date.isoformat(),
    "hourly": ",".join(vars_list),
    "timezone": "UTC",
}
data = self.get("archive", params=params)
```
> Appelle l'endpoint `/archive` d'Open-Meteo. Le paramètre `hourly` reçoit les variables séparées par des virgules. Le fuseau `UTC` est **forcé** pour garantir la cohérence lors de la fusion avec les données énergie (qui utilisent aussi UTC).

```python
n_hours = len(data.get("hourly", {}).get("time", []))
```
> Accès **défensif** : si la clé `hourly` ou `time` est absente (réponse partielle), retourne `{}` puis `[]` plutôt que de lever une `KeyError`.

---

### Méthode `fetch_weather_df`

```python
if region and region in REGION_COORDINATES:
    lat, lon = REGION_COORDINATES[region]
    client = MeteoClient(latitude=lat, longitude=lon, region=region)
    data = client.fetch_weather(start_date, end_date, variables)
else:
    data = self.fetch_weather(start_date, end_date, variables)
```
> Si une région différente est demandée, crée un client temporaire avec ses coordonnées plutôt que de modifier l'instance courante.

```python
df = pd.DataFrame(hourly)
df.rename(columns={"time": "datetime"}, inplace=True)
df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
```
> Convertit la réponse JSON en DataFrame pandas. Renomme `time` en `datetime` pour harmoniser avec le schéma commun du pipeline. Force le fuseau UTC sur la colonne datetime.

```python
if region or self.region:
    df["region"] = region or self.region
```
> Ajoute la colonne `region` uniquement si une région est connue. Permet de distinguer les données météo lors d'une fusion multi-régions.

---

## 5. MeteoFranceClient — API Météo-Concept

**Fichier :** `src/ingestion/meteo_france_client.py`

Hérite de `APIClient`. Alternative à Open-Meteo pour des données météo régionales françaises plus précises.

**URL de base :** `https://api.meteo-concept.com/api`

**Authentification :** Clé API (`METEO_FRANCE_API_KEY`).

---

### Méthode `fetch_weather`

```python
if end_date is None:
    end_date = date.today() - timedelta(days=1)
if start_date is None:
    start_date = end_date - timedelta(days=30)
```
> Valeurs par défaut : hier comme date de fin, 30 jours avant comme début.

```python
params = {
    "apikey": self.api_key,
    "lat": latitude,
    "lon": longitude,
    "token": self.api_key,
}
```
> La clé API est envoyée **deux fois** (`apikey` et `token`) car différents endpoints de Météo-Concept acceptent l'un ou l'autre nom de paramètre.

---

### Méthode `fetch_weather_df`

```python
records = data.get("history", []) or data.get("results", [])
```
> Météo-Concept a changé le nom du champ entre versions de l'API. On essaie `history` en premier, puis `results` comme fallback.

```python
column_mapping = {
    "time": "datetime",
    "t": "temperature_2m",
    "rh": "relative_humidity_2m",
    "wind": "wind_speed_10m",
    "precip": "precipitation",
    ...
}
for old_col, new_col in column_mapping.items():
    if old_col in df.columns and new_col not in df.columns:
        df[new_col] = df[old_col]
```
> Normalise les noms de colonnes vers le schéma standard du pipeline. La condition `new_col not in df.columns` évite d'écraser une colonne déjà correctement nommée.

```python
df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
```
> `errors="coerce"` : les dates invalides sont converties en `NaT` (Not a Time) plutôt que de lever une exception — le pipeline continue avec des valeurs manquantes.

---

## 6. WebScraper — Scraping HTML

**Fichier :** `src/ingestion/scraper.py`

Scraper générique pour récupérer des données complémentaires depuis des pages web. Utilisé notamment pour le site RTE éCO2mix.

---

### Constructeur `__init__`

```python
self.session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; DataPipeline/1.0; +https://github.com/projet-data)"
})
```
> Définit un `User-Agent` qui identifie le bot de manière transparente. Évite les erreurs 403 sur les sites qui bloquent les requêtes sans User-Agent.

---

### Méthode `fetch_page`

```python
return BeautifulSoup(response.text, "lxml")
```
> Utilise le parser **lxml** plutôt que `html.parser` : plus rapide et plus tolérant face au HTML malformé (balises non fermées, encodages incorrects).

```python
if attempt == self.max_retries:
    self.logger.error("Échec après %d tentatives pour %s", ...)
    raise
```
> Relève l'exception uniquement à la dernière tentative. Les tentatives intermédiaires logguent un warning mais continuent.

---

### Méthode `extract_tables`

```python
for table in soup.find_all("table"):
    for row in table.find_all("tr"):
        cells = [cell.get_text(strip=True) for cell in row.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
```
> Extrait toutes les tables HTML. `find_all(["th", "td"])` capture à la fois les cellules d'en-tête et de données. `strip=True` supprime les espaces et sauts de ligne parasites autour du texte. Les lignes vides (séparateurs HTML) sont ignorées.

---

### Méthode `extract_links`

```python
for a_tag in soup.find_all("a", href=True):
    href = a_tag["href"]
    if pattern is None or pattern in href:
        links.append({"text": a_tag.get_text(strip=True), "href": href})
```
> `find_all("a", href=True)` garantit que chaque balise a un attribut `href` — l'accès direct `a_tag["href"]` est donc sûr sans vérification supplémentaire.

---

## 7. Configuration centralisée (`settings.py`)

**Fichier :** `config/settings.py`

Toutes les constantes de configuration sont regroupées ici et importées par les clients.

| Constante | Valeur | Usage |
|-----------|--------|-------|
| `ODRE_BASE_URL` | `https://odre.opendatasoft.com/api/explore/v2.1` | Base URL ODRE |
| `ODRE_DATASET` | `consommation-quotidienne-brute-regionale` | Dataset ODRE |
| `ODRE_REGION` | `Île-de-France` | Région par défaut |
| `ODRE_ROWS_LIMIT` | `100` | Taille de page ODRE |
| `RTE_API_KEY` | `os.getenv("RTE_API_KEY")` | Token OAuth2 RTE (secret) |
| `OPENMETEO_BASE_URL` | `https://archive-api.open-meteo.com/v1` | Base URL Open-Meteo |
| `METEO_FRANCE_API_KEY` | `os.getenv("METEO_FRANCE_API_KEY")` | Clé Météo-Concept (secret) |
| `REQUEST_TIMEOUT` | `30` secondes | Timeout HTTP global |
| `MAX_RETRIES` | `3` | Nombre de tentatives |
| `RETRY_DELAY` | `2` secondes | Délai de base entre retries |

### Coordonnées régionales

```python
REGION_COORDINATES = {
    "idf":                (48.8566,  2.3522),  # Paris
    "provence":           (43.5,     5.5),     # Aix-en-Provence
    "bretagne":           (48.1,    -3.3),     # Rennes
    "nouvelle-aquitaine": (46.0,    -0.5),     # Bordeaux
}
```

---

## 8. Vue d'ensemble — Comment les APIs s'articulent

```
                    ┌─────────────────────────────────┐
                    │         APIClient (base)         │
                    │  Session HTTP + Retry + Timeout   │
                    └────────────┬────────────┬────────┘
                                 │            │
                    ┌────────────▼──┐   ┌─────▼──────────────┐
                    │  ODREClient   │   │    MeteoClient      │
                    │ Consommation  │   │  Météo historique   │
                    │ régionale     │   │  (Open-Meteo)       │
                    └───────────────┘   └────────────────────┘
                                               │
                                   ┌───────────▼────────────┐
                                   │   MeteoFranceClient    │
                                   │  Météo-Concept (clé)   │
                                   └────────────────────────┘

    ┌───────────────────────────────────┐
    │           RTEClient               │
    │  Génération électricité (OAuth2)  │
    │  (classe autonome, pas d'héritage)│
    └───────────────────────────────────┘

    ┌───────────────────────────────────┐
    │           WebScraper              │
    │  Scraping HTML (BeautifulSoup)    │
    │  (classe autonome, pas d'héritage)│
    └───────────────────────────────────┘
```

### Flux de données

| Source | Client | Données | Format sortie |
|--------|--------|---------|---------------|
| RTE API | `RTEClient` | Génération par filière (nucléaire, éolien…) | `list[dict]` |
| ODRE | `ODREClient` | Consommation quotidienne par région | `dict` / `list[dict]` |
| Open-Meteo | `MeteoClient` | Météo horaire (temp, humidité, vent…) | `pd.DataFrame` |
| Météo-Concept | `MeteoFranceClient` | Météo régionale française | `pd.DataFrame` |
| HTML web | `WebScraper` | Tables et liens HTML | `list[list]` / `list[dict]` |

### Secrets requis (variables d'environnement)

| Variable | Obligatoire | Usage |
|----------|-------------|-------|
| `RTE_API_KEY` | Oui (si RTE activé) | Token Base64 OAuth2 RTE |
| `METEO_FRANCE_API_KEY` | Oui (si Météo-Concept activé) | Clé API Météo-Concept |

> **Open-Meteo** et **ODRE** ne nécessitent aucune clé.
