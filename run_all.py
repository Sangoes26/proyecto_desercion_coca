"""
run_all.py
==========
Ejecuta todo el proyecto de principio a fin. Uso (desde la raíz del repositorio):

    python run_all.py            # usa las bases ya descargadas en data/raw/
    python run_all.py --descargar  # además intenta descargar lo que falte

1. src/01_carga_datos.py (opcional)        descarga las bases oficiales en data/raw/.
2. notebooks/01_limpieza_union.ipynb       importación, limpieza y unión de las seis fuentes.
3. notebooks/02_variables_eda_kmeans.ipynb construcción de variables, inventario, EDA y K-Means.
4. notebooks/03_modelado.ipynb             asociación (OLS) y modelos predictivos.

Cada notebook se ejecuta completo y se guarda con todas sus salidas.
"""

import subprocess
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent
NOTEBOOKS = ["01_limpieza_union.ipynb", "02_variables_eda_kmeans.ipynb", "03_modelado.ipynb"]

if "--descargar" in sys.argv:
    print(">>> Descarga de las bases (solo lo que falte en data/raw/)")
    if subprocess.run([sys.executable, str(ROOT / "src" / "01_carga_datos.py")], cwd=ROOT).returncode != 0:
        sys.exit("La descarga terminó con error. Revise el mensaje anterior.")

for nombre in NOTEBOOKS:
    ruta = ROOT / "notebooks" / nombre
    print(f">>> Ejecutando {nombre} ...", flush=True)
    inicio = time.time()
    nb = nbformat.read(ruta, as_version=4)
    NotebookClient(nb, timeout=3600, kernel_name="python3",
                   resources={"metadata": {"path": str(ROOT / "notebooks")}}).execute()
    nbformat.write(nb, ruta)
    print(f"    listo en {time.time() - inicio:.0f} s")

print("Proyecto ejecutado correctamente. Resultados en data/processed/, outputs/ y dentro de cada notebook.")
