"""
config.py
=========
Parámetros centrales del proyecto. Todos los scripts importan este archivo,
de modo que cualquier cambio de años, rutas o fuentes se hace en un solo lugar.

Decisiones metodológicas registradas aquí (validadas por el equipo el 30-sep-2026):
- D1: la segunda entrega cubre datos + limpieza + feature engineering + EDA.
- D2: corte transversal municipal.
      * Target: tasa de deserción PROMEDIO 2022-2024 (años pospandemia).
      * Predictores: promedios 2021-2023 (rezagados un año frente al target
        para mitigar simultaneidad). IPM: único dato municipal, 2018 (censal).
- D3: PAE -> se intenta una fuente municipal; si no existe, se excluye.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas (relativas a la raíz del repositorio -> reproducible en cualquier PC)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "outputs" / "reports"
FIGURES = ROOT / "outputs" / "figures"

for carpeta in (DATA_RAW, DATA_PROCESSED, REPORTS, FIGURES):
    carpeta.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Reproducibilidad
# ---------------------------------------------------------------------------
SEED = 42

# ---------------------------------------------------------------------------
# Ventanas temporales (decisión D2)
# ---------------------------------------------------------------------------
TARGET_YEARS = [2022, 2023, 2024]      # años del target (deserción)
PREDICTOR_YEARS = [2021, 2022, 2023]   # años de los predictores
COCA_PERSISTENCE_YEARS = list(range(2014, 2024))  # 10 años para medir persistencia
TARGET_PERCENTILE = 0.75               # umbral principal de Deserción_Alta
SENSITIVITY_PERCENTILES = [0.80, 0.90] # umbrales de sensibilidad

# ---------------------------------------------------------------------------
# Fuentes de datos
# Portal de datos abiertos: API Socrata (SODA) de datos.gov.co.
# Los identificadores (4x4) se verificaron con los metadatos de cada conjunto.
# ---------------------------------------------------------------------------
SOCRATA_BASE = "https://www.datos.gov.co"

SOCRATA_DATASETS = {
    # nombre_local: (id_socrata, descripción)
    "men_educacion_municipal": (
        "nudc-7mev",
        "MEN - Estadísticas en educación preescolar, básica y media por municipio (2011-2024)",
    ),
    "coca_hectareas_municipal": (
        "acs4-3wgp",
        "MinJusticia/ODC - Detección de cultivos de coca (hectáreas) por municipio (2001-2024)",
    ),
    "municipios_pdet": (
        "idrk-ba8y",
        "ART - Municipios PDET (170 municipios)",
    ),
}

# Víctimas (RUV): base de 36,9 millones de filas -> se descarga AGREGADA
# en el servidor (suma por municipio, año, reporte y sexo).
RUV_DATASET_ID = "m64i-rnss"  # "VICTIMAS POR AÑOS MUNICIPAL" - Unidad para las Víctimas

# PAE: conjunto candidato cuya estructura NO se pudo verificar (decisión D3).
PAE_CANDIDATE_ID = "me9b-uwtw"

# Nombres de los archivos crudos (data/raw) que usan los scripts 03 en adelante
RAW_FILES = {
    "men": "men_educacion_municipal.csv",
    "coca": "coca_hectareas_municipal.csv",
    "ruv": "ruv_victimas_municipio_anio.csv",
    "pdet": "municipios_pdet.csv",
    "ipm": "ipm_municipal_2018.xlsx",
    "poblacion": "poblacion_municipal_area_2018_2042.xlsx",
}

# Archivos Excel del DANE (descarga directa)
DIRECT_FILES = {
    "ipm_municipal_2018.xlsx": (
        "https://www.dane.gov.co/files/investigaciones/condiciones_vida/pobreza/2018/"
        "informacion-censal/anexo-censal-pobreza-municipal-2018.xlsx",
        "DANE - Anexo medida de pobreza multidimensional municipal de fuente censal 2018",
    ),
    "poblacion_municipal_area_2018_2042.xlsx": (
        "https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/"
        "PPED-AreaMun-2018-2042_VP.xlsx",
        "DANE - Serie municipal de población por área 2018-2042 (proyecciones CNPV 2018)",
    ),
}
