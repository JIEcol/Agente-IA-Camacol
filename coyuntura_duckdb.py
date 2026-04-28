#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Carga y normalización de Tablas de Coyuntura en DuckDB

Objetivo:
- Leer los archivos Excel de tablas de coyuntura (unidades, área, netas, valor ventas)
- Normalizar el formato especial (cabeceras en filas 5–6, datos desde fila 7)
- Guardar todo en una tabla única de DuckDB para poder hacer consultas tipo LIVO

Esquema de la tabla `coyuntura` en DuckDB:
- periodo       (VARCHAR)   -> texto como 'ene-10', 'oct-25'
- departamento (VARCHAR)   -> nombre del departamento (Antioquia, Valle, etc.)
- caracteristica (VARCHAR) -> 'VIP', 'VIS (sin VIP)', '> VIS y hasta 500 smml', 'Mayor a 500 smml', 'VIS', 'NO VIS', 'TOTAL', etc.
- valor        (DOUBLE)    -> número de unidades / área / netas / valor, según archivo
- hoja         (VARCHAR)   -> nombre de la hoja: 'Lanzamientos', 'Iniciaciones', 'Ventas', 'Oferta'
- tipo_fuente  (VARCHAR)   -> 'unidades', 'area', 'netas', 'valor_ventas'

Con esto tendrás una sola tabla `coyuntura` donde puedes hacer consultas tipo:

SELECT valor
FROM coyuntura
WHERE tipo_fuente = 'unidades'
  AND hoja = 'Oferta'
  AND departamento = 'Antioquia'
  AND caracteristica = 'TOTAL'
  AND periodo = 'oct-25';

que para tu ejemplo debe devolver 20816.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import duckdb
import pandas as pd
import re

# Rutas de los archivos de tablas de coyuntura (ajusta si cambian)
BASE_FOLDER = Path(
    r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\Coordenada Urbana"
)

COYUNTURA_FILES: Dict[str, Path] = {
    # Número de unidades
    "unidades": BASE_FOLDER / "Tablas_de_Coyuntura_oct25.xlsx",
    # Área de las construcciones
    "area": BASE_FOLDER / "Tablas de Coyuntura_oct25_Área.xlsx",
    # Netas
    "netas": BASE_FOLDER / "Tablas de Coyuntura_oct25_Netas.xlsx",
    # Riesgo (indicadores de riesgo de inventario, rotación, etc.)
    "riesgo": BASE_FOLDER / "Tablas de Coyuntura_oct25_Riesgo.xlsx",
    # Valor de ventas
    "valor_ventas": BASE_FOLDER / "Tablas de Coyuntura_oct25_Valor Ventas.xlsx",
}

# Hojas de interés en cada archivo
# Nota: algunas hojas adicionales (UTV, UTV %, Rotación de Inventarios) solo existen en el archivo de Riesgo,
# y las hojas de valor ventas corrientes/constantes solo en el archivo de Valor Ventas.
HOJAS_INTERES: List[str] = [
    "Lanzamientos",
    "Iniciaciones",
    "Ventas",
    "Oferta",
    "UTV",
    "UTV %",
    "Rotación de Inventarios",
    "Valor ventas corrientes",
    "Valor ventas constantes",
]

# Ruta por defecto de la base DuckDB donde se guardará la tabla `coyuntura`
DEFAULT_DUCKDB_PATH = BASE_FOLDER / "coyuntura.duckdb"


