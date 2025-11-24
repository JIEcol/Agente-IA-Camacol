#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo DuckDB + Text-to-SQL para consultas rápidas sobre datos LIVO
Ventajas:
- 100x más rápido que Pandas
- Carga instantánea de Excel/CSV
- SQL nativo optimizado
- Text-to-SQL con LLM
"""

import duckdb
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
import json
import hashlib
from datetime import datetime
import os

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except:
    PANDAS_AVAILABLE = False

try:
    from langdetect import detect, LangDetectException
    LANGDETECT_AVAILABLE = True
except:
    LANGDETECT_AVAILABLE = False
    print("⚠️ langdetect no disponible. Instalar con: pip install langdetect")

class LIVOSQLSystem:
    """Sistema de consultas SQL sobre LIVO usando DuckDB"""
    
    # Diccionario de sinónimos: mapea términos comunes a nombres de columnas
    SINONIMOS = {
        # Ubicación geográfica
        'ciudad': ['municipio', 'localidad', 'población', 'urbe', 'capital', 'ciudades'],
        'departamento': ['depto', 'estado', 'provincia', 'region', 'departamentos'],
        'regional': ['zona regional', 'región', 'regional camacol', 'regionales'],
        'barrio': ['sector', 'vecindario', 'colonia', 'localidad', 'barrios'],
        'zona': ['sector urbano', 'area urbana', 'zonas'],
        
        # Características de vivienda
        'tipo_vivienda': [
            'tipo de vivienda', 'clase de vivienda', 'categoría vivienda',
            'vis', 'vivienda de interes social', 'vivienda de interés social',
            'vip', 'vivienda de interes prioritario', 'vivienda de interés prioritario',
            'no vis', 'no vivienda de interes social', 'vivienda no vis'
        ],
        'uso_etapa': ['uso', 'destino', 'tipo de uso', 'uso del proyecto', 'usos'],
        'destino_etapa': ['destino del proyecto', 'finalidad', 'propósito'],
        'modalidad': ['tipo de modalidad', 'clase de licencia', 'modalidades'],
        'estado': ['estado de licencia', 'estatus', 'situación', 'estados'],
        'fase': ['etapa', 'fase del proyecto', 'fases'],
        'estrato': ['nivel socioeconomico', 'nivel socioeconómico', 'estrato socioeconomico', 'estratos'],
        
        # Empresa constructora
        'compania_constructora': ['constructora', 'empresa constructora', 'constructor', 'empresa', 
                                   'compañía', 'constructoras', 'empresas constructoras'],
        'nit_constructora': ['nit', 'nit empresa', 'identificación empresa', 'nits'],
        
        # Métricas numéricas
        'unidades': ['numero de unidades', 'número de unidades', 'cantidad de unidades', 
                     'total unidades', 'unidades de vivienda', 'viviendas', 'apartamentos'],
        'area': ['área', 'area construida', 'área construida', 'metros cuadrados', 'm2', 
                 'metraje', 'superficie', 'áreas', 'tamaño'],
        'valor': ['precio', 'costo', 'monto', 'valor total', 'presupuesto', 'valores', 'precios'],
        'precio_mc_promedio': ['precio por metro', 'precio m2', 'valor por m2', 'costo por metro'],
        'cuenta': ['conteo', 'cantidad', 'número', 'total'],
        
        # Fechas y periodos temporales
        'fecha': ['fecha de licencia', 'fecha expedición', 'cuando', 'fechas', 'periodo', 'momento'],
        'año_corrido': ['año', 'anio', 'año actual', 'este año', 'años', 'anual'],
        'doce_meses': ['12 meses', 'ultimo año', 'último año', 'año completo', 'rolling 12'],
        
        # Términos de tendencias y análisis temporal
        'tendencia': ['evolución', 'comportamiento', 'patrón', 'desarrollo', 'trayectoria'],
        'crecimiento': ['incremento', 'aumento', 'variación', 'cambio', 'tasa'],
        'comparacion': ['vs', 'versus', 'comparado con', 'respecto a', 'frente a'],
        
        # Clasificaciones
        'politica_vivienda': ['política de vivienda', 'programa de vivienda', 'tipo programa'],
        'segmento_pre': ['segmento', 'segmento de precio', 'rango de precio'],
        'rango_area': ['rango de área', 'rango de tamaño', 'clasificación por área'],
        'AM_capital': ['area metropolitana', 'área metropolitana', 'am', 'metropolitana'],
    }
    
    def __init__(self, livo_path: str):
        self.livo_path = Path(livo_path)
        self.conn = None
        self.schema_info = {}
        
        # Caché de consultas
        self.cache_consultas = {}
        self.cache_file = Path('cache_livo_consultas.json')
        self._cargar_cache()
        
        # Historial de consultas
        self.historial = []
        self.historial_file = Path('historial_livo_consultas.json')
        self._cargar_historial()
        
    def inicializar(self) -> Tuple[bool, str]:
        """Inicializa DuckDB y carga LIVO"""
        try:
            # Crear conexión DuckDB en memoria
            self.conn = duckdb.connect(':memory:')
            
            # Cargar LIVO
            if self.livo_path.suffix.lower() in ['.xlsx', '.xls']:
                if not PANDAS_AVAILABLE:
                    return False, "❌ Pandas no disponible"
                
                df = pd.read_excel(self.livo_path)
                self.conn.register('livo', df)
                
            elif self.livo_path.suffix.lower() == '.csv':
                self.conn.execute(f"CREATE TABLE livo AS SELECT * FROM read_csv_auto('{self.livo_path}')")
            else:
                return False, f"❌ Formato no soportado: {self.livo_path.suffix}"
            
            # Obtener schema
            result = self.conn.execute("PRAGMA table_info('livo')").fetchall()
            self.schema_info = {
                'columns': [row[1] for row in result],
                'types': {row[1]: row[2] for row in result}
            }
            
            filas = self.conn.execute("SELECT COUNT(*) FROM livo").fetchone()[0]
            
            # Analizar metadatos de columnas
            print("🔍 Analizando metadatos de columnas...")
            self._analizar_metadatos()
            
            return True, f"✅ LIVO cargado: {filas:,} registros, {len(self.schema_info['columns'])} columnas"
            
        except Exception as e:
            return False, f"❌ Error: {str(e)}"
    
    def _analizar_metadatos(self):
        """Analiza metadatos inteligentes de cada columna"""
        self.metadata = {}
        
        # Mapeo de nombres de columnas reales de LIVO
        columnas_clave = [
            'fecha', 'año_corrido', 'doce_meses', 'regional', 'departamento', 
            'divipola', 'ciudad', 'zona', 'barrio', 'estrato', 
            'destino_etapa', 'uso_etapa', 'compania_constructora', 'nit_constructora',
            'modalidad', 'tipo_vivienda', 'estado', 'fase', 'last_estado',
            'identificador', 'nuevorango_pre', 'rangos_decreto_pre', 'rango_minviv',
            'rango_ppm2', 'rango_area', 'AM_capital', 'segmento_pre', 'usos',
            'politica_vivienda', 'unidades', 'area', 'valor', 'precio_mc_promedio', 'cuenta'
        ]
        
        for col in self.schema_info['columns']:
            try:
                # Tipo SQL
                tipo_sql = self.schema_info['types'].get(col, 'UNKNOWN')
                
                # Detectar tipo Python
                if 'INT' in tipo_sql.upper() or 'BIGINT' in tipo_sql.upper():
                    tipo_python = 'integer'
                elif 'DOUBLE' in tipo_sql.upper() or 'FLOAT' in tipo_sql.upper() or 'DECIMAL' in tipo_sql.upper():
                    tipo_python = 'float'
                elif 'BOOL' in tipo_sql.upper():
                    tipo_python = 'boolean'
                elif 'DATE' in tipo_sql.upper() or 'TIME' in tipo_sql.upper():
                    tipo_python = 'datetime'
                else:
                    tipo_python = 'string'
                
                # Contar valores únicos (solo para columnas categóricas)
                valores_unicos = None
                ejemplos = []
                valores_completos = []  # Lista completa de valores únicos
                
                if tipo_python == 'string':
                    # Contar valores únicos
                    count_query = f"SELECT COUNT(DISTINCT {col}) FROM livo WHERE {col} IS NOT NULL"
                    valores_unicos = self.conn.execute(count_query).fetchone()[0]
                    
                    # Si tiene pocos valores únicos (<100), obtener TODOS los valores
                    if valores_unicos and valores_unicos < 100:
                        valores_query = f"SELECT DISTINCT {col} FROM livo WHERE {col} IS NOT NULL ORDER BY {col}"
                        valores_completos = [row[0] for row in self.conn.execute(valores_query).fetchall()]
                        ejemplos = valores_completos[:10]  # Primeros 10 como ejemplos
                    elif valores_unicos and valores_unicos < 500:
                        # Si tiene entre 100-500, obtener muestra representativa
                        ejemplos_query = f"SELECT DISTINCT {col} FROM livo WHERE {col} IS NOT NULL ORDER BY {col} LIMIT 20"
                        ejemplos = [row[0] for row in self.conn.execute(ejemplos_query).fetchall()]
                
                # Rangos para numéricos
                min_val = None
                max_val = None
                if tipo_python in ['integer', 'float']:
                    try:
                        stats_query = f"SELECT MIN({col}), MAX({col}) FROM livo WHERE {col} IS NOT NULL"
                        min_val, max_val = self.conn.execute(stats_query).fetchone()
                    except:
                        pass
                
                # Determinar criterios de uso
                filtrable = True  # Todas las columnas son filtrables
                agregable = tipo_python == 'string' and valores_unicos and valores_unicos < 500
                calculable = tipo_python in ['integer', 'float']
                
                # Determinar funciones de agregación aplicables
                funciones_agregacion = []
                if calculable:
                    funciones_agregacion = ['SUM', 'AVG', 'MIN', 'MAX', 'COUNT']
                elif tipo_python == 'string':
                    funciones_agregacion = ['COUNT']
                elif tipo_python == 'datetime':
                    funciones_agregacion = ['MIN', 'MAX', 'COUNT']
                
                # Guardar metadatos completos
                self.metadata[col] = {
                    'tipo_sql': tipo_sql,
                    'tipo_python': tipo_python,
                    'valores_unicos': valores_unicos,
                    'ejemplos': ejemplos,
                    'valores_completos': valores_completos,  # Lista completa de opciones
                    'min': min_val,
                    'max': max_val,
                    # Criterios de uso
                    'filtrable': filtrable,
                    'agregable': agregable,
                    'calculable': calculable,
                    'funciones_agregacion': funciones_agregacion
                }
                
            except Exception as e:
                print(f"⚠️ Error analizando {col}: {e}")
                self.metadata[col] = {
                    'tipo_sql': tipo_sql,
                    'tipo_python': 'unknown',
                    'valores_unicos': None,
                    'ejemplos': [],
                    'valores_completos': [],
                    'min': None,
                    'max': None,
                    'filtrable': False,
                    'agregable': False,
                    'calculable': False,
                    'funciones_agregacion': []
                }
        
        print(f"✅ Metadatos analizados para {len(self.metadata)} columnas")
    
    def _formatear_columnas(self) -> str:
        """Formatea las columnas con sus tipos para el prompt"""
        columnas_formateadas = []
        for col in self.schema_info['columns'][:20]:  # Primeras 20 columnas
            tipo = self.schema_info['types'].get(col, 'UNKNOWN')
            columnas_formateadas.append(f"  - {col} ({tipo})")
        return '\n'.join(columnas_formateadas)
    
    def _generar_diccionario_sinonimos(self) -> str:
        """Genera diccionario de sinónimos para el prompt"""
        sinonimos_text = "DICCIONARIO DE SINÓNIMOS (el usuario puede usar estos términos):\n\n"
        
        for campo, sinonimos in self.SINONIMOS.items():
            if campo in self.metadata:
                sinonimos_str = ", ".join(sinonimos[:5])  # Primeros 5 sinónimos
                sinonimos_text += f"  - '{campo}' también se puede referir como: {sinonimos_str}\n"
        
        sinonimos_text += "\n⚠️ IMPORTANTE: Cuando el usuario use estos términos, traduce al nombre de columna correcto.\n\n"
        
        # Agregar contexto específico sobre tipos de vivienda
        sinonimos_text += self._generar_contexto_tipos_vivienda()
        
        return sinonimos_text
    
    def _generar_contexto_tipos_vivienda(self) -> str:
        """Genera contexto detallado sobre VIS, VIP y No VIS"""
        contexto = """CONTEXTO IMPORTANTE - TIPOS DE VIVIENDA EN COLOMBIA:

