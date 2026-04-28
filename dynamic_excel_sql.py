#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sistema SQL Dinámico para Archivos Excel Genéricos.
Permite consultar cualquier Excel usando DuckDB y Text-to-SQL con LLM.
"""
import duckdb
import pandas as pd
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
import traceback
import re
import os
import warnings

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

class DynamicExcelSQLSystem:
    def __init__(self, excel_path: Optional[str] = None):
        self.excel_path = Path(excel_path) if excel_path else None
        self.conn = None
        self.tables = {}  # Diccionario {nombre_tabla: schema_str}

    def inicializar(self) -> Tuple[bool, str]:
        """Inicializa la conexión y carga el archivo principal si existe (compatibilidad)"""
        try:
            # Usar base de datos en memoria para velocidad
            self.conn = duckdb.connect(database=':memory:')
            
            if self.excel_path:
                return self.cargar_archivo(self.excel_path)
            
            return True, "Sistema SQL inicializado (sin datos)"
        except Exception as e:
            return False, f"Error inicializando sistema: {str(e)}"

    def cargar_archivo(self, path: Path, table_prefix: str = None) -> Tuple[bool, str]:
        """Carga todas las hojas de un archivo Excel en tablas separadas"""
        try:
            if not self.conn:
                self.conn = duckdb.connect(database=':memory:')
                
            # Generar prefijo de tabla si no se provee
            if not table_prefix:
                # Limpiar nombre de archivo para usar como nombre de tabla
                clean_name = re.sub(r'[^a-zA-Z0-9]', '_', path.stem).lower()
                if clean_name[0].isdigit():
                    clean_name = f"t_{clean_name}"
                table_prefix = clean_name
            
            xls = pd.ExcelFile(path)
            loaded_sheets = []
            
            # Detectar si es el archivo de Cifras (requiere manejo especial de headers)
            is_cifras_file = "colombia-construccion-en-cifras" in path.name.lower()

            # Helper para aplanar columnas MultiIndex con forward fill (para celdas combinadas)
            def flatten_cols(df_local):
                if not isinstance(df_local.columns, pd.MultiIndex):
                    return [str(c).strip() for c in df_local.columns]
                cols_data = [list(c) for c in df_local.columns]
                # Forward fill por nivel (rellena horizontalmente los títulos agrupados)
                for level_idx in range(len(cols_data[0])):
                    last_val = None
                    for col_idx in range(len(cols_data)):
                        val = cols_data[col_idx][level_idx]
                        val_str = str(val)
                        if pd.isna(val) or "Unnamed" in val_str:
                            if last_val is not None:
                                cols_data[col_idx][level_idx] = last_val
                        else:
                            last_val = val
                return [" - ".join([str(p).strip() for p in parts if "Unnamed" not in str(p) and pd.notna(p)]) for parts in cols_data]

            for sheet_name in xls.sheet_names:
                df = None
                
                # --- LÓGICA ESPECÍFICA PARA "Colombia Construcción en Cifras" ---
                if is_cifras_file:
                    sheet_lower = sheet_name.lower()
                    try:
                        # Caso 1: Hoja PIB (Headers jerárquicos: Miles de millones -> Edificaciones)
                        if "pib" in sheet_lower and "construcción" in sheet_lower:
                            # Buscar fila que contiene "Edificaciones" para anclar el header
                            preview = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=15)
                            header_row_2 = None
                            for idx, row in preview.iterrows():
                                if row.astype(str).str.contains("Edificaciones", case=False).any():
                                    header_row_2 = idx
                                    break
                            
                            if header_row_2 is not None and header_row_2 > 0:
                                # Leer usando las dos filas de encabezado
                                df = pd.read_excel(xls, sheet_name=sheet_name, header=[header_row_2-1, header_row_2])
                                new_cols = flatten_cols(df)
                                if not new_cols[0]: new_cols[0] = "Periodo"
                                df.columns = new_cols

                        # Caso 2: Hoja Empleo (Headers jerárquicos: Total Nacional -> No. ocupados)
                        elif "empleo" in sheet_lower:
                            preview = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=15)
                            header_row_2 = None
                            for idx, row in preview.iterrows():
                                if row.astype(str).str.contains("Ocupados construcción", case=False).any():
                                    header_row_2 = idx
                                    break
                            
                            if header_row_2 is not None and header_row_2 > 0:
                                df = pd.read_excel(xls, sheet_name=sheet_name, header=[header_row_2-1, header_row_2])
                                new_cols = flatten_cols(df)
                                if not new_cols[0]: new_cols[0] = "Trimestre_Movil"
                                df.columns = new_cols

                        # Caso 3: Censo Edificaciones (Headers de 3 niveles)
                        elif "censo" in sheet_lower and "edificaciones" in sheet_lower:
                            preview = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=15)
                            header_row_3 = None
                            for idx, row in preview.iterrows():
                                # Buscamos texto característico de la 3ra fila de encabezados
                                if row.astype(str).str.contains("Continúan en proceso", case=False).any():
                                    header_row_3 = idx
                                    break
                            
                            if header_row_3 is not None and header_row_3 >= 2:
                                df = pd.read_excel(xls, sheet_name=sheet_name, header=[header_row_3-2, header_row_3-1, header_row_3])
                                new_cols = flatten_cols(df)
                                if not new_cols[0]: new_cols[0] = "Periodo"
                                df.columns = new_cols

                        # Caso 4: Licencias (Headers de 2 niveles: Vivienda -> VIP)
                        elif "licencias" in sheet_lower:
                            preview = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=15)
                            header_row_2 = None
                            for idx, row in preview.iterrows():
                                row_str = row.astype(str).str.lower()
                                if row_str.str.contains("vis", case=False).any() and row_str.str.contains("no vis", case=False).any():
                                    header_row_2 = idx
                                    break
                            
                            if header_row_2 is not None and header_row_2 > 0:
                                df = pd.read_excel(xls, sheet_name=sheet_name, header=[header_row_2-1, header_row_2])
                                new_cols = flatten_cols(df)
                                if not new_cols[0] or new_cols[0].lower() == "fecha": new_cols[0] = "Periodo"
                                df.columns = new_cols

                        # Caso 5: Histórico Departamento (Headers de 2 niveles: Antioquia -> VIS)
                        elif "histórico" in sheet_lower and "departamento" in sheet_lower:
                            preview = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=15)
                            header_row_2 = None
                            for idx, row in preview.iterrows():
                                if row.astype(str).str.contains("Total vivienda", case=False).any():
                                    header_row_2 = idx
                                    break
                            
                            if header_row_2 is not None and header_row_2 > 0:
                                df = pd.read_excel(xls, sheet_name=sheet_name, header=[header_row_2-1, header_row_2])
                                new_cols = flatten_cols(df)
                                if not new_cols[0]: new_cols[0] = "Periodo"
                                df.columns = new_cols
                    except Exception as e:
                        print(f"⚠️ Advertencia: Carga especial falló para {sheet_name}: {e}. Usando método genérico.")
                        df = None

                # --- LÓGICA GENÉRICA (si no se cargó arriba) ---
                if df is None:
                    try:
                        df_preview = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=20)
                        if df_preview.empty: continue
                        
                        # Detectar fila de encabezado por densidad de texto
                        header_row_idx = 0
                        max_score = -1
                        for i, row in df_preview.iterrows():
                            non_nulls = row.count()
                            strings = sum(1 for val in row if isinstance(val, str) and len(str(val).strip()) > 0)
                            score = strings * 2 + non_nulls
                            if score > max_score:
                                max_score = score
                                header_row_idx = i
                        
                        df = pd.read_excel(xls, sheet_name=sheet_name, header=header_row_idx)
                    except Exception:
                        continue

                # Limpiar nombres de columnas
                clean_cols = []
                for c in df.columns:
                    c_str = str(c).strip()
                    c_str = re.sub(r'[\n\r\t]+', '_', c_str)
                    c_str = re.sub(r'[^a-zA-Z0-9_]', '_', c_str).lower()
                    c_str = re.sub(r'_+', '_', c_str).strip('_')
                    
                    if not c_str:
                        c_str = f"col_{len(clean_cols)}"
                    
                    if c_str[0].isdigit():
                        c_str = f"col_{c_str}"
                    
                    original_c_str = c_str
                    counter = 1
                    while c_str in clean_cols:
                        c_str = f"{original_c_str}_{counter}"
                        counter += 1
                    
                    clean_cols.append(c_str)
                
                df.columns = clean_cols
                
                # Nombre de tabla: prefijo_hoja
                clean_sheet = re.sub(r'[^a-zA-Z0-9]', '_', sheet_name).lower()
                table_name = f"{table_prefix}_{clean_sheet}"
                
                # Registrar DataFrame en DuckDB
                self.conn.register(table_name, df)
                
                # Analizar esquema para el LLM
                schema = self._analizar_schema(df, table_name)
                self.tables[table_name] = schema
                loaded_sheets.append(sheet_name)
            
            return True, f"Cargado {path.name}: {len(loaded_sheets)} hojas procesadas."
        except Exception as e:
            return False, f"Error cargando {path.name}: {str(e)}"

    def _analizar_schema(self, df: pd.DataFrame, table_name: str) -> str:
        """Genera una descripción del esquema para el LLM"""
        schema = f"Tabla: {table_name}\n"
        schema += f"Filas: {len(df)}\n"
        schema += "Columnas:\n"
        
        for col in df.columns:
            dtype = str(df[col].dtype)
            # Obtener ejemplos de valores no nulos
            sample = df[col].dropna().unique()[:3].tolist()
            sample_str = [str(s) for s in sample]
            schema += f"- {col} ({dtype}): Ejemplos: {', '.join(sample_str)}\n"
            
        # Agregar muestra de datos (primeras 3 filas) para contexto
        schema += "\nMuestra de datos (primeras 3 filas):\n"
        try:
            schema += df.head(3).to_string(index=False) + "\n"
        except Exception:
            schema += "(No se pudo generar muestra de datos)\n"
            
        return schema

    def consultar(self, pregunta: str, llm_function) -> Tuple[bool, str]:
        """Genera y ejecuta SQL basado en la pregunta"""
        if not self.conn:
            return False, "Sistema no inicializado"
            
        # Combinar esquemas de todas las tablas cargadas
        full_schema = "\n\n".join(self.tables.values())
        
        prompt = f"""
        Eres un experto en SQL (DuckDB). Tienes acceso a varias tablas con datos de archivos Excel.
        Tu tarea es generar una consulta SQL para responder a la pregunta del usuario.

        ESQUEMAS DISPONIBLES:
        {full_schema}

        PREGUNTA: "{pregunta}"

        REGLAS:
        1. Identifica la tabla más relevante para la pregunta.
        2. Usa ILIKE para comparaciones de texto (case insensitive).
        3. Si piden totales, usa SUM(). Si piden conteo, usa COUNT().
        4. Responde SOLO con el código SQL, sin explicaciones ni markdown.
        5. Asegúrate de usar los nombres de columnas exactos del esquema.

        SQL:
        """
        
        sql_response, _ = llm_function(prompt)
        
        if not sql_response:
            return False, "No se pudo generar el SQL"
            
        # Limpiar SQL
        sql = sql_response.strip().replace('```sql', '').replace('```', '').strip()
        
        try:
            print(f"[DynamicSQL] Ejecutando: {sql}")
            result = self.conn.execute(sql).fetchall()
            columns = [desc[0] for desc in self.conn.description]
            
            # Formatear respuesta
            if not result:
                return True, "No se encontraron datos."
            
            if len(result) == 1 and len(columns) == 1:
                val = result[0][0]
                if isinstance(val, (int, float)):
                    return True, f"**Resultado:** {val:,.2f}" if isinstance(val, float) else f"**Resultado:** {val:,}"
                return True, f"**Resultado:** {val}"
                
            return True, f"Se encontraron {len(result)} registros:\n" + str(result[:5])
            
        except Exception as e:
            print(f"[DynamicSQL] Error SQL: {e}")
            return False, f"Error ejecutando consulta en el archivo: {str(e)}"

if __name__ == "__main__":
    # Bloque de prueba interactiva
    from llm_providers import llamar_api_ia
    from config import AI_PROVIDERS
    
    # Configurar proveedor rápido
    FAST_PROVIDER = next((p for p in AI_PROVIDERS if p["name"] == "Groq"), None)
    def mock_llm(prompt): return llamar_api_ia(prompt, FAST_PROVIDER)

    RAG_FOLDER = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG")
    print(f"📂 Buscando archivos Excel en: {RAG_FOLDER}")
    
    # Excluir archivos que ya tienen sus propios sistemas (LIVO y Coyuntura)
    patrones_exclusion = ["livo", "coyuntura"]
    
    archivos = [
        f for f in RAG_FOLDER.rglob("*.xlsx") 
        if not f.name.startswith("~$") 
        and not any(p in f.name.lower() for p in patrones_exclusion)
    ]
    
    if not archivos:
        print("❌ No se encontraron archivos Excel.")
        exit()

    # Cargar TODOS los archivos automáticamente
    sys = DynamicExcelSQLSystem()
    sys.inicializar()
    
    print(f"\n🚀 Cargando {len(archivos)} archivos en la base de datos...")
    for i, f in enumerate(archivos, 1):
        ok, msg = sys.cargar_archivo(f)
        print(f"[{i}/{len(archivos)}] {msg}")

    print("\n✅ Todos los archivos cargados. Puedes hacer preguntas sobre cualquiera de ellos.")
    
    while True:
        q = input("\nPregunta (o 'salir'): ")
        if q.lower() in ['salir', 'exit']: break
        
        ok, resp = sys.consultar(q, mock_llm)
        print(resp)