#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""\
Módulo de análisis tipo "Goal Seek" para LIVO vs RAG.

Para cada pregunta del archivo preguntas_oferta_autogeneradas.txt:
- Obtiene el valor esperado (RAG).
- Genera el SQL base usando LIVOSQLSystem._generar_sql_sin_llm.
- Ejecuta la consulta en DuckDB (SUM(unidades)).
- Registra en un Excel la pregunta, valor esperado, valor obtenido y el SQL usado.

Este es el primer paso: registrar sistemáticamente las discrepancias y las
consultas generadas. Más adelante se pueden añadir variantes de SQL
(hipótesis de negocio) para explorar diferentes configuraciones.
"""

import re
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any

import pandas as pd

from livo_sql import LIVOSQLSystem

# --- Configuración de logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Rutas de archivos
BASE_DIR = Path(__file__).resolve().parent
RAG_FILE_PATH = BASE_DIR / "preguntas_oferta_autogeneradas.txt"
LIVO_PATH = BASE_DIR / "RAG" / "2025" / "Coordenada Urbana" / "LIVO_total_nov25_.xlsx"
PREV_GOAL_SEEK_PATH = BASE_DIR / "goal_seek_resultados.xlsx"


def parse_rag_file(file_path: Path) -> List[Tuple[str, str]]:
    """Parsea el archivo de preguntas y respuestas y devuelve una lista de tuplas (pregunta, respuesta)."""
    qa_pairs: List[Tuple[str, str]] = []
    try:
        with file_path.open("r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        start_index = -1
        for i, line in enumerate(lines):
            if line.startswith("P:"):
                start_index = i
                break

        if start_index != -1:
            for i in range(start_index, len(lines), 2):
                if i + 1 < len(lines) and lines[i].startswith("P:") and lines[i + 1].startswith("R:"):
                    pregunta = lines[i].replace("P: ", "").strip()
                    respuesta_esperada = lines[i + 1].replace("R: ", "").strip()
                    qa_pairs.append((pregunta, respuesta_esperada))
    except FileNotFoundError:
        logger.error(f"El archivo RAG no fue encontrado en: {file_path}")
    return qa_pairs


def extract_value(text: str) -> str:
    """Extrae el primer valor numérico (con puntos como separadores de miles) de un texto."""
    if not text:
        return "N/A"
    match = re.search(r"(\d[\d\.]*)\s*(unidades)?\.", text)
    if not match:
        match = re.search(r"(\d[\d\.]*)", text)
    return match.group(1) if match else "N/A"


def generar_variantes_sql(sql_base: str, sql_prev_best: str = None) -> List[Tuple[str, str]]:
    """Genera variantes del SQL base modificando filtros de cuenta y uso_etapa.

    Devuelve lista de tuplas (variant_id, sql).
    """
    variantes: List[Tuple[str, str]] = []

    # Normalizar espacios para facilitar reemplazos simples
    sql = sql_base

    # Patrones que vamos a tocar (si existen en el SQL base)
    patron_cuenta_oferta = "AND cuenta = 'Oferta'"
    patron_uso_vivienda = "AND uso_etapa IN ('Casa', 'Apartamento')"

    # Opciones para cuenta
    opciones_cuenta = [
        ("cuenta_oferta", patron_cuenta_oferta),
        ("cuenta_oferta_ventas", "AND cuenta IN ('Oferta', 'Ventas')"),
        ("cuenta_sin_filtro", ""),
    ]

    # Opciones para uso_etapa
    opciones_uso = [
        ("uso_vivienda", patron_uso_vivienda),
        ("uso_sin_filtro", ""),
    ]

    # Determinar si los patrones están presentes
    tiene_cuenta = patron_cuenta_oferta in sql
    tiene_uso = patron_uso_vivienda in sql

    # Si no hay ninguno de los patrones, solo devolver la variante base
    if not tiene_cuenta and not tiene_uso:
        return [("base", sql_base)]

    # Generar combinaciones
    for id_cuenta, cuenta_str in opciones_cuenta if tiene_cuenta else [("cuenta_base", patron_cuenta_oferta)]:
        for id_uso, uso_str in opciones_uso if tiene_uso else [("uso_base", patron_uso_vivienda)]:
            sql_var = sql
            if tiene_cuenta:
                sql_var = sql_var.replace(patron_cuenta_oferta, cuenta_str)
            if tiene_uso:
                sql_var = sql_var.replace(patron_uso_vivienda, uso_str)
            variant_id = f"{id_cuenta}|{id_uso}"
            variantes.append((variant_id, sql_var))

    # Eliminar duplicados si los hubiera
    seen = set()
    variantes_unicas: List[Tuple[str, str]] = []
    for vid, s in variantes:
        if s not in seen:
            seen.add(s)
            variantes_unicas.append((vid, s))

    # Añadir variante previa "prev_best" si se proporciona y no está ya presente
    if sql_prev_best:
        if sql_prev_best not in seen:
            variantes_unicas.append(("prev_best", sql_prev_best))

    return variantes_unicas


def main():
    # 1. Inicializar LIVO
    logger.info(f"Usando archivo LIVO: {LIVO_PATH}")
    livo_system = LIVOSQLSystem(str(LIVO_PATH))
    exito, msg = livo_system.inicializar()
    if not exito:
        logger.error(f"No se pudo inicializar LIVO SQL: {msg}")
        return

    # 2. Cargar preguntas RAG
    qa_pairs = parse_rag_file(RAG_FILE_PATH)
    if not qa_pairs:
        logger.error("No se encontraron pares P/R en el archivo RAG.")
        return

    # 3. Cargar resultados previos (para reentrenamiento) si existen
    prev_best_by_question: Dict[str, Dict[str, Any]] = {}
    if PREV_GOAL_SEEK_PATH.exists():
        try:
            df_prev = pd.read_excel(PREV_GOAL_SEEK_PATH)
            # Normalizar nombres esperados en caso de que falten
            if "mejor_para_pregunta" in df_prev.columns:
                for pregunta_val, group in df_prev.groupby("pregunta"):
                    # Preferir las filas marcadas como mejor_para_pregunta
                    candidatos = group[group.get("mejor_para_pregunta", False) == True]
                    if candidatos.empty:
                        # Si no hay marcadas, tomar la de menor diferencia_abs que no sea None
                        if "diferencia_abs" in group.columns:
                            group_valid = group.dropna(subset=["diferencia_abs"])
                            if not group_valid.empty:
                                min_diff = group_valid["diferencia_abs"].min()
                                candidatos = group_valid[group_valid["diferencia_abs"] == min_diff]
                        if candidatos.empty:
                            candidatos = group
                    # Tomar la primera candidata como mejor previa
                    best_row = candidatos.iloc[0]
                    prev_best_by_question[str(pregunta_val)] = {
                        "sql": best_row.get("sql"),
                        "valor_obtenido_livo": best_row.get("valor_obtenido_livo"),
                        "diferencia_abs": best_row.get("diferencia_abs"),
                    }
            logger.info(f"Reentrenamiento: se cargaron mejores variantes previas para {len(prev_best_by_question)} preguntas.")
        except Exception as e:
            logger.warning(f"No se pudo leer el Excel previo de Goal Seek: {e}")

    logger.info(f"Iniciando Goal Seek para {len(qa_pairs)} preguntas...")

    registros = []

    for idx, (pregunta, resp_rag) in enumerate(qa_pairs, start=1):
        valor_esperado = extract_value(resp_rag)

        prev_info = prev_best_by_question.get(pregunta, {})
        prev_sql = prev_info.get("sql")
        prev_val = prev_info.get("valor_obtenido_livo")
        prev_diff = prev_info.get("diferencia_abs")

        # Usamos directamente el motor de reglas para obtener el SQL base
        sql_base = livo_system._generar_sql_sin_llm(pregunta)  # uso interno y controlado

        if not sql_base:
            registros.append(
                {
                    "indice": idx,
                    "pregunta": pregunta,
                    "valor_esperado_rag": valor_esperado,
                    "valor_obtenido_livo": "N/A",
                    "coincide": False,
                    "variant_id": "sin_sql",
                    "sql": None,
                    "nota": "No se pudo generar SQL con _generar_sql_sin_llm",
                    "prev_valor_obtenido_livo": prev_val,
                    "prev_diferencia_abs": prev_diff,
                    "prev_sql": prev_sql,
                }
            )
            continue

        variantes_sql = generar_variantes_sql(sql_base, sql_prev_best=prev_sql)

        for variant_id, sql in variantes_sql:
            try:
                result = livo_system.conn.execute(sql).fetchall()

                # Manejo explícito de casos sin filas o SUM NULL → registrar 0
                if not result:
                    valor_obtenido = 0
                elif len(result) == 1 and len(result[0]) >= 1:
                    valor_obtenido = result[0][0] if result[0][0] is not None else 0
                else:
                    valor_obtenido = None

                coincide = False
                try:
                    if valor_obtenido is not None and valor_esperado not in ("N/A", None, ""):
                        # Normalizar puntos de miles
                        esperado_num = int(str(valor_esperado).replace(".", ""))
                        obtenido_num = int(valor_obtenido)
                        coincide = esperado_num == obtenido_num
                except Exception:
                    pass

                registros.append(
                    {
                        "indice": idx,
                        "pregunta": pregunta,
                        "valor_esperado_rag": valor_esperado,
                        "valor_obtenido_livo": valor_obtenido,
                        "coincide": coincide,
                        "variant_id": variant_id,
                        "sql": sql,
                        "nota": "",
                        "prev_valor_obtenido_livo": prev_val,
                        "prev_diferencia_abs": prev_diff,
                        "prev_sql": prev_sql,
                    }
                )
            except Exception as e:
                registros.append(
                    {
                        "indice": idx,
                        "pregunta": pregunta,
                        "valor_esperado_rag": valor_esperado,
                        "valor_obtenido_livo": "ERROR",
                        "coincide": False,
                        "variant_id": variant_id,
                        "sql": sql,
                        "nota": f"Error ejecutando SQL: {e}",
                        "prev_valor_obtenido_livo": prev_val,
                        "prev_diferencia_abs": prev_diff,
                        "prev_sql": prev_sql,
                    }
                )

    # 3. Construir DataFrame y marcar mejor variante por pregunta
    df = pd.DataFrame(registros)

    # Normalizar valores numéricos para calcular diferencias
    def _to_int_safe(x):
        try:
            if x is None or x == "N/A" or x == "ERROR":
                return None
            return int(str(x).replace(".", ""))
        except Exception:
            return None

    df["esperado_num"] = df["valor_esperado_rag"].apply(_to_int_safe)
    df["obtenido_num"] = df["valor_obtenido_livo"].apply(_to_int_safe)

    def _calc_diff(row):
        if row["esperado_num"] is None or row["obtenido_num"] is None:
            return None
        return abs(row["esperado_num"] - row["obtenido_num"])

    df["diferencia_abs"] = df.apply(_calc_diff, axis=1)

    # Inicializar columna de mejor variante
    df["mejor_para_pregunta"] = False

    # Para cada pregunta (indice), marcar mejor variante
    for idx_val, group in df.groupby("indice"):
        # 1) Preferir coincidencia exacta
        exactos = group[group["coincide"] == True]
        if not exactos.empty:
            # Marcar todos los exactos como mejores (pueden ser varias variantes que coinciden)
            df.loc[exactos.index, "mejor_para_pregunta"] = True
            continue

        # 2) Si no hay exacto, elegir la de menor diferencia_abs (ignorando None)
        group_valid = group.dropna(subset=["diferencia_abs"])
        if not group_valid.empty:
            min_diff = group_valid["diferencia_abs"].min()
            mejores = group_valid[group_valid["diferencia_abs"] == min_diff]
            df.loc[mejores.index, "mejor_para_pregunta"] = True

    # 4. Exportar a Excel
    output_path = BASE_DIR / "goal_seek_resultados.xlsx"
    df.to_excel(output_path, index=False)
    logger.info(f"Archivo de resultados de Goal Seek generado en: {output_path}")


if __name__ == "__main__":
    main()