═══ VIP (Vivienda de Interés Prioritario) ═══
- Valor máximo: 90 SMMLV (Salarios Mínimos Mensuales Legales Vigentes)
- Público objetivo: Personas con ingresos más bajos o en situación de vulnerabilidad
- Subsidios: Elegibles para subsidios gubernamentales
- Características: Área de construcción mínima, estacionamientos, equipamiento comunal

═══ VIS (Vivienda de Interés Social) ═══
- Valor máximo: 135 o 150 SMMLV (según municipio)
- Público objetivo: Familias con ingresos bajos a medios
- Subsidios: Elegibles para subsidios del gobierno nacional y cajas de compensación familiar
- Características: Deben cumplir características establecidas por el gobierno

═══ No VIS (No Vivienda de Interés Social) ═══
- Valor: Superior a 150 SMMLV
- Público objetivo: Familias con ingresos medios y altos
- Subsidios: Generalmente no elegibles para subsidios
- Características: Vivienda sin restricciones de interés social

CUANDO EL USUARIO PREGUNTE:
- "VIS" o "vivienda de interés social" → Usar: tipo_vivienda = 'VIS'
- "VIP" o "vivienda prioritaria" → Usar: tipo_vivienda = 'VIP'
- "No VIS" o "vivienda no social" → Usar: tipo_vivienda = 'No VIS'

