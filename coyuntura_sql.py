#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo de consultas SQL sobre tablas de coyuntura usando DuckDB.

Usa la base generada por `coyuntura_duckdb.py` (coyuntura.duckdb) y permite
consultar directamente valores por:

- tipo_fuente  (unidades, area, netas, riesgo, valor_ventas)
- hoja         (Lanzamientos, Iniciaciones, Ventas, Oferta, UTV, ...)
- departamento (Antioquia, Valle, etc.)
- caracteristica (VIP, VIS, NO VIS, TOTAL, etc.)
- periodo      (texto tal como quedó en DuckDB, por ejemplo 'oct-25')
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Any
from datetime import datetime

import duckdb
import pandas as pd


@dataclass
class CoyunturaConfig:
    """Configuración básica para el sistema de coyuntura."""

    # Ruta a la base DuckDB generada por coyuntura_duckdb.py
    db_path: Path = Path(
        r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\Coordenada Urbana\coyuntura.duckdb"
    )


class CoyunturaSQLSystem:
    """Sistema de consultas sobre la tabla `coyuntura` en DuckDB."""

    def __init__(self, config: Optional[CoyunturaConfig] = None) -> None:
        self.config = config or CoyunturaConfig()
        self.conn: Optional[duckdb.DuckDBPyConnection] = None

    def inicializar(self) -> Tuple[bool, str]:
        """Abre la conexión a DuckDB y valida que exista la tabla `coyuntura`."""

        try:
            if not self.config.db_path.exists():
                return False, f"❌ No se encontró la base de datos de coyuntura: {self.config.db_path}"

            self.conn = duckdb.connect(str(self.config.db_path), read_only=True)

            tablas = self.conn.execute("SHOW TABLES").fetchall()
            if not any("coyuntura" in t for t in tablas):
                return False, "❌ La base DuckDB no contiene la tabla `coyuntura`. Ejecuta primero coyuntura_duckdb.py"

            filas = self.conn.execute("SELECT COUNT(*) FROM coyuntura").fetchone()[0]
            return True, f"✅ Coyuntura cargada: {filas:,} registros"

        except Exception as e:  # pragma: no cover - logging simple
            return False, f"❌ Error inicializando CoyunturaSQLSystem: {e}"

    def cerrar(self) -> None:
        """Cierra la conexión a DuckDB si está abierta."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def consultar_valor(
        self,
        tipo_fuente: str,
        hoja: str,
        departamento: str,
        caracteristica: str,
        periodo_clave: str,
        periodo_texto: Optional[str] = None,
    ) -> tuple[bool, str, Optional[Any]]:
        """Consulta un valor puntual en la tabla `coyuntura`.
        
        Devuelve (exito, mensaje, valor).
        """
        if self.conn is None:
            ok, msg = self.inicializar()
            if not ok:
                return False, f"Error al conectar con la base de datos: {msg}", None

        try:
            # 1. Intentar con periodo_clave (YYYY-MM) usando lógica robusta de fechas
            if periodo_clave:
                try:
                    p_year, p_month = map(int, periodo_clave.split('-'))
                except ValueError:
                    p_year, p_month = None, None

                query_clave = """
                    SELECT valor, periodo
                    FROM coyuntura
                    WHERE lower(trim(tipo_fuente)) = lower(trim(?))
                      AND lower(trim(hoja)) = lower(trim(?))
                      AND lower(trim(departamento)) = lower(trim(?))
                      AND lower(trim(caracteristica)) = lower(trim(?))
                      AND (
                          CAST(periodo AS VARCHAR) LIKE ?
                          OR (
                              ? IS NOT NULL AND ? IS NOT NULL
                              AND TRY_CAST(periodo AS DATE) IS NOT NULL 
                              AND YEAR(TRY_CAST(periodo AS DATE)) = ? 
                              AND MONTH(TRY_CAST(periodo AS DATE)) = ?
                          )
                      )
                """
                params_clave = [
                    tipo_fuente, hoja, departamento, caracteristica, 
                    f"{periodo_clave}%", 
                    p_year, p_month, p_year, p_month
                ]
                result = self.conn.execute(query_clave, params_clave).fetchall()
                
                if result:
                    periodo_encontrado = result[0][1]
                    return True, f"✅ Valor encontrado para {periodo_encontrado}", result[0][0]

            # 2. Intentamos con búsqueda exacta usando periodo_texto (ej: 'sep-25')
            if periodo_texto:
                query = """
                    SELECT valor, periodo
                    FROM coyuntura
                    WHERE lower(trim(tipo_fuente)) = lower(trim(?))
                      AND lower(trim(hoja)) = lower(trim(?))
                      AND lower(trim(departamento)) = lower(trim(?))
                      AND lower(trim(caracteristica)) = lower(trim(?))
                      AND lower(trim(periodo)) = lower(trim(?))
                """
                params = [tipo_fuente, hoja, departamento, caracteristica, periodo_texto]
                result = self.conn.execute(query, params).fetchall()
                
                if result:
                    return True, f"✅ Valor encontrado para {periodo_texto}", result[0][0]

            # 3. Si no hay coincidencia exacta, intentamos con búsqueda flexible
            if periodo_texto:
                # Primero intentamos con el formato 'sep-25' o similar
                query_flex = """
                    SELECT valor, periodo
                    FROM coyuntura
                    WHERE lower(trim(tipo_fuente)) = lower(trim(?))
                      AND lower(trim(hoja)) = lower(trim(?))
                      AND lower(trim(departamento)) = lower(trim(?))
                      AND lower(trim(caracteristica)) = lower(trim(?))
                      AND (lower(trim(periodo)) LIKE lower(?) 
                           OR lower(trim(periodo)) LIKE lower(?))
                    ORDER BY periodo DESC
                    LIMIT 1
                """
                # Intentamos con formato 'sep-25' y 'sept-25'
                mes_abrev = periodo_texto.split('-')[0][:3]  # 'sep' de 'sep-25'
                params_flex = [
                    tipo_fuente, hoja, departamento, caracteristica,
                    f"{mes_abrev}%",  # sep%
                    f"{mes_abrev}%"   # sept%
                ]
                result = self.conn.execute(query_flex, params_flex).fetchall()
                
                if result:
                    periodo_encontrado = result[0][1]
                    return True, f"✅ Valor encontrado para {periodo_encontrado}", result[0][0]

            # Si aún no hay resultados, mostramos los períodos disponibles para diagnóstico
            try:
                diag_query = """
                    SELECT DISTINCT periodo, tipo_fuente, hoja, departamento, caracteristica
                    FROM coyuntura
                    WHERE lower(trim(departamento)) LIKE lower(?)
                      AND lower(trim(hoja)) LIKE lower(?)
                      AND lower(trim(caracteristica)) LIKE lower(?)
                    ORDER BY periodo DESC
                    LIMIT 20
                """
                diag_params = [f"%{departamento}%", f"%{hoja}%", f"%{caracteristica}%"]
                diag_rows = self.conn.execute(diag_query, diag_params).fetchall()
                if diag_rows:
                    print(f"\\n[DIAGNOSTICO] Registros disponibles (últimos 20):")
                    for row in diag_rows:
                        print(f"  - {row[1]}/{row[2]}/{row[3]}/{row[4]}: {row[0]}")
            except Exception as e:
                print(f"[ERROR DIAGNOSTICO] {str(e)}")

            return False, "⚠️ No se encontró un registro que coincida con los filtros.", None
            
        except Exception as e:
            return False, f"❌ Error ejecutando la consulta: {str(e)}", None

def _leer_oferta_desde_excel(
    departamento: str, caracteristica: str, pregunta_norm: str
) -> Tuple[bool, Optional[float], str]:
    """Lee directamente del Excel de unidades la oferta por departamento.

    Usa los bloques de 7 columnas a partir de B (Antioquia) en la hoja Oferta.
    Solo pensado para filas de resumen (oct-24, oct-25, Año corrido oct-25).
    """

    try:
        base_folder = Path(
            r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\Coordenada Urbana"
        )
        excel_path = base_folder / "Tablas_de_Coyuntura_nov25.xlsx"

        # Determinar fila según el periodo mencionado
        pregunta_l = pregunta_norm
        if "2024" in pregunta_l:
            row = 198
            periodo_legible = "oct-24"
        elif "2025" in pregunta_l and ("octubre" in pregunta_l or "oct" in pregunta_l):
            row = 196
            periodo_legible = "oct-25"
        else:
            # Por defecto: año corrido oct-25
            row = 203
            periodo_legible = "Año corrido oct-25"
        # Mapeo de departamentos en bloques de 7 columnas desde la columna B (índice 1)
        deptos_excel = [
            "Antioquia",
            "Atlántico",
            "Bogotá & Cundinamarca",
            "Bolívar",
            "Boyacá",
            "Caldas",
            "Huila",
            "Nariño",
            "Norte de Santander",
            "Risaralda",
            "Santander",
            "Tolima",
            "Valle",
            "Cesar",
            "Meta",
            "Córdoba & Sucre",
            "Magdalena",
            "Quindío",
            "Cauca",
            "5 Regionales",
            "13 Regionales",
            "18 Regionales",
            "19 Regionales",
        ]

        # Buscar índice de bloque por comparación normalizada
        dep_norm = _normalizar_texto(departamento)
        block_index = None
        for i, dep_excel in enumerate(deptos_excel):
            if _normalizar_texto(dep_excel) == dep_norm:
                block_index = i
                break
        if block_index is None:
            return False, None, ""

        # Elegir offset de característica dentro del bloque (7 columnas)
        car = caracteristica.upper().strip()
        if car == "VIP":
            offset = 0
        elif car == "VIS (SIN VIP)":
            offset = 1
        elif car.startswith("> VIS"):
            offset = 2
        elif car.startswith("MAYOR A 500"):
            offset = 3
        elif car == "VIS":
            offset = 4
        elif car == "NO VIS":
            offset = 5
        else:
            # TOTAL u otras variantes
            offset = 6

        base_col = 1 + block_index * 7
        col_idx = base_col + offset

        # Intentar leer con engine openpyxl para evitar problemas de permisos
        df = pd.read_excel(excel_path, sheet_name="Oferta", header=None, dtype=object, engine='openpyxl')
        v = df.iat[row - 1, col_idx]
        print(f"[DEBUG EXCEL] Leyendo fila {row}, columna {col_idx} (departamento={departamento}, caracteristica={caracteristica})")
        print(f"[DEBUG EXCEL] Valor leído: '{v}' (tipo: {type(v)})")
        valor = float(str(v).replace(",", ""))
        print(f"[DEBUG EXCEL] Valor convertido: {valor}")
        return True, valor, periodo_legible
    except Exception as e:
        if "Permission denied" in str(e) or "being used by another process" in str(e):
             print(f"[DEBUG EXCEL] ⚠️ El archivo Excel está abierto o bloqueado. Usando solo base de datos DuckDB.")
        else:
             print(f"[DEBUG EXCEL] ERROR leyendo Excel directo: {e}")
        return False, None, ""

def _normalizar_texto(texto: str) -> str:
    """Texto minúsculas y sin tildes para comparaciones simples."""
    texto = texto.lower()
    texto = (
        texto.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )
    return texto

def _extraer_periodos(texto: str) -> list[tuple[Optional[str], Optional[str]]]:
    """Extrae TODOS los períodos encontrados en el texto."""
    import re
    
    # Mapeo de nombres de meses a números
    meses = {
        'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04', 'may': '05', 'jun': '06',
        'jul': '07', 'ago': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12'
    }
    
    # Buscar patrones como 'sep 25', 'septiembre 2025', 'sep-25', 'septiembre del 2025', etc.
    patrones = [
        (r'(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)[a-z]*[\s-]*(\d{2,4})', 1, 2),  # sep-25 o sep 25
        (r'(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)(?:\s+del?)?\s+(\d{4})', 1, 2),  # septiembre 2025 o septiembre del 2025
        (r'(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)[\s-]*(?:de\s*)?(\d{4})', 1, 2)  # compatibilidad con formato anterior
    ]
    
    matches_encontrados = []
    for patron, grupo_mes, grupo_anio in patrones:
        for match in re.finditer(patron, texto, re.IGNORECASE):
            matches_encontrados.append((match, grupo_mes, grupo_anio))
    
    # Ordenar por posición en el texto para mantener el orden lógico
    matches_encontrados.sort(key=lambda x: x[0].start())
    
    resultados = []
    spans_usados = []
    
    for match, grupo_mes, grupo_anio in matches_encontrados:
        start, end = match.span()
        # Evitar duplicados si un patrón captura lo mismo que otro (solapamiento)
        if any(s <= start < e or s < end <= e for s, e in spans_usados):
            continue
            
        try:
            mes_str = match.group(grupo_mes)[:3].lower()  # Toma solo las primeras 3 letras
            anio_str = match.group(grupo_anio)
            
            # Asegurar que el año tenga 2 dígitos
            if len(anio_str) == 4:
                anio_2d = anio_str[2:]
            else:
                anio_2d = anio_str.zfill(2)
            
            # Formatear periodo_texto como 'sep-25'
            periodo_texto = f"{mes_str}-{anio_2d}"
            
            # Formatear periodo_clave como '2025-09' para ordenamiento
            anio_4d = f"20{anio_2d}" if len(anio_2d) == 2 else anio_2d
            mes_num = meses[mes_str]
            periodo_clave = f"{anio_4d}-{mes_num}"
            
            resultados.append((periodo_texto, periodo_clave))
            spans_usados.append((start, end))
        except KeyError:
            continue
            
    return resultados

def responder_pregunta_coyuntura(pregunta: str) -> tuple[bool, str, list[dict] | dict]:
    """Interpreta una pregunta simple de coyuntura y responde usando DuckDB.

    Versión inicial basada en reglas, pensada para preguntas tipo:
    - "total de unidades de vivienda en oferta para octubre de 2025 en Antioquia"
    - "unidades en oferta en Atlántico para septiembre 2025"
    - "área neta en oferta en Bogotá para oct-25"
    """
    # Extraer TODOS los períodos de la pregunta
    periodos_encontrados = _extraer_periodos(pregunta)
    print(f"[DEBUG PERIODOS] Encontrados: {periodos_encontrados}")
    
    pregunta_norm = _normalizar_texto(pregunta)
    print(f"[DEBUG INICIO] pregunta_norm: '{pregunta_norm}'")

    # 1. Detectar tipo_fuente (priorizando área/valor/netas/riesgo sobre unidades)
    tiene_area = any(p in pregunta_norm for p in ["area", "metros", "m2"])
    tiene_valor = any(p in pregunta_norm for p in ["valor", "pesos", "monto"])
    tiene_ventas_dinero = "ventas" in pregunta_norm and any(
        p in pregunta_norm for p in ["pesos", "miles", "millones", "valor"]
    )
    tiene_netas = "neta" in pregunta_norm or "netas" in pregunta_norm
    tiene_riesgo = any(p in pregunta_norm for p in ["riesgo", "rotacion", "rotaci", "utv"])
    tiene_unidades = any
    print(f"[DEBUG TIPO] tiene_area={tiene_area}, tiene_valor={tiene_valor}, tiene_ventas_dinero={tiene_ventas_dinero}")
    print(f"[DEBUG TIPO] tiene_netas={tiene_netas}, tiene_riesgo={tiene_riesgo}, tiene_unidades={tiene_unidades}")

    if tiene_area:
        tipo_fuente = "area"
    elif tiene_valor or tiene_ventas_dinero:
        tipo_fuente = "valor_ventas"
    elif tiene_netas:
        tipo_fuente = "netas"
    elif tiene_riesgo:
        tipo_fuente = "riesgo"
    elif tiene_unidades:
        tipo_fuente = "unidades"
    else:
        tipo_fuente = "unidades"  # default razonable

    # 2. Detectar hoja principal
    # Caso especial 1: valor de ventas (tablas de valor_ventas)
    if tipo_fuente == "valor_ventas":
        if "corriente" in pregunta_norm:
            hoja = "Valor ventas corrientes"
        elif "constante" in pregunta_norm:
            hoja = "Valor ventas constantes"
        else:
            # Si no se especifica, asumimos corrientes
            hoja = "Valor ventas corrientes"

    # Caso especial 2: riesgo (UTV, UTV %, Rotación de Inventarios)
    elif tipo_fuente == "riesgo":
        if (
            "utv %" in pregunta_norm
            or "utv%" in pregunta_norm
            or "% utv" in pregunta_norm
            or ("porcentaje" in pregunta_norm and "utv" in pregunta_norm)
        ):
            hoja = "UTV %"
        elif "rotacion de inventarios" in pregunta_norm or "rotación de inventarios" in pregunta_norm:
            hoja = "Rotación de Inventarios"
        elif "utv" in pregunta_norm or "unidades terminadas sin vender" in pregunta_norm:
            hoja = "UTV"
        else:
            # Si no se especifica, usar Oferta como agregación general de riesgo
            hoja = "Oferta"

    else:
        # Tablas normales (unidades, area, netas)
        # IMPORTANTE: Evaluar ventas ANTES que oferta para evitar conflictos
        print(f"[DEBUG HOJA] pregunta_norm contiene 'venta': {'venta' in pregunta_norm}")
        print(f"[DEBUG HOJA] pregunta_norm contiene 'vendida': {'vendida' in pregunta_norm}")
        print(f"[DEBUG HOJA] pregunta_norm contiene 'oferta': {'oferta' in pregunta_norm}")
        
        if ("venta" in pregunta_norm or "vendida" in pregunta_norm or "vendieron" in pregunta_norm or "vendio" in pregunta_norm):
            hoja = "Ventas"
            print(f"[DEBUG HOJA] Detectó VENTAS")
        elif "lanzamiento" in pregunta_norm or "levantamiento" in pregunta_norm:
            hoja = "Lanzamientos"
            print(f"[DEBUG HOJA] Detectó LANZAMIENTOS")
        elif (
            "iniciacion" in pregunta_norm
            or "iniciaci" in pregunta_norm
            or "iniciad" in pregunta_norm  # iniciada, iniciadas, iniciados
        ):
            hoja = "Iniciaciones"
            print(f"[DEBUG HOJA] Detectó INICIACIONES")
        elif "oferta" in pregunta_norm:
            hoja = "Oferta"
            print(f"[DEBUG HOJA] Detectó OFERTA")
        else:
            # Default: si no menciona nada específico, asumimos oferta
            hoja = "Oferta"
            print(f"[DEBUG HOJA] Default OFERTA")
    
    print(f"[DEBUG] tipo_fuente={tipo_fuente}, hoja={hoja}")

    # 3. Detectar departamento (por ahora lista corta, se puede ampliar)
    departamentos = [
        "Antioquia",
        "Atlántico",
        "Bogotá",
        "Bogotá & Cundinamarca",
        "Bogota & Cundinamarca",
        "Bolívar",
        "Boyacá",
        "Caldas",
        "Cauca",
        "Cesar",
        "Cundinamarca",
        "Córdoba & Sucre",
        "Huila",
        "Nariño",
        "Norte de Santander",
        "Quindío",
        "Risaralda",
        "Santander",
        "Tolima",
        "Valle",
        "19 Regionales",
    ]

    departamento = None
    
    # Caso especial: todo el país
    if "colombia" in pregunta_norm or "todo el pais" in pregunta_norm or "todo el país" in pregunta_norm:
        departamento = "19 Regionales"
    
    # Buscar departamento en la pregunta
    if departamento is None:
        for d in departamentos:
            if _normalizar_texto(d) in pregunta_norm:
                departamento = d
                break
    
    # Si no se encontró departamento, usar "19 Regionales" como valor por defecto
    usando_default_depto = False
    if departamento is None:
        departamento = "19 Regionales"
        usando_default_depto = True
        print(f"[DEBUG] Usando departamento por defecto: {departamento}")
    else:
        print(f"[DEBUG] Departamento detectado: {departamento}")
    
    # 4. Determinar característica (TOTAL, VIS, VIP, etc.)
    caracteristica = "TOTAL"  # Valor por defecto
    
    if "no vis" in pregunta_norm:
        caracteristica = "No VIS"
    elif "vis" in pregunta_norm:
        if "sin vip" in pregunta_norm:
            caracteristica = "VIS (sin VIP)"
        elif "vip" not in pregunta_norm:
            caracteristica = "VIS"
    elif "vip" in pregunta_norm:
        caracteristica = "VIP"
    
    print(f"[DEBUG] Característica: {caracteristica}")
    
    # 5. Lógica de Períodos
    
    # CASO ESPECIAL: Año específico sin mes (Agregación Anual)
    # Detectar si hay año pero no mes
    import re
    anio_match = re.search(r'\b(20[1-2][0-9])\b', pregunta)
    
    # Definir meses para verificar si hay mes explícito
    meses_nombres = ["enero", "ene", "febrero", "feb", "marzo", "mar", "abril", "abr", 
                     "mayo", "may", "junio", "jun", "julio", "jul", "agosto", "ago", 
                     "septiembre", "sep", "sept", "setiembre", "octubre", "oct", 
                     "noviembre", "nov", "diciembre", "dic"]
    
    mes_detectado = any(m in pregunta_norm for m in meses_nombres)
    palabras_reciente = ["mes anterior", "mes pasado", "ultimo mes", "último mes", "reciente", "actual"]
    busca_reciente = any(p in pregunta_norm for p in palabras_reciente)
    
    if anio_match and not mes_detectado and not busca_reciente:
        anio_texto = anio_match.group(1)
        anio_corto = anio_texto[-2:]
        
        # Inicializar sistema
        try:
            system = CoyunturaSQLSystem()
            if system.conn is None:
                ok, msg = system.inicializar()
                if not ok: return False, msg, {}
        except Exception as e:
            return False, str(e), {}

        # CASO 1: Variables STOCK (Oferta) -> Promedio y Cierre
        if hoja == "Oferta":
            print(f"[DEBUG] Oferta Anual {anio_texto}: Calculando Promedio y Cierre...")
            
            # Obtener todos los datos del año
            query_all = """
                SELECT periodo, valor
                FROM coyuntura
                WHERE lower(trim(tipo_fuente)) = lower(trim(?))
                  AND lower(trim(hoja)) = lower(trim(?))
                  AND lower(trim(departamento)) = lower(trim(?))
                  AND lower(trim(caracteristica)) = lower(trim(?))
                  AND periodo LIKE ?
            """
            params = [tipo_fuente, hoja, departamento, caracteristica, f"%{anio_corto}"]
            rows = system.conn.execute(query_all, params).fetchall()
            system.cerrar()
            
            if rows:
                # Calcular Promedio
                valores = [r[1] for r in rows if r[1] is not None]
                promedio = sum(valores) / len(valores) if valores else 0
                
                # Encontrar Cierre (último periodo cronológico)
                def sort_key_periodo(p_str):
                    try:
                        if not p_str or '-' not in p_str: return (0, 0)
                        parts = p_str.split('-')
                        m_txt = parts[0].lower()[:3]
                        y_txt = parts[1]
                        y = int(y_txt)
                        if y < 100: y += 2000
                        meses_map = {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
                                     'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12, 'sept': 9}
                        m = meses_map.get(m_txt, 0)
                        return (y, m)
                    except: return (0, 0)

                rows.sort(key=lambda x: sort_key_periodo(x[0]), reverse=True)
                ultimo_periodo = rows[0][0]
                valor_cierre = rows[0][1]
                
                respuesta = (
                    f"📊 **Oferta en {departamento} ({caracteristica}) para el año {anio_texto}**:\n\n"
                    f"🔹 **Promedio del año:** {int(promedio):,} unidades\n"
                    f"🔹 **Cierre ({ultimo_periodo}):** {int(valor_cierre):,} unidades\n\n"
                    f"_(Nota: La oferta es una variable de stock, por lo que se presenta el promedio y el dato al cierre, no la suma)_"
                )
                return True, respuesta, {'tipo': 'stock_anual', 'promedio': promedio, 'cierre': valor_cierre, 'anio': anio_texto}
            else:
                return False, f"⚠️ No se encontraron datos de oferta para el año {anio_texto}.", {}

        # CASO 2: Variables FLUJO (Ventas, Lanzamientos, Iniciaciones) -> Suma
        else:
            print(f"[DEBUG] Flujo Anual {anio_texto} ({hoja}): Calculando Suma...")
            query_sum = """
                SELECT SUM(valor)
                FROM coyuntura
                WHERE lower(trim(tipo_fuente)) = lower(trim(?))
                  AND lower(trim(hoja)) = lower(trim(?))
                  AND lower(trim(departamento)) = lower(trim(?))
                  AND lower(trim(caracteristica)) = lower(trim(?))
                  AND periodo LIKE ?
            """
            params = [tipo_fuente, hoja, departamento, caracteristica, f"%{anio_corto}"]
            result = system.conn.execute(query_sum, params).fetchone()
            system.cerrar()
            
            total = result[0] if result and result[0] else 0
            
            if total > 0:
                respuesta = (
                    f"📊 **Total {hoja} en {departamento} ({caracteristica}) para el año {anio_texto}**:\n"
                    f"🔹 **{int(total):,} unidades**\n\n"
                    f"_(Nota: {hoja} es una variable de flujo, por lo que se presenta la suma acumulada del año)_"
                )
                return True, respuesta, {'tipo': 'flujo_anual', 'total': total, 'anio': anio_texto}
            else:
                return False, f"⚠️ No se encontraron datos de {hoja} para el año {anio_texto}.", {}

    # Si no se especificó NINGÚN período (o solo año para oferta), intentar obtener el último disponible
    if not periodos_encontrados or busca_reciente:
        print("[DEBUG] No se especificó período o se busca reciente, buscando el último disponible...")
        try:
            system = CoyunturaSQLSystem()
            if system.conn is None:
                ok, msg = system.inicializar()
                if not ok:
                    return False, f"❌ Error al conectar con la base de datos: {msg}", {}
            
            # Filtro opcional por año si se detectó en el texto (para casos como "Oferta 2024")
            filtro_anio = ""
            params = [tipo_fuente, hoja, departamento, caracteristica]
            
            import re
            anio_match = re.search(r'\b(20[1-2][0-9])\b', pregunta)
            if anio_match:
                anio_corto = anio_match.group(1)[-2:]
                filtro_anio = "AND periodo LIKE ?"
                params.append(f"%{anio_corto}")

            # Buscar el último período disponible para estos parámetros
            query = f"""
                SELECT DISTINCT periodo
                FROM coyuntura
                WHERE lower(trim(tipo_fuente)) = lower(trim(?))
                  AND lower(trim(hoja)) = lower(trim(?))
                  AND lower(trim(departamento)) = lower(trim(?))
                  AND lower(trim(caracteristica)) = lower(trim(?))
                  {filtro_anio}
            """
            print(f"[DEBUG] Buscando último período con: {params}")
            
            rows = system.conn.execute(query, params).fetchall()
            
            if rows:
                # Ordenar periodos en Python para asegurar orden cronológico correcto
                meses_order = {
                    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
                    'sept': 9
                }
                
                def sort_key_periodo(p_str):
                    try:
                        if not p_str or '-' not in p_str: return (0, 0)
                        parts = p_str.split('-')
                        m_txt = parts[0].lower()[:3]
                        y_txt = parts[1]
                        y = int(y_txt)
                        if y < 100: y += 2000
                        m = meses_order.get(m_txt, 0)
                        return (y, m)
                    except:
                        return (0, 0)

                periodos_list = [r[0] for r in rows if r[0]]
                periodos_list.sort(key=sort_key_periodo, reverse=True)
                
                if periodos_list:
                    ultimo_periodo = periodos_list[0]
                    periodos_encontrados = [(ultimo_periodo, None)]
                    print(f"[DEBUG] Último período encontrado: {ultimo_periodo}")
                else:
                    return False, "⚠️ No se encontraron datos para los parámetros especificados.", {}
            else:
                return False, "⚠️ No se encontraron datos para los parámetros especificados.", {}
                
        except Exception as e:
            return False, f"❌ Error al buscar el último período: {str(e)}", {}
    
    # 6. Realizar la consulta
    respuestas_acumuladas = []
    metadatos_acumulados = []
    
    try:
        system = CoyunturaSQLSystem()
        if system.conn is None:
            ok, msg = system.inicializar()
            if not ok:
                return False, f"❌ Error al conectar con la base de datos: {msg}", {}
        
        # Iterar sobre cada período encontrado
        for p_texto, p_clave in periodos_encontrados:
            print(f"[DEBUG] Consultando con: tipo_fuente={tipo_fuente}, hoja={hoja}, "
                  f"departamento={departamento}, caracteristica={caracteristica}, "
                  f"periodo_texto={p_texto}")
            
            # Usar consultar_valor con el formato correcto
            exito, mensaje, valor = system.consultar_valor(
                tipo_fuente=tipo_fuente,
                hoja=hoja,
                departamento=departamento,
                caracteristica=caracteristica,
                periodo_clave=p_clave or "",
                periodo_texto=p_texto
            )
            
            # Fallback para "19 Regionales" vs "Total 19 Regionales"
            if not exito and departamento == "19 Regionales":
                print(f"[DEBUG] Reintentando con 'Total 19 Regionales'...")
                exito, mensaje, valor = system.consultar_valor(
                    tipo_fuente=tipo_fuente,
                    hoja=hoja,
                    departamento="Total 19 Regionales",
                    caracteristica=caracteristica,
                    periodo_clave=periodo_clave or "",
                    periodo_texto=p_texto,
                )

            if exito:
                # Formatear la respuesta de manera amigable
                respuesta_texto = ""
                if tipo_fuente == "unidades":
                    respuesta_texto = f"📊 {hoja} en {departamento} ({caracteristica}) para {p_texto}: {int(valor):,} unidades"
                elif tipo_fuente == "area":
                    respuesta_texto = f"📏 Área en {hoja.lower()} en {departamento} ({caracteristica}) para {p_texto}: {float(valor):,.2f} m²"
                elif tipo_fuente == "valor_ventas":
                    respuesta_texto = f"💰 {hoja} en {departamento} para {p_texto}: ${float(valor):,.0f} millones"
                else:
                    respuesta_texto = f"📈 {hoja} en {departamento} ({caracteristica}) para {p_texto}: {valor}"
                
                # --- MEJORA UNHAPPY PATH: Validación de "Ceros Sospechosos" ---
                ciudades_principales = ["bogota", "medellin", "cali", "barranquilla", "bucaramanga", "cartagena", "antioquia", "valle", "atlantico"]
                if valor == 0 and _normalizar_texto(departamento) in ciudades_principales and hoja in ["Ventas", "Oferta"]:
                    respuesta_texto += "\n⚠️ **Alerta de Integridad:** El sistema reporta 0 unidades, lo cual es inusual para esta región principal. Podría tratarse de un rezago en la carga de información."

                # --- MEJORA HAPPY PATH: Contexto de Estacionalidad ---
                if "dic-" in p_texto.lower() or "ene-" in p_texto.lower():
                    respuesta_texto += "\n❄️ **Contexto Histórico:** Diciembre y Enero suelen presentar estacionalidad en la actividad comercial debido al cierre de año y periodo vacacional."

                respuestas_acumuladas.append(respuesta_texto)
                
                # Determinar nombre de archivo aproximado para referencia
                archivo_ref = {
                    "unidades": "Tablas_de_Coyuntura_oct25.xlsx",
                    "area": "Tablas de Coyuntura_oct25_Área.xlsx",
                    "netas": "Tablas de Coyuntura_oct25_Netas.xlsx",
                    "riesgo": "Tablas de Coyuntura_oct25_Riesgo.xlsx",
                    "valor_ventas": "Tablas de Coyuntura_oct25_Valor Ventas.xlsx",
                }.get(tipo_fuente, "Archivo Coyuntura Desconocido")

                descripcion_proceso = (
                    f"Archivo: {archivo_ref} | "
                    f"Hoja: {hoja} | "
                    f"Ubicación: {departamento} vs {caracteristica} | "
                    f"Fecha: {p_texto} | "
                    f"Regional: {departamento} | "
                    f"Categoría: {caracteristica}"
                )
                
                # Guardar metadatos para análisis posterior
                metadatos_acumulados.append({
                    'tipo_fuente': tipo_fuente,
                    'hoja': hoja,
                    'departamento': departamento,
                    'caracteristica': caracteristica,
                    'periodo_texto': p_texto,
                    'valor': valor,
                    'proceso_consulta': descripcion_proceso
                })
            else:
                respuestas_acumuladas.append(f"⚠️ {mensaje}")

        if not respuestas_acumuladas:
             return False, "No se pudo obtener información.", {}
             
        # Combinar respuestas
        respuesta_final = "\n".join(respuestas_acumuladas)
        return True, respuesta_final, metadatos_acumulados
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[ERROR] {error_details}")
        return False, f"❌ Ocurrió un error al procesar la solicitud: {str(e)}", {}

    # 7. Verificar si es una pregunta sobre años corridos
    if any(p in pregunta_norm for p in ["año corrido", "ano corrido", "acumulado"]):
        # Buscar el año en la pregunta
        anio_match = re.search(r"(20\d{2})", pregunta)
        if anio_match:
            anio = anio_match.group(1)
            return False, f"📊 Para consultas de año corrido {anio}, por favor especifica un mes específico (ej. 'enero {anio} a septiembre {anio}').", {}
        else:
            return False, "📊 Para consultas de año corrido, por favor especifica el año y el rango de meses (ej. 'enero a septiembre 2025').", {}

    return False, "ℹ️ No se pudo generar una respuesta. Por favor reformula tu pregunta.", {}

    # Ruta especial: oferta de unidades en resumen de coyuntura leída directo de Excel
    # (filas oct-24, oct-25, Año corrido oct-25). Se aplica cuando NO se menciona año
    # explícito en la pregunta y estamos en unidades/Oferta para un departamento
    # que existe en la fila de resumen.
    resumen_deptos_raw = [
        "Antioquia",
        "Atlántico",
        "Bogotá & Cundinamarca",
        "Bolívar",
        "Boyacá",
        "Caldas",
        "Huila",
        "Nariño",
        "Norte de Santander",
        "Risaralda",
        "Santander",
        "Tolima",
        "Valle",
        "Cesar",
        "Meta",
        "Córdoba & Sucre",
        "Magdalena",
        "Quindío",
        "Cauca",
        "5 Regionales",
        "13 Regionales",
        "18 Regionales",
        "19 Regionales",
    ]
    resumen_deptos = {_normalizar_texto(d) for d in resumen_deptos_raw}

    # Debug: verificar condiciones para ruta especial
    dep_normalizado = _normalizar_texto(departamento)
    print(f"[DEBUG] tipo_fuente={tipo_fuente}, hoja={hoja}, anio_match={anio_match}")
    print(f"[DEBUG] departamento='{departamento}', normalizado='{dep_normalizado}'")
    print(f"[DEBUG] dep_normalizado in resumen_deptos: {dep_normalizado in resumen_deptos}")
    print(f"[DEBUG] resumen_deptos contiene: {sorted(resumen_deptos)}")

    if (
        tipo_fuente == "unidades"
        and hoja == "Oferta"
        and anio_match is None  # no se detectó año explícito en la pregunta
        and _normalizar_texto(departamento) in resumen_deptos
    ):
        print(f"[DEBUG] Entrando a ruta especial Excel para {departamento}")
        ok_excel, valor_excel, periodo_legible_excel = _leer_oferta_desde_excel(
            departamento, caracteristica, pregunta_norm
        )
        print(f"[DEBUG] Resultado Excel: ok_excel={ok_excel}, valor_excel={valor_excel}")
        if ok_excel and valor_excel is not None:
            texto_tipo = "unidades de vivienda"
            respuesta = (
                f"Para {departamento}, en {periodo_legible_excel}, el {texto_tipo} en oferta "
                f"({caracteristica}) es {valor_excel:,.0f}."
            )
            
            # Descripción del proceso para auditoría
            descripcion_proceso = (
                f"Archivo: Tablas_de_Coyuntura_oct25.xlsx (Excel Directo) | "
                f"Hoja: {hoja} | "
                f"Ubicación: {departamento} vs {caracteristica} | "
                f"Fecha: {periodo_legible_excel} | "
                f"Regional: {departamento} | "
                f"Categoría: {caracteristica}"
            )
            
            metadata = {
                'tipo_fuente': tipo_fuente,
                'hoja': hoja,
                'departamento': departamento,
                'caracteristica': caracteristica,
                'periodo_texto': periodo_legible_excel,
                'valor': valor_excel,
                'proceso_consulta': descripcion_proceso
            }
            return True, respuesta, metadata
        else:
            print(f"[DEBUG] Excel falló, continuando a DuckDB")
    else:
        print(f"[DEBUG] NO entra a ruta especial Excel")

    # 5. Detectar periodo (mes y año) y mapear a clave 'YYYY-MM'
    # Mapeo de nombres de meses en español a número de mes
    meses_num = {
        "enero": "01",
        "ene": "01",
        "febrero": "02",
        "feb": "02",
        "marzo": "03",
        "mar": "03",
        "abril": "04",
        "abr": "04",
        "mayo": "05",
        "may": "05",
        "junio": "06",
        "jun": "06",
        "julio": "07",
        "jul": "07",
        "agosto": "08",
        "ago": "08",
        "septiembre": "09",
        "setiembre": "09",
        "sep": "09",
        "octubre": "10",
        "oct": "10",
        "noviembre": "11",
        "nov": "11",
        "diciembre": "12",
        "dic": "12",
    }

    mes_num = None
    mes_str = None
    for nombre_mes, num in meses_num.items():
        if f" {nombre_mes} " in f" {pregunta_norm} ":
            mes_num = num
            mes_str = nombre_mes[:3]  # ej: 'sep', 'oct'
            break

    # Verificar si la fecha es posterior al último período disponible
    if mes_num and anio_4d:
        try:
            # Inicializar el sistema para verificar el último período
            system = CoyunturaSQLSystem()
            ok, msg_init = system.inicializar()
            if not ok:
                return f"Error al inicializar la base de datos: {msg_init}"
            
            # Obtener el último período disponible
            query = """
                SELECT DISTINCT periodo 
                FROM coyuntura
            """
            result = system.conn.execute(query).fetchall()
            
            ultimo_periodo = None
            if result:
                # Ordenar en Python para garantizar orden cronológico (evitar error alfabético sep > nov)
                meses_order_check = {
                    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12, 'sept': 9
                }
                def sort_key_check(p_str):
                    try:
                        if not p_str or '-' not in p_str: return (0, 0)
                        parts = p_str.split('-')
                        m_txt = parts[0].lower()[:3]
                        y = int(parts[1]) + (2000 if int(parts[1]) < 100 else 0)
                        return (y, meses_order_check.get(m_txt, 0))
                    except: return (0, 0)
                
                periodos_check = [r[0] for r in result if r[0]]
                periodos_check.sort(key=sort_key_check, reverse=True)
                if periodos_check:
                    ultimo_periodo = periodos_check[0]

            system.cerrar()
            
            if ultimo_periodo:
                # Extraer mes y año del último período (formato: 'MMM-YY')
                try:
                    ultimo_mes, ultimo_anio = ultimo_periodo.split('-')
                    # Convertir a formato comparable
                    meses_inv = {v: k for k, v in meses_num.items()}
                    # Obtener el nombre del mes en minúsculas (3 letras)
                    ultimo_mes_nombre = ultimo_mes.lower()[:3]
                    # Obtener el número del mes del último período
                    ultimo_mes_num = meses_num.get(ultimo_mes_nombre, 1)
                    
                    # Obtener año completo (asumimos formato YY)
                    ultimo_anio_completo = int(f"20{ultimo_anio}")
                    anio_solicitado = int(anio_4d)
                    
                    # Comparar con la fecha solicitada
                    if (anio_solicitado > ultimo_anio_completo) or \
                       (anio_solicitado == ultimo_anio_completo and int(mes_num) > int(ultimo_mes_num)):
                        return False, f"⚠️ No tengo datos para {mes_str.capitalize()}-{anio_4d}. Los datos más recientes son de {ultimo_periodo}. ¿Te gustaría verlos?", {}
                except Exception as e:
                    print(f"[DEBUG] Error al comparar con último período: {e}")
            
        except Exception as e:
            print(f"[DEBUG] Error al verificar fecha futura: {e}")
            # Continuar con la consulta normal si hay un error en la verificación

    periodo_candidatos = []
    periodo_clave = None
    if mes_str and anio_4d:
        # Construir el texto del período que coincide con la base de datos, ej: 'sep-25'
        # Agregar variante 'sept' para septiembre, ya que Excel a veces usa 'sept-YY'
        if mes_str == 'sep':
            periodo_candidatos.append(f"sept-{anio_4d[2:]}")
        periodo_candidatos.insert(0, f"{mes_str}-{anio_4d[2:]}")
        periodo_legible = f"{mes_str}-{anio_4d}"
    else:
        # Si no se detectó año explícito, usar el periodo por defecto "Año corrido oct25"
        periodo_candidatos.append("año corrido oct25")
        periodo_legible = "Año corrido oct25"

    # Ejecutar consulta
    system = CoyunturaSQLSystem()
    ok, msg_init = system.inicializar()
    if not ok:
        return f"Error al inicializar la base de datos: {msg_init}"

    # Inicializar variables
    exito = False
    mensaje = "No se encontró información para la consulta"
    valor = None
    
    # Probar candidatos de periodo hasta encontrar uno
    for p_texto in periodo_candidatos:
        print(f"[DEBUG CONSULTA] Probando periodo_texto='{p_texto}'...")
        try:
            exito, mensaje, valor = system.consultar_valor(
                tipo_fuente=tipo_fuente,
                hoja=hoja,
                departamento=departamento,
                caracteristica=caracteristica,
                periodo_clave=periodo_clave,
                periodo_texto=p_texto,
            )
            if exito and valor is not None:
                break
        except Exception as e:
            print(f"[ERROR] Error en consulta: {str(e)}")
            mensaje = f"Error al procesar la consulta: {str(e)}"
            exito = False

    system.cerrar()

    if not exito or valor is None:
        return False, f"No se pudo obtener la información solicitada. {mensaje}", {}

    # Construir respuesta en lenguaje natural
    texto_tipo = {
        "unidades": "unidades de vivienda",
        "area": "metros cuadrados de área",
        "valor_ventas": "valor de ventas",
        "netas": "unidades netas",
        "riesgo": "indicador de riesgo",
    }.get(tipo_fuente, "valor")

    respuesta = (
        f"Para {departamento}, en {periodo_legible}, el {texto_tipo} en {hoja.lower()} "
        f"({caracteristica}) es {valor:,.0f}."
    )
    
    metadata = {
        'tipo_fuente': tipo_fuente,
        'hoja': hoja,
        'departamento': departamento,
        'caracteristica': caracteristica,
        'periodo_texto': periodo_legible,
        'valor': valor
    }

    return True, respuesta, metadata

def obtener_comparacion_anual(metadata: dict) -> str | None:
    """Calcula la variación anual usando los metadatos de una consulta exitosa."""
    try:
        periodo_actual = metadata.get('periodo_texto') # e.g. 'sep-25'
        if not periodo_actual or '-' not in periodo_actual:
            return None
            
        mes, anio_str = periodo_actual.split('-')
        try:
            anio = int(anio_str)
            # Ajuste para años de 2 dígitos
            if anio < 100: anio += 2000
        except:
            return None
            
        anio_anterior = anio - 1
        periodo_anterior = f"{mes}-{str(anio_anterior)[2:]}"
        
        system = CoyunturaSQLSystem()
        exito, _, valor_anterior = system.consultar_valor(
            metadata['tipo_fuente'],
            metadata['hoja'],
            metadata['departamento'],
            metadata['caracteristica'],
            periodo_clave=None,
            periodo_texto=periodo_anterior
        )
        system.cerrar()
        
        if exito and valor_anterior and valor_anterior > 0:
            valor_actual = metadata['valor']
            variacion = ((valor_actual - valor_anterior) / valor_anterior) * 100
            
            # --- MEJORA UNHAPPY PATH: Gestión de Datos Atípicos (Outliers) ---
            advertencia = ""
            if variacion > 500 or variacion < -90:
                advertencia = " ⚠️ **Nota:** Esta variación es inusualmente alta (Spike), podría deberse a un efecto base, lanzamiento de megaproyectos o ajuste de reportes."
            
            direccion = "crecimiento" if variacion >= 0 else "decrecimiento"
            return f"📉 **Dato Comparativo:** Esto representa un {direccion} del {abs(variacion):.1f}% frente al mismo mes del año anterior ({periodo_anterior}).{advertencia}"
    except Exception as e:
        print(f"[ERROR] Falló comparación anual: {e}")
    return None

def obtener_acumulado_anual(metadata: dict) -> str | None:
    """Calcula el acumulado anual (YTD) para variables de flujo."""
    try:
        # Solo para variables de flujo
        hoja = metadata.get('hoja')
        if hoja not in ['Ventas', 'Lanzamientos', 'Iniciaciones']:
            return None
            
        periodo_actual = metadata.get('periodo_texto') # e.g. 'sep-25'
        if not periodo_actual or '-' not in periodo_actual:
            return None
            
        mes_str, anio_str = periodo_actual.split('-')
        
        # Mapeo de meses
        meses_num = {
            'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12, 'sept': 9
        }
        mes_idx = meses_num.get(mes_str.lower()[:3])
        if not mes_idx or mes_idx == 1: # Si es enero, el acumulado es igual al mes
            return None
            
        # Consultar acumulado
        system = CoyunturaSQLSystem()
        # Traer todos los meses del año para sumar
        query = """
            SELECT periodo, valor
            FROM coyuntura
            WHERE lower(trim(tipo_fuente)) = lower(trim(?))
              AND lower(trim(hoja)) = lower(trim(?))
              AND lower(trim(departamento)) = lower(trim(?))
              AND lower(trim(caracteristica)) = lower(trim(?))
              AND periodo LIKE ?
        """
        params = [metadata['tipo_fuente'], metadata['hoja'], metadata['departamento'], metadata['caracteristica'], f"%-{anio_str}"]
        
        if system.conn is None: system.inicializar()
        rows = system.conn.execute(query, params).fetchall()
        system.cerrar()
        
        suma_ytd = sum(v for p, v in rows if v is not None and meses_num.get(p.split('-')[0].lower()[:3], 13) <= mes_idx)
        
        if suma_ytd > 0:
            return f"📅 **Acumulado Año ({anio_str}):** {int(suma_ytd):,} unidades (Ene-{mes_str.capitalize()})"
            
    except Exception as e:
        print(f"[ERROR] Falló acumulado anual: {e}")
    return None

def obtener_fechas_referencia() -> Tuple[Optional[str], Optional[str]]:
    """
    Retorna (ultimo_mes_texto, mes_anterior_texto) basado en los datos disponibles en la BD.
    Calcula dinámicamente cuál es el último mes con datos y el anterior a este.
    Ejemplo retorno: ('noviembre 2025', 'octubre 2025')
    """
    ultimo_txt = None
    anterior_txt = None
    
    try:
        system = CoyunturaSQLSystem()
        ok, msg = system.inicializar()
        if not ok:
            return None, None
            
        query = "SELECT DISTINCT periodo FROM coyuntura"
        rows = system.conn.execute(query).fetchall()
        system.cerrar()
        
        if not rows:
            return None, None
            
        # Ordenar cronológicamente (lógica compartida)
        meses_order = {
            'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
            'sept': 9
        }
        
        def sort_key(p_str):
            try:
                if not p_str or '-' not in p_str: return (0, 0)
                parts = p_str.split('-')
                m_txt = parts[0].lower()[:3]
                y_txt = parts[1]
                y = int(y_txt)
                if y < 100: y += 2000
                m = meses_order.get(m_txt, 0)
                return (y, m)
            except: return (0, 0)

        periodos = [r[0] for r in rows if r[0]]
        periodos.sort(key=sort_key, reverse=True)
        
        if periodos:
            # Función auxiliar para formatear 'nov-25' a 'noviembre 2025'
            meses_full = {'ene': 'enero', 'feb': 'febrero', 'mar': 'marzo', 'abr': 'abril', 'may': 'mayo', 'jun': 'junio', 'jul': 'julio', 'ago': 'agosto', 'sep': 'septiembre', 'oct': 'octubre', 'nov': 'noviembre', 'dic': 'diciembre', 'sept': 'septiembre'}
            def fmt(p):
                try:
                    m, y = p.split('-')
                    return f"{meses_full.get(m.lower()[:3], m)} 20{y}"
                except: return p
            
            ultimo_txt = fmt(periodos[0])
            if len(periodos) > 1:
                anterior_txt = fmt(periodos[1])
                
    except Exception as e:
        print(f"[ERROR] obtener_fechas_referencia: {e}")
        
    return ultimo_txt, anterior_txt

if __name__ == "__main__":
    # Modo interactivo: escribe tu pregunta personalizada
    while True:
        pregunta = input("\n¿Qué quieres preguntar sobre coyuntura? (o 'salir' para terminar): ")
        if pregunta.lower() in ['salir', 'exit', 'quit', '']:
            break
        
        print("Pregunta:", pregunta)
        exito, respuesta, meta = responder_pregunta_coyuntura(pregunta)
        print(f"Respuesta ({'OK' if exito else 'Error'}):", respuesta)