def _normalizar_hoja(
    df: pd.DataFrame,
    sheet_name: str,
    tipo_fuente: str,
) -> pd.DataFrame:
    """Convierte el DataFrame crudo (cabeceras en filas 5–6) a formato largo.

    Se asume que el DataFrame ya se leyó con `header=[4, 5]` para usar filas 5 y 6
    como multi-índice de columnas.
    """

    # Asegurarse de que tenemos MultiIndex en columnas
    if not isinstance(df.columns, pd.MultiIndex):
        raise ValueError(
            f"La hoja '{sheet_name}' no tiene columnas MultiIndex. "
            "Verifica que se leyó con header=[4, 5]."
        )

    # Normalizar nombre de la primera columna (periodo)
    # En muchos archivos será algo como ('Ubicación', 'Periodo') o ('Ubicación', 'Fecha')
    # Identificamos la columna cuyo segundo nivel contenga 'Periodo' o 'Fecha'
    periodo_col = None
    for col in df.columns:
        top, bottom = col
        if isinstance(bottom, str):
            bottom_low = bottom.lower()
            if "period" in bottom_low or "fecha" in bottom_low:
                periodo_col = col
                break
    if periodo_col is None:
        # Fallback: usar la primera columna
        periodo_col = df.columns[0]

    # Renombrar columna de periodo a un nombre simple si es posible
    df = df.rename(columns={periodo_col: ("Periodo", "Periodo")})

    # Determinar realmente cómo se llama la columna de periodo después del rename
    if ("Periodo", "Periodo") in df.columns:
        periodo_key = ("Periodo", "Periodo")
    else:
        # Fallback de seguridad: usar el label original
        periodo_key = periodo_col

    # Eliminar filas totalmente vacías
    df = df.dropna(how="all")

    # Lista de DataFrames en formato largo por cada combinación departamento/característica
    registros: List[pd.DataFrame] = []

    for col in df.columns:
        top, bottom = col

        # Saltar la columna de periodo (usando la clave detectada)
        if col == periodo_key:
            continue

        # Algunas columnas pueden estar vacías o ser totales sin departamento
        if pd.isna(top):
            continue

        # Construir sub-DataFrame usando la clave de periodo correcta
        sub = df[[periodo_key, col]].copy()
        sub.columns = ["periodo", "valor"]

        sub["departamento"] = str(top).strip()
        sub["caracteristica"] = str(bottom).strip()
        sub["hoja"] = sheet_name
        sub["tipo_fuente"] = tipo_fuente

        registros.append(sub)

    if not registros:
        return pd.DataFrame(
            columns=[
                "periodo",
                "departamento",
                "caracteristica",
                "valor",
                "hoja",
                "tipo_fuente",
            ]
        )

    df_long = pd.concat(registros, ignore_index=True)

    # Limpiar valores obvios
    df_long["periodo"] = df_long["periodo"].astype(str).str.strip()

    # Intentar convertir 'valor' a numérico (coercion a NaN si hay texto)
    df_long["valor"] = pd.to_numeric(df_long["valor"], errors="coerce")

    # Eliminar filas sin valor numérico
    df_long = df_long.dropna(subset=["valor"])

    return df_long[
        [
            "periodo",
            "departamento",
            "caracteristica",
            "valor",
            "hoja",
            "tipo_fuente",
        ]
    ]