"""
        return contexto
    
    def _generar_schema_inteligente(self) -> str:
        """Genera descripción inteligente del schema con metadatos y criterios de uso"""
        schema_text = "ESQUEMA DE DATOS LIVO (Licencias de Construcción):\n\n"
        
        # Separar por criterios de uso
        campos_filtro = []  # Campos categóricos para filtrar
        campos_agregacion = []  # Campos para agrupar
        campos_calculo = []  # Campos numéricos para calcular
        
        for col, meta in self.metadata.items():
            tipo = meta['tipo_python']
            
            # CAMPOS CATEGÓRICOS (para filtros y agrupación)
            if tipo == 'string' and meta['agregable']:
                if meta['valores_completos']:
                    # Mostrar TODOS los valores disponibles
                    valores_str = ", ".join([str(v) for v in meta['valores_completos']])
                    campos_filtro.append(
                        f"  - {col}:\n" +
                        f"    Tipo: CATEGÓRICO\n" +
                        f"    Valores disponibles ({len(meta['valores_completos'])}): {valores_str}\n" +
                        f"    Uso: Filtrar (WHERE), Agrupar (GROUP BY)\n" +
                        f"    Funciones: {', '.join(meta['funciones_agregacion'])}"
                    )
                elif meta['valores_unicos'] and meta['valores_unicos'] < 500:
                    campos_filtro.append(
                        f"  - {col}:\n" +
                        f"    Tipo: CATEGÓRICO\n" +
                        f"    Valores únicos: {meta['valores_unicos']}\n" +
                        f"    Ejemplos: {', '.join([str(e) for e in meta['ejemplos'][:10]])}\n" +
                        f"    Uso: Filtrar (WHERE), Agrupar (GROUP BY)\n" +
                        f"    Funciones: {', '.join(meta['funciones_agregacion'])}"
                    )
            
            # CAMPOS DE TEXTO LIBRE (solo para filtros)
            elif tipo == 'string' and not meta['agregable']:
                campos_filtro.append(
                    f"  - {col}:\n" +
                    f"    Tipo: TEXTO LIBRE\n" +
                    f"    Valores únicos: {meta['valores_unicos'] or 'Muchos'}\n" +
                    f"    Uso: Filtrar con LIKE (WHERE UPPER({col}) LIKE UPPER('%valor%'))\n" +
                    f"    Funciones: {', '.join(meta['funciones_agregacion'])}"
                )
            
            # CAMPOS NUMÉRICOS (para cálculos)
            elif tipo in ['integer', 'float'] and meta['calculable']:
                campos_calculo.append(
                    f"  - {col}:\n" +
                    f"    Tipo: NUMÉRICO\n" +
                    f"    Rango: [{meta['min']:.2f} - {meta['max']:.2f}]\n" +
                    f"    Uso: Calcular, Filtrar (WHERE {col} > valor)\n" +
                    f"    Funciones: {', '.join(meta['funciones_agregacion'])}"
                )
            
            # CAMPOS DE FECHA
            elif tipo == 'datetime':
                campos_filtro.append(
                    f"  - {col}:\n" +
                    f"    Tipo: FECHA\n" +
                    f"    Uso: Filtrar (WHERE, BETWEEN)\n" +
                    f"    Funciones: {', '.join(meta['funciones_agregacion'])}"
                )
        
        # Construir schema organizado
        if campos_filtro:
            schema_text += "═══ CAMPOS PARA FILTROS Y AGRUPACIÓN ═══\n\n"
            schema_text += "\n\n".join(campos_filtro[:10]) + "\n\n"
        
        if campos_calculo:
            schema_text += "═══ CAMPOS NUMÉRICOS PARA CÁLCULOS ═══\n\n"
            schema_text += "\n\n".join(campos_calculo[:8]) + "\n\n"
        
        return schema_text
    
    def consultar(self, pregunta: str, llm_function, usuario: str = "default") -> Tuple[bool, str]:
        """Consulta usando Text-to-SQL con LLM (con mejoras integradas)"""
        if not self.conn:
            return False, "❌ Sistema no inicializado"
        
        # MEJORA 1: Detección de idioma y traducción
        pregunta_original = pregunta
        pregunta, fue_traducida = self.traducir_pregunta(pregunta, llm_function)
        if fue_traducida:
            print(f"🌍 Pregunta traducida: {pregunta}")
        
        # MEJORA 2: Detección de ambigüedades
        tiene_ambiguedades, ambiguedades = self.detectar_ambiguedades(pregunta)
        if tiene_ambiguedades:
            mensaje_ambiguedad = "⚠️ **Tu pregunta podría ser más específica:**\n\n"
            for amb in ambiguedades:
                mensaje_ambiguedad += f"- {amb}\n"
            mensaje_ambiguedad += "\n🔄 **Intentaré responder con los datos disponibles...**\n\n"
            # No retornar, solo advertir
            print(mensaje_ambiguedad)
        
        # MEJORA 3: Buscar en caché
        cache_result = self._buscar_en_cache(pregunta)
        if cache_result:
            print(f"⚡ Usando resultado cacheado (guardado: {cache_result['timestamp']})")
            sql_cacheado = cache_result['sql']
            
            # Ejecutar SQL cacheado
            try:
                result = self.conn.execute(sql_cacheado).fetchall()
                columns = [desc[0] for desc in self.conn.description]
                
                # Formatear resultados
                respuesta = self._formatear_resultados(result, columns, sql_cacheado)
                
                # Agregar badge de caché
                respuesta = f"⚡ **Resultado cacheado (ultra rápido)**\n\n{respuesta}"
                
                # MEJORA 4: Explicación del SQL
                explicacion = self.explicar_sql(sql_cacheado, llm_function)
                respuesta += f"\n\n💡 **Qué hice:** {explicacion}"
                
                # MEJORA 5: Sugerencias de preguntas relacionadas
                sugerencias = self.generar_preguntas_relacionadas(pregunta, respuesta, llm_function)
                if sugerencias:
                    respuesta += "\n\n💭 **Preguntas relacionadas que podrías hacer:**\n"
                    for i, sug in enumerate(sugerencias, 1):
                        respuesta += f"{i}. {sug}\n"
                
                return True, respuesta
                
            except Exception as e:
                print(f"⚠️ SQL cacheado falló, regenerando: {e}")
                # Continuar con generación normal
        
        # 1. Generar componentes del prompt
        schema_inteligente = self._generar_schema_inteligente()
        diccionario_sinonimos = self._generar_diccionario_sinonimos()
        contexto_tipos = self._generar_contexto_tipos_vivienda()
        
        # 2. Construir prompt completo
        prompt = f"""Eres un experto en SQL y datos de licencias de construcción (LIVO) en Colombia.

{schema_inteligente}

{diccionario_sinonimos}

REGLAS CRÍTICAS:
1. CAMPOS CATEGÓRICOS: Usa EXACTAMENTE los valores listados (respeta mayúsculas/minúsculas)
2. FILTROS DE TEXTO: UPPER(columna) LIKE UPPER('%valor%') para búsquedas flexibles
3. CAMPOS NUMÉRICOS: Usa operadores =, >, <, >=, <= (NUNCA LIKE)
4. AGREGACIONES: Usa las funciones indicadas (SUM, AVG, COUNT, MIN, MAX)
5. AGRUPACIÓN: GROUP BY para categorizar resultados
6. ORDENAMIENTO: ORDER BY ... DESC para rankings
7. LÍMITE: LIMIT N para top N resultados
8. FILTROS MÚLTIPLES: Usa AND para combinar múltiples condiciones (5-7 filtros es normal)
9. CONSULTAS COMPLEJAS: Puedes combinar filtros geográficos, categóricos, numéricos y de fecha
10. CÁLCULOS MULTINIVEL: Usa CTEs (WITH) o subconsultas para cálculos anidados de 2-3 niveles
11. OPERACIONES MATEMÁTICAS: Puedes usar +, -, *, /, %, ROUND(), CAST() sobre resultados agregados
12. ESTADÍSTICAS AVANZADAS: Usa STDDEV(), VARIANCE(), PERCENTILE_CONT() cuando sea necesario

EJEMPLOS DE CONSULTAS CORRECTAS:

"Cuántas licencias en Bogotá" →
SELECT COUNT(*) FROM livo WHERE UPPER(ciudad) LIKE UPPER('%Bogotá%')

"Total unidades por ciudad" →
SELECT ciudad, SUM(unidades) as total FROM livo GROUP BY ciudad

"Licencias de tipo VIS en Medellín" →
SELECT COUNT(*) FROM livo WHERE UPPER(ciudad) LIKE UPPER('%Medellín%') AND tipo_vivienda = 'VIS'

"Área promedio por estrato" →
SELECT estrato, AVG(area) as area_promedio FROM livo GROUP BY estrato ORDER BY estrato

"Top 10 constructoras con más unidades" →
SELECT compania_constructora, SUM(unidades) as total FROM livo GROUP BY compania_constructora ORDER BY total DESC LIMIT 10

EJEMPLOS CON LENGUAJE NATURAL (usando sinónimos):

"Cuántas viviendas hay en la capital" → (viviendas=unidades, capital=ciudad)
SELECT SUM(unidades) FROM livo WHERE UPPER(ciudad) LIKE UPPER('%Bogotá%')

