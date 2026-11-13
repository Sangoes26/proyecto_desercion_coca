"""
01_carga_datos.py
=================
ETAPA 10 - Adquisición de las bases de datos.

Qué hace
    Descarga de forma programática todas las bases oficiales del proyecto y
    las guarda SIN MODIFICAR en data/raw/. También guarda los metadatos
    oficiales de cada conjunto de datos.gov.co (sirven para la ficha técnica).

Por qué se necesita
    La rúbrica (criterio 3) premia la importación programática y reproducible.
    Descargar a mano obligaría a pasos no documentados.

Qué produce
    - data/raw/*.csv / *.xlsx / *_metadata.json
    - outputs/reports/01_log_descargas.csv  (URL, archivo, tamaño, hash,
      fecha de consulta -> trazabilidad de la fuente)

Relación con el objetivo económico
    Sin estas bases no se puede construir el target (deserción) ni los
    predictores (coca, pobreza, conflicto, ruralidad).

Uso
    python src/01_carga_datos.py            # descarga lo que falte
    python src/01_carga_datos.py --force    # vuelve a descargar todo
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime

import pandas as pd
import requests

import config

HEADERS = {"User-Agent": "Proyecto-academico-Externado/1.0 (python-requests)"}
TIMEOUT = 600  # segundos: la agregación del RUV puede tardar en el servidor


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def sha256(path):
    """Huella del archivo: permite verificar que otro usuario tenga los mismos datos."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def get_con_reintentos(url, params=None, intentos=3):
    """GET con reintentos: los portales públicos fallan de forma intermitente."""
    for i in range(1, intentos + 1):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            print(f"   intento {i}/{intentos} falló: {e}")
            if i == intentos:
                raise
            time.sleep(5 * i)


LOG = []


def registrar(nombre, url, destino, descripcion, estado):
    """Agrega una fila al log de descargas (insumo de la ficha técnica)."""
    LOG.append({
        "archivo": destino.name,
        "descripcion": descripcion,
        "url": url,
        "estado": estado,
        "bytes": destino.stat().st_size if destino.exists() else None,
        "sha256": sha256(destino) if destino.exists() else None,
        "fecha_consulta": datetime.now().isoformat(timespec="seconds"),
    })


# ---------------------------------------------------------------------------
# 1. Conjuntos de datos.gov.co (Socrata) descargados completos
# ---------------------------------------------------------------------------
def descargar_socrata_completo(nombre, dataset_id, descripcion, force):
    destino = config.DATA_RAW / f"{nombre}.csv"
    url = f"{config.SOCRATA_BASE}/resource/{dataset_id}.csv"

    # Metadatos oficiales (nombre, fecha de actualización, columnas)
    meta_url = f"{config.SOCRATA_BASE}/api/views/{dataset_id}.json"
    meta_destino = config.DATA_RAW / f"{nombre}_metadata.json"
    if force or not meta_destino.exists():
        try:
            meta_destino.write_bytes(get_con_reintentos(meta_url).content)
        except requests.RequestException:
            print(f"   (no se pudieron descargar metadatos de {dataset_id})")

    if destino.exists() and not force:
        print(f"[omitido] {destino.name} ya existe")
        registrar(nombre, url, destino, descripcion, "existente")
        return

    print(f"[descarga] {descripcion}")
    # $limit alto para traer todas las filas en una sola petición;
    # $order=:id garantiza un orden estable (reproducibilidad).
    r = get_con_reintentos(url, params={"$limit": 100000, "$order": ":id"})
    destino.write_bytes(r.content)
    filas = len(pd.read_csv(destino, dtype=str))
    print(f"   -> {destino.name}: {filas:,} filas")
    registrar(nombre, url, destino, descripcion, "descargado")