def cargar_tablas_coyuntura_en_duckdb(
    duckdb_path: Path | str | None = None,
    sobrescribir_tabla: bool = False,
) -> None:
    """Carga todas las tablas de coyuntura en una tabla única `coyuntura` de DuckDB.

    - Lee los 4 archivos definidos en COYUNTURA_FILES.
    - Procesa solo las hojas en HOJAS_INTERES.
    - Normaliza el formato y concatena todo en un DataFrame largo.
    - Inserta en la tabla `coyuntura` de DuckDB.
    """

    db_path = Path(duckdb_path) if duckdb_path is not None else DEFAULT_DUCKDB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n🚀 Cargando tablas de coyuntura en DuckDB: {db_path}")

    tablas: List[pd.DataFrame] = []

    for tipo_fuente, file_path in COYUNTURA_FILES.items():
        if not file_path.exists():
            print(f"⚠️ Archivo no encontrado para {tipo_fuente}: {file_path}")
            continue

        print(f"📄 Procesando archivo [{tipo_fuente}]: {file_path.name}")

        xls = pd.ExcelFile(file_path)

        for sheet_name in HOJAS_INTERES:
            if sheet_name not in xls.sheet_names:
                print(f"  ⚠️ Hoja no encontrada, se omite: {sheet_name}")
                continue

            print(f"  ➜ Hoja: {sheet_name}")

            # Leer usando filas 5 y 6 como cabeceras (índices 4 y 5)
            df_raw = pd.read_excel(
                xls,
                sheet_name=sheet_name,
                header=[4, 5],
                dtype=object,
            )

            df_long = _normalizar_hoja(df_raw, sheet_name=sheet_name, tipo_fuente=tipo_fuente)

            print(
                f"    ✓ Filas normalizadas: {len(df_long)} (periodos únicos: {df_long['periodo'].nunique()})"
            )

            tablas.append(df_long)

    if not tablas:
        print("❌ No se generaron datos de coyuntura. Revisa rutas y hojas.")
        return

    df_coyuntura = pd.concat(tablas, ignore_index=True)

    # Crear agregados nacionales (Total 19 Regionales) para unidades en Oferta
    try:
        mask_unidades_oferta = (
            (df_coyuntura["tipo_fuente"].str.lower() == "unidades")
            & (df_coyuntura["hoja"].str.lower() == "oferta")
        )

        df_unid_oferta = df_coyuntura[mask_unidades_oferta].copy()

        if not df_unid_oferta.empty:
            # Excluir cualquier fila existente de Total 19 Regionales en unidades/oferta
            df_unid_oferta = df_unid_oferta[
                df_unid_oferta["departamento"].str.lower() != "total 19 regionales"
            ]

            df_agg_total = (
                df_unid_oferta
                .groupby(["periodo", "caracteristica", "hoja", "tipo_fuente"], as_index=False)[
                    "valor"
                ]
                .sum()
            )
            df_agg_total["departamento"] = "Total 19 Regionales"

            # Alinear columnas y concatenar
            df_agg_total = df_agg_total[
                [
                    "periodo",
                    "departamento",
                    "caracteristica",
                    "valor",
                    "hoja",
                    "tipo_fuente",
                ]
            ]

            df_coyuntura = pd.concat([df_coyuntura, df_agg_total], ignore_index=True)
            print(
                f"  ➕ Agregados nacionales (Total 19 Regionales) creados para unidades/oferta: {len(df_agg_total)} filas"
            )
    except Exception as e:
        print(f"  ⚠️ No se pudieron crear agregados nacionales para unidades/oferta: {e}")

    print(
        f"\n✅ Total filas de coyuntura normalizadas: {len(df_coyuntura)} "
        f"(periodos: {df_coyuntura['periodo'].nunique()}, departamentos: {df_coyuntura['departamento'].nunique()})"
    )

    # Conectar / crear base DuckDB
    conn = duckdb.connect(str(db_path), read_only=False)

    # Crear/limpiar tabla destino
    if sobrescribir_tabla:
        conn.execute("DROP TABLE IF EXISTS coyuntura")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS coyuntura (
            periodo       VARCHAR,
            departamento  VARCHAR,
            caracteristica VARCHAR,
            valor         DOUBLE,
            hoja          VARCHAR,
            tipo_fuente   VARCHAR
        )
        """
    )

    # Registrar DataFrame y hacer INSERT
    conn.register("df_coyuntura", df_coyuntura)

    conn.execute(
        """
        INSERT INTO coyuntura
        SELECT periodo, departamento, caracteristica, valor, hoja, tipo_fuente
        FROM df_coyuntura
        """
    )

    filas_tabla = conn.execute("SELECT COUNT(*) FROM coyuntura").fetchone()[0]
    print(f"✅ Tabla 'coyuntura' actualizada. Filas totales en DuckDB: {filas_tabla}")

    conn.close()


if __name__ == "__main__":
    # Ejecución directa para pruebas manuales
    cargar_tablas_coyuntura_en_duckdb(sobrescribir_tabla=True)