"Qué empresas tienen más apartamentos" → (empresas=compania_constructora, apartamentos=unidades)
SELECT compania_constructora, SUM(unidades) as total FROM livo GROUP BY compania_constructora ORDER BY total DESC LIMIT 10

"Precio promedio por metro cuadrado" → (precio por metro=precio_mc_promedio)
SELECT AVG(precio_mc_promedio) FROM livo

"Licencias en el depto de Antioquia" → (depto=departamento)
SELECT COUNT(*) FROM livo WHERE UPPER(departamento) LIKE UPPER('%Antioquia%')

"Constructoras en nivel socioeconómico 3" → (nivel socioeconómico=estrato)
SELECT DISTINCT compania_constructora FROM livo WHERE estrato = 3

EJEMPLOS DE CONSULTAS COMPLEJAS (5-7 FILTROS COMBINADOS):

"Licencias VIS en Bogotá, estrato 3, con más de 50 unidades, en zona urbana, del año 2024" →
SELECT COUNT(*), SUM(unidades) as total_unidades
FROM livo 
WHERE tipo_vivienda = 'VIS'
  AND UPPER(ciudad) LIKE UPPER('%Bogotá%')
  AND estrato = 3
  AND unidades > 50
  AND UPPER(zona) LIKE UPPER('%urbana%')
  AND YEAR(fecha) = 2024

"Top 5 constructoras con más unidades VIP en Medellín, estrato 1 o 2, área menor a 60m2, estado vigente" →
SELECT compania_constructora, SUM(unidades) as total, AVG(area) as area_promedio
FROM livo
WHERE tipo_vivienda = 'VIP'
  AND UPPER(ciudad) LIKE UPPER('%Medellín%')
  AND estrato IN (1, 2)
  AND area < 60
  AND UPPER(estado) LIKE UPPER('%vigente%')
GROUP BY compania_constructora
ORDER BY total DESC
LIMIT 5

"Total unidades No VIS en Cali, estrato 5 o 6, uso residencial, área mayor a 100m2, valor superior a 500 millones" →
SELECT SUM(unidades) as total_unidades, AVG(valor) as valor_promedio, AVG(area) as area_promedio
FROM livo
WHERE tipo_vivienda = 'No VIS'
  AND UPPER(ciudad) LIKE UPPER('%Cali%')
  AND estrato IN (5, 6)
  AND UPPER(uso_etapa) LIKE UPPER('%residencial%')
  AND area > 100
  AND valor > 500000000

"Licencias en departamento de Antioquia, regional Medellín, VIS, fase construcción, entre 20 y 100 unidades, últimos 12 meses" →
SELECT ciudad, COUNT(*) as num_licencias, SUM(unidades) as total_unidades
FROM livo
WHERE UPPER(departamento) LIKE UPPER('%Antioquia%')
  AND UPPER(regional) LIKE UPPER('%Medellín%')
  AND tipo_vivienda = 'VIS'
  AND UPPER(fase) LIKE UPPER('%construcción%')
  AND unidades BETWEEN 20 AND 100
  AND doce_meses = 1
GROUP BY ciudad
ORDER BY total_unidades DESC

EJEMPLOS DE CÁLCULOS MULTINIVEL:

--- NIVEL 1: Agregaciones básicas ---
"Total unidades por ciudad" →
SELECT ciudad, SUM(unidades) as total FROM livo GROUP BY ciudad

--- NIVEL 2: Cálculos sobre agregaciones (usando CTE) ---
"Porcentaje de unidades por ciudad respecto al total nacional" →
WITH totales_ciudad AS (
  SELECT ciudad, SUM(unidades) as total_ciudad
  FROM livo
  GROUP BY ciudad
),
total_nacional AS (
  SELECT SUM(unidades) as total FROM livo
)
SELECT 
  tc.ciudad,
  tc.total_ciudad,
  ROUND(tc.total_ciudad * 100.0 / tn.total, 2) as porcentaje
FROM totales_ciudad tc
CROSS JOIN total_nacional tn
ORDER BY porcentaje DESC

--- NIVEL 2: Diferencia vs promedio ---
"Ciudades con unidades por encima del promedio nacional" →
WITH totales AS (
  SELECT ciudad, SUM(unidades) as total
  FROM livo
  GROUP BY ciudad
),
promedio AS (
  SELECT AVG(total) as prom FROM totales
)
SELECT 
  t.ciudad,
  t.total,
  p.prom as promedio_nacional,
  ROUND(t.total - p.prom, 0) as diferencia
FROM totales t
CROSS JOIN promedio p
WHERE t.total > p.prom
ORDER BY diferencia DESC

--- NIVEL 3: Cálculos sobre cálculos (CTEs anidados) ---
"Tasa de crecimiento de unidades VIS vs No VIS por ciudad, comparando con promedio regional" →
WITH unidades_por_tipo AS (
  SELECT 
    ciudad,
    departamento,
    tipo_vivienda,
    SUM(unidades) as total
  FROM livo
  GROUP BY ciudad, departamento, tipo_vivienda
),
ratio_ciudad AS (
  SELECT 
    ciudad,
    departamento,
    SUM(CASE WHEN tipo_vivienda = 'VIS' THEN total ELSE 0 END) as vis,
    SUM(CASE WHEN tipo_vivienda = 'No VIS' THEN total ELSE 0 END) as no_vis,
    ROUND(SUM(CASE WHEN tipo_vivienda = 'VIS' THEN total ELSE 0 END) * 100.0 / 
          NULLIF(SUM(total), 0), 2) as pct_vis
  FROM unidades_por_tipo
  GROUP BY ciudad, departamento
),
promedio_regional AS (
  SELECT 
    departamento,
    AVG(pct_vis) as prom_regional
  FROM ratio_ciudad
  GROUP BY departamento
)
SELECT 
  rc.ciudad,
  rc.departamento,
  rc.vis,
  rc.no_vis,
  rc.pct_vis,
  pr.prom_regional,
  ROUND(rc.pct_vis - pr.prom_regional, 2) as diferencia_vs_regional
FROM ratio_ciudad rc
JOIN promedio_regional pr ON rc.departamento = pr.departamento
WHERE ABS(rc.pct_vis - pr.prom_regional) > 5
ORDER BY diferencia_vs_regional DESC

--- NIVEL 3: Índice compuesto (precio/m2 ajustado por estrato) ---
"Calcular índice de accesibilidad: (precio promedio / area promedio) / factor estrato" →
WITH metricas_base AS (
  SELECT 
    ciudad,
    estrato,
    AVG(precio_mc_promedio) as precio_prom,
    AVG(area) as area_prom,
    COUNT(*) as num_licencias
  FROM livo
  WHERE precio_mc_promedio > 0 AND area > 0
  GROUP BY ciudad, estrato
),
factor_estrato AS (
  SELECT 
    estrato,
    CASE 
      WHEN estrato <= 2 THEN 0.5
      WHEN estrato <= 4 THEN 1.0
      ELSE 1.5
    END as factor
  FROM (SELECT DISTINCT estrato FROM livo) e
),
indice_calculado AS (
  SELECT 
    mb.ciudad,
    mb.estrato,
    mb.precio_prom,
    mb.area_prom,
    fe.factor,
    ROUND((mb.precio_prom / NULLIF(mb.area_prom, 0)) / fe.factor, 2) as indice_accesibilidad
  FROM metricas_base mb
  JOIN factor_estrato fe ON mb.estrato = fe.estrato
)
SELECT 
  ciudad,
  estrato,
  precio_prom,
  area_prom,
  indice_accesibilidad,
  RANK() OVER (ORDER BY indice_accesibilidad) as ranking_accesibilidad
FROM indice_calculado
ORDER BY indice_accesibilidad
LIMIT 20