# ---------------------------------------------------------------------------
# 2. RUV: agregación en el servidor
# ---------------------------------------------------------------------------
def descargar_ruv(force):
    """
    La base "VICTIMAS POR AÑOS MUNICIPAL" tiene ~37 millones de filas porque
    desagrega por sexo, etnia, discapacidad y ciclo vital. Pedimos al servidor
    que SUME las personas por municipio y año (vigencia).
    """
    destino = config.DATA_RAW / "ruv_victimas_municipio_anio.csv"
    descripcion = "Unidad para las Víctimas - Víctimas por años municipal (agregado)"
    base = f"{config.SOCRATA_BASE}/resource/{config.RUV_DATASET_ID}.json"
    if destino.exists() and not force:
        print(f"[omitido] {destino.name} ya existe")
        registrar("ruv", base, destino, descripcion, "existente")
        return

    meta_destino = config.DATA_RAW / "ruv_victimas_metadata.json"
    if force or not meta_destino.exists():
        try:
            meta_destino.write_bytes(get_con_reintentos(
                f"{config.SOCRATA_BASE}/api/views/{config.RUV_DATASET_ID}.json").content)
        except requests.RequestException:
            pass

    # Muestra cruda de 2.000 filas: permite verificar la estructura real
    muestra = config.DATA_RAW / "ruv_muestra_cruda.csv"
    if force or not muestra.exists():
        r = get_con_reintentos(base.replace(".json", ".csv"), params={"$limit": 2000})
        muestra.write_bytes(r.content)

    # Valores posibles de VIGENCIA (para no suponer su formato)
    r = get_con_reintentos(base, params={"$select": "vigencia, count(*) AS n",
                                         "$group": "vigencia", "$limit": 500})
    vigencias = pd.DataFrame(r.json())
    vigencias.to_csv(config.DATA_RAW / "ruv_vigencias_disponibles.csv", index=False)
    print(f"   vigencias disponibles en RUV: {len(vigencias)}")

    if destino.exists() and not force:
        print(f"[omitido] {destino.name} ya existe")
        registrar("ruv", base, destino, descripcion, "existente")
        return

    # Lección aprendida en la primera ejecución: pedir los tres años juntos y
    # agrupar por varias columnas supera el tiempo límite del servidor. Por eso
    # se consulta UN AÑO a la vez y se agrupa solo por municipio y año (la base
    # trae un único tipo de reporte, así que no hay doble conteo). Cada año se
    # guarda por separado en ruv_por_anio/ para poder retomar si se interrumpe.
    carpeta_anios = config.DATA_RAW / "ruv_por_anio"
    carpeta_anios.mkdir(exist_ok=True)
    print(f"[descarga] {descripcion} - años {config.PREDICTOR_YEARS} (unos 4 min por año)")

    # IMPORTANTE: la base apila una copia COMPLETA de las cifras por cada fecha
    # de corte mensual (31 cortes entre 2024 y 2026). Sumar sin filtrar el corte
    # multiplica las víctimas ~31 veces. Se usa solo el corte más reciente.
    cortes = pd.DataFrame(get_con_reintentos(base, params={
        "$select": "fecha_corte", "$group": "fecha_corte", "$limit": 500}).json())
    fechas = pd.to_datetime(cortes["fecha_corte"], format="mixed", dayfirst=True)
    corte = cortes.loc[fechas.idxmax(), "fecha_corte"]
    print(f"   fecha de corte usada: {corte} (de {len(cortes)} cortes disponibles)")

    partes = []
    for anio in config.PREDICTOR_YEARS:
        archivo_anio = carpeta_anios / f"ruv_{anio}.csv"
        if archivo_anio.exists() and not force:
            partes.append(pd.read_csv(archivo_anio, dtype=str))
            continue
        params = {
            "$select": "cod_ciudad_muni, sum(per_ocu::number) AS per_ocu",
            "$where": f"vigencia='{anio}' AND fecha_corte='{corte}'",
            "$group": "cod_ciudad_muni",
            "$limit": 50000,
        }
        lote = pd.DataFrame(get_con_reintentos(base, params=params).json())
        lote["vigencia"] = anio
        lote["fecha_corte"] = corte
        lote.to_csv(archivo_anio, index=False)
        print(f"   {anio}: {len(lote):,} municipios")
        partes.append(lote)

    df = pd.concat(partes, ignore_index=True)
    if df.empty:
        print("   ATENCIÓN: la consulta no devolvió filas. Revise "
              "data/raw/ruv_vigencias_disponibles.csv (formato de VIGENCIA).")
    df.to_csv(destino, index=False)
    print(f"   -> {destino.name}: {len(df):,} filas")
    registrar("ruv", base, destino, descripcion, "descargado")


# ---------------------------------------------------------------------------
# 3. PAE: verificación de una fuente candidata (decisión D3)
# ---------------------------------------------------------------------------
def explorar_pae(force):
    """No se descarga como insumo del modelo: solo se guardan metadatos y una
    muestra para decidir si existe cobertura PAE a nivel municipal."""
    pid = config.PAE_CANDIDATE_ID
    for sufijo, url, params in [
        ("metadata.json", f"{config.SOCRATA_BASE}/api/views/{pid}.json", None),
        ("muestra.csv", f"{config.SOCRATA_BASE}/resource/{pid}.csv", {"$limit": 2000}),
    ]:
        destino = config.DATA_RAW / f"pae_candidato_{sufijo}"
        if destino.exists() and not force:
            continue
        try:
            destino.write_bytes(get_con_reintentos(url, params=params, intentos=2).content)
            print(f"[PAE] guardado {destino.name}")
        except requests.RequestException as e:
            print(f"[PAE] no disponible ({e}). Se documenta como limitación.")


# ---------------------------------------------------------------------------
# 4. Archivos Excel del DANE
# ---------------------------------------------------------------------------
def descargar_directo(nombre_archivo, url, descripcion, force):
    destino = config.DATA_RAW / nombre_archivo
    if destino.exists() and not force:
        print(f"[omitido] {destino.name} ya existe")
        registrar(nombre_archivo, url, destino, descripcion, "existente")
        return
    print(f"[descarga] {descripcion}")
    destino.write_bytes(get_con_reintentos(url).content)
    print(f"   -> {destino.name}: {destino.stat().st_size / 1e6:.1f} MB")
    registrar(nombre_archivo, url, destino, descripcion, "descargado")


# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Descarga de bases del proyecto")
    parser.add_argument("--force", action="store_true", help="volver a descargar todo")
    args = parser.parse_args()

    errores = []
    tareas = [
        *[(descargar_socrata_completo, (n, i, d, args.force))
          for n, (i, d) in config.SOCRATA_DATASETS.items()],
        (descargar_ruv, (args.force,)),
        *[(descargar_directo, (n, u, d, args.force))
          for n, (u, d) in config.DIRECT_FILES.items()],
        (explorar_pae, (args.force,)),
    ]
    for funcion, argumentos in tareas:
        try:
            funcion(*argumentos)
        except Exception as e:  # se registra y se continúa con las demás bases
            print(f"   ERROR en {funcion.__name__}{argumentos[:1]}: {e}")
            errores.append((funcion.__name__, str(e)))

    pd.DataFrame(LOG).to_csv(config.REPORTS / "01_log_descargas.csv", index=False)
    print(f"\nLog guardado en {config.REPORTS / '01_log_descargas.csv'}")
    if errores:
        print(f"Terminó con {len(errores)} error(es):")
        for f, e in errores:
            print(f" - {f}: {e}")
        sys.exit(1)
    print("Todas las descargas terminaron correctamente.")


if __name__ == "__main__":
    main()