EJEMPLOS DE ANÁLISIS DE TENDENCIAS Y COMPORTAMIENTOS (NIVEL 3):

--- TENDENCIA 1: Serie temporal mensual con crecimiento ---
"Evolución mensual de licencias VIS en Bogotá en los últimos 12 meses con tasa de crecimiento" →
WITH serie_mensual AS (
  SELECT 
    YEAR(fecha) as anio,
    MONTH(fecha) as mes,
    DATE_TRUNC('month', fecha) as periodo,
    COUNT(*) as num_licencias,
    SUM(unidades) as total_unidades
  FROM livo
  WHERE tipo_vivienda = 'VIS'
    AND UPPER(ciudad) LIKE UPPER('%Bogotá%')
    AND fecha >= CURRENT_DATE - INTERVAL '12 months'
  GROUP BY YEAR(fecha), MONTH(fecha), DATE_TRUNC('month', fecha)
),
con_lag AS (
  SELECT 
    periodo,
    anio,
    mes,
    num_licencias,
    total_unidades,
    LAG(total_unidades) OVER (ORDER BY periodo) as unidades_mes_anterior
  FROM serie_mensual
)
SELECT 
  periodo,
  anio,
  mes,
  num_licencias,
  total_unidades,
  unidades_mes_anterior,
  ROUND((total_unidades - unidades_mes_anterior) * 100.0 / NULLIF(unidades_mes_anterior, 0), 2) as tasa_crecimiento_mom,
  SUM(total_unidades) OVER (ORDER BY periodo ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) / 3 as promedio_movil_3m
FROM con_lag
ORDER BY periodo

--- TENDENCIA 2: Comparación Year-over-Year (YoY) ---
"Comparar unidades VIS por ciudad: 2024 vs 2023 con variación porcentual" →
WITH unidades_2023 AS (
  SELECT ciudad, SUM(unidades) as unidades_2023
  FROM livo
  WHERE YEAR(fecha) = 2023 AND tipo_vivienda = 'VIS'
  GROUP BY ciudad
),
unidades_2024 AS (
  SELECT ciudad, SUM(unidades) as unidades_2024
  FROM livo
  WHERE YEAR(fecha) = 2024 AND tipo_vivienda = 'VIS'
  GROUP BY ciudad
)
SELECT 
  COALESCE(u23.ciudad, u24.ciudad) as ciudad,
  COALESCE(u23.unidades_2023, 0) as unidades_2023,
  COALESCE(u24.unidades_2024, 0) as unidades_2024,
  COALESCE(u24.unidades_2024, 0) - COALESCE(u23.unidades_2023, 0) as diferencia_absoluta,
  ROUND((COALESCE(u24.unidades_2024, 0) - COALESCE(u23.unidades_2023, 0)) * 100.0 / 
        NULLIF(u23.unidades_2023, 0), 2) as variacion_yoy_pct
FROM unidades_2023 u23
FULL OUTER JOIN unidades_2024 u24 ON u23.ciudad = u24.ciudad
WHERE COALESCE(u23.unidades_2023, 0) > 0 OR COALESCE(u24.unidades_2024, 0) > 0
ORDER BY variacion_yoy_pct DESC

--- TENDENCIA 3: Análisis de estacionalidad trimestral ---
"Patrón estacional de licencias por trimestre en los últimos 3 años" →
WITH datos_trimestrales AS (
  SELECT 
    YEAR(fecha) as anio,
    QUARTER(fecha) as trimestre,
    COUNT(*) as num_licencias,
    SUM(unidades) as total_unidades
  FROM livo
  WHERE fecha >= CURRENT_DATE - INTERVAL '3 years'
  GROUP BY YEAR(fecha), QUARTER(fecha)
),
promedio_por_trimestre AS (
  SELECT 
    trimestre,
    AVG(total_unidades) as promedio_trimestral,
    STDDEV(total_unidades) as desviacion_trimestral
  FROM datos_trimestrales
  GROUP BY trimestre
)
SELECT 
  dt.anio,
  dt.trimestre,
  dt.num_licencias,
  dt.total_unidades,
  pt.promedio_trimestral,
  ROUND((dt.total_unidades - pt.promedio_trimestral) * 100.0 / pt.promedio_trimestral, 2) as desviacion_pct,
  CASE 
    WHEN dt.total_unidades > pt.promedio_trimestral + pt.desviacion_trimestral THEN 'Alto'
    WHEN dt.total_unidades < pt.promedio_trimestral - pt.desviacion_trimestral THEN 'Bajo'
    ELSE 'Normal'
  END as clasificacion_estacional
FROM datos_trimestrales dt
JOIN promedio_por_trimestre pt ON dt.trimestre = pt.trimestre
ORDER BY dt.anio, dt.trimestre

--- TENDENCIA 4: Ranking dinámico de ciudades por periodo ---
"Ranking de ciudades por unidades cada año, mostrando cambios de posición" →
WITH unidades_anuales AS (
  SELECT 
    YEAR(fecha) as anio,
    ciudad,
    SUM(unidades) as total_unidades
  FROM livo
  WHERE YEAR(fecha) >= 2020
  GROUP BY YEAR(fecha), ciudad
),
con_ranking AS (
  SELECT 
    anio,
    ciudad,
    total_unidades,
    RANK() OVER (PARTITION BY anio ORDER BY total_unidades DESC) as ranking_anio,
    LAG(RANK() OVER (PARTITION BY anio ORDER BY total_unidades DESC)) 
      OVER (PARTITION BY ciudad ORDER BY anio) as ranking_anio_anterior
  FROM unidades_anuales
)
SELECT 
  anio,
  ciudad,
  total_unidades,
  ranking_anio,
  ranking_anio_anterior,
  CASE 
    WHEN ranking_anio_anterior IS NULL THEN 'Nueva'
    WHEN ranking_anio < ranking_anio_anterior THEN 'Subió ' || (ranking_anio_anterior - ranking_anio) || ' posiciones'
    WHEN ranking_anio > ranking_anio_anterior THEN 'Bajó ' || (ranking_anio - ranking_anio_anterior) || ' posiciones'
    ELSE 'Mantuvo posición'
  END as cambio_ranking
FROM con_ranking
WHERE ranking_anio <= 10
ORDER BY anio DESC, ranking_anio

--- TENDENCIA 5: Concentración de mercado (HHI - Herfindahl Index) ---
"Calcular índice de concentración de mercado por constructoras a lo largo del tiempo" →
WITH participacion_anual AS (
  SELECT 
    YEAR(fecha) as anio,
    compania_constructora,
    SUM(unidades) as unidades_constructora
  FROM livo
  WHERE YEAR(fecha) >= 2020
  GROUP BY YEAR(fecha), compania_constructora
),
total_anual AS (
  SELECT anio, SUM(unidades_constructora) as total_mercado
  FROM participacion_anual
  GROUP BY anio
),
participacion_pct AS (
  SELECT 
    pa.anio,
    pa.compania_constructora,
    pa.unidades_constructora,
    ta.total_mercado,
    (pa.unidades_constructora * 100.0 / ta.total_mercado) as participacion_pct
  FROM participacion_anual pa
  JOIN total_anual ta ON pa.anio = ta.anio
),
hhi_anual AS (
  SELECT 
    anio,
    SUM(participacion_pct * participacion_pct) as hhi,
    COUNT(DISTINCT compania_constructora) as num_constructoras
  FROM participacion_pct
  GROUP BY anio
)
SELECT 
  anio,
  ROUND(hhi, 2) as indice_herfindahl,
  num_constructoras,
  CASE 
    WHEN hhi < 1500 THEN 'Mercado competitivo'
    WHEN hhi < 2500 THEN 'Mercado moderadamente concentrado'
    ELSE 'Mercado altamente concentrado'
  END as clasificacion_mercado,
  LAG(hhi) OVER (ORDER BY anio) as hhi_anio_anterior,
  ROUND(hhi - LAG(hhi) OVER (ORDER BY anio), 2) as cambio_concentracion
FROM hhi_anual
ORDER BY anio

EJEMPLOS DE ANÁLISIS AVANZADO NIVEL 4 (MODELOS PREDICTIVOS Y SIMULACIONES):

--- NIVEL 4.1: Modelo predictivo simple (proyección lineal) ---
WITH datos_historicos AS (
  SELECT 
    YEAR(fecha) as anio,
    SUM(unidades) as total_unidades
  FROM livo
  WHERE tipo_vivienda = 'VIS'
    AND YEAR(fecha) BETWEEN 2021 AND 2024
  GROUP BY YEAR(fecha)
),
regresion_lineal AS (
  SELECT 
    anio,
    total_unidades,
    AVG(total_unidades) OVER () as promedio_y,
    AVG(anio) OVER () as promedio_x,
    (anio - AVG(anio) OVER ()) * (total_unidades - AVG(total_unidades) OVER ()) as numerador,
    (anio - AVG(anio) OVER ()) * (anio - AVG(anio) OVER ()) as denominador
  FROM datos_historicos
),
coeficientes AS (
  SELECT 
    SUM(numerador) / NULLIF(SUM(denominador), 0) as pendiente,
    AVG(promedio_y) - (SUM(numerador) / NULLIF(SUM(denominador), 0)) * AVG(promedio_x) as intercepto
  FROM regresion_lineal
),
proyeccion AS (
  SELECT 
    2025 as anio,
    ROUND(c.intercepto + c.pendiente * 2025, 0) as proyeccion_2025,
    c.pendiente,
    c.intercepto
  FROM coeficientes c
)
SELECT 
  dh.anio,
  dh.total_unidades as real,
  NULL as proyeccion,
  'Histórico' as tipo
FROM datos_historicos dh
UNION ALL
SELECT 
  p.anio,
  NULL as real,
  p.proyeccion_2025 as proyeccion,
  'Proyección' as tipo
FROM proyeccion p
ORDER BY anio

--- NIVEL 4.2: Índice compuesto multidimensional (scoring de ciudades) ---
WITH metricas_volumen AS (
  SELECT 
    ciudad,
    SUM(unidades) as total_unidades,
    COUNT(DISTINCT compania_constructora) as num_constructoras,
    AVG(precio_mc_promedio) as precio_promedio
  FROM livo
  WHERE doce_meses = 1
  GROUP BY ciudad
),
metricas_crecimiento AS (
  SELECT 
    ciudad,
    SUM(CASE WHEN YEAR(fecha) = 2024 THEN unidades ELSE 0 END) as unidades_2024,
    SUM(CASE WHEN YEAR(fecha) = 2023 THEN unidades ELSE 0 END) as unidades_2023,
    ROUND((SUM(CASE WHEN YEAR(fecha) = 2024 THEN unidades ELSE 0 END) - 
           SUM(CASE WHEN YEAR(fecha) = 2023 THEN unidades ELSE 0 END)) * 100.0 / 
           NULLIF(SUM(CASE WHEN YEAR(fecha) = 2023 THEN unidades ELSE 0 END), 0), 2) as tasa_crecimiento
  FROM livo
  GROUP BY ciudad
),
metricas_diversificacion AS (
  SELECT 
    ciudad,
    COUNT(DISTINCT tipo_vivienda) as tipos_vivienda,
    COUNT(DISTINCT estrato) as estratos_atendidos,
    STDDEV(unidades) as volatilidad
  FROM livo
  WHERE doce_meses = 1
  GROUP BY ciudad
),
metricas_normalizadas AS (
  SELECT 
    mv.ciudad,
    -- Normalizar volumen (0-100)
    ROUND((mv.total_unidades - MIN(mv.total_unidades) OVER ()) * 100.0 / 
          NULLIF(MAX(mv.total_unidades) OVER () - MIN(mv.total_unidades) OVER (), 0), 2) as score_volumen,
    -- Normalizar crecimiento (0-100)
    ROUND((mc.tasa_crecimiento - MIN(mc.tasa_crecimiento) OVER ()) * 100.0 / 
          NULLIF(MAX(mc.tasa_crecimiento) OVER () - MIN(mc.tasa_crecimiento) OVER (), 0), 2) as score_crecimiento,
    -- Normalizar diversificación (0-100)
    ROUND((md.num_constructoras - MIN(md.num_constructoras) OVER ()) * 100.0 / 
          NULLIF(MAX(md.num_constructoras) OVER () - MIN(md.num_constructoras) OVER (), 0), 2) as score_diversificacion,
    -- Normalizar precio (inverso, menor precio = mayor score)
    ROUND((MAX(mv.precio_promedio) OVER () - mv.precio_promedio) * 100.0 / 
          NULLIF(MAX(mv.precio_promedio) OVER () - MIN(mv.precio_promedio) OVER (), 0), 2) as score_precio,
    mv.total_unidades,
    mc.tasa_crecimiento,
    md.num_constructoras,
    mv.precio_promedio
  FROM metricas_volumen mv
  JOIN metricas_crecimiento mc ON mv.ciudad = mc.ciudad
  JOIN metricas_diversificacion md ON mv.ciudad = md.ciudad
  WHERE mv.total_unidades > 100
),
indice_final AS (
  SELECT 
    ciudad,
    total_unidades,
    tasa_crecimiento,
    num_constructoras,
    precio_promedio,
    score_volumen,
    score_crecimiento,
    score_diversificacion,
    score_precio,
    -- Índice compuesto con pesos: 30% volumen, 30% crecimiento, 25% diversificación, 15% precio
    ROUND((score_volumen * 0.30 + score_crecimiento * 0.30 + score_diversificacion * 0.25 + score_precio * 0.15), 2) as indice_atractivo,
    RANK() OVER (ORDER BY (score_volumen * 0.30 + score_crecimiento * 0.30 + score_diversificacion * 0.25 + score_precio * 0.15) DESC) as ranking
  FROM metricas_normalizadas
)
SELECT 
  ciudad,
  indice_atractivo,
  ranking,
  total_unidades,
  tasa_crecimiento,
  num_constructoras,
  precio_promedio,
  CASE 
    WHEN indice_atractivo >= 75 THEN 'Muy Atractivo'
    WHEN indice_atractivo >= 50 THEN 'Atractivo'
    WHEN indice_atractivo >= 25 THEN 'Moderado'
    ELSE 'Bajo Atractivo'
  END as clasificacion
FROM indice_final
ORDER BY indice_atractivo DESC
LIMIT 20

--- NIVEL 4.3: Análisis multidimensional (cubo OLAP simplificado) ---
WITH datos_base AS (
  SELECT 
    ciudad,
    tipo_vivienda,
    estrato,
    YEAR(fecha) as anio,
    SUM(unidades) as total_unidades
  FROM livo
  WHERE YEAR(fecha) >= 2022
    AND ciudad IN ('Bogotá', 'Medellín', 'Cali', 'Barranquilla')
  GROUP BY ciudad, tipo_vivienda, estrato, YEAR(fecha)
),
con_totales AS (
  SELECT 
    ciudad,
    tipo_vivienda,
    estrato,
    anio,
    total_unidades,
    -- Total por ciudad-tipo-estrato (todos los años)
    SUM(total_unidades) OVER (PARTITION BY ciudad, tipo_vivienda, estrato) as total_ciudad_tipo_estrato,
    -- Total por ciudad-tipo (todos estratos y años)
    SUM(total_unidades) OVER (PARTITION BY ciudad, tipo_vivienda) as total_ciudad_tipo,
    -- Total por ciudad (todo)
    SUM(total_unidades) OVER (PARTITION BY ciudad) as total_ciudad,
    -- Total general
    SUM(total_unidades) OVER () as total_general
  FROM datos_base
)
SELECT 
  ciudad,
  tipo_vivienda,
  estrato,
  anio,
  total_unidades,
  ROUND(total_unidades * 100.0 / NULLIF(total_ciudad_tipo_estrato, 0), 2) as pct_del_periodo,
  ROUND(total_unidades * 100.0 / NULLIF(total_ciudad_tipo, 0), 2) as pct_del_tipo,
  ROUND(total_unidades * 100.0 / NULLIF(total_ciudad, 0), 2) as pct_de_ciudad,
  ROUND(total_unidades * 100.0 / NULLIF(total_general, 0), 2) as pct_del_total
FROM con_totales
ORDER BY ciudad, tipo_vivienda, estrato, anio

--- NIVEL 4.4: Simulación de escenarios (what-if analysis) ---
WITH escenario_actual AS (
  SELECT 
    'Actual' as escenario,
    tipo_vivienda,
    SUM(unidades) as total_unidades,
    AVG(precio_mc_promedio) as precio_promedio,
    COUNT(*) as num_licencias
  FROM livo
  WHERE UPPER(ciudad) LIKE UPPER('%Bogotá%')
    AND doce_meses = 1
  GROUP BY tipo_vivienda
),
escenario_simulado AS (
  SELECT 
    'Simulado (+20% VIS, -10% No VIS)' as escenario,
    tipo_vivienda,
    CASE 
      WHEN tipo_vivienda = 'VIS' THEN ROUND(total_unidades * 1.20, 0)
      WHEN tipo_vivienda = 'No VIS' THEN ROUND(total_unidades * 0.90, 0)
      ELSE total_unidades
    END as total_unidades,
    precio_promedio,
    CASE 
      WHEN tipo_vivienda = 'VIS' THEN ROUND(num_licencias * 1.20, 0)
      WHEN tipo_vivienda = 'No VIS' THEN ROUND(num_licencias * 0.90, 0)
      ELSE num_licencias
    END as num_licencias
  FROM escenario_actual
),
comparacion AS (
  SELECT 
    ea.tipo_vivienda,
    ea.total_unidades as unidades_actual,
    es.total_unidades as unidades_simulado,
    es.total_unidades - ea.total_unidades as diferencia_absoluta,
    ROUND((es.total_unidades - ea.total_unidades) * 100.0 / ea.total_unidades, 2) as diferencia_pct,
    ea.precio_promedio,
    ea.num_licencias as licencias_actual,
    es.num_licencias as licencias_simulado
  FROM escenario_actual ea
  JOIN escenario_simulado es ON ea.tipo_vivienda = es.tipo_vivienda
)
SELECT 
  tipo_vivienda,
  unidades_actual,
  unidades_simulado,
  diferencia_absoluta,
  diferencia_pct,
  precio_promedio,
  licencias_actual,
  licencias_simulado,
  ROUND(unidades_simulado * 100.0 / SUM(unidades_simulado) OVER (), 2) as participacion_simulada
FROM comparacion
ORDER BY tipo_vivienda

PREGUNTA DEL USUARIO: {pregunta}

Genera SOLO el SQL (sin explicaciones, sin markdown, sin comentarios):
"""
        
        # 3. Generar SQL con LLM

        respuesta_llm, _ = llm_function(prompt)
        if not respuesta_llm:
            return False, " Error al generar SQL"
        sql = respuesta_llm.strip().replace('```sql', '').replace('```', '').strip()
        
        sql = '\n'.join([line for line in sql.split('\n') if not line.strip().startswith('--')])
        sql = sql.strip()
        
        if ';' in sql:
            sql = sql.split(';')[0].strip()
            print(f"⚠️ Múltiples sentencias detectadas, usando solo la primera")
        
        if len(sql) > 500:
            print(f"⚠️ SQL muy largo ({len(sql)} chars), verificando...")
        
        print(f"\n📊 SQL: {sql}\n")
        
        try:
            result = self.conn.execute(sql).fetchall()
            columns = [desc[0] for desc in self.conn.description]
            
            if len(columns) == 1 and len(result) == 1:
                valor = result[0][0]
                if isinstance(valor, (int, float)):
                    return True, f"📊 **Resultado:** {valor:,.0f}"
                else:
                    return True, f"📊 **Resultado:** {valor}"
            
            respuesta = f"📊 **Resultados ({len(result)} registros):**\n\n"
            respuesta += "| " + " | ".join(columns) + " |\n"
            respuesta += "| " + " | ".join(["---"] * len(columns)) + " |\n"
            
            for row in result[:10]:
                respuesta += "| " + " | ".join([str(v) for v in row]) + " |\n"
            
            if len(result) > 10:
                respuesta += f"\n_Mostrando 10 de {len(result)}_\n"
            
            respuesta += f"\n```sql\n{sql}\n```"
            return True, respuesta
            
        except Exception as e:
            return False, f"❌ Error SQL: {str(e)}"
    
    def _cargar_cache(self):
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache_consultas = json.load(f)
                print(f"✅ Caché cargado: {len(self.cache_consultas)} consultas")
        except Exception as e:
            print(f"⚠️ Error cargando caché: {e}")
            self.cache_consultas = {}
    
    def _guardar_cache(self):
        """Guarda caché de consultas en archivo"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_consultas, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Error guardando caché: {e}")
    
    def _obtener_hash_pregunta(self, pregunta: str) -> str:
        """Genera hash único de la pregunta para caché"""
        return hashlib.md5(pregunta.lower().strip().encode()).hexdigest()
    
    def _buscar_en_cache(self, pregunta: str) -> Optional[Dict[str, Any]]:
        """Busca consulta en caché"""
        hash_pregunta = self._obtener_hash_pregunta(pregunta)
        return self.cache_consultas.get(hash_pregunta)
    
    def _guardar_en_cache(self, pregunta: str, sql: str, exito: bool, resultado: str = ""):
        """Guarda consulta exitosa en caché"""
        if exito:  # Solo cachear consultas exitosas
            hash_pregunta = self._obtener_hash_pregunta(pregunta)
            self.cache_consultas[hash_pregunta] = {
                'pregunta': pregunta,
                'sql': sql,
                'timestamp': datetime.now().isoformat(),
                'resultado_preview': resultado[:200] if resultado else ""
            }
            self._guardar_cache()
    
    def _cargar_historial(self):
        """Carga historial de consultas desde archivo"""
        try:
            if self.historial_file.exists():
                with open(self.historial_file, 'r', encoding='utf-8') as f:
                    self.historial = json.load(f)
                print(f"✅ Historial cargado: {len(self.historial)} consultas")
        except Exception as e:
            print(f"⚠️ Error cargando historial: {e}")
            self.historial = []
    
    def _guardar_historial(self):
        """Guarda historial de consultas en archivo"""
        try:
            with open(self.historial_file, 'w', encoding='utf-8') as f:
                json.dump(self.historial, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Error guardando historial: {e}")
    
    def _agregar_a_historial(self, pregunta: str, sql: str, exito: bool, error: str = "", usuario: str = "default"):
        """Agrega consulta al historial"""
        entrada = {
            'timestamp': datetime.now().isoformat(),
            'usuario': usuario,
            'pregunta': pregunta,
            'sql': sql,
            'exito': exito,
            'error': error if not exito else ""
        }
        self.historial.append(entrada)
        
        # Mantener solo últimas 100 consultas
        if len(self.historial) > 100:
            self.historial = self.historial[-100:]
        
        self._guardar_historial()
    
    def detectar_idioma(self, texto: str) -> str:
        """Detecta el idioma del texto"""
        if not LANGDETECT_AVAILABLE:
            return 'es'  # Asumir español por defecto
        
        try:
            idioma = detect(texto)
            return idioma
        except LangDetectException:
            return 'es'
    
    def traducir_pregunta(self, pregunta: str, llm_function) -> Tuple[str, bool]:
        """Traduce pregunta a español si está en otro idioma"""
        idioma = self.detectar_idioma(pregunta)
        
        if idioma == 'es':
            return pregunta, False
        
        # Traducir usando LLM
        prompt_traduccion = f"""Traduce la siguiente pregunta al español: {pregunta} Traducción en español (solo la traducción, sin explicaciones):"""
        traduccion, _ = llm_function(prompt_traduccion)
        if traduccion:
            return traduccion.strip(), True
        else:
            return pregunta, False
    def detectar_ambiguedades(self, pregunta: str) -> Tuple[bool, List[str]]:
        """Detecta si la pregunta necesita aclaración"""
        ambiguedades = []
        pregunta_lower = pregunta.lower()
        
        # Detectar falta de periodo temporal
        palabras_temporales = ['año', 'mes', '2024', '2023', '2022', 'últimos', 'reciente', 'actual', 'doce_meses', 'trimestre']
        if not any(palabra in pregunta_lower for palabra in palabras_temporales):
            if any(palabra in pregunta_lower for palabra in ['tendencia', 'evolución', 'crecimiento', 'comparación']):
                ambiguedades.append("📅 **Periodo temporal no especificado.** ¿Qué periodo? (ej: 2024, últimos 12 meses, trimestre actual)")
        
        # Detectar falta de ubicación cuando se pregunta por ciudad
        if 'ciudad' in pregunta_lower or 'ciudades' in pregunta_lower:
            ciudades_conocidas = ['bogotá', 'medellín', 'cali', 'barranquilla', 'cartagena', 'bucaramanga']
            if not any(ciudad in pregunta_lower for ciudad in ciudades_conocidas):
                if 'todas' not in pregunta_lower and 'top' not in pregunta_lower:
                    ambiguedades.append("🌍 **Ciudad no especificada.** ¿Qué ciudad? (ej: Bogotá, Medellín, Cali) o ¿quieres ver todas?")
        
        # Detectar falta de tipo de vivienda
        if any(palabra in pregunta_lower for palabra in ['vivienda', 'unidades', 'licencias']):
            if not any(tipo in pregunta_lower for tipo in ['vis', 'vip', 'no vis', 'todas']):
                if 'tipo' not in pregunta_lower:
                    ambiguedades.append("🏠 **Tipo de vivienda no especificado.** ¿VIS, VIP, No VIS o todas?")
        
        return len(ambiguedades) > 0, ambiguedades
    
    def validar_y_corregir_sql(self, sql: str, error: str, pregunta: str, llm_function) -> Optional[str]:
        """Intenta corregir SQL que falló"""
        print(f"⚠️ Intentando corregir SQL que falló...")
        
        prompt_correccion = f"""El siguiente SQL falló con error. Corrígelo.

SQL FALLIDO:
{sql}

ERROR:
{error}

PREGUNTA ORIGINAL:
{pregunta}

SCHEMA DE LA TABLA 'livo':
{self._generar_schema_inteligente()}

INSTRUCCIONES:
- Analiza el error y corrige el SQL
- Asegúrate de usar nombres de columnas correctos
- Verifica la sintaxis SQL
- Genera SOLO el SQL corregido, sin explicaciones

SQL CORREGIDO:"""
        
        sql_corregido, _ = llm_function(prompt_correccion)
        
        if sql_corregido:
            # Limpiar
            sql_corregido = sql_corregido.strip().replace('```sql', '').replace('```', '').strip()
            sql_corregido = '\n'.join([line for line in sql_corregido.split('\n') if not line.strip().startswith('--')])
            sql_corregido = sql_corregido.strip()
            
            if ';' in sql_corregido:
                sql_corregido = sql_corregido.split(';')[0].strip()
            
            return sql_corregido
        
        return None
    
    def explicar_sql(self, sql: str, llm_function) -> str:
        """Genera explicación en lenguaje natural del SQL"""
        prompt_explicacion = f"""Explica en español simple y conciso qué hace este SQL:

{sql}

Explicación (máximo 2-3 líneas, lenguaje simple):"""
        
        explicacion, _ = llm_function(prompt_explicacion)
        
        if explicacion:
            return explicacion.strip()
        else:
            return "Consulta SQL sobre datos LIVO"
    
    def generar_preguntas_relacionadas(self, pregunta: str, resultado: str, llm_function) -> List[str]:
        """Sugiere 3 preguntas de seguimiento"""
        # Limitar resultado para no sobrecargar el prompt
        resultado_preview = resultado[:300] if len(resultado) > 300 else resultado
        
        prompt_sugerencias = f"""Basado en esta consulta sobre datos LIVO:

Pregunta: {pregunta}
Resultado: {resultado_preview}...

Sugiere 3 preguntas de seguimiento interesantes y relevantes que el usuario podría hacer.

Formato: Una pregunta por línea, sin números ni viñetas.

Preguntas sugeridas:"""
        
        sugerencias, _ = llm_function(prompt_sugerencias)
        
        if sugerencias:
            # Parsear sugerencias
            lineas = [l.strip() for l in sugerencias.strip().split('\n') if l.strip()]
            # Limpiar números y viñetas
            preguntas = []
            for linea in lineas[:3]:  # Máximo 3
                # Remover números, viñetas, etc.
                linea_limpia = linea.lstrip('0123456789.-•* ')
                if linea_limpia and len(linea_limpia) > 10:
                    preguntas.append(linea_limpia)
            
            return preguntas[:3]
        
        return []
    
    def exportar_resultados_excel(self, df: 'pd.DataFrame', pregunta: str, sql: str, filename: str = "resultados_livo.xlsx") -> bool:
        """Exporta resultados a Excel con múltiples hojas"""
        if not PANDAS_AVAILABLE:
            return False
        
        try:
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                # Hoja 1: Datos
                df.to_excel(writer, sheet_name='Datos', index=False)
                
                # Hoja 2: Metadata
                metadata = pd.DataFrame({
                    'Campo': ['Pregunta', 'SQL', 'Fecha', 'Registros', 'Columnas'],
                    'Valor': [
                        pregunta,
                        sql,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        len(df),
                        len(df.columns)
                    ]
                })
                metadata.to_excel(writer, sheet_name='Metadata', index=False)
                
                # Hoja 3: Estadísticas (si hay columnas numéricas)
                columnas_numericas = df.select_dtypes(include=['int64', 'float64']).columns
                if len(columnas_numericas) > 0:
                    stats = df[columnas_numericas].describe()
                    stats.to_excel(writer, sheet_name='Estadísticas')
            
            return True
        except Exception as e:
            print(f"⚠️ Error exportando a Excel: {e}")
            return False
    
    def obtener_historial(self, usuario: str = "default", limite: int = 10) -> List[Dict[str, Any]]:
        """Obtiene historial de consultas del usuario"""
        historial_usuario = [h for h in self.historial if h.get('usuario') == usuario]
        return historial_usuario[-limite:]  # Últimas N consultas
    
    def limpiar_cache(self):
        """Limpia el caché de consultas"""
        self.cache_consultas = {}
        self._guardar_cache()
        print("✅ Caché limpiado")
    
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema"""
        consultas_exitosas = sum(1 for h in self.historial if h.get('exito', False))
        consultas_fallidas = len(self.historial) - consultas_exitosas
        
        return {
            'total_consultas': len(self.historial),
            'consultas_exitosas': consultas_exitosas,
            'consultas_fallidas': consultas_fallidas,
            'tasa_exito': round(consultas_exitosas / len(self.historial) * 100, 2) if self.historial else 0,
            'consultas_cacheadas': len(self.cache_consultas),
            'usuarios_unicos': len(set(h.get('usuario', 'default') for h in self.historial))
        }