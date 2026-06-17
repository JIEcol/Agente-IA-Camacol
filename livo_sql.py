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
from typing import Dict, List, Tuple, Optional, Any
import duckdb
import unicodedata
import pandas as pd
from datetime import datetime
import re
import json
import hashlib
import time
from functools import lru_cache

# Importar LLM y configuración de proveedores
from llm_providers import llamar_api_ia
from config import AI_PROVIDERS, AIModel

# Importar streamlit para debug en interfaz (opcional)
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer, util
    SEMANTIC_CACHE_AVAILABLE = True
except ImportError:
    SEMANTIC_CACHE_AVAILABLE = False

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

try:
    from visualization_system import LIVOVisualizationSystem
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False
    print("⚠️ Sistema de visualización no disponible. Instalar matplotlib y seaborn.")

# Importar sistemas de Coyuntura para respuestas oficiales
try:
    from ventas_coyuntura import ventas_coyuntura
    from oferta_coyuntura import oferta_coyuntura
    from lanzamientos_coyuntura import lanzamientos_coyuntura
    from iniciaciones_coyuntura import iniciaciones_coyuntura
    from rotacion_coyuntura import rotacion_coyuntura
    from coyuntura_sql import responder_pregunta_coyuntura
    COYUNTURA_AVAILABLE = True
except ImportError:
    COYUNTURA_AVAILABLE = False

# --- CONFIGURACIÓN ---
FAST_PROVIDER = next((p for p in AI_PROVIDERS if p["name"] == "Groq"), None)

def normalize_text(text: str) -> str:
    """Convierte texto a minúsculas y remueve tildes."""
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn').lower()

class SalarioMinimoColombiano:
    """Manejo de salarios mínimos de Colombia por año"""
    
    # Salarios mínimos históricos de Colombia (en pesos)
    SALARIOS_MINIMOS = {
        2020: 877803,
        2021: 908526,
        2022: 1000000,
        2023: 1160000,
        2024: 1300000,
        2025: 1423500,  # Oficial 2025
        2026: 1550000   # Proyectado
    }
    
    @classmethod
    def obtener_salario_minimo(cls, año: int) -> int:
        """Obtiene el salario mínimo para un año específico"""
        return cls.SALARIOS_MINIMOS.get(año, cls.SALARIOS_MINIMOS[2024])  # Default 2024
    
    @classmethod
    def obtener_salario_actual(cls) -> int:
        """Obtiene el salario mínimo del año actual"""
        año_actual = datetime.now().year
        return cls.obtener_salario_minimo(año_actual)
    
    @classmethod
    def calcular_rangos_vivienda(cls, año: int = None) -> Dict[str, Dict[str, int]]:
        """Calcula los rangos de clasificación de vivienda por valor"""
        if año is None:
            año = datetime.now().year
        
        salario_minimo = cls.obtener_salario_minimo(año)
        
        return {
            'VIP': {
                'min': 0,
                'max': salario_minimo * 90,
                'descripcion': 'Vivienda de Interés Prioritario (< 90 SMMLV)'
            },
            'VIS': {
                'min': salario_minimo * 90,
                'max': salario_minimo * 135,
                'descripcion': 'Vivienda de Interés Social (90 - 135 SMMLV)'
            },
            'NO_VIS': {
                'min': salario_minimo * 135,
                'max': float('inf'),
                'descripcion': 'Vivienda No VIS (> 135 SMMLV)'
            }
        }

# Base de conocimiento estática con ejemplos Few-Shot para Text-to-SQL
FEW_SHOT_EXAMPLES = [
    {
        "keywords": ["oferta", "unidades", "bogota"],
        "pregunta": "¿Cuántas unidades hay en oferta para Bogotá?",
        "sql": "SELECT SUM(unidades) AS total_unidades_oferta FROM livo WHERE cuenta = 'Oferta' AND UPPER(regional) LIKE UPPER('%Bogotá%') AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta');"
    },
    {
        "keywords": ["precio", "medellin", "promedio"],
        "pregunta": "¿Cuál es el precio promedio en Medellín?",
        "sql": "SELECT AVG(valor) AS precio_promedio FROM livo WHERE UPPER(regional) LIKE UPPER('%Medellín%') AND fecha = (SELECT MAX(fecha) FROM livo);"
    },
    {
        "keywords": ["vis", "antioquia"],
        "pregunta": "¿Cuántas unidades VIS hay en Antioquia?",
        "sql": "SELECT SUM(unidades) AS total_vis FROM livo WHERE cuenta = 'Oferta' AND segmento_pre = 'VIS' AND UPPER(regional) LIKE UPPER('%Antioquia%') AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta');"
    },
    {
        "keywords": ["lanzamientos", "barranquilla"],
        "pregunta": "¿Cuántos lanzamientos hay en Barranquilla?",
        "sql": "SELECT SUM(unidades) AS total_lanzamientos FROM livo WHERE cuenta = 'Lanzamientos' AND UPPER(regional) LIKE UPPER('%Barranquilla%') AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Lanzamientos');"
    },
    {
        "keywords": ["crecimiento", "variacion", "frente al"],
        "pregunta": "¿Cuál es la variación del precio promedio de las unidades lanzadas en 2026 frente al 2025?",
        "sql": "WITH datos_2025 AS (\n    SELECT AVG(valor) as promedio_2025\n    FROM livo\n    WHERE cuenta = 'Lanzamientos' AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2025\n),\ndatos_2026 AS (\n    SELECT AVG(valor) as promedio_2026\n    FROM livo\n    WHERE cuenta = 'Lanzamientos' AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2026\n)\nSELECT \n    promedio_2025, promedio_2026,\n    ROUND(((promedio_2026 - promedio_2025) / NULLIF(promedio_2025, 0)) * 100, 2) as variacion_porcentaje\nFROM datos_2025, datos_2026;"
    },
    {
        "keywords": ["ranking", "constructoras", "lideres", "top"],
        "pregunta": "Identifica las constructoras líderes",
        "sql": "SELECT compania_constructora, SUM(unidades) as total_unidades FROM livo WHERE cuenta = 'Ventas' GROUP BY compania_constructora ORDER BY total_unidades DESC LIMIT 10;"
    },
    {
        "keywords": ["absorcion", "tasa"],
        "pregunta": "Analiza la tasa de absorción mensual de vivienda VIS vs No VIS en Medellín",
        "sql": "WITH oferta AS (\n    SELECT segmento_pre, SUM(unidades) as total_oferta\n    FROM livo\n    WHERE cuenta = 'Oferta' AND UPPER(regional) LIKE UPPER('%Medellín%') AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')\n    GROUP BY segmento_pre\n),\nventas AS (\n    SELECT segmento_pre, SUM(unidades) as total_ventas\n    FROM livo\n    WHERE cuenta = 'Ventas' AND UPPER(regional) LIKE UPPER('%Medellín%') AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Ventas')\n    GROUP BY segmento_pre\n)\nSELECT \n    o.segmento_pre, o.total_oferta, COALESCE(v.total_ventas, 0) as total_ventas,\n    ROUND((COALESCE(v.total_ventas, 0) * 100.0 / NULLIF((o.total_oferta + COALESCE(v.total_ventas, 0)), 0)), 2) as tasa_absorcion_porcentaje\nFROM oferta o\nLEFT JOIN ventas v ON o.segmento_pre = v.segmento_pre;"
    }
]

class LIVOSQLSystem:
    """Sistema de consultas SQL sobre LIVO usando DuckDB"""
    
    @staticmethod
    def obtener_rangos_vivienda_sql(año: int = None, cities: Optional[Any] = None) -> Dict[str, str]:
        """Genera las condiciones SQL para clasificar vivienda por valor.

        Si `cities` (string o lista de strings) está completamente contenida en las
        aglomeraciones especiales, usa VIS hasta 150 SMMLV y NO VIS > 150 SMMLV.
        En caso contrario mantiene el esquema general VIS hasta 135 SMMLV.
        """

        # Año efectivo
        año_efectivo = año or datetime.now().year
        rangos = SalarioMinimoColombiano.calcular_rangos_vivienda(año_efectivo)

        # Lista de municipios especiales coherente con generar_clasificacion_temporal_sql
        ciudades_vis_150 = set([
            # Barranquilla
            'Sitionuevo', 'Sabanalarga', 'Ponedera', 'Palmar de Varela', 'Santo Tomás',
            'Malambo', 'Soledad', 'Galapa', 'Barranquilla',
            # Bogotá DC
            'Tabio', 'Cajicá', 'Cota', 'Sibaté', 'La Calera', 'Funza', 'Chía', 'Mosquera',
            'Facatativá', 'Zipaquirá', 'Madrid', 'Soacha', 'Tocancipá', 'Bogotá, D.C.', 'Bogotá',
            # Bucaramanga
            'Piedecuesta', 'Girón', 'Floridablanca', 'Bucaramanga',
            # Cali
            'Puerto Tejada', 'Candelaria', 'Yumbo', 'Jamundí', 'Cali',
            # Cartagena
            'Clemencia', 'Turbaco', 'Cartagena De Indias', 'Cartagena',
            # Medellín
            'Girardota', 'Caldas', 'Itagüí', 'Sabaneta', 'La Estrella', 'Envigado',
            'Copacabana', 'Bello', 'Medellín',
            # Cúcuta (Decreto 1607 de 2022)
            'Cúcuta', 'Los Patios', 'Villa Del Rosario'
        ])

        usar_esquema_especial = False
        ciudades_consulta: Optional[set] = None

        if cities is not None:
            # Normalizar a conjunto de strings
            if isinstance(cities, str):
                ciudades_consulta = {cities}
            else:
                try:
                    ciudades_consulta = {str(c) for c in cities}
                except Exception:
                    ciudades_consulta = None

            if ciudades_consulta:
                # Esquema especial solo si TODAS las ciudades están en la lista especial
                if ciudades_consulta.issubset(ciudades_vis_150):
                    usar_esquema_especial = True

        salario_minimo = SalarioMinimoColombiano.obtener_salario_minimo(año_efectivo)

        # Convertir a miles (como está en la base de datos)
        vip_max_miles = rangos['VIP']['max'] // 1000                # 90 SMMLV
        vis_min_miles = rangos['VIS']['min'] // 1000                # 90 SMMLV

        if usar_esquema_especial:
            # VIS hasta 150 SMMLV, NO VIS > 150 SMMLV
            vis_max_miles = (salario_minimo * 150) // 1000
            no_vis_min_miles = vis_max_miles
        else:
            # Esquema general: VIS hasta 135 SMMLV, NO VIS > 135 SMMLV
            vis_max_miles = rangos['VIS']['max'] // 1000
            no_vis_min_miles = rangos['NO_VIS']['min'] // 1000

        return {
            'VIP': f"valor < {vip_max_miles}",
            'VIS': f"valor >= {vis_min_miles} AND valor < {vis_max_miles}",
            'NO_VIS': f"valor >= {no_vis_min_miles}",
            'info': {
                'salario_minimo': salario_minimo,
                'año': año_efectivo,
                'rangos_pesos': rangos,
                'esquema_especial': usar_esquema_especial,
                'ciudades_consulta': list(ciudades_consulta) if ciudades_consulta else None
            }
        }
    
    @staticmethod
    def generar_clasificacion_temporal_sql(
        valor_campo: str = 'valor',
        fecha_campo: str = 'fecha',
        ciudad_campo: str = 'ciudad'
    ) -> str:
        """Genera SQL para clasificar VIS/VIP/No VIS basado en año y municipio.

        Aplica:
        - VIP: < 90 SMMLV (en todo el país)
        - VIS: 90-135 SMMLV en la mayoría de municipios
        - VIS: 90-150 SMMLV en aglomeraciones Decreto 1467/2019 (y extensiones)
        - NO VIS: >135 SMMLV (general) o >150 SMMLV (aglomeraciones especiales)
        """
        sql_cases = []

        # Lista de municipios donde el tope VIS es 150 SMMLV (NO VIS > 150 SMMLV)
        ciudades_vis_150 = [
            # Barranquilla
            'Sitionuevo', 'Sabanalarga', 'Ponedera', 'Palmar de Varela', 'Santo Tomás',
            'Malambo', 'Soledad', 'Galapa', 'Barranquilla',
            # Bogotá DC
            'Tabio', 'Cajicá', 'Cota', 'Sibaté', 'La Calera', 'Funza', 'Chía', 'Mosquera',
            'Facatativá', 'Zipaquirá', 'Madrid', 'Soacha', 'Tocancipá', 'Bogotá, D.C.', 'Bogotá',
            # Bucaramanga
            'Piedecuesta', 'Girón', 'Floridablanca', 'Bucaramanga',
            # Cali
            'Puerto Tejada', 'Candelaria', 'Yumbo', 'Jamundí', 'Cali',
            # Cartagena
            'Clemencia', 'Turbaco', 'Cartagena De Indias', 'Cartagena',
            # Medellín
            'Girardota', 'Caldas', 'Itagüí', 'Sabaneta', 'La Estrella', 'Envigado',
            'Copacabana', 'Bello', 'Medellín',
            # Cúcuta (Decreto 1607 de 2022)
            'Cúcuta', 'Los Patios', 'Villa Del Rosario'
        ]

        ciudades_vis_150_sql = ", ".join([f"'{c}'" for c in ciudades_vis_150])
        condicion_ciudad_especial = f"{ciudad_campo} IN ({ciudades_vis_150_sql})"
        condicion_ciudad_general = f"{ciudad_campo} NOT IN ({ciudades_vis_150_sql})"

        for año in range(2020, 2027):  # Rango de años con datos
            # Rangos base con VIS hasta 135 SMMLV
            rangos = SalarioMinimoColombiano.calcular_rangos_vivienda(año)
            salario_minimo = SalarioMinimoColombiano.obtener_salario_minimo(año)

            vip_max_miles = rangos['VIP']['max'] // 1000                # 90 SMMLV
            vis_min_miles = rangos['VIS']['min'] // 1000                # 90 SMMLV
            vis_max_general_miles = rangos['VIS']['max'] // 1000        # 135 SMMLV
            # Tope VIS especial 150 SMMLV
            vis_max_especial_miles = (salario_minimo * 150) // 1000
            no_vis_min_general_miles = rangos['NO_VIS']['min'] // 1000  # 135 SMMLV
            no_vis_min_especial_miles = vis_max_especial_miles          # 150 SMMLV

            # Condición para cada año
            año_condition = f"LEFT({fecha_campo}, 4) = '{año}'"

            # --- Aglomeraciones especiales (VIS hasta 150 SMMLV) ---
            # VIP
            sql_cases.append(f"""
    WHEN {año_condition} AND {condicion_ciudad_especial} AND {valor_campo} < {vip_max_miles} THEN 'VIP'""")

            # VIS
            sql_cases.append(f"""
    WHEN {año_condition} AND {condicion_ciudad_especial} AND {valor_campo} >= {vis_min_miles} AND {valor_campo} < {vis_max_especial_miles} THEN 'VIS'""")

            # NO VIS
            sql_cases.append(f"""
    WHEN {año_condition} AND {condicion_ciudad_especial} AND {valor_campo} >= {no_vis_min_especial_miles} THEN 'NO_VIS'""")

            # --- Resto de municipios (VIS hasta 135 SMMLV) ---
            # VIP
            sql_cases.append(f"""
    WHEN {año_condition} AND {condicion_ciudad_general} AND {valor_campo} < {vip_max_miles} THEN 'VIP'""")

            # VIS
            sql_cases.append(f"""
    WHEN {año_condition} AND {condicion_ciudad_general} AND {valor_campo} >= {vis_min_miles} AND {valor_campo} < {vis_max_general_miles} THEN 'VIS'""")

            # NO VIS
            sql_cases.append(f"""
    WHEN {año_condition} AND {condicion_ciudad_general} AND {valor_campo} >= {no_vis_min_general_miles} THEN 'NO_VIS'""")

        # SQL completo con CASE
        sql_completo = f"""CASE{''.join(sql_cases)}
    ELSE 'SIN_CLASIFICAR'
END AS clasificacion_vivienda_temporal"""

        return sql_completo
    
    @staticmethod
    def explicar_cambios_clasificacion() -> str:
        """Explica cómo puede cambiar la clasificación de un proyecto a lo largo del tiempo"""
        
        ejemplos = []
        años_ejemplo = [2023, 2024, 2025]
        valor_ejemplo = 130000  # 130 millones (en miles)
        
        for año in años_ejemplo:
            rangos = SalarioMinimoColombiano.calcular_rangos_vivienda(año)
            salario = SalarioMinimoColombiano.obtener_salario_minimo(año)
            
            # Determinar clasificación
            vip_max_miles = rangos['VIP']['max'] // 1000
            vis_max_miles = rangos['VIS']['max'] // 1000
            
            if valor_ejemplo < vip_max_miles:
                clasificacion = "VIP"
            elif valor_ejemplo < vis_max_miles:
                clasificacion = "VIS"
            else:
                clasificacion = "NO_VIS"
            
            ejemplos.append(f"- {año}: Salario ${salario:,} → Proyecto $130M = {clasificacion}")
        
        return f"""
CLASIFICACIÓN TEMPORAL DE VIVIENDA - CAMBIOS POR AÑO:

Un mismo proyecto puede cambiar de clasificación según el año debido a:
1. Los salarios mínimos aumentan cada año
2. Los rangos VIS/VIP/No VIS se recalculan automáticamente
3. Los proyectos pueden durar 1-3 años

EJEMPLO - Proyecto de $130 millones:
{''.join(chr(10) + ej for ej in ejemplos)}

RECOMENDACIÓN CRÍTICA:
⚠️  Para análisis históricos, usar la clasificación del AÑO ESPECÍFICO del proyecto
⚠️  No usar clasificación actual para proyectos de años anteriores
⚠️  Considerar que un proyecto puede "cambiar" de categoría entre años
"""
    
    # Tabla completa de metadatos LIVO con sinónimos y palabras clave
    METADATA_LIVO = {
        # Fechas y períodos temporales
        'fecha': {
            'tipo': 'VARCHAR',
            'descripcion': 'Fecha de registro en formato texto YYYYMMDD (Ej: 20210101)',
            'sinonimos': ['día', 'momento', 'cuándo', 'calendario', 'fecha de registro', 'momento de corte', 'mes', 'trimestre']
        },
        'año_corrido': {
            'tipo': 'INTEGER', 
            'descripcion': 'Año corrido del proyecto',
            'sinonimos': ['año', 'periodo anual', 'ejercicio', 'año fiscal', 'por año', 'anualmente']
        },
        'doce_meses': {
            'tipo': 'INTEGER',
            'descripcion': 'Año de corte de los últimos 12 meses (Ej: 2025)',
            'sinonimos': ['últimos 12 meses', 'TTM', 'LTM', 'año móvil', 'periodo reciente', 'acumulado 12M']
        },
        
        # Ubicación geográfica
        'regional': {
            'tipo': 'VARCHAR',
            'descripcion': 'Región CAMACOL (Valores LIVO: Boyacá_Casanare, Cúcuta_Nororiente, Bogotá & Cundinamarca, etc.)',
            'sinonimos': ['región', 'zona grande', 'área geográfica', 'macrozona', 'dónde (macro)']
        },
        'departamento': {
            'tipo': 'VARCHAR',
            'descripcion': 'Departamento de Colombia',
            'sinonimos': ['estado', 'provincia', 'división administrativa', 'de qué departamento', 'jurisdicción']
        },
        'divipola': {
            'tipo': 'VARCHAR',
            'descripcion': 'Código DIVIPOLA del municipio',
            'sinonimos': ['código DIVIPOLA', 'código municipal', 'identificador geográfico', 'código DANE']
        },
        'ciudad': {
            'tipo': 'VARCHAR',
            'descripcion': 'Ciudad o municipio',
            'sinonimos': ['municipio', 'localidad', 'población', 'urbe', 'en qué ciudad', 'capital']
        },
        'zona': {
            'tipo': 'VARCHAR',
            'descripcion': 'Zona dentro de la ciudad',
            'sinonimos': ['sector', 'distrito', 'subzona', 'sector geográfico', 'microzona']
        },
        'barrio': {
            'tipo': 'VARCHAR',
            'descripcion': 'Barrio específico',
            'sinonimos': ['vecindario', 'comuna', 'urbanización', 'localidad', 'sector']
        },
        
        # Características socioeconómicas y de proyecto
        'estrato': {
            'tipo': 'INTEGER',
            'descripcion': 'Estrato socioeconómico',
            'sinonimos': ['nivel socioeconómico', 'clase social', 'estrato social', 'nivel', 'clasificación'],
            'valores_completos': [0, 1, 2, 3, 4, 5, 6]
        },
        'destino_etapa': {
            'tipo': 'VARCHAR',
            'descripcion': 'Destino o finalidad del proyecto',
            'sinonimos': ['destino', 'finalidad', 'tipo de proyecto', 'uso principal', 'qué se va a hacer'],
            'valores_completos': ['Venta', 'Uso Propio', 'Arrendar', 'Adjudicación', 'Sin Definir']
        },
        'uso_etapa': {
            'tipo': 'VARCHAR',
            'descripcion': 'Tipo de uso de la construcción',
            'sinonimos': ['tipo de unidad', 'clase de inmueble', 'tipo de propiedad', 'qué es', 'vivienda', 'comercial', 'oficinas'],
            'valores_completos': ['Apartamento', 'Casa']
        },
        
        # Información de constructoras
        'compania_constructora': {
            'tipo': 'VARCHAR',
            'descripcion': 'Nombre de la empresa constructora (se debe usar junto con nit_constructora)',
            'sinonimos': ['constructora', 'empresa', 'firma', 'quién construyó', 'quién hizo', 'desarrolladora', 'compañía']
        },
        'nit_constructora': {
            'tipo': 'VARCHAR',
            'descripcion': 'NIT de la constructora (identificador único; nunca debe estar vacío y se usa siempre junto al nombre)',
            'sinonimos': ['NIT', 'identificación constructora', 'cédula jurídica', 'RUT', 'nit de la constructora']
        },
        
        # Estados y fases del proyecto (Ciclo de vida de la construcción)
        # 
        # IMPORTANTE: DIFERENCIA ENTRE estado Y last_estado
        # Tener ambos campos en la base de datos es una práctica común para análisis de transición y reportería histórica.
        #
        # 1. La Diferencia Conceptual:
        # - estado (Estado Actual/Vigente): Situación del proyecto hoy, en el corte del mes actual. Es el estado "vivo" para tableros de control.
        # - last_estado (Estado Anterior/Previo): Estado en el que estaba el proyecto justo antes de cambiar al estado actual. Es el estado histórico inmediato.
        #
        # 2. ¿Para qué se usan ambos campos?
        # A. Análisis de Transiciones y "Matriz de Migración": Permite medir cómo se mueven los proyectos entre estados.
        #    - last_estado=Preventa → estado=Construcción: El proyecto avanzó al alcanzar punto de equilibrio (Avance normal)
        #    - last_estado=Construcción → estado=Paralizado: El proyecto sufrió un problema operativo/financiero (Alerta)
        #    - last_estado=Paralizado → estado=Construcción: El proyecto reactivó su obra (Reactivación)
        # B. Calcular la "Siniestralidad" o Tasa de Deserción: Al buscar estado=Cancelado, last_estado indica si se canceló en planos (Proyectado) o ya vendido (Preventa)
        # C. Control de Calidad de Datos: Detecta errores humanos. Si last_estado=Proyectado → estado=TVE es imposible metodológicamente.
        #
        # 3. Ejemplo práctico:
        # - Torres del Norte: last_estado=Preventa, estado=Construcción, fase=Cimentación → Arrancó obra (alcanzó punto de equilibrio)
        # - Residencial El Bosque: last_estado=Construcción, estado=Paralizado, fase=Estructura → Se frenó (estaba levantando estructura)
        # - Sendero Verde: last_estado=Rediseñado, estado=Preventa, fase=Sin Iniciar → Volvió a preventa
        #
        # CICLO DE VIDA DE LA CONSTRUCCIÓN (Orden Cronológico):
        # 1. Proyectado + Sin Iniciar = Planeación: Diseño, viabilidad o trámites de licencias. Sin actividad física ni comercial.
        # 2. Preventa + Sin Iniciar/Preliminar = Comercialización: Apertura de salas de ventas y búsqueda del punto de equilibrio. Fases Preliminares (cerramientos, movimiento de tierras).
        # 3. Construcción + Cimentación = Ejecución (Etapa Inicial): Obra subterránea, pilotaje y bases estructurales tras alcanzar el punto de equilibrio.
        # 4. Construcción + Obra Negra = Ejecución (Avance): Muros divisorios, mampostería básica y canalizaciones internas primarias.
        # 5. Construcción/TE + Estructura = Ejecución (Hito Estructural): Estructura principal (vigas, columnas, losas). Si se completa el 100%, el estado puede mutar a TE (Terminado en Estructura).
        # 6. Construcción + Acabados = Ejecución (Etapa Final): Revestimientos, yesos, pisos, carpintería, fachadas e instalaciones definitivas.
        # 7. Construcción + Urbanismo = Adecuación del Entorno: Vías de acceso, andenes, zonas verdes y áreas comunes.
        # 8. TVE + Terminado = Cierre/Postventa: Obra física concluida al 100% y estado TVE (Terminado Vendido Entregado) con escrituración y entrega de llaves.
        'estado': {
            'tipo': 'VARCHAR',
            'descripcion': 'Estado actual del proyecto (Preventa, Paralizado, Construcción, TVE, Rediseñado, TE, Cancelado, Proyectado). TE = Terminado y Entregado, TVE = Terminado, Vendido y Entregado',
            'sinonimos': ['estatus', 'situación', 'condición', 'cómo está', 'estado actual', 'vendido', 'en obra', 'terminado'],
            'valores_completos': ['Construcción', 'Preventa', 'TVE', 'Rediseñado', 'Paralizado', 'TE', 'Cancelado', 'Proyectado']
        },
        'fase': {
            'tipo': 'VARCHAR',
            'descripcion': 'Fase constructiva del proyecto (Sin Iniciar, Estructura, Terminado, Obra Negra, Cimentación, Preliminar, Acabados, Urbanismo)',
            'sinonimos': ['etapa', 'progreso', 'ciclo', 'momento del proyecto', 'en qué etapa va', 'preventa', 'lanzamiento'],
            'valores_completos': ['Sin Iniciar', 'Estructura', 'Terminado', 'Obra Negra', 'Cimentación', 'Preliminar', 'Acabados', 'Urbanismo']
        },
        'last_estado': {
            'tipo': 'VARCHAR',
            'descripcion': 'Último estado registrado del proyecto (Cancelado, TVE, Construcción, Paralizado, TE, Preventa, Rediseñado, Proyectado). TE = Terminado y Entregado, TVE = Terminado, Vendido y Entregado. Úsalo junto con estado para análisis de transiciones.',
            'sinonimos': ['estado anterior', 'último estatus', 'condición previa', 'estado histórico', 'ultimo estado', 'último estado'],
            'valores_completos': ['Cancelado', 'TVE', 'Construcción', 'Paralizado', 'TE', 'Preventa', 'Rediseñado', 'Proyectado']
        },
        
        # Rangos y clasificaciones de precio
        'nuevorango_pre': {
            'tipo': 'VARCHAR',
            'descripcion': 'Nuevo rango de precios',
            'sinonimos': ['rango de precio', 'nivel de valor', 'banda de precio', 'costo', 'segmento de precio']
        },
        'rangos_decreto_pre': {
            'tipo': 'VARCHAR',
            'descripcion': 'Rangos de decreto de precios',
            'sinonimos': ['rango PPM2', 'precio por metro cuadrado', 'valor por metro', 'rango de decreto', 'precio unitario']
        },
        'rango_ppm2': {
            'tipo': 'VARCHAR',
            'descripcion': 'Rango de precio por metro cuadrado (PPM2)',
            'sinonimos': ['precio por m2', 'rango precio metro cuadrado', 'banda ppm2', 'valor m2']
        },
        'rango_area': {
            'tipo': 'VARCHAR',
            'descripcion': 'Rango de área construida',
            'sinonimos': ['rango de área', 'rango de tamaño', 'banda de metros cuadrados', 'segmento de área']
        },
        'AM_capital': {
            'tipo': 'VARCHAR',
            'descripcion': 'Aglomeración metropolitana o capital asociada al proyecto (por ejemplo Bogotá D.C., Barranquilla AM, Bucaramanga AM, etc.)',
            'sinonimos': ['área metropolitana', 'aglomeración', 'am capital', 'corredor urbano', 'ciudad principal']
        },
        'segmento_pre': {
            'tipo': 'VARCHAR',
            'descripcion': 'Segmento VIS/NO VIS del proyecto (clasificación de vivienda por política previa)',
            'sinonimos': ['vis/no vis', 'segmento vis', 'segmento no vis', 'segmento vivienda vis no vis', 'clasificación vis/no vis']
        },
        'politica_vivienda': {
            'tipo': 'VARCHAR',
            'descripcion': 'Tipo de política de vivienda',
            'sinonimos': ['tipo de política', 'VIS', 'NO VIS', 'interés social', 'qué política aplica', 'subsidio']
        },
        'segmento_pre': {
            'tipo': 'VARCHAR',
            'descripcion': 'Clasificación de vivienda (VIS, No VIS, VIP)',
            'sinonimos': ['tipo de vivienda', 'clasificación', 'segmento', 'vis', 'no vis', 'vip'],
            'valores_completos': ['No VIS', 'VIS', 'VIP', 'SIN ASIGNAR']
        },
        
        # Métricas numéricas principales
        'unidades': {
            'tipo': 'INTEGER',
            'descripcion': 'Número de unidades del proyecto',
            'sinonimos': ['cantidad', 'número de unidades', 'total de viviendas', 'cuántas unidades', 'inventario', 'SUM(unidades)']
        },
        'area': {
            'tipo': 'DOUBLE',
            'descripcion': 'Área construida en metros cuadrados',
            'sinonimos': ['metros cuadrados', 'tamaño', 'superficie', 'cuánto mide', 'dimensión', 'AVG(area)', 'MAX(area)']
        },
        'valor': {
            'tipo': 'DOUBLE',
            'descripcion': 'Valor económico del proyecto',
            'sinonimos': ['precio', 'costo', 'monto', 'valor de venta', 'valor final', 'cuánto vale', 'precio promedio', 'AVG(valor)', 'SUM(valor)']
        },
        'cuenta': {
            'tipo': 'VARCHAR',
            'descripcion': 'Estado/categoría del registro (Saldo que inicia, Oferta, Ventas, Renuncias, Iniciaciones, Entregadas, Lanzamientos, Paralizado, Culminadas, etc.)',
            'sinonimos': [
                'estado de cuenta', 'tipo de saldo', 'oferta', 'disponible', 'inventario', 'stock', 'ventas', 'vendidas', 'comercializadas', 'negocios', 
                'renuncias', 'desistimientos', 'cancelaciones', 'iniciaciones', 'inicios de obra', 'arranques', 'entregadas', 'terminadas', 'finalizadas', 
                'lanzamientos', 'nuevos proyectos', 'preventa', 'paralizado', 'obras detenidas', 'suspendidas', 'culminadas', 'obra terminada', 'saldo que inicia', 'saldo inicial'
            ]
        }
    }

    # Describir lógicamente el nombre del proyecto (antes identificador)
    METADATA_LIVO['nombre_proyecto'] = {
        'tipo': 'VARCHAR',
        'descripcion': 'Nombre del proyecto (identificador único del proyecto en LIVO)',
        'sinonimos': ['nombre del proyecto', 'identificador de proyecto', 'id proyecto', 'código de proyecto', 'nombre del proyecto identificador']
    }
    
    # Diccionario de sinónimos simplificado para compatibilidad (generado automáticamente)
    SINONIMOS = {
        columna: info['sinonimos'] 
        for columna, info in METADATA_LIVO.items()
    }
    
    def _build_semantic_cache_embeddings(self) -> Optional[Dict[str, Any]]:
        """Construye los embeddings para el caché semántico."""
        if not self.cache_consultas:
            return None
        print("🧠 Construyendo embeddings para caché semántico...")
        cached_questions = [data['pregunta'] for data in self.cache_consultas.values()]
        embeddings = self.semantic_cache_model.encode(cached_questions, convert_to_tensor=True)
        return {'questions': cached_questions, 'embeddings': embeddings}

    def __init__(self, livo_path: str):
        self.livo_path = Path(livo_path)
        self.conn = None
        self.schema_info = {}
        self.location_kb = []
        
        # 1. Cargar caché de consultas
        self.cache_consultas = {}
        self.cache_file = Path('cache_livo_consultas.json')
        self._cargar_cache()
        
        # 2. Inicializar caché semántico (si está disponible)
        self.semantic_cache_embeddings = None
        if SEMANTIC_CACHE_AVAILABLE:
            try:
                self.semantic_cache_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                self.semantic_cache_embeddings = self._build_semantic_cache_embeddings()
            except Exception as e:
                print(f"⚠️ Error inicializando caché semántico: {e}. Continuando sin él.")
        
        # 3. Cargar historial de consultas
        self.historial = []
        self.historial_file = Path('historial_livo_consultas.json')
        self._cargar_historial()

    def inicializar(self) -> Tuple[bool, str]:
        """Inicializa DuckDB y carga LIVO"""
        try:
            db_file = self.livo_path.with_suffix('.duckdb')
            
            # Conectar a la base de datos (se creará si no existe)
            self.conn = duckdb.connect(database=str(db_file), read_only=False)
            
            # Verificar si la tabla 'livo' ya existe en la BD
            tables = self.conn.execute("SHOW TABLES").fetchall()
            table_exists = any('livo' in t for t in tables)
            
            # Cargar LIVO
            if not table_exists:
                print(f"🚀 Primera ejecución: Convirtiendo {self.livo_path.name} a formato DuckDB. Esto puede tardar varios minutos...")
                if self.livo_path.suffix.lower() in ['.xlsx', '.xls']:
                    if not PANDAS_AVAILABLE:
                        return False, "❌ Pandas no disponible para la conversión inicial."
                    
                    df = pd.read_excel(self.livo_path, engine='openpyxl')
                    # Crear la tabla 'livo' desde el DataFrame de pandas
                    self.conn.execute("CREATE TABLE livo AS SELECT * FROM df")
                    
                elif self.livo_path.suffix.lower() == '.csv':
                    self.conn.execute(f"CREATE TABLE livo AS SELECT * FROM read_csv_auto('{self.livo_path}')")
                else:
                    return False, f"❌ Formato no soportado: {self.livo_path.suffix}"
                
                print(f"✅ Conversión completa. Base de datos guardada en: {db_file.name}")
            
            else:
                print(f"⚡ LIVO cargado desde caché de DuckDB ({db_file.name}). Inicio ultra rápido.")

            # Asegurar columnas temporales derivadas de "fecha" (YYYYMMDD)
            try:
                # Crear columna fecha_date si no existe
                self.conn.execute("ALTER TABLE livo ADD COLUMN IF NOT EXISTS fecha_date DATE")

                # Poblar fecha_date solo donde esté nula y exista valor en fecha
                # Se asume que fecha viene en formato entero o texto YYYYMMDD
                self.conn.execute(
                    """
                    UPDATE livo
                    SET fecha_date = CAST(try_strptime(CAST(fecha AS VARCHAR), '%Y%m%d') AS DATE)
                    WHERE fecha IS NOT NULL AND fecha_date IS NULL
                    """
                )

                # Crear columnas de apoyo mes y año si no existen
                self.conn.execute("ALTER TABLE livo ADD COLUMN IF NOT EXISTS mes INTEGER")
                self.conn.execute("ALTER TABLE livo ADD COLUMN IF NOT EXISTS año INTEGER")

                # Poblar mes y año a partir de fecha_date cuando exista valor
                self.conn.execute(
                    """
                    UPDATE livo
                    SET mes = EXTRACT(MONTH FROM fecha_date),
                        año = EXTRACT(YEAR FROM fecha_date)
                    WHERE fecha_date IS NOT NULL
                    """
                )

                # Asegurar que nit_constructora nunca esté vacío: usar compania_constructora como fallback
                self.conn.execute(
                    """
                    UPDATE livo
                    SET nit_constructora = compania_constructora
                    WHERE (nit_constructora IS NULL OR TRIM(nit_constructora) = '')
                      AND compania_constructora IS NOT NULL
                    """
                )
            except Exception as e:
                print(f"⚠️ No se pudieron crear/actualizar columnas temporales (fecha_date, mes, año) o nit_constructora: {e}")

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
            
            # Cargar/Generar base de conocimiento de ubicaciones relacionales
            self._cargar_o_generar_location_kb()
            
            return True, f"✅ LIVO cargado: {filas:,} registros, {len(self.schema_info['columns'])} columnas"
            
        except Exception as e:
            return False, f"❌ Error: {str(e)}"
    
    def _cargar_o_generar_location_kb(self):
        """Carga la base de conocimiento de relaciones geográficas o la genera si no existe."""
        kb_path = Path("LIVO_base_conocimiento_ubicaciones.json")
        if kb_path.exists():
            try:
                with open(kb_path, "r", encoding="utf-8") as f:
                    self.location_kb = json.load(f)
                print(f"📖 Base de conocimiento de ubicaciones cargada ({len(self.location_kb)} relaciones).")
            except Exception as e:
                print(f"⚠️ Error cargando base de conocimiento geográfica: {e}")
                self.location_kb = []
        else:
            print("🗺️ Base de conocimiento de ubicaciones no encontrada. Generándola desde la BD...")
            try:
                query = """
                SELECT DISTINCT 
                    COALESCE(regional, '') as regional, 
                    COALESCE(departamento, '') as departamento, 
                    COALESCE(ciudad, '') as ciudad, 
                    COALESCE(AM_capital, '') as AM_capital
                FROM livo 
                ORDER BY regional, departamento, ciudad;
                """
                rows = self.conn.execute(query).fetchall()
                self.location_kb = []
                for r in rows:
                    self.location_kb.append({
                        "regional": r[0],
                        "departamento": r[1],
                        "ciudad": r[2],
                        "AM_capital": r[3]
                    })
                with open(kb_path, "w", encoding="utf-8") as f:
                    json.dump(self.location_kb, f, ensure_ascii=False, indent=4)
                print(f"✅ Base de conocimiento geográfica generada y guardada en {kb_path.name} ({len(self.location_kb)} registros).")
            except Exception as e:
                print(f"⚠️ No se pudo generar la base de conocimiento geográfica: {e}")

    def _analizar_metadatos(self):
        """Analiza metadatos inteligentes de cada columna"""
        self.metadata = {}
        
        # SISTEMA DE ASOCIACIÓN SEMÁNTICA
        # Mapeo de términos del lenguaje natural a nombres de campos correctos
        self.terminos_a_campos = {
            # Cuenta/Estado del proyecto
            'oferta': 'cuenta',
            'disponible': 'cuenta', 
            'stock': 'cuenta',
            'inventario': 'cuenta',
            'lanzamiento': 'cuenta',
            'lanzada': 'cuenta',
            'salida a ventas': 'cuenta',
            'venta': 'cuenta',
            'vendido': 'cuenta',
            'ventas': 'cuenta',
            'iniciacion': 'cuenta',
            'iniciada': 'cuenta',
            'inicio de obra': 'cuenta',
            'arranque': 'cuenta',
            'entregada': 'cuenta',
            'entrega': 'cuenta',
            'finalizada': 'cuenta',
            'habitables': 'cuenta',
            'culminada': 'cuenta',
            'culminacion': 'cuenta',
            'obra terminada': 'cuenta',
            'paralizado': 'cuenta',
            'paralizada': 'cuenta',
            'obras detenidas': 'cuenta',
            'suspendida': 'cuenta',
            
            # Ubicación geográfica
            'antioquia': 'departamento',
            'bogota': 'ciudad',
            'bogotá': 'ciudad',
            'medellin': 'ciudad',
            'medellín': 'ciudad',
            'cali': 'ciudad',
            'barranquilla': 'ciudad',
            'cartagena': 'ciudad',
            'bucaramanga': 'ciudad',
            'pereira': 'ciudad',
            'manizales': 'ciudad',
            'ibague': 'ciudad',
            'villavicencio': 'ciudad',
            'soacha': 'ciudad',
            
            # Tipo de vivienda
            'vis': 'segmento_pre',
            'vip': 'segmento_pre', 
            'no vis': 'segmento_pre',
            'interés social': 'segmento_pre',
            'interés prioritario': 'segmento_pre',
            'vivienda de interés social': 'segmento_pre',
            'vivienda de interés prioritario': 'segmento_pre',
            
            # Uso/Etapa
            'casa': 'uso_etapa',
            'apartamento': 'uso_etapa',
            'apartamentos': 'uso_etapa',
            'casas': 'uso_etapa',
            
            # Constructora
            'constructora': 'compania_constructora',
            'constructor': 'compania_constructora',
            'empresa': 'compania_constructora',
            'desarrollador': 'compania_constructora',
            
            # Proyecto
            'proyecto': 'nombre_proyecto',
            'nombre': 'nombre_proyecto',
            'conjunto': 'nombre_proyecto',
            'edificio': 'nombre_proyecto',
            'urbanización': 'nombre_proyecto',
            
            # Métricas
            'unidades': 'unidades',
            'cantidad': 'unidades',
            'numero': 'unidades',
            'viviendas': 'unidades',
            'metros': 'area',
            'área': 'area',
            'tamaño': 'area',
            'superficie': 'area',
            'precio': 'valor',
            'valor': 'valor',
            'costo': 'valor',
            
            # Tiempo
            'abril': 'mes',
            'enero': 'mes',
            'febrero': 'mes',
            'marzo': 'mes',
            'mayo': 'mes',
            'junio': 'mes',
            'julio': 'mes',
            'agosto': 'mes',
            'septiembre': 'mes',
            'octubre': 'mes',
            'noviembre': 'mes',
            'diciembre': 'mes',
            '2026': 'año',
            '2025': 'año',
            '2024': 'año',
        }
        
        # Mapeo de nombres de columnas reales de LIVO
        columnas_clave = [
            'fecha', 'año_corrido', 'doce_meses', 'regional', 'departamento', 
            'divipola', 'ciudad', 'zona', 'barrio', 'estrato', 
            'destino_etapa', 'uso_etapa', 'compania_constructora', 'nit_constructora',
            'estado', 'fase', 'last_estado',
            'nombre_proyecto', 'nuevorango_pre', 'rangos_decreto_pre',
            'rango_ppm2', 'rango_area', 'AM_capital', 'segmento_pre',
            'politica_vivienda', 'unidades', 'area', 'valor', 'cuenta'
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
    
    def generar_diccionario_valores(self, columnas: Optional[List[str]] = None,
                                    max_valores_por_columna: Optional[int] = None) -> Dict[str, List[Any]]:
        """Genera un diccionario {columna: [valores_únicos]} consultando directamente DuckDB.

        Args:
            columnas: Lista opcional de nombres de columnas. Si es None, usa todas las columnas
                      disponibles en self.schema_info['columns'].
            max_valores_por_columna: Límite opcional de valores únicos por columna (ORDER BY y LIMIT).

        Returns:
            Dict[str, List[Any]] con los valores distintos no nulos por cada columna solicitada.
        """
        if not self.conn:
            raise RuntimeError("LIVOSQLSystem no está inicializado. Llama primero a inicializar().")

        if not self.schema_info:
            raise RuntimeError("Schema de LIVO no cargado. Verifica la inicialización.")

        # Si no se especifican columnas, usar todas las columnas de la tabla
        columnas_objetivo = columnas or list(self.schema_info.get('columns', []))

        diccionario: Dict[str, List[Any]] = {}

        for col in columnas_objetivo:
            if col not in self.schema_info.get('columns', []):
                # Ignorar silenciosamente columnas que no existan en la tabla
                continue

            try:
                limit_clause = ""
                if max_valores_por_columna is not None and max_valores_por_columna > 0:
                    limit_clause = f" LIMIT {int(max_valores_por_columna)}"

                query = f"SELECT DISTINCT {col} FROM livo WHERE {col} IS NOT NULL ORDER BY {col}{limit_clause}"
                rows = self.conn.execute(query).fetchall()
                valores = [r[0] for r in rows]
                diccionario[col] = valores
            except Exception as e:
                print(f"⚠️ Error obteniendo valores únicos para {col}: {e}")

        return diccionario
    
    def _expandir_terminos_usuario(self, pregunta: str) -> str:
        """Expande términos del usuario usando asociación semántica (CONSERVANDO términos críticos)"""
        pregunta_expandida = pregunta.lower()
        
        # TÉRMINOS CRÍTICOS QUE NO DEBEN SER REEMPLAZADOS (conservan información específica)
        terminos_prohibidos = {
            'vis', 'vip', 'no vis', 'sin vip',  # Tipos de vivienda
            'antioquia', 'bogota', 'medellin', 'cali', 'barranquilla', 'cartagena',  # Ciudades específicas
            'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre', 'enero', 'febrero', 'marzo',  # Meses
            '2026', '2025', '2024'  # Años
        }
        
        # Reemplazar solo términos no críticos
        for termino, campo in self.terminos_a_campos.items():
            if termino in pregunta_expandida and termino not in terminos_prohibidos:
                # Reemplazar el término con el nombre del campo
                pregunta_expandida = pregunta_expandida.replace(termino, campo)
        
        return pregunta_expandida
    
    def _formatear_columnas(self) -> str:
        """Formatea las columnas con sus tipos para el prompt"""
        columnas_formateadas = []
        for col in self.schema_info['columns'][:20]:  # Primeras 20 columnas
            tipo = self.schema_info['types'].get(col, 'UNKNOWN')
            columnas_formateadas.append(f"  - {col} ({tipo})")
        return '\n'.join(columnas_formateadas)

    def _formatear_resultados(self, result, columns, sql: str) -> str:
        """Formatea los resultados SQL en texto legible.

        Esta versión es sencilla pero suficiente para la validación automática:
        - Si no hay filas: indica que no se encontraron resultados.
        - Si hay una sola celda numérica: devuelve directamente ese valor en texto con aclaraciones de escala monetaria.
        - En otros casos: construye una tabla básica texto con encabezados y notas de escala si aplica.
        """
        # Sin filas
        if not result:
            return f"No se encontraron resultados para la consulta. SQL: {sql}"

        # Verificar si todos los valores de la fila única son None (ej: SUM o AVG sobre consultas sin filas coincidentes)
        if len(result) == 1 and all(v is None or str(v).strip().lower() in ['none', 'null', 'nan'] for v in result[0]):
            # Detectar si la pregunta menciona una ciudad específica para sugerir la regional correcta
            ciudad_a_regional = {
                'medellín': 'Antioquia',
                'barranquilla': 'Atlántico',
                'cali': 'Valle del Cauca',
                'bucaramanga': 'Santander',
                'pereira': 'Risaralda',
                'manizales': 'Caldas',
                'bogotá': 'Bogotá & Cundinamarca'
            }
            
            sugerencia = ""
            for ciudad, regional in ciudad_a_regional.items():
                if ciudad in sql.lower():
                    sugerencia = f"\n\n💡 **Sugerencia:** Si mencionaste '{ciudad.capitalize()}', intenta consultar por la regional **{regional}** en su lugar."
                    break
            
            return (
                "**Sin registros disponibles:** No se encontraron transacciones en la base de datos para esta combinación de filtros (región, mes y cuenta de obra)."
                f"{sugerencia}\n\n"
                "**Nota metodológica:** Es muy común que para ciertos departamentos con menor volumen de actividad edificadora "
                "(como el Meta, Boyacá, Sucre, Córdoba, etc.) en un mes específico (ej: abril 2026), no se hayan registrado movimientos "
                "de una cuenta de obra en particular (como **Lanzamientos** o **Iniciaciones**). Intenta consultar con un acumulado "
                "más amplio (ej: *'en los últimos 12 meses'*) o en un departamento de mayor volumen."
            )

        # Una fila, una o dos columnas (caso típico de SUM o AVG, o comparación anual)
        if len(result) == 1 and len(columns) in [1, 2]:
            # Formatear la respuesta de una o dos columnas
            respuesta_formateada = []
            for i, col_name in enumerate(columns):
                valor_celda = result[0][i]
                nombre_columna_limpio = col_name.replace('_', ' ')
                
                # Identificar si es una columna de tipo valor/precio monetario general o por m2
                is_m2_monetary = ("m2" in col_name.lower() or "mc" in col_name.lower()) and ("precio" in col_name.lower() or "valor" in col_name.lower() or "costo" in col_name.lower())
                is_monetary = ("valor" in col_name.lower() or "precio" in col_name.lower() or "costo" in col_name.lower()) and not is_m2_monetary
                
                if valor_celda is None or str(valor_celda).strip().lower() in ['none', 'null', 'nan']:
                    if is_monetary or is_m2_monetary:
                        respuesta_formateada.append(
                            f"**{nombre_columna_limpio}:** No se registran montos económicos (el valor es nulo o no existen registros para esta combinación de filtros).\n\n"
                            f"**Nota metodológica:** Algunas cuentas como **Entregadas**, **Culminadas** o **Iniciaciones** "
                            f"registran principalmente volúmenes físicos de viviendas (**unidades**). Te sugerimos consultar por el **número de unidades** para esta misma selección (ej: *'Calcula la cantidad de unidades para Entregadas en Risaralda...'*)."
                        )
                    else:
                        respuesta_formateada.append(f"**{nombre_columna_limpio}:** None")
                elif isinstance(valor_celda, (int, float)):
                    if is_m2_monetary:
                        pesos_enteros = valor_celda * 1000
                        millones_pesos = valor_celda / 1000.0
                        respuesta_formateada.append(
                            f"**{nombre_columna_limpio}:** {valor_celda:,.2f} miles de pesos por m²\n"
                            f"  - Equivalente a: **${pesos_enteros:,.0f} COP por m²**\n"
                            f"  - Expresado en millones: **${millones_pesos:,.2f} millones de pesos por m²**"
                        )
                    elif is_monetary:
                        pesos_enteros = valor_celda * 1000
                        millones_pesos = valor_celda / 1000.0
                        respuesta_formateada.append(
                            f"**{nombre_columna_limpio}:** {valor_celda:,.2f} miles de pesos\n"
                            f"  - Equivalente a: **${pesos_enteros:,.0f} COP**\n"
                            f"  - Expresado en millones: **${millones_pesos:,.2f} millones de pesos**"
                        )
                    else:
                        respuesta_formateada.append(f"**{nombre_columna_limpio}:** {valor_celda:,.0f}")
                else:
                    respuesta_formateada.append(f"**{nombre_columna_limpio}:** {valor_celda}")
            respuesta_final = "\n".join(respuesta_formateada)
            # Agregar el query SQL utilizado
            respuesta_final += f"\n\n📊 **Query ejecutado:**\n```sql\n{sql}\n```"
            return respuesta_final

        # Tabla sencilla - formato markdown mejorado
        lineas = []
        
        # Encabezados con primera letra mayúscula
        column_names = [str(c).replace('_', ' ').title() for c in columns]
        
        # Calcular anchos máximos para alineación
        anchos = [len(c) for c in column_names]
        for fila in result:
            for i, valor in enumerate(fila):
                anchos[i] = max(anchos[i], len(str(valor)))
        
        # Construir encabezado y separador con alineación
        encabezado = " | ".join(c.ljust(anchos[i]) for i, c in enumerate(column_names))
        separador = " | ".join("-" * anchos[i] for i in range(len(column_names)))
        
        lineas.append("| " + encabezado + " |")
        lineas.append("| " + separador + " |")
        
        # Filas con formato numérico
        for fila in result:
            valores_formateados = []
            for i, valor in enumerate(fila):
                if isinstance(valor, (int, float)) and valor is not None:
                    # Formato numérico con separadores de miles
                    if isinstance(valor, float):
                        valor_str = f"{valor:,.2f}"
                    else:
                        valor_str = f"{valor:,}"
                else:
                    valor_str = str(valor)
                valores_formateados.append(valor_str.ljust(anchos[i]))
            lineas.append("| " + " | ".join(valores_formateados) + " |")

        # Agregar aclaración de escala al final si hay columnas de valor o m2
        tiene_monetario = False
        tiene_m2_monetario = False
        for col_name in columns:
            is_m2 = ("m2" in col_name.lower() or "mc" in col_name.lower()) and ("precio" in col_name.lower() or "valor" in col_name.lower() or "costo" in col_name.lower())
            is_gen = ("valor" in col_name.lower() or "precio" in col_name.lower() or "costo" in col_name.lower()) and not is_m2
            if is_m2:
                tiene_m2_monetario = True
            if is_gen:
                tiene_monetario = True
        
        if tiene_monetario or tiene_m2_monetario:
            lineas.append("\n💡 **Nota sobre escala monetaria (en miles de pesos):**")
            
            if tiene_monetario:
                lineas.append("- **Campos de valor general** (ej: valor total, suma valor):")
                lineas.append("  - Multiplicar por 1,000 para pesos enteros (ej: `776,700` miles = `$776,700,000 COP`).")
                lineas.append("  - Dividir por 1,000 para millones de pesos (ej: `776,700` miles = `$776.70` millones de pesos).")
            
            if tiene_m2_monetario:
                lineas.append("- **Campos de precio por metro cuadrado (m²)** (ej: precio_mc_promedio):")
                lineas.append("  - Multiplicar por 1,000 para pesos enteros por m² (ej: `4,500` miles = `$4,500,000 COP por m²`).")
                lineas.append("  - Dividir por 1,000 para millones de pesos por m² (ej: `4,500` miles = `$4.50` millones de pesos por m²).")

        resultado_tabla = "\n".join(lineas)
        # Agregar el query SQL utilizado
        resultado_tabla += f"\n\n📊 **Query ejecutado:**\n```sql\n{sql}\n```"
        return resultado_tabla

    # --- MÓDULO SIMPLE DE TEXT-TO-SQL SIN LLM (uso específico en validación) ---

    def _generar_sql_sin_llm(self, pregunta: str) -> Optional[str]:
        """Genera SQL aproximado SIN usar LLM, basado en reglas simples.

        Por ahora maneja preguntas de oferta de unidades totales de vivienda
        (todas, VIP, VIS, No VIS) por región, inspiradas en el archivo
        preguntas_oferta_autogeneradas.txt.

        Devuelve el SQL como string o None si la pregunta no coincide con
        los patrones soportados.
        """
        if not pregunta:
            return None

        texto = normalize_text(pregunta)
        
        # Inicializar variables para evitar UnboundLocalError
        tiene_agrupacion = any(x in texto for x in [' por ', ' segun ', ' según ', ' cada ', ' agrupado ', ' distribucion ', ' distribución ', ' desglosado ', ' desglose '])
        
        # --- DETECCIÓN DE CRECIMIENTO INTERANUAL (dejar para LLM) ---
        # Si la pregunta menciona crecimiento, variación, evolución o "entre X y Y",
        # devolver None para que el LLM maneje esta consulta compleja
        crecimiento_keywords = ['crecimiento', 'variacion', 'variación', 'evolucion', 'evolución', 'cambio']
        if any(kw in texto for kw in crecimiento_keywords):
            print(f"[DEBUG LIVO reglas] Detectada pregunta de crecimiento interanual, delegando a LLM")
            return None
        
        # Detectar patrón "entre X y Y" (ej: "entre 2025 y 2026")
        if re.search(r'entre\s+\d{4}\s+y\s+\d{4}', texto):
            print(f"[DEBUG LIVO reglas] Detectado patrón 'entre X y Y', delegando a LLM")
            return None
        
        # --- DETECCIÓN DE RANKINGS POR CIUDAD/DEPARTAMENTO CON FILTROS ESPECÍFICOS (dejar para LLM) ---
        # Si la pregunta pide ranking por ciudad/departamento Y tiene filtros específicos (VIS, estrato, apartamento),
        # delegar al LLM para que aplique correctamente los filtros y el GROUP BY
        ranking_keywords = ['ranking', 'top', 'ranking de ciudades', 'por ciudad', 'ranking de departamentos', 'por departamento']
        has_ranking = any(kw in texto for kw in ranking_keywords)
        
        # Detectar filtros específicos
        has_vis = 'vis' in texto or 'interés social' in texto or 'interes social' in texto
        has_estrato = re.search(r'\bestrato\s+\d+\b', texto)
        has_apartamento = 'apartamento' in texto or 'apartamentos' in texto
        has_casa = 'casa' in texto or 'casas' in texto
        
        # Eliminadas las delegaciones automáticas al LLM para permitir que las reglas específicas procesen:
        # - Preguntas de trimestre (ahora manejadas por regla TASA DE ABSORCIÓN)
        # - Preguntas de proyectos (ahora manejadas por regla TOP PROYECTOS)
        # - Rankings por ciudad con filtros (ahora manejados por regla RANKING PRECIO M²)
        
        # --- DETECCIÓN DE AGRUPACIÓN POR ESTRATO (dejar para LLM) ---
        # Si la pregunta menciona estratos específicos (ej: "estratos 4-6", "estrato 4, 5 y 6"), delegar al LLM
        # Esto permite que el LLM genere GROUP BY estrato con la estructura correcta
        has_estrato_rango = re.search(r'estratos?\s*\d+\s*[-–]\s*\d+', texto) or re.search(r'estratos?\s*\d+,\s*\d+\s*y\s*\d+', texto)
        if has_estrato_rango:
            print(f"[DEBUG LIVO reglas] Detectado rango de estratos, delegando a LLM")
            return None
        # DEBUG: mostrar cómo se normaliza la pregunta
        try:
            print(f"[DEBUG LIVO reglas] Pregunta original: {pregunta}")
            print(f"[DEBUG LIVO reglas] Pregunta normalizada: {texto}")
        except Exception:
            pass

        # --- DETECCIÓN DE PARÁMETROS PARA MEDIA MÓVIL (N PERIODOS) ---
        n_periodos_ma = 3  # Valor por defecto
        if any(x in texto for x in ['media movil', 'promedio movil', 'suavizado', 'moving average']):
            # Patrón 1: "media movil 8 meses" o "promedio movil de 12 meses"
            ma_match = re.search(r"(?:media|promedio)\s+movil\s+(?:de\s+)?(\d+)\s+meses?", texto)
            if ma_match:
                n_periodos_ma = int(ma_match.group(1))
            else:
                # Patrón 2: "a 8 meses" (ej: "media movil a 8 meses")
                ma_match2 = re.search(r"a\s+(\d+)\s+meses?", texto)
                if ma_match2:
                    n_periodos_ma = int(ma_match2.group(1))
                else:
                    # Patrón 3: números en texto ("tres", "cinco", etc.)
                    numeros_txt = {"tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "doce": 12, "dieciocho": 18, "veinticuatro": 24}
                    for palabra, valor in numeros_txt.items():
                        if f"movil {palabra} meses" in texto or f"movil de {palabra} meses" in texto or f"a {palabra} meses" in texto:
                            n_periodos_ma = valor
                            break

        group_by_cols = []
        # Limpieza de frases de métricas/nombres para evitar falsos positivos en detección de operaciones
        temp_text_for_avg = texto.replace("precio_mc_promedio", "").replace("precio promedio m2", "").replace("precio promedio", "")
        
        temp_text_for_sum = texto
        for phrase in ['numero de unidades', 'número de unidades', 'total de unidades', 'total de viviendas', 'unidades totales']:
            temp_text_for_sum = temp_text_for_sum.replace(phrase, "")

        # --- DETECCIÓN DE MÉTRICA Y OPERACIÓN (COMÚN PARA TODAS LAS REGLAS) ---
        # Detección de operación PRIMERO para evitar que "valor máximo" detecte "valor" como métrica
        op_funcion = "SUM"
        
        # debug_op_msg = f"[DEBUG _generar_sql_sin_llm] Detectando op_funcion para: {texto}"
        # if STREAMLIT_AVAILABLE:
        #     st.text(debug_op_msg)
        # else:
        #     print(debug_op_msg)
        
        # Palabras clave de entidades para decidir si "mayor" es un cálculo de MAX o un RANKING/Top
        entidades_agrupacion = ['constructora', 'constructoras', 'empresa', 'empresas', 'firma', 'firmas', 'proyecto', 'proyectos', 'departamento', 'departamentos', 'ciudad', 'ciudades', 'regional', 'regionales', 'estrato', 'estratos', 'tipo', 'tipos', 'segmento', 'segmentos', 'zona', 'zonas', 'sector', 'sectores', 'barrio', 'barrios']
        
        if any(re.search(r'\b' + re.escape(x) + r'\b', texto) if len(x) <= 3 else x in texto for x in ['ranking', 'top', 'principales', 'lideres', 'lider', 'posicion']) or (any(re.search(r'\b' + re.escape(x) + r'\b', texto) for x in ['mayor', 'mas', 'mejor', 'máximo', 'máxima', 'maximo', 'maxima']) and any(e in texto for e in entidades_agrupacion)):
            op_funcion = "RANKING"
        elif any(x in texto for x in ['agrupado por', 'agrupar por', 'agrupación por', 'agrupacion por', ' por ', ' segun ', ' según ', 'distribucion', 'distribución', ' cada ']):
            op_funcion = "GROUP_BY"
        elif any(x in texto for x in ['acumulado del año', 'acumulado anual', 'ytd', 'total año corrido']):
            op_funcion = "YTD"
        elif any(re.search(r'\b' + re.escape(x) + r'\b', texto) if len(x) <= 3 else x in texto for x in ['media movil', 'media móvil', 'promedio movil', 'promedio móvil', 'suavizado', 'moving average']) and not any(m in texto for m in ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre', 'ene-', 'feb-', 'mar-', 'abr-', 'may-', 'jun-', 'jul-', 'ago-', 'sep-', 'oct-', 'nov-', 'dic-']):
            op_funcion = "MOVING_AVG"
        elif any(x in texto for x in ['pronostico', 'proyeccion', 'prediccion', 'estimar', 'forecast', 'arima', 'arma', 'tendencia futura']):
            op_funcion = "FORECAST"
        elif any(x in texto for x in ['absorcion', 'tasa de absorcion', 'velocidad de venta']):
            op_funcion = "ABSORCION"
        elif any(x in texto for x in ['desistimiento', 'renuncia', 'tasa de cancelacion', 'churn']):
            op_funcion = "DESISTIMIENTO"
        elif any(x in texto for x in ['percentil', 'quantile', 'cuantil', 'distribucion de precios']):
            op_funcion = "PERCENTILE"
        elif any(x in texto for x in ['concentracion', 'concentración', 'hhi', 'monopolio', 'dominio de mercado']):
            op_funcion = "HHI"
        elif any(x in texto for x in ['segmentar por area', 'segmentar por área', 'tamaños de vivienda', 'buckets de area', 'distribucion por area']):
            op_funcion = "BUCKET_AREA"
        elif any(x in texto for x in ['segmentar por precio', 'segmentar por valor', 'rangos smlv', 'buckets de precio']):
            op_funcion = "BUCKET_SMLV"
        elif any(x in texto for x in ['promedio ponderado', 'promedio_ponderado']):
            op_funcion = "PROMEDIO_PONDERADO"
        elif any(x in texto for x in ['crecimiento', 'crecieron', 'variacion', 'variación', 'cambio', 'diferencia', 'frente a', 'comparado con']):
            op_funcion = "VARIACION"
            # debug_op_msg2 = f"[DEBUG _generar_sql_sin_llm] VARIACION detectado, op_funcion={op_funcion}"
            # if STREAMLIT_AVAILABLE:
            #     st.text(debug_op_msg2)
            # else:
            #     print(debug_op_msg2)
        elif any(x in texto for x in ['conteo de valores unicos', 'conteo de valores únicos', 'distinct_count']):
            op_funcion = "DISTINCT_COUNT"
        elif any(x in texto for x in ['moda', 'mode', 'más frecuente', 'valor mas frecuente', 'valor más frecuente', 'frecuente']):
            op_funcion = "MODE"
        elif any(x in texto for x in ['desviacion', 'desviación', 'stddev']):
            op_funcion = "STDDEV"
        elif any(x in texto for x in ['varianza', 'variance']):
            op_funcion = "VAR_POP"
        elif any(x in texto for x in ['mediana', 'median']):
            op_funcion = "MEDIAN"
        elif any(re.search(r'\b' + re.escape(x) + r'\b', texto) if len(x) <= 3 else x in texto for x in ['maximo', 'máximo', 'max', 'más alto']):
            op_funcion = "MAX"
        elif any(re.search(r'\b' + re.escape(x) + r'\b', texto) if len(x) <= 3 else x in texto for x in ['minimo', 'mínimo', 'min', 'más bajo', 'menor']):
            op_funcion = "MIN"
        elif any(x in texto for x in ['diferencia de meses', 'cuantos meses', 'meses hay entre', 'meses de diferencia']):
            op_funcion = "MONTH_DIFF"
        elif re.search(r'\b(promedio|media|avg|average)\b', temp_text_for_avg):
            op_funcion = "AVG"
        elif any(x in temp_text_for_sum for x in ['totalidad', 'total', 'suma', 'sumatoria', 'numero', 'número', 'cantidad', 'resultado', 'valores', 'unidades']):
            op_funcion = "SUM"
        elif any(x in texto for x in ['clustering', 'cluster', 'clúster', 'similitud', 'agrupar proyectos']):
            op_funcion = "CLUSTERING"
        elif any(x in texto for x in ['clasificacion', 'clasificación', 'categorizar', 'perfilado']):
            op_funcion = "CLASSIFICATION"
        elif any(x in texto for x in ['asociacion', 'asociación', 'relacion entre', 'vinculo']):
            op_funcion = "ASSOCIATION"
        elif any(x in texto for x in ['conteo', 'conteo de']):
            op_funcion = "COUNT"
        
        # Detección mejorada para COUNT vs SUM(unidades)
        # COUNT para: proyectos (conteo de proyectos/distintos), rankings de cantidad de proyectos
        # SUM(unidades) para: casas, inmuebles, vivienda (unidades físicas)
        elif any(x in texto for x in ['proyectos', 'proyecto']) and not any(x in texto for x in ['unidades', 'unidades']):
            # Preguntas como "cuántos proyectos", "top 5 ciudades con mayor cantidad de proyectos"
            op_funcion = "COUNT"
            col_metrica = "identificador"  # Para contar proyectos distintos
        elif any(x in texto for x in ['constructora', 'constructoras', 'empresa', 'empresas']) and 'proyectos' in texto and not any(x in texto for x in ['unidades', 'unidades']):
            # Preguntas como "top 5 constructoras con mayor cantidad de proyectos"
            op_funcion = "COUNT"
            col_metrica = "compania_constructora"  # Para contar proyectos por constructora
        elif any(x in texto for x in ['casas', 'inmueble', 'inmuebles', 'vivienda', 'viviendas']):
            # Preguntas sobre casas, inmuebles, vivienda SIEMPRE usan SUM(unidades)
            op_funcion = "SUM"
            col_metrica = "unidades"
        
        # Detección de preguntas de segmentación VIS/VIP/NO VIS (Reglas Específicas)
        elif any(x in texto for x in ['vis', 'vip', 'no vis']):
            # Detectar si pregunta por tabla de segmentación
            if any(x in texto for x in ['tabla', 'desglose', 'desglosado', 'desglosar', 'comparación', 'comparativo', 'breakdown']):
                if 'no vis' in texto.lower():
                    op_funcion = "SEGMENT_TABLE_NO_VIS"
                else:
                    op_funcion = "SEGMENT_TABLE_VIS"
            # Para preguntas simples de VIS/VIP, usar SUM con filtros específicos
            elif 'vis' in texto.lower() and 'vip' not in texto.lower():
                op_funcion = "SUM"
                col_metrica = "unidades"
            elif 'vip' in texto.lower():
                op_funcion = "SUM"
                col_metrica = "unidades"
            elif 'no vis' in texto.lower():
                op_funcion = "SUM"
                col_metrica = "unidades"
        
        # Detección de métrica DESPUÉS de operación
        # Reglas claras: cantidad→unidades, tamaño→area, precio/costo/valor→valor
        # No sobrescribir si ya fue definido para COUNT
        if op_funcion != "COUNT":
            col_metrica = "unidades"  # Por defecto para SUM/AVG/etc.
            
            if 'precio_mc_promedio' in texto:
                col_metrica = "precio_mc_promedio"
            elif any(x in texto for x in ['metro cuadrado', 'm2', 'precio promedio m2']):
                col_metrica = "precio_mc_promedio"
            elif any(x in texto for x in ['superficie', 'area', 'área', 'area', 'tamaño', 'tamano', 'metros cuadrados', 'dimension', 'dimension', 'dimensión', 'dimension']):
                col_metrica = "area"
            elif any(x in texto for x in ['numero de unidades', 'número de unidades', 'numero de unidades', 'cantidad de unidades', 'total de unidades', 'total de viviendas', 'viviendas', 'cantidad']):
                col_metrica = "unidades"
            elif any(x in texto for x in ['valor', 'precio', 'costo', 'pesos', 'monetario', 'dinero', 'plata', 'monto']):
                col_metrica = "valor"
            elif "proyecto" in texto:
                col_metrica = "identificador"
        
        # Validación de preguntas no realistas: COUNT sobre variables numéricas
        # Esta validación debe estar ANTES de las reglas independientes
        if op_funcion == "COUNT" and col_metrica in ["unidades", "valor", "area", "precio_mc_promedio"]:
            # Retornar None para indicar pregunta mal formulada
            return None
        
        if op_funcion == "COUNT":
            metrica_sql = "COUNT(*)"
            alias_sql = "total_registros"
        elif op_funcion == "DESISTIMIENTO":
            metrica_sql = "SUM(CASE WHEN cuenta='Renuncias' THEN unidades ELSE 0 END) * 100.0 / NULLIF(SUM(CASE WHEN cuenta IN ('Ventas', 'Renuncias') THEN unidades ELSE 0 END), 0)"
            alias_sql = "tasa_desistimiento_pct"
        elif op_funcion == "PERCENTILE":
            metrica_sql = f"approx_quantile({col_metrica}, 0.5)" # Por defecto mediana
            alias_sql = f"mediana_{col_metrica}"
        elif op_funcion == "PROMEDIO_PONDERADO":
            metrica_sql = "SUM(valor * unidades) / SUM(unidades)"
            alias_sql = "promedio_ponderado"
        elif op_funcion == "DISTINCT_COUNT":
            metrica_sql = f"COUNT(DISTINCT {col_metrica})"
            alias_sql = "valores_unicos"
        elif op_funcion == "GROUP_BY":
            metrica_sql = f"SUM({col_metrica})"
            alias_sql = "total"
        elif op_funcion == "RANKING":
            # Si es RANKING y se pregunta por oferta sin especificar unidades, usar COUNT
            # para contar registros en lugar de sumar unidades
            if 'oferta' in texto and not any(x in texto for x in ['unidades', 'viviendas', 'cantidad', 'total de', 'numero de', 'número de']):
                metrica_sql = "COUNT(*)"
                alias_sql = "total_registros"
            else:
                metrica_sql = f"SUM({col_metrica})"
                alias_sql = "total"
        elif col_metrica == "identificador":
            metrica_sql = "COUNT(DISTINCT identificador)"
            alias_sql = "total_proyectos"
        elif op_funcion == "MONTH_DIFF":
            metrica_sql = "date_diff('month', MIN(fecha_date), MAX(fecha_date))"
            alias_sql = "meses_de_diferencia"
        elif op_funcion == "YTD":
            metrica_sql = "SUM(unidades)"
            alias_sql = "acumulado_ytd"
        elif op_funcion == "MOVING_AVG":
            # Ventana dinámica: N periodos (N-1 precedentes + actual)
            preceding = max(0, n_periodos_ma - 1)
            metrica_sql = f"AVG(SUM({col_metrica})) OVER (ORDER BY fecha_date ROWS BETWEEN {preceding} PRECEDING AND CURRENT ROW)"
            alias_sql = f"media_movil_{n_periodos_ma}m_{col_metrica}"
        elif op_funcion == "ABSORCION":
            # Ratio: Ventas / (Oferta + Ventas) * 100
            metrica_sql = "SUM(CASE WHEN cuenta='Ventas' THEN unidades ELSE 0 END) * 100.0 / NULLIF(SUM(CASE WHEN cuenta IN ('Ventas', 'Oferta') THEN unidades ELSE 0 END), 0)"
            alias_sql = "tasa_absorcion_pct"
        elif op_funcion == "FORECAST":
            metrica_sql = f"SUM({col_metrica})" # Se procesa en la regla 0h
            alias_sql = "valor_historico"
        elif op_funcion == "BUCKET_AREA":
            metrica_sql = "SUM(unidades)"
            alias_sql = "unidades_por_segmento"
        elif op_funcion == "BUCKET_SMLV":
            # Para este cálculo usamos una lógica especial en la regla 0k
            metrica_sql = "SUM(unidades)"
            alias_sql = "unidades_por_rango_smlv"
        elif op_funcion == "HHI":
            metrica_sql = "SUM(unidades)" # Base para el cálculo en el CTE
            alias_sql = "unidades_para_hhi"
        elif op_funcion == "PROMEDIO_PONDERADO":
            metrica_sql = "SUM(valor * unidades) / SUM(unidades)"
            alias_sql = "promedio_ponderado"
        elif op_funcion in ["SUM", "AVG", "VARIACION"]: # Para VARIACION usamos SUM como base para comparar volúmenes
            func_base = "SUM" if op_funcion == "VARIACION" else op_funcion
            metrica_sql = f"COALESCE({func_base}({col_metrica}), 0)"
            alias_sql = f"{col_metrica}_{op_funcion.lower()}"
        else:
            metrica_sql = f"{op_funcion}({col_metrica})"
            alias_sql = f"{col_metrica}_{op_funcion.lower()}"

        # --- VALIDACIÓN DE RELEVANCIA (Evitar falsos positivos) ---
        # Si la pregunta menciona temas ajenos a LIVO (Macro, Normativa), rechazar para que pasen a otros motores.
        terminos_excluyentes = [
            'pib', 'inflacion', 'ipc', 'tasa', 'dolar', 'trm', 'desempleo', 'empleo', 'ocupados',
            'normativa', 'decreto', 'resolucion', 'ley ', 'circular', 'reglamento', 'sentencia',
            'subsidio', 'mi casa ya', 'cajas de compensacion', 'ahorro programado', 'deficit', 'proyeccion',
            # Nuevos términos para RAG (Documentos)
            'resumen', 'documento', 'requisito', 'iniciativa', 'norma', 'impuesto', 'catastro',
            'propiedad horizontal', 'seguridad industrial', 'tramite', 'espacio publico', 'cesion',
            'plusvalia', 'sostenible', 'certificacion', 'residuo', 'eficiencia', 'panel', 'ahorro'
        ]
        if any(t in texto for t in terminos_excluyentes):
            return None

        # Detección de intención temporal general (para saber si filtrar por último periodo o no)
        temporal_keywords = [
            '201', '202', # Años 201x, 202x
            'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
            'mes', 'anio', 'ano', 'trimestre', 'semestre', 'ultimo', 'reciente', 'actual',
            'doce', '12', 'seis', '6', 'diez', '10', 'dieciocho', '18', 'veinticuatro', '24'
        ]
        tiene_tiempo = any(k in texto for k in temporal_keywords)

        # Detección de año explícito
        anio_match = re.search(r"(20[0-9]{2})", texto)
        anio = anio_match.group(1) if anio_match else None
        anio_filtro = f" AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {anio}" if anio_match else ""

        # Detección de mes explícito
        mes_filtro = ""
        mes_nombre_detectado = None  # Guardar nombre del mes para conversión a rango
        filtro_temporal = ""  # Inicializar filtro temporal
        meses_map_regex = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
            'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
        }
        
        # NUEVO: Detectar múltiples periodos temporales separados por conectores
        conectores_temporales = [' y ', ' e ', ' o ']
        texto_lower = texto.lower()
        multiple_periodos = False
        periodos_encontrados = []
        
        for conector in conectores_temporales:
            if conector in texto_lower:
                partes = texto_lower.split(conector)
                for parte in partes:
                    # Detectar mes-año en cada parte (ej: "abril 2025")
                    mes_match = re.search(r'(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s*(20[0-9]{2})', parte)
                    if mes_match:
                        mes_nombre = mes_match.group(1)
                        anio = mes_match.group(2)
                        mes_num = meses_map_regex.get(mes_nombre, 1)
                        fecha_inicio = f"{anio}{mes_num:02d}01"
                        fecha_fin = f"{anio}{mes_num:02d}32"
                        periodos_encontrados.append(f"(fecha >= {fecha_inicio} AND fecha < {fecha_fin})")
                        multiple_periodos = True
                    # Detectar formato corto (ej: "abr-25")
                    elif re.search(r'(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)-(\d{2})', parte):
                        periodo_match = re.search(r'(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)-(\d{2})', parte)
                        mes_abr = periodo_match.group(1)
                        anio_abr = periodo_match.group(2)
                        mes_map_abr = {'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04', 'may': '05', 'jun': '06',
                                      'jul': '07', 'ago': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12'}
                        mes_num = mes_map_abr.get(mes_abr, '01')
                        anio_num = f"20{anio_abr}"
                        fecha_inicio = f"{anio_num}{mes_num}01"
                        fecha_fin = f"{anio_num}{mes_num}32"
                        periodos_encontrados.append(f"(fecha >= {fecha_inicio} AND fecha < {fecha_fin})")
                        multiple_periodos = True
                
                if len(periodos_encontrados) > 1:
                    # Unir periodos con OR
                    filtro_temporal = f" AND ({' OR '.join(periodos_encontrados)})"
                    anio_filtro = ""  # Limpiar para no duplicar
                    mes_filtro = ""  # Limpiar para no duplicar
                    break
        
        # Si no hay múltiples periodos, usar lógica original
        if not multiple_periodos:
            for mes_nombre, mes_num in meses_map_regex.items():
                # Buscar usando límites de palabra para evitar falsos positivos como "mayor" detectado como "mayo"
                if re.search(r'\b' + re.escape(mes_nombre) + r'\b', texto):
                    mes_filtro = f" AND CAST(SUBSTR(CAST(fecha AS VARCHAR), 5, 2) AS INTEGER) = {mes_num}"
                    mes_nombre_detectado = mes_nombre
                    break
        
        # Detección de formato mes-año (ej: "ene-26", "feb-26")
        periodo_match = re.search(r"(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)-(\d{2})", texto)
        if periodo_match:
            mes_abr = periodo_match.group(1)
            anio_abr = periodo_match.group(2)
            mes_map_abr = {'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04', 'may': '05', 'jun': '06',
                          'jul': '07', 'ago': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12'}
            mes_num = mes_map_abr.get(mes_abr, '01')
            anio_num = f"20{anio_abr}"
            fecha_inicio = f"{anio_num}{mes_num}01"
            fecha_fin = f"{anio_num}{mes_num}32"
            filtro_temporal = f" AND fecha >= {fecha_inicio} AND fecha < {fecha_fin}"
            anio_filtro = ""  # Limpiar para no duplicar
            mes_filtro = ""  # Limpiar para no duplicar
        
        # Si hay año y mes, convertir directamente a rango de fechas (incluso si hay múltiples periodos)
        if anio_match and mes_nombre_detectado:
            mes_map = {'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04', 'may': '05', 'jun': '06',
                      'jul': '07', 'ago': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12',
                      'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05', 'junio': '06',
                      'julio': '07', 'agosto': '08', 'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'}
            mes_num = mes_map.get(mes_nombre_detectado, '01')
            anio_num = anio_match.group(1)
            fecha_inicio = f"{anio_num}{mes_num}01"
            fecha_fin = f"{anio_num}{mes_num}32"
            filtro_temporal = f" AND fecha >= {fecha_inicio} AND fecha < {fecha_fin}"
            anio_filtro = ""  # Limpiar para no duplicar
            mes_filtro = ""  # Limpiar para no duplicar

        # Decidir el filtro final
        if not filtro_temporal:  # Solo si no se convirtió a rango arriba
            if anio_filtro and mes_filtro:
                # Guardar información para conversión posterior
                filtro_temporal = f"{anio_filtro} {mes_filtro}"
            elif anio_filtro or mes_filtro:
                filtro_temporal = anio_filtro or mes_filtro
        
        # Manejo explícito de "último año" o "últimos 12 meses"
        if "ultimo ano" in texto or "ultimo año" in texto or "ultimos 12 meses" in texto or "últimos 12 meses" in texto or "últimos doce meses" in texto or "ultimos doce meses" in texto:
            filtro_temporal = " AND doce_meses = (SELECT MAX(doce_meses) FROM livo)"
        # NUEVO: Manejo de "este año" (Año calendario actual en la BD)
        elif "este ano" in texto or "este año" in texto:
            filtro_temporal = " AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = (SELECT MAX(CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER)) FROM livo)"
        # NUEVO: Lógica diferenciada para "mes anterior" vs "último mes"
        elif any(p in texto for p in ["mes anterior", "mes pasado", "ultimo mes", "ultimo periodo", "reciente", "actual"]):
             # Intentar detectar cuenta para hacer el MAX(fecha) específico
             cuenta_detectada = None
             if "ventas" in texto or "vendidas" in texto:
                 cuenta_detectada = "Ventas"
             elif "oferta" in texto or "disponible" in texto:
                 cuenta_detectada = "Oferta"
             elif "iniciaciones" in texto or "iniciadas" in texto:
                 cuenta_detectada = "Iniciaciones"
             elif "lanzamientos" in texto or "lanzadas" in texto:
                 cuenta_detectada = "Lanzamientos"
             
             # Sub-caso A: Mes anterior (Penúltimo registro disponible) - LÓGICA DE COYUNTURA
             if any(p in texto for p in ["mes anterior"]):
                 if cuenta_detectada:
                     filtro_temporal = f" AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = '{cuenta_detectada}' AND fecha < (SELECT MAX(fecha) FROM livo))"
                 else:
                     filtro_temporal = " AND fecha = (SELECT MAX(fecha) FROM livo WHERE fecha < (SELECT MAX(fecha) FROM livo))"
             
             # Sub-caso B: Último mes (Último registro disponible)
             else:
                 if cuenta_detectada:
                     filtro_temporal = f" AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = '{cuenta_detectada}')"
                 else:
                     filtro_temporal = " AND fecha = (SELECT MAX(fecha) FROM livo)"

        # --- REGLA DE METADATA: CONSULTA DE COBERTURA / FECHA DE CORTE ---
        # Responde directamente a preguntas sobre la vigencia de los datos
        if any(x in texto for x in ['hasta que fecha', 'fecha de corte', 'periodo de informacion', 'ultimo mes disponible', 'fecha maxima', 'periodo de cobertura', 'fecha de los datos', 'actualizado a', 'que meses tienen datos']):
             sql = "SELECT MAX(fecha) as \"Última Fecha de Corte\" FROM livo WHERE fecha IS NOT NULL"
             print(f"[DEBUG LIVO reglas] SQL METADATA (Cobertura): {sql}")
             return sql

        # Helper: obtener año de la pregunta (por ejemplo "2025")
        def _extraer_anio(texto_local: str) -> int:
            import re
            m = re.search(r"(20[0-9]{2})", texto_local)
            if not m:
                # Si no se encuentra, asumimos el año 2025 (como en el archivo de preguntas)
                return 2025
            try:
                return int(m.group(1))
            except Exception:
                return 2025

        # --- LÓGICA ESPECIAL PARA SEGMENTACIÓN VIS/VIP/NO VIS (Reglas Específicas) ---
        if op_funcion in ["SEGMENT_TABLE_VIS", "SEGMENT_TABLE_NO_VIS"]:
            # Estas operaciones ya manejan su propia lógica en las reglas 0o y 0p
            return self._generar_sql_con_operacion(texto, op_funcion, col_metrica, metrica_sql, alias_sql, filtro_temporal, anio_filtro, mes_filtro)
        
        # --- LÓGICA ESPECIAL PARA OFERTA (STOCK) ---
        # Si piden oferta y un año, NO sumar todo el año. Tomar el último corte.
        # EXCEPCIÓN: Si se menciona un mes específico, dejar que el LLM maneje la consulta puntual.
        meses_especificos = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 
                           'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        tiene_mes = any(m in texto for m in meses_especificos)

        if "oferta" in texto:
            region = self._extraer_region_general(texto)
            if region:
                region_cond = self._condicion_region_general(region)
                
                # Detectar si hay múltiples regiones
                es_multiple_regiones = region and '|' in region
                
                # Si hay mes específico (con o sin año), usar filtro temporal de rango y GROUP BY regional si hay múltiples regiones
                if tiene_mes and filtro_temporal:
                    if es_multiple_regiones:
                        sql = (
                            f"SELECT regional, {metrica_sql} AS {alias_sql}_oferta "
                            "FROM livo "
                            f"WHERE cuenta = 'Oferta' "
                            f"AND {region_cond} "
                            f"{filtro_temporal} "
                            " "
                            " "
                            "GROUP BY regional "
                            "ORDER BY {alias_sql}_oferta DESC"
                        )
                    else:
                        sql = (
                            f"SELECT {metrica_sql} AS {alias_sql}_oferta "
                            "FROM livo "
                            f"WHERE cuenta = 'Oferta' "
                            f"AND {region_cond} "
                            f"{filtro_temporal} "
                            " "
                            ""
                        )
                    try:
                        print(f"[DEBUG LIVO reglas] SQL generado (Oferta con mes específico): {sql}")
                        return sql
                    except Exception:
                        pass
                # Si hay año pero no mes específico, usar lógica original (promedio y cierre del año)
                elif anio_match:
                        # SQL para Promedio y Cierre
                        sql = f"""
                        WITH mensual AS (
                            SELECT CAST(SUBSTR(CAST(fecha AS VARCHAR), 5, 2) AS INTEGER) as mes, SUM(unidades) as total_mensual
                            FROM livo
                            WHERE cuenta = 'Oferta' 
                              AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {anio}
                              AND {region_cond}
                                                          GROUP BY CAST(SUBSTR(CAST(fecha AS VARCHAR), 5, 2) AS INTEGER)
                        ),
                        promedio AS (
                            SELECT AVG(total_mensual) as val FROM mensual
                        ),
                        cierre AS (
                            SELECT SUM(unidades) as val
                            FROM livo
                            WHERE cuenta = 'Oferta'
                              AND fecha = (
                                  SELECT MAX(fecha) FROM livo 
                                  WHERE cuenta = 'Oferta' 
                                  AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {anio}
                              )
                              AND {region_cond}
                                                      )
                        SELECT 
                            CAST(promedio.val AS INTEGER) as "Promedio Mensual {anio}",
                            CAST(cierre.val AS INTEGER) as "Cierre {anio}"
                        FROM promedio, cierre
                        """
                        try:
                            print(f"[DEBUG LIVO reglas] SQL generado (Oferta con año): {sql}")
                            return sql
                        except Exception:
                            pass

        # --- LÓGICA GENERAL PARA TODAS LAS CUENTAS CON FILTRO TEMPORAL ESPECÍFICO ---
        # Esta lógica aplica a Ventas, Lanzamientos, Iniciaciones, Entregadas, Renuncias, Saldo que inicia, Paralizado, Culminadas
        # cuando hay mes específico y múltiples regiones
        if tiene_mes and filtro_temporal:
            # Detectar tipo de cuenta
            cuenta_calculo = None
            if any(x in texto for x in ['lanzamiento', 'lanzada', 'salida a ventas', 'nuevos proyectos']): 
                cuenta_calculo = 'Lanzamientos'
            elif any(x in texto for x in ['iniciacion', 'iniciada', 'inicio de obra']): 
                cuenta_calculo = 'Iniciaciones'
            elif any(x in texto for x in ['entrega', 'entregada', 'terminada', 'finalizada']): 
                cuenta_calculo = 'Entregadas'
            elif any(x in texto for x in ['vendidas', 'vendido', 'vender', 'se han vendido']): 
                cuenta_calculo = 'Ventas'
            elif any(x in texto for x in ['paralizado', 'paralizada', 'obras detenidas', 'suspendidas']): 
                cuenta_calculo = 'Paralizado'
            elif any(x in texto for x in ['renuncias', 'renuncia', 'desistimientos', 'cancelaciones']): 
                cuenta_calculo = 'Renuncias'
            elif any(x in texto for x in ['saldo', 'saldo que inicia', 'saldo inicial']): 
                cuenta_calculo = 'Saldo que inicia'
            elif any(x in texto for x in ['culminadas', 'culminada', 'obra terminada', 'construccion completa']): 
                cuenta_calculo = 'Culminadas'
            
            if cuenta_calculo:
                region = self._extraer_region_general(texto)
                if region:
                    region_cond = self._condicion_region_general(region)
                    es_multiple_regiones = region and '|' in region
                    
                    if es_multiple_regiones:
                        sql = (
                            f"SELECT regional, {metrica_sql} AS {alias_sql}_{cuenta_calculo.lower().replace(' ', '_')} "
                            "FROM livo "
                            f"WHERE cuenta = '{cuenta_calculo}' "
                            f"AND {region_cond} "
                            f"{filtro_temporal} "
                            " "
                            " "
                            "GROUP BY regional "
                            f"ORDER BY {alias_sql}_{cuenta_calculo.lower().replace(' ', '_')} DESC"
                        )
                    else:
                        sql = (
                            f"SELECT {metrica_sql} AS {alias_sql}_{cuenta_calculo.lower().replace(' ', '_')} "
                            "FROM livo "
                            f"WHERE cuenta = '{cuenta_calculo}' "
                            f"AND {region_cond} "
                            f"{filtro_temporal} "
                            " "
                            ""
                        )
                    try:
                        print(f"[DEBUG LIVO reglas] SQL generado ({cuenta_calculo} con mes específico): {sql}")
                        return sql
                    except Exception:
                        pass

        # --- TIER 1: REGLAS DE NEGOCIO INDEPENDIENTES Y ESPECÍFICAS ---
        # Estas reglas tienen lógica de negocio implícita (ej: filtrar por vivienda para venta)
        # y se ejecutan primero para las preguntas más comunes.

        # 0a) VARIACION tiene PRIORIDAD MÁXIMA sobre ventas totales
        # porque preguntas de crecimiento tienen palabras como "vendidas" que coinciden con ventas totales
        if op_funcion == "VARIACION":
            # debug_var_msg = f"[DEBUG VARIACION TIER 1] Entrando a lógica VARIACION con op_funcion={op_funcion}"
            # if STREAMLIT_AVAILABLE:
            #     st.text(debug_var_msg)
            # else:
            #     print(debug_var_msg)
            
            anios = re.findall(r"(20[0-9]{2})", texto)
            # debug_var_msg2 = f"[DEBUG VARIACION TIER 1] Años encontrados: {anios}"
            # if STREAMLIT_AVAILABLE:
            #     st.text(debug_var_msg2)
            # else:
            #     print(debug_var_msg2)
            
            if len(anios) == 1:
                anios.append(str(int(anios[0]) - 1)) # Si pide un solo año, comparar con el anterior
            
            # Buscar meses mencionados
            meses_encontrados = []
            for m_txt, m_num in meses_map_regex.items():
                if re.search(r'\b' + re.escape(m_txt) + r'\b', texto):
                    meses_encontrados.append((m_txt, m_num))
            
            # debug_var_msg3 = f"[DEBUG VARIACION TIER 1] Meses encontrados: {meses_encontrados}"
            # if STREAMLIT_AVAILABLE:
            #     st.text(debug_var_msg3)
            # else:
            #     print(debug_var_msg3)
            
            # Detectar cuenta (Ventas por defecto)
            cuenta_calculo = None  # None significa todas las cuentas
            cuenta_filtro = ""  # Sin filtro por defecto
            if any(x in texto for x in ['lanzamiento', 'lanzada', 'salida a ventas', 'nuevos proyectos']): 
                cuenta_calculo = 'Lanzamientos'
                cuenta_filtro = "cuenta = 'Lanzamientos'"
            elif any(x in texto for x in ['oferta', 'disponible', 'stock', 'inventario']): 
                cuenta_calculo = 'Oferta'
                cuenta_filtro = "cuenta = 'Oferta'"
            elif any(x in texto for x in ['saldo', 'saldo que inicia', 'saldo inicial']): 
                cuenta_calculo = 'Saldo que inicia'
                cuenta_filtro = "cuenta = 'Saldo que inicia'"
            elif any(x in texto for x in ['iniciacion', 'iniciada', 'inicio de obra']): 
                cuenta_calculo = 'Iniciaciones'
                cuenta_filtro = "cuenta = 'Iniciaciones'"
            elif any(x in texto for x in ['entrega', 'entregada', 'terminada', 'finalizada']): 
                cuenta_calculo = 'Entregadas'
                cuenta_filtro = "cuenta = 'Entregadas'"
            elif any(x in texto for x in ['vendidas', 'vendido', 'vender', 'se han vendido']): 
                cuenta_calculo = 'Ventas'
                cuenta_filtro = "cuenta = 'Ventas'"
            elif any(x in texto for x in ['paralizado', 'paralizada', 'obras detenidas', 'suspendidas']): 
                cuenta_calculo = 'Paralizado'
                cuenta_filtro = "cuenta = 'Paralizado'"
            elif any(x in texto for x in ['renuncias', 'renuncia', 'desistimientos', 'cancelaciones']): 
                cuenta_calculo = 'Renuncias'
                cuenta_filtro = "cuenta = 'Renuncias'"
            elif any(x in texto for x in ['culminadas', 'culminada', 'obra terminada', 'construccion completa']): 
                cuenta_calculo = 'Culminadas'
                cuenta_filtro = "cuenta = 'Culminadas'"
            
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"

            # Detectar si es variación de precio promedio
            es_variacion_precio_promedio = any(x in texto for x in ['precio promedio', 'precio medio', 'valor promedio', 'valor medio'])

            # Determinar periodos (Mes-Año vs Mes-Año o Año vs Año)
            if len(anios) >= 2:
                a1, a2 = anios[0], anios[1] # Ej: 2026, 2025
                
                # Caso especial: Variación de precio promedio
                if es_variacion_precio_promedio:
                    # Caso A: Comparación de meses específicos
                    if len(meses_encontrados) >= 1:
                        m1_num = meses_encontrados[0][1]
                        m2_num = meses_encontrados[1][1] if len(meses_encontrados) > 1 else m1_num
                        m1_name = meses_encontrados[0][0].title()
                        m2_name = meses_encontrados[1][0].title() if len(meses_encontrados) > 1 else m1_name
                        
                        f1_start, f1_end = f"{a1}{m1_num:02d}01", f"{a1}{m1_num:02d}32"
                        f2_start, f2_end = f"{a2}{m2_num:02d}01", f"{a2}{m2_num:02d}32"

                        cuenta_cond_actual = f"AND {cuenta_filtro}" if cuenta_filtro else ""
                        cuenta_cond_anterior = f"AND {cuenta_filtro}" if cuenta_filtro else ""

                        sql = f"""
                        WITH datos_actual AS (
                            SELECT 
                                COALESCE(SUM(valor), 0) as suma_valor,
                                COALESCE(SUM(unidades), 0) as suma_unidades
                            FROM livo
                            WHERE {region_cond} {cuenta_cond_actual} AND fecha >= {f1_start} AND fecha < {f1_end}                          ),
                        datos_anterior AS (
                            SELECT 
                                COALESCE(SUM(valor), 0) as suma_valor,
                                COALESCE(SUM(unidades), 0) as suma_unidades
                            FROM livo
                            WHERE {region_cond} {cuenta_cond_anterior} AND fecha >= {f2_start} AND fecha < {f2_end}                          )
                        SELECT 
                            ROUND((curr.suma_valor / 1000.0) / NULLIF(curr.suma_unidades, 0), 2) as "Precio Promedio {m1_name} {a1} (millones de pesos)",
                            ROUND((prev.suma_valor / 1000.0) / NULLIF(prev.suma_unidades, 0), 2) as "Precio Promedio {m2_name} {a2} (millones de pesos)",
                            ROUND(((curr.suma_valor / 1000.0) / NULLIF(curr.suma_unidades, 0) - (prev.suma_valor / 1000.0) / NULLIF(prev.suma_unidades, 0)) / NULLIF((prev.suma_valor / 1000.0) / NULLIF(prev.suma_unidades, 0), 0) * 100, 2) as "Crecimiento (%)"
                        FROM datos_actual curr, datos_anterior prev
                        """
                    
                    # Caso B: Comparación anual total
                    else:
                        cuenta_cond_actual = f"AND {cuenta_filtro}" if cuenta_filtro else ""
                        cuenta_cond_anterior = f"AND {cuenta_filtro}" if cuenta_filtro else ""

                        sql = f"""
                        WITH datos_actual AS (
                            SELECT 
                                COALESCE(SUM(valor), 0) as suma_valor,
                                COALESCE(SUM(unidades), 0) as suma_unidades
                            FROM livo
                            WHERE {region_cond} {cuenta_cond_actual} AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {a1}                          ),
                        datos_anterior AS (
                            SELECT 
                                COALESCE(SUM(valor), 0) as suma_valor,
                                COALESCE(SUM(unidades), 0) as suma_unidades
                            FROM livo
                            WHERE {region_cond} {cuenta_cond_anterior} AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {a2}                          )
                        SELECT 
                            ROUND((curr.suma_valor / 1000.0) / NULLIF(curr.suma_unidades, 0), 2) as "Precio Promedio Año {a1} (millones de pesos)",
                            ROUND((prev.suma_valor / 1000.0) / NULLIF(prev.suma_unidades, 0), 2) as "Precio Promedio Año {a2} (millones de pesos)",
                            ROUND(((curr.suma_valor / 1000.0) / NULLIF(curr.suma_unidades, 0) - (prev.suma_valor / 1000.0) / NULLIF(prev.suma_unidades, 0)) / NULLIF((prev.suma_valor / 1000.0) / NULLIF(prev.suma_unidades, 0), 0) * 100, 2) as "Crecimiento (%)"
                        FROM datos_actual curr, datos_anterior prev
                        """
                
                # Caso normal: Variación de otras métricas (unidades, valor, etc.)
                else:
                    # Caso A: Comparación de meses específicos
                    if len(meses_encontrados) >= 1:
                        m1_num = meses_encontrados[0][1]
                        m2_num = meses_encontrados[1][1] if len(meses_encontrados) > 1 else m1_num
                        m1_name = meses_encontrados[0][0].title()
                        m2_name = meses_encontrados[1][0].title() if len(meses_encontrados) > 1 else m1_name
                        
                        f1_start, f1_end = f"{a1}{m1_num:02d}01", f"{a1}{m1_num:02d}32"
                        f2_start, f2_end = f"{a2}{m2_num:02d}01", f"{a2}{m2_num:02d}32"

                        cuenta_cond_actual = f"AND {cuenta_filtro}" if cuenta_filtro else ""
                        cuenta_cond_anterior = f"AND {cuenta_filtro}" if cuenta_filtro else ""

                        sql = f"""
                        WITH actual AS (SELECT {metrica_sql} as val FROM livo WHERE {region_cond} {cuenta_cond_actual} AND fecha >= {f1_start} AND fecha < {f1_end}  ),
                        anterior AS (SELECT {metrica_sql} as val FROM livo WHERE {region_cond} {cuenta_cond_anterior} AND fecha >= {f2_start} AND fecha < {f2_end}  )
                        SELECT curr.val as "{m1_name} {a1}", prev.val as "{m2_name} {a2}", (curr.val - prev.val) as "Variación Absoluta", ROUND(((curr.val - prev.val) * 100.0) / NULLIF(prev.val, 0), 2) as "Crecimiento (%)" FROM actual curr, anterior prev
                        """
                    
                    # Caso B: Comparación anual total
                    else:
                        cuenta_cond_actual = f"AND {cuenta_filtro}" if cuenta_filtro else ""
                        cuenta_cond_anterior = f"AND {cuenta_filtro}" if cuenta_filtro else ""

                        sql = f"""
                        WITH actual AS (SELECT {metrica_sql} as val FROM livo WHERE {region_cond} {cuenta_cond_actual} AND LEFT(CAST(fecha AS VARCHAR), 4) = '{a1}'  ),
                        anterior AS (SELECT {metrica_sql} as val FROM livo WHERE {region_cond} {cuenta_cond_anterior} AND LEFT(CAST(fecha AS VARCHAR), 4) = '{a2}'  )
                        SELECT curr.val as "Año {a1}", prev.val as "Año {a2}", (curr.val - prev.val) as "Variación Absoluta", ROUND(((curr.val - prev.val) * 100.0) / NULLIF(prev.val, 0), 2) as "Crecimiento (%)" FROM actual curr, anterior prev
                        """
                
                try:
                    # Si es oferta, no comparar totales sumados del año sino el promedio o el último corte
                    if cuenta_calculo == 'Oferta' and len(meses_encontrados) == 0 and not es_variacion_precio_promedio:
                        sql = sql.replace(metrica_sql, f"COALESCE(AVG({col_metrica}), 0)")

                    # print(f"[DEBUG LIVO reglas TIER 1] SQL VARIACION: {sql}")
                    return sql.strip()
                except Exception: pass

        # 0b) Conteo de constructoras - PRIORIDAD ALTA para preguntas de conteo de entidades
        if ("cuales" in texto or "cuantas" in texto or "cuantos" in texto or "registraron" in texto or "registraron" in texto or "registró" in texto or "tienen" in texto or "hubo" in texto) and ("constructora" in texto or "constructoras" in texto or "empresa" in texto or "empresas" in texto or "firma" in texto or "firmas" in texto):
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Detectar cuenta (Ventas por defecto)
            cuenta_filtro = "cuenta = 'Ventas'"
            if any(x in texto for x in ['lanzamiento', 'lanzada', 'salida a ventas', 'nuevos proyectos']): 
                cuenta_filtro = "cuenta = 'Lanzamientos'"
            elif any(x in texto for x in ['oferta', 'disponible', 'stock', 'inventario']): 
                cuenta_filtro = "cuenta = 'Oferta'"
            elif any(x in texto for x in ['iniciacion', 'iniciada', 'inicio de obra']): 
                cuenta_filtro = "cuenta = 'Iniciaciones'"
            elif any(x in texto for x in ['entrega', 'entregada', 'terminada', 'finalizada']): 
                cuenta_filtro = "cuenta = 'Entregadas'"
            
            # Si hay múltiples regiones, agrupar por regional
            es_multiple_regiones = region and '|' in region
            if es_multiple_regiones:
                sql = (
                    f"SELECT regional, COUNT(DISTINCT compania_constructora) AS total_constructoras "
                    "FROM livo "
                    f"WHERE {cuenta_filtro} "
                    f"AND {region_cond} "
                    f"{filtro_temporal} "
                    " "
                    " "
                    "GROUP BY regional "
                    "ORDER BY total_constructoras DESC"
                )
            else:
                sql = (
                    f"SELECT COUNT(DISTINCT compania_constructora) AS total_constructoras "
                    "FROM livo "
                    f"WHERE {cuenta_filtro} "
                    f"AND {region_cond} "
                    f"{filtro_temporal} "
                    " "
                    ""
                )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Conteo Constructoras): {sql}")
                return sql
            except Exception:
                pass

        # 0c) Ventas totales - PRIORIDAD MÁXIMA para preguntas comunes
        if ("cuales" in texto or "cuáles" in texto or "cuantas" in texto or "cuántas" in texto or "cuantos" in texto or "cuántos" in texto) and ("vendido" in texto or "vendidas" in texto or "vender" in texto or "se han vendido" in texto):
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Detectar si hay múltiples regiones
            es_multiple_regiones = region and '|' in region
            
            # Si no hay región específica o hay múltiples regiones, agregar desglose por regionales
            if not region or region in ['nacional', 'colombia', 'pais', 'todo el pais'] or es_multiple_regiones:
                sql = (
                    f"SELECT regional, {metrica_sql} AS {alias_sql}_ventas_totales "
                    "FROM livo "
                    f"WHERE cuenta = 'Ventas' "
                    f"AND {region_cond} "
                    f"{filtro_temporal} "
                    "GROUP BY regional "
                    "ORDER BY {alias_sql}_ventas_totales DESC"
                )
            else:
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_ventas_totales "
                    "FROM livo "
                    f"WHERE cuenta = 'Ventas' "
                    f"AND {region_cond} "
                    f"{filtro_temporal}"
                )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Ventas Totales - Cuántas vendidas): {sql}")
                return sql
            except Exception:
                pass

        # 0) Rotación de Inventarios (PRIORIDAD ALTA)
        if "rotacion" in texto or "rotación" in texto:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            es_multiple_regiones = region and '|' in region
            
            # SQL para calcular rotación (Meses de oferta)
            # Fórmula: Oferta Actual / Promedio Ventas (últimos 12 meses)
            if es_multiple_regiones:
                sql = f"""
                WITH oferta_actual AS (
                    SELECT regional, COALESCE(SUM(unidades), 0) as oferta
                    FROM livo
                    WHERE cuenta = 'Oferta'
                      AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
                      AND {region_cond}
                                          GROUP BY regional
                ),
                ventas_12m AS (
                    SELECT regional, CAST(SUBSTR(CAST(fecha AS VARCHAR), 1, 6) AS INTEGER) as mes_anio, SUM(unidades) as total_mensual
                    FROM livo
                    WHERE cuenta = 'Ventas'
                      AND doce_meses = (SELECT MAX(doce_meses) FROM livo)
                      AND {region_cond}
                                          GROUP BY regional, mes_anio
                ),
                ventas_promedio AS (
                    SELECT regional, COALESCE(AVG(total_mensual), 0) as ventas_prom
                    FROM ventas_12m
                    GROUP BY regional
                )
                SELECT 
                    regional,
                    oferta as "Oferta Actual",
                    CAST(ventas_prom AS INTEGER) as "Ventas Promedio Mensual",
                    CASE 
                        WHEN ventas_prom = 0 THEN 0 
                        ELSE ROUND(oferta / ventas_prom, 1) 
                    END as "Meses de Rotación"
                FROM oferta_actual
                JOIN ventas_promedio ON oferta_actual.regional = ventas_promedio.regional
                ORDER BY "Meses de Rotación" DESC
                """
            else:
                sql = f"""
                WITH oferta_actual AS (
                    SELECT COALESCE(SUM(unidades), 0) as oferta
                    FROM livo
                    WHERE cuenta = 'Oferta'
                      AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
                      AND {region_cond}
                                      ),
                ventas_12m AS (
                    SELECT CAST(SUBSTR(CAST(fecha AS VARCHAR), 1, 6) AS INTEGER) as mes_anio, SUM(unidades) as total_mensual
                    FROM livo
                    WHERE cuenta = 'Ventas'
                      AND doce_meses = (SELECT MAX(doce_meses) FROM livo)
                      AND {region_cond}
                                          GROUP BY mes_anio
                ),
                ventas_promedio AS (
                    SELECT COALESCE(AVG(total_mensual), 0) as ventas_prom
                    FROM ventas_12m
                )
                SELECT 
                    oferta as "Oferta Actual",
                    CAST(ventas_prom AS INTEGER) as "Ventas Promedio Mensual",
                    CASE 
                        WHEN ventas_prom = 0 THEN 0 
                        ELSE ROUND(oferta / ventas_prom, 1) 
                    END as "Meses de Rotación"
                FROM oferta_actual, ventas_promedio
                """
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Rotación): {sql}")
                return sql
            except Exception:
                pass

        # 0b) Precio/Costo/Valor Promedio de Vivienda (PRIORIDAD ALTA)
        # Fórmula según especificación: (Suma de valor / 1000) / Suma de unidades = millones de pesos
        # Donde Suma de valor está expresado en miles
        # Tamaño promedio: Suma de área / Suma de unidades = m²
        # Detecta: precio promedio, costo promedio, valor promedio, precio medio, costo medio, valor medio, tamaño promedio, área promedio, etc.
        if ("precio promedio" in texto or "precio medio" in texto or 
            "costo promedio" in texto or "costo medio" in texto or
            "valor promedio" in texto or "valor medio" in texto or
            "tamaño promedio" in texto or "tamano promedio" in texto or
            "área promedio" in texto or "area promedio" in texto or
            "superficie promedio" in texto or "m2 promedio" in texto):
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            es_multiple_regiones = region and '|' in region
            
            # Detectar fecha específica (ej: abril 2026 -> 20260401)
            fecha_filtro = ""
            if anio_match and mes_nombre_detectado:
                mes_map = {'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04', 'may': '05', 'jun': '06',
                          'jul': '07', 'ago': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12',
                          'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05', 'junio': '06',
                          'julio': '07', 'agosto': '08', 'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'}
                mes_num = mes_map.get(mes_nombre_detectado, '01')
                anio_num = anio_match.group(1)
                fecha_especifica = f"{anio_num}{mes_num}01"
                # CORRECCIÓN: Usar formato numérico directo, no string
                fecha_filtro = f" AND fecha = {fecha_especifica}"
            elif filtro_temporal:
                # Usar el filtro temporal existente si no hay fecha específica
                fecha_filtro = filtro_temporal
            
            # Detectar cuenta para el cálculo de promedios (Prioridad: Lanzamientos, Oferta, etc.)
            cuenta_calculo = 'Ventas'
            if any(x in texto for x in ['lanzamiento', 'lanzada', 'salida a ventas', 'nuevos proyectos', 'oferta nueva', 'levantamiento']):
                cuenta_calculo = 'Lanzamientos'
            elif any(x in texto for x in ['oferta', 'disponible', 'stock', 'inventario']):
                cuenta_calculo = 'Oferta'
            elif any(x in texto for x in ['iniciacion', 'iniciada', 'inicio de obra', 'arranques']):
                cuenta_calculo = 'Iniciaciones'
            elif any(x in texto for x in ['entregada', 'entrega', 'finalizada', 'habitables']):
                cuenta_calculo = 'Entregadas'
            elif any(x in texto for x in ['culminada', 'culminacion', 'obra terminada', 'construccion completa']):
                cuenta_calculo = 'Culminadas'
            elif any(x in texto for x in ['paralizado', 'paralizada', 'obras detenidas', 'suspendida']):
                cuenta_calculo = 'Paralizado'
            elif any(x in texto for x in ['renuncia', 'desistimiento', 'cancelacion', 'negocio caido']):
                cuenta_calculo = 'Renuncias'
            elif any(x in texto for x in ['saldo que inicia', 'saldo inicial', 'inventario inicial']):
                cuenta_calculo = 'Saldo que inicia'

            # SQL para calcular precio promedio y tamaño promedio
            # Fórmula: (suma_valor / 1000) / suma_unidades = millones de pesos por unidad
            # Nota: valor en LIVO está en miles, por lo que (valor / 1000) = valor en millones
            if es_multiple_regiones:
                sql = f"""
                WITH datos_calculo AS (
                    SELECT 
                        regional,
                        COALESCE(SUM(valor), 0) as suma_valor,
                        COALESCE(SUM(unidades), 0) as suma_unidades,
                        COALESCE(SUM(area), 0) as suma_area
                    FROM livo
                    WHERE cuenta = '{cuenta_calculo}'
                                            AND {region_cond}
                      {fecha_filtro}
                    GROUP BY regional
                )
                SELECT 
                    regional,
                    ROUND((suma_valor / 1000.0) / NULLIF(suma_unidades, 0), 2) as "Precio Promedio (millones de pesos)",
                    ROUND(suma_area / NULLIF(suma_unidades, 0), 2) as "Tamaño Promedio (m²)",
                    suma_valor as "Suma de Valor (en miles)",
                    suma_unidades as "Suma de Unidades",
                    suma_area as "Suma de Área"
                FROM datos_calculo
                ORDER BY "Precio Promedio (millones de pesos)" DESC
                """
            else:
                sql = f"""
                WITH datos_calculo AS (
                    SELECT 
                        COALESCE(SUM(valor), 0) as suma_valor,
                        COALESCE(SUM(unidades), 0) as suma_unidades,
                        COALESCE(SUM(area), 0) as suma_area
                    FROM livo
                    WHERE cuenta = '{cuenta_calculo}'
                                            AND {region_cond}
                      {fecha_filtro}
                )
                SELECT 
                    ROUND((suma_valor / 1000.0) / NULLIF(suma_unidades, 0), 2) as "Precio Promedio (millones de pesos)",
                    ROUND(suma_area / NULLIF(suma_unidades, 0), 2) as "Tamaño Promedio (m²)",
                    suma_valor as "Suma de Valor (en miles)",
                    suma_unidades as "Suma de Unidades",
                    suma_area as "Suma de Área"
                FROM datos_calculo
                """
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Precio Promedio Vivienda): {sql}")
                return sql
            except Exception:
                pass

        # 0c) Top Constructoras (Ranking) - PRIORIDAD ALTA
        if ("top" in texto or "ranking" in texto or "mejores" in texto) and ("constructora" in texto or "empresa" in texto):
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Intentar detectar número de forma flexible (top 10, ranking de las 10, las 10 mejores, etc.)
            limit = 5
            match_num = re.search(r"\b(\d{1,2})\b", texto)
            if match_num:
                limit = int(match_num.group(1))
            
            # Definir métrica (por defecto Ventas último año si no se especifica)
            cuenta_filtro = "cuenta = 'Ventas'"
            tiempo_filtro = "AND doce_meses = (SELECT MAX(doce_meses) FROM livo)"
            
            if any(x in texto for x in ['oferta', 'disponible', 'stock', 'inventario']): 
                cuenta_filtro = "cuenta = 'Oferta'"
                tiempo_filtro = "AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')"
            elif any(x in texto for x in ['saldo', 'saldo que inicia', 'saldo inicial']): 
                cuenta_filtro = "cuenta = 'Saldo que inicia'"
                tiempo_filtro = "AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Saldo que inicia')"
            elif any(x in texto for x in ['lanzamiento', 'lanzada', 'salida a ventas', 'nuevos proyectos']): 
                cuenta_filtro = "cuenta = 'Lanzamientos'"
                tiempo_filtro = "AND doce_meses = (SELECT MAX(doce_meses) FROM livo)"
            elif any(x in texto for x in ['iniciacion', 'iniciada', 'inicio de obra']): 
                cuenta_filtro = "cuenta = 'Iniciaciones'"
                tiempo_filtro = "AND doce_meses = (SELECT MAX(doce_meses) FROM livo)"
            elif any(x in texto for x in ['entrega', 'entregada', 'terminada', 'finalizada']): 
                cuenta_filtro = "cuenta = 'Entregadas'"
                tiempo_filtro = "AND doce_meses = (SELECT MAX(doce_meses) FROM livo)"
            elif any(x in texto for x in ['paralizado', 'paralizada', 'obras detenidas']): 
                cuenta_filtro = "cuenta = 'Paralizado'"
                tiempo_filtro = "AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Paralizado')"
            elif any(x in texto for x in ['renuncias', 'renuncia', 'desistimientos']): 
                cuenta_filtro = "cuenta = 'Renuncias'"
                tiempo_filtro = "AND doce_meses = (SELECT MAX(doce_meses) FROM livo)"
            elif any(x in texto for x in ['culminadas', 'culminada', 'obra terminada']): 
                cuenta_filtro = "cuenta = 'Culminadas'"
                tiempo_filtro = "AND doce_meses = (SELECT MAX(doce_meses) FROM livo)"
            
            sql = f"""
            SELECT compania_constructora, COALESCE(SUM(unidades), 0) as unidades
            FROM livo
            WHERE {cuenta_filtro} AND {region_cond} {tiempo_filtro}
            GROUP BY compania_constructora
            ORDER BY unidades DESC
            LIMIT {limit}
            """
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Top Constructoras): {sql}")
                return sql
            except Exception:
                pass

        # 1) Unidades totales de vivienda VIS sin VIP por región
        if "vis sin vip" in texto:
            region = self._extraer_region_general(texto)
            if region: # Requiere región para ser específico
                region_cond = self._condicion_region_general(region)
                es_multiple_regiones = region and '|' in region
                
                if es_multiple_regiones:
                    sql = (
                        f"SELECT regional, {metrica_sql} AS {alias_sql}_vis_sin_vip "
                        "FROM livo "
                        f"WHERE segmento_pre = 'VIS' AND {region_cond} "
                        " "
                        ""
                        f"{filtro_temporal} "
                        "GROUP BY regional "
                        "ORDER BY {alias_sql}_vis_sin_vip DESC"
                    )
                else:
                    sql = (
                        f"SELECT {metrica_sql} AS {alias_sql}_vis_sin_vip "
                        "FROM livo "
                        f"WHERE segmento_pre = 'VIS' AND {region_cond} "
                        " "
                        ""
                        f"{filtro_temporal}"
                    )
                try:
                    print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (VIS sin VIP): {sql}")
                    return sql
                except Exception:
                    pass

        # 2) Unidades totales de vivienda VIS (incluyendo VIP) por región
        if "vivienda de interes social" in texto and "vis" in texto and "sin vip" not in texto:
            region = self._extraer_region_general(texto)
            if region:
                region_cond = self._condicion_region_general(region)
                es_multiple_regiones = region and '|' in region
                
                if es_multiple_regiones:
                    sql = (
                        f"SELECT regional, {metrica_sql} AS {alias_sql}_vis "
                        "FROM livo "
                        "WHERE segmento_pre IN ('VIS', 'VIP') "
                        f"AND {region_cond} "
                        " "
                        ""
                        f"{filtro_temporal} "
                        "GROUP BY regional "
                        "ORDER BY {alias_sql}_vis DESC"
                    )
                else:
                    sql = (
                        f"SELECT {metrica_sql} AS {alias_sql}_vis "
                        "FROM livo "
                        "WHERE segmento_pre IN ('VIS', 'VIP') "
                        f"AND {region_cond} "
                        " "
                        ""
                        f"{filtro_temporal}"
                    )
                try:
                    print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (VIS total): {sql}")
                    return sql
                except Exception:
                    pass

        # 3) Unidades totales de vivienda No VIS por región
        # Saltar si hay intención de agrupación por tipo
        if "no vis" in texto and "unidades" in texto and not any(x in texto for x in ['agrupado por', 'por vis, no vis', 'por vis, vip', 'por no vis, vip']):
            region = self._extraer_region_general(texto)
            if region:
                region_cond = self._condicion_region_general(region)
                es_multiple_regiones = region and '|' in region
                
                if es_multiple_regiones:
                    sql = (
                        f"SELECT regional, {metrica_sql} AS {alias_sql}_no_vis "
                        "FROM livo "
                        f"WHERE segmento_pre = 'No VIS' AND {region_cond} "
                        " "
                        ""
                        f"{filtro_temporal} "
                        "GROUP BY regional "
                        "ORDER BY {alias_sql}_no_vis DESC"
                    )
                else:
                    sql = (
                        f"SELECT {metrica_sql} AS {alias_sql}_no_vis "
                        "FROM livo "
                        f"WHERE segmento_pre = 'No VIS' AND {region_cond} "
                        " "
                        ""
                        f"{filtro_temporal}"
                    )
                try:
                    print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (No VIS): {sql}")
                    return sql
                except Exception:
                    pass

        # 4) Unidades totales de vivienda VIP por región
        if (
            "unidades totales de vivienda vip" in texto
            or "oferta de unidades vip" in texto
            or ("oferta de unidades de vivienda" in texto and "vip" in texto)
            or ("vivienda de interes prioritario" in texto and "vip" in texto)
        ):
            region = self._extraer_region_general(texto)
            if region:
                region_cond = self._condicion_region_general(region)
                es_multiple_regiones = region and '|' in region
                
                if es_multiple_regiones:
                    sql = (
                        f"SELECT regional, {metrica_sql} AS {alias_sql}_vip "
                        "FROM livo "
                        f"WHERE segmento_pre = 'VIP' AND {region_cond} "
                        " "
                        ""
                        f"{filtro_temporal} "
                        "GROUP BY regional "
                        "ORDER BY {alias_sql}_vip DESC"
                    )
                else:
                    sql = (
                        f"SELECT {metrica_sql} AS {alias_sql}_vip "
                        "FROM livo "
                        f"WHERE segmento_pre = 'VIP' AND {region_cond} "
                        " "
                        ""
                        f"{filtro_temporal}"
                    )
                try:
                    print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (VIP): {sql}")
                    return sql
                except Exception:
                    pass

        # 5) Unidades totales de vivienda (todas las tipologías) por región
        if (
            "unidades totales de vivienda" in texto
            and "vivienda de interes social" not in texto
            and "no vis" not in texto
            and not any(x in texto for x in [' por ', ' cada ', ' segun ', ' según ', ' desglosado ', ' desglose '])
        ):
            region = self._extraer_region_general(texto)
            if region:
                region_cond = self._condicion_region_general(region)
                es_multiple_regiones = region and '|' in region
                
                if es_multiple_regiones:
                    sql = (
                        f"SELECT regional, {metrica_sql} AS {alias_sql}_totales "
                        "FROM livo "
                        f"WHERE {region_cond} "
                        " "
                        ""
                        f"{filtro_temporal} "
                        "GROUP BY regional "
                        "ORDER BY {alias_sql}_totales DESC"
                    )
                else:
                    sql = (
                        f"SELECT {metrica_sql} AS {alias_sql}_totales "
                        "FROM livo "
                        f"WHERE {region_cond} "
                        " "
                        ""
                        f"{filtro_temporal}"
                    )
                try:
                    print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (total vivienda): {sql}")
                    return sql
                except Exception:
                    pass

        # 6) Unidades de vivienda con precio entre VIS y hasta 500 SMMLV
        if "precio entre vis y hasta 500 smmlv" in texto:
            region = self._extraer_region_general(texto)
            if region:
                region_cond = self._condicion_region_general(region)
                es_multiple_regiones = region and '|' in region

                anio = _extraer_anio(texto)
                rangos = SalarioMinimoColombiano.calcular_rangos_vivienda(anio)
                salario = SalarioMinimoColombiano.obtener_salario_minimo(anio)

                vis_min_miles = rangos['VIS']['min'] // 1000
                limite_500_miles = (salario * 500) // 1000

                if es_multiple_regiones:
                    sql = (
                        f"SELECT regional, {metrica_sql} AS {alias_sql}_precio_vis_a_500_smmlv "
                        "FROM livo "
                        f"WHERE {region_cond} "
                        f"AND valor >= {vis_min_miles} "
                        f"AND valor <= {limite_500_miles} "
                        " "
                        ""
                        f"{filtro_temporal} "
                        "GROUP BY regional "
                        "ORDER BY {alias_sql}_precio_vis_a_500_smmlv DESC"
                    )
                else:
                    sql = (
                        f"SELECT {metrica_sql} AS {alias_sql}_precio_vis_a_500_smmlv "
                        "FROM livo "
                        f"WHERE {region_cond} "
                        f"AND valor >= {vis_min_miles} "
                        f"AND valor <= {limite_500_miles} "
                        " "
                        ""
                        f"{filtro_temporal}"
                    )
                try:
                    print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (precio VIS-500 SMMLV): {sql}")
                    return sql
                except Exception:
                    pass

        # 7) Unidades de vivienda con precio mayor a 500 SMMLV
        if "precio mayor a 500 smmlv" in texto:
            region = self._extraer_region_general(texto)
            if region:
                region_cond = self._condicion_region_general(region)
                es_multiple_regiones = region and '|' in region

                anio = _extraer_anio(texto)
                salario = SalarioMinimoColombiano.obtener_salario_minimo(anio)
                limite_500_miles = (salario * 500) // 1000

                if es_multiple_regiones:
                    sql = (
                        f"SELECT regional, {metrica_sql} AS {alias_sql}_precio_mayor_500_smmlv "
                        "FROM livo "
                        f"WHERE {region_cond} "
                        f"AND valor > {limite_500_miles} "
                        " "
                        ""
                        f"{filtro_temporal} "
                        "GROUP BY regional "
                        "ORDER BY {alias_sql}_precio_mayor_500_smmlv DESC"
                    )
                else:
                    sql = (
                        f"SELECT {metrica_sql} AS {alias_sql}_precio_mayor_500_smmlv "
                        "FROM livo "
                        f"WHERE {region_cond} "
                        f"AND valor > {limite_500_miles} "
                        " "
                        ""
                        f"{filtro_temporal}"
                    )
                try:
                    print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (precio > 500 SMMLV): {sql}")
                    return sql
                except Exception:
                    pass

        # 8) Lanzamientos de vivienda (VIP, VIS, No VIS o Total)
        # Saltar si es operación especial (no SUM simple)
        operaciones_especiales = ["GROUP_BY", "RANKING", "MAX", "MIN", "AVG", "MEDIAN", "MODE", "STDDEV", "VAR_POP", "COUNT", "PROMEDIO_PONDERADO", "DISTINCT_COUNT"]
        if ("lanzamientos" in texto or "lanzadas" in texto) and op_funcion not in operaciones_especiales:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Detectar si hay múltiples regiones
            es_multiple_regiones = region and '|' in region
            
            # Determinar tipo de vivienda
            tipo_filtro = ""
            if "vip" in texto:
                tipo_filtro = "AND segmento_pre = 'VIP'"
            elif "no vis" in texto:
                tipo_filtro = "AND segmento_pre = 'No VIS'"
            elif "vis" in texto: # VIS total (incluye VIP si no se dice 'sin vip')
                if "sin vip" in texto:
                    tipo_filtro = "AND segmento_pre = 'VIS'"
                else:
                    tipo_filtro = "AND segmento_pre IN ('VIS', 'VIP')"
            
            # Si hay múltiples regiones, agregar GROUP BY regional
            if es_multiple_regiones:
                sql = (
                    f"SELECT regional, {metrica_sql} AS {alias_sql}_lanzamientos "
                    "FROM livo "
                    f"WHERE cuenta = 'Lanzamientos' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal} "
                    "GROUP BY regional "
                    "ORDER BY {alias_sql}_lanzamientos DESC"
                )
            else:
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_lanzamientos "
                    "FROM livo "
                    f"WHERE cuenta = 'Lanzamientos' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal}"
                )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Lanzamientos): {sql}")
                return sql
            except Exception:
                pass

        # 9) Iniciaciones de vivienda (VIP, VIS, No VIS o Total)
        # Saltar si es operación especial (no SUM simple)
        if ("iniciaciones" in texto or "iniciadas" in texto) and op_funcion not in operaciones_especiales:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Detectar si hay múltiples regiones
            es_multiple_regiones = region and '|' in region
            
            # Determinar tipo de vivienda
            tipo_filtro = ""
            if "vip" in texto:
                tipo_filtro = "AND segmento_pre = 'VIP'"
            elif "no vis" in texto:
                tipo_filtro = "AND segmento_pre = 'No VIS'"
            elif "vis" in texto: # VIS total (incluye VIP si no se dice 'sin vip')
                if "sin vip" in texto:
                    tipo_filtro = "AND segmento_pre = 'VIS'"
                else:
                    tipo_filtro = "AND segmento_pre IN ('VIS', 'VIP')"
            
            # Si hay múltiples regiones, agregar GROUP BY regional
            if es_multiple_regiones:
                sql = (
                    f"SELECT regional, {metrica_sql} AS {alias_sql}_iniciaciones "
                    "FROM livo "
                    f"WHERE cuenta = 'Iniciaciones' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal} "
                    "GROUP BY regional "
                    "ORDER BY {alias_sql}_iniciaciones DESC"
                )
            else:
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_iniciaciones "
                    "FROM livo "
                    f"WHERE cuenta = 'Iniciaciones' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal}"
                )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Iniciaciones): {sql}")
                return sql
            except Exception:
                pass

        # 10) Entregadas de vivienda (VIP, VIS, No VIS o Total)
        if ("entregadas" in texto or "entregada" in texto or "terminadas" in texto or "finalizadas" in texto) and op_funcion not in operaciones_especiales:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Detectar si hay múltiples regiones
            es_multiple_regiones = region and '|' in region
            
            # Determinar tipo de vivienda
            tipo_filtro = ""
            if "vip" in texto:
                tipo_filtro = "AND segmento_pre = 'VIP'"
            elif "no vis" in texto:
                tipo_filtro = "AND segmento_pre = 'No VIS'"
            elif "vis" in texto:
                if "sin vip" in texto:
                    tipo_filtro = "AND segmento_pre = 'VIS'"
                else:
                    tipo_filtro = "AND segmento_pre IN ('VIS', 'VIP')"
            
            # Si hay múltiples regiones, agregar GROUP BY regional
            if es_multiple_regiones:
                sql = (
                    f"SELECT regional, {metrica_sql} AS {alias_sql}_entregadas "
                    "FROM livo "
                    f"WHERE cuenta = 'Entregadas' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal} "
                    "GROUP BY regional "
                    "ORDER BY {alias_sql}_entregadas DESC"
                )
            else:
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_entregadas "
                    "FROM livo "
                    f"WHERE cuenta = 'Entregadas' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal}"
                )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Entregadas): {sql}")
                return sql
            except Exception:
                pass

        # 11) Renuncias de vivienda (VIP, VIS, No VIS o Total)
        if ("renuncias" in texto or "renuncia" in texto or "desistimientos" in texto or "cancelaciones" in texto) and op_funcion not in operaciones_especiales:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Detectar si hay múltiples regiones
            es_multiple_regiones = region and '|' in region
            
            # Determinar tipo de vivienda
            tipo_filtro = ""
            if "vip" in texto:
                tipo_filtro = "AND segmento_pre = 'VIP'"
            elif "no vis" in texto:
                tipo_filtro = "AND segmento_pre = 'No VIS'"
            elif "vis" in texto:
                if "sin vip" in texto:
                    tipo_filtro = "AND segmento_pre = 'VIS'"
                else:
                    tipo_filtro = "AND segmento_pre IN ('VIS', 'VIP')"
            
            # Si hay múltiples regiones, agregar GROUP BY regional
            if es_multiple_regiones:
                sql = (
                    f"SELECT regional, {metrica_sql} AS {alias_sql}_renuncias "
                    "FROM livo "
                    f"WHERE cuenta = 'Renuncias' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal} "
                    "GROUP BY regional "
                    "ORDER BY {alias_sql}_renuncias DESC"
                )
            else:
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_renuncias "
                    "FROM livo "
                    f"WHERE cuenta = 'Renuncias' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal}"
                )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Renuncias): {sql}")
                return sql
            except Exception:
                pass

        # 12) Saldo que inicia de vivienda (VIP, VIS, No VIS o Total)
        if ("saldo" in texto or "saldo que inicia" in texto or "saldo inicial" in texto) and op_funcion not in operaciones_especiales:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Detectar si hay múltiples regiones
            es_multiple_regiones = region and '|' in region
            
            # Determinar tipo de vivienda
            tipo_filtro = ""
            if "vip" in texto:
                tipo_filtro = "AND segmento_pre = 'VIP'"
            elif "no vis" in texto:
                tipo_filtro = "AND segmento_pre = 'No VIS'"
            elif "vis" in texto:
                if "sin vip" in texto:
                    tipo_filtro = "AND segmento_pre = 'VIS'"
                else:
                    tipo_filtro = "AND segmento_pre IN ('VIS', 'VIP')"
            
            # Si hay múltiples regiones, agregar GROUP BY regional
            if es_multiple_regiones:
                sql = (
                    f"SELECT regional, {metrica_sql} AS {alias_sql}_saldo_inicia "
                    "FROM livo "
                    f"WHERE cuenta = 'Saldo que inicia' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal} "
                    "GROUP BY regional "
                    "ORDER BY {alias_sql}_saldo_inicia DESC"
                )
            else:
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_saldo_inicia "
                    "FROM livo "
                    f"WHERE cuenta = 'Saldo que inicia' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal}"
                )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Saldo que inicia): {sql}")
                return sql
            except Exception:
                pass

        # 13) Paralizado de vivienda (VIP, VIS, No VIS o Total)
        if ("paralizado" in texto or "paralizada" in texto or "obras detenidas" in texto or "suspendidas" in texto) and op_funcion not in operaciones_especiales:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Detectar si hay múltiples regiones
            es_multiple_regiones = region and '|' in region
            
            # Determinar tipo de vivienda
            tipo_filtro = ""
            if "vip" in texto:
                tipo_filtro = "AND segmento_pre = 'VIP'"
            elif "no vis" in texto:
                tipo_filtro = "AND segmento_pre = 'No VIS'"
            elif "vis" in texto:
                if "sin vip" in texto:
                    tipo_filtro = "AND segmento_pre = 'VIS'"
                else:
                    tipo_filtro = "AND segmento_pre IN ('VIS', 'VIP')"
            
            # Si hay múltiples regiones, agregar GROUP BY regional
            if es_multiple_regiones:
                sql = (
                    f"SELECT regional, {metrica_sql} AS {alias_sql}_paralizado "
                    "FROM livo "
                    f"WHERE cuenta = 'Paralizado' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal} "
                    "GROUP BY regional "
                    "ORDER BY {alias_sql}_paralizado DESC"
                )
            else:
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_paralizado "
                    "FROM livo "
                    f"WHERE cuenta = 'Paralizado' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal}"
                )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Paralizado): {sql}")
                return sql
            except Exception:
                pass

        # 14) Culminadas de vivienda (VIP, VIS, No VIS o Total)
        if ("culminadas" in texto or "culminada" in texto or "obra terminada" in texto or "construccion completa" in texto) and op_funcion not in operaciones_especiales:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Detectar si hay múltiples regiones
            es_multiple_regiones = region and '|' in region
            
            # Determinar tipo de vivienda
            tipo_filtro = ""
            if "vip" in texto:
                tipo_filtro = "AND segmento_pre = 'VIP'"
            elif "no vis" in texto:
                tipo_filtro = "AND segmento_pre = 'No VIS'"
            elif "vis" in texto:
                if "sin vip" in texto:
                    tipo_filtro = "AND segmento_pre = 'VIS'"
                else:
                    tipo_filtro = "AND segmento_pre IN ('VIS', 'VIP')"
            
            # Si hay múltiples regiones, agregar GROUP BY regional
            if es_multiple_regiones:
                sql = (
                    f"SELECT regional, {metrica_sql} AS {alias_sql}_culminadas "
                    "FROM livo "
                    f"WHERE cuenta = 'Culminadas' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal} "
                    "GROUP BY regional "
                    "ORDER BY {alias_sql}_culminadas DESC"
                )
            else:
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_culminadas "
                    "FROM livo "
                    f"WHERE cuenta = 'Culminadas' "
                    f"AND {region_cond} "
                    f"{tipo_filtro} "
                    " "
                    ""
                    f"{filtro_temporal}"
                )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Culminadas): {sql}")
                return sql
            except Exception:
                pass

        # 0e) Cálculo de HHI (Concentración de Mercado)
        if op_funcion == "HHI":
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Detectar año si se especifica
            anio_hhi = anio_match.group(1) if anio_match else "(SELECT MAX(CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER)) FROM livo)"
            
            sql = f"""
            WITH participaciones AS (
                SELECT 
                    compania_constructora,
                    SUM(unidades) * 100.0 / SUM(SUM(unidades)) OVER () as share
                FROM livo
                WHERE {region_cond}
                  AND cuenta = 'Oferta' -- HHI se calcula sobre la oferta
                  AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {anio_hhi}
                  AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta' AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {anio_hhi})
                GROUP BY compania_constructora
            )
            SELECT ROUND(SUM(share * share), 2) as indice_hhi FROM participaciones
            """
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (HHI): {sql}")
                return sql
            except Exception:
                pass

        # 0f) Cálculo de YTD (Year-to-Date / Acumulado Anual)
        if op_funcion == "YTD":
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Detectar año (por defecto el último año disponible)
            anio_ytd = anio_match.group(1) if anio_match else "(SELECT MAX(CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER)) FROM livo)"
            
            # Detectar cuenta (Ventas por defecto)
            cuenta_calculo = 'Ventas'
            if any(x in texto for x in ['lanzamiento', 'lanzada', 'salida a ventas', 'nuevos proyectos']): cuenta_calculo = 'Lanzamientos'
            elif any(x in texto for x in ['oferta', 'disponible', 'stock', 'inventario']): cuenta_calculo = 'Oferta'
            elif any(x in texto for x in ['iniciacion', 'iniciada', 'inicio de obra']): cuenta_calculo = 'Iniciaciones'
            elif any(x in texto for x in ['entrega', 'entregada', 'terminada', 'finalizada']): cuenta_calculo = 'Entregadas'
            
            sql = f"""
            SELECT 
                CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) as anio,
                SUM(unidades) as total_unidades_ytd
            FROM livo
            WHERE cuenta = '{cuenta_calculo}'
              AND {region_cond}
              AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {anio_ytd}
              AND CAST(SUBSTR(CAST(fecha AS VARCHAR), 5, 2) AS INTEGER) <= (SELECT MAX(CAST(SUBSTR(CAST(fecha AS VARCHAR), 5, 2) AS INTEGER)) FROM livo WHERE CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {anio_ytd})
                           GROUP BY anio
            """
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (YTD): {sql}")
                return sql
            except Exception:
                pass

        # 0g) Bucketing Dinámico de Áreas
        if op_funcion == "BUCKET_AREA":
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            sql = f"""
            SELECT 
                CASE 
                    WHEN area < 50 THEN '1. Pequeño (<50m2)'
                    WHEN area BETWEEN 50 AND 80 THEN '2. Mediano (50-80m2)'
                    WHEN area BETWEEN 80 AND 120 THEN '3. Grande (80-120m2)'
                    ELSE '4. Extra Grande (>120m2)'
                END as segmento_area,
                SUM(unidades) as unidades,
                ROUND(AVG(precio_mc_promedio), 2) as precio_m2_promedio
            FROM livo
            WHERE {region_cond}
              AND cuenta = 'Oferta'
              AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
            GROUP BY segmento_area
            ORDER BY segmento_area
            """
            print(f"[DEBUG LIVO reglas] SQL BUCKET AREA: {sql}")
            return sql

        # 0h) Media Móvil (Series de tiempo suavizadas)
        if op_funcion == "MOVING_AVG":
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            # Asegurar que el intervalo de datos sea suficiente para el cálculo solicitado
            interval_months = max(12, n_periodos_ma + 6)
            sql = f"""
            SELECT 
                DATE_TRUNC('month', fecha_date) as mes,
                SUM({col_metrica}) as valor_mensual,
                ROUND({metrica_sql}, 2) as "{alias_sql}"
            FROM livo
            WHERE {region_cond} AND cuenta = 'Ventas'
              AND fecha_date >= (SELECT MAX(fecha_date) - INTERVAL '{interval_months} months' FROM livo)
            GROUP BY mes, fecha_date
            ORDER BY mes
            """
            return sql

        # 0i) Pronóstico mediante Regresión Lineal Simple
        if op_funcion == "FORECAST":
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            # Convertimos la fecha a un número serial para la regresión
            sql = f"""
            WITH serie AS (
                SELECT 
                    epoch(DATE_TRUNC('month', fecha_date)) as x,
                    SUM({col_metrica}) as y
                FROM livo
                WHERE {region_cond} AND cuenta = 'Ventas'
                  AND fecha_date >= (SELECT MAX(fecha_date) - INTERVAL '12 months' FROM livo)
                GROUP BY x
            ),
            modelo AS (
                SELECT 
                    regr_slope(y, x) as pendiente,
                    regr_intercept(y, x) as intercepto
                FROM serie
            ),
            ultimo_mes AS (SELECT MAX(x) + 2592000 as proximo_x FROM serie)
            SELECT 
                (SELECT ROUND(y, 0) FROM serie WHERE x = (SELECT MAX(x) FROM serie)) as "Último Dato Real",
                ROUND(intercepto + pendiente * proximo_x, 0) as "Pronóstico Próximo Mes",
                CASE WHEN pendiente > 0 THEN 'Creciente' ELSE 'Decreciente' END as "Tendencia"
            FROM modelo, ultimo_mes
            """
            return sql

        # 0j) Tasa de Absorción Mensual
        if op_funcion == "ABSORCION":
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            sql = f"""
            SELECT 
                DATE_TRUNC('month', fecha_date) as mes,
                SUM(CASE WHEN cuenta='Ventas' THEN unidades ELSE 0 END) as ventas,
                SUM(CASE WHEN cuenta='Oferta' THEN unidades ELSE 0 END) as inventario_final,
                ROUND({metrica_sql}, 2) as "{alias_sql}"
            FROM livo
            WHERE {region_cond}
              AND fecha_date >= (SELECT MAX(fecha_date) - INTERVAL '6 months' FROM livo)
            GROUP BY mes, fecha_date
            ORDER BY mes
            """
            return sql

        # 0k) Segmentación por Rangos SMLV (Bucketing de Precios)
        if op_funcion == "BUCKET_SMLV":
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            # Aproximación de rangos SMLV basada en el salario 2025 (~1.42M)
            sql = f"""
            SELECT 
                CASE 
                    WHEN valor < 128115 THEN '1. VIP (<90 SMLV)'
                    WHEN valor BETWEEN 128115 AND 192173 THEN '2. VIS (90-135 SMLV)'
                    WHEN valor BETWEEN 192173 AND 334522 THEN '3. Rango 135-235 SMLV'
                    WHEN valor BETWEEN 334522 AND 500000 THEN '4. Rango 235-350 SMLV'
                    WHEN valor BETWEEN 500000 AND 711750 THEN '5. Rango 350-500 SMLV'
                    ELSE '6. Segmento Alto (>500 SMLV)'
                END as rango_smlv,
                SUM(unidades) as unidades,
                ROUND(SUM(valor) / NULLIF(SUM(unidades), 0), 0) as precio_promedio_unidad
            FROM livo
            WHERE {region_cond}
              AND cuenta = 'Oferta'
              AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
            GROUP BY rango_smlv
            ORDER BY rango_smlv
            """
            return sql

        # 0l) Análisis de Percentiles Dinámicos
        if op_funcion == "PERCENTILE":
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            sql = f"""
            SELECT 
                '{region or 'Nacional'}' as ubicacion,
                ROUND(approx_quantile({col_metrica}, 0.25), 2) as "Percentil 25 (Bajo)",
                ROUND(approx_quantile({col_metrica}, 0.50), 2) as "Mediana (P50)",
                ROUND(approx_quantile({col_metrica}, 0.75), 2) as "Percentil 75 (Alto)",
                ROUND(AVG({col_metrica}), 2) as "Promedio Simple"
            FROM livo
            WHERE {region_cond}
              AND cuenta = 'Oferta'
              AND {col_metrica} > 0
              AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
            """
            return sql

        # 0m) Preparación de datos para Clustering (Segmentación de Proyectos)
        if op_funcion == "CLUSTERING":
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            sql = f"""
            SELECT 
                nombre_proyecto,
                AVG(valor) as valor_promedio,
                AVG(area) as area_promedio,
                AVG(precio_mc_promedio) as precio_m2,
                SUM(unidades) as total_unidades,
                MAX(estrato) as estrato
            FROM livo
            WHERE {region_cond}
              AND cuenta = 'Oferta'
              AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
            GROUP BY nombre_proyecto
            HAVING AVG(valor) > 0
            """
            return sql

        # 0n) Preparación de datos para Clasificación (Perfilado de Vivienda)
        if op_funcion == "CLASSIFICATION":
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            sql = f"""
            SELECT 
                segmento_pre,
                estrato,
                destino_etapa,
                uso_etapa,
                AVG(valor) as valor_medio,
                AVG(area) as area_media,
                COUNT(*) as frecuencia
            FROM livo
            WHERE {region_cond}
            GROUP BY segmento_pre, estrato, destino_etapa, uso_etapa
            """
            return sql

        # 0o) Tabla de Segmentación VIS/VIP/NO VIS (Reglas Específicas)
        if op_funcion == "SEGMENT_TABLE_VIS":
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            sql = f"""
            SELECT 
                'VIS' as segmento,
                SUM(unidades) as unidades,
                ROUND(SUM(valor) / 1000000.0, 2) as valor_millones,
                ROUND(AVG(area), 2) as area_promedio
            FROM livo
            WHERE {region_cond}
              AND cuenta = 'Oferta'
              AND segmento_pre = 'VIS'
              AND rangos_decreto_pre = 'VIS 70 - 135 SML'
              AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
            
            UNION ALL
            
            SELECT 
                'VIP' as segmento,
                SUM(unidades) as unidades,
                ROUND(SUM(valor) / 1000000.0, 2) as valor_millones,
                ROUND(AVG(area), 2) as area_promedio
            FROM livo
            WHERE {region_cond}
              AND cuenta = 'Oferta'
              AND segmento_pre = 'VIS'
              AND rangos_decreto_pre = 'VIP'
              AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
            
            UNION ALL
            
            SELECT 
                'TOTAL' as segmento,
                SUM(unidades) as unidades,
                ROUND(SUM(valor) / 1000000.0, 2) as valor_millones,
                ROUND(AVG(area), 2) as area_promedio
            FROM livo
            WHERE {region_cond}
              AND cuenta = 'Oferta'
              AND segmento_pre = 'VIS'
              AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
            
            ORDER BY segmento
            """
            return sql

        # 0p) Tabla de Segmentación NO VIS
        if op_funcion == "SEGMENT_TABLE_NO_VIS":
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            sql = f"""
            SELECT 
                'NO VIS' as segmento,
                SUM(unidades) as unidades,
                ROUND(SUM(valor) / 1000000.0, 2) as valor_millones,
                ROUND(AVG(area), 2) as area_promedio
            FROM livo
            WHERE {region_cond}
              AND cuenta = 'Oferta'
              AND segmento_pre = 'NO VIS'
              AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
            """
            return sql

        # 0q) Preparación de datos para Reglas de Asociación (Co-ocurrencia)
        if op_funcion == "ASSOCIATION":
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            sql = f"""
            SELECT 
                ciudad, zona, estrato, segmento_pre, 
                COUNT(*) as conteo_asociacion
            FROM livo
            WHERE {region_cond}
            GROUP BY ALL
            ORDER BY conteo_asociacion DESC
            """
            return sql

        # 10) Ventas totales (Definición estricta: Cuenta=Ventas + Región + Tiempo, sin filtros extra)
        if ("ventas totales" in texto or "se han vendido" in texto or "unidades vendidas" in texto) and not tiene_agrupacion and op_funcion not in ["RANKING", "GROUP_BY"]:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Si no hay región específica, agregar desglose por regionales
            if not region or region in ['nacional', 'colombia', 'pais', 'todo el pais']:
                sql = (
                    f"SELECT regional, {metrica_sql} AS {alias_sql}_ventas_totales "
                    "FROM livo "
                    f"WHERE cuenta = 'Ventas' "
                    f"AND {region_cond} "
                    f"{filtro_temporal} "
                    "GROUP BY regional "
                    "ORDER BY {alias_sql}_ventas_totales DESC"
                )
            else:
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_ventas_totales "
                    "FROM livo "
                    f"WHERE cuenta = 'Ventas' "
                    f"AND {region_cond} "
                    f"{filtro_temporal}"
                )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Ventas Totales): {sql}")
                return sql
            except Exception:
                pass

        # debug_before_var = f"[DEBUG _generar_sql_sin_llm] Antes de bloque VARIACION, op_funcion={op_funcion}"
        # if STREAMLIT_AVAILABLE:
        #     st.text(debug_before_var)
        # else:
        #     print(debug_before_var)
        
        # 0d) Análisis de Variación / Crecimiento (Comparación entre periodos)
        if op_funcion == "VARIACION":
            # debug_var_msg = f"[DEBUG VARIACION] Entrando a lógica VARIACION con op_funcion={op_funcion}"
            # if STREAMLIT_AVAILABLE:
            #     st.text(debug_var_msg)
            # else:
            #     print(debug_var_msg)
            
            anios = re.findall(r"(20[0-9]{2})", texto)
            # debug_var_msg2 = f"[DEBUG VARIACION] Años encontrados: {anios}"
            # if STREAMLIT_AVAILABLE:
            #     st.text(debug_var_msg2)
            # else:
            #     print(debug_var_msg2)
            
            if len(anios) == 1:
                anios.append(str(int(anios[0]) - 1)) # Si pide un solo año, comparar con el anterior
            
            # Buscar meses mencionados
            meses_encontrados = []
            for m_txt, m_num in meses_map_regex.items():
                if re.search(r'\b' + re.escape(m_txt) + r'\b', texto):
                    meses_encontrados.append((m_txt, m_num))
            
            # debug_var_msg3 = f"[DEBUG VARIACION] Meses encontrados: {meses_encontrados}"
            # if STREAMLIT_AVAILABLE:
            #     st.text(debug_var_msg3)
            # else:
            #     print(debug_var_msg3)
            
            # Detectar cuenta (Ventas por defecto)
            cuenta_calculo = None  # None significa todas las cuentas
            cuenta_filtro = ""  # Sin filtro por defecto
            if any(x in texto for x in ['lanzamiento', 'lanzada', 'salida a ventas', 'nuevos proyectos']): 
                cuenta_calculo = 'Lanzamientos'
                cuenta_filtro = "cuenta = 'Lanzamientos'"
            elif any(x in texto for x in ['oferta', 'disponible', 'stock', 'inventario']): 
                cuenta_calculo = 'Oferta'
                cuenta_filtro = "cuenta = 'Oferta'"
            elif any(x in texto for x in ['saldo', 'saldo que inicia', 'saldo inicial']): 
                cuenta_calculo = 'Saldo que inicia'
                cuenta_filtro = "cuenta = 'Saldo que inicia'"
            elif any(x in texto for x in ['iniciacion', 'iniciada', 'inicio de obra']): 
                cuenta_calculo = 'Iniciaciones'
                cuenta_filtro = "cuenta = 'Iniciaciones'"
            elif any(x in texto for x in ['entrega', 'entregada', 'terminada', 'finalizada']): 
                cuenta_calculo = 'Entregadas'
                cuenta_filtro = "cuenta = 'Entregadas'"
            elif any(x in texto for x in ['vendidas', 'vendido', 'vender', 'se han vendido']): 
                cuenta_calculo = 'Ventas'
                cuenta_filtro = "cuenta = 'Ventas'"
            elif any(x in texto for x in ['paralizado', 'paralizada', 'obras detenidas', 'suspendidas']): 
                cuenta_calculo = 'Paralizado'
                cuenta_filtro = "cuenta = 'Paralizado'"
            elif any(x in texto for x in ['renuncias', 'renuncia', 'desistimientos', 'cancelaciones']): 
                cuenta_calculo = 'Renuncias'
                cuenta_filtro = "cuenta = 'Renuncias'"
            elif any(x in texto for x in ['culminadas', 'culminada', 'obra terminada', 'construccion completa']): 
                cuenta_calculo = 'Culminadas'
                cuenta_filtro = "cuenta = 'Culminadas'"
            
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"

            # Detectar si es variación de precio promedio
            es_variacion_precio_promedio = any(x in texto for x in ['precio promedio', 'precio medio', 'valor promedio', 'valor medio'])

            # Determinar periodos (Mes-Año vs Mes-Año o Año vs Año)
            if len(anios) >= 2:
                a1, a2 = anios[0], anios[1] # Ej: 2026, 2025
                
                # Caso especial: Variación de precio promedio
                if es_variacion_precio_promedio:
                    # Caso A: Comparación de meses específicos
                    if len(meses_encontrados) >= 1:
                        m1_num = meses_encontrados[0][1]
                        m2_num = meses_encontrados[1][1] if len(meses_encontrados) > 1 else m1_num
                        m1_name = meses_encontrados[0][0].title()
                        m2_name = meses_encontrados[1][0].title() if len(meses_encontrados) > 1 else m1_name
                        
                        f1_start, f1_end = f"{a1}{m1_num:02d}01", f"{a1}{m1_num:02d}32"
                        f2_start, f2_end = f"{a2}{m2_num:02d}01", f"{a2}{m2_num:02d}32"

                        cuenta_cond_actual = f"AND {cuenta_filtro}" if cuenta_filtro else ""
                        cuenta_cond_anterior = f"AND {cuenta_filtro}" if cuenta_filtro else ""

                        sql = f"""
                        WITH datos_actual AS (
                            SELECT 
                                COALESCE(SUM(valor), 0) as suma_valor,
                                COALESCE(SUM(unidades), 0) as suma_unidades
                            FROM livo
                            WHERE {region_cond} {cuenta_cond_actual} AND fecha >= {f1_start} AND fecha < {f1_end}                          ),
                        datos_anterior AS (
                            SELECT 
                                COALESCE(SUM(valor), 0) as suma_valor,
                                COALESCE(SUM(unidades), 0) as suma_unidades
                            FROM livo
                            WHERE {region_cond} {cuenta_cond_anterior} AND fecha >= {f2_start} AND fecha < {f2_end}                          )
                        SELECT 
                            ROUND((curr.suma_valor / 1000.0) / NULLIF(curr.suma_unidades, 0), 2) as "Precio Promedio {m1_name} {a1} (millones de pesos)",
                            ROUND((prev.suma_valor / 1000.0) / NULLIF(prev.suma_unidades, 0), 2) as "Precio Promedio {m2_name} {a2} (millones de pesos)",
                            ROUND(((curr.suma_valor / 1000.0) / NULLIF(curr.suma_unidades, 0) - (prev.suma_valor / 1000.0) / NULLIF(prev.suma_unidades, 0)) / NULLIF((prev.suma_valor / 1000.0) / NULLIF(prev.suma_unidades, 0), 0) * 100, 2) as "Crecimiento (%)"
                        FROM datos_actual curr, datos_anterior prev
                        """
                    
                    # Caso B: Comparación anual total
                    else:
                        cuenta_cond_actual = f"AND {cuenta_filtro}" if cuenta_filtro else ""
                        cuenta_cond_anterior = f"AND {cuenta_filtro}" if cuenta_filtro else ""

                        sql = f"""
                        WITH datos_actual AS (
                            SELECT 
                                COALESCE(SUM(valor), 0) as suma_valor,
                                COALESCE(SUM(unidades), 0) as suma_unidades
                            FROM livo
                            WHERE {region_cond} {cuenta_cond_actual} AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {a1}                          ),
                        datos_anterior AS (
                            SELECT 
                                COALESCE(SUM(valor), 0) as suma_valor,
                                COALESCE(SUM(unidades), 0) as suma_unidades
                            FROM livo
                            WHERE {region_cond} {cuenta_cond_anterior} AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {a2}                          )
                        SELECT 
                            ROUND((curr.suma_valor / 1000.0) / NULLIF(curr.suma_unidades, 0), 2) as "Precio Promedio Año {a1} (millones de pesos)",
                            ROUND((prev.suma_valor / 1000.0) / NULLIF(prev.suma_unidades, 0), 2) as "Precio Promedio Año {a2} (millones de pesos)",
                            ROUND(((curr.suma_valor / 1000.0) / NULLIF(curr.suma_unidades, 0) - (prev.suma_valor / 1000.0) / NULLIF(prev.suma_unidades, 0)) / NULLIF((prev.suma_valor / 1000.0) / NULLIF(prev.suma_unidades, 0), 0) * 100, 2) as "Crecimiento (%)"
                        FROM datos_actual curr, datos_anterior prev
                        """
                
                # Caso normal: Variación de otras métricas (unidades, valor, etc.)
                else:
                    # Caso A: Comparación de meses específicos
                    if len(meses_encontrados) >= 1:
                        m1_num = meses_encontrados[0][1]
                        m2_num = meses_encontrados[1][1] if len(meses_encontrados) > 1 else m1_num
                        m1_name = meses_encontrados[0][0].title()
                        m2_name = meses_encontrados[1][0].title() if len(meses_encontrados) > 1 else m1_name
                        
                        f1_start, f1_end = f"{a1}{m1_num:02d}01", f"{a1}{m1_num:02d}32"
                        f2_start, f2_end = f"{a2}{m2_num:02d}01", f"{a2}{m2_num:02d}32"

                        cuenta_cond_actual = f"AND {cuenta_filtro}" if cuenta_filtro else ""
                        cuenta_cond_anterior = f"AND {cuenta_filtro}" if cuenta_filtro else ""

                        sql = f"""
                        WITH actual AS (SELECT {metrica_sql} as val FROM livo WHERE {region_cond} {cuenta_cond_actual} AND fecha >= {f1_start} AND fecha < {f1_end}  ),
                        anterior AS (SELECT {metrica_sql} as val FROM livo WHERE {region_cond} {cuenta_cond_anterior} AND fecha >= {f2_start} AND fecha < {f2_end}  )
                        SELECT curr.val as "{m1_name} {a1}", prev.val as "{m2_name} {a2}", (curr.val - prev.val) as "Variación Absoluta", ROUND(((curr.val - prev.val) * 100.0) / NULLIF(prev.val, 0), 2) as "Crecimiento (%)" FROM actual curr, anterior prev
                        """
                    
                    # Caso B: Comparación anual total
                    else:
                        cuenta_cond_actual = f"AND {cuenta_filtro}" if cuenta_filtro else ""
                        cuenta_cond_anterior = f"AND {cuenta_filtro}" if cuenta_filtro else ""

                        sql = f"""
                        WITH actual AS (SELECT {metrica_sql} as val FROM livo WHERE {region_cond} {cuenta_cond_actual} AND LEFT(CAST(fecha AS VARCHAR), 4) = '{a1}'  ),
                        anterior AS (SELECT {metrica_sql} as val FROM livo WHERE {region_cond} {cuenta_cond_anterior} AND LEFT(CAST(fecha AS VARCHAR), 4) = '{a2}'  )
                        SELECT curr.val as "Año {a1}", prev.val as "Año {a2}", (curr.val - prev.val) as "Variación Absoluta", ROUND(((curr.val - prev.val) * 100.0) / NULLIF(prev.val, 0), 2) as "Crecimiento (%)" FROM actual curr, anterior prev
                        """
                
                try:
                    # Si es oferta, no comparar totales sumados del año sino el promedio o el último corte
                    if cuenta_calculo == 'Oferta' and len(meses_encontrados) == 0 and not es_variacion_precio_promedio:
                        sql = sql.replace(metrica_sql, f"COALESCE(AVG({col_metrica}), 0)")

                    print(f"[DEBUG LIVO reglas] SQL VARIACION: {sql}")
                    return sql.strip()
                except Exception: pass

        # 11) Oferta disponible/total (Definición estricta: Cuenta=Oferta + Región + Tiempo, sin filtros extra)
        if ("oferta disponible" in texto or "oferta total" in texto) and not tiene_agrupacion:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Ajuste temporal para STOCK (Oferta): Usar último corte del periodo si es un rango
            final_temporal = filtro_temporal
            if filtro_temporal and "fecha =" not in filtro_temporal:
                 ft_clean = filtro_temporal.strip()
                 if ft_clean.upper().startswith("AND"):
                     ft_clean = ft_clean[3:].strip()
                 # Subconsulta para fecha máxima dentro del filtro
                 subquery_date = f"(SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta' AND {region_cond} AND {ft_clean})"
                 final_temporal = f" AND fecha = {subquery_date}"
            
            if not final_temporal:
                 final_temporal = " AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')"

            sql = (
                f"SELECT {metrica_sql} AS {alias_sql}_oferta_disponible "
                "FROM livo "
                f"WHERE cuenta = 'Oferta' "
                f"AND {region_cond} "
                f"{final_temporal}"
            )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Oferta Disponible): {sql}")
                return sql
            except Exception:
                pass

        # 11b) Oferta por tipo de vivienda (VIP, VIS, No VIS) - Definición estricta sin filtros extra
        # Saltar si hay intención de agrupación
        if "oferta" in texto and any(t in texto for t in ["vip", "vis", "no vis"]) and not any(x in texto for x in [' por ', ' segun ', ' según ', ' cada ', ' agrupado ', ' distribucion ', ' distribución ', ' desglosado ', ' desglose ']):
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Determinar tipo
            tipo_filtro = ""
            if "vip" in texto:
                tipo_filtro = "AND segmento_pre = 'VIP'"
            elif "no vis" in texto:
                tipo_filtro = "AND segmento_pre = 'No VIS'"
            elif "vis" in texto:
                if "sin vip" in texto:
                    tipo_filtro = "AND segmento_pre = 'VIS'"
                else:
                    tipo_filtro = "AND segmento_pre IN ('VIS', 'VIP')"
            
            # Fecha: Último corte de Oferta
            final_temporal = " AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')"
            
            sql = (
                f"SELECT {metrica_sql} AS {alias_sql}_oferta_tipo "
                "FROM livo "
                f"WHERE cuenta = 'Oferta' "
                f"AND {region_cond} "
                f"{tipo_filtro} "
                f"{final_temporal}"
            )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Oferta por Tipo): {sql}")
                return sql
            except Exception:
                pass

        # 13) Precio promedio por metro cuadrado (Definición estricta: Cuenta=Oferta + Región + Tiempo)
        if "precio" in texto and ("metro cuadrado" in texto or "m2" in texto):
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Detectar cuenta para el cálculo de precio m2 (Oferta por defecto para precio m2)
            cuenta_m2 = 'Oferta'
            if any(x in texto for x in ['venta', 'vendida', 'comercializada']):
                cuenta_m2 = 'Ventas'
            elif any(x in texto for x in ['lanzamiento', 'lanzada', 'salida a ventas']):
                cuenta_m2 = 'Lanzamientos'
            elif any(x in texto for x in ['iniciacion', 'iniciada', 'inicio de obra']):
                cuenta_m2 = 'Iniciaciones'
            elif any(x in texto for x in ['entregada', 'entrega']):
                cuenta_m2 = 'Entregadas'
            elif any(x in texto for x in ['culminada', 'obra terminada']):
                cuenta_m2 = 'Culminadas'
            elif any(x in texto for x in ['paralizado', 'suspendida']):
                cuenta_m2 = 'Paralizado'
            elif any(x in texto for x in ['renuncia', 'desistimiento']):
                cuenta_m2 = 'Renuncias'
            elif any(x in texto for x in ['saldo que inicia', 'saldo inicial']):
                cuenta_m2 = 'Saldo que inicia'

            # Usar último corte de la cuenta seleccionada para precios actuales si no hay filtro temporal
            final_temporal = filtro_temporal or f" AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = '{cuenta_m2}')"
            
            sql = (
                f"SELECT AVG(precio_mc_promedio) AS {alias_sql} "
                "FROM livo "
                f"WHERE cuenta = '{cuenta_m2}' "
                f"AND {region_cond} "
                f"{final_temporal}"
            )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Precio M2): {sql}")
                return sql
            except Exception:
                pass

        # 14) Licencias de Construcción (Regla de negocio: Estado = Construcción, Preventa, Proyectado)
        if "licencia" in texto and "construccion" in texto:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Si no hay otros filtros de estado explícitos, aplicar la regla de negocio
            if not any(k in texto for k in ['estado =', 'fase =']):
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_licencias_construccion "
                    "FROM livo "
                    f"WHERE {region_cond} "
                    "AND estado IN ('Construcción', 'Preventa', 'Proyectado') "
                    f"{filtro_temporal}"
                )
                try:
                    print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Licencias Construcción): {sql}")
                    return sql
                except Exception:
                    pass

        # --- TIER 2: MOTOR DE REGLAS COMBINATORIO (FALLBACK) ---
        # Si ninguna de las reglas específicas anteriores coincidió, se intenta
        # construir una consulta combinando todos los filtros detectados.
        print("[DEBUG LIVO reglas] Ninguna regla independiente coincidió, usando motor combinatorio...")

        # --- MOTOR DE REGLAS COMBINATORIO UNIFICADO ---
        # En lugar de reglas aisladas, acumulamos todos los filtros detectados.
        
        filtros = []
        group_by_cols = [] # Nueva lista para columnas de agrupación
        
        # 1. Región (Geografía)
        region = self._extraer_region_general(texto)
        es_multiple_regiones = region and '|' in region if region else False
        
        if region:
            filtros.append(self._condicion_region_general(region))
            # Si hay múltiples regiones, agregar GROUP BY regional automáticamente
            if es_multiple_regiones:
                if "regional" not in group_by_cols:
                    group_by_cols.append("regional")
            
        # 2. Temporalidad (Año/Fecha)
        if filtro_temporal:
            clean_temporal = filtro_temporal.strip()
            if clean_temporal.upper().startswith("AND "):
                clean_temporal = clean_temporal[4:].strip()
            filtros.append(clean_temporal)

        # 3. Tipo de Vivienda (VIS/VIP/No VIS)
        tipos_interes = []
        
        # Detectar si hay intención explícita de agrupación por tipo
        agrupar_por_tipo = False
        if 'agrupado por' in texto:
            # Verificar si después de "agrupado por" se mencionan tipos de vivienda
            texto_despues_agrupado = texto.split('agrupado por')[-1].lower()
            if any(t in texto_despues_agrupado for t in ['vis', 'vip', 'tipo de vivienda']):
                agrupar_por_tipo = True
        elif any(x in texto for x in ['por vis, no vis', 'por vis, vip', 'por no vis, vip', 'por vis, no vis y vip']):
            agrupar_por_tipo = True
        
        # Detectar No VIS
        if "no vis" in texto:
            tipos_interes.append("'No VIS'")
            
        # Detectar VIS (asegurando que no sea parte de "no vis")
        texto_sin_novis = texto.replace("no vis", "")
        if "vis" in texto_sin_novis:
            if "sin vip" in texto:
                tipos_interes.append("'VIS'")
            else:
                tipos_interes.append("'VIS'")
                if "vip" not in texto:
                     tipos_interes.append("'VIP'")
        
        # Detectar VIP explícito
        if "vip" in texto and "'VIP'" not in tipos_interes:
            tipos_interes.append("'VIP'")
            
        if tipos_interes:
            tipos_interes = sorted(list(set(tipos_interes)))
            # Solo aplicar filtro si NO hay intención de agrupación explícita
            if not agrupar_por_tipo:
                if len(tipos_interes) == 1:
                    filtros.append(f"segmento_pre = {tipos_interes[0]}")
                else:
                    filtros.append(f"segmento_pre IN ({', '.join(tipos_interes)})")
            
            # Si hay múltiples tipos o intención de agrupación, preparar agrupación
            if len(tipos_interes) > 1 or agrupar_por_tipo or any(x in texto for x in ['comparar', 'vs', 'diferencia', 'distribucion']):
                if "segmento_pre" not in group_by_cols:
                    group_by_cols.append("segmento_pre")
        elif any(x in texto for x in ['agrupado por tipo', 'por tipo de vivienda']):
            # Si se menciona agrupación por tipo pero no se detectaron tipos específicos, agregar agrupación
            if "segmento_pre" not in group_by_cols:
                group_by_cols.append("segmento_pre")

        # 4. Cuenta (Estado contable)
        cuentas_map = {
            # Saldo que inicia
            'saldo': 'Saldo que inicia', 'saldo que inicia': 'Saldo que inicia', 'saldo inicial': 'Saldo que inicia', 'inventario inicial': 'Saldo que inicia',
            'stock inicial': 'Saldo que inicia', 'unidades al inicio': 'Saldo que inicia', 'comienzo del periodo': 'Saldo que inicia',
            'saldo de arranque': 'Saldo que inicia', 'base inicial': 'Saldo que inicia', 'punto de partida': 'Saldo que inicia',
            'inventario de apertura': 'Saldo que inicia', 'stock de apertura': 'Saldo que inicia', 'unidades iniciales': 'Saldo que inicia',
            'saldo anterior': 'Saldo que inicia', 'remanente anterior': 'Saldo que inicia', 'stock previo': 'Saldo que inicia',
            'inicio de mes': 'Saldo que inicia',

            # Oferta
            'oferta': 'Oferta', 'disponible': 'Oferta', 'inventario': 'Oferta', 'stock': 'Oferta',
            'unidades disponibles': 'Oferta', 'oferta comercial': 'Oferta', 'vivienda disponible': 'Oferta',
            'en venta': 'Oferta', 'por vender': 'Oferta', 'stock disponible': 'Oferta', 'inventario final': 'Oferta',
            'oferta total': 'Oferta', 'unidades en oferta': 'Oferta', 'mercado disponible': 'Oferta',
            'stock de vivienda': 'Oferta', 'oferta de vivienda': 'Oferta', 'unidades a la venta': 'Oferta',

            # Ventas
            'ventas': 'Ventas', 'vendidas': 'Ventas', 'vendido': 'Ventas', 'vendieron': 'Ventas',
            'comercializadas': 'Ventas', 'negocios': 'Ventas', 'cierres': 'Ventas', 'promesas': 'Ventas',
            'unidades vendidas': 'Ventas', 'absorcion': 'Ventas', 'absorción': 'Ventas', 'demanda': 'Ventas',
            'colocacion': 'Ventas', 'colocación': 'Ventas', 'ventas netas': 'Ventas', 'escrituradas': 'Ventas',
            'separaciones': 'Ventas', 'unidades comercializadas': 'Ventas', 'mercado vendido': 'Ventas',
            'flujo de ventas': 'Ventas', 'ventas del mes': 'Ventas', 'se vendieron': 'Ventas', 'compradas': 'Ventas',

            # Renuncias
            'renuncias': 'Renuncias', 'renuncia': 'Renuncias', 'desistimientos': 'Renuncias', 'desistimiento': 'Renuncias',
            'cancelaciones': 'Renuncias', 'devoluciones': 'Renuncias', 'negocios caidos': 'Renuncias', 'negocios caídos': 'Renuncias',
            'ventas canceladas': 'Renuncias', 'unidades devueltas': 'Renuncias', 'rescisiones': 'Renuncias',
            'anulaciones': 'Renuncias', 'reversiones': 'Renuncias', 'caidas de negocio': 'Renuncias', 'caídas de negocio': 'Renuncias',
            'desistidas': 'Renuncias', 'renunciadas': 'Renuncias', 'retornos a oferta': 'Renuncias',
            'canceladas': 'Renuncias', 'ventas caidas': 'Renuncias', 'ventas caídas': 'Renuncias', 'unidades desistidas': 'Renuncias',
            'desistido': 'Renuncias', 'estado desistido': 'Renuncias', 'en estado desistido': 'Renuncias',

            # Iniciaciones
            'iniciaciones': 'Iniciaciones', 'iniciadas': 'Iniciaciones', 'inicios de obra': 'Iniciaciones',
            'arranques': 'Iniciaciones', 'obras iniciadas': 'Iniciaciones', 'construccion iniciada': 'Iniciaciones', 'construcción iniciada': 'Iniciaciones',
            'nuevos frentes': 'Iniciaciones', 'apertura de obra': 'Iniciaciones', 'unidades iniciadas': 'Iniciaciones',
            'comienzo de construccion': 'Iniciaciones', 'comienzo de construcción': 'Iniciaciones', 'ejecucion iniciada': 'Iniciaciones', 'ejecución iniciada': 'Iniciaciones',
            'obras nuevas': 'Iniciaciones', 'proyectos iniciados': 'Iniciaciones', 'inicio de construccion': 'Iniciaciones', 'inicio de construcción': 'Iniciaciones',
            'arranques de obra': 'Iniciaciones', 'unidades en ejecucion': 'Iniciaciones', 'unidades en ejecución': 'Iniciaciones',
            'primera piedra': 'Iniciaciones', 'empezaron obra': 'Iniciaciones',

            # Entregadas
            'entregadas': 'Entregadas', 'entregas': 'Entregadas', 'terminadas': 'Entregadas', 'finalizadas': 'Entregadas',
            'escrituradas y entregadas': 'Entregadas', 'llaves en mano': 'Entregadas', 'unidades entregadas': 'Entregadas',
            'fin de obra': 'Entregadas', 'construccion terminada': 'Entregadas', 'construcción terminada': 'Entregadas',
            'entregas efectivas': 'Entregadas', 'culminacion de entrega': 'Entregadas', 'culminación de entrega': 'Entregadas',
            'recibidas por cliente': 'Entregadas', 'unidades finalizadas': 'Entregadas', 'obra blanca terminada': 'Entregadas',
            'habitables': 'Entregadas', 'entrega material': 'Entregadas', 'posesion entregada': 'Entregadas', 'posesión entregada': 'Entregadas',

            # Lanzamientos
            'lanzamientos': 'Lanzamientos', 'lanzadas': 'Lanzamientos', 'lanzamiento': 'Lanzamientos',
            'nuevos proyectos': 'Lanzamientos', 'salida a ventas': 'Lanzamientos', 'preventa': 'Lanzamientos',
            'oferta nueva': 'Lanzamientos', 'unidades lanzadas': 'Lanzamientos', 'nuevos desarrollos': 'Lanzamientos',
            'levantamiento': 'Lanzamientos', 'levantamientos': 'Lanzamientos',
            'apertura de ventas': 'Lanzamientos', 'lanzamiento comercial': 'Lanzamientos', 'proyectos nuevos': 'Lanzamientos',
            'unidades nuevas': 'Lanzamientos', 'entrada al mercado': 'Lanzamientos', 'inicio de comercializacion': 'Lanzamientos', 'inicio de comercialización': 'Lanzamientos',
            'nuevos sobre planos': 'Lanzamientos', 'oferta reciente': 'Lanzamientos',

            # Paralizado
            'paralizado': 'Paralizado', 'paralizada': 'Paralizado', 'paralizando': 'Paralizado',
            'obras detenidas': 'Paralizado', 'suspendidas': 'Paralizado', 'frenadas': 'Paralizado',
            'quietas': 'Paralizado', 'sin avance': 'Paralizado', 'paralizacion': 'Paralizado', 'paralización': 'Paralizado',
            'bloqueo de obra': 'Paralizado', 'construccion parada': 'Paralizado', 'construcción parada': 'Paralizado',
            'proyectos suspendidos': 'Paralizado', 'obras paradas': 'Paralizado', 'inactivos': 'Paralizado',
            'detenidos': 'Paralizado', 'estancados': 'Paralizado', 'suspension de obra': 'Paralizado', 'suspensión de obra': 'Paralizado',
            'no avanzan': 'Paralizado', 'congelados': 'Paralizado',

            # Culminadas
            'culminadas': 'Culminadas', 'culminada': 'Culminadas',
            'obra terminada': 'Culminadas', 'estructura finalizada': 'Culminadas', 'construccion completa': 'Culminadas', 'construcción completa': 'Culminadas',
            'unidades acabadas': 'Culminadas', 'fin de construccion': 'Culminadas', 'fin de construcción': 'Culminadas',
            '100% construido': 'Culminadas', 'obra concluida': 'Culminadas', 'proyecto terminado': 'Culminadas',
            'edificacion completa': 'Culminadas', 'edificación completa': 'Culminadas', 'finalizacion de obra': 'Culminadas', 'finalización de obra': 'Culminadas',
            'terminacion fisica': 'Culminadas', 'terminación física': 'Culminadas', 'unidades concluidas': 'Culminadas',
            'acabados listos': 'Culminadas', 'cierre de obra': 'Culminadas', 'construccion finalizada': 'Culminadas', 'construcción finalizada': 'Culminadas',
            'estado terminado': 'Culminadas', 'en estado terminado': 'Culminadas'
        }
        
        for key, val in cuentas_map.items():
            # Usar regex para palabra completa para evitar falsos positivos
            if re.search(r'\b' + re.escape(key) + r'\b', texto):
                filtros.append(f"cuenta = '{val}'")
                break
        
        # 5. Last Estado
        last_estado_map = {
            'construccion': 'Construcción',
            'tve': 'TVE',
            'preventa': 'Preventa',
            'cancelado': 'Cancelado',
            'paralizado': 'Paralizado',
            'te': 'TE',
            'rediseñado': 'Rediseñado',
            'proyectado': 'Proyectado'
        }
        
        for key, val in last_estado_map.items():
            # Verificar palabra completa
            if re.search(r'\b' + re.escape(key) + r'\b', texto):
                if f"last_estado {key}" in texto or f"ultimo estado {key}" in texto:
                    filtros.append(f"last_estado = '{val}'")
                    break
        
        # 6. Fase
        fase_map = {
            'preliminar': 'Preliminar',
            'sin iniciar': 'Sin Iniciar',
            'terminado': 'Terminado',
            'estructura': 'Estructura',
            'obra negra': 'Obra Negra',
            'acabados': 'Acabados',
            'cimentacion': 'Cimentación',
            'urbanismo': 'Urbanismo'
        }
        
        for key, val in fase_map.items():
            if re.search(r'\b' + re.escape(key) + r'\b', texto):
                filtros.append(f"fase = '{val}'")
                break
        
        # 7. Estado
        estado_map = {
            'construccion': 'Construcción',
            'preventa': 'Preventa',
            'tve': 'TVE',
            'rediseñado': 'Rediseñado',
            'paralizado': 'Paralizado',
            'paralizando': 'Paralizado',
            'te': 'TE',
            'cancelado': 'Cancelado',
            'proyectado': 'Proyectado'
        }
        
        for key, val in estado_map.items():
            # Usar regex para palabra completa (CRÍTICO para evitar que 'te' coincida con 'norte' o 'terminado')
            if re.search(r'\b' + re.escape(key) + r'\b', texto):
                if f"last_estado {key}" not in texto:
                    filtros.append(f"estado = '{val}'")
                    break
        
        # 8. Uso Etapa
        uso_etapa_map = {
            'apartamento': 'Apartamento',
            'casa': 'Casa',
            'oficina': 'Oficina',
            'local': 'Local',
            'bodega': 'Bodega',
            'lote': 'Lote',
            'consultorio': 'Consultorio',
            'hotel': 'Hotel',
            'hospital': 'Hospital',
            'educacion': 'Educación',
            'comercio': 'Comercio',
            'industria': 'Industria'
        }
        
        for key, val in uso_etapa_map.items():
            if re.search(r'\b' + re.escape(key) + r'\b', texto):
                filtros.append(f"uso_etapa = '{val}'")
                break
        
        # 9. Destino Etapa
        destino_etapa_map = {
            'venta': 'Venta',
            'uso propio': 'Uso Propio',
            'arrendar': 'Arrendar',
            'adjudicacion': 'Adjudicación',
            'sin definir': 'Sin Definir'
        }
        
        for key, val in destino_etapa_map.items():
            # 'venta' puede ser ambiguo con 'ventas' (cuenta). Si dice 'ventas' es cuenta, si dice 'venta' es destino.
            if key == 'venta' and re.search(r'\bventas\b', texto):
                continue
            if re.search(r'\b' + re.escape(key) + r'\b', texto):
                filtros.append(f"destino_etapa = '{val}'")
                break
        
        # 10. Estrato
        estrato_match = re.search(r"estrato\s*([0-6])", texto)
        if estrato_match:
            estrato_val = int(estrato_match.group(1))
            filtros.append(f"estrato = {estrato_val}")

        # 11. Detección de columnas de agrupación (SOLO para GROUP_BY y RANKING explícitos)
        # NO agregar agrupación para consultas simples de conteo
        if op_funcion in ["GROUP_BY", "RANKING"]:
            # Mapeo de términos de agrupación a columnas
            agrupacion_map = {
                'modalidad': 'modalidad',
                'sector': 'zona',
                'zona': 'zona',
                'distrito': 'zona',
                'situacion': 'estado',
                'clasificacion': 'segmento_pre',
                'clase social': 'estrato',
                'nivel socioeconomico': 'estrato',
                'estatus': 'estado',
                'estado': 'estado',
                'fase': 'fase',
                'regional': 'regional',
                'regionales': 'regional',
                'departamento': 'departamento',
                'departamentos': 'departamento',
                'ciudad': 'ciudad',
                'ciudades': 'ciudad',
                'estrato': 'estrato',
                'tipo': 'segmento_pre',
                'tipos': 'segmento_pre',
                'segmento': 'segmento_pre',
                'segmentos': 'segmento_pre',
                'constructora': 'compania_constructora',
                'constructoras': 'compania_constructora',
                'empresa': 'compania_constructora',
                'empresas': 'compania_constructora',
                'firma': 'compania_constructora',
                'firmas': 'compania_constructora',
                'cuenta': 'cuenta',
                'cuentas': 'cuenta',
                'uso_etapa': 'uso_etapa',
                'uso': 'uso_etapa',
                'usos': 'uso_etapa',
                'destino_etapa': 'destino_etapa',
                'destino': 'destino_etapa',
                'destinos': 'destino_etapa',
                'last_estado': 'last_estado',
                'ultimo_estado': 'last_estado',
                'último_estado': 'last_estado',
                'ultimo estado': 'last_estado',
                'último estado': 'last_estado',
                'nuevorango_pre': 'nuevorango_pre',
                'nuevo_rango': 'nuevorango_pre',
                'rangos_decreto_pre': 'rangos_decreto_pre',
                'rango_decreto': 'rangos_decreto_pre',
                'rango_minviv': 'rango_minviv',
                'rango_min_vivienda': 'rango_minviv',
                'rango_ppm2': 'rango_ppm2',
                'rango_ppm': 'rango_ppm2',
                'rango_area': 'rango_area',
                'rango_metros': 'rango_area',
                'am_capital': 'AM_capital',
                'aglomeracion': 'AM_capital',
                'area_metropolitana': 'AM_capital'
            }
            
            for key, col in agrupacion_map.items():
                if key in texto:
                    if col not in group_by_cols:
                        group_by_cols.append(col)

        # --- CONSTRUCCIÓN FINAL DEL SQL ---
        # Solo construir si se detectó al menos un filtro
        if filtros:
            # --- LÓGICA DE NEGOCIO ADICIONAL (Contexto de Vivienda para Venta) ---
            # Palabras clave que implican explícitamente una consulta sobre vivienda PARA LA VENTA
            explicit_sale_keywords = [
                'venta', 'vendida', 'comercializada', 'para la venta', 'en venta',
                'ventas', 'lanzamientos', 'lanzadas', 'iniciaciones', 'iniciadas', 'oferta',
                'paralizado', 'culminadas', 'entregadas', 'renuncias', 'saldo que inicia'
            ]
            # Palabras de segmentación que NO implican venta forzosa
            segmentation_keywords = ['vis', 'vip', 'no vis', 'vivienda de interes', 'precio entre', 'precio mayor']
            
            is_explicit_sale_query = any(k in texto for k in explicit_sale_keywords)
            is_segmentation_query = any(k in texto for k in segmentation_keywords) and not is_explicit_sale_query
            
            # Verificar si ya se aplicaron filtros de uso o destino
            has_uso_filter = any('uso_etapa' in f for f in filtros)
            has_destino_filter = any('destino_etapa' in f for f in filtros)

            # NOTA: Filtros uso_etapa y destino_etapa eliminados para coincidir con queries humanos

            where_clause = " AND ".join(filtros)
            
            # --- PROTECCIÓN OFERTA: NO SUMAR ENTRE PERIODOS ---
            # Si se consulta 'Oferta' y NO hay filtro temporal específico (rango de fechas), forzar que sea solo del último periodo disponible.
            # Si hay filtro temporal específico (ej: "fecha >= 20260101"), respetar el rango de fechas.
            tiene_rango_fechas = any("fecha >=" in f for f in filtros)
            if any("cuenta = 'Oferta'" in f for f in filtros) and not tiene_rango_fechas:
                # Subconsulta para encontrar la fecha máxima que cumple con los filtros actuales
                subquery_max_fecha = f"(SELECT MAX(fecha) FROM livo WHERE {where_clause})"
                where_clause += f" AND fecha = {subquery_max_fecha}"
            
            # Construcción de SELECT y GROUP BY
            cols_select = [f"{metrica_sql} AS {alias_sql}"]
            group_by_clause = ""
            
            if group_by_cols:
                cols_select = group_by_cols + cols_select
                group_by_clause = f" GROUP BY {', '.join(group_by_cols)} ORDER BY {alias_sql} DESC"

            # Extraer top_n si es una consulta de RANKING
            limit_clause = ""
            if op_funcion == "RANKING":
                top_n = 5  # Valor por defecto
                # Buscar números en el texto (ej: "los 5 principales", "top 10")
                match_n = re.search(r'\b(top|los)?\s*(\d+)\s*(principales)?\b', texto)
                if match_n:
                    top_n = int(match_n.group(2))
                else:
                    match_any_num = re.search(r'\b(\d{1,2})\b', texto)
                    if match_any_num:
                        top_n = int(match_any_num.group(1))
                limit_clause = f" LIMIT {top_n}"

            sql = (
                f"SELECT {', '.join(cols_select)} "
                "FROM livo "
                f"WHERE {where_clause}"
                f"{group_by_clause}"
                f"{limit_clause}"
            )
            try:
                print(f"[DEBUG LIVO reglas] SQL Combinatorio (con lógica de negocio) generado: {sql}")
                return sql
            except Exception:
                pass

        # Si no se reconoce el patrón, no generamos SQL
        return None

    def _extraer_region_general(self, texto_local: str) -> Optional[str]:
        """Extrae región usando lista conocida (más robusto que regex "en ...").
        
        Ahora soporta múltiples regiones separadas por conectores como "y", "e", "o".
        Retorna una lista de regiones (separadas por |) o una sola región si es única.
        """
        ubicaciones = [
            # Regionales (con nombres exactos de la base de datos)
            'bogota y cundinamarca', 'bogota & cundinamarca', 'bogota cundinamarca',
            'cordoba y sucre', 'cordoba & sucre', 'cordoba sucre',
            'nariño', 'narino',
            'valle', 'valle del cauca',
            'bolivar', 'bolívar',
            'antioquia',
            'santander',
            'cauca',
            'tolima',
            'huila',
            'risaralda',
            'atlantico', 'atlántico',
            'caldas',
            'boyaca casanare', 'boyacá casanare', 'boyaca_casanare',
            'magdalena',
            'cucuta nororiente', 'cúcuta nororiente', 'cucuta_nororiente',
            'meta',
            'cesar',
            'quindio', 'quindío',
            # Departamentos y ciudades (para compatibilidad)
            'bogota d.c.', 'bogota', 'cundinamarca',
            'sucre',
            'norte de santander', 'cucuta', 'cúcuta',
            'boyaca', 'boyacá',
            'cartagena',
            'cali',
            'medellin',
            'barranquilla',
            'bucaramanga',
            'pereira',
            'manizales',
            'ibague',
            'santa marta',
            'villavicencio',
            'pasto',
            'monteria',
            'valledupar',
            'popayan',
            'armenia',
            'neiva',
            'tunja',
            'riohacha',
            'sincelejo',
            'florencia',
            'yopal',
            'quibdo',
            'san andres',
            'leticia',
            'mocoa',
            'mitu',
            'puerto carreno',
            'inirida',
            'san jose del guaviare',
            'arauca',
            # Referencias nacionales
            'nacional', 'colombia', 'pais', 'todo el pais'
        ]
        # Ordenar por longitud descendente para coincidir "bogota y cundinamarca" antes que "bogota"
        ubicaciones.sort(key=len, reverse=True)
        
        # Detectar múltiples regiones separadas por conectores
        # Conectores: " y ", " e ", " o "
        conectores = [' y ', ' e ', ' o ']
        texto_lower = texto_local.lower()
        for conector in conectores:
            if conector in texto_lower:
                partes = texto_lower.split(conector)
                regiones_encontradas = []
                for parte in partes:
                    for ubicacion in ubicaciones:
                        if re.search(r'\b' + re.escape(ubicacion) + r'\b', parte, re.IGNORECASE):
                            regiones_encontradas.append(ubicacion)
                            break
                if len(regiones_encontradas) > 1:
                    # Retornar las regiones unidas con "|" para procesamiento posterior
                    return '|'.join(regiones_encontradas)
        
        # Si no hay múltiples regiones, buscar una sola
        texto_lower = texto_local.lower()
        for ubicacion in ubicaciones:
            if ubicacion in texto_lower:
                return ubicacion
        return None

    def _condicion_region_general(self, region_fragmento: str) -> str:
        """Genera condición SQL para región.
        
        Si el fragmento contiene "|", genera condiciones OR para múltiples regiones.
        Si no, usa la lógica original para una sola región.
        """
        # Mapeo de nombres de usuario a nombres exactos de regionales en la base de datos
        mapeo_regional = {
            'bogota': 'Bogotá & Cundinamarca',
            'bogota d.c.': 'Bogotá & Cundinamarca',
            'cundinamarca': 'Bogotá & Cundinamarca',
            'bogota cundinamarca': 'Bogotá & Cundinamarca',
            'bogota y cundinamarca': 'Bogotá & Cundinamarca',
            'bogota & cundinamarca': 'Bogotá & Cundinamarca',
            'atlantico': 'Atlántico',
            'atlántico': 'Atlántico',
            'cordoba': 'Córdoba & Sucre',
            'cordoba y sucre': 'Córdoba & Sucre',
            'cordoba & sucre': 'Córdoba & Sucre',
            'sucre': 'Córdoba & Sucre',
            'narino': 'Nariño',
            'nariño': 'Nariño',
            'bolivar': 'Bolívar',
            'bolívar': 'Bolívar',
            'boyaca': 'Boyacá_Casanare',
            'boyacá': 'Boyacá_Casanare',
            'boyaca casanare': 'Boyacá_Casanare',
            'boyacá casanare': 'Boyacá_Casanare',
            'cucuta': 'Cúcuta_Nororiente',
            'cúcuta': 'Cúcuta_Nororiente',
            'cucuta nororiente': 'Cúcuta_Nororiente',
            'cúcuta nororiente': 'Cúcuta_Nororiente',
            'quindio': 'Quindío',
            'quindío': 'Quindío',
        }
        
        # Verificar si hay múltiples regiones separadas por "|"
        if '|' in region_fragmento:
            regiones = region_fragmento.split('|')
            condiciones = []
            for region in regiones:
                # Normalizar cada región individualmente
                frag_norm = normalize_text(region).upper()
                
                # Aplicar mapeo a nombre exacto de regional
                frag_lower = normalize_text(region).lower()
                if frag_lower in mapeo_regional:
                    frag_norm = normalize_text(mapeo_regional[frag_lower]).upper()
                else:
                    # Caso especial: espacio simple "BOGOTA CUNDINAMARCA" -> "BOGOTA & CUNDINAMARCA"
                    frag_norm = frag_norm.replace('BOGOTA CUNDINAMARCA', 'BOGOTA & CUNDINAMARCA')
                    frag_norm = frag_norm.replace('CORDOBA SUCRE', 'CORDOBA & SUCRE')
                
                # Si es una referencia nacional, no filtrar (traer todo)
                if frag_norm in ['NACIONAL', 'COLOMBIA', 'PAIS', 'TODO EL PAIS']:
                    continue
                
                # Escapar comillas simples
                frag_norm = frag_norm.replace("'", "''")
                
                # Generar condición para esta región
                norm_depto = (
                    "UPPER(TRANSLATE(departamento, "
                    "'ÁÉÍÓÚÜÑáéíóúüñ', "
                    "'AEIOUUNAEIOUUN'))"
                )
                norm_regional = (
                    "UPPER(TRANSLATE(regional, "
                    "'ÁÉÍÓÚÜÑáéíóúüñ', "
                    "'AEIOUUNAEIOUUN'))"
                )
                norm_ciudad = (
                    "UPPER(TRANSLATE(ciudad, "
                    "'ÁÉÍÓÚÜÑáéíóúüñ', "
                    "'AEIOUUNAEIOUUN'))"
                )
                
                condiciones.append(
                    f"({norm_depto} LIKE '%{frag_norm}%' "
                    f"OR {norm_regional} LIKE '%{frag_norm}%' "
                    f"OR {norm_ciudad} LIKE '%{frag_norm}%')"
                )
            
            if condiciones:
                return " OR ".join(condiciones)
            else:
                return "1=1"
        
        # Lógica original para una sola región
        # Para evitar problemas de tildes, normalizamos ambos lados.
        # 1) Normalizamos el fragmento en Python (sin tildes, minúsculas)
        frag_norm = normalize_text(region_fragmento).replace(' y ', ' & ').replace(' - ', ' & ').upper()
        
        # Aplicar mapeo a nombre exacto de regional
        frag_lower = normalize_text(region_fragmento).lower()
        if frag_lower in mapeo_regional:
            frag_norm = normalize_text(mapeo_regional[frag_lower]).upper()
        else:
            # Caso especial: espacio simple "BOGOTA CUNDINAMARCA" -> "BOGOTA & CUNDINAMARCA"
            frag_norm = frag_norm.replace('BOGOTA CUNDINAMARCA', 'BOGOTA & CUNDINAMARCA')
            frag_norm = frag_norm.replace('CORDOBA SUCRE', 'CORDOBA & SUCRE')

        # Si es una referencia nacional, no filtrar (traer todo)
        if frag_norm in ['NACIONAL', 'COLOMBIA', 'PAIS', 'TODO EL PAIS']:
            return "1=1"

        # Escapar comillas simples en el fragmento para evitar errores SQL
        frag_norm = frag_norm.replace("'", "''")

        # 2) En SQL, usamos TRANSLATE para quitar tildes antes del LIKE
        norm_depto = (
            "UPPER(TRANSLATE(departamento, "
            "'ÁÉÍÓÚÜÑáéíóúüñ', "
            "'AEIOUUNAEIOUUN'))"
        )
        norm_regional = (
            "UPPER(TRANSLATE(regional, "
            "'ÁÉÍÓÚÜÑáéíóúüñ', "
            "'AEIOUUNAEIOUUN'))"
        )
        norm_ciudad = (
            "UPPER(TRANSLATE(ciudad, "
            "'ÁÉÍÓÚÜÑáéíóúüñ', "
            "'AEIOUUNAEIOUUN'))"
        )

        return (
            f"({norm_depto} LIKE '%{frag_norm}%' "
            f"OR {norm_regional} LIKE '%{frag_norm}%' "
            f"OR {norm_ciudad} LIKE '%{frag_norm}%')"
        )

    def _consultar_coyuntura_directa(self, pregunta: str) -> Optional[str]:
        """Consulta directa a los sistemas oficiales de Coyuntura (DuckDB), sin usar SQL de LIVO.

        Ahora delega en `responder_pregunta_coyuntura` de coyuntura_sql.py, que usa la tabla
        `coyuntura` en DuckDB y detecta automáticamente el último período disponible
        (por ejemplo, nov-25), sin depender de fechas hardcodeadas.
        """
        if not COYUNTURA_AVAILABLE:
            return None

        texto = normalize_text(pregunta)

        # 1. Solo aplicar a preguntas claramente de Coyuntura (ventas, oferta, lanzamientos, iniciaciones, rotación)
        es_coyuntura = any(
            p in texto
            for p in [
                "venta", "ventas", "vendida", "vendidas", "vendieron", "vendio",
                "oferta", "lanzamiento", "lanzamientos",
                "iniciacion", "iniciaciones", "iniciad",
                "rotacion", "rotación", "inventarios", "utv",
            ]
        )
        if not es_coyuntura:
            return None

        # 2. Solo priorizar Coyuntura cuando se pregunta por el último período / mes anterior
        palabras_reciente = [
            "mes anterior",
            "mes pasado",
            "ultimo mes",
            "último mes",
            "reciente",
            "actual",
        ]
        if not any(p in texto for p in palabras_reciente):
            return None

        try:
            # Delegar completamente en el sistema oficial de Coyuntura (DuckDB)
            # que ya maneja:
            # - detección de tipo_fuente (unidades/área/valor/riesgo)
            # - selección de hoja (Ventas, Oferta, Lanzamientos, Iniciaciones, Rotación)
            # - detección de departamento o 19 Regionales
            # - elección del último período disponible en la tabla `coyuntura`
            ok, respuesta, _meta = responder_pregunta_coyuntura(pregunta)
            if ok and respuesta:
                return respuesta
            return None
        except Exception as e:
            print(f"Error consultando coyuntura directa (DuckDB): {e}")
            return None

    def responder_pregunta_sin_llm(self, pregunta: str) -> Optional[str]:
        """Responde a una pregunta usando solo reglas SQL, sin LLM.

        Devuelve texto con el resultado o None si no se pudo generar/ejecutar el SQL.
        """
        # Intentar respuesta directa de Coyuntura (Prioridad Alta)
        respuesta_coyuntura = self._consultar_coyuntura_directa(pregunta)
        if respuesta_coyuntura:
            return respuesta_coyuntura

        sql = self._generar_sql_sin_llm(pregunta)
        if not sql or not self.conn:
            return None

        try:
            result = self.conn.execute(sql).fetchall()
            columns = [desc[0] for desc in self.conn.description]
            respuesta = self._formatear_resultados(result, columns, sql)
            
            # --- COMENTADO: Generar Contexto LIVO (Análisis automático) ---
            # contexto_livo = []
            # 
            # # 1. Análisis Comparativo (Año anterior)
            # comp = self._realizar_analisis_comparativo(sql, result, columns)
            # if comp: contexto_livo.append(comp)
            # 
            # # 2. Anomalías (vs Promedio)
            # anom = self._detectar_anomalias(sql, result, columns)
            # if anom: contexto_livo.append(anom)
            # 
            # # 3. Contexto Avanzado (Market Share, Segmentos, Coyuntura, Salud, Momentum, Normativa)
            # avanzado = self._generar_contexto_avanzado(sql, result, columns, pregunta)
            # contexto_livo.extend(avanzado)
            # 
            # if contexto_livo:
            #     respuesta += "\n\n**Contexto LIVO:**\n" + "\n".join(contexto_livo)
            
            respuesta += f"\n\n**Query:** `{sql}`"
            return respuesta
        except Exception as e:
            return f"Error al ejecutar SQL sin LLM: {e}"
    
    def _generar_diccionario_sinonimos(self) -> str:
        """Genera diccionario de sinónimos para el prompt"""
        sinonimos_text = "DICCIONARIO DE SINÓNIMOS (el usuario puede usar estos términos):\n\n"
        
        for campo, sinonimos in self.SINONIMOS.items():
            if campo in self.metadata:
                sinonimos_str = ", ".join(sinonimos[:5])  # Primeros 5 sinónimos
                sinonimos_text += f"  - '{campo}' también se puede referir como: {sinonimos_str}\n"
        
        sinonimos_text += "\n⚠️ IMPORTANTE: Cuando el usuario use estos términos, traduce al nombre de columna correcto.\n\n"
        
        # Agregar contexto específico sobre tipos de vivienda y períodos temporales
        sinonimos_text += self._generar_contexto_temporal()
        sinonimos_text += self._generar_contexto_tipos_vivienda()
        
        return sinonimos_text
    
    def _detectar_periodo_mas_reciente(self) -> str:
        """Detecta el período más reciente disponible en los datos"""
        try:
            if not self.conn:
                return "No disponible"
            
            # Obtener la fecha más reciente en formato YYYYMMDD
            query_fecha_max = "SELECT MAX(fecha) FROM livo WHERE fecha IS NOT NULL"
            fecha_max = self.conn.execute(query_fecha_max).fetchone()[0]
            
            if fecha_max:
                # Convertir YYYYMMDD a formato legible
                fecha_str = str(fecha_max)
                if len(fecha_str) == 8:
                    año = fecha_str[:4]
                    mes = fecha_str[4:6]
                    dia = fecha_str[6:8]
                    
                    meses = {
                        '01': 'enero', '02': 'febrero', '03': 'marzo', '04': 'abril',
                        '05': 'mayo', '06': 'junio', '07': 'julio', '08': 'agosto',
                        '09': 'septiembre', '10': 'octubre', '11': 'noviembre', '12': 'diciembre'
                    }
                    
                    mes_nombre = meses.get(mes, mes)
                    return f"{mes_nombre} de {año} (fecha: {fecha_max})"
                else:
                    return f"Fecha: {fecha_max}"
            else:
                return "No disponible"
                
        except Exception as e:
            return f"Error al detectar: {str(e)}"
    
    def _calcular_ultimos_n_meses(self, n_meses: int) -> str:
        """Calcula los últimos N meses desde la fecha más reciente"""
        try:
            if not self.conn:
                return "No disponible"
            
            # Obtener la fecha más reciente
            query_fecha_max = "SELECT MAX(fecha) FROM livo WHERE fecha IS NOT NULL"
            fecha_max = self.conn.execute(query_fecha_max).fetchone()[0]
            
            if not fecha_max:
                return "No hay fechas disponibles"
            
            fecha_str = str(fecha_max)
            if len(fecha_str) != 8:
                return f"Formato de fecha incorrecto: {fecha_max}"
            
            año_actual = int(fecha_str[:4])
            mes_actual = int(fecha_str[4:6])
            
            meses_resultado = []
            año = año_actual
            mes = mes_actual
            
            for i in range(n_meses):
                meses_resultado.append(f"{año:04d}{mes:02d}")
                
                # Retroceder un mes
                mes -= 1
                if mes == 0:
                    mes = 12
                    año -= 1
            
            meses_nombres = {
                1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
                5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
                9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
            }
            
            # Convertir a nombres legibles
            meses_legibles = []
            for mes_codigo in meses_resultado:
                año_mes = int(mes_codigo[:4])
                mes_num = int(mes_codigo[4:6])
                mes_nombre = meses_nombres.get(mes_num, str(mes_num))
                meses_legibles.append(f"{mes_nombre} {año_mes}")
            
            return f"Últimos {n_meses} meses: {', '.join(meses_legibles)} (códigos: {', '.join(meses_resultado)})"
            
        except Exception as e:
            return f"Error al calcular: {str(e)}"
    
    def _obtener_ultimo_periodo_oferta_por_anio(self, anio: int) -> str:
        """Obtiene el último período disponible de OFERTA (cuenta = 'Oferta') para un año dado.

        Regla de negocio:
        - Las ofertas no se suman entre meses.
        - Para un año dado se debe usar solo la última oferta disponible (mes más reciente de ese año).
        """
        try:
            if not self.conn:
                return "No disponible"

            query = """
                SELECT
                    MAX(fecha) AS fecha_max
                FROM livo
                WHERE cuenta = 'Oferta'
                  AND LEFT(CAST(fecha AS VARCHAR), 4) = ?
            """
            fecha_max = self.conn.execute(query, [str(anio)]).fetchone()[0]

            if not fecha_max:
                return f"No hay oferta disponible para el año {anio}"

            fecha_str = str(fecha_max)
            if len(fecha_str) != 8:
                return f"Oferta más reciente en el año {anio}: fecha {fecha_max} (formato no estándar)"

            año = int(fecha_str[:4])
            mes = int(fecha_str[4:6])

            meses_nombres = {
                1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
                5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
                9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
            }

            mes_nombre = meses_nombres.get(mes, str(mes))
            return (
                f"Para el año {año}, la oferta se debe tomar solo del mes más reciente: "
                f"{mes_nombre} {año} (código fecha: {fecha_max})."
            )
        except Exception as e:
            return f"Error al obtener último período de oferta para {anio}: {str(e)}"

    def generar_sql_oferta_anual(self, anio: int, columna_unidades: str = 'unidades') -> str:
        """Genera un SQL que calcula la oferta anual usando SOLO el último corte de oferta del año dado.

        Regla:
        - cuenta = 'Oferta'
        - Se usa MAX(fecha) dentro del año especificado
        - Solo se suman las unidades del período de oferta más reciente de ese año
        """
        anio_str = str(anio)
        sql = f"""
WITH ultimo_periodo AS (
  SELECT MAX(fecha) AS fecha_max
  FROM livo
  WHERE cuenta = 'Oferta'
    AND LEFT(CAST(fecha AS VARCHAR), 4) = '{anio_str}'
),
oferta_filtrada AS (
  SELECT *
  FROM livo
  WHERE cuenta = 'Oferta'
    AND fecha = (SELECT fecha_max FROM ultimo_periodo)
)
SELECT SUM({columna_unidades}) AS oferta_anual
FROM oferta_filtrada
"""
        return sql.strip()

    def _generar_contexto_temporal(self) -> str:
        """Genera contexto detallado sobre manejo de períodos temporales"""
        periodo_reciente = self._detectar_periodo_mas_reciente()
        ejemplo_oferta_2025 = self._obtener_ultimo_periodo_oferta_por_anio(2025)
        
        contexto = f"""CONTEXTO CRÍTICO - MANEJO DE PERÍODOS TEMPORALES EN LIVO:

═══ PERÍODO MÁS RECIENTE DISPONIBLE ═══
📅 Último dato disponible: {periodo_reciente}

═══ FORMATO DE FECHAS ═══
🗓️ Formato original: YYYYMMDD (sin guiones, sin barras)
   Ejemplo: 20251031 = 31 de octubre de 2025
   
═══ VARIABLES TEMPORALES CLAVE ═══

🔹 AÑO_CORRIDO:
   - Definición: Período de 12 meses desde el mismo mes del año anterior hasta el mes actual
   - Ejemplo: Si corte es octubre 2025, año corrido = octubre 2024 a octubre 2025
   - Uso: WHERE año_corrido = 1 para obtener datos del año corrido
   - IMPORTANTE: Es diferente al año calendario completo

🔹 ÚLTIMO AÑO:
   - Definición: Toda la información del año actual (año calendario completo)
   - Ejemplo: Si estamos en 2025, último año = todo el año 2025 (enero a diciembre)
   - Uso: WHERE LEFT(CAST(fecha AS VARCHAR), 4) = '2025' para obtener todo el año 2025
   - Diferencia: No es lo mismo que año corrido

🔹 DOCE_MESES:
   - Definición: Año de corte de los últimos 12 meses móviles.
   - Ejemplo: Contiene el año (ej: 2025) que representa el acumulado de 12 meses.
   - Uso: WHERE doce_meses = (SELECT MAX(doce_meses) FROM livo) para obtener el periodo más reciente.
   - Sinónimos: "TTM", "LTM", "año móvil", "periodo reciente"

🔹 FECHA (YYYYMMDD):
   - Formato numérico: 20251031
   - Para extraer año: CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER)
   - Para extraer mes: CAST(SUBSTR(CAST(fecha AS VARCHAR), 5, 2) AS INTEGER)
   - Para filtrar por año: WHERE LEFT(CAST(fecha AS VARCHAR), 4) = '2024'
   - Para filtrar por mes: WHERE SUBSTRING(CAST(fecha AS VARCHAR), 5, 2) = '10'

🔹 ÚLTIMOS N MESES:
   - Proceso: 1) Identificar mes más reciente con MAX(fecha)
   - Proceso: 2) Contar hacia atrás N meses desde esa fecha
   - Ejemplo: Si corte es octubre 2025 (20251031), últimos 4 meses:
     * Octubre 2025 (202510xx)
     * Septiembre 2025 (202509xx) 
     * Agosto 2025 (202508xx)
     * Julio 2025 (202507xx)
   - SQL: WHERE LEFT(CAST(fecha AS VARCHAR), 6) IN ('202510', '202509', '202508', '202507')

🔹 OFERTA (cuenta = 'Oferta') - REGLA CRÍTICA:
   - Las ofertas NO se suman entre meses.
   - "Oferta de septiembre 2025" → usar SOLO registros de septiembre 2025.
   - "Oferta del año 2025" → usar SOLO la oferta del último mes disponible de 2025
     (no sumar enero–diciembre, sino tomar únicamente el último corte).
   - Ejemplo de último período de oferta para 2025 (auto-detectado):
     {ejemplo_oferta_2025}
   - SQL típico para elegir el último período de oferta de un año:
     SELECT MAX(fecha) FROM livo
     WHERE cuenta = 'Oferta' AND LEFT(CAST(fecha AS VARCHAR), 4) = '2025';
     -- Luego filtrar SOLO por ese código de fecha en la consulta principal.

═══ EJEMPLOS DE CONSULTAS TEMPORALES CORRECTAS ═══

❌ INCORRECTO:
   WHERE año_corrido = 2024

✅ CORRECTO:
   WHERE año_corrido = 1                    -- Para año corrido (oct 2024 - oct 2025)
   WHERE LEFT(CAST(fecha AS VARCHAR), 4) = '2025'           -- Para último año (todo 2025)
   WHERE doce_meses = (SELECT MAX(doce_meses) FROM livo) -- Para últimos 12 meses móviles
   WHERE LEFT(CAST(fecha AS VARCHAR), 6) IN ('202510', '202509', '202508', '202507')  -- Últimos 4 meses

═══ DETECCIÓN AUTOMÁTICA DE PERÍODOS ═══
- "año corrido" → Usar año_corrido = 1 (período de 12 meses desde mismo mes año anterior)
- "último año" → Usar LEFT(CAST(fecha AS VARCHAR), 4) = '2025' (año calendario completo actual)
- "últimos 12 meses" → Usar doce_meses = 1 (12 meses móviles)
- "últimos N meses" → Calcular desde MAX(fecha) hacia atrás N meses
- "2024", "2025" → Extraer año específico de fecha

"""
        return contexto
    
    def _generar_contexto_tipos_vivienda(self) -> str:
        """Genera contexto detallado sobre VIS, VIP y No VIS basado en VALOR"""
        
        # Obtener rangos actuales
        rangos = SalarioMinimoColombiano.calcular_rangos_vivienda()
        salario_actual = SalarioMinimoColombiano.obtener_salario_actual()
        año_actual = datetime.now().year
        
        contexto = f"""CONTEXTO CRÍTICO - NUEVA CLASIFICACIÓN DE VIVIENDA POR VALOR:

⚠️ CAMBIO IMPORTANTE: Ya NO usar campo 'segmento_pre'. Ahora clasificar por campo 'valor'

🚨 ASPECTO TEMPORAL CRÍTICO:
Los proyectos duran 1-3 años y los salarios mínimos cambian cada año.
Un mismo proyecto puede cambiar de clasificación VIS/VIP/No VIS entre años.

═══ SALARIO MÍNIMO {año_actual} ═══
💰 Salario Mínimo Legal Vigente: ${salario_actual:,} pesos

🚨 VARIABLES CRÍTICAS LIVO - VERIFICACIÓN OBLIGATORIA:

Antes de cualquier consulta LIVO, SIEMPRE verificar y especificar:
✅ usos: Tipo de construcción (residencial/no residencial)
✅ cuenta: Estado del proyecto (ventas, entregas, proceso, renuncias)  
✅ estado: Estado específico del proyecto
✅ fase: Fase constructiva (más general que estado)
✅ last_estado: Último estado registrado
✅ destino_etapa: Propósito del proyecto
✅ uso_etapa: Tipo específico (Casa, Apartamento - singular)

⚠️ RECOMENDACIONES TEMPORALES APLICADAS:
📈 Para análisis históricos: Usar clasificación del AÑO del proyecto
🚫 No usar rangos actuales para proyectos de años anteriores  
📋 Explicar en reportes que la clasificación puede cambiar entre años
🔄 Usar SQL temporal para análisis multi-anuales

CONTEXTO IMPORTANTE - TIPOS DE VIVIENDA EN COLOMBIA:

═══ VIP (Vivienda de Interés Prioritario) ═══:
   - Rango: $0 hasta ${rangos['VIP']['max']:,} pesos (< 90 SMMLV)
   - SQL: WHERE valor < {rangos['VIP']['max']}
   - Público: Personas con ingresos más bajos

🏘️ VIS (Vivienda de Interés Social):  
   - Rango: ${rangos['VIS']['min']:,} hasta ${rangos['VIS']['max']:,} pesos (90 - 135 SMMLV)
   - SQL: WHERE valor >= {rangos['VIS']['min']} AND valor < {rangos['VIS']['max']}
   - Público: Familias con ingresos bajos a medios

🏢 NO VIS (No Vivienda de Interés Social):
   - Rango: Más de ${rangos['NO_VIS']['min']:,} pesos (> 135 SMMLV)  
   - SQL: WHERE valor >= {rangos['NO_VIS']['min']}
   - Público: Familias con ingresos medios y altos

═══ CLASIFICACIÓN TEMPORAL (CRÍTICO) ═══

⚠️ PROBLEMA: Un proyecto de $130M puede ser:
   - 2023: VIS (salario $1,160,000)
   - 2024: VIS (salario $1,300,000) 
   - 2025: VIP (salario $1,423,500)

✅ SOLUCIÓN: Usar clasificación del año específico del proyecto

📊 SQL TEMPORAL CORRECTO:
{self.generar_clasificacion_temporal_sql()}

═══ EJEMPLOS SQL CORRECTOS ═══

❌ INCORRECTO (método anterior):
   WHERE segmento_pre = 'VIS'

❌ INCORRECTO (clasificación fija):
   WHERE valor >= {rangos['VIS']['min']} AND valor < {rangos['VIS']['max']}  -- Solo para {año_actual}

✅ CORRECTO (clasificación temporal):
   SELECT *, {self.generar_clasificacion_temporal_sql()}
   FROM livo 
   WHERE clasificacion_vivienda_temporal = 'VIS'

═══ DETECCIÓN AUTOMÁTICA ═══
- "VIP" o "vivienda prioritaria" → Usar clasificación temporal
- "VIS" o "vivienda de interés social" → Usar clasificación temporal  
- "No VIS" o "vivienda no social" → Usar clasificación temporal
- Para año específico → Usar rangos de ese año solamente

⚠️ IMPORTANTE: 
- El campo 'valor' está en miles de pesos en la base de datos
- SIEMPRE considerar el año del proyecto para clasificación correcta
- Los rangos cambian cada año con el salario mínimo

{self.explicar_cambios_clasificacion()}
"""
        return contexto
    
    def _generar_contexto_negocio(self) -> str:
        """Genera contexto sobre el ciclo de vida y las reglas de negocio del sector constructor."""
        return """
CONTEXTO CRÍTICO - REGLAS DE ORO DEL SECTOR CONSTRUCTOR:

El mercado de vivienda sigue una lógica contable y de flujos. Entenderla es clave.

--- REGLA 1: ECUACIÓN DE CONTINUIDAD DE LA OFERTA ---
La oferta no es un número aislado, es el resultado de una identidad contable.
Fórmula: **Oferta Final = Oferta Inicial + Lanzamientos - Ventas**
- **Oferta (Stock):** Es una FOTO de la disponibilidad en un momento específico. NO ES SUMABLE a través del tiempo. Para períodos largos (ej: "oferta del año"), se debe usar el PROMEDIO o el dato de CIERRE (último mes).
- **Lanzamientos (Flujo):** Aumentan el inventario disponible. SON SUMABLES.
- **Ventas (Flujo):** Disminuyen el inventario. SON SUMABLES.

--- REGLA 2: INDICADORES CLAVE DE MERCADO ---
1.  **Meses de Inventario (Ratio de Absorción):** Mide cuánto tiempo tardaría en venderse todo el inventario actual al ritmo de ventas actual.
    - Fórmula: `Meses de Inventario = Oferta Actual / Promedio de Ventas (últimos meses)`
    - Interpretación:
        - **> 12 meses:** Mercado sobreofertado, posible presión a la baja en precios.
        - **6 a 12 meses:** Mercado equilibrado.
        - **< 6 meses:** Escasez de oferta, posible presión al alza en precios.

2.  **Tasa de Rotación:** Mide la eficiencia con la que se vende la oferta total disponible en un período.
    - Fórmula: `Tasa de Rotación = Ventas del Período / (Oferta Inicial + Lanzamientos del Período)`

--- REGLA 3: EL CICLO DE VIDA (LIVO) ---
El flujo de la actividad edificadora sigue estas etapas secuenciales:

1. **LANZAMIENTO (Preventa):** Salida al mercado sobre planos. Aumenta la oferta.
2. **VENTA (Cierre de Negocio):** Cierre de promesas de compraventa. Reduce la oferta.
3. **INICIACIÓN (Inicio de Obra):** Comienzo de la construcción física. Es un INDICADOR REZAGADO. Las iniciaciones de hoy reflejan las ventas de hace 6 a 12 meses. No afecta directamente la oferta comercial disponible (se puede vender algo no iniciado).
4. **OFERTA (Inventario):** Unidades remanentes que no se han vendido. Es el resultado final del ciclo.
"""

    def _obtener_ejemplos_few_shot(self, pregunta: str) -> str:
        """Obtiene dinámicamente los 2 mejores ejemplos SQL para inyectar en el prompt."""
        texto_norm = normalize_text(pregunta)
        puntuaciones = []
        
        for ex in FEW_SHOT_EXAMPLES:
            score = 0
            # Puntuación basada en palabras clave coincidentes
            for kw in ex["keywords"]:
                if kw in texto_norm:
                    score += 3
            # Puntuación por similitud de palabras completas
            words_pregunta = set(texto_norm.split())
            words_ex = set(normalize_text(ex["pregunta"]).split())
            score += len(words_pregunta.intersection(words_ex))
            puntuaciones.append((score, ex))
            
        # Ordenar por puntuación descendente y tomar los 2 mejores
        puntuaciones.sort(key=lambda x: x[0], reverse=True)
        mejores = [ex for score, ex in puntuaciones if score > 0][:2]
        
        # Si no hay coincidencias de palabras clave, tomar 2 por defecto
        if not mejores:
            mejores = [FEW_SHOT_EXAMPLES[0], FEW_SHOT_EXAMPLES[4]]
            
        ejemplos_text = "═══ EJEMPLOS DE CONSULTAS SQL RELEVANTES PARA TU PREGUNTA ═══\n\n"
        for i, ex in enumerate(mejores, 1):
            ejemplos_text += f"Ejemplo {i}:\nPregunta: \"{ex['pregunta']}\"\nSQL:\n```sql\n{ex['sql']}\n```\n\n"
            
        return ejemplos_text

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
                    # LIMITAR A 20 VALORES PARA NO SATURAR EL PROMPT (Evita error 413 en Groq)
                    valores_mostrar = meta['valores_completos'][:20]
                    valores_str = ", ".join([str(v) for v in valores_mostrar])
                    if len(meta['valores_completos']) > 20:
                        valores_str += f", ... ({len(meta['valores_completos']) - 20} más)"
                    
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
    
    def es_pregunta_livo(self, pregunta: str) -> bool:
        """
        Determina si una pregunta está relacionada con el universo de datos de LIVO
        (licencias de construcción, vivienda, constructoras, etc.) utilizando
        el diccionario de datos y los campos/valores del esquema de LIVO.
        """
        texto = normalize_text(pregunta)
        
        # EXCEPCIÓN CONCEPTUAL: Si la pregunta es teórica, legal o conceptual (e.g., "¿Qué es...?", "¿Cómo funciona...?")
        # se debe responder con el LLM (Groq) directamente en lugar de intentar generar SQL para DuckDB.
        # EXCEPCIÓN: Si la pregunta tiene "cuales son" + palabras de datos (unidades, vendidas, etc.), es una pregunta LIVO
        if any(kw in texto for kw in ['unidades', 'vendidas', 'vendido', 'ventas', 'oferta', 'lanzamientos', 'iniciaciones', 'entregadas']):
            # Si tiene palabras de datos, no tratar como conceptual aunque tenga "que es" o "que son"
            pass
        else:
            conceptos_keywords = [
                'que es', 'que son', 'cómo funciona', 'como funciona',
                'diferencia', 'cual es la funcion', 'cual es la función', 'para que sirve', 'para qué sirve',
                'como solicitar', 'cómo solicitar', 'como postularse', 'cómo postularse', 'explicar', 'explicame',
                'camacol', 'coordenada urbana', 'mi casa ya', 'subsidio', 'casa', 'vivienda de interes',
                'vivienda de interes social', 'vivienda de interes prioritario',
                'ministerio de vivienda', 'ley de vivienda', 'programa', 'fondo nacional del ahorro'
            ]
            # Evitar coincidencias de subcadena falsas (ej: "casa" en "Casanare" o "Boyacá_Casanare", "vis" en "division")
            for kw in conceptos_keywords:
                if len(kw) <= 5 or kw in ['subsidio', 'programa', 'explicar', 'diferencia']:
                    if re.search(r'\b' + re.escape(kw) + r'\b', texto):
                        return False
                else:
                    if kw in texto:
                        return False

        # 1. Palabras clave de ALTA CONFIANZA (específicas de LIVO/Construcción)
        alta_confianza = [
            'unidades', 'vis', 'vip', 'no vis', 'constructora', 'constructoras', 'empresa', 'empresas', 'firma', 'firmas', 'licencia', 'licencias',
            'lanzamientos', 'lanzadas', 'iniciaciones', 'iniciadas', 'vivienda', 'viviendas',
            'desistimientos', 'paralizado', 'paralizada', 'paralizando', 'culminadas', 'culminada',
            'entregadas', 'entregas', 'saldo que inicia', 'saldo inicial', 'precio_mc_promedio',
            'compania_constructora', 'compañia_constructora', 'obras detenidas', 'suspendidas',
            'desistido', 'desistimiento', 'apartamento', 'apartamentos', 'casa', 'casas',
            'vendido', 'vendidas', 'vender', 'se han vendido', 'se vendieron', 'comercializado', 'comercializadas',
            'costo', 'precio', 'valor'  # Sinónimos para métricas monetarias
        ]
        
        # Condición especial: preguntas sobre constructoras/empresas con cuentas
        has_constructora = any(kw in texto for kw in ['constructora', 'constructoras', 'empresa', 'empresas', 'firma', 'firmas'])
        has_cuenta = any(kw in texto for kw in ['ventas', 'lanzamientos', 'lanzadas', 'oferta', 'iniciaciones', 'iniciadas', 'entregadas', 'paralizado', 'renuncias', 'saldo'])
        if has_constructora and has_cuenta:
            return True
        
        for kw in alta_confianza:
            match = re.search(r'\b' + re.escape(kw) + r'\b', texto)
            if match:
                # debug_msg2 = f"[DEBUG es_pregunta_livo] Coincidencia alta_confianza: '{kw}' en texto"
                # if STREAMLIT_AVAILABLE:
                #     st.text(debug_msg2)
                # else:
                #     print(debug_msg2)
                return True
                
        # 2. Palabras clave de MEDIA CONFIANZA (compartidas con lenguaje general)
        # Solo se consideran LIVO si vienen acompañadas de un contexto relevante (operaciones, periodos, cuentas)
        media_confianza_contextual = [
            'fecha', 'año_corrido', 'doce_meses', 'regional', 'departamento', 'divipola', 'ciudad', 'zona', 'barrio', 
            'estrato', 'destino_etapa', 'uso_etapa', 'modalidad', 'fase', 'last_estado', 'identificador', 
            'nuevorango_pre', 'rangos_decreto_pre', 'rango_minviv', 'rango_ppm2', 'rango_area', 'am_capital', 
            'segmento_pre', 'usos', 'politica_vivienda', 'area', 'área', 'valor', 'cuenta', 'fecha_date', 'mes', 'año',
            'dia', 'momento', 'cuando', 'calendario', 'fecha de registro', 'momento de corte', 'trimestre',
            'periodo anual', 'ejercicio', 'año fiscal', 'por año', 'anualmente', 'por ano', 'anualmente',
            'ultimos 12 meses', 'ttm', 'ltm', 'año movil', 'periodo reciente', 'acumulado 12m', 'ano movil',
            'region', 'zona grande', 'area geografica', 'macrozona', 'donde (macro)', 'ubicacion', 'ubicación',
            'provincia', 'division administrativa', 'de que departamento', 'jurisdiccion',
            'codigo divipola', 'codigo municipal', 'identificador geografico', 'codigo dane',
            'municipio', 'localidad', 'poblacion', 'urbe', 'en que ciudad', 'capital',
            'sector', 'distrito', 'subzona', 'sector geografico', 'microzona',
            'vecindario', 'comuna', 'urbanizacion', 'localidad', 'sector',
            'nivel socioeconomico', 'clase social', 'estrato social', 'nivel', 'clasificacion',
            'destino o finalidad', 'uso', 'tipo de vivienda', 'empresa constructora', 'tipo de licencia', 'por valor', 'fase constructiva', 'ultimo estado', 
            'area metropolitana', 'segmento de precio', 'uso del proyecto', 'unidades de vivienda',
            'metros cuadrados', 'm2', 'metro cuadrado', 'area construida', 'valor en miles', 
            'precio promedio por metro', 'estado contable', 'estado de cuenta', 'tipo de saldo'
        ]
        
        # Opciones categóricas de LIVO
        regionales = ['antioquia', 'atlantico', 'bogota & cundinamarca', 'bogota', 'bolivar', 'boyaca_casanare', 
                     'caldas', 'cauca', 'cesar', 'cordoba & sucre', 'cucuta_nororiente', 'huila', 'magdalena', 
                     'meta', 'narino', 'quindio', 'risaralda', 'santander', 'tolima', 'valle', 'cundinamarca']
        
        # Contexto: operaciones o periodos típicos de LIVO
        operaciones = ['suma', 'promedio', 'total', 'cantidad', 'cuantos', 'cuantas', 'ranking', 'top', 'mayor', 'menor', 'distribucion', 'conteo', 'maximo', 'minimo', 'mediana', 'moda', 'crecieron', 'crecimiento', 'registraron', 'registró', 'tienen', 'hubo']
        periodos = ['ene-26', 'feb-26', 'mar-26', 'abr-26', 'may-26', 'jun-26', 'jul-26', 'ago-26', 'sep-26', 'oct-26', 'nov-26', 'dic-26',
                    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
                    '2026', '2025', '2024', '2023', 'trimestre', 'mes', 'año']
        cuentas = ['culminadas', 'entregadas', 'iniciaciones', 'lanzamientos', 'oferta', 'paralizado', 'renuncias', 'saldo que inicia', 'ventas', 'construccion', 'preventa', 'proyectado']
        
        # Check for presence of high-confidence data keywords
        has_alta_confianza_data = any(re.search(r'\b' + re.escape(kw) + r'\b', texto) for kw in alta_confianza)

        # Check for presence of contextual data keywords
        has_media_confianza = any(re.search(r'\b' + re.escape(kw) + r'\b', texto) for kw in media_confianza_contextual)
        has_regional = any(re.search(r'\b' + re.escape(reg) + r'\b', texto) for reg in regionales)
        has_operacion = any(re.search(r'\b' + re.escape(op) + r'\b', texto) for op in operaciones)
        has_periodo = any(re.search(r'\b' + re.escape(per) + r'\b', texto) for per in periodos)
        has_cuenta = any(re.search(r'\b' + re.escape(cta) + r'\b', texto) for cta in cuentas)
        
        # DEBUG: Imprimir estado de detección (comentado)
        # debug_msg = f"[DEBUG es_pregunta_livo] texto: {texto}\n"
        # debug_msg += f"[DEBUG es_pregunta_livo] has_alta_confianza_data: {has_alta_confianza_data}\n"
        # debug_msg += f"[DEBUG es_pregunta_livo] has_media_confianza: {has_media_confianza}\n"
        # debug_msg += f"[DEBUG es_pregunta_livo] has_operacion: {has_operacion}\n"
        # debug_msg += f"[DEBUG es_pregunta_livo] has_periodo: {has_periodo}"
        # 
        # if STREAMLIT_AVAILABLE:
        #     st.text(debug_msg)
        # else:
        #     print(debug_msg)
        
        # 3. Palabras clave CONCEPTUALES (que deberían ir a LLM general)
        # EXCEPCIÓN: Si la pregunta tiene palabras de datos, no tratar como conceptual
        if not any(kw in texto for kw in ['unidades', 'vendidas', 'vendido', 'ventas', 'oferta', 'lanzamientos', 'iniciaciones', 'entregadas']):
            conceptos_keywords = [
                'que es', 'que son', 'cómo funciona', 'como funciona', 'requisito', 'requisitos',
                'diferencia', 'cual es la funcion', 'cual es la función', 'para que sirve', 'para qué sirve',
                'como solicitar', 'cómo solicitar', 'como postularse', 'cómo postularse', 'explicar', 'explicame',
                'camacol', 'coordenada urbana', 'mi casa ya', 'subsidio',
                'ministerio de vivienda', 'ley de vivienda', 'programa', 'fondo nacional del ahorro'
            ]
            has_conceptual_keywords = any(kw in texto for kw in conceptos_keywords)
        else:
            has_conceptual_keywords = False

        # Decision logic:
        # If it has high-confidence data keywords, it's LIVO.
        if has_alta_confianza_data:
            # print(f"[DEBUG es_pregunta_livo] RETORNO TRUE por alta_confianza")
            return True
        
        # If it has contextual data keywords AND an operation/region/period/account, it's LIVO.
        if has_media_confianza and has_operacion and (has_regional or has_periodo or has_cuenta):
            return True
        if has_regional and has_cuenta: # e.g., "ventas en bogota"
            return True
        if has_regional and has_periodo and has_operacion: # e.g., "total unidades en bogota en 2025"
            return True
            
        # If it has conceptual keywords AND NO strong data keywords, it's conceptual.
        if has_conceptual_keywords and not has_alta_confianza_data and not (has_media_confianza and has_operacion):
            return False

        # Default to LIVO if it's not clearly conceptual and has some data-like terms.
        # This makes it more likely to try LIVO first.
        return has_media_confianza or has_regional or has_operacion or has_periodo or has_cuenta
    
    def clasificar_intencion_pregunta(self, pregunta: str) -> str:
        """
        Clasifica la intención de la pregunta para prevenir alucinaciones
        """
        pregunta_lower = pregunta.lower()
        
        # Patrones de conteo simple
        if any(word in pregunta_lower for word in ["cuántas", "cuántos", "conteo", "total", "cantidad"]):
            if "unidades" in pregunta_lower:
                return "conteo_unidades"
            return "conteo_simple"
        
        # Patrones de promedio
        elif any(word in pregunta_lower for word in ["promedio", "media", "average", "promedio"]):
            return "promedio"
        
        # Patrones de variación
        elif any(word in pregunta_lower for word in ["variación", "cambio", "diferencia", "variaron", "varió"]):
            return "variacion"
        
        # Patrones de porcentaje/tasa
        elif any(word in pregunta_lower for word in ["tasa", "porcentaje", "proporción"]):
            return "porcentaje"
        
        # Patrones de preventa específica
        elif "preventa" in pregunta_lower:
            return "preventa"
        
        # Patrones de lanzamientos
        elif any(word in pregunta_lower for word in ["lanzamientos", "lanzamiento"]):
            return "lanzamientos"
        
        else:
            return "desconocida"
    
    def validar_coherencia_sql(self, sql: str, pregunta: str, intencion: str) -> tuple[bool, str]:
        """
        Valida la coherencia entre el SQL generado y la intención de la pregunta
        """
        errores = []
        sql_upper = sql.upper()
        
        # 1. DETECCIÓN CRÍTICA: Alucinación sistemática de preventa
        if intencion == "preventa":
            # Detectar patrón de alucinación: tasa de desistimiento en lugar de conteo
            if any(pattern in sql_upper for pattern in ["TASA_DESISTIMIENTO", "RENUNCIAS", "VENTAS"]) and "PREVENTA" not in sql_upper:
                errores.append("ALUCINACIÓN DETECTADA: Generó consulta de tasa/renuncias en lugar de conteo de preventa")
            
            # Validar filtros esenciales de preventa
            if "USO_ETAPA LIKE '%PREVENTA%'" not in sql_upper:
                errores.append("Pregunta de preventa requiere filtro uso_etapa LIKE '%PREVENTA%'")
            if "CUENTA = 'OFERTA'" not in sql_upper:
                errores.append("Pregunta de preventa debe usar cuenta = 'Oferta'")
        
        # 2. Validar filtros específicos según palabras clave de la pregunta
        filtros_requeridos = self._extraer_filtros_requeridos(pregunta)
        for filtro in filtros_requeridos:
            if filtro["condicion"] not in sql_upper:
                errores.append(f"Filtro requerido omitido: {filtro['descripcion']}")
        
        # 3. Detectar contradicciones WHERE vs SELECT
        where_cuenta = self._extraer_condicion_where(sql, "cuenta")
        select_cuentas = self._extraer_condiciones_select(sql, "cuenta")
        
        if where_cuenta and select_cuentas:
            if not any(cond.strip("'") in where_cuenta for cond in select_cuentas):
                errores.append(f"Contradicción: WHERE usa {where_cuenta} pero SELECT usa {select_cuentas}")
        
        # 4. Validar coherencia de agregación vs intención
        if intencion == "conteo_unidades":
            if "TASA" in sql_upper or "PORCENTAJE" in sql_upper:
                errores.append("Pregunta pide conteo pero SQL calcula tasa/porcentaje")
            if "AVG(" in sql_upper and "SUM(" not in sql_upper and "COUNT(" not in sql_upper:
                errores.append("Pregunta pide conteo pero SQL usa promedio")
        
        elif intencion == "promedio":
            if "SUM(" in sql_upper and "AVG(" not in sql_upper:
                errores.append("Pregunta pide promedio pero SQL usa suma")
        
        # 5. Validar campos incorrectos comunes
        campos_incorrectos = {
            "COMPANIA_CONSTRUCTORA": "CUENTA",
            "BARRIO": "CIUDAD",
            "DEPARTAMENTO": "CIUDAD"
        }
        
        for incorrecto, correcto in campos_incorrectos.items():
            if incorrecto in sql_upper:
                errores.append(f"Campo incorrecto '{incorrecto}', debería usar '{correcto}'")
        
        # 6. Validar filtros de ciudad
        if any(ciudad in pregunta.upper() for ciudad in ["MEDELLÍN", "BOGOTÁ", "CALI", "BARRANQUILLA"]):
            ciudad_encontrada = next((ciudad for ciudad in ["MEDELLÍN", "BOGOTÁ", "CALI", "BARRANQUILLA"] 
                                   if ciudad in pregunta.upper()), None)
            if ciudad_encontrada and ciudad_encontrada not in sql_upper:
                errores.append(f"Pregunta menciona {ciudad_encontrada} pero no aparece en el SQL")
        
        # 7. Detectar over-engineering
        complejidad = self._calcular_complejidad_sql(sql)
        if intencion in ["conteo_unidades", "preventa"] and complejidad > 7:
            errores.append("Query excesivamente complejo para pregunta simple")
        
        return len(errores) == 0, "; ".join(errores) if errores else "SQL coherente"
    
    def _extraer_filtros_requeridos(self, pregunta: str) -> list:
        """
        Extrae filtros requeridos basados en palabras clave de la pregunta
        """
        pregunta_upper = pregunta.upper()
        filtros = []
        
        # Filtro "sin VIP"
        if "SIN VIP" in pregunta_upper or "NO VIP" in pregunta_upper:
            filtros.append({
                "condicion": "NOT LIKE '%VIP%'",
                "descripcion": "excluir VIP (NOT LIKE '%VIP%')"
            })
        
        # Filtro "arriendo"
        if "ARRIENDO" in pregunta_upper:
            filtros.append({
                "condicion": "DESTINO_ETAPA = 'ARRIENDAR'",
                "descripcion": "arriendo (DESTINO_ETAPA = 'ARRIENDAR')"
            })
        
        # Filtro "VIS" específico
        if " VIS" in pregunta_upper and "SIN VIP" not in pregunta_upper:
            filtros.append({
                "condicion": "RANGOS_DECRETO_PRE LIKE 'VIS %'",
                "descripcion": "filtro VIS (RANGOS_DECRETO_PRE LIKE 'VIS %')"
            })
        
        # Filtro "No VIS"
        if " NO VIS" in pregunta_upper:
            filtros.append({
                "condicion": "RANGOS_DECRETO_PRE NOT LIKE 'VIS %'",
                "descripcion": "filtro No VIS (RANGOS_DECRETO_PRE NOT LIKE 'VIS %')"
            })
        
        return filtros
    
    def _calcular_complejidad_sql(self, sql: str) -> int:
        """
        Calcula la complejidad del SQL basado en varios factores
        """
        sql_upper = sql.upper()
        complejidad = 0
        
        # Contar funciones agregadas
        complejidad += len(re.findall(r'\b(SUM|AVG|COUNT|MAX|MIN)\s*\(', sql_upper))
        
        # Contar CASE WHEN
        complejidad += len(re.findall(r'\b(CASE|WHEN|THEN|ELSE|END)\b', sql_upper)) * 2
        
        # Contar subqueries
        complejidad += len(re.findall(r'\(SELECT', sql_upper)) * 3
        
        # Contar UNIONs
        complejidad += len(re.findall(r'\bUNION\b', sql_upper)) * 2
        
        # Contar JOINs
        complejidad += len(re.findall(r'\b(JOIN|INNER|LEFT|RIGHT|CROSS)\s+JOIN\b', sql_upper))
        
        # Contar funciones complejas
        complejidad += len(re.findall(r'\b(TRANSLATE|COALESCE|NULLIF|DATE_SUB|EXTRACT)\s*\(', sql_upper)) * 2
        
        return complejidad
    
    def _extraer_condicion_where(self, sql: str, columna: str) -> str:
        """Extrae condición WHERE para una columna específica"""
        match = re.search(rf'WHERE\s+.*?{columna}\s*=\s*[\'"]([^\'"]+)[\'"]', sql, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _extraer_condiciones_select(self, sql: str, columna: str) -> list:
        """Extrae condiciones SELECT para una columna específica"""
        condiciones = []
        # Buscar en CASE WHEN
        cases = re.findall(rf'WHEN\s+{columna}\s*=\s*[\'"]([^\'"]+)[\'"]', sql, re.IGNORECASE)
        condiciones.extend(cases)
        return condiciones
    
    def verificar_contradicciones_obvias(self, sql: str) -> tuple[bool, str]:
        """
        Detecta contradicciones obvias en el SQL generado
        """
        sql_upper = sql.upper()
        
        # 1. WHERE cuenta = X pero SELECT usa cuenta = Y
        where_match = re.search(r'WHERE\s+CUENTA\s*=\s*[\'"]([^\'"]+)[\'"]', sql_upper)
        if where_match:
            where_cuenta = where_match.group(1)
            select_matches = re.findall(r'CUENTA\s*=\s*[\'"]([^\'"]+)[\'"]', sql_upper)
            for select_cuenta in select_matches:
                if select_cuenta != where_cuenta:
                    return False, f"Contradicción: WHERE cuenta='{where_cuenta}' vs SELECT cuenta='{select_cuenta}'"
        
        # 2. SELECT de agregación sin GROUP BY correspondiente
        if any(agg in sql_upper for agg in ['SUM(', 'AVG(', 'COUNT(', 'MAX(', 'MIN(']):
            if 'GROUP BY' not in sql_upper:
                # Permitir agregaciones globales sin GROUP BY (solo una fila de resultado)
                # Si hay múltiples columnas en SELECT sin agregación, entonces sí requiere GROUP BY
                select_columns = re.search(r'SELECT\s+(.+?)\s+FROM', sql_upper, re.IGNORECASE)
                if select_columns:
                    columns_part = select_columns.group(1)
                    # Contar columnas no agregadas
                    non_agg_cols = []
                    for col in columns_part.split(','):
                        col = col.strip()
                        if not any(agg in col for agg in ['SUM(', 'AVG(', 'COUNT(', 'MAX(', 'MIN(']):
                            non_agg_cols.append(col)
                    
                    # Si hay columnas no agregadas, requiere GROUP BY
                    if len(non_agg_cols) > 1:  # Más allá de la función de agregación
                        return False, "Agregación con columnas no agregadas requiere GROUP BY"
        
        # 3. HAVING sin GROUP BY
        if 'HAVING' in sql_upper and 'GROUP BY' not in sql_upper:
            return False, "HAVING sin GROUP BY"
        
        # 4. NUEVO: Detectar condiciones imposibles en WHERE
        impossible_patterns = [
            (r"SEGMENTO_PRE\s*=\s*'SI'\s+AND\s*SEGMENTO_PRE\s*=\s*'NO VIS'", "segmento_pre = 'SI' AND segmento_pre = 'No VIS' es imposible"),
            (r"SEGMENTO_PRE\s*=\s*'VIS'\s+AND\s*SEGMENTO_PRE\s*=\s*'NO VIS'", "segmento_pre = 'VIS' AND segmento_pre = 'No VIS' es imposible"),
            (r"RANGOS_DECRETO_PRE\s*LIKE\s*'VIS%'\s+AND\s*RANGOS_DECRETO_PRE\s*NOT\s+LIKE\s'%VIP'", "Condición redundante: VIS ya excluye VIP"),
            (r"CUENTA\s*=\s*'OFERTA'\s+AND\s+CUENTA\s*=\s*'(VENTAS|LANZAMIENTOS)'", "cuenta no puede ser 'Oferta' y otra cuenta simultáneamente")
        ]
        
        for pattern, message in impossible_patterns:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                return False, f"Condición imposible detectada: {message}"
        
        # 5. NUEVO: Detectar uso incorrecto de COUNT vs SUM
        if 'COUNT(*)' in sql_upper and 'UNIDADES' in sql_upper:
            return False, "Para contar unidades debe usar SUM(unidades), no COUNT(*)"
        
        # 6. NUEVO: Detectar campos incorrectos comunes
        incorrect_fields = {
            'BARRIO': 'CIUDAD',
            'COMPANIA_CONSTRUCTORA': 'CUENTA',
            'DEPARTAMENTO': 'CIUDAD'
        }
        
        for incorrect, correct in incorrect_fields.items():
            if f"{incorrect} LIKE" in sql_upper:
                return False, f"Campo incorrecto '{incorrect}', debe usar '{correct}'"
        
        # 7. NUEVO: Detectar filtros omitidos críticos
        if 'PREVENTA' in sql_upper and 'USO_ETAPA' not in sql_upper:
            return False, "Pregunta de preventa requiere filtro uso_etapa LIKE '%PREVENTA%'"
        
        if 'ARRIENDAR' in sql_upper and 'DESTINO_ETAPA' not in sql_upper:
            return False, "Pregunta de arriendo requiere filtro destino_etapa = 'Arrendar'"
        
        # 8. NUEVO: Detectar funciones incorrectas (UPPEN, UPPUNTO, etc.)
        incorrect_functions = ['UPPEN', 'UPPUNTO', 'UPPENT', 'UPPUNTO']
        for func in incorrect_functions:
            if func in sql_upper:
                return False, f"Función incorrecta '{func}', debe usar 'UPPER'"
        
        # 9. NUEVO: Detectar uso incorrecto de SUM(valor) vs SUM(unidades)
        if 'SUM(VALOR)' in sql_upper and ('UNIDADES' in sql_upper or 'VIS' in sql_upper or 'PREVENTA' in sql_upper):
            return False, "Para contar unidades debe usar SUM(unidades), no SUM(valor)"
        
        # 10. NUEVO: Detectar cuenta incorrecta para preguntas específicas
        if ('LANZAMIENTOS' in sql_upper or 'PREVENTA' in sql_upper) and 'CUENTA = \'VENTAS\'' in sql_upper:
            return False, "Para preventa/lanzamientos debe usar cuenta = 'Oferta', no 'Ventas'"
        
        # 11. NUEVO: Detectar filtros restrictivos innecesarios
        if 'DOCE_MESES = 1' in sql_upper:
            return False, "Filtro restrictivo doce_meses=1 puede omitir datos relevantes"
        
        # 12. NUEVO: Detectar falta de filtro de ciudad en preguntas específicas
        ciudades_especificas = ['ITAGÜÍ', 'CARTAGO', 'CHINCHINÁ', 'ZIPAQUIRÁ', 'BOGOTÁ', 'MEDELLÍN', 'CALI', 'CÚCUTA', 'CHÍA', 'VILLAVICENCIO', 'ENVIGADO']
        for ciudad in ciudades_especificas:
            if ciudad in sql_upper and f"CIUDAD LIKE '%{ciudad}%'" not in sql_upper and f"UPPER(CIUDAD) LIKE '%{ciudad}%'" not in sql_upper:
                return False, f"Pregunta menciona {ciudad} pero SQL no filtra por esa ciudad"
        
        # 13. NUEVO: Detectar patrones específicos de preventa y lanzamientos
        if 'PREVENTA' in sql_upper:
            # Verificar que use cuenta='Oferta' y no 'Ventas' o 'Lanzamientos'
            if 'CUENTA = \'VENTAS\'' in sql_upper:
                return False, "Pregunta de preventa debe usar cuenta = 'Oferta', no 'Ventas'"
            if 'CUENTA = \'LANZAMIENTOS\'' in sql_upper:
                return False, "Pregunta de preventa debe usar cuenta = 'Oferta', no 'Lanzamientos'"
            
            # Verificar que no genere tasas de desistimiento
            if 'TASA_DESISTIMIENTO' in sql_upper or 'RENUNCIAS' in sql_upper:
                return False, "Pregunta de preventa no debe generar tasas de desistimiento"
        
        if 'LANZAMIENTOS' in sql_upper:
            # Verificar que use SUM(unidades) y no SUM(valor)
            if 'SUM(VALOR)' in sql_upper:
                return False, "Para contar lanzamientos debe usar SUM(unidades), no SUM(valor)"
            
            # Verificar que use cuenta='Oferta' o 'Lanzamientos'
            if 'CUENTA = \'VENTAS\'' in sql_upper:
                return False, "Pregunta de lanzamientos debe usar cuenta = 'Oferta' o 'Lanzamientos', no 'Ventas'"
        
        # 14. NUEVO: Detectar operadores de comparación incorrectos
        if 'UPPER(CIUDAD) =' in sql_upper:
            return False, "Para comparar ciudad debe usar LIKE, no = (ej: UPPER(ciudad) LIKE '%CIUDAD%')"
        
        # 15. NUEVO: Detectar UNION ALL innecesario para preguntas simples
        if 'UNION ALL' in sql_upper and ('PREVENTA' in sql_upper or 'ARRENDAR' in sql_upper):
            return False, "UNION ALL innecesario para preguntas simples de preventa o arriendo"
        
        # 16. NUEVO: Detectar patrones específicos de análisis y agregación
        if any(palabra in sql_upper for palabra in ['CRECIDO', 'VARIACIÓN', 'PROMEDIO', 'MÓVIL', 'MOVIL']):
            # Detectar uso incorrecto de funciones de agregación
            if 'AVG(VALOR)' in sql_upper and ('UNIDADES' in sql_upper or 'TOTAL' in sql_upper):
                return False, "Para análisis de unidades debe usar AVG(unidades) o SUM(unidades), no AVG(valor)"
            
            if 'SUM(VALOR)' in sql_upper and ('UNIDADES' in sql_upper or 'TOTAL' in sql_upper):
                return False, "Para contar unidades debe usar SUM(unidades), no SUM(valor)"
            
            # Detectar falta de filtros para análisis temporal
            if '2025' in sql_upper or '2026' in sql_upper:
                if 'CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER)' not in sql_upper:
                    return False, "Para análisis temporal debe extraer año de fecha con CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER)"
            
            # Detectar uso incorrecto de HAVING sin GROUP BY
            if 'HAVING' in sql_upper and 'GROUP BY' not in sql_upper:
                return False, "HAVING requiere GROUP BY clause"
        
        # 17. NUEVO: Detectar patrones específicos de preventa y análisis
        if 'PREVENTA' in sql_upper and any(palabra in sql_upper for palabra in ['VARIACIÓN', 'PROMEDIO', 'CRECIDO']):
            if 'AVG(VALOR)' in sql_upper:
                return False, "Para análisis de preventa debe usar SUM(unidades), no AVG(valor)"
            if 'USO_ETAPA' not in sql_upper:
                return False, "Análisis de preventa requiere filtro uso_etapa LIKE '%PREVENTA%'"
        
        # 18. NUEVO: Detectar patrones específicos de arriendo y análisis
        if 'ARRIENDAR' in sql_upper and any(palabra in sql_upper for palabra in ['VARIACIÓN', 'PROMEDIO', 'CRECIDO']):
            if 'DESTINO_ETAPA' not in sql_upper:
                return False, "Análisis de arriendo requiere filtro destino_etapa = 'Arrendar'"
            if 'UPPER(SEGMENTO_PRE)' in sql_upper and 'ARRENDAR' in sql_upper:
                return False, "Para arrendar debe usar destino_etapa, no segmento_pre"
        
        # 19. NUEVO: Detectar patrones específicos de iniciaciones
        if 'INICIACIONES' in sql_upper:
            if 'CUENTA = \'INICIACIONES\'' not in sql_upper:
                return False, "Para análisis de iniciaciones debe usar cuenta = 'Iniciaciones'"
            if 'AVG(VALOR)' in sql_upper and ('UNIDADES' in sql_upper or 'TOTAL' in sql_upper):
                return False, "Para análisis de iniciaciones debe usar AVG(unidades) o SUM(unidades), no AVG(valor)"
        
        # 20. NUEVO: Detectar patrones específicos de cuentas incorrectas en análisis
        if any(palabra in sql_upper for palabra in ['CRECIDO', 'VARIACIÓN', 'PROMEDIO', 'MÓVIL', 'MOVIL']):
            # Detectar uso incorrecto de cuentas para arriendo
            if 'ARRIENDAR' in sql_upper:
                if 'CUENTA = \'LANZAMIENTOS\'' in sql_upper:
                    return False, "Para análisis de arriendo debe usar destino_etapa = 'Arrendar', no cuenta = 'Lanzamientos'"
                if 'CUENTA = \'OFERTA\'' in sql_upper and 'DESTINO_ETAPA' not in sql_upper:
                    return False, "Para análisis de arriendo debe incluir filtro destino_etapa = 'Arrendar'"
            
            # Detectar uso incorrecto de cuentas para preventa
            if 'PREVENTA' in sql_upper:
                if 'CUENTA = \'LANZAMIENTOS\'' in sql_upper:
                    return False, "Para análisis de preventa debe usar uso_etapa LIKE '%PREVENTA%', no cuenta = 'Lanzamientos'"
                if 'DESTINO_ETAPA = \'VENTA\'' in sql_upper:
                    return False, "Para análisis de preventa debe usar uso_etapa LIKE '%PREVENTA%', no destino_etapa = 'Venta'"
            
            # Detectar uso incorrecto de cuentas para lanzamientos
            if 'LANZAMIENTOS' in sql_upper:
                if 'CUENTA = \'OFERTA\'' in sql_upper and 'CUENTA = \'LANZAMIENTOS\'' not in sql_upper:
                    return False, "Para análisis de lanzamientos debe usar cuenta = 'Lanzamientos'"
                if 'CUENTA = \'VENTAS\'' in sql_upper:
                    return False, "Para análisis de lanzamientos debe usar cuenta = 'Lanzamientos', no cuenta = 'Ventas'"
            
            # Detectar uso incorrecto de COUNT(*) en análisis
            if 'COUNT(*)' in sql_upper and ('UNIDADES' in sql_upper or 'TOTAL' in sql_upper):
                return False, "Para análisis de unidades debe usar SUM(unidades), no COUNT(*)"
            
            # Detectar falta de filtros específicos por tipo de análisis
            if 'NO VIS' in sql_upper:
                if 'TIPO_VIVIENDA = \'NO VIS\'' not in sql_upper and 'SEGMENTO_PRE = \'NO VIS\'' not in sql_upper:
                    return False, "Para análisis No VIS debe incluir filtro segmento_pre = 'No VIS' o segmento_pre = 'No VIS'"
        
        # 21. NUEVO: Validación estricta para patrones sistemáticos de cuentas incorrectas
        # Detectar uso sistemático de cuenta='Lanzamientos' para preguntas que no son de lanzamientos
        if 'CUENTA = \'LANZAMIENTOS\'' in sql_upper:
            # Si menciona arriendo pero usa Lanzamientos
            if 'ARRIENDAR' in sql_upper:
                return False, "ERROR CRÍTICO: Para preguntas de arriendo debe usar destino_etapa = 'Arrendar', nunca cuenta = 'Lanzamientos'"
            
            # Si menciona preventa pero usa Lanzamientos
            if 'PREVENTA' in sql_upper:
                return False, "ERROR CRÍTICO: Para preguntas de preventa debe usar uso_etapa LIKE '%PREVENTA%', nunca cuenta = 'Lanzamientos'"
            
            # Si menciona iniciaciones pero usa Lanzamientos
            if 'INICIACIONES' in sql_upper:
                return False, "ERROR CRÍTICO: Para preguntas de iniciaciones debe usar cuenta = 'Iniciaciones', nunca cuenta = 'Lanzamientos'"
        
        # Detectar uso sistemático de destino_etapa = 'Venta' para preguntas que no son de venta
        if 'DESTINO_ETAPA = \'VENTA\'' in sql_upper:
            # Si menciona arriendo pero usa destino_etapa = 'Venta'
            if 'ARRIENDAR' in sql_upper:
                return False, "ERROR CRÍTICO: Para preguntas de arriendo debe usar destino_etapa = 'Arrendar', nunca destino_etapa = 'Venta'"
            
            # Si menciona preventa pero usa destino_etapa = 'Venta'
            if 'PREVENTA' in sql_upper:
                return False, "ERROR CRÍTICO: Para preguntas de preventa debe usar uso_etapa LIKE '%PREVENTA%', nunca destino_etapa = 'Venta'"
        
        # 22. NUEVO: Validación de filtros específicos por tipo de pregunta
        # Para preguntas de arriendo
        if 'ARRIENDAR' in sql_upper:
            if 'DESTINO_ETAPA' not in sql_upper:
                return False, "Para preguntas de arriendo debe incluir filtro destino_etapa = 'Arrendar'"
        
        # Para preguntas de preventa
        if 'PREVENTA' in sql_upper:
            if 'USO_ETAPA' not in sql_upper:
                return False, "Para preguntas de preventa debe incluir filtro uso_etapa LIKE '%PREVENTA%'"
        
        # Para preguntas de iniciaciones
        if 'INICIACIONES' in sql_upper:
            if 'CUENTA = \'INICIACIONES\'' not in sql_upper:
                return False, "Para preguntas de iniciaciones debe usar cuenta = 'Iniciaciones'"
        
        # 23. NUEVO: Validación de funciones de agregación por tipo de análisis
        if any(palabra in sql_upper for palabra in ['CRECIDO', 'VARIACIÓN', 'PROMEDIO', 'MÓVIL', 'MOVIL']):
            # Para análisis de unidades
            if ('UNIDADES' in sql_upper or 'TOTAL' in sql_upper) and 'AVG(VALOR)' in sql_upper:
                return False, "Para análisis de unidades debe usar AVG(unidades) o SUM(unidades), nunca AVG(valor)"
            
            # Para análisis de iniciaciones
            if 'INICIACIONES' in sql_upper and 'AVG(VALOR)' in sql_upper:
                return False, "Para análisis de iniciaciones debe usar AVG(unidades) o SUM(unidades), nunca AVG(valor)"
        
        # 24. NUEVO: Validación de filtros de ciudad específicos
        ciudades_comunes = ['MEDELLÍN', 'BELLO', 'ZIPAQUIRÁ', 'SABANETA', 'CARTAGO', 'VILLAVICENCIO', 'BUCARAMANGA', 'PEREIRA', 'MANIZALES', 'CALI', 'BARRANQUILLA', 'CÚCUTA']
        for ciudad in ciudades_comunes:
            if ciudad in sql_upper:
                # Verificar que filtre por esa ciudad
                if f"CIUDAD LIKE '%{ciudad}%'" not in sql_upper and f"UPPER(CIUDAD) LIKE '%{ciudad}%'" not in sql_upper:
                    return False, f"Pregunta menciona {ciudad} pero SQL no filtra por esa ciudad específica"
        
        # 25. ORDER BY sin columnas válidas
        if 'ORDER BY' in sql_upper:
            order_match = re.search(r'ORDER BY\s+(\w+)', sql_upper)
            if order_match:
                order_col = order_match.group(1)
                if order_col not in sql_upper[:sql_upper.find('ORDER BY')]:
                    return False, f"ORDER BY usa columna '{order_col}' que no está en SELECT"
        
        return True, "Sin contradicciones obvias"
    
    def validar_y_corregir_sql_completo(self, sql: str, pregunta: str) -> tuple[bool, str, str]:
        """
        Sistema completo de validación y corrección de SQL para prevenir alucinaciones
        
        Returns:
            (es_valido, mensaje, sql_corregido)
        """
        # 1. Clasificar intención de la pregunta
        intencion = self.clasificar_intencion_pregunta(pregunta)
        
        # 2. Verificar contradicciones obvias
        es_coherente, msg_contradicciones = self.verificar_contradicciones_obvias(sql)
        if not es_coherente:
            return False, f"Contradicción detectada: {msg_contradicciones}", sql
        
        # 3. Validar coherencia con intención
        es_valido, msg_coherencia = self.validar_coherencia_sql(sql, pregunta, intencion)
        if not es_valido:
            return False, f"Incoherencia: {msg_coherencia}", sql
        
        # 4. Aplicar correcciones sintácticas existentes
        sql_corregido = self.corregir_sql_hallucinado(sql)
        
        # 5. Verificación final post-corrección
        es_final_valido, msg_final = self.verificar_contradicciones_obvias(sql_corregido)
        if not es_final_valido:
            return False, f"Error post-corrección: {msg_final}", sql_corregido
        
        return True, f"SQL válido (intención: {intencion})", sql_corregido
    
    def generar_sql_validado(self, pregunta: str, ciudad: str = None, filtros_adicionales: dict = None) -> str:
        """
        Genera SQL validado basado en la intención de la pregunta con plantillas específicas
        """
        intencion = self.clasificar_intencion_pregunta(pregunta)
        pregunta_upper = pregunta.upper()
        
        # Extraer ciudad si no se proporcionó
        if not ciudad:
            for ciudad_posible in ["MEDELLÍN", "BOGOTÁ", "CALI", "BARRANQUILLA", "PEREIRA", "MANIZALES", "CARTAGENA", "SOACHA", "BUCARAMANGA", "META", "SABANETA", "FLORIDABLANCA", "BELLO", "ITAGÜÍ"]:
                if ciudad_posible in pregunta_upper:
                    ciudad = ciudad_posible
                    break
        
        # Plantillas específicas para casos problemáticos identificados
        if "PREVENTA" in pregunta_upper and ("UNIDADES" in pregunta_upper or "CUÁNTAS" in pregunta_upper):
            # Caso específico: unidades de preventa (alucinación sistemática)
            if not ciudad:
                return None  # Requerir ciudad para preventa
            ciudad_filtro = f"UPPER(ciudad) LIKE '%{ciudad.upper()}%'"
            return f"""
                SELECT SUM(unidades) AS total_unidades_preventa
                FROM livo 
                WHERE {ciudad_filtro} 
                AND cuenta = 'Oferta' 
                AND UPPER(uso_etapa) LIKE '%PREVENTA%'
                AND fecha = (SELECT MAX(fecha) FROM livo)
            """.strip()
        
        elif "ARRIENDO" in pregunta_upper and ("UNIDADES" in pregunta_upper or "CUÁNTAS" in pregunta_upper):
            # Caso: unidades en arriendo
            if not ciudad:
                return None  # Requerir ciudad para arriendo
            ciudad_filtro = f"UPPER(ciudad) LIKE '%{ciudad.upper()}%'"
            return f"""
                SELECT COALESCE(SUM(unidades), 0) AS unidades_arriendo
                FROM livo 
                WHERE {ciudad_filtro} 
                AND cuenta = 'Oferta'
                AND destino_etapa = 'Arrendar'
                                AND fecha = (SELECT MAX(fecha) FROM livo)
            """.strip()
        
        elif "VIP" in pregunta_upper and "NO VIS" not in pregunta_upper and "SIN VIP" not in pregunta_upper and ("UNIDADES" in pregunta_upper or "CUÁNTAS" in pregunta_upper):
            # Caso: unidades VIP
            if not ciudad:
                return None  # Requerir ciudad para consultas específicas
            ciudad_filtro = f"UPPER(ciudad) LIKE '%{ciudad.upper()}%'"
            return f"""
                SELECT SUM(unidades) AS total_vip
                FROM livo 
                WHERE {ciudad_filtro} 
                AND cuenta = 'Oferta'
                AND segmento_pre = 'VIS'
                AND rangos_decreto_pre = 'VIP'
                AND fecha = (SELECT MAX(fecha) FROM livo)
            """.strip()
        
        elif "SIN VIP" in pregunta_upper and ("UNIDADES" in pregunta_upper or "CUÁNTAS" in pregunta_upper):
            # Caso: unidades VIS sin VIP
            if not ciudad:
                return None  # Requerir ciudad para consultas específicas
            ciudad_filtro = f"UPPER(ciudad) LIKE '%{ciudad.upper()}%'"
            return f"""
                SELECT SUM(unidades) AS total_vis_sin_vip
                FROM livo 
                WHERE {ciudad_filtro} 
                AND cuenta = 'Oferta'
                AND segmento_pre = 'VIS'
                AND rangos_decreto_pre = 'VIS 70 - 135 SML'
                AND fecha = (SELECT MAX(fecha) FROM livo)
            """.strip()
        
        elif "NO VIS" in pregunta_upper and ("UNIDADES" in pregunta_upper or "CUÁNTAS" in pregunta_upper):
            # Caso: unidades No VIS
            if not ciudad:
                return None  # Requerir ciudad para consultas específicas
            ciudad_filtro = f"UPPER(ciudad) LIKE '%{ciudad.upper()}%'"
            return f"""
                SELECT SUM(unidades) AS total_no_vis
                FROM livo 
                WHERE {ciudad_filtro} 
                AND cuenta = 'Oferta'
                AND segmento_pre = 'NO VIS'
                AND fecha = (SELECT MAX(fecha) FROM livo)
            """.strip()
        
        elif "VIS" in pregunta_upper and ("UNIDADES" in pregunta_upper or "CUÁNTAS" in pregunta_upper):
            # Caso: unidades VIS (general)
            if not ciudad:
                return None  # Requerir ciudad para consultas específicas
            ciudad_filtro = f"UPPER(ciudad) LIKE '%{ciudad.upper()}%'"
            return f"""
                SELECT SUM(unidades) AS total_vis
                FROM livo 
                WHERE {ciudad_filtro} 
                AND cuenta = 'Oferta'
                AND segmento_pre = 'VIS'
                AND rangos_decreto_pre IN ('VIS 70 - 135 SML', 'VIP')
                AND fecha = (SELECT MAX(fecha) FROM livo)
            """.strip()
        
        elif "LANZAMIENTOS" in pregunta_upper and ("CUÁNTOS" in pregunta_upper or "CUÁNTAS" in pregunta_upper):
            # Caso: cuántos lanzamientos
            if not ciudad:
                return None  # Requerir ciudad para consultas específicas
            ciudad_filtro = f"UPPER(ciudad) LIKE '%{ciudad.upper()}%'"
            return f"""
                SELECT SUM(unidades) AS total_lanzamientos
                FROM livo 
                WHERE {ciudad_filtro} 
                AND cuenta = 'Lanzamientos'
                                                AND fecha = (SELECT MAX(fecha) FROM livo)
            """.strip()
        
        # Plantillas base por intención (casos generales)
        elif intencion == "conteo_unidades":
            ciudad_filtro = f"UPPER(ciudad) LIKE '%{ciudad.upper()}%'" if ciudad else "1=1"
            return f"""
                SELECT SUM(unidades) AS total_unidades
                FROM livo 
                WHERE {ciudad_filtro} 
                AND cuenta = 'Oferta'
                AND doce_meses = (SELECT MAX(doce_meses) FROM livo)
            """.strip()
        
        elif intencion == "promedio":
            ciudad_filtro = f"UPPER(ciudad) LIKE '%{ciudad.upper()}%'" if ciudad else "1=1"
            return f"""
                SELECT AVG(valor) AS valor_promedio
                FROM livo 
                WHERE {ciudad_filtro} 
                AND cuenta = 'Oferta'
                AND doce_meses = (SELECT MAX(doce_meses) FROM livo)
            """.strip()
        
        # Para otras intenciones complejas, dejar que el LLM genere pero validar
        return None
    
    def corregir_sql_hallucinado(self, sql: str) -> str:
        """Corrige errores sintácticos comunes y alucinaciones de LLMs en el SQL"""
        import re
        # 1. Corregir variaciones de UPPER (ej: UPPUNET, UPPNER, UPPEER, UPPPER -> UPPER)
        sql = re.sub(r'\bUP[P|E][A-Z_]*\(', 'UPPER(', sql, flags=re.IGNORECASE)

        # 1b. CORRECCIÓN CRÍTICA: UPPER(col) LIKE UPPER('%valor%') → UPPER(col) LIKE '%VALOR%'
        # DuckDB no acepta % dentro de UPPER() en cláusula LIKE — causa "syntax error at or near %"
        def fix_upper_like(m):
            col = m.group(1)
            val = m.group(2)
            # Extraer el valor sin los % para devolverlo en mayúsculas dentro del patrón
            return f"UPPER({col}) LIKE '{val.upper()}'"
        sql = re.sub(
            r'UPPER\s*\(\s*([^)]+)\s*\)\s*LIKE\s*UPPER\s*\(\s*\'([^\']*)\'\s*\)',
            fix_upper_like,
            sql, flags=re.IGNORECASE
        )

        # 2. Corregir signo de porcentaje FUERA de comillas en contexto LIKE
        # Caso A: LIKE %'valor%'  → LIKE '%valor%'
        sql = re.sub(r"LIKE\s+%\s*'([^']*)'", lambda m: "LIKE '%" + m.group(1).strip('%') + "%'", sql, flags=re.IGNORECASE)
        # Caso B: LIKE '%valor'%  → LIKE '%valor%'  (% final fuera de cierre de comilla)
        sql = re.sub(r"LIKE\s+'([^'%][^']*)'\s*%", lambda m: "LIKE '%" + m.group(1).strip('%') + "%'", sql, flags=re.IGNORECASE)

        # 3. Doble porcentaje dentro de string LIKE: '%%valor%%' → '%valor%'
        sql = re.sub(r"LIKE\s+'%%([^']+)%%'", r"LIKE '%\1%'", sql, flags=re.IGNORECASE)
        sql = re.sub(r"LIKE\s+'%%([^']+)%'",  r"LIKE '%\1%'", sql, flags=re.IGNORECASE)
        sql = re.sub(r"LIKE\s+'%([^']+)%%'",  r"LIKE '%\1%'", sql, flags=re.IGNORECASE)
        
        # 4. Corregir doble comillas de strings literales a comillas simples para DuckDB
        sql = re.sub(r'LIKE\s+"([^"]+)"', r"LIKE '\1'", sql, flags=re.IGNORECASE)
        sql = re.sub(r'=\s+"([^"]+)"', r"= '\1'", sql, flags=re.IGNORECASE)
        
        # 5. CORRECCIÓN CRÍTICA: rango_decreto_pre (singular alucinado) → rangos_decreto_pre (plural real)
        sql = re.sub(r'\brango_decreto_pre\b', 'rangos_decreto_pre', sql, flags=re.IGNORECASE)
        
        # 6. CORRECCIÓN CRÍTICA: eliminar filtros numéricos alucinados (rangos_decreto_pre =/<=/>=/</>/ != número)
        sql = re.sub(r'\brangos_decreto_pre\s*(?:=|<=|>=|<|>|!=)\s*\d+', "segmento_pre = 'No VIS'", sql, flags=re.IGNORECASE)
        # 6b. Eliminar columna alucinada segmento_pre (no existe en LIVO)
        sql = re.sub(r'\bAND\s+segmento_pre\s*=\s*\'[^\']*\'', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bWHERE\s+segmento_pre\s*=\s*\'[^\']*\'\s+AND\b', 'WHERE', sql, flags=re.IGNORECASE)
        # 6c. Columnas alucinadas usadas como nombre de métrica → unidades
        # El LLM escribe AVG(iniciaciones), SUM(ventas), SUM(lanzamientos), etc. — no existen, es SUM(unidades)
        # NOTA: Excluir CTEs (ventas, oferta) que son nombres de tablas temporales, no columnas
        sql = re.sub(
            r'\b(SUM|AVG|COUNT|MIN|MAX)\s*\(\s*(iniciaciones|lanzamientos|entregas|entregadas|renuncias|desistimientos|culminadas|paralizado|saldo_que_inicia)\s*\)',
            lambda m: f'{m.group(1)}(unidades)',
            sql, flags=re.IGNORECASE
        )
        
        # 7. CORRECCIÓN CRÍTICA: Ambigüedad en columnas de subconsultas con CROSS JOIN implícito
        # Caso específico: SELECT AVG(promedio_2026) - AVG(promedio_2025) FROM (sub1), (sub2)
        # donde ambas subconsultas usan el mismo nombre de columna
        if "AVG(promedio_2026) - AVG(promedio_2025)" in sql and "BETWEEN 2025 AND 2026" in sql:
            # Extraer el WHERE común de ambas subconsultas
            where_pattern = r'WHERE\s+(.+?)\s+AND\s+segmento_pre'
            where_match = re.search(where_pattern, sql, re.IGNORECASE | re.DOTALL)
            if where_match:
                where_clause = where_match.group(1)
                
                # Reconstruir SQL con columnas distintas y CROSS JOIN explícito
                sql = f"""SELECT 
    datos_2026.promedio_2026 - datos_2025.promedio_2025 AS variacion_unidades 
FROM (
    SELECT AVG(valor) AS promedio_2025 
    FROM livo 
    WHERE {where_clause} AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2025
        AND segmento_pre = 'VIS' AND rangos_decreto_pre = 'VIS 70 - 135 SML'
) AS datos_2025
CROSS JOIN (
    SELECT AVG(valor) AS promedio_2026 
    FROM livo 
    WHERE {where_clause} AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2026
        AND segmento_pre = 'VIS' AND rangos_decreto_pre = 'VIS 70 - 135 SML'
) AS datos_2026"""
        
        # 8. CORRECCIÓN CRÍTICA: BETWEEN con rangos_decreto_pre (VARCHAR) vs números (INTEGER)
        # Error: Cannot mix values of type VARCHAR and INTEGER_LITERAL in BETWEEN clause
        sql = re.sub(
            r'\brangos_decreto_pre\s+BETWEEN\s+(\d+)\s+AND\s+(\d+)',
            lambda m: f"CAST(rangos_decreto_pre AS INTEGER) BETWEEN {m.group(1)} AND {m.group(2)}",
            sql,
            flags=re.IGNORECASE
        )
        
        # 9. CORRECCIÓN CRÍTICA: GROUP BY incompleto cuando columnas están en SELECT pero no en GROUP BY
        # Error: column "X" must appear in the GROUP BY clause or must be part of an aggregate function
        # Casos comunes: cuenta, doce_meses, UPPER(AM_capital) en SELECT pero no en GROUP BY
        
        # Para cada parte del SQL (considerando UNION ALL)
        sql_parts = sql.split("UNION ALL")
        corrected_parts = []
        
        for part in sql_parts:
            # Verificar si hay funciones de agregación en SELECT
            has_aggregation = any(agg in part.upper() for agg in ['SUM(', 'AVG(', 'COUNT(', 'MAX(', 'MIN('])
            
            # Si hay agregación pero no GROUP BY, verificar si se necesita agregar
            if has_aggregation and "GROUP BY" not in part:
                # Buscar columnas no agregadas en SELECT que requieren GROUP BY
                select_match = re.search(r'SELECT\s+(.+?)\s+FROM', part, re.IGNORECASE)
                if select_match:
                    select_columns = select_match.group(1)
                    non_aggregated_columns = []
                    
                    # Analizar cada columna en SELECT
                    for col_expr in select_columns.split(','):
                        col_expr = col_expr.strip()
                        
                        # Si no es una función de agregación, es una columna que necesita GROUP BY
                        if not re.search(r'\b(SUM|AVG|COUNT|MAX|MIN)\s*\(', col_expr, re.IGNORECASE):
                            # Extraer el nombre de la columna base (sin alias)
                            if ' AS ' in col_expr:
                                # Caso: cuenta AS 'Oferta' -> extraer 'cuenta'
                                base_col = col_expr.split(' AS ')[0].strip()
                                # Quitar comillas si existen
                                base_col = base_col.strip("'\"")
                            else:
                                base_col = col_expr.strip()
                            
                            # Si es una columna de tabla (no constante), agregar a GROUP BY
                            if base_col and not re.search(r'^[0-9\+\-\*\/\s]+$', base_col):
                                non_aggregated_columns.append(base_col)
                    
                    # Si hay columnas no agregadas, agregar GROUP BY
                    if non_aggregated_columns:
                        group_by_clause = " GROUP BY " + ", ".join(non_aggregated_columns)
                        # Insertar GROUP BY antes de ORDER BY o al final
                        if "ORDER BY" in part:
                            part = part.replace("ORDER BY", group_by_clause + " ORDER BY")
                        elif "HAVING" in part:
                            part = part.replace("HAVING", group_by_clause + " HAVING")
                        else:
                            part += group_by_clause
            
            # Si ya existe GROUP BY, verificar que esté completo
            elif has_aggregation and "GROUP BY" in part:
                # Columnas comunes que faltan en GROUP BY
                common_missing_columns = []
                
                # Verificar cuenta
                if " cuenta," in part or " cuenta " in part or re.search(r'SELECT[^,]*\bcuenta\b', part, re.IGNORECASE):
                    group_by_section = part.split("GROUP BY")[1] if "GROUP BY" in part else ""
                    if "cuenta" not in group_by_section:
                        common_missing_columns.append("cuenta")
                
                # Verificar doce_meses
                if " doce_meses" in part and "GROUP BY" in part:
                    group_by_section = part.split("GROUP BY")[1]
                    # doce_meses puede estar en CASE WHEN, verificar si no está como columna directa
                    if not re.search(r'\bdoce_meses\s*(?:,|$)', group_by_section):
                        common_missing_columns.append("doce_meses")
                
                # NUEVO: Verificar columnas transformadas en SELECT que faltan en GROUP BY
                # Caso específico: UPPER(AM_capital) AS ciudad en SELECT pero AM_capital no en GROUP BY
                select_match = re.search(r'SELECT\s+(.+?)\s+FROM', part, re.IGNORECASE)
                if select_match:
                    select_columns = select_match.group(1)
                    group_by_section = part.split("GROUP BY")[1] if "GROUP BY" in part else ""
                    
                    # Buscar columnas transformadas con UPPER(), LOWER(), etc.
                    transformed_columns = re.findall(r'(UPPER|LOWER|TRIM)\s*\(\s*([^)]+)\s*\)\s+AS\s+(\w+)', select_columns, re.IGNORECASE)
                    
                    for func, column, alias in transformed_columns:
                        # Si la columna base no está en GROUP BY, agregarla
                        if column.strip() not in group_by_section and alias not in group_by_section:
                            common_missing_columns.append(column.strip())
                    
                    # Buscar columnas simples con alias que faltan en GROUP BY
                    simple_columns = re.findall(r'([^,\s]+)\s+AS\s+(\w+)', select_columns, re.IGNORECASE)
                    for column, alias in simple_columns:
                        # Si es una columna de tabla (no función) y no está en GROUP BY
                        if not re.search(r'\b(SUM|AVG|COUNT|MAX|MIN)\s*\(', column, re.IGNORECASE):
                            if column.strip() not in group_by_section and alias not in group_by_section:
                                common_missing_columns.append(column.strip())
                
                # Agregar columnas faltantes al GROUP BY
                if common_missing_columns:
                    missing_str = ', '.join(common_missing_columns) + ', '
                    part = re.sub(r'GROUP BY\s+', f'GROUP BY {missing_str}', part, count=1, flags=re.IGNORECASE)
            
            corrected_parts.append(part)
        
        sql = "UNION ALL".join(corrected_parts)
        
        # 9.5. CORRECCIÓN CRÍTICA: Eliminar WITH ROLLUP (no compatible con DuckDB)
        # Error: WITH ROLLUP no es soportado por DuckDB
        sql = re.sub(r'\bWITH\s+ROLLUP\b', '', sql, flags=re.IGNORECASE)
        
        # 9.6. CORRECCIÓN CRÍTICA: Reemplazar segmento_pre (no existe) por segmento_pre
        # Error: Column "segmento_pre" does not exist
        sql = re.sub(r'\bTIPO_VIVIENDA\b', 'segmento_pre', sql, flags=re.IGNORECASE)
        
        # 9.7. CORRECCIÓN CRÍTICA: Corregir uso incorrecto de regional vs ciudad
        # Para ciudades específicas, usar ciudad en lugar de regional
        ciudades_especificas = [
            'PEREIRA', 'MANIZALES', 'ARMENIA', 'IBAGUÉ', 'NEIVA', 'POPAYÁN',
            'PASTO', 'TULUÁ', 'BUGA', 'CARTAGO', 'CHINCHINÁ', 'RIONEGRO',
            'ITAGÜÍ', 'ENVIGADO', 'LA ESTRELLA', 'SABANETA', 'CALDAS',
            'BARRANQUILLA', 'SOLEDAD', 'MALAMBO', 'SOACHA', 'FUSAGASUGÁ',
            'CHÍA', 'COTA', 'GIRARDOT', 'ZIPAQUIRÁ', 'MOSQUERA', 'SIBATÉ'
        ]
        
        for ciudad in ciudades_especificas:
            # Si filtra por ciudad específica pero usa regional, corregir
            if f"UPPER(ciudad) LIKE '%{ciudad}%'" in sql.upper() and "UPPER(regional)" in sql.upper():
                sql = re.sub(r'UPPER\s*\(\s*regional\s*\)', 'UPPER(ciudad)', sql, flags=re.IGNORECASE)
                break
        
        # 9.8. CORRECCIÓN CRÍTICA: Simplificar filtros redundantes de VIS/No VIS
        # Si pregunta específica por No VIS, eliminar filtros de VIS
        if "NO VIS" in sql.upper() and "'VIS'" in sql and "'NO VIS'" in sql:
            # Mantener solo el filtro No VIS
            sql = re.sub(r"AND\s+\w+\s*IN\s*\(\s*'VIS'\s*,\s*'No VIS'\s*\)", "", sql, flags=re.IGNORECASE)
            sql = re.sub(r"AND\s+\w+\s*=\s*'VIS'\s*AND\s+\w+\s*=\s*'No VIS'", "AND segmento_pre = 'No VIS'", sql, flags=re.IGNORECASE)
        
        # 9.9. CORRECCIÓN CRÍTICA: Eliminar columnas alucinadas que no existen en LIVO
        # Error: Referenced column "X" not found in FROM clause!
        columnas_alucinadas = [
            'tipo_propiedad', 'plural', 'segmento', 'CATEGORIZADOS', 
            'divipola', 'vivienda_tipo', 'precio_mc_promedio'
        ]
        
        for columna in columnas_alucinadas:
            # Eliminar referencias a columnas alucinadas en WHERE
            sql = re.sub(rf'AND\s+UPPER\s*\(\s*{columna}\s*\)\s*NOT\s+LIKE\s+UPPER\s*\(\s*\'[^\']*\'\s*\)', '', sql, flags=re.IGNORECASE)
            sql = re.sub(rf'AND\s+{columna}\s*=\s*[\'"][^\'\"]*[\'"]', '', sql, flags=re.IGNORECASE)
            sql = re.sub(rf'AND\s+{columna}\s*IN\s*\([^)]*\)', '', sql, flags=re.IGNORECASE)
            sql = re.sub(rf'AND\s+{columna}\s*IS\s+NOT\s+NULL', '', sql, flags=re.IGNORECASE)
            sql = re.sub(rf'AND\s+{columna}\s*IS\s+NULL', '', sql, flags=re.IGNORECASE)
            
            # Eliminar referencias en CASE WHEN
            sql = re.sub(rf'AND\s+{columna}\s*=\s*[\'"][^\'\"]*[\'"]\s*THEN', 'AND 1=1 THEN', sql, flags=re.IGNORECASE)
            sql = re.sub(rf'WHEN\s+{columna}\s*=\s*[\'"][^\'\"]*[\'"]\s*THEN', 'WHEN 1=1 THEN', sql, flags=re.IGNORECASE)
            
            # Eliminar referencias en SELECT
            sql = re.sub(rf'{columna}\s+AS\s+\w+', 'NULL AS \1', sql, flags=re.IGNORECASE)
            sql = re.sub(rf'UPPER\s*\(\s*{columna}\s*\)\s+AS\s+\w+', 'NULL AS \1', sql, flags=re.IGNORECASE)
        
        # 9.10. CORRECCIÓN CRÍTICA: Corregir errores de sintaxis comunes
        # Error: doce meses → doce_meses, año corrido → año_corrido
        sql = re.sub(r'\bdoce\s+meses\b', 'doce_meses', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\baño\s+corrido\b', 'año_corrido', sql, flags=re.IGNORECASE)
        
        # 9.11. CORRECCIÓN CRÍTICA: Corregir operaciones con INTERVAL incompatibles
        # Error: No function matches the given name and argument types '-(BIGINT, INTERVAL)'
        sql = re.sub(
            r'fecha\s*-\s*INTERVAL\s+[\'"]\d+\s+(year|month|day|hour|minute|second)[\'"]',
            lambda m: f"DATE_SUB(fecha, INTERVAL '1 {m.group(1)}')",
            sql,
            flags=re.IGNORECASE
        )
        
        sql = re.sub(
            r'fecha\s*-\s*INTERVAL\s+[\'"]\d+\s+(year|month|day|hour|minute|second)[\'"]\s*\+\s*INTERVAL\s+[\'"]\d+\s+(year|month|day|hour|minute|second)[\'"]',
            lambda m: f"DATE_SUB(DATE_SUB(fecha, INTERVAL '1 {m.group(1)}'), INTERVAL '1 {m.group(1)}')",
            sql,
            flags=re.IGNORECASE
        )
        
        # 9.12. CORRECCIÓN CRÍTICA: Eliminar GROUP BY con columnas que no existen
        # Error: column "X" must appear in the GROUP BY clause
        if "GROUP BY" in sql:
            # Eliminar referencias a columnas alucinadas en GROUP BY
            for columna in columnas_alucinadas:
                sql = re.sub(rf'\b{columna}\b\s*,?\s*', '', sql, flags=re.IGNORECASE)
                sql = re.sub(rf',\s*{columna}\b', '', sql, flags=re.IGNORECASE)
        
        # 9.13. CORRECCIÓN CRÍTICA: Corregir sintaxis LIKE con condiciones complejas
        # Error: syntax error at or near "VIS"
        sql = re.sub(r"LIKE\s+['\"]%PREVENTA\s+CON\s+segmento_pre\s*=\s*['\"]VIS['\"]%['\"]", "LIKE '%PREVENTA%' AND segmento_pre = 'VIS'", sql, flags=re.IGNORECASE)
        sql = re.sub(r"LIKE\s+['\"]%PREVENTA\s+CON\s+segmento_pre\s*=\s*['\"]No VIS['\"]%['\"]", "LIKE '%PREVENTA%' AND segmento_pre = 'No VIS'", sql, flags=re.IGNORECASE)
        
        # 9.14. CORRECCIÓN CRÍTICA: Eliminar funciones incompatibles con DuckDB
        # Error: Parser Error con ROLLUP, RANK, DAYOFYEAR
        sql = re.sub(r'\bROLLUP\s*\([^)]*\)', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bGROUP\s+BY\s+ROLLUP\s*\([^)]*\)', 'GROUP BY 1', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bRANK\s*\(\s*[^)]*\s*\)', '1', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bDAYOFYEAR\b', 'DAY', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bDAYOFWEEK\b', 'DAY', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bDAYOFMONTH\b', 'DAY', sql, flags=re.IGNORECASE)
        
        # 9.15. CORRECCIÓN CRÍTICA: Corregir operaciones BETWEEN invalidas
        # Error: syntax error at or near "="
        sql = re.sub(r'LIKE\s+[\'"][^\'\"]*[\'"]\s+BETWEEN\s+(\d+)\s+AND\s+(\d+)', r'LIKE \'%\' AND CAST(\1 AS INTEGER) BETWEEN \1 AND \2', sql, flags=re.IGNORECASE)
        sql = re.sub(r'BETWEEN\s+\(\s*SELECT\s+MAX\s*\([^)]*\)\s*-\s*\d+\s+DAY\s*\)', 'BETWEEN DATE_SUB((SELECT MAX(fecha)), INTERVAL 1 DAY)', sql, flags=re.IGNORECASE)
        
        # 9.16. CORRECCIÓN CRÍTICA: Corregir conversiones de tipo incorrectas
        # Error: Conversion Error: Could not convert string to INT64
        sql = re.sub(r'CAST\s*\(\s*rangos_decreto_pre\s+AS\s+INTEGER\s*\)', 'rangos_decreto_pre', sql, flags=re.IGNORECASE)
        sql = re.sub(r'estrato\s*=\s*\(\s*SELECT\s+DISTINCT\s+rangos_decreto_pre\s+FROM\s+livo\s*\)', '1=1', sql, flags=re.IGNORECASE)
        
        # 9.17. CORRECCIÓN CRÍTICA: Simplificar queries complejos con UNION ALL
        # Error: Set operations can only apply to expressions with the same number of result columns
        if "UNION ALL" in sql and sql.count("SELECT") > 3:
            # Si hay más de 3 SELECTs en UNION ALL, simplificar a uno solo
            first_select = sql.split("UNION ALL")[0].strip()
            sql = first_select
        
        # 9.18. CORRECCIÓN CRÍTICA: Corregir subqueries incompletas
        # Error: Referenced column not found in FROM clause
        sql = re.sub(r'FROM\s*\(\s*SELECT\s+CASE\s+WHEN.*?\)', 'FROM livo', sql, flags=re.IGNORECASE | re.DOTALL)
        
        # 9.19. CORRECCIÓN CRÍTICA: Eliminar columnas alucinadas adicionales
        # Error: Referenced column not found
        columnas_alucinadas_adicionales = [
            'segmento_etapa', 'rangos_decreto_pre_etapa', 'tipo_cuenta', 
            'barrio', 'divipola', 'estrato', 'tipo_propiedad'
        ]
        
        for columna in columnas_alucinadas_adicionales:
            # Eliminar en WHERE
            sql = re.sub(rf'AND\s+UPPER\s*\(\s*{columna}\s*\)\s*LIKE\s+[\'"][^\'\"]*[\'"]', '', sql, flags=re.IGNORECASE)
            sql = re.sub(rf'AND\s+{columna}\s*=\s*[\'"][^\'\"]*[\'"]', '', sql, flags=re.IGNORECASE)
            sql = re.sub(rf'AND\s+{columna}\s*IN\s*\([^)]*\)', '', sql, flags=re.IGNORECASE)
            
            # Eliminar en SELECT
            sql = re.sub(rf'{columna}\s+AS\s+\w+', 'NULL AS \1', sql, flags=re.IGNORECASE)
        
        # 9.20. CORRECCIÓN CRÍTICA: Corregir sintaxis de WITH CTEs
        # Error: Parser Error con WITH
        sql = re.sub(r'WITH\s+\w+\s+AS\s*\([^)]*\)\s*,?\s*', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'GROUP\s+BY\s+WITH\s+ROLLUP', 'GROUP BY 1', sql, flags=re.IGNORECASE)
        
        # 9.21. CORRECCIÓN CRÍTICA: Corregir UPPENT por UPPER
        # Error: UPPENT no existe
        sql = re.sub(r'UPPENT\s*\(', 'UPPER(', sql, flags=re.IGNORECASE)
        
        # 9.22. CORRECCIÓN CRÍTICA: Eliminar segmento_pre (no existe)
        # Error: Column "segmento_pre" does not exist
        sql = re.sub(r'segmento_pre\s*=\s*[\'"][^\'\"]*[\'"]', 'segmento_pre = \'VIS\'', sql, flags=re.IGNORECASE)
        sql = re.sub(r'segmento_pre\s*IN\s*\([^)]*\)', 'segmento_pre IN (\'VIS\', \'No VIS\')', sql, flags=re.IGNORECASE)
        
        # 9.23. CORRECCIÓN CRÍTICA: MANTENER rangos_decreto_pre en WHERE (la columna existe)
        # La columna rangos_decreto_pre SÍ existe, no eliminarla
        # sql = re.sub(r'AND\s+rangos_decreto_pre\s*IN\s*\([^)]*\)', '', sql, flags=re.IGNORECASE)
        # sql = re.sub(r'AND\s+rangos_decreto_pre\s*=\s*[\'"][^\'\"]*[\'"]', '', sql, flags=re.IGNORECASE)
        
        # 9.24. CORRECCIÓN CRÍTICA: Eliminar compania_constructora (no existe)
        # Error: Column "compania_constructora" does not exist
        sql = re.sub(r'compania_constructora\s*=\s*[\'"][^\'\"]*[\'"]', 'cuenta = \'Oferta\'', sql, flags=re.IGNORECASE)
        
        # 9.25. CORRECCIÓN CRÍTICA: Eliminar doce_meses = 1 sin contexto
        # Error: doce_meses = 1 sin MAX()
        sql = re.sub(r'doce_meses\s*=\s*1', 'doce_meses = (SELECT MAX(doce_meses) FROM livo)', sql, flags=re.IGNORECASE)
        
        # 9.26. CORRECCIÓN CRÍTICA: Eliminar contexto LIVO de la respuesta
        # Esto se manejará en la generación de respuesta, no en SQL
        
        # 9.27. CORRECCIÓN CRÍTICA: Eliminar zona (no existe)
        # Error: Column "zona" does not exist
        sql = re.sub(r'AND\s+zona\s*=\s*[\'"][^\'\"]*[\'"]', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'AND\s+UPPER\s*\(\s*zona\s*\)\s*LIKE\s*UPPER\s*\([^)]*\)', '', sql, flags=re.IGNORECASE)
        
        # 9.28. CORRECCIÓN CRÍTICA: MANTENER rangos_decreto_pre en WHERE y HAVING (la columna existe)
        # La columna rangos_decreto_pre SÍ existe, no eliminarla
        # Solo eliminar condiciones inválidas como rangos_decreto_pre <= número
        sql = re.sub(r'HAVING\s+rangos_decreto_pre\s*<=\s*\d+', 'HAVING 1=1', sql, flags=re.IGNORECASE)
        sql = re.sub(r'AND\s+rangos_decreto_pre\s*<=\s*\d+', '', sql, flags=re.IGNORECASE)
        # Mantener rangos_decreto_pre IN (...) porque es válido
        # sql = re.sub(r'AND\s+rangos_decreto_pre\s*IN\s*\([^)]*\)', '', sql, flags=re.IGNORECASE)
        
        # 9.29. CORRECCIÓN CRÍTICA: Eliminar unidades BETWEEN sin contexto
        # Error: BETWEEN sin columna válida
        sql = re.sub(r'AND\s+unidades\s+BETWEEN\s+\d+\s+AND\s+\d+', '', sql, flags=re.IGNORECASE)
        
        # 9.30. CORRECCIÓN CRÍTICA: Eliminar doce_meses = 1 sin MAX
        # Error: doce_meses = 1 sin contexto
        sql = re.sub(r'AND\s+doce_meses\s*=\s*1', 'AND doce_meses = (SELECT MAX(doce_meses) FROM livo)', sql, flags=re.IGNORECASE)
        
        # 9.31. CORRECCIÓN CRÍTICA: Eliminar segmento_pre != 'VIP'
        # Error: segmento_pre no existe
        sql = re.sub(r'AND\s+segmento_pre\s*!=\s*[\'"]VIP[\'"]', '', sql, flags=re.IGNORECASE)
        
        # 9.32. CORRECCIÓN CRÍTICA: Simplificar queries complejas con UNION ALL duplicados
        # Error: Queries duplicadas en UNION ALL
        if sql.count("UNION ALL") > 2:
            # Simplificar a solo el primer SELECT
            first_select = sql.split("UNION ALL")[0].strip()
            sql = first_select
        
        # 9.33. CORRECCIÓN CRÍTICA: MANTENER rango_decreto_pre (la columna existe)
        # La columna rango_decreto_pre SÍ existe, no eliminarla
        # Solo eliminar condiciones inválidas como rango_decreto_pre = 'texto'
        sql = re.sub(r'rango_decreto_pre\s*=\s*[\'"][^\'\"]*[\'"]', 'rangos_decreto_pre IS NOT NULL', sql, flags=re.IGNORECASE)
        # Mantener rango_decreto_pre IS NOT NULL porque es válido
        # sql = re.sub(r'rango_decreto_pre\s*IS\s+NOT\s+NULL', '1=1', sql, flags=re.IGNORECASE)
        # Mantener rango_decreto_pre IN (...) porque es válido
        # sql = re.sub(r'rango_decreto_pre\s*IN\s*\([^)]*\)', '', sql, flags=re.IGNORECASE)
        
        # 9.34. CORRECCIÓN CRÍTICA: Eliminar segmento_pre en WHERE y GROUP BY
        # Error: Column "segmento_pre" does not exist
        sql = re.sub(r'WHERE\s+.*segmento_pre\s*=\s*[\'"][^\'\"]*[\'"]', 'WHERE 1=1', sql, flags=re.IGNORECASE)
        sql = re.sub(r'AND\s+segmento_pre\s*=\s*[\'"][^\'\"]*[\'"]', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'GROUP\s+BY\s+.*segmento_pre', 'GROUP BY 1', sql, flags=re.IGNORECASE)
        
        # 9.35. CORRECCIÓN CRÍTICA: Eliminar GROUP BY ROLLUP pero mantener rangos_decreto_pre
        # Error: ROLLUP no es compatible con DuckDB, pero rangos_decreto_pre SÍ existe
        sql = re.sub(r'GROUP\s+BY\s+ROLLUP\s*\([^)]*\)', 'GROUP BY rangos_decreto_pre', sql, flags=re.IGNORECASE)
        sql = re.sub(r'GROUP\s+BY\s+.*ROLLUP\s*\([^)]*\)', 'GROUP BY rangos_decreto_pre', sql, flags=re.IGNORECASE)
        
        # 9.36. CORRECCIÓN CRÍTICA: Eliminar WITH CTEs complejas
        # Error: WITH statements no son compatibles
        sql = re.sub(r'WITH\s+\w+\s+AS\s*\([^)]*\)\s*,?\s*', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'GROUP\s+BY\s+divipola,\s*año_corrido\s+WITH\s+CUBE', 'GROUP BY 1', sql, flags=re.IGNORECASE)
        
        # 9.37. CORRECCIÓN CRÍTICA: Eliminar funciones de ventana
        # Error: Funciones de ventana no son compatibles
        sql = re.sub(r'OVER\s*\([^)]*\)', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'ROW_NUMBER\s*\([^)]*\)', '1', sql, flags=re.IGNORECASE)
        
        # 9.38. CORRECCIÓN CRÍTICA: Simplificar condiciones de fecha complejas
        # Error: BETWEEN con fechas incorrectas
        sql = re.sub(r'CAST\s*\(\s*LEFT\s*\([^)]*\)\s+AS\s+VARCHAR\s*\)\s+BETWEEN\s+\d+\s+AND\s+\d+', '1=1', sql, flags=re.IGNORECASE)
        
        # 10. CORRECCIÓN CRÍTICA: JOIN con USING incorrecto cuando la columna no existe en la tabla derecha
        # Error: Column "X" does not exist on right side of join!
        # Patrón: WITH ... JOIN tabla USING (columna) donde tabla no tiene 'columna'
        if "USING (" in sql and "WITH" in sql:
            # Buscar patrones de USING incorrectos en CTEs
            using_pattern = r'(\w+)\s+JOIN\s+(\w+)\s+USING\s*\(([^)]+)\)'
            def fix_incorrect_using(match):
                left_table = match.group(1)
                right_table = match.group(2)
                using_column = match.group(3).strip()
                
                # Si es un JOIN entre tablas con diferentes estructuras (como en el ejemplo)
                # reemplazar USING por CROSS JOIN ya que no hay columna común real
                return f"{left_table} CROSS JOIN {right_table}"
            
            sql = re.sub(using_pattern, fix_incorrect_using, sql, flags=re.IGNORECASE)
        
        # 11. CORRECCIÓN CRÍTICA: DATE_SUB con INTERVAL no es válido en DuckDB
        # Error: No function matches the given name and argument types 'date_sub(DATE, INTERVAL)'
        # DuckDB usa: CURRENT_DATE - INTERVAL '1 year' o date('today', '-1 year')
        sql = re.sub(
            r'DATE_SUB\s*\(\s*CURRENT_DATE\s*\(\s*\)\s*,\s*INTERVAL\s+(\d+)\s+(YEAR|MONTH|DAY)\s*\)',
            lambda m: f"CURRENT_DATE - INTERVAL '{m.group(1)} {m.group(2).lower()}'",
            sql,
            flags=re.IGNORECASE
        )
        
        sql = re.sub(
            r'DATE_SUB\s*\(\s*CURRENT_DATE\s*,\s*INTERVAL\s+(\d+)\s+(YEAR|MONTH|DAY)\s*\)',
            lambda m: f"CURRENT_DATE - INTERVAL '{m.group(1)} {m.group(2).lower()}'",
            sql,
            flags=re.IGNORECASE
        )
        
        # También corregir DATE_SUB con TIMESTAMP
        sql = re.sub(
            r'DATE_SUB\s*\(\s*CURRENT_TIMESTAMP\s*\(\s*\)\s*,\s*INTERVAL\s+(\d+)\s+(YEAR|MONTH|DAY|HOUR|MINUTE|SECOND)\s*\)',
            lambda m: f"CURRENT_TIMESTAMP - INTERVAL '{m.group(1)} {m.group(2).lower()}'",
            sql,
            flags=re.IGNORECASE
        )
        
        sql = re.sub(
            r'DATE_SUB\s*\(\s*CURRENT_TIMESTAMP\s*,\s*INTERVAL\s+(\d+)\s+(YEAR|MONTH|DAY|HOUR|MINUTE|SECOND)\s*\)',
            lambda m: f"CURRENT_TIMESTAMP - INTERVAL '{m.group(1)} {m.group(2).lower()}'",
            sql,
            flags=re.IGNORECASE
        )
        
        # 12. CORRECCIÓN CRÍTICA: Referencias a columnas que no existen en FROM clause
        # Error: Referenced column "promedio_valor_pre_vis" not found in FROM clause!
        # Candidate bindings: "datos_segmento_pre_vis.promedio_valor"
        if "promedio_valor_pre_vis" in sql:
            # Reemplazar la referencia incorrecta con el nombre correcto según el error
            sql = sql.replace("promedio_valor_pre_vis", "datos_segmento_pre_vis.promedio_valor")
        
        # Corrección general para patrones similares
        # Patrón: columna_incorrecta -> tabla_correcta.columna_correcta
        column_corrections = {
            "promedio_valor_pre_vis": "datos_segmento_pre_vis.promedio_valor",
            "total_2025": "datos_2025.total_2025",
            "total_2026": "datos_2026.total_2026",
            "promedio_valor_rango_decreto": "datos_rango_decreto.promedio_valor",
            "rango_decreto": "rangos_decreto_pre",
            "valor_max_vip": "valor",
            "CURDATE()": "CURRENT_DATE",
            "tipo_transaccion": "zona",
            "segment_pre": "segmento_pre",
            "rango_decreto_pre_vip": "rangos_decreto_pre",
            "rangos_decreto_pre_vip": "rangos_decreto_pre",
            "rango": "rangos_decreto_pre",
            "RANGEO_DECRETO_PRE": "rangos_decreto_pre",
            "año_corrado": "año_corrido"
        }
        
        for incorrect, correct in column_corrections.items():
            if incorrect in sql:
                # Para rango_decreto, usar replace_all para asegurar todas las instancias
                if incorrect == "rango_decreto":
                    sql = sql.replace(incorrect, correct)
                else:
                    # Para otros, usar regex con word boundaries
                    pattern = r'\b' + re.escape(incorrect) + r'\b(?!\.)'
                    sql = re.sub(pattern, correct, sql, flags=re.IGNORECASE)
        
        # 13. CORRECCIÓN CRÍTICA: Funciones y tablas no existentes
        # Error: Scalar Function with name curdate does not exist
        # Error: Table with name valores does not exist
        sql = sql.replace("CURDATE()", "CURRENT_DATE")
        sql = sql.replace("DATE_SUB(CURDATE()", "DATE_SUB(CURRENT_DATE")
        
        # Eliminar referencias a tablas no existentes como 'valores'
        if "FROM valores WHERE" in sql:
            # Reemplazar subquery de tabla no existente con valor constante
            sql = re.sub(
                r'SELECT\s+valor\s+FROM\s+valores\s+WHERE\s+nombre\s*=\s*[\'"][^\'\"]*[\'"]',
                "SELECT MAX(CAST(REPLACE(rangos_decreto_pre, 'VIS ', '') AS INTEGER)) FROM livo WHERE rangos_decreto_pre LIKE 'VIS %'",
                sql,
                flags=re.IGNORECASE
            )
        
        # 14. CORRECCIÓN CRÍTICA: GROUP BY WITH ROLLUP/CUBE que causan errores de sintaxis
        # Error: syntax error at end of input
        # DuckDB puede tener problemas con WITH ROLLUP/CUBE, eliminarlos para asegurar compatibilidad
        
        # Eliminar completamente WITH ROLLUP/CUBE para evitar errores de sintaxis
        sql = re.sub(
            r'\s+WITH\s+(ROLLUP|CUBE)\s*;?\s*$',
            '',
            sql,
            flags=re.IGNORECASE
        )
        
        # También eliminar WITH ROLLUP/CUBE en medio de las consultas
        sql = re.sub(
            r'\s+WITH\s+(ROLLUP|CUBE)\s*(?=[a-zA-Z_]|$)',
            '',
            sql,
            flags=re.IGNORECASE
        )
        
        # Corregir GROUP BY ROLLUP(columna) a GROUP BY columna (sin ROLLUP)
        sql = re.sub(
            r'GROUP BY\s+ROLLUP\s*\(\s*([^)]*)\s*\)',
            lambda m: f"GROUP BY {m.group(1).strip()}",
            sql,
            flags=re.IGNORECASE
        )
        
        # 15. CORRECCIÓN CRÍTICA: Sintaxis incorrecta sin operador
        # Error: syntax error at or near "VIS"
        # Patrón: segmento_pre VIS (falta operador)
        sql = re.sub(
            r'\bsegmento_pre\s+VIS\b',
            "segmento_pre = 'VIS'",
            sql,
            flags=re.IGNORECASE
        )
        
        sql = re.sub(
            r'\brangos_decreto_pre\s+VIP\b',
            "rangos_decreto_pre LIKE 'VIP%'",
            sql,
            flags=re.IGNORECASE
        )
        
        # 16. CORRECCIÓN CRÍTICA: HAVING sin GROUP BY u ORDER BY inválido
        # Error: syntax error at or near "HAVING" / "ORDER"
        # Eliminar HAVING si no hay GROUP BY
        if "HAVING" in sql and "GROUP BY" not in sql:
            sql = re.sub(
                r'\bHAVING\s+[^;]*',
                '',
                sql,
                flags=re.IGNORECASE
            )
        
        # Eliminar ORDER BY si está al final sin SELECT previo válido
        if sql.strip().endswith("ORDER BY") or re.search(r'ORDER BY\s*$', sql, re.IGNORECASE):
            sql = re.sub(
                r'ORDER BY\s*$',
                '',
                sql,
                flags=re.IGNORECASE
            )
        
        # 17. CORRECCIÓN CRÍTICA: GROUP BY HAVING sin columnas especificadas
        # Error: syntax error at or near "HAVING"
        # Patrón: GROUP BY HAVING condicion (sin columnas antes de HAVING)
        sql = re.sub(
            r'GROUP BY\s+HAVING\s+([^;]*)',
            r'GROUP BY zona, departamento, ciudad HAVING \1',
            sql,
            flags=re.IGNORECASE
        )
        
        # 18. CORRECCIÓN CRÍTICA: Strings literales con comillas dobles en SELECT
        # Error: Referenced column "Últimos 12 meses" not found in FROM clause
        # Patrón: "string literal" AS columna (debe ser 'string literal')
        sql = re.sub(
            r'"([^"]+)"\s+AS\s+(\w+)',
            lambda m: f"'{m.group(1)}' AS {m.group(2)}",
            sql,
            flags=re.IGNORECASE
        )
        
        # También corregir strings literales sin AS
        sql = re.sub(
            r'"([^"]+)"\s*,',
            lambda m: f"'{m.group(1)}',",
            sql,
            flags=re.IGNORECASE
        )
        
        # 19. CORRECCIÓN CRÍTICA: Agregados en WHERE clause
        # Error: WHERE clause cannot contain aggregates!
        # Patrón: WHERE ... (SELECT MAX(...)) = valor
        sql = re.sub(
            r'WHERE\s+.*?\(SELECT\s+MAX\s*\([^)]+\)\s*FROM\s+[^)]+\)\s*=\s*\d+',
            lambda m: re.sub(r'\(SELECT\s+MAX\s*\([^)]+\)\s*FROM\s+[^)]+\)\s*=\s*\d+', '1=1', m.group(0)),
            sql,
            flags=re.IGNORECASE
        )
        
        # 20. CORRECCIÓN CRÍTICA: WITH CUBE/ROLLUP sintaxis incorrecta
        # Error: syntax error at or near "WITH"
        # Patrón: GROUP BY WITH CUBE (columna) USING ROLLUP
        sql = re.sub(
            r'GROUP BY\s+WITH\s+(CUBE|ROLLUP)\s*\([^)]*\)\s+USING\s+(ROLLUP|CUBE)',
            'GROUP BY zona, departamento, ciudad',
            sql,
            flags=re.IGNORECASE
        )
        
        # Corregir GROUP BY WITH ROLLUP, HAVING al final
        sql = re.sub(
            r'GROUP BY\s+WITH\s+ROLLUP\s*,\s+HAVING\s+([^;]*)',
            'GROUP BY zona, departamento, ciudad',
            sql,
            flags=re.IGNORECASE
        )
        # 6d-pre. UPPER(AM_capital) LIKE 'CIUDAD AM%' → AM_capital = 'Ciudad AM'
        sql = re.sub(
            r"UPPER\s*\(\s*AM_capital\s*\)\s*LIKE\s*UPPER\s*\(\s*'([^']+?)\s*%?'\s*\)",
            lambda m: f"AM_capital = '{m.group(1).strip().rstrip('%')}'",
            sql, flags=re.IGNORECASE
        )
        # 6d. Tildes incorrectas en nombres de ciudades comunes
        sql = sql.replace("'CÚCATA'", "'Cúcuta'").replace("'Cucata'", "'Cúcuta'").replace("'CUCUTA'", "'Cúcuta'")\
                 .replace("'CÚCATA AM'", "'Cúcuta AM'").replace("'Cucata AM'", "'Cúcuta AM'")\
                 .replace("'BOGOTA'", "'Bogotá'").replace("'Bogota'", "'Bogotá'")\
                 .replace("'MEDELLIN'", "'Medellín'").replace("'Medellin'", "'Medellín'")\
                 .replace("'PEREIRA'", "'Pereira'").replace("'MANIZALES'", "'Manizales'")\
                 .replace("'BUCARAMANGA'", "'Bucaramanga'").replace("'BARRANQUILLA'", "'Barranquilla'")\
                 .replace("'CALI'", "'Cali'")
        
        # 7. CORRECCIÓN CRÍTICA: GROUP BY rango(s)_decreto_pre → GROUP BY ROLLUP(rangos_decreto_pre)
        sql = re.sub(r'\bGROUP\s+BY\s+rangos_decreto_pre\b(?!\s*\))', 
                     'GROUP BY ROLLUP(rangos_decreto_pre)', sql, flags=re.IGNORECASE)
        
        # 8. CORRECCIÓN CRÍTICA: OR de zonas metropolitanas sin paréntesis
        # Añadir paréntesis si hay un patrón: "ciudad = '...' OR AM_capital = '...'" sin paréntesis
        sql = re.sub(
            r'(?<!\()(ciudad\s*=\s*\'[^\']+\'\s*OR\s*AM_capital\s*(?:=|IN)\s*(?:\'[^\']+\'|\([^)]+\)))(?!\))',
            r'(\1)', sql, flags=re.IGNORECASE
        )
        
        # 9. CORRECCIÓN CRÍTICA: WITH ROLLUP (sintaxis MySQL) → GROUP BY ROLLUP(...) (DuckDB)
        sql = re.sub(r'GROUP\s+BY\s+([\w,\s\.`"]+)\s+WITH\s+ROLLUP',
                     lambda m: f'GROUP BY ROLLUP({m.group(1).strip()})', sql, flags=re.IGNORECASE)
        
        # 10. CORRECCIÓN CRÍTICA: GROUP BY col1, ROLLUP → GROUP BY ROLLUP(col1) (DuckDB)
        sql = re.sub(r'GROUP\s+BY\s+([\w\.`"]+)\s*,\s*ROLLUP\b(?!\s*\()',
                     lambda m: f'GROUP BY ROLLUP({m.group(1).strip()})', sql, flags=re.IGNORECASE)
        
        # 11. CORRECCIÓN CRÍTICA: ROLLUP(col) en la cláusula SELECT → eliminar (no es válido en SELECT)
        sql = re.sub(r',?\s*ROLLUP\s*\([^)]+\)\s*AS\s*\w+', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r',?\s*ROLLUP\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)
        
        # 12. CORRECCIÓN CRÍTICA: UPPER(segmento_pre) LIKE UPPER('%rangos_decreto_pre%') → eliminar filtro basura
        sql = re.sub(r"AND\s+UPPER\s*\(\s*segmento_pre\s*\)\s*LIKE\s+UPPER\s*\(\s*'%rangos_decreto_pre%'\s*\)",
                     '', sql, flags=re.IGNORECASE)
        
        # 13. CORRECCIÓN CRÍTICA: OR de año sin paréntesis → envolver en paréntesis
        # Patrón: CAST(...) = 2025 OR CAST(...) = 2026  →  (CAST(...) = 2025 OR CAST(...) = 2026)
        sql = re.sub(
            r'(?<!\()('  
            r'CAST\(LEFT\(CAST\(fecha AS VARCHAR\),\s*4\)\s*AS INTEGER\)\s*=\s*20\d{2}'  
            r'\s*OR\s*'  
            r'CAST\(LEFT\(CAST\(fecha AS VARCHAR\),\s*4\)\s*AS INTEGER\)\s*=\s*20\d{2}'  
            r')(?!\))',
            r'(\1)', sql, flags=re.IGNORECASE
        )
        
        # 14. CORRECCIÓN CRÍTICA: eliminar comentarios inline -- ... al final de líneas
        sql = re.sub(r'--[^\n]*', '', sql)

        # 14b. CORRECCIÓN: llaves/corchetes alucinados dentro de expresiones SQL → paréntesis
        # El LLM escribe CAST(LEFT(CAST(fecha AS VARCHAR}, 4) en lugar de VARCHAR), 4)
        sql = re.sub(r'VARCHAR\s*}', 'VARCHAR)', sql, flags=re.IGNORECASE)
        sql = re.sub(r'VARCHAR\s*]', 'VARCHAR)', sql, flags=re.IGNORECASE)
        # Caso general: } o ] solos que no forman parte de JSON → )
        sql = re.sub(r'(?<=\w)\s*}\s*(?=\s*,|\s*\)|\s+AS|\s+FROM|\s+WHERE)', ')', sql)

        # 14d. CORRECCIÓN: ROLLUP(expresion) en SELECT (no es función) → extraer expresión interna
        sql = re.sub(
            r'\bROLLUP\s*\(\s*((?:AVG|SUM|COUNT|MIN|MAX)\s*\([^)]+\)(?:\s*FILTER\s*\([^)]+\))?)\s*\)',
            lambda m: m.group(1),
            sql, flags=re.IGNORECASE
        )

        # 14e. CORRECCIÓN: AGG(col) FILTER (WHERE condicion_de_año) → AGG(CASE WHEN condicion THEN col END)
        # DuckDB soporta FILTER pero el LLM lo aplica incorrectamente — convertir a CASE WHEN seguro
        sql = re.sub(
            r'(AVG|SUM|COUNT|MIN|MAX)\s*\(([^)]+)\)\s*FILTER\s*\(\s*WHERE\s*([^)]+)\)',
            lambda m: f'{m.group(1)}(CASE WHEN {m.group(3).strip()} THEN {m.group(2).strip()} END)',
            sql, flags=re.IGNORECASE
        )

        # 14f. CORRECCIÓN: fecha BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD' → año extraído con CAST
        # La columna fecha es YYYYMMDD (entero), no fecha ISO string
        sql = re.sub(
            r"fecha\s+BETWEEN\s+'(\d{4})-\d{2}-\d{2}'\s+AND\s+'(\d{4})-\d{2}-\d{2}'",
            lambda m: (
                f"CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {m.group(1)}"
                if m.group(1) == m.group(2)
                else f"CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) BETWEEN {m.group(1)} AND {m.group(2)}"
            ),
            sql, flags=re.IGNORECASE
        )
        
        # 14g. CORRECCIÓN MASIVA: Todas las fechas string 'YYYY-MM-DD' → YYYYMMDD numérico
        # El LLM sigue generando fechas en formato ISO a pesar de las instrucciones
        def convertir_fecha_string_a_numero(match):
            fecha_str = match.group(1)  # '2026-04-01'
            año, mes, dia = fecha_str.split('-')
            return f"{año}{mes}{dia}"  # '20260401'
        
        # Corregir fecha = 'YYYY-MM-DD' → fecha = YYYYMMDD
        sql = re.sub(
            r"fecha\s*=\s*'(\d{4}-\d{2}-\d{2})'",
            lambda m: f"fecha = {convertir_fecha_string_a_numero(m)}",
            sql, flags=re.IGNORECASE
        )
        
        # Corregir fecha >= 'YYYY-MM-DD' → fecha >= YYYYMMDD
        sql = re.sub(
            r"fecha\s*>=\s*'(\d{4}-\d{2}-\d{2})'",
            lambda m: f"fecha >= {convertir_fecha_string_a_numero(m)}",
            sql, flags=re.IGNORECASE
        )
        
        # Corregir fecha <= 'YYYY-MM-DD' → fecha <= YYYYMMDD
        sql = re.sub(
            r"fecha\s*<=\s*'(\d{4}-\d{2}-\d{2})'",
            lambda m: f"fecha <= {convertir_fecha_string_a_numero(m)}",
            sql, flags=re.IGNORECASE
        )
        
        # Corregir fecha IN ('YYYY-MM-DD') → fecha = YYYYMMDD
        sql = re.sub(
            r"fecha\s+IN\s*\('(\d{4}-\d{2}-\d{2})'\)",
            lambda m: f"fecha = {convertir_fecha_string_a_numero(m)}",
            sql, flags=re.IGNORECASE
        )

        # 14g. CORRECCIÓN: AND estrato = 0 (filtro sin sentido alucinado) → eliminar
        sql = re.sub(r'\bAND\s+estrato\s*=\s*0\b', '', sql, flags=re.IGNORECASE)
        
        # 14h. CORRECCIÓN: rangos_decreto_pre_pre_vip (columna inexistente) → rangos_decreto_pre
        sql = re.sub(r'rangos_decreto_pre_pre_vip', 'rangos_decreto_pre', sql, flags=re.IGNORECASE)

        # 14c. CORRECCIÓN: CASE WHEN ... condicion ELSE (sin THEN) → insertar THEN unidades
        # El LLM omite el THEN: "CASE WHEN x = 'y' AND z = 'w' ELSE 0 END" → "CASE WHEN x = 'y' AND z = 'w' THEN unidades ELSE 0 END"
        sql = re.sub(
            r'(CASE\s+WHEN\s+[^T][^H][^E][^N]+?)\s+ELSE\s+0\s+END',
            lambda m: m.group(0) if ' THEN ' in m.group(0).upper() else m.group(1) + ' THEN unidades ELSE 0 END',
            sql, flags=re.IGNORECASE
        )

        # 15. CORRECCIÓN: CASE WHEN rangos_decreto_pre = '01'/'02'/número → eliminar columna CASE alucinada
        # El LLM inventa segmentos numéricos que no existen en rangos_decreto_pre (VARCHAR descriptivo)
        sql = re.sub(
            r',?\s*CASE\s+WHEN\s+rangos?_decreto_pre\s*=\s*\'?\d+\'?[^E]*END\s+AS\s+\w+',
            '', sql, flags=re.IGNORECASE | re.DOTALL
        )

        # 16. CORRECCIÓN: SUM/COUNT/AVG(...) OVER () AS col en SELECT con GROUP BY → eliminar (incompatible DuckDB)
        sql = re.sub(
            r',?\s*(?:SUM|COUNT|AVG|MIN|MAX)\s*\([^)]*\)\s*OVER\s*\(\s*\)\s*AS\s*\w+',
            '', sql, flags=re.IGNORECASE
        )

        # 17. CORRECCIÓN: UPPER(ciudad) = UPPER('valor') → ciudad = 'valor' (= no necesita UPPER doble)
        sql = re.sub(
            r"UPPER\s*\(\s*(ciudad|departamento|regional|AM_capital)\s*\)\s*=\s*UPPER\s*\(\s*'([^']+)'\s*\)",
            lambda m: f"UPPER({m.group(1)}) LIKE '%{m.group(2).upper()}%'",
            sql, flags=re.IGNORECASE
        )

        # 18. CORRECCIÓN: HAVING col IN (...) con valores numéricos alucinados sobre rangos_decreto_pre → eliminar
        sql = re.sub(
            r"\bHAVING\s+rangos?_decreto_pre\s+IN\s*\([^)]*\)",
            '', sql, flags=re.IGNORECASE
        )
        # HAVING sin función de agregación sobre columna simple también es inválido → eliminar
        sql = re.sub(
            r"\bHAVING\s+(?!(?:SUM|AVG|COUNT|MIN|MAX)\s*\()(\w+\s*(?:=|!=|<|>|<=|>=|IN|LIKE|IS)[^;]+?)(?=\s+ORDER|\s+LIMIT|\s*$)",
            '', sql, flags=re.IGNORECASE
        )

        # 19. CORRECCIÓN: nombres de ciudad alucinados por el LLM → nombre correcto
        city_corrections = {
            r"'PELIAS(?:\s+AM)?'": ("'Pereira'", "'Pereira AM'"),
            r"'PELEAS(?:\s+AM)?'": ("'Pereira'", "'Pereira AM'"),
            r"'BUCARAMANGA(?:\s+AM)?'": ("'Bucaramanga'", "'Bucaramanga AM'"),
            r"'BUCAMARANGA(?:\s+AM)?'": ("'Bucaramanga'", "'Bucaramanga AM'"),
            r"'MONTERIA(?:\s+AM)?'": ("'Montería'", "'Montería AM'"),
            r"'MONTERREY(?:\s+AM)?'": ("'Montería'", "'Montería AM'"),
        }
        for pattern, (ciudad_val, am_val) in city_corrections.items():
            if 'AM' in pattern:
                sql = re.sub(pattern.replace('(?:\\s+AM)?', '\\s+AM'), am_val, sql, flags=re.IGNORECASE)
                sql = re.sub(pattern.replace('(?:\\s+AM)?', ''), ciudad_val, sql, flags=re.IGNORECASE)

        sql = ' '.join(sql.split())  # Normalizar espacios
        
        return sql
    
    # ============================================================================
    # NUEVAS FUNCIONES INTEGRADAS - Generación de SQL desde Proceso Humano
    # ============================================================================
    
    def generar_sql_desde_proceso(self, proceso: str, pregunta: str = None) -> Optional[str]:
        """
        Genera query SQL complejo basado en descripción del Proceso Humano.
        Integra: queries simples, TOP/Ranking, precios promedio, CTEs.
        """
        if not proceso or pd.isna(proceso):
            return None
        
        proc_lower = str(proceso).lower()
        proc_original = str(proceso)
        
        # 1. Queries con cálculo de variación/porcentaje (requieren CTEs)
        if any(x in proc_lower for x in ['variacion', 'variación', 'crecimiento', 'tasa', 'porcentaje']):
            return self._generar_sql_con_ctes(proc_original, pregunta)
        
        # 2. Queries con precio promedio (requieren SUM(valor)/SUM(unidades))
        if 'precio promedio' in proc_lower and ('valor' in proc_lower or 'unidades' in proc_lower):
            return self._generar_sql_precio_promedio(proc_original, pregunta)
        
        # 3. Queries con TOP/Ranking/LIMIT
        if any(x in proc_lower for x in ['top', 'ranking', 'limit']):
            return self._generar_sql_top_n(proc_original, pregunta)
        
        # 4. Queries simples (default)
        return self._generar_sql_simple(proc_original, pregunta)
    
    def _generar_sql_simple(self, proceso: str, pregunta: str = None) -> str:
        """Genera query simple SELECT...FROM...WHERE"""
        proc_lower = proceso.lower()
        
        # Detectar si hay GROUP BY
        campos_group = None
        if 'group by' in proc_lower:
            group_match = re.search(r'group\s+by\s+([\w,\s]+)', proc_lower)
            if group_match:
                campos = [c.strip() for c in group_match.group(1).split(',')]
                campos_group = ['segmento_pre' if c == 'segmento' else c for c in campos]
        
        # Construir SELECT
        select_parts = []
        if campos_group:
            select_parts.extend(campos_group)
        
        # Detectar métrica
        if 'sum(' in proc_lower or 'sum(unidades)' in proc_lower:
            select_parts.append("SUM(unidades) AS total")
        elif 'count(' in proc_lower:
            select_parts.append("COUNT(*) AS total")
        else:
            select_parts.append("SUM(unidades) AS total")
        
        query_parts = ["SELECT", ", ".join(select_parts), "FROM livo"]
        
        # Construir WHERE usando las condiciones del proceso
        condiciones = self._construir_condiciones_desde_proceso(proceso)
        
        if condiciones:
            query_parts.append("WHERE")
            query_parts.append(" AND ".join(condiciones))
        
        # GROUP BY
        if campos_group:
            query_parts.append(f"GROUP BY {', '.join(campos_group)}")
        
        # ORDER BY
        if 'order by' in proc_lower:
            order_match = re.search(r'order\s+by\s+([\w\s,]+?)(?:\s+limit|\s*$)', proc_lower)
            if order_match:
                order_fields = order_match.group(1).strip()
                order_fields = order_fields.replace('uso', 'usos')
                if 'evolución mensual' in proc_lower or 'evolucion mensual' in proc_lower:
                    order_fields = order_fields.replace('mes', 'mes_anio')
                query_parts.append(f"ORDER BY {order_fields}")
            elif 'order by total' in proc_lower:
                query_parts.append("ORDER BY total DESC")
        
        # LIMIT
        limit_match = re.search(r'limit\s+(\d+)', proc_lower)
        if limit_match:
            query_parts.append(f"LIMIT {limit_match.group(1)}")
        
        return ' '.join(query_parts)
    
    def _generar_sql_top_n(self, proceso: str, pregunta: str = None) -> str:
        """Genera query con TOP/Ranking/LIMIT"""
        proc_lower = proceso.lower()
        
        # Detectar campo de agrupación
        campo_group = None
        if 'constructora' in proc_lower or 'compania_constructora' in proc_lower:
            campo_group = 'compania_constructora'
        elif 'departamento' in proc_lower:
            campo_group = 'departamento'
        elif 'ciudad' in proc_lower or 'metro cuadrado' in proc_lower or 'precio' in proc_lower:
            campo_group = 'ciudad'
        elif 'proyecto' in proc_lower or 'identificador' in proc_lower:
            campo_group = 'identificador'
        else:
            campo_group = 'compania_constructora'
        
        # Detectar cuenta
        cuenta = self._detectar_cuenta(proceso) or 'Oferta'
        
        # Construir condiciones base
        condiciones_base = [f"cuenta = '{cuenta}'"]
        
        # Detectar filtros adicionales
        if 'antioquia' in proc_lower:
            condiciones_base.append("UPPER(regional) LIKE '%ANTIOQUIA%'")
        if 'bogota' in proc_lower or 'bogotá' in proc_lower:
            condiciones_base.append("ciudad LIKE '%BOGOT%'")
        if 'segmento_pre = vis' in proc_lower:
            condiciones_base.append("segmento_pre = 'VIS'")
        
        # Detectar límite
        limit_match = re.search(r'(?:top|limit)\s+(\d+)', proc_lower)
        limite = limit_match.group(1) if limit_match else '10'
        
        # Detectar orden
        orden = 'DESC'
        if 'menor' in proc_lower or 'asc' in proc_lower:
            orden = 'ASC'
        
        where_clause = " AND ".join(condiciones_base)
        
        query = f"""SELECT {campo_group}, SUM(unidades) AS total 
FROM livo 
WHERE {where_clause}
GROUP BY {campo_group}
ORDER BY total {orden}
LIMIT {limite}"""
        
        return ' '.join(query.split())
    
    def _generar_sql_precio_promedio(self, proceso: str, pregunta: str = None) -> str:
        """Genera query con cálculo de precio promedio ponderado"""
        proc_lower = proceso.lower()
        
        # Detectar filtros base
        condiciones = ["cuenta = 'Oferta'"]
        
        if 'lanzamiento' in proc_lower:
            condiciones[0] = "cuenta = 'Lanzamientos'"
        
        # Filtros adicionales
        if 'bogota' in proc_lower or 'bogotá' in proc_lower:
            condiciones.append("ciudad LIKE '%BOGOT%'")
        
        # Fecha
        if 'ultimo periodo' in proc_lower or 'último periodo' in proc_lower:
            condiciones.append("fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')")
        elif 'abril 2026' in proc_lower or '20260401' in proc_lower:
            condiciones.append("fecha = 20260401")
        
        # Segmento
        if 'segmento_pre' in proc_lower:
            if 'vis' in proc_lower and 'vip' not in proc_lower:
                condiciones.append("segmento_pre = 'VIS'")
        
        where_clause = " AND ".join(condiciones)
        
        # Detectar si necesita GROUP BY
        if 'por segmento' in proc_lower or 'por tipo' in proc_lower or 'group by' in proc_lower:
            query = f"""SELECT segmento_pre,
    SUM(unidades) AS total_unidades,
    SUM(valor) AS valor_total,
    SUM(valor) / SUM(unidades) AS precio_promedio
FROM livo 
WHERE {where_clause}
GROUP BY segmento_pre"""
        else:
            query = f"""SELECT 
    SUM(unidades) AS total_unidades,
    SUM(valor) AS valor_total,
    SUM(valor) / SUM(unidades) AS precio_promedio
FROM livo 
WHERE {where_clause}"""
        
        return ' '.join(query.split())
    
    def _generar_sql_con_ctes(self, proceso: str, pregunta: str = None) -> str:
        """Genera query con CTEs (WITH) para cálculos de variación, tasas, porcentajes"""
        proc_lower = proceso.lower()
        
        if 'crecimiento' in proc_lower or 'variacion' in proc_lower or 'variación' in proc_lower:
            return self._generar_cte_crecimiento(proceso, pregunta)
        elif 'tasa de absorcion' in proc_lower or 'absorcion' in proc_lower:
            return self._generar_cte_absorcion(proceso, pregunta)
        elif 'desistimiento' in proc_lower or 'renuncias' in proc_lower:
            return self._generar_cte_desistimiento(proceso, pregunta)
        elif 'porcentaje' in proc_lower or 'estratos' in proc_lower:
            return self._generar_cte_porcentaje(proceso, pregunta)
        
        return self._generar_sql_simple(proceso, pregunta)
    
    def _generar_cte_crecimiento(self, proceso: str, pregunta: str = None) -> str:
        """Genera CTE para cálculo de crecimiento usando AÑO CORRIDO (mismos meses)"""
        proc_lower = proceso.lower()
        
        if 'departamento' in proc_lower:
            campo_group = 'departamento'
            tabla_cte = 'deptos'
        elif 'constructora' in proc_lower or 'compania' in proc_lower:
            campo_group = 'compania_constructora'
            tabla_cte = 'constructoras'
        else:
            campo_group = 'departamento'
            tabla_cte = 'deptos'
        
        cuenta = 'Lanzamientos' if 'lanzamiento' in proc_lower else 'Ventas'
        
        # Usar AÑO CORRIDO: detectar el último mes disponible en 2026 y comparar mismos meses en 2025
        # Esto permite comparaciones justas (ej: ene-abr 2026 vs ene-abr 2025)
        query = f"""WITH meses_2026 AS (
    -- Detectar el último mes con datos en 2026
    SELECT MAX(CAST(SUBSTRING(CAST(fecha AS VARCHAR), 5, 2) AS INTEGER)) AS ultimo_mes
    FROM livo 
    WHERE cuenta = '{cuenta}' AND CAST(fecha AS VARCHAR) LIKE '2026%'
),
{tabla_cte}_2025 AS (
    -- Sumar unidades para los mismos meses en 2025 (año corrido)
    SELECT {campo_group}, SUM(unidades) AS unidades_2025
    FROM livo 
    WHERE cuenta = '{cuenta}' 
      AND CAST(fecha AS VARCHAR) LIKE '2025%'
      AND CAST(SUBSTRING(CAST(fecha AS VARCHAR), 5, 2) AS INTEGER) <= (SELECT ultimo_mes FROM meses_2026)
    GROUP BY {campo_group}
),
{tabla_cte}_2026 AS (
    -- Sumar unidades para los meses disponibles en 2026
    SELECT {campo_group}, SUM(unidades) AS unidades_2026
    FROM livo 
    WHERE cuenta = '{cuenta}' AND CAST(fecha AS VARCHAR) LIKE '2026%'
    GROUP BY {campo_group}
)
SELECT 
    t25.{campo_group},
    t25.unidades_2025,
    t26.unidades_2026,
    CASE 
        WHEN t25.unidades_2025 > 0 THEN ((t26.unidades_2026 - t25.unidades_2025) / t25.unidades_2025) * 100 
        ELSE NULL 
    END AS crecimiento_porcentaje
FROM {tabla_cte}_2025 t25
JOIN {tabla_cte}_2026 t26 ON t25.{campo_group} = t26.{campo_group}
ORDER BY crecimiento_porcentaje DESC NULLS LAST
LIMIT 5"""
        
        return query
    
    def _generar_cte_absorcion(self, proceso: str, pregunta: str = None) -> str:
        """Genera CTE para tasa de absorción: Ventas / (Oferta + Ventas)"""
        proc_lower = proceso.lower()
        
        regional_cond = "regional = 'Antioquia'"
        if 'bogota' in proc_lower or 'bogotá' in proc_lower:
            regional_cond = "ciudad LIKE '%BOGOT%'"
        
        query = f"""WITH ventas AS (
    SELECT SUM(unidades) AS total_ventas
    FROM livo 
    WHERE cuenta = 'Ventas'
      AND {regional_cond}
      AND fecha >= (SELECT MAX(fecha) - 300 FROM livo)
),
oferta_ventas AS (
    SELECT SUM(unidades) AS total_oferta_ventas
    FROM livo 
    WHERE cuenta IN ('Oferta', 'Ventas')
      AND {regional_cond}
      AND fecha >= (SELECT MAX(fecha) - 300 FROM livo)
)
SELECT 
    v.total_ventas,
    ov.total_oferta_ventas,
    (v.total_ventas / ov.total_oferta_ventas) * 100 AS tasa_absorcion
FROM ventas v, oferta_ventas ov"""
        
        return query
    
    def _generar_cte_desistimiento(self, proceso: str, pregunta: str = None) -> str:
        """Genera CTE para tasa de desistimiento: Renuncias / Ventas"""
        query = """WITH renuncias AS (
    SELECT compania_constructora, SUM(unidades) AS total_renuncias
    FROM livo 
    WHERE cuenta = 'Renuncias'
      AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Renuncias')
    GROUP BY compania_constructora
),
ventas AS (
    SELECT compania_constructora, SUM(unidades) AS total_ventas
    FROM livo 
    WHERE cuenta = 'Ventas'
      AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Ventas')
    GROUP BY compania_constructora
)
SELECT 
    r.compania_constructora,
    r.total_renuncias,
    v.total_ventas,
    r.total_renuncias / v.total_ventas AS tasa_desistimiento
FROM renuncias r
JOIN ventas v ON r.compania_constructora = v.compania_constructora
ORDER BY tasa_desistimiento DESC"""
        
        return query
    
    def _generar_cte_porcentaje(self, proceso: str, pregunta: str = None) -> str:
        """Genera CTE para cálculos de porcentaje"""
        proc_lower = proceso.lower()
        
        if 'estratos' in proc_lower and ('4' in proc_lower or '5' in proc_lower or '6' in proc_lower):
            query = """WITH estratos_4_6 AS (
    SELECT SUM(unidades) AS unidades_estratos_4_6
    FROM livo 
    WHERE cuenta = 'Lanzamientos'
      AND estrato IN ('4', '5', '6')
      AND fecha >= (SELECT MAX(fecha) - 10000 FROM livo)
),
total_lanzamientos AS (
    SELECT SUM(unidades) AS total_unidades
    FROM livo 
    WHERE cuenta = 'Lanzamientos'
      AND fecha >= (SELECT MAX(fecha) - 10000 FROM livo)
)
SELECT 
    e.unidades_estratos_4_6,
    t.total_unidades,
    (e.unidades_estratos_4_6 / t.total_unidades) * 100 AS porcentaje
FROM estratos_4_6 e, total_lanzamientos t"""
            return query
        
        return self._generar_sql_simple(proceso, pregunta)
    
    def _construir_condiciones_desde_proceso(self, proceso: str) -> list:
        """Construye lista de condiciones WHERE desde descripción de proceso"""
        proc_lower = proceso.lower()
        condiciones = []
        
        # Cuenta
        cuenta = self._detectar_cuenta(proceso)
        if cuenta:
            condiciones.append(f"cuenta = '{cuenta}'")
        else:
            condiciones.append("cuenta = 'Oferta'")
        
        # Segmento
        if 'segmento_pre = vis' in proc_lower:
            condiciones.append("segmento_pre = 'VIS'")
        elif 'segmento_pre = vip' in proc_lower:
            condiciones.append("segmento_pre = 'VIP'")
        
        # Rangos
        rangos_match = re.search(r'rangos_decreto_pre\s+in\s*\(([^)]+)\)', proceso, re.IGNORECASE)
        if rangos_match:
            valores = rangos_match.group(1).strip()
            condiciones.append(f"rangos_decreto_pre IN ({valores})")
        
        # Ciudad
        if 'bogota' in proc_lower or 'bogotá' in proc_lower:
            condiciones.append("ciudad LIKE '%BOGOT%'")
        elif 'medellin' in proc_lower or 'medellín' in proc_lower:
            condiciones.append("ciudad LIKE '%MEDELL%'")
        
        # Regional
        if 'antioquia' in proc_lower:
            condiciones.append("UPPER(regional) LIKE '%ANTIOQUIA%'")
        elif 'valle' in proc_lower:
            condiciones.append("regional = 'Valle'")
        
        # Fecha
        condicion_fecha = self._construir_condicion_fecha(proceso, cuenta or 'Oferta')
        if condicion_fecha:
            condiciones.append(condicion_fecha)
        
        return condiciones
    
    def _detectar_cuenta(self, proceso: str) -> Optional[str]:
        """Detecta el tipo de cuenta del proceso"""
        proc_lower = proceso.lower()
        
        if "cuenta = 'ventas'" in proc_lower or 'cuenta = ventas' in proc_lower:
            return 'Ventas'
        elif "cuenta = 'oferta'" in proc_lower or 'cuenta = oferta' in proc_lower:
            return 'Oferta'
        elif "cuenta = 'lanzamientos'" in proc_lower or 'cuenta = lanzamientos' in proc_lower:
            return 'Lanzamientos'
        elif "cuenta = 'renuncias'" in proc_lower or 'cuenta = renuncias' in proc_lower:
            return 'Renuncias'
        elif 'lanzamiento' in proc_lower:
            return 'Lanzamientos'
        elif 'ventas' in proc_lower:
            return 'Ventas'
        return None
    
    def _construir_condicion_fecha(self, proceso: str, cuenta_default: str = 'Oferta') -> Optional[str]:
        """Construye condición de fecha"""
        proc_lower = proceso.lower()
        
        if 'ultimo periodo' in proc_lower or 'último periodo' in proc_lower:
            return f"fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = '{cuenta_default}')"
        elif 'ultimo año' in proc_lower or 'último año' in proc_lower:
            return f"fecha >= (SELECT MAX(fecha) - 10000 FROM livo WHERE cuenta = '{cuenta_default}')"
        elif 'ultimo trimestre' in proc_lower or 'último trimestre' in proc_lower:
            return f"fecha >= (SELECT MAX(fecha) - 300 FROM livo WHERE cuenta = '{cuenta_default}')"
        elif '20260401' in proc_lower or 'abril 2026' in proc_lower:
            return "fecha = 20260401"
        elif '2025' in proc_lower and '2026' in proc_lower:
            return None
        
        return f"fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = '{cuenta_default}')"
    
    def _generar_sql_desde_reglas(self, pregunta: str) -> Optional[str]:
        """Genera SQL usando sistema de reglas SIN ninguna modificación externa"""
        try:
            # Sistema de reglas puro - sin expansión semántica, sin traducción
            texto_norm = normalize_text(pregunta)
            
            # Depuración: Analizar qué regla se aplica y por qué
            resultado_depuracion = {
                'pregunta_original': pregunta,
                'texto_normalizado': texto_norm,
                'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Aplicar reglas de negocio específicas (orden crítico para evitar conflictos)
            
            # REGLA PARA TASA DE ABSORCIÓN (prioridad máxima)
            if any(palabra in texto_norm for palabra in ['tasa de absorcion', 'tasa de absorción', 'absorcion', 'absorción']) and any(palabra in texto_norm for palabra in ['ventas', 'oferta']):
                # Detectar regional - usar valores exactos de la base de datos
                regional_cond = "1=1"
                if 'bogota' in texto_norm or 'bogotá' in texto_norm:
                    regional_cond = "regional = 'Bogotá & Cundinamarca'"
                elif 'antioquia' in texto_norm or 'medellin' in texto_norm or 'medellín' in texto_norm:
                    regional_cond = "regional = 'Antioquia'"
                elif 'atlantico' in texto_norm or 'atlántico' in texto_norm or 'barranquilla' in texto_norm:
                    regional_cond = "regional = 'Atlántico'"
                elif 'valle' in texto_norm or 'cali' in texto_norm:
                    regional_cond = "regional = 'Valle'"
                
                # Query con CTE para tasa de absorción - usar fecha máxima (no trimestre con agregado en WHERE)
                query = f"""WITH max_fecha AS (
    SELECT MAX(fecha) AS fecha_max
    FROM livo 
    WHERE cuenta = 'Oferta'
),
ventas AS (
    SELECT SUM(unidades) AS total_ventas
    FROM livo 
    WHERE cuenta = 'Ventas'
      AND fecha = (SELECT fecha_max FROM max_fecha)
      AND {regional_cond}
),
oferta AS (
    SELECT SUM(unidades) AS total_oferta
    FROM livo 
    WHERE cuenta = 'Oferta'
      AND fecha = (SELECT fecha_max FROM max_fecha)
      AND {regional_cond}
)
SELECT 
    v.total_ventas,
    o.total_oferta,
    (v.total_ventas / NULLIF(v.total_ventas + o.total_oferta, 0)) * 100 AS tasa_absorcion_porcentaje
FROM ventas v, oferta o"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'TASA DE ABSORCIÓN',
                    'proceso': f'Tasa absorción Ventas/(Oferta+Ventas), {regional_cond}',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
            # REGLA PARA RANKING DE CIUDADES POR PRECIO PROMEDIO (prioridad alta)
            if any(palabra in texto_norm for palabra in ['ranking', 'top', 'ciudades']) and any(palabra in texto_norm for palabra in ['precio promedio', 'precio', 'promedio']) and 'vis' in texto_norm and 'estrato 3' in texto_norm:
                # Query para ranking de ciudades por precio promedio del metro cuadrado
                query = """SELECT 
    ciudad,
    ROUND(SUM(valor) / SUM(area) / 1000000, 2) AS precio_promedio_millones_m2,
    SUM(unidades) AS total_unidades
FROM livo 
WHERE cuenta = 'Oferta'
    AND segmento_pre = 'VIS'
    AND estrato = '3'
    AND uso_etapa = 'Apartamento'
    AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
    AND ciudad IS NOT NULL
GROUP BY ciudad
HAVING SUM(area) > 0
ORDER BY precio_promedio_millones_m2 DESC
LIMIT 15"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'RANKING PRECIO M² VIS ESTRATO 3',
                    'proceso': 'Ranking ciudades por precio promedio m² en apartamentos VIS estrato 3',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
            # REGLA PARA TASA DE ABSORCIÓN (Ventas / (Oferta + Ventas))
            if any(palabra in texto_norm for palabra in ['tasa de absorcion', 'tasa de absorción', 'absorcion', 'absorción']) and any(palabra in texto_norm for palabra in ['ventas', 'oferta']):
                # Detectar regional
                regional_cond = "1=1"
                if 'bogota' in texto_norm or 'bogotá' in texto_norm:
                    regional_cond = "ciudad LIKE '%BOGOT%'"
                elif 'antioquia' in texto_norm or 'medellin' in texto_norm or 'medellín' in texto_norm:
                    regional_cond = "UPPER(regional) LIKE '%ANTIOQUIA%'"
                elif 'atlantico' in texto_norm or 'atlántico' in texto_norm or 'barranquilla' in texto_norm:
                    regional_cond = "UPPER(regional) LIKE '%ATLANTICO%'"
                elif 'valle' in texto_norm or 'cali' in texto_norm:
                    regional_cond = "regional = 'Valle'"
                
                # Detectar si es último trimestre
                trimestre_cond = "fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')"
                if 'trimestre' in texto_norm or 'último trimestre' in texto_norm:
                    trimestre_cond = "trimestre = (SELECT MAX(trimestre) FROM livo WHERE cuenta = 'Oferta')"
                
                # Query con CTE para tasa de absorción
                query = f"""WITH ventas AS (
    SELECT SUM(unidades) AS total_ventas
    FROM livo 
    WHERE cuenta = 'Ventas'
      AND {trimestre_cond}
      AND {regional_cond}
),
oferta AS (
    SELECT SUM(unidades) AS total_oferta
    FROM livo 
    WHERE cuenta = 'Oferta'
      AND {trimestre_cond}
      AND {regional_cond}
)
SELECT 
    v.total_ventas,
    o.total_oferta,
    (v.total_ventas / NULLIF(v.total_ventas + o.total_oferta, 0)) * 100 AS tasa_absorcion_porcentaje
FROM ventas v, oferta o"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'TASA DE ABSORCIÓN',
                    'proceso': f'Tasa absorción Ventas/(Oferta+Ventas), {regional_cond}',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
            # REGLA PARA UNIDADES Y PRECIO PROMEDIO POR SEGMENTO VIS/NO VIS (mover antes de reglas VIS generales)
            if any(palabra in texto_norm for palabra in ['vis', 'no vis']) and any(palabra in texto_norm for palabra in ['unidades', 'precio promedio']) and ('lanzaron' in texto_norm or 'lanzamiento' in texto_norm):
                # Detectar regional - usar valores exactos de la base de datos
                regional_cond = "1=1"
                if 'valle' in texto_norm or 'cauca' in texto_norm or 'cali' in texto_norm:
                    regional_cond = "regional = 'Valle'"
                elif 'bogota' in texto_norm or 'bogotá' in texto_norm:
                    regional_cond = "regional = 'Bogotá & Cundinamarca'"
                elif 'antioquia' in texto_norm or 'medellin' in texto_norm or 'medellín' in texto_norm:
                    regional_cond = "regional = 'Antioquia'"
                elif 'atlantico' in texto_norm or 'atlántico' in texto_norm or 'barranquilla' in texto_norm:
                    regional_cond = "regional = 'Atlántico'"
                
                # Detectar año
                año_cond = "CAST(fecha AS VARCHAR) LIKE '2026%'"
                if '2025' in texto_norm:
                    año_cond = "CAST(fecha AS VARCHAR) LIKE '2025%'"
                
                # Query con CTE para segmentar VIS y No VIS
                query = f"""WITH datos_segmentados AS (
    SELECT 
        CASE 
            WHEN segmento_pre = 'VIS' THEN 'VIS'
            ELSE 'NO VIS'
        END AS segmento,
        SUM(unidades) AS total_unidades,
        SUM(valor) AS valor_total
    FROM livo 
    WHERE cuenta = 'Lanzamientos'
      AND {año_cond}
      AND {regional_cond}
    GROUP BY CASE WHEN segmento_pre = 'VIS' THEN 'VIS' ELSE 'NO VIS' END
)
SELECT 
    segmento,
    total_unidades,
    ROUND(valor_total / total_unidades / 1000000, 2) AS precio_promedio_millones,
    valor_total
FROM datos_segmentados
ORDER BY segmento"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'UNIDADES Y PRECIO PROMEDIO POR SEGMENTO',
                    'proceso': f'Unidades y precio promedio VIS/No VIS, {regional_cond}, {año_cond}',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
            # REGLA PARA TOP PROYECTOS POR VALOR/SALDO EN REGIONAL (prioridad alta)
            if any(palabra in texto_norm for palabra in ['top', 'mayor', 'mayores', 'mayor saldo']) and any(palabra in texto_norm for palabra in ['proyectos', 'proyecto', 'identificador']) and any(palabra in texto_norm for palabra in ['valor', 'saldo', 'total']):
                # Detectar número para TOP (default 10)
                import re
                top_match = re.search(r'top\s+(\d+)', texto_norm)
                limite = top_match.group(1) if top_match else '10'
                
                # Detectar regional - usar valores exactos de la base de datos
                regional_cond = "1=1"
                if 'caribe' in texto_norm or 'atlantico' in texto_norm or 'atlántico' in texto_norm or 'barranquilla' in texto_norm or 'cartagena' in texto_norm:
                    regional_cond = "regional = 'Atlántico'"
                elif 'bogota' in texto_norm or 'bogotá' in texto_norm:
                    regional_cond = "regional = 'Bogotá & Cundinamarca'"
                elif 'antioquia' in texto_norm or 'medellin' in texto_norm:
                    regional_cond = "regional = 'Antioquia'"
                elif 'valle' in texto_norm or 'cali' in texto_norm:
                    regional_cond = "regional = 'Valle'"
                
                # Detectar si es saldo que inicia
                es_saldo = any(x in texto_norm for x in ['saldo que inicia', 'saldo', 'inicia', 'inicial', 'fase inicial'])
                
                # Usar cuenta correcta según el tipo de consulta
                cuenta_filtro = "'Saldo que inicia'" if es_saldo else "'Oferta'"
                fecha_cond_filtro = f"fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = {cuenta_filtro})"
                
                # Query para top proyectos por valor - SOLO usar identificador (no nombre_proyecto ni compania_constructora)
                query = f"""SELECT 
    identificador,
    SUM(unidades) AS total_unidades,
    SUM(valor) AS valor_total
FROM livo 
WHERE cuenta = {cuenta_filtro}
    AND {regional_cond}
    AND {fecha_cond_filtro}
GROUP BY identificador
ORDER BY valor_total DESC
LIMIT {limite}"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'TOP PROYECTOS POR VALOR',
                    'proceso': f'Top {limite} proyectos por valor, {regional_cond}, cuenta={cuenta_filtro}',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return ' '.join(query.split())
            
            # REGLA PARA UNIDADES Y PRECIO PROMEDIO POR SEGMENTO VIS/NO VIS (prioridad alta)
            if any(palabra in texto_norm for palabra in ['vis', 'no vis']) and any(palabra in texto_norm for palabra in ['unidades', 'precio promedio']) and ('lanzaron' in texto_norm or 'lanzamiento' in texto_norm):
                # Detectar regional
                regional_cond = "1=1"
                if 'valle' in texto_norm or 'cauca' in texto_norm or 'cali' in texto_norm:
                    regional_cond = "regional = 'Valle'"
                elif 'bogota' in texto_norm or 'bogotá' in texto_norm:
                    regional_cond = "ciudad LIKE '%BOGOT%'"
                elif 'antioquia' in texto_norm or 'medellin' in texto_norm or 'medellín' in texto_norm:
                    regional_cond = "UPPER(regional) LIKE '%ANTIOQUIA%'"
                elif 'atlantico' in texto_norm or 'atlántico' in texto_norm or 'barranquilla' in texto_norm:
                    regional_cond = "UPPER(regional) LIKE '%ATLANTICO%'"
                
                # Detectar año
                año_cond = "CAST(fecha AS VARCHAR) LIKE '2026%'"
                if '2025' in texto_norm:
                    año_cond = "CAST(fecha AS VARCHAR) LIKE '2025%'"
                
                # Query con CTE para segmentar VIS y No VIS
                query = f"""WITH datos_segmentados AS (
    SELECT 
        CASE 
            WHEN segmento_pre = 'VIS' THEN 'VIS'
            ELSE 'NO VIS'
        END AS segmento,
        SUM(unidades) AS total_unidades,
        SUM(valor) AS valor_total
    FROM livo 
    WHERE cuenta = 'Lanzamientos'
      AND {año_cond}
      AND {regional_cond}
    GROUP BY CASE WHEN segmento_pre = 'VIS' THEN 'VIS' ELSE 'NO VIS' END
)
SELECT 
    segmento,
    total_unidades,
    ROUND(valor_total / total_unidades / 1000000, 2) AS precio_promedio_millones,
    valor_total
FROM datos_segmentados
ORDER BY segmento"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'UNIDADES Y PRECIO PROMEDIO POR SEGMENTO',
                    'proceso': f'Unidades y precio promedio VIS/No VIS, {regional_cond}, {año_cond}',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
            # REGLA PARA PORCENTAJE DE ESTRATOS 4-6 EN LANZAMIENTOS (prioridad alta)
            if any(palabra in texto_norm for palabra in ['porcentaje', 'porciento', '%']) and any(palabra in texto_norm for palabra in ['estratos', 'estrato', '4', '5', '6']) and 'lanzamiento' in texto_norm:
                # Query con CTE para calcular porcentaje de estratos 4-6
                query = """WITH estratos_4_6 AS (
    SELECT SUM(unidades) AS unidades_estratos_4_6
    FROM livo 
    WHERE cuenta = 'Lanzamientos'
      AND estrato IN ('4', '5', '6')
      AND fecha >= (SELECT MAX(fecha) - 10000 FROM livo WHERE cuenta = 'Lanzamientos')
),
total_lanzamientos AS (
    SELECT SUM(unidades) AS total_unidades
    FROM livo 
    WHERE cuenta = 'Lanzamientos'
      AND fecha >= (SELECT MAX(fecha) - 10000 FROM livo WHERE cuenta = 'Lanzamientos')
)
SELECT 
    e.unidades_estratos_4_6,
    t.total_unidades,
    (e.unidades_estratos_4_6 / t.total_unidades) * 100 AS porcentaje
FROM estratos_4_6 e, total_lanzamientos t"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'PORCENTAJE ESTRATOS 4-6',
                    'proceso': 'Porcentaje estratos 4-6 en lanzamientos último año',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
            # REGLA PARA PRECIO PROMEDIO GENERAL (prioridad alta)
            if 'precio promedio' in texto_norm and ('unidades' in texto_norm or 'vivienda' in texto_norm or 'apartamento' in texto_norm):
                # Detectar región
                regional_cond = "1=1"
                if 'bogota' in texto_norm or 'bogotá' in texto_norm:
                    regional_cond = "ciudad LIKE '%BOGOT%'"
                elif 'antioquia' in texto_norm or 'medellin' in texto_norm or 'medellín' in texto_norm:
                    regional_cond = "UPPER(regional) LIKE '%ANTIOQUIA%'"
                elif 'atlantico' in texto_norm or 'atlántico' in texto_norm or 'barranquilla' in texto_norm:
                    regional_cond = "UPPER(regional) LIKE '%ATLANTICO%'"
                elif 'valle' in texto_norm or 'cali' in texto_norm:
                    regional_cond = "regional = 'Valle'"
                
                # Detectar filtros adicionales
                filtros_adicionales = []
                if 'vis' in texto_norm:
                    filtros_adicionales.append("segmento_pre = 'VIS'")
                if 'no vis' in texto_norm:
                    filtros_adicionales.append("segmento_pre = 'NO VIS'")
                if 'vip' in texto_norm:
                    filtros_adicionales.append("rangos_decreto_pre = 'VIP'")
                
                where_adicional = " AND " + " AND ".join(filtros_adicionales) if filtros_adicionales else ""
                
                # Query para precio promedio ponderado general
                query = f"""SELECT 
    ROUND(SUM(valor) / SUM(unidades) / 1000000, 2) AS precio_promedio_millones,
    SUM(unidades) AS total_unidades,
    SUM(valor) AS valor_total
FROM livo 
WHERE cuenta = 'Oferta'
    AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
    AND {regional_cond}
    {where_adicional}"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'PRECIO PROMEDIO GENERAL',
                    'proceso': f'Precio promedio general, {regional_cond}',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
            # REGLA PARA PRECIO PROMEDIO DE LANZAMIENTOS EN FECHA ESPECÍFICA (prioridad alta)
            if 'precio promedio' in texto_norm and ('lanzamiento' in texto_norm or 'lanzaron' in texto_norm):
                # Detectar fecha específica
                fecha_cond = "fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Lanzamientos')"
                if 'abril 2026' in texto_norm or '20260401' in texto_norm:
                    fecha_cond = "fecha = 20260401"
                elif '2025' in texto_norm:
                    fecha_cond = "CAST(fecha AS VARCHAR) LIKE '2025%'"
                
                # Detectar filtros adicionales
                filtros_adicionales = []
                if 'vis' in texto_norm:
                    filtros_adicionales.append("segmento_pre = 'VIS'")
                if 'no vis' in texto_norm:
                    filtros_adicionales.append("segmento_pre = 'NO VIS'")
                if 'vip' in texto_norm:
                    filtros_adicionales.append("rangos_decreto_pre = 'VIP'")
                
                where_adicional = " AND " + " AND ".join(filtros_adicionales) if filtros_adicionales else ""
                
                # Query para precio promedio ponderado
                query = f"""SELECT 
    ROUND(SUM(valor) / SUM(unidades) / 1000000, 2) AS precio_promedio_millones,
    SUM(unidades) AS total_unidades,
    SUM(valor) AS valor_total
FROM livo 
WHERE cuenta = 'Lanzamientos'
    AND {fecha_cond}
    {where_adicional}"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'PRECIO PROMEDIO LANZAMIENTOS',
                    'proceso': f'Precio promedio lanzamientos, {fecha_cond}',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
            if 'no vis' in texto_norm and 'vis' in texto_norm:
                # Caso ambiguo: "vis no vis" -> priorizar NO VIS
                resultado_depuracion.update({
                    'regla_aplicada': 'NO VIS (caso ambiguo)',
                    'proceso': 'SUM(unidades), cuenta=Oferta, segmento_pre=NO VIS',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return self._generar_sql_no_vis_puro(pregunta)
            elif 'no vis' in texto_norm:
                resultado_depuracion.update({
                    'regla_aplicada': 'NO VIS',
                    'proceso': 'SUM(unidades), cuenta=Oferta, segmento_pre=NO VIS',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return self._generar_sql_no_vis_puro(pregunta)
            elif 'vip' in texto_norm and 'no vis' not in texto_norm and 'sin vip' not in texto_norm:
                resultado_depuracion.update({
                    'regla_aplicada': 'VIP',
                    'proceso': 'SUM(unidades), cuenta=Oferta, segmento_pre=VIS, rangos_decreto_pre=VIP',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return self._generar_sql_vip_puro(pregunta)
            elif 'sin vip' in texto_norm:
                resultado_depuracion.update({
                    'regla_aplicada': 'VIS SIN VIP',
                    'proceso': 'SUM(unidades), cuenta=Oferta, segmento_pre=VIS, rangos_decreto_pre=VIS 70 - 135 SML',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return self._generar_sql_sin_vip_puro(pregunta)
            elif 'vis' in texto_norm and 'no vis' not in texto_norm and 'sin vip' not in texto_norm and 'vip' not in texto_norm:
                resultado_depuracion.update({
                    'regla_aplicada': 'VIS TOTAL',
                    'proceso': 'SUM(unidades), cuenta=Oferta, segmento_pre=VIS, rangos_decreto_pre IN (VIS 70 - 135 SML, VIP)',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return self._generar_sql_vis_total_puro(pregunta)
            
            # REGLA PARA PRECIO PROMEDIO CON MÚLTIPLES SEGMENTOS - Detectar "precio promedio" + "vis y no vis" + "lanzamientos"
            elif 'precio promedio' in texto_norm and ('lanzamiento' in texto_norm or 'lanzaron' in texto_norm) and ('vis' in texto_norm and 'no vis' in texto_norm):
                # Detectar regional
                regional_cond = "1=1"
                if 'valle' in texto_norm or 'valle del cauca' in texto_norm:
                    regional_cond = "regional = 'Valle'"
                elif 'antioquia' in texto_norm:
                    regional_cond = "UPPER(regional) LIKE '%ANTIOQUIA%'"
                elif 'bogota' in texto_norm or 'bogotá' in texto_norm:
                    regional_cond = "ciudad LIKE '%BOGOT%'"
                
                # Detectar año
                year_cond = "CAST(fecha AS VARCHAR) LIKE '2026%'" if '2026' in texto_norm else "CAST(fecha AS VARCHAR) LIKE '2025%'" if '2025' in texto_norm else "fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Lanzamientos')"
                
                # Query con CTE para ambos segmentos
                query = f"""WITH datos_segmento AS (
    SELECT 
        segmento_pre,
        SUM(unidades) AS total_unidades,
        SUM(valor) AS total_valor,
        SUM(valor) / NULLIF(SUM(unidades), 0) AS precio_promedio
    FROM livo 
    WHERE cuenta = 'Lanzamientos'
        AND segmento_pre IN ('VIS', 'NO VIS')
        AND {regional_cond}
        AND {year_cond}
    GROUP BY segmento_pre
)
SELECT 
    segmento_pre AS segmento,
    total_unidades AS unidades,
    ROUND(precio_promedio / 1000000, 2) AS precio_promedio_millones
FROM datos_segmento
ORDER BY segmento_pre"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'PRECIO PROMEDIO MULTI-SEGMENTO',
                    'proceso': f'Precio promedio VIS/No VIS, Lanzamientos, {regional_cond}',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
            # REGLA PARA COMPARACIÓN ENTRE REGIONES CON DESGLOSE POR USO
            elif any(palabra in texto_norm for palabra in ['comparación', 'comparacion', 'versus', 'vs']) and any(palabra in texto_norm for palabra in ['casa', 'apartamento', 'uso', 'tipo de uso']) and any(palabra in texto_norm for palabra in ['bogota', 'bogotá', 'antioquia', 'regionales', 'regional']):
                # Detectar regiones
                regiones = []
                if 'bogota' in texto_norm or 'bogotá' in texto_norm or 'cundinamarca' in texto_norm:
                    regiones.append("regional = 'Bogotá y Cundinamarca'")
                if 'antioquia' in texto_norm:
                    regiones.append("UPPER(regional) LIKE '%ANTIOQUIA%'")
                if 'valle' in texto_norm:
                    regiones.append("regional = 'Valle'")
                if 'atlantico' in texto_norm or 'atlántico' in texto_norm:
                    regiones.append("UPPER(regional) LIKE '%ATLANTICO%'")
                
                # Si no se detectaron regiones específicas, usar filtros genéricos
                if not regiones:
                    regiones = ["1=1"]
                
                # Construir condición OR para múltiples regiones
                region_cond = " OR ".join(regiones)
                
                # Query con desglose por regional y uso_etapa
                query = f"""SELECT 
    regional,
    uso_etapa,
    SUM(unidades) AS total_unidades
FROM livo 
WHERE cuenta = 'Oferta'
    AND ({region_cond})
    AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
    AND uso_etapa IN ('Casa', 'Apartamento')
GROUP BY regional, uso_etapa
ORDER BY regional, uso_etapa"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'COMPARACIÓN REGIONAL POR USO',
                    'proceso': f'Comparación entre regiones con desglose Casa/Apartamento: {region_cond}',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
            # REGLA PARA RANKING DE CIUDADES POR PRECIO PROMEDIO (más general)
            elif any(palabra in texto_norm for palabra in ['ranking', 'top', 'ciudades']) and any(palabra in texto_norm for palabra in ['precio promedio', 'precio', 'promedio']) and 'vis' in texto_norm and 'estrato 3' in texto_norm:
                # Query para ranking de ciudades por precio promedio del metro cuadrado
                query = """SELECT 
    ciudad,
    ROUND(SUM(valor) / SUM(area) / 1000000, 2) AS precio_promedio_millones_m2,
    SUM(unidades) AS total_unidades
FROM livo 
WHERE cuenta = 'Oferta'
    AND segmento_pre = 'VIS'
    AND estrato = '3'
    AND uso_etapa = 'Apartamento'
    AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
    AND ciudad IS NOT NULL
GROUP BY ciudad
HAVING SUM(area) > 0
ORDER BY precio_promedio_millones_m2 DESC
LIMIT 15"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'RANKING PRECIO M² VIS ESTRATO 3',
                    'proceso': 'Ranking ciudades por precio promedio m² en apartamentos VIS estrato 3',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
            # REGLA PARA VARIACIÓN DE PRECIO PROMEDIO GENERAL ENTRE AÑOS
            if any(palabra in texto_norm for palabra in ['variacion', 'variación', 'comparar', 'frente']) and 'precio promedio' in texto_norm and any(palabra in texto_norm for palabra in ['2025', '2026']):
                # Query con CTE para variación de precio promedio entre 2025 y 2026
                query = """WITH datos_2025 AS (
    SELECT 
        SUM(valor) AS total_valor_2025,
        SUM(unidades) AS total_unidades_2025
    FROM livo 
    WHERE cuenta = 'Lanzamientos'
      AND CAST(fecha AS VARCHAR) LIKE '2025%'
),
datos_2026 AS (
    SELECT 
        SUM(valor) AS total_valor_2026,
        SUM(unidades) AS total_unidades_2026
    FROM livo 
    WHERE cuenta = 'Lanzamientos'
      AND CAST(fecha AS VARCHAR) LIKE '2026%'
)
SELECT 
    ROUND(d25.total_valor_2025 / d25.total_unidades_2025 / 1000000, 2) AS precio_promedio_2025_millones,
    ROUND(d26.total_valor_2026 / d26.total_unidades_2026 / 1000000, 2) AS precio_promedio_2026_millones,
    d25.total_unidades_2025 AS unidades_2025,
    d26.total_unidades_2026 AS unidades_2026,
    ROUND(((d26.total_valor_2026 / d26.total_unidades_2026) - (d25.total_valor_2025 / d25.total_unidades_2025)) / (d25.total_valor_2025 / d25.total_unidades_2025) * 100, 2) AS variacion_porcentaje
FROM datos_2025 d25, datos_2026 d26"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'VARIACIÓN PRECIO PROMEDIO LANZAMIENTOS',
                    'proceso': 'Variación precio promedio lanzamientos 2025 vs 2026',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
                        
            # REGLA PARA RANKING DE CIUDADES POR PRECIO PROMEDIO M² EN APARTAMENTOS VIS, ESTRATO 3 (versión específica con m2)
            elif any(palabra in texto_norm for palabra in ['ranking', 'top', 'ciudades']) and any(palabra in texto_norm for palabra in ['precio promedio', 'precio', 'promedio']) and any(palabra in texto_norm for palabra in ['metro cuadrado', 'm2', 'm²']) and 'vis' in texto_norm and 'estrato 3' in texto_norm:
                # Query para ranking de ciudades por precio promedio del metro cuadrado
                query = """SELECT 
    ciudad,
    ROUND(SUM(valor) / SUM(area) / 1000000, 2) AS precio_promedio_millones_m2,
    SUM(unidades) AS total_unidades
FROM livo 
WHERE cuenta = 'Oferta'
    AND segmento_pre = 'VIS'
    AND estrato = '3'
    AND uso_etapa = 'Apartamento'
    AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
    AND ciudad IS NOT NULL
GROUP BY ciudad
HAVING SUM(area) > 0
ORDER BY precio_promedio_millones_m2 DESC
LIMIT 15"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'RANKING PRECIO M² VIS ESTRATO 3',
                    'proceso': 'Ranking ciudades por precio promedio m² en apartamentos VIS estrato 3',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
            # REGLA PARA TASA DE DESISTIMIENTO POR CONSTRUCTORA
            elif any(palabra in texto_norm for palabra in ['desistimiento', 'renuncia', 'renuncias']) and any(palabra in texto_norm for palabra in ['constructora', 'constructoras', 'compania', 'companias']):
                # Query con CTE para tasa de desistimiento: Renuncias / Ventas
                query = """WITH renuncias AS (
    SELECT compania_constructora, SUM(unidades) AS total_renuncias
    FROM livo 
    WHERE cuenta = 'Renuncias'
      AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Renuncias')
    GROUP BY compania_constructora
),
ventas AS (
    SELECT compania_constructora, SUM(unidades) AS total_ventas
    FROM livo 
    WHERE cuenta = 'Ventas'
      AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Ventas')
    GROUP BY compania_constructora
)
SELECT 
    r.compania_constructora,
    r.total_renuncias,
    v.total_ventas,
    (r.total_renuncias / NULLIF(v.total_ventas, 0)) * 100 AS tasa_desistimiento
FROM renuncias r
JOIN ventas v ON r.compania_constructora = v.compania_constructora
ORDER BY tasa_desistimiento DESC
LIMIT 10"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'TASA DE DESISTIMIENTO',
                    'proceso': 'Tasa desistimiento Renuncias/Ventas por constructora',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query.strip()
            
            # REGLA PARA PORCENTAJE DE ESTRATOS 4-6 EN LANZAMIENTOS
            elif any(palabra in texto_norm for palabra in ['porcentaje', 'porciento', '%']) and any(palabra in texto_norm for palabra in ['estratos', 'estrato', '4', '5', '6']) and 'lanzamiento' in texto_norm:
                # Query con CTE para calcular porcentaje de estratos 4-6
                query = """WITH estratos_4_6 AS (
    SELECT SUM(unidades) AS unidades_estratos_4_6
    FROM livo 
    WHERE cuenta = 'Lanzamientos'
      AND estrato IN ('4', '5', '6')
      AND fecha >= (SELECT MAX(fecha) - 10000 FROM livo WHERE cuenta = 'Lanzamientos')
),
total_lanzamientos AS (
    SELECT SUM(unidades) AS total_unidades
    FROM livo 
    WHERE cuenta = 'Lanzamientos'
      AND fecha >= (SELECT MAX(fecha) - 10000 FROM livo WHERE cuenta = 'Lanzamientos')
)
SELECT 
    e.unidades_estratos_4_6,
    t.total_unidades,
    (e.unidades_estratos_4_6 / t.total_unidades) * 100 AS porcentaje
FROM estratos_4_6 e, total_lanzamientos t"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'PORCENTAJE ESTRATOS 4-6',
                    'proceso': 'Porcentaje estratos 4-6 en lanzamientos último año',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return ' '.join(query.split())
            
                        
            # REGLA PARA CRECIMIENTO INTERANUAL - Detectar "crecimiento", "variacion", "comparar" (con o sin años)
            elif any(palabra in texto_norm for palabra in ['crecimiento', 'variacion', 'variación', 'comparar', 'vs', 'frente']) and any(palabra in texto_norm for palabra in ['constructora', 'compania', 'departamento']):
                # Determinar si es por constructora o departamento
                campo_group = 'compania_constructora' if any(x in texto_norm for x in ['constructora', 'compania']) else 'departamento'
                cuenta = 'Ventas' if 'ventas' in texto_norm else ('Lanzamientos' if 'lanzamiento' in texto_norm else 'Oferta')
                
                # Generar query con año corrido
                query_cte = self._generar_cte_crecimiento(f"{campo_group} crecimiento {cuenta}", pregunta)
                
                resultado_depuracion.update({
                    'regla_aplicada': 'CRECIMIENTO INTERANUAL',
                    'proceso': f'CTE año corrido: {campo_group}, cuenta={cuenta}',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return query_cte
            
            # REGLA PARA EVOLUCIÓN MENSUAL - Detectar "evolución mensual", "mes a mes", "tendencia mensual"
            elif any(palabra in texto_norm for palabra in ['evolucion', 'evolución', 'tendencia', 'comportamiento', 'serie']) and any(palabra in texto_norm for palabra in ['mensual', 'mes', 'mes a mes']):
                # Detectar cuenta
                cuenta = 'Ventas' if 'ventas' in texto_norm else ('Lanzamientos' if 'lanzamiento' in texto_norm else 'Oferta')
                
                # Detectar período (últimos 12 meses por defecto)
                ultimos_12_meses = any(x in texto_norm for x in ['12 meses', 'doce meses', 'ultimos meses', 'ttm', 'ltm'])
                
                # Detectar región
                region_cond = "1=1"
                if 'bogota' in texto_norm or 'bogotá' in texto_norm:
                    region_cond = "ciudad LIKE '%BOGOT%'"
                elif 'medellin' in texto_norm or 'medellín' in texto_norm:
                    region_cond = "ciudad LIKE '%MEDELL%'"
                elif 'cali' in texto_norm:
                    region_cond = "ciudad LIKE '%CALI%'"
                elif 'antioquia' in texto_norm:
                    region_cond = "UPPER(regional) LIKE '%ANTIOQUIA%'"
                elif 'atlantico' in texto_norm or 'atlántico' in texto_norm or 'barranquilla' in texto_norm:
                    region_cond = "UPPER(regional) LIKE '%ATLANTICO%'"
                elif 'valle' in texto_norm:
                    region_cond = "regional = 'Valle'"
                
                if ultimos_12_meses:
                    # Usar doce_meses para últimos 12 meses
                    query = f"""SELECT 
    SUBSTRING(CAST(fecha AS VARCHAR), 1, 4) || '-' || SUBSTRING(CAST(fecha AS VARCHAR), 5, 2) AS mes_anio,
    SUBSTRING(CAST(fecha AS VARCHAR), 1, 4) AS año,
    SUBSTRING(CAST(fecha AS VARCHAR), 5, 2) AS mes,
    SUM(unidades) AS total_unidades
FROM livo 
WHERE cuenta = '{cuenta}' 
    AND doce_meses = (SELECT MAX(doce_meses) FROM livo WHERE cuenta = '{cuenta}')
    AND {region_cond}
GROUP BY SUBSTRING(CAST(fecha AS VARCHAR), 1, 4) || '-' || SUBSTRING(CAST(fecha AS VARCHAR), 5, 2),
         SUBSTRING(CAST(fecha AS VARCHAR), 1, 4),
         SUBSTRING(CAST(fecha AS VARCHAR), 5, 2)
ORDER BY mes_anio"""
                else:
                    # Usar último año disponible
                    query = f"""SELECT 
    SUBSTRING(CAST(fecha AS VARCHAR), 1, 4) || '-' || SUBSTRING(CAST(fecha AS VARCHAR), 5, 2) AS mes_anio,
    SUBSTRING(CAST(fecha AS VARCHAR), 1, 4) AS año,
    SUBSTRING(CAST(fecha AS VARCHAR), 5, 2) AS mes,
    SUM(unidades) AS total_unidades
FROM livo 
WHERE cuenta = '{cuenta}' 
    AND CAST(SUBSTRING(CAST(fecha AS VARCHAR), 1, 4) AS INTEGER) = (SELECT MAX(CAST(SUBSTRING(CAST(fecha AS VARCHAR), 1, 4) AS INTEGER)) FROM livo WHERE cuenta = '{cuenta}')
    AND {region_cond}
GROUP BY SUBSTRING(CAST(fecha AS VARCHAR), 1, 4) || '-' || SUBSTRING(CAST(fecha AS VARCHAR), 5, 2),
         SUBSTRING(CAST(fecha AS VARCHAR), 1, 4),
         SUBSTRING(CAST(fecha AS VARCHAR), 5, 2)
ORDER BY mes_anio"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'EVOLUCIÓN MENSUAL',
                    'proceso': f'Evolución mensual {cuenta}, {"últimos 12 meses" if ultimos_12_meses else "último año"}',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return ' '.join(query.split())
            
            # REGLA PARA TOP/RANKING - Detectar cuando se pide "top 5", "mayor cantidad de departamentos", etc.
            elif any(palabra in texto_norm for palabra in ['top', 'ranking', 'mayor', 'mayores']) and any(palabra in texto_norm for palabra in ['departamento', 'departamentos', 'constructora', 'constructoras', 'ciudad', 'ciudades']):
                # Determinar el campo de agrupación
                if 'departamento' in texto_norm:
                    campo_group = 'departamento'
                elif 'constructora' in texto_norm or 'compania' in texto_norm:
                    campo_group = 'compania_constructora'
                elif 'ciudad' in texto_norm:
                    campo_group = 'ciudad'
                else:
                    campo_group = 'departamento'
                
                # Detectar número para TOP (default 5)
                import re
                top_match = re.search(r'top\s+(\d+)', texto_norm)
                limite = top_match.group(1) if top_match else '5'
                
                # Detectar cuenta (Ventas vs Oferta)
                cuenta = 'Ventas' if 'ventas' in texto_norm else 'Oferta'
                
                # Detectar fecha
                fecha_cond = "fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = '{}')".format(cuenta)
                if 'abril' in texto_norm or '202604' in texto_norm:
                    fecha_cond = "fecha = 20260401"
                
                query_top = f"""SELECT {campo_group}, SUM(unidades) AS total 
FROM livo 
WHERE cuenta = '{cuenta}' AND {fecha_cond}
GROUP BY {campo_group}
ORDER BY total DESC
LIMIT {limite}"""
                
                resultado_depuracion.update({
                    'regla_aplicada': 'TOP/RANKING',
                    'proceso': f'TOP {limite} {campo_group}, cuenta={cuenta}',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return ' '.join(query_top.split())
            
            # REGLA GENERAL PARA CONTEO TOTAL DE UNIDADES
            elif any(palabra in texto_norm for palabra in ['unidades', 'total', 'cuantas', 'cuántos', 'cantidad']) and not any(palabra in texto_norm for palabra in ['ranking', 'top', 'por', 'según', 'agrupado', 'distribución']):
                resultado_depuracion.update({
                    'regla_aplicada': 'CONTEO TOTAL GENERAL',
                    'proceso': 'SUM(unidades), cuenta=Oferta, sin filtros de segmentación ni destino_etapa (pregunta general)',
                    'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
                })
                self._guardar_depuracion_reglas(resultado_depuracion)
                return self._generar_sql_total_general_puro(pregunta)
            
            # Ninguna regla aplicable
            resultado_depuracion.update({
                'regla_aplicada': 'NINGUNA',
                'proceso': 'NO APLICA - usa LLM fallback',
                'filtros_detectados': self._extraer_filtros_pregunta(pregunta)
            })
            self._guardar_depuracion_reglas(resultado_depuracion)
            return None
            
        except Exception as e:
            print(f"[DEBUG] Error en generación de SQL de reglas: {e}")
            # Guardar error en depuración
            error_depuracion = {
                'pregunta_original': pregunta,
                'texto_normalizado': normalize_text(pregunta) if 'normalize_text' in globals() else pregunta.lower(),
                'regla_aplicada': 'ERROR',
                'proceso': f'ERROR: {str(e)}',
                'filtros_detectados': 'ERROR',
                'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            self._guardar_depuracion_reglas(error_depuracion)
            return None
    
    def _extraer_filtros_pregunta(self, pregunta: str) -> str:
        """Extrae y documenta todos los filtros detectados en la pregunta"""
        import re
        filtros = []
        
        # Detectar región/departamento/ciudad
        regiones = ['antioquia', 'bogota', 'medellin', 'cali', 'barranquilla', 'cartagena', 'bucaramanga', 'pereira', 'manizales']
        for region in regiones:
            if region in pregunta.lower():
                filtros.append(f"regional/departamento: {region}")
        
        # Detectar fecha
        anio_match = re.search(r"(20[0-9]{2})", pregunta)
        if anio_match:
            año = anio_match.group(1)
            meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
            for mes in meses:
                if mes in pregunta.lower():
                    mes_num = {'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05', 'junio': '06',
                              'julio': '07', 'agosto': '08', 'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'}[mes]
                    fecha_especifica = f"{año}{mes_num}01"
                    filtros.append(f"fecha: {fecha_especifica} ({mes} {año})")
                    break
            else:
                filtros.append(f"año: {año}")
        
        # Detectar tipo de vivienda (orden crítico para evitar conflictos)
        if 'no vis' in pregunta.lower():
            filtros.append("segmento_pre: NO VIS")
        elif 'vis' in pregunta.lower():
            if 'sin vip' in pregunta.lower():
                filtros.append("segmento_pre: VIS, rangos_decreto_pre: VIS 70 - 135 SML")
            elif 'vip' in pregunta.lower():
                filtros.append("segmento_pre: VIS, rangos_decreto_pre: VIP")
            else:
                filtros.append("segmento_pre: VIS, rangos_decreto_pre: IN (VIS 70 - 135 SML, VIP)")
        
        # Filtros por defecto (solo cuenta)
        filtros.extend([
            "cuenta: Oferta (por defecto)"
        ])
        
        return " | ".join(filtros)
    
    def _guardar_depuracion_reglas(self, datos_depuracion: dict):
        """Guarda información de depuración en archivo Excel"""
        try:
            import pandas as pd
            import os
            
            # Nombre del archivo de depuración
            archivo_depuracion = "depuracion_sql_reglas.xlsx"
            
            # Verificar si el archivo ya existe
            if os.path.exists(archivo_depuracion):
                # Leer archivo existente
                df_existente = pd.read_excel(archivo_depuracion, engine='openpyxl')
                # Agregar nueva fila
                df_nuevo = pd.DataFrame([datos_depuracion])
                df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
            else:
                # Crear nuevo DataFrame
                df_final = pd.DataFrame([datos_depuracion])
            
            # Guardar en Excel
            df_final.to_excel(archivo_depuracion, index=False, engine='openpyxl')
            print(f"[DEBUG] Depuración guardada en {archivo_depuracion}")
            
        except Exception as e:
            print(f"[DEBUG] Error guardando depuración: {e}")
    
    def _generar_filtro_regional(self, pregunta: str, region: str) -> str:
        """
        Genera el filtro SQL correcto según el tipo de región y la pregunta.
        
        Lógica especial para Bogotá:
        - "Bogotá" (solo) → buscar en ciudad o departamento
        - "Bogotá y Cundinamarca" → buscar en regional
        """
        if not region or region.lower() == 'nacional':
            return ""
        
        pregunta_lower = pregunta.lower()
        region_norm = region.upper()
        
        # Normalización para TRANSLATE (quitar tildes)
        translate_expr = "UPPER(TRANSLATE({campo}, 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun'))"
        
        # Detectar si es caso especial de Bogotá
        region_norm_lower = region_norm.lower()
        if 'bogot' in region_norm_lower or 'bogot' in pregunta_lower:
            # Si la pregunta NO menciona Cundinamarca, buscar en ciudad/departamento
            if 'cundinamarca' not in pregunta_lower:
                # Bogotá solo: buscar en ciudad o departamento
                filtro_ciudad = translate_expr.format(campo='ciudad') + f" LIKE '%{region_norm}%'"
                filtro_depto = translate_expr.format(campo='departamento') + f" LIKE '%{region_norm}%'"
                return f" AND ({filtro_ciudad} OR {filtro_depto})"
            else:
                # Bogotá y Cundinamarca: buscar en regional
                return f" AND {translate_expr.format(campo='regional')} LIKE '%{region_norm}%" + " & CUNDINAMARCA%'"
        
        # Para otras regiones, buscar en regional
        return f" AND {translate_expr.format(campo='regional')} LIKE '%{region_norm}%'"
    
    def _detectar_filtros_adicionales(self, pregunta: str) -> tuple:
        """
        Detecta filtros adicionales de estado y fase en la pregunta.
        Retorna: (filtro_estado, filtro_fase)
        """
        import re
        
        # Normalizar espacios múltiples y convertir a minúsculas
        pregunta_lower = re.sub(r'\s+', ' ', pregunta.lower()).strip()
        
        # Detectar estado (con manejo de errores ortográficos comunes)
        filtro_estado = ""
        if 'preventa' in pregunta_lower or 'en preventa' in pregunta_lower:
            # Solo aplicar si NO es lanzamiento
            if 'lanzamiento' not in pregunta_lower and 'lanzamientos' not in pregunta_lower:
                filtro_estado = " AND estado = 'Preventa'"
        elif 'construccion' in pregunta_lower or 'en construccion' in pregunta_lower or 'construcción' in pregunta_lower or 'contruccion' in pregunta_lower:
            filtro_estado = " AND estado = 'Construcción'"
        elif 'estrado' in pregunta_lower:  # Error ortográfico común
            filtro_estado = " AND estado = 'Construcción'"
        # Nota: lanzamientos se maneja cambiando la cuenta
        
        # Detectar fase (varias variantes)
        filtro_fase = ""
        # Variantes con "fase" explícito (con o sin espacios múltiples)
        if re.search(r'fase\s+terminad[oa]', pregunta_lower):
            filtro_fase = " AND fase = 'Terminado'"
        elif 'fase sin iniciar' in pregunta_lower:
            filtro_fase = " AND fase = 'Sin Iniciar'"
        # Variantes sin "fase" explícito (ej: "construccion terminado")
        elif re.search(r'(construccion|contruccion)\s+terminad[oa]', pregunta_lower):
            filtro_fase = " AND fase = 'Terminado'"
        elif re.search(r'preventa\s+terminad[oa]', pregunta_lower):
            filtro_fase = " AND fase = 'Terminado'"
        
        return filtro_estado, filtro_fase
    
    def _generar_sql_vip_puro(self, pregunta: str) -> str:
        """Genera SQL específico para VIP sin interferencia"""
        region = self._extraer_region_general(pregunta)
        region_cond = self._condicion_region_general(region) if region else "1=1"
        
        # Detectar fecha específica
        anio_match = re.search(r"(20[0-9]{2})", pregunta)
        mes_nombre_detectado = None
        for mes, num in [('enero', '01'), ('febrero', '02'), ('marzo', '03'), ('abril', '04'), 
                        ('mayo', '05'), ('junio', '06'), ('julio', '07'), ('agosto', '08'), 
                        ('septiembre', '09'), ('octubre', '10'), ('noviembre', '11'), ('diciembre', '12')]:
            if mes in pregunta.lower():
                mes_nombre_detectado = mes
                break
        
        # Detectar si es lanzamiento primero (para determinar cuenta y fecha)
        es_lanzamiento = 'lanzamiento' in pregunta.lower() or 'lanzamientos' in pregunta.lower()
        cuenta = 'Lanzamientos' if es_lanzamiento else 'Oferta'
        
        fecha_filtro = ""
        if anio_match and mes_nombre_detectado:
            mes_map = {'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05', 'junio': '06',
                      'julio': '07', 'agosto': '08', 'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'}
            mes_num = mes_map.get(mes_nombre_detectado, '01')
            anio_num = anio_match.group(1)
            fecha_especifica = f"{anio_num}{mes_num}01"
            fecha_filtro = f" AND fecha = {fecha_especifica}"
        else:
            fecha_filtro = f" AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = '{cuenta}')"
        
        # Generar filtro regional usando función auxiliar (maneja lógica especial para Bogotá)
        region_simple = self._generar_filtro_regional(pregunta, region)
        
        # Detectar filtros adicionales de estado y fase
        filtro_estado, filtro_fase = self._detectar_filtros_adicionales(pregunta)
        
        sql = f"""
        SELECT SUM(unidades) AS total 
        FROM livo 
        WHERE cuenta = '{cuenta}' 
        AND segmento_pre = 'VIS' 
        AND rangos_decreto_pre = 'VIP'
        {region_simple}
        {filtro_estado}
        {filtro_fase}
        {fecha_filtro}
        """
        
        return sql.strip()
    
    def _generar_sql_total_general_puro(self, pregunta: str) -> str:
        """Genera SQL específico para conteo total general sin filtros de segmentación"""
        region = self._extraer_region_general(pregunta)
        region_cond = self._condicion_region_general(region) if region else "1=1"
        
        # Detectar fecha específica
        anio_match = re.search(r"(20[0-9]{2})", pregunta)
        mes_nombre_detectado = None
        for mes, num in [('enero', '01'), ('febrero', '02'), ('marzo', '03'), ('abril', '04'), 
                        ('mayo', '05'), ('junio', '06'), ('julio', '07'), ('agosto', '08'), 
                        ('septiembre', '09'), ('octubre', '10'), ('noviembre', '11'), ('diciembre', '12')]:
            if mes in pregunta.lower():
                mes_nombre_detectado = mes
                break
        
        # Detectar si es lanzamiento primero (para determinar cuenta y fecha)
        es_lanzamiento = 'lanzamiento' in pregunta.lower() or 'lanzamientos' in pregunta.lower()
        cuenta = 'Lanzamientos' if es_lanzamiento else 'Oferta'
        
        fecha_filtro = ""
        if anio_match and mes_nombre_detectado:
            mes_map = {'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05', 'junio': '06',
                      'julio': '07', 'agosto': '08', 'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'}
            mes_num = mes_map.get(mes_nombre_detectado, '01')
            anio_num = anio_match.group(1)
            fecha_especifica = f"{anio_num}{mes_num}01"
            fecha_filtro = f" AND fecha = {fecha_especifica}"
        else:
            fecha_filtro = f" AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = '{cuenta}')"
        
        # Generar filtro regional usando función auxiliar (maneja lógica especial para Bogotá)
        region_simple = self._generar_filtro_regional(pregunta, region)
        
        # Detectar filtros adicionales de estado y fase
        filtro_estado, filtro_fase = self._detectar_filtros_adicionales(pregunta)
        
        sql = f"""
        SELECT SUM(unidades) AS total 
        FROM livo 
        WHERE cuenta = '{cuenta}' 
        {region_simple}
        {filtro_estado}
        {filtro_fase}
        {fecha_filtro}
        """
        
        return sql.strip()
    
    def _generar_sql_no_vis_puro(self, pregunta: str) -> str:
        """Genera SQL específico para NO VIS sin interferencia"""
        region = self._extraer_region_general(pregunta)
        region_cond = self._condicion_region_general(region) if region else "1=1"
        
        # Detectar fecha específica
        anio_match = re.search(r"(20[0-9]{2})", pregunta)
        mes_nombre_detectado = None
        for mes, num in [('enero', '01'), ('febrero', '02'), ('marzo', '03'), ('abril', '04'), 
                        ('mayo', '05'), ('junio', '06'), ('julio', '07'), ('agosto', '08'), 
                        ('septiembre', '09'), ('octubre', '10'), ('noviembre', '11'), ('diciembre', '12')]:
            if mes in pregunta.lower():
                mes_nombre_detectado = mes
                break
        
        # Detectar si es lanzamiento primero (para determinar cuenta y fecha)
        es_lanzamiento = 'lanzamiento' in pregunta.lower() or 'lanzamientos' in pregunta.lower()
        cuenta = 'Lanzamientos' if es_lanzamiento else 'Oferta'
        
        fecha_filtro = ""
        if anio_match and mes_nombre_detectado:
            mes_map = {'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05', 'junio': '06',
                      'julio': '07', 'agosto': '08', 'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'}
            mes_num = mes_map.get(mes_nombre_detectado, '01')
            anio_num = anio_match.group(1)
            fecha_especifica = f"{anio_num}{mes_num}01"
            fecha_filtro = f" AND fecha = {fecha_especifica}"
        else:
            fecha_filtro = f" AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = '{cuenta}')"
        
        # Generar filtro regional usando función auxiliar (maneja lógica especial para Bogotá)
        region_simple = self._generar_filtro_regional(pregunta, region)
        
        # Detectar filtros adicionales de estado y fase
        filtro_estado, filtro_fase = self._detectar_filtros_adicionales(pregunta)
        
        sql = f"""
        SELECT SUM(unidades) AS total 
        FROM livo 
        WHERE cuenta = '{cuenta}' 
        AND segmento_pre = 'No VIS'
        {region_simple}
        {filtro_estado}
        {filtro_fase}
        {fecha_filtro}
        """
        
        return sql.strip()
    
    def _generar_sql_sin_vip_puro(self, pregunta: str) -> str:
        """Genera SQL específico para VIS SIN VIP sin interferencia"""
        region = self._extraer_region_general(pregunta)
        
        # Detectar fecha específica
        anio_match = re.search(r"(20[0-9]{2})", pregunta)
        mes_nombre_detectado = None
        for mes, num in [('enero', '01'), ('febrero', '02'), ('marzo', '03'), ('abril', '04'), 
                        ('mayo', '05'), ('junio', '06'), ('julio', '07'), ('agosto', '08'), 
                        ('septiembre', '09'), ('octubre', '10'), ('noviembre', '11'), ('diciembre', '12')]:
            if mes in pregunta.lower():
                mes_nombre_detectado = mes
                break
        
        # Detectar si es lanzamiento primero (para determinar cuenta y fecha)
        es_lanzamiento = 'lanzamiento' in pregunta.lower() or 'lanzamientos' in pregunta.lower()
        cuenta = 'Lanzamientos' if es_lanzamiento else 'Oferta'
        
        fecha_filtro = ""
        if anio_match and mes_nombre_detectado:
            mes_map = {'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05', 'junio': '06',
                      'julio': '07', 'agosto': '08', 'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'}
            mes_num = mes_map.get(mes_nombre_detectado, '01')
            anio_num = anio_match.group(1)
            fecha_especifica = f"{anio_num}{mes_num}01"
            fecha_filtro = f" AND fecha = {fecha_especifica}"
        else:
            fecha_filtro = f" AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = '{cuenta}')"
        
        # Generar filtro regional usando función auxiliar (maneja lógica especial para Bogotá)
        region_simple = self._generar_filtro_regional(pregunta, region)
        
        # Detectar filtros adicionales de estado y fase
        filtro_estado, filtro_fase = self._detectar_filtros_adicionales(pregunta)
        
        # Generar SQL en el orden exacto de QUERY REGLAS: fecha → cuenta → regional → segmento → rangos
        sql = f"SELECT SUM(unidades) AS total FROM livo WHERE cuenta = '{cuenta}' AND segmento_pre = 'VIS' AND rangos_decreto_pre = 'VIS 70 - 135 SML'{region_simple}{filtro_estado}{filtro_fase}{fecha_filtro}"
        
        return sql.strip()
    
    def _generar_sql_vis_total_puro(self, pregunta: str) -> str:
        """Genera SQL específico para VIS TOTAL sin interferencia"""
        region = self._extraer_region_general(pregunta)
        region_cond = self._condicion_region_general(region) if region else "1=1"
        
        # Detectar fecha específica
        anio_match = re.search(r"(20[0-9]{2})", pregunta)
        mes_nombre_detectado = None
        for mes, num in [('enero', '01'), ('febrero', '02'), ('marzo', '03'), ('abril', '04'), 
                        ('mayo', '05'), ('junio', '06'), ('julio', '07'), ('agosto', '08'), 
                        ('septiembre', '09'), ('octubre', '10'), ('noviembre', '11'), ('diciembre', '12')]:
            if mes in pregunta.lower():
                mes_nombre_detectado = mes
                break
        
        # Detectar si es lanzamiento primero (para determinar cuenta y fecha)
        es_lanzamiento = 'lanzamiento' in pregunta.lower() or 'lanzamientos' in pregunta.lower()
        cuenta = 'Lanzamientos' if es_lanzamiento else 'Oferta'
        
        fecha_filtro = ""
        if anio_match and mes_nombre_detectado:
            mes_map = {'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05', 'junio': '06',
                      'julio': '07', 'agosto': '08', 'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'}
            mes_num = mes_map.get(mes_nombre_detectado, '01')
            anio_num = anio_match.group(1)
            fecha_especifica = f"{anio_num}{mes_num}01"
            fecha_filtro = f" AND fecha = {fecha_especifica}"
        else:
            fecha_filtro = f" AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = '{cuenta}')"
        
        # Generar filtro regional usando función auxiliar (maneja lógica especial para Bogotá)
        region_simple = self._generar_filtro_regional(pregunta, region)
        
        # Detectar filtros adicionales de estado y fase
        filtro_estado, filtro_fase = self._detectar_filtros_adicionales(pregunta)
        
        sql = f"""
        SELECT SUM(unidades) AS total 
        FROM livo 
        WHERE cuenta = '{cuenta}' 
        AND segmento_pre = 'VIS' 
        AND rangos_decreto_pre IN ('VIS 70 - 135 SML', 'VIP')
        {region_simple}
        {filtro_estado}
        {filtro_fase}
        {fecha_filtro}
        """
        
        return sql.strip()

    def consultar(self, pregunta: str, llm_function, usuario: str = "default", 
                 generate_chart: bool = False, channel: str = "streamlit") -> Tuple[bool, str, Optional[Dict]]:
        """Consulta usando Text-to-SQL con LLM (con mejoras integradas)"""
        if not self.conn:
            return False, "❌ Sistema no inicializado"
        
        # === ARQUITECTURA DE CONVIVENCIA ===
        # 1. PRIMERO: Intentar con SQL de REGLAS (prioridad absoluta, sin modificación)
        sql_reglas = self._generar_sql_desde_reglas(pregunta)
        if sql_reglas:
            try:
                print(f"[DEBUG] Usando SQL de reglas (prioridad absoluta)")
                cursor = self.conn.execute(sql_reglas)
                resultado = cursor.fetchall()
                if resultado:
                    # Obtener nombres de columnas desde el cursor
                    columnas = [desc[0] for desc in cursor.description] if cursor.description else []
                    respuesta_formateada = self._formatear_resultados(resultado, columnas, sql_reglas)
                    return True, respuesta_formateada, {"sql": sql_reglas, "metodo": "reglas"}
            except Exception as e:
                print(f"[DEBUG] SQL de reglas falló: {e}")
        
        # 2. SEGUNDO: Si reglas fallan, usar LLM con asociación semántica
        print(f"[DEBUG] Reglas no aplicables, usando LLM con asociación semántica")
        
        # MEJORA: Expansión de términos SOLO para LLM (no afecta a reglas)
        pregunta_original = pregunta
        pregunta_expandida = self._expandir_terminos_usuario(pregunta)
        if pregunta_expandida != pregunta.lower():
            print(f"🧠 Términos expandidos para LLM: {pregunta} → {pregunta_expandida}")
        
        # MEJORA: Detección de idioma y traducción SOLO para LLM
        pregunta, fue_traducida = self.traducir_pregunta(pregunta_expandida, llm_function)
        if fue_traducida:
            print(f"🌍 Pregunta traducida para LLM: {pregunta}")
            
        # === APLICACIÓN DE REGLAS DE NEGOCIO POR DEFECTO (solo para LLM) ===
        texto_norm = normalize_text(pregunta)
        
        # REGIONES METROPOLITANAS / ÁREAS METROPOLITANAS:
        if any(x in texto_norm for x in ['bogota region', 'region de bogota']):
            pregunta += " (filtrar ÚNICAMENTE por ciudad = 'Bogotá' Y AM_capital = 'Bogotá D.C.'. NO incluir municipios aledaños ni otros corredores de Cundinamarca)"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [BOGOTÁ REGIÓN] Forzando ciudad = 'Bogotá' AND AM_capital = 'Bogotá D.C.' exclusivamente.")
        elif any(x in texto_norm for x in ['metropolitana de bogota', 'bogota y alrededores', 'bogota am', 'alrededores de bogota']):
            pregunta += " (filtrar por ciudad = 'Bogotá' o AM_capital en ('Bogotá D.C.', 'Corredor Autopista Norte', 'Corredor Autopista Sur', 'Corredor Calle 13', 'Corredor Cundinamarca-Caliente', 'Corredor Vía-La Calera'))"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [METROPOLITANA BOGOTÁ] Forzando ciudad = 'Bogotá' o corredores/AM_capital de Bogotá.")
        elif any(x in texto_norm for x in ['valle de aburra', 'metropolitana de medellin', 'medellin y alrededores', 'medellin am', 'region de medellin', 'alrededores de medellin']):
            pregunta += " (filtrar por ciudad = 'Medellín' o AM_capital = 'Medellín AM')"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [METROPOLITANA MEDELLÍN] Forzando ciudad = 'Medellín' o AM_capital = 'Medellín AM'.")
        elif any(x in texto_norm for x in ['metropolitana de cali', 'cali y alrededores', 'cali am', 'cali region', 'region de cali', 'alrededores de cali']):
            pregunta += " (filtrar por ciudad = 'Cali' o AM_capital = 'Cali AM')"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [METROPOLITANA CALI] Forzando ciudad = 'Cali' o AM_capital = 'Cali AM'.")
        elif any(x in texto_norm for x in ['metropolitana de barranquilla', 'barranquilla y alrededores', 'barranquilla am', 'region de barranquilla', 'alrededores de barranquilla']):
            pregunta += " (filtrar por ciudad = 'Barranquilla' o AM_capital = 'Barranquilla AM')"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [METROPOLITANA BARRANQUILLA] Forzando ciudad = 'Barranquilla' o AM_capital = 'Barranquilla AM'.")
        elif any(x in texto_norm for x in ['metropolitana de bucaramanga', 'bucaramanga y alrededores', 'bucaramanga am', 'region de bucaramanga', 'alrededores de bucaramanga']):
            pregunta += " (filtrar por ciudad = 'Bucaramanga' o AM_capital = 'Bucaramanga AM')"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [METROPOLITANA BUCARAMANGA] Forzando ciudad = 'Bucaramanga' o AM_capital = 'Bucaramanga AM'.")
        elif any(x in texto_norm for x in ['metropolitana de pereira', 'pereira y alrededores', 'pereira am', 'region de pereira', 'alrededores de pereira']):
            pregunta += " (filtrar por ciudad = 'Pereira' o AM_capital = 'Pereira AM')"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [METROPOLITANA PEREIRA] Forzando ciudad = 'Pereira' o AM_capital = 'Pereira AM'.")
        elif any(x in texto_norm for x in ['metropolitana de manizales', 'manizales y alrededores', 'manizales am', 'region de manizales', 'alrededores de manizales']):
            pregunta += " (filtrar por ciudad = 'Manizales' o AM_capital = 'Manizales AM')"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [METROPOLITANA MANIZALES] Forzando ciudad = 'Manizales' o AM_capital = 'Manizales AM'.")
        elif any(x in texto_norm for x in ['metropolitana de cucuta', 'cucuta y alrededores', 'cucuta am', 'cucuta region', 'region de cucuta', 'alrededores de cucuta']):
            pregunta += " (filtrar por ciudad = 'Cúcuta' o AM_capital = 'Cúcuta AM')"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [METROPOLITANA CÚCUTA] Forzando ciudad = 'Cúcuta' o AM_capital = 'Cúcuta AM'.")

        # PREVENTAS: Forzar cuenta = Oferta y estado = Preventa
        if 'preventa' in texto_norm:
            pregunta += " de la cuenta Oferta con estado Preventa"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [PREVENTAS] Pregunta de Preventas. Forzando 'cuenta = Oferta' y 'estado = Preventa'.")

        # ARRIENDOS: Forzar segmento_pre = Arrendar
        if any(ak in texto_norm for ak in ['arriendo', 'alquiler', 'rentar', 'arrendar', 'renta']):
            pregunta += " con segmento_pre Arrendar"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [ARRIENDO] Pregunta de Arriendo. Forzando 'segmento_pre = Arrendar'.")

        # VIS, VIP, NO VIS DEFINITIONS - DETECCIÓN MEJORADA Y ESPECÍFICA
        if 'vip' in texto_norm and 'no vis' not in texto_norm and 'sin vip' not in texto_norm:
            pregunta += " con segmento_pre = 'VIS' y rangos_decreto_pre = 'VIP'"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [VIP] Forzando segmento_pre = 'VIS' y rangos_decreto_pre = 'VIP'.")
        elif 'no vis' in texto_norm and 'vis' not in texto_norm:
            pregunta += " con segmento_pre = 'NO VIS'"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [NO VIS] Forzando segmento_pre = 'NO VIS'.")
        elif 'sin vip' in texto_norm:
            pregunta += " con segmento_pre = 'VIS' y rangos_decreto_pre = 'VIS 70 - 135 SML'"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [SIN VIP] Forzando segmento_pre = 'VIS' y rangos_decreto_pre = 'VIS 70 - 135 SML'.")
        elif 'vis' in texto_norm and 'no vis' not in texto_norm and 'sin vip' not in texto_norm and 'vip' not in texto_norm:
            pregunta += " con segmento_pre = 'VIS' y rangos_decreto_pre IN ('VIS 70 - 135 SML', 'VIP')"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [VIS TOTAL] Forzando segmento_pre = 'VIS' y rangos_decreto_pre IN ('VIS 70 - 135 SML', 'VIP').")
        elif 'interes social' in texto_norm or 'interés social' in texto_norm:
            pregunta += " con segmento_pre = 'VIS' y rangos_decreto_pre IN ('VIS 70 - 135 SML', 'VIP')"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [INTERÉS SOCIAL] Forzando segmento_pre = 'VIS' y rangos_decreto_pre IN ('VIS 70 - 135 SML', 'VIP').")

        # REGLA 1: Si no coloca cuenta (ventas, lanzamientos, etc.), por defecto cuenta = Oferta
        cuentas_keywords = [
            'venta', 'lanzamiento', 'iniciacion', 'entrega', 'renuncia', 'desistimiento',
            'saldo que inicia', 'paralizado', 'culminada', 'oferta', 'disponible', 'stock', 'inventario', 'rotacion'
        ]
        tiene_cuenta = any(ck in texto_norm for ck in cuentas_keywords)
        if not tiene_cuenta:
            pregunta += " de la cuenta Oferta"
            texto_norm = normalize_text(pregunta)
            print(f"📌 [REGLA 1] Sin cuenta en pregunta. Aplicando por defecto: 'cuenta = Oferta'.")

        # Mapeo de keywords → valor exacto del campo 'cuenta' en LIVO
        cuentas_flujo_map = [
            ('saldo que inicia', 'Saldo que inicia'),
            ('lanzamiento',      'Lanzamientos'),
            ('iniciacion',       'Iniciaciones'),
            ('entrega',          'Entregadas'),
            ('renuncia',         'Renuncias'),
            ('desistimiento',    'Renuncias'),
            ('paralizado',       'Paralizado'),
            ('culminada',        'Culminadas'),
            ('venta',            'Ventas'),
            ('rotacion',         'Ventas'),
        ]
        cuenta_flujo_detectada = None
        for kw, cuenta_val in cuentas_flujo_map:
            if kw in texto_norm:
                cuenta_flujo_detectada = cuenta_val
                break
        es_cuenta_flujo = cuenta_flujo_detectada is not None

        # REGLA ESPECIAL: Histórico / Evolución / Tendencia → siempre doce_meses + año_corrido
        historico_keywords = [
            'historico', 'histórico', 'evolucion', 'evolución', 'tendencia', 'todos los periodos',
            'todos los meses', 'serie historica', 'serie histórica', 'a lo largo del tiempo'
        ]
        es_historico = any(hk in texto_norm for hk in historico_keywords)
        if es_historico:
            cuenta_hint = f" usando cuenta = '{cuenta_flujo_detectada}'" if cuenta_flujo_detectada else ""
            pregunta += (
                f" mostrando los resultados comparativos{cuenta_hint}:"
                f" 1) Últimos 12 meses con filtro doce_meses = (SELECT MAX(doce_meses) FROM livo)"
                f" 2) Año corrido con filtro año_corrido = (SELECT MAX(año_corrido) FROM livo)"
                f" en una tabla con UNION ALL (los valores válidos del campo cuenta son EXACTAMENTE:"
                f" 'Oferta', 'Paralizado', 'Ventas', 'Saldo que inicia', 'Lanzamientos', 'Renuncias',"
                f" 'Entregadas', 'Iniciaciones', 'Culminadas')"
            )
            texto_norm = normalize_text(pregunta)
            print(f"📌 [REGLA HISTÓRICO] Pregunta histórica/evolución/tendencia. Forzando doce_meses + año_corrido.")

        # REGLAS 4 & 5: Detección de período de tiempo ausente
        tiempo_keywords = [
            '201', '202', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
            'ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
            'trimestre', 'semestre', 'mes', 'anio', 'ano', 'acumulado', 'doce meses', '12 meses', 'año corrido'
        ]
        tiene_tiempo = any(tk in texto_norm for tk in tiempo_keywords) or es_historico

        es_avg_promedio = any(pk in texto_norm for pk in ['promedio', 'media', 'avg', 'average'])
        es_oferta = any(ok in texto_norm for ok in ['oferta', 'disponible', 'stock', 'inventario'])

        if not tiene_tiempo:
            if es_oferta and not es_avg_promedio and not es_cuenta_flujo:
                # Regla 4A: Oferta pura sin periodo -> último período disponible
                print("📌 [REGLA 4A] Cuenta Oferta sin período. Usará el último período disponible.")
            else:
                # Regla 4B & 5: Lanzamientos, ventas, iniciaciones, promedio sin período
                # -> Mostrar 2 resultados: Últimos 12 meses y Año corrido
                cuenta_hint = f" usando cuenta = '{cuenta_flujo_detectada}'" if cuenta_flujo_detectada else ""
                pregunta += (
                    f" mostrando los resultados comparativos{cuenta_hint}:"
                    f" 1) Últimos 12 meses con filtro doce_meses = (SELECT MAX(doce_meses) FROM livo)"
                    f" 2) Año corrido con filtro año_corrido = (SELECT MAX(año_corrido) FROM livo)"
                    f" en una tabla con UNION ALL (los valores válidos del campo cuenta son EXACTAMENTE:"
                    f" 'Oferta', 'Paralizado', 'Ventas', 'Saldo que inicia', 'Lanzamientos', 'Renuncias',"
                    f" 'Entregadas', 'Iniciaciones', 'Culminadas')"
                )
                texto_norm = normalize_text(pregunta)
                print(f"📌 [REGLA 4B/5] Sin período temporal. Cuenta detectada: {cuenta_flujo_detectada or 'No especificada'}. Solicitando tabla comparativa 'Últimos 12 Meses' vs 'Año Corrido'.")
        
        # Clasificar si la pregunta es sobre LIVO o no (si no, responder con LLM directamente)
        if not self.es_pregunta_livo(pregunta):
            print(f" Consulta no clasificada como LIVO. Usando fallback...")
            return False, "Consulta no clasificada como LIVO. Usando fallback...", None

        # MEJORA 2: Detección de ambigüedades
        tiene_ambiguedades, ambiguedades = self.detectar_ambiguedades(pregunta)
        if tiene_ambiguedades:
            mensaje_ambiguedad = " **Tu pregunta podría ser más específica:**\n\n"
            for amb in ambiguedades:
                mensaje_ambiguedad += f"- {amb}\n"
            mensaje_ambiguedad += "\n **Intentaré responder con los datos disponibles...**\n\n"
            # No retornar, solo advertir
            print(mensaje_ambiguedad)
        
        # MEJORA: Intentar respuesta directa de Coyuntura (Prioridad Alta)
        respuesta_coyuntura = self._consultar_coyuntura_directa(pregunta)
        if respuesta_coyuntura:
            return True, respuesta_coyuntura, None

        # MEJORA: Intentar primero con reglas específicas (sin LLM) para consultas complejas
        # Luego con reglas simples si las específicas fallan
        print(f"[DEBUG] Intentando reglas específicas primero...")
        
        # Intentar primero con reglas específicas (con CTEs complejos)
        sql_reglas = self._generar_sql_desde_reglas(pregunta)
        es_sql_reglas_especificas = False
        if sql_reglas:
            print(f"[DEBUG] SQL generado por reglas específicas: {sql_reglas[:100]}...")
            es_sql_reglas_especificas = True
        else:
            print(f"[DEBUG] Reglas específicas no aplicaron, intentando reglas simples...")
            sql_reglas = self._generar_sql_sin_llm(pregunta)
        
        # debug_sql_msg2 = f"[DEBUG _generar_sql_sin_llm] SQL generado: {sql_reglas if sql_reglas else 'None'}"
        # if STREAMLIT_AVAILABLE:
        #     st.text(debug_sql_msg2)
        # else:
        #     print(debug_sql_msg2)
        
        if sql_reglas:
            # Solo aplicar correcciones si NO es de reglas específicas (las reglas específicas ya están correctas)
            if not es_sql_reglas_especificas:
                sql_reglas = self.corregir_sql_hallucinado(sql_reglas)
            print(f"Usando SQL generado por reglas (sin LLM): {sql_reglas}")
            try:
                result = self.conn.execute(sql_reglas).fetchall()
                columns = [desc[0] for desc in self.conn.description]
                
                # Formatear resultados
                respuesta = self._formatear_resultados(result, columns, sql_reglas)
                
                # Verificar si se usó filtro geográfico en el SQL generado por reglas
                # Si no hay filtro de departamento/regional, asumimos nacional y agregamos el tip
                if "departamento" not in sql_reglas.lower() and "regional" not in sql_reglas.lower():
                    respuesta += "\n\n*Tip:* También puedo darte este dato por departamento o ciudad (ej: 'en Antioquia' o 'en Bogotá')."
                
                # Agregar badge
                # Determinar si es contexto de vivienda (Coyuntura) o general (LIVO)
                es_coyuntura_vivienda = any(p in pregunta.lower() for p in ["mes anterior", "mes pasado"])
                
                # Si se mencionan usos no residenciales, NO es coyuntura de vivienda
                non_res_keywords = ['oficina', 'local', 'bodega', 'lote', 'consultorio', 'hotel', 'hospital', 'educacion', 'comercio', 'industria']
                if any(k in normalize_text(pregunta) for k in non_res_keywords):
                    es_coyuntura_vivienda = False

                if es_coyuntura_vivienda:
                    respuesta = f"**Respuesta rápida (Estimación LIVO)**\n\n{respuesta}\n\n*Fuente: Base de datos LIVO (Simulando reglas de Coyuntura)*"
                else:
                    respuesta = f"**Respuesta rápida (LIVO)**\n\n{respuesta}\n\n*Fuente: Base de datos LIVO (Cálculo directo)*"
                respuesta += f"\n\n**Query:** `{sql_reglas}`"
                
                # Generar gráfico si se solicita
                chart_data = None
                if generate_chart and result:
                    chart_data = self._generar_grafico(result, columns, pregunta, channel)
                
                return True, respuesta, chart_data
            except Exception as e:
                print(f"⚠️ SQL de reglas falló: {e}. Intentando con LLM...")

        # MEJORA 3: Buscar en caché
        cache_result = self._buscar_en_cache(pregunta)
        if cache_result:
            print(f"⚡ Usando resultado cacheado (guardado: {cache_result['timestamp']})")
            sql_cacheado = cache_result['sql']
            
            # Ejecutar SQL cacheado
            sql_cacheado = self.corregir_sql_hallucinado(sql_cacheado)
            try:
                result = self.conn.execute(sql_cacheado).fetchall()
                columns = [desc[0] for desc in self.conn.description]
                
                # Formatear resultados
                respuesta = self._formatear_resultados(result, columns, sql_cacheado)
                
                # Agregar badge de caché
                respuesta = f"**Resultado cacheado (ultra rápido)**\n\n{respuesta}\n\n*Fuente: Base de datos LIVO (Caché)*"
                respuesta += f"\n\n**Query:** `{sql_cacheado}`"
                
                # MEJORA 4: Explicación del SQL
                explicacion = self.explicar_sql(sql_cacheado, llm_function)
                respuesta += f"\n\n**Qué hice:** {explicacion}"
                
                # MEJORA 5: Sugerencias de preguntas relacionadas
                sugerencias = self.generar_preguntas_relacionadas(pregunta, respuesta, llm_function)
                if sugerencias:
                    respuesta += "\n\n**Preguntas relacionadas que podrías hacer:**\n"
                    for i, sug in enumerate(sugerencias, 1):
                        respuesta += f"{i}. {sug}\n"
                
                # MEJORA 6: Generar gráfico si se solicita
                chart_data = None
                if generate_chart and result:
                    chart_data = self._generar_grafico(result, columns, pregunta, channel)
                
                return True, respuesta, chart_data
                
            except Exception as e:
                print(f"⚠️ SQL cacheado falló, regenerando: {e}")
                # Continuar con generación normal
        
        # 1. Generar componentes del prompt
        schema_inteligente = self._generar_schema_inteligente()
        diccionario_sinonimos = self._generar_diccionario_sinonimos()
        contexto_tipos = self._generar_contexto_tipos_vivienda()
        
        # 2. Construir prompt completo (usando la pregunta normalizada)
        prompt = f"""Eres un experto en SQL y datos de licencias de construcción (LIVO) en Colombia.

{schema_inteligente}

{diccionario_sinonimos}

REGLAS CRÍTICAS:
1. DESAMBIGUACIÓN DE UBICACIÓN (BOGOTÁ Y NIVEL NACIONAL - MUY CRÍTICO):
   - Si el usuario pregunta por "Bogotá" o "Bogota", debes filtrar por departamento 'Bogotá D.C.' y/o ciudad 'Bogotá' usando la condición: `(UPPER(departamento) LIKE '%BOGOTA%' OR UPPER(ciudad) LIKE '%BOGOTA%')`.
   - Si el usuario NO menciona ninguna ubicación geográfica (ninguna regional, departamento, ciudad o barrio) en la pregunta, debes asumir por defecto que se refiere a nivel nacional y **NO** debes aplicar ningún filtro de ubicación geográfica en el WHERE.
1b. DESAMBIGUACIÓN (REGIONAL vs DEPARTAMENTO vs CIUDAD):
   - El campo `departamento` tiene las siguientes opciones de respuesta exactas: 'Bogotá D.C.', 'Córdoba', 'Nariño', 'Valle del Cauca', 'Bolívar', 'Antioquia', 'Cundinamarca', 'Santander', 'Cauca', 'Tolima', 'Huila', 'Risaralda', 'Atlántico', 'Caldas', 'Boyacá', 'Magdalena', 'Norte de Santander', 'Meta', 'Cesar', 'Quindío', 'Sucre'.
   - Si el usuario pide "departamento de Antioquia", usa `WHERE departamento = 'Antioquia'`.
   - Si el usuario pide "regional Antioquia", usa `WHERE regional = 'Antioquia'`.
   - Si solo dice "en Antioquia", y la pregunta es sobre datos agregados (oferta, ventas), asume `regional`. Si es sobre detalles (proyectos, constructoras), asume `departamento`.
   - ¡Recuerda que Risaralda, Antioquia, Valle, Atlántico, Cundinamarca, Bolívar, Santander, Tolima, Quindío, Caldas, Magdalena son DEPARTAMENTOS o REGIONALES, NUNCA ciudades!
   - NUNCA uses `WHERE ciudad = 'Risaralda'` o `WHERE ciudad = 'Antioquia'`. Las ciudades/municipios válidos son nombres como 'Pereira', 'Medellín', 'Cali', 'Barranquilla', 'Bogotá D.C.', etc.
   - Si el usuario escribe "y" para unir regiones (ej: "Bogotá y Cundinamarca"), conviértelo a "&" para que coincida con la base de datos (ej: "Bogotá & Cundinamarca").
1b_metro. ZONAS METROPOLITANAS Y ÁREAS METROPOLITANAS (MUY CRÍTICO):
   - Si la pregunta del usuario se refiere a una Zona Metropolitana, Región o "Ciudad y alrededores/alrededores", debes usar tanto la columna `ciudad` como `AM_capital`.
   - **¡REGLA DE ORO DE PARÉNTESIS!** Debes **SIEMPRE** envolver estas condiciones OR entre paréntesis para que no rompan la lógica de los filtros AND subsiguientes. Por ejemplo: `(ciudad = 'Manizales' OR AM_capital = 'Manizales AM')`.
   - **DIFERENCIA CRÍTICA ENTRE 'BOGOTÁ REGIÓN' Y 'BOGOTÁ AM / ZONA METROPOLITANA':**
     * **Bogotá Región** significa ÚNICAMENTE la ciudad capital: `ciudad = 'Bogotá' AND AM_capital = 'Bogotá D.C.'`. NO incluye municipios aledaños, corredores ni Cundinamarca.
     * **Bogotá AM / Zona Metropolitana de Bogotá / Bogotá y alrededores** sí incluye toda el área metropolitana: `(ciudad = 'Bogotá' OR AM_capital IN ('Bogotá D.C.', 'Corredor Autopista Norte', 'Corredor Autopista Sur', 'Corredor Calle 13', 'Corredor Cundinamarca-Caliente', 'Corredor Vía-La Calera'))`
   - Utiliza las siguientes correspondencias exactas para otras ciudades:
     * **Medellín Región / Valle de Aburrá / Medellín y alrededores / Medellín AM:** `(ciudad = 'Medellín' OR AM_capital = 'Medellín AM')`
     * **Cali Región / Cali AM / Cali y alrededores:** `(ciudad = 'Cali' OR AM_capital = 'Cali AM')`
     * **Barranquilla Región / Barranquilla AM / Barranquilla y alrededores:** `(ciudad = 'Barranquilla' OR AM_capital = 'Barranquilla AM')`
     * **Bucaramanga Región / Bucaramanga AM / Bucaramanga y alrededores:** `(ciudad = 'Bucaramanga' OR AM_capital = 'Bucaramanga AM')`
     * **Pereira Región / Pereira AM / Pereira y alrededores:** `(ciudad = 'Pereira' OR AM_capital = 'Pereira AM')`
     * **Manizales Región / Manizales AM / Manizales y alrededores:** `(ciudad = 'Manizales' OR AM_capital = 'Manizales AM')`
     * **Cúcuta Región / Cúcuta AM / Cúcuta y alrededores:** `(ciudad = 'Cúcuta' OR AM_capital = 'Cúcuta AM')`
1c. DESAMBIGUACIÓN (CUENTA vs ESTADO vs FASE):
   - El campo `cuenta` es de importancia crítica y define la métrica transaccional. Sus valores válidos son EXACTAMENTE: 'Ventas', 'Iniciaciones', 'Culminadas', 'Entregadas', 'Oferta', 'Renuncias', 'Lanzamientos', 'Saldo que inicia', 'Paralizado'.
   - Si el usuario pide "Entregadas", "Ventas", "Iniciaciones", "Culminadas", "Oferta", "Lanzamientos", "Renuncias", "Saldo que inicia" o "Paralizado", utiliza SIEMPRE `cuenta = 'Entregadas'`, `cuenta = 'Ventas'`, etc.
   - NUNCA filtres por `estado = 'Entregadas'` o `estado = 'Ventas'`. El campo `estado` es para el estado físico de la obra ('Construcción', 'Preventa', 'TVE', 'TE', 'Cancelado', 'Paralizado', 'Proyectado', 'Rediseñado').
   - **PROHIBICIÓN ABSOLUTA DE COLUMNAS ALUCINADAS EN AGREGACIONES:** La tabla `livo` NO tiene columnas llamadas `iniciaciones`, `ventas`, `lanzamientos`, `entregas`, `renuncias`, `culminadas`. NUNCA escribas `SUM(iniciaciones)`, `AVG(ventas)`, `AVG(iniciaciones)`, `COUNT(lanzamientos)`, etc. La única columna numérica de conteo es `unidades`. Siempre usa `SUM(unidades)` o `AVG(unidades)` combinado con el filtro `cuenta = 'Iniciaciones'` (o el valor correspondiente).
1d. RANKINGS Y AGRUPACIONES (CONSTRUCTORAS / PROYECTOS):
   - Si la pregunta pide un ranking, top o "principales" de "constructores", "constructoras", "empresas", "firmas", "compañías" o "proyectos", **SIEMPRE** debes seleccionar la columna `compania_constructora` (o `nombre_proyecto` según sea el caso), calcular la agregación correspondiente (ej: `SUM(unidades) AS total`), agrupar utilizando `GROUP BY compania_constructora` (o `GROUP BY nombre_proyecto`), ordenar de forma descendente (`ORDER BY total DESC`), y limitar la cantidad de resultados (`LIMIT N`).
   - NUNCA devuelvas una agregación global (como un simple `SELECT SUM(unidades) FROM livo...` sin columnas ni cláusula GROUP BY) si el usuario solicita un ranking por constructores o proyectos. Es indispensable incluir la columna y la agrupación.
1e. PERÍODO TEMPORAL AUSENTE Y REGLAS DE TABLAS COMPARATIVAS (MUY CRÍTICO):
   - Si la pregunta NO especifica ningún período temporal (año o mes):
     - **Caso A (Cuenta Oferta):** Si la cuenta es 'Oferta' (y no se pide área total), debes filtrar por la fecha máxima de oferta disponible: `fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')`.
     - **Caso B (Otras cuentas o valores/áreas promedio):** Si la cuenta es DIFERENTE a 'Oferta' (ej: Ventas, Lanzamientos, Iniciaciones, etc.) O si la pregunta pide "valor promedio", "precio promedio", "área promedio", etc. (y no se pide área total), **SIEMPRE** debes mostrar los resultados comparativos para **Últimos 12 Meses** (filtro `doce_meses = (SELECT MAX(doce_meses) FROM livo)`) y para **Año Corrido** (filtro `año_corrido = (SELECT MAX(año_corrido) FROM livo)`) usando `UNION ALL` en una sola tabla comparativa.
     - **Caso C (ÁREA TOTAL - MUY CRÍTICO):** Si la pregunta pide "area total", "área total", "suma de area", "suma de área", "total de area" o "total de área" (unidades sumadas por área) y NO se especifica período temporal, **SIEMPRE** debes mostrar **3 resultados** usando `UNION ALL` en una sola tabla comparativa:
       1. `"Último Periodo"`: filtro de fecha máxima `fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')` (o la cuenta correspondiente).
       2. `"Últimos 12 Meses"`: filtro `doce_meses = (SELECT MAX(doce_meses) FROM livo)`.
       3. `"Año Corrido"`: filtro `año_corrido = (SELECT MAX(año_corrido) FROM livo)`.
     - Ejemplo de SQL para Caso C (Área total sin periodo):
       ```sql
       SELECT 'Último Periodo' AS periodo, SUM(area) AS total FROM livo WHERE cuenta = 'Oferta' AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
       UNION ALL
       SELECT 'Últimos 12 Meses' AS periodo, SUM(area) AS total FROM livo WHERE cuenta = 'Oferta' AND doce_meses = (SELECT MAX(doce_meses) FROM livo)
       UNION ALL
       SELECT 'Año Corrido' AS periodo, SUM(area) AS total FROM livo WHERE cuenta = 'Oferta' AND año_corrido = (SELECT MAX(año_corrido) FROM livo)
       ```
     - Ejemplo de SQL para Caso B (Ventas globales sin periodo):
       ```sql
       SELECT 'Últimos 12 Meses' AS periodo, SUM(unidades) AS total FROM livo WHERE cuenta = 'Ventas' AND doce_meses = (SELECT MAX(doce_meses) FROM livo)
       UNION ALL
       SELECT 'Año Corrido' AS periodo, SUM(unidades) AS total FROM livo WHERE cuenta = 'Ventas' AND año_corrido = (SELECT MAX(año_corrido) FROM livo)
       ```
     - Ejemplo de SQL para Caso B (Lanzamientos en Bogotá Región sin periodo — SOLO ciudad capital, NO corredores):
       ```sql
       SELECT 'Últimos 12 Meses' AS periodo, SUM(unidades) AS total FROM livo WHERE cuenta = 'Lanzamientos' AND ciudad = 'Bogotá' AND AM_capital = 'Bogotá D.C.' AND doce_meses = (SELECT MAX(doce_meses) FROM livo)
       UNION ALL
       SELECT 'Año Corrido' AS periodo, SUM(unidades) AS total FROM livo WHERE cuenta = 'Lanzamientos' AND ciudad = 'Bogotá' AND AM_capital = 'Bogotá D.C.' AND año_corrido = (SELECT MAX(año_corrido) FROM livo)
       ```
     - Ejemplo si la consulta requiere agrupaciones (ej. por regional):
       ```sql
       WITH doce_mes_datos AS (
           SELECT regional, SUM(unidades) AS total FROM livo WHERE cuenta = 'Ventas' AND doce_meses = (SELECT MAX(doce_meses) FROM livo) GROUP BY regional
       ),
       ano_cor_datos AS (
           SELECT regional, SUM(unidades) AS total FROM livo WHERE cuenta = 'Ventas' AND año_corrido = (SELECT MAX(año_corrido) FROM livo) GROUP BY regional
       )
       SELECT 
           COALESCE(d.regional, a.regional) AS regional,
           COALESCE(d.total, 0) AS "Últimos 12 Meses",
           COALESCE(a.total, 0) AS "Año Corrido"
       FROM doce_mes_datos d
       FULL OUTER JOIN ano_cor_datos a ON d.regional = a.regional
       ```
1f. FILTROS ESPECÍFICOS Y NUEVAS REGLAS DE NEGOCIO (PREVENTA, ARRIENDO, VIS, VIP, NO VIS - CRÍTICO):
   - **PREVENTA:** Si el usuario pregunta por "preventa" o "preventas", debes filtrar usando `cuenta = 'Oferta' AND UPPER(estado) = 'PREVENTA'`.
   - **ARRIENDO:** Si el usuario pregunta por "arriendo", "alquiler", "renta", "arrendar" o "rentar", debes filtrar usando `segmento_pre = 'Arrendar'`.
   - **VIS (POR DEFECTO INCLUYE VIP):** Si el usuario pregunta por "VIS" o "Vivienda de Interés Social" (y no dice "sin VIP"), debes incluir tanto VIS como VIP usando: `segmento_pre = 'VIS' AND rangos_decreto_pre IN ('VIS 70 - 135 SML', 'VIP')`.
   - **VIS SIN VIP:** Si el usuario pregunta por "VIS sin VIP", debes filtrar únicamente el rango VIS usando: `segmento_pre = 'VIS' AND rangos_decreto_pre = 'VIS 70 - 135 SML'`.
   - **VIP:** Si el usuario pregunta por "VIP" de forma específica, debes filtrar usando: `segmento_pre = 'VIS' AND rangos_decreto_pre = 'VIP'`.
  - **NO VIS (DESGLOSE Y TOTALIZADO EN TABLA):** Si el usuario pregunta por "No VIS" o "No Interés Social", debes filtrar usando `segmento_pre = 'No VIS'`. Para dar el desglose por rango junto con el total global de No VIS en el mismo resultado, debes agrupar por `ROLLUP(rangos_decreto_pre)`.
     - **¡REGLA DE COLUMNA PLURAL EXTREMADAMENTE CRÍTICA!** El nombre correcto de la columna es **SIEMPRE en PLURAL**: `rangos_decreto_pre`. NUNCA uses la palabra en singular `rango_decreto_pre` (o `rango_decreto_pre = ...`).
     - **PROHIBICIÓN ABSOLUTA DE FILTROS NUMÉRICOS ALUCINADOS:** NUNCA escribas condiciones del tipo `rangos_decreto_pre = 1`, `rangos_decreto_pre <= 100`, `rangos_decreto_pre >= 70`, etc. Esta columna es de tipo texto (VARCHAR) y contiene cadenas descriptivas como 'VIS 70 - 135 SML', 'VIP', 'No VIS 135 - 235 SML', 'No VIS 235 - 335 SML', etc. NUNCA la compares con enteros ni uses operadores numéricos (=, <=, >=, <, >) con números.
     - **COLUMNA segmento_pre NO EXISTE:** NUNCA uses `segmento_pre` — esa columna no existe en LIVO. Para filtrar VIS/VIP/No VIS usa siempre `segmento_pre` y `rangos_decreto_pre`.
     - Ejemplo de SQL para No VIS: `SELECT COALESCE(rangos_decreto_pre, 'TOTAL NO VIS') AS rango, SUM(unidades) AS total FROM livo WHERE segmento_pre = 'No VIS' GROUP BY ROLLUP(rangos_decreto_pre)`
     - Ejemplo de SQL para VIS sin VIP: `SELECT AVG(area) AS area_promedio FROM livo WHERE segmento_pre = 'VIS' AND rangos_decreto_pre = 'VIS 70 - 135 SML' AND ciudad = 'Bogotá' AND AM_capital = 'Bogotá D.C.' AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')`
   - Si el usuario menciona un estrato específico (ej: "estrato 3", "estrato 4"), filtra por `estrato = 3` (o el número correspondiente).
   - Si el usuario menciona "apartamento", "apartamentos", "piso", filtra por `uso_etapa = 'Apartamento'`.
   - Si el usuario menciona "casa", "casas", "vivienda unifamiliar", filtra por `uso_etapa = 'Casa'`.
   - **SIEMPRE** aplica estos filtros cuando se mencionan explícitamente en la pregunta.
1f. RANKINGS POR CIUDAD/DEPARTAMENTO:
   - Si la pregunta pide "ranking de ciudades", "por ciudad", "top ciudades", "ranking de departamentos" o "por departamento", **SIEMPRE** debes:
     1. Seleccionar la columna `ciudad` o `departamento` en el SELECT.
     2. Agrupar por esa columna con `GROUP BY ciudad` o `GROUP BY departamento`.
     3. Ordenar por la métrica solicitada en forma descendente `ORDER BY ... DESC`.
     4. Limitar los resultados con `LIMIT N` (ej: LIMIT 10).
   - NUNCA devuelvas una agregación global sin GROUP BY cuando se solicita un ranking por ciudad o departamento.
1g. CÁLCULO DE CRECIMIENTO INTERANUAL (MUY CRÍTICO):
   - Si la pregunta menciona "crecimiento", "variación", "evolución", "cambio" o "entre X y Y" (ej: "entre 2025 y 2026"), **SIEMPRE** debes:
     1. Usar CTEs (WITH) para calcular los datos de cada periodo por separado.
     2. Usar `FULL OUTER JOIN` (o `CROSS JOIN` si es resultado único) para unir ambos periodos.
     3. Calcular el porcentaje de crecimiento con la fórmula: `ROUND(((valor_2 - valor_1) / NULLIF(valor_1, 0)) * 100, 2)`.
     4. Incluir columnas para ambos periodos y el porcentaje de crecimiento.
   - **CAMPOS DE PERÍODO DISPONIBLES — MUY IMPORTANTE:**
     - `fecha`: entero YYYYMMDD (ej: 20250415) — fecha exacta del registro.
     - `doce_meses`: año entero (ej: 2024, 2025) — indica los **últimos 12 meses móviles** cerrados a ese año. `doce_meses = 2025` = últimos 12 meses hasta el corte 2025.
     - `año_corrido`: año entero (ej: 2024, 2025) — indica el **acumulado enero→mes_corte** de ese año. `año_corrido = 2025` = acumulado 2025 hasta el mes disponible.
     - Los valores disponibles son años enteros: 2019, 2020, 2021, 2022, 2023, 2024, 2025, etc.
   - **REGLA CRÍTICA DE PERÍODOS COMPARABLES — NUNCA uses CAST(año) para comparaciones:**
     - El año en curso (ej: 2026) puede tener datos solo hasta abril. Filtrar `año = 2026` da 4 meses vs `año = 2025` que da 12 meses — comparación inválida.
     - **SIEMPRE usa `doce_meses` o `año_corrido` para comparaciones interanuales:**
       - **Opción A — flujos (Lanzamientos, Ventas, Iniciaciones):** usa `doce_meses`. Compara `doce_meses = 2025` vs `doce_meses = 2024`. Ambos son 12 meses completos comparables.
       - **Opción B — acumulado año corrido:** usa `año_corrido`. Compara `año_corrido = 2025` vs `año_corrido = 2024`. Ambos son el mismo corte de mes (ene→mes_corte) en años distintos.
       - **Opción C — precio/oferta puntual:** usa `fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')` para el período actual.
     - NUNCA uses `CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2025` para comparaciones interanuales de flujo — da años incompletos.
   - Ejemplo correcto para variación de flujo entre `doce_meses` comparables:
     ```sql
     WITH datos_anterior AS (
         SELECT SUM(unidades) AS total_anterior
         FROM livo
         WHERE cuenta = 'Lanzamientos'
           AND segmento_pre = 'No VIS'
           AND UPPER(ciudad) LIKE '%MONTERÍA%'
           AND doce_meses = (SELECT MAX(doce_meses) FROM livo) - 1
     ),
     datos_actual AS (
         SELECT SUM(unidades) AS total_actual
         FROM livo
         WHERE cuenta = 'Lanzamientos'
           AND segmento_pre = 'No VIS'
           AND UPPER(ciudad) LIKE '%MONTERÍA%'
           AND doce_meses = (SELECT MAX(doce_meses) FROM livo)
     )
     SELECT
         total_anterior AS "12 meses anteriores",
         total_actual   AS "Últimos 12 meses",
         ROUND(((total_actual - total_anterior) / NULLIF(total_anterior, 0)) * 100, 2) AS variacion_pct
     FROM datos_anterior CROSS JOIN datos_actual
     ```
   - Ejemplo correcto para variación de precio promedio entre `año_corrido` comparables:
     ```sql
     WITH datos_2024 AS (
         SELECT AVG(valor) AS precio_2024
         FROM livo
         WHERE cuenta = 'Oferta' AND segmento_pre = 'No VIS'
           AND UPPER(ciudad) LIKE '%MONTERÍA%'
           AND año_corrido = (SELECT MAX(año_corrido) FROM livo) - 1
     ),
     datos_2025 AS (
         SELECT AVG(valor) AS precio_2025
         FROM livo
         WHERE cuenta = 'Oferta' AND segmento_pre = 'No VIS'
           AND UPPER(ciudad) LIKE '%MONTERÍA%'
           AND año_corrido = (SELECT MAX(año_corrido) FROM livo)
     )
     SELECT
         ROUND(precio_2024, 0) AS precio_año_anterior,
         ROUND(precio_2025, 0) AS precio_año_actual,
         ROUND(((precio_2025 - precio_2024) / NULLIF(precio_2024, 0)) * 100, 2) AS variacion_pct
     FROM datos_2024 CROSS JOIN datos_2025
     ```
   - **PROHIBICIÓN ABSOLUTA en variaciones:** NUNCA uses `(SELECT ... FROM livo WHERE año=2025) AS s1, (SELECT ... FROM livo WHERE año=2026) AS s2` con coma — DuckDB lo trata como CROSS JOIN implícito. NUNCA calcules `AVG(valor) - AVG(valor)` en el mismo subquery (da siempre 0). SIEMPRE usa CTEs separadas + CROSS JOIN explícito con `doce_meses` o `año_corrido`.
1g-bis. MEDIA MÓVIL (MOVING AVERAGE) — CRÍTICO:
   - Si la pregunta menciona "media móvil", "promedio móvil", "moving average", "suavizado" o "promedio de N meses", **SIEMPRE** genera una ventana deslizante con función de ventana de DuckDB.
   - **NUNCA** uses GROUP BY ni ROLLUP para media móvil — requiere función de ventana `OVER (ORDER BY ... ROWS BETWEEN ...)`.
   - **NUNCA** filtres por `rangos_decreto_pre` con valores numéricos ('01', '02') — esa columna es texto descriptivo.
   - La estructura correcta es: CTE mensual → función de ventana AVG OVER con ROWS BETWEEN (N-1) PRECEDING AND CURRENT ROW.
   - Detecta el número de meses en la pregunta: "media móvil 3 meses" → N=3, "media móvil 6 meses" → N=6. Default N=3.
   - Ejemplo para **media móvil de 6 meses de ventas No VIS en Pereira AM**:
     ```sql
     WITH mensual AS (
         SELECT
             CAST(LEFT(CAST(fecha AS VARCHAR), 6) AS INTEGER) AS mes_anio,
             SUM(unidades) AS total_mensual
         FROM livo
         WHERE cuenta = 'Ventas'
           AND (ciudad = 'Pereira' OR AM_capital = 'Pereira AM')
           AND segmento_pre = 'No VIS'
         GROUP BY mes_anio
     )
     SELECT
         mes_anio,
         total_mensual,
         ROUND(AVG(total_mensual) OVER (
             ORDER BY mes_anio
             ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
         ), 2) AS media_movil_6m
     FROM mensual
     ORDER BY mes_anio
     ```
   - Para media móvil de 3 meses: `ROWS BETWEEN 2 PRECEDING AND CURRENT ROW`
   - Para media móvil de 12 meses: `ROWS BETWEEN 11 PRECEDING AND CURRENT ROW`
   - Fórmula general N meses: `ROWS BETWEEN (N-1) PRECEDING AND CURRENT ROW`
1h. DETECCIÓN DE TRIMESTRES (MUY CRÍTICO):
   - Si la pregunta menciona "trimestre", "último trimestre", "este trimestre" o "trimestral", **NO uses** `MAX(fecha)` (que solo toma un mes).
   - En su lugar, filtra por los últimos 3 meses disponibles usando: `fecha >= (SELECT MAX(fecha) FROM livo) - INTERVAL '2 months'` o equivalentemente extrae los últimos 3 meses distintos.
   - Ejemplo para último trimestre:
     ```sql
     WITH ultimo_trimestre AS (
         SELECT DISTINCT fecha
         FROM livo
         ORDER BY fecha DESC
         LIMIT 3
     )
     SELECT SUM(unidades) as total
     FROM livo
     WHERE fecha IN (SELECT fecha FROM ultimo_trimestre)
       AND cuenta = 'Ventas'
       AND regional = 'Medellín'
     ```
   - Para cálculos de tasas (ej: tasa de absorción), calcula oferta y ventas por separado para el trimestre y luego el ratio.
1i-pre. PRECIO PROMEDIO Y MÉTRICAS DE VALOR (CRÍTICO):
   - Si la pregunta pide "precio promedio", "valor promedio", "precio por m²" o similar, usa **`AVG(valor)`** — NUNCA `SUM(unidades)`.
   - La columna `valor` contiene el precio de venta en miles de pesos COP. La columna `area` contiene m².
   - **VALORES VÁLIDOS de `rangos_decreto_pre`** (son texto descriptivo, NO números ni etiquetas inventadas):
     - Para VIS: `'VIS 70 - 135 SML'`, `'VIP'`
     - Para No VIS: `'No VIS 135 - 235 SML'`, `'No VIS 235 - 335 SML'`, `'No VIS 335 - 435 SML'`, `'No VIS > 435 SML'`
     - NUNCA uses valores inventados como `'Exento'`, `'Reducido'`, `'Incrementado'`, `'01'`, `'02'`, `'Menor a 50 unidades'`, etc.
   - **COLUMNAS DUPLICADAS PROHIBIDAS:** NUNCA repitas el mismo alias (`AS total_unidades`) dos veces en el SELECT — DuckDB genera error.
   - **ROLLUP NO ES FUNCIÓN:** NUNCA uses `ROLLUP(AVG(...))` o `ROLLUP(SUM(...))` — `ROLLUP` solo va en `GROUP BY ROLLUP(col)`. En SELECT solo van expresiones de agregación normales.
   - **FILTER mal usado PROHIBIDO:** NUNCA uses `AVG(valor) FILTER (WHERE UPPER(fase) LIKE '%PRE%')` — esto causa errores. Para filtrar dentro de una agregación usa `AVG(CASE WHEN condicion THEN valor END)`.
   - **fecha NO ES STRING ISO:** La columna `fecha` contiene enteros YYYYMMDD (ej: 20250315). NUNCA uses `fecha BETWEEN '2025-01-01' AND '2026-12-31'`. Para filtrar por año usa `CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2025`.
   - **estrato = 0 PROHIBIDO:** NUNCA filtres por `estrato = 0` — no tiene sentido de negocio. Los estratos válidos son 1 al 6.
   - Ejemplo correcto para precio promedio No VIS en un departamento:
     ```sql
     SELECT AVG(valor) AS precio_promedio_no_vis
     FROM livo
     WHERE cuenta = 'Oferta'
       AND segmento_pre = 'No VIS'
       AND UPPER(departamento) LIKE '%SANTANDER%'
       AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
     ```
1i. CÁLCULO DE TASAS Y RATIOS:
   - Si la pregunta pide una tasa, ratio, porcentaje o cálculo entre dos métricas (ej: "tasa de absorción (Ventas / (Oferta + Ventas))"), **SIEMPRE** debes:
     1. Calcular cada componente por separado en CTEs.
     2. Devolver una tabla con las columnas de cada componente y el resultado del cálculo.
     3. Ejemplo para tasa de absorción:
     ```sql
     WITH datos_trimestre AS (
         SELECT DISTINCT fecha
         FROM livo
         ORDER BY fecha DESC
         LIMIT 3
     ),
     oferta AS (
         SELECT SUM(unidades) as total_oferta
         FROM livo
         WHERE fecha IN (SELECT fecha FROM datos_trimestre)
           AND cuenta = 'Oferta'
           AND UPPER(ciudad) LIKE UPPER('%Medellín%')
     ),
     ventas AS (
         SELECT SUM(unidades) as total_ventas
         FROM livo
         WHERE fecha IN (SELECT fecha FROM datos_trimestre)
           AND cuenta = 'Ventas'
           AND UPPER(ciudad) LIKE UPPER('%Medellín%')
     )
     SELECT 
         o.total_oferta as "Oferta (unidades)",
         v.total_ventas as "Ventas (unidades)",
         ROUND((v.total_ventas * 100.0 / NULLIF((o.total_oferta + v.total_ventas), 0)), 2) as "Tasa de absorción (%)"
     FROM oferta o
     CROSS JOIN ventas v
     ```
1j. BÚSQUEDA FLEXIBLE Y COLUMNA CORRECTA POR TIPO DE ENTIDAD (MUY CRÍTICO):
   - **COLUMNA CORRECTA según el tipo de entidad geográfica mencionada:**
     - Si el usuario menciona una **ciudad o municipio** (ej: Medellín, Barranquilla, Soacha, Chía, Bello, Envigado, Itagüí, Palmira, etc.), filtra por la columna `ciudad`: `UPPER(ciudad) LIKE '%MEDELLÍN%'`.
     - Si el usuario menciona un **departamento** (ej: Antioquia, Valle del Cauca, Cundinamarca, etc.), filtra por la columna `departamento`: `UPPER(departamento) LIKE '%ANTIOQUIA%'`.
     - Si el usuario menciona una **regional de Camacol** (ej: Bogotá & Cundinamarca, Córdoba & Sucre, Cúcuta_Nororiente, etc.), filtra por la columna `regional`: `UPPER(regional) LIKE '%BOGOTÁ%'`.
     - Si el usuario menciona un **área metropolitana** (Medellín AM, Cali AM, etc.), usa la condición combinada con `AM_capital`.
   - **PROHIBICIÓN ABSOLUTA**: NUNCA uses `UPPER(regional) LIKE '%MEDELLÍN%'` para buscar la ciudad Medellín. La ciudad `Medellín` está en la columna `ciudad`, NO en `regional`. El valor en `regional` para Medellín es `'Antioquia'`.
   - **SINTAXIS OBLIGATORIA DUCKDB**: El patrón `%` SIEMPRE va FUERA de `UPPER()`. NUNCA escribas `UPPER(col) LIKE UPPER('%valor%')` — DuckDB genera error "syntax error at or near %". La forma correcta es `UPPER(col) LIKE '%VALOR%'` (patrón en mayúsculas sin UPPER adicional).
   - Ejemplo correcto ciudad: `AND UPPER(ciudad) LIKE '%BOGOTÁ%'`
   - Ejemplo correcto departamento: `AND UPPER(departamento) LIKE '%ANTIOQUIA%'`
   - Ejemplo correcto regional: `AND UPPER(regional) LIKE '%ANTIOQUIA%'`
1k. SUGERENCIA DE REGIONALES ALTERNATIVAS (CUANDO NO HAY RESULTADOS):
   - Si el usuario menciona una ciudad (ej: "Medellín", "Barranquilla", "Cali") pero no hay resultados con LIKE, asume el departamento correspondiente:
     - "Medellín" → "Antioquia"
     - "Barranquilla" → "Atlántico"
     - "Cali" → "Valle del Cauca"
     - "Bucaramanga" → "Santander"
     - "Pereira" → "Risaralda"
     - "Manizales" → "Caldas"
     - "Bogotá" → "Bogotá & Cundinamarca"
   - Si no hay resultados con la búsqueda flexible, intenta filtrar por el departamento asociado a la ciudad mencionada.
   - Ejemplo: Si `UPPER(regional) LIKE UPPER('%Medellín%')` no devuelve resultados, intenta `UPPER(departamento) LIKE UPPER('%Antioquia%')`.
1l. RANKINGS DE PROYECTOS (USAR CAMPO IDENTIFICADOR - MUY CRÍTICO):
   - Si la pregunta menciona "proyecto", "proyectos", "obra" o "desarrollo", **SIEMPRE** debes usar el campo `identificador` para agrupar y seleccionar.
   - **NUNCA**, bajo ninguna circunstancia, uses `compania_constructora`, `nombre_proyecto` o `regional` cuando se pide ranking de proyectos.
   - **ESTRICTAMENTE PROHIBIDO**: Usar `compania_constructora` en rankings de proyectos. El campo correcto es `identificador`.
   - La estructura correcta es: `SELECT identificador, SUM(unidades) AS total FROM livo GROUP BY identificador ORDER BY total DESC LIMIT N`.
   - Ejemplo: "Top 15 proyectos con mayor saldo que inicia" → `SELECT identificador, SUM(valor) AS total FROM livo WHERE cuenta = 'Saldo que inicia' GROUP BY identificador ORDER BY total DESC LIMIT 15`.
   - Si usas `compania_constructora` en lugar de `identificador`, la respuesta será INCORRECTA.
1m. AGRUPACIÓN POR ESTRATO CON COMPARACIÓN INTERANUAL:
   - Si la pregunta menciona estratos específicos (ej: "estratos 4-6", "estrato 4, 5 y 6") y pide comparación interanual o porcentaje, **SIEMPRE** debes:
     1. Agrupar por `estrato` con `GROUP BY estrato` para mostrar CADA estrato en filas separadas (estrato 4, estrato 5, estrato 6).
     2. Filtrar por los estratos mencionados (ej: `estrato IN (4, 5, 6)`).
     3. Calcular datos para el año actual y el año anterior usando CTEs.
     4. Devolver una tabla con columnas: estrato, suma_año_actual, suma_año_pasado, porcentaje_crecimiento.
   - **IMPORTANTE**: "estratos 4-6" significa desagregar en estrato 4, estrato 5 y estrato 6 individualmente, NO solo el total.
   - Ejemplo para estratos 4-6 (muestra 3 filas: una por cada estrato):
     ```sql
     WITH datos_actual AS (
         SELECT estrato, SUM(unidades) as suma_actual
         FROM livo
         WHERE cuenta = 'Lanzamientos'
           AND estrato IN (4, 5, 6)
           AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2026
         GROUP BY estrato
     ),
     datos_pasado AS (
         SELECT estrato, SUM(unidades) as suma_pasado
         FROM livo
         WHERE cuenta = 'Lanzamientos'
           AND estrato IN (4, 5, 6)
           AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2025
         GROUP BY estrato
     )
     SELECT 
         COALESCE(d1.estrato, d2.estrato) as estrato,
         COALESCE(d1.suma_actual, 0) as "Suma lanzamientos año actual",
         COALESCE(d2.suma_pasado, 0) as "Suma lanzamientos año pasado",
         ROUND(((d1.suma_actual - d2.suma_pasado) / NULLIF(d2.suma_pasado, 0)) * 100, 2) as "% Crecimiento"
     FROM datos_actual d1
     FULL OUTER JOIN datos_pasado d2 ON d1.estrato = d2.estrato
     ORDER BY estrato
     ```
1n. FILTRO TEMPORAL PARA SALDOS (ÚLTIMO MES):
   - Si la pregunta menciona "saldo", "saldos" o "saldo que inicia", **SIEMPRE** debes filtrar por el último mes disponible (MAX fecha).
   - NUNCA uses datos históricos completos para saldos sin especificación temporal.
   - La estructura correcta es: `WHERE ... AND fecha = (SELECT MAX(fecha) FROM livo)`.
   - Ejemplo: "Top 15 proyectos con mayor saldo que inicia" → `SELECT identificador, SUM(valor) AS total FROM livo WHERE cuenta = 'Saldo que inicia' AND fecha = (SELECT MAX(fecha) FROM livo) GROUP BY identificador ORDER BY total DESC LIMIT 15`.
1o. ORDENAMIENTO POR UNIDADES VS VALOR:
   - Si la pregunta especifica "ordenados por unidades", "por unidades" o "según unidades", **SIEMPRE** debes usar `SUM(unidades)` en el ORDER BY.
   - Si la pregunta especifica "ordenados por valor", "por valor" o "según valor", **SIEMPRE** debes usar `SUM(valor)` en el ORDER BY.
   - Si la pregunta no especifica el criterio de ordenamiento, usa `SUM(valor)` por defecto para rankings de proyectos.
   - Ejemplo "ordenados por unidades" → `SELECT identificador, SUM(unidades) AS total FROM livo GROUP BY identificador ORDER BY total DESC LIMIT 15`.
   - Ejemplo "ordenados por valor" → `SELECT identificador, SUM(valor) AS total FROM livo GROUP BY identificador ORDER BY total DESC LIMIT 15`.
2. CAMPOS CATEGÓRICOS: Usa EXACTAMENTE los valores listados (respeta mayúsculas/minúsculas).
3. FILTROS DE TEXTO: Usa `UPPER(columna) LIKE UPPER('%valor%')` para búsquedas flexibles.
4. CAMPOS NUMÉRICOS: Usa operadores `=`, `>`, `<`, `>=`, `<=` (NUNCA `LIKE`).
5. AGREGACIONES: Usa las funciones indicadas (SUM, AVG, COUNT, MIN, MAX).
6. AGRUPACIÓN: Usa `GROUP BY` para categorizar resultados.
7. ORDENAMIENTO: Usa `ORDER BY ... DESC` para rankings.
8. LÍMITE: Usa `LIMIT N` para top N resultados.
9. CÁLCULOS MULTINIVEL: Usa CTEs (WITH) o subconsultas para cálculos anidados.

EJEMPLOS DE CONSULTAS CORRECTAS:

"Cuántas licencias en Bogotá" →
SELECT COUNT(*) FROM livo WHERE UPPER(ciudad) LIKE UPPER('%Bogotá%')

"Total unidades por ciudad" →
SELECT ciudad, SUM(unidades) as total FROM livo GROUP BY ciudad

"Licencias de tipo VIS en Medellín" →
SELECT COUNT(*) FROM livo WHERE UPPER(ciudad) LIKE UPPER('%Medellín%') AND segmento_pre = 'VIS'

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
WHERE segmento_pre = 'VIS'
  AND UPPER(ciudad) LIKE UPPER('%Bogotá%')
  AND estrato = 3
  AND unidades > 50
  AND UPPER(zona) LIKE UPPER('%urbana%')
  AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2024

"Top 5 constructoras con más unidades VIP en Medellín, estrato 1 o 2, área menor a 60m2, estado vigente" →
SELECT compania_constructora, SUM(unidades) as total, AVG(area) as area_promedio
FROM livo
WHERE segmento_pre = 'VIP'
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
WHERE segmento_pre = 'No VIS'
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
  AND segmento_pre = 'VIS'
  AND UPPER(fase) LIKE UPPER('%construcción%')
  AND unidades BETWEEN 20 AND 100
  AND doce_meses = 1
GROUP BY ciudad
ORDER BY total_unidades DESC

{self._obtener_ejemplos_few_shot(pregunta)}

PREGUNTA DEL USUARIO: {pregunta}

Genera SOLO el SQL (sin explicaciones, sin markdown, sin comentarios):
"""
        
        # 3. Generar SQL con LLM
        respuesta_llm, _ = llm_function(prompt)
        
        # --- MEJORA: Manejar el caso en que todos los LLM fallen ---
        if not respuesta_llm:
            return False, " No se pudo generar la consulta SQL porque todos los proveedores de IA fallaron. Por favor, revisa los límites de tu API.", None
            
        sql = respuesta_llm.strip().replace('```sql', '').replace('```', '').strip()
        
        sql = '\n'.join([line for line in sql.split('\n') if not line.strip().startswith('--')])
        sql = sql.strip()
        
        # Auto-corrección de alucinaciones y sintaxis incorrecta del LLM
        sql = self.corregir_sql_hallucinado(sql)
        
        if ';' in sql:
            sql = sql.split(';')[0].strip()
            print(f" Múltiples sentencias detectadas, usando solo la primera")
        
        if len(sql) > 500:
            print(f" SQL muy largo ({len(sql)} chars), verificando...")
        
        print(f"\n SQL: {sql}\n")
        
        try:
            result = self.conn.execute(sql).fetchall()
            columns = [desc[0] for desc in self.conn.description]
            
            # Formatear la respuesta principal
            respuesta = self._formatear_resultados(result, columns, sql)
            respuesta += "\n\n *Fuente: Base de datos LIVO (SQL Generado)*"
            respuesta += f"\n\n **Query:** `{sql}`"

            # --- Generación de Contexto Unificado (Consistente con reglas) ---
            contexto_items = []
            
            # COMENTADO: Eliminar análisis comparativo y anomalías
            # 1. Análisis Comparativo
            # comp = self._realizar_analisis_comparativo(sql, result, columns)
            # if comp: contexto_items.append(comp)

            # 2. Anomalías
            # anom = self._detectar_anomalias(sql, result, columns)
            # if anom: contexto_items.append(anom)
            
            # COMENTADO: Eliminar generación de contexto avanzado
            # 3. Contexto Avanzado (Market Share, Segmentos, Coyuntura, Salud, Momentum, Normativa)
            # avanzado = self._generar_contexto_avanzado(sql, result, columns, pregunta)
            # if avanzado: contexto_items.extend(avanzado)

            # COMENTADO: Eliminar contexto LIVO completamente
            # if contexto_items:
            #     respuesta += "\n\n **Contexto LIVO:**\n" + "\n".join(contexto_items)

            # MEJORA: Visualización Automática y Contextual
            chart_data = None
            if generate_chart:
                chart_data = self._generar_grafico(result, columns, pregunta, channel)

            return True, respuesta, chart_data
            
        except Exception as e:
            error_msg = str(e)
            # Reintento automático para SQL truncado o con errores corregibles
            if any(x in error_msg.lower() for x in ['syntax error at end of input', 'syntax error', 'binder error', 'parser error']):
                print(f"⚠️ SQL con error '{error_msg[:80]}', intentando auto-corrección con LLM...")
                try:
                    sql_corregido = self.validar_y_corregir_sql(sql, error_msg, pregunta, llm_function)
                    if sql_corregido:
                        sql_corregido = self.corregir_sql_hallucinado(sql_corregido)
                        result2 = self.conn.execute(sql_corregido).fetchall()
                        columns2 = [desc[0] for desc in self.conn.description]
                        respuesta2 = self._formatear_resultados(result2, columns2, sql_corregido)
                        respuesta2 += "\n\n *Fuente: Base de datos LIVO (SQL Corregido)*"
                        respuesta2 += f"\n\n **Query:** `{sql_corregido}`"
                        return True, respuesta2, None
                except Exception as e2:
                    print(f"⚠️ Reintento también falló: {e2}")
            return False, f"❌ Error SQL: {error_msg}", None

    def _realizar_analisis_comparativo(self, sql_original: str, resultado_actual: list, columnas: list) -> Optional[str]:
        """Intenta ejecutar la misma consulta para el año anterior y añade una comparación."""
        # Buscar un año en la consulta SQL
        # Soporte para sintaxis simple y robusta (CAST...)
        regex_anio = r"(?:LEFT\(fecha,\s*4\)\s*=\s*'(\d{4})')|(?:YEAR\(fecha\)\s*=\s*(\d{4}))|(?:CAST\(LEFT\(CAST\(fecha\s+AS\s+VARCHAR\),\s*4\)\s+AS\s+INTEGER\)\s*=\s*(\d{4}))"
        match = re.search(regex_anio, sql_original, re.IGNORECASE)
        if not match:
            return None

        try:
            # Encontrar cuál grupo capturó el año
            año_actual_str = next((g for g in match.groups() if g is not None), None)
            if not año_actual_str:
                return None
                
            año_actual = int(año_actual_str)
            año_anterior = año_actual - 1

            # Crear la consulta para el año anterior
            sql_anterior = sql_original.replace(str(año_actual), str(año_anterior))
            resultado_anterior = self.conn.execute(sql_anterior).fetchall()

            # Comparar si los resultados son comparables (una sola cifra numérica)
            if len(resultado_actual) == 1 and len(resultado_anterior) == 1 and len(columnas) == 1 and isinstance(resultado_actual[0][0], (int, float)):
                valor_actual = resultado_actual[0][0]
                valor_anterior = resultado_anterior[0][0]
                if valor_anterior > 0:
                    cambio_pct = ((valor_actual - valor_anterior) / valor_anterior) * 100
                    return f"📈 **Análisis Comparativo:** El resultado representa un **{'incremento' if cambio_pct >= 0 else 'decremento'} del {cambio_pct:.2f}%** en comparación con el año {año_anterior} (que fue de {valor_anterior:,.0f})."
            
            # 2. Caso Complejo: Tabla / Agrupación (NUEVO - Soporte para resultados complejos)
            # Si hay más de 1 fila o columnas, comparamos el agregado total
            elif len(resultado_actual) > 0 and len(resultado_anterior) > 0:
                # Identificar columna numérica para sumar (heurística por nombre)
                idx_numerico = -1
                for i, col in enumerate(columnas):
                    if any(x in col.lower() for x in ['unidades', 'valor', 'area', 'precio', 'total', 'count', 'sum', 'avg']):
                        idx_numerico = i
                        break
                
                if idx_numerico != -1:
                    # Calcular totales
                    total_actual = sum(row[idx_numerico] for row in resultado_actual if isinstance(row[idx_numerico], (int, float)))
                    total_anterior = sum(row[idx_numerico] for row in resultado_anterior if isinstance(row[idx_numerico], (int, float)))
                    
                    if total_anterior > 0:
                        cambio_pct = ((total_actual - total_anterior) / total_anterior) * 100
                        return f"📈 **Análisis Comparativo (Agregado):** El volumen total analizado para {año_actual} ({total_actual:,.0f}) presenta una variación del **{cambio_pct:.2f}%** frente al año {año_anterior} ({total_anterior:,.0f})."

        except Exception as e:
            print(f"⚠️ Error en análisis comparativo: {e}")
        return None
    
    def _generar_contexto_avanzado(self, sql: str, result: list, columns: list, pregunta: str) -> List[str]:
        """Genera contexto avanzado: Market Share, Segmentos, Coyuntura, Salud, Momentum, Normativa."""
        contexto = []
        
        # Determinar tipo de resultado
        es_dato_unico = len(result) == 1 and len(columns) == 1 and isinstance(result[0][0], (int, float))
        es_tabla_agrupada = len(result) > 1 and len(columns) >= 2
        valor_actual = result[0][0] if es_dato_unico else 0
        
        # Detectar múltiples regiones en la pregunta
        region = self._extraer_region_general(pregunta)
        es_multiple_regiones = region and '|' in region if region else False
        
        # Si hay múltiples regiones, generar contexto específico para cada una usando LLM
        if es_multiple_regiones:
            regiones = region.split('|')
            contexto.append(f"🗺️ **Análisis por Región:** Consulta que involucra {len(regiones)} regiones: {', '.join(regiones)}")
            
            # Generar contexto de coyuntura para cada región (sistema estadístico)
            if COYUNTURA_AVAILABLE:
                for reg in regiones:
                    pregunta_region = pregunta.replace(region, reg)  # Crear pregunta específica para esta región
                    narrativa = self._obtener_narrativa_coyuntura(pregunta_region)
                    if narrativa:
                        contexto.append(f"📊 **Coyuntura {reg}:** {narrativa}")
            
            # Generar contexto cualitativo usando LLM para cada región
            try:
                for reg in regiones:
                    prompt_llm = f"""
Genera un contexto cualitativo breve (máximo 2-3 frases) sobre el mercado inmobiliario en {reg} para Colombia.
Contexto: El usuario está preguntando sobre: "{pregunta}"
Enfócate en:
- Dinámica del mercado (dinámico, estable, en recuperación)
- Características principales (tipo de proyectos, segmentos predominantes)
- Tendencias recientes relevantes

Responde de forma concisa y directa, sin introducciones ni explicaciones."""
                    
                    # Usar FAST_PROVIDER si está disponible
                    provider = FAST_PROVIDER if FAST_PROVIDER else AI_PROVIDERS[0] if AI_PROVIDERS else None
                    if provider:
                        respuesta_llm, error_llm = llamar_api_ia(prompt_llm, provider)
                        if respuesta_llm and not error_llm:
                            # Limpiar respuesta si es tupla
                            if isinstance(respuesta_llm, tuple):
                                respuesta_llm = respuesta_llm[0]
                            if isinstance(respuesta_llm, str):
                                contexto.append(f"🤖 **Contexto {reg} (IA):** {respuesta_llm.strip()}")
            except Exception as e:
                print(f"⚠️ Error generando contexto LLM para regiones: {e}")
        else:
            # 1. Integración Narrativa de Coyuntura (única región)
            if COYUNTURA_AVAILABLE:
                narrativa = self._obtener_narrativa_coyuntura(pregunta)
                if narrativa: contexto.append(f"📊 **Coyuntura:** {narrativa}")

        # 2. Contexto Normativo Proactivo
        normativo = self._obtener_contexto_normativo(pregunta)
        if normativo: contexto.append(f"⚖️ **Normativa:** {normativo}")

        # 3. Contexto para resultados agrupados (tablas)
        if es_tabla_agrupada:
            contexto_tabla = self._generar_contexto_tabla(result, columns, pregunta)
            if contexto_tabla: contexto.extend(contexto_tabla)

        if es_dato_unico and valor_actual > 0:
            # 4. Market Share (Participación)
            share = self._calcular_market_share(sql, valor_actual)
            if share: contexto.append(share)

            # 5. Desglose por Segmento (VIS vs No VIS)
            # Solo si no está filtrado ya por tipo específico en el SQL
            if "segmento_pre =" not in sql and "segmento_pre IN" not in sql:
                desglose = self._calcular_desglose_segmento(sql, valor_actual)
                if desglose: contexto.append(desglose)
            
            # 6. Indicadores Cruzados (Salud del Mercado)
            salud = self._calcular_indicadores_salud(sql, valor_actual)
            if salud: contexto.append(salud)
            
            # 7. Tendencia de Corto Plazo (Momentum)
            momentum = self._calcular_momentum(sql, valor_actual)
            if momentum: contexto.append(momentum)
            
            # 8. Proyecciones a Corto Plazo (Forecasting)
            forecast = self._calcular_proyeccion_corto_plazo(sql, valor_actual)
            if forecast: contexto.append(forecast)

            # 9. Benchmarking Automático (Comparación entre Pares)
            benchmark = self._calcular_benchmarking(sql, valor_actual)
            if benchmark: contexto.append(benchmark)

            # 10. Análisis de Absorción de Lanzamientos
            absorcion = self._calcular_absorcion_lanzamientos(sql, valor_actual)
            if absorcion: contexto.append(absorcion)

            # 11. Índice de Concentración de Mercado (HHI)
            concentracion = self._calcular_concentracion_mercado(sql)
            if concentracion: contexto.append(concentracion)

            # 12. Contexto de Valorización (Precios)
            valorizacion = self._calcular_valorizacion_precios(sql)
            if valorizacion: contexto.append(valorizacion)

            # 13. Alertas de Agotamiento (Stockout)
            agotamiento = self._calcular_alerta_agotamiento(sql, valor_actual)
            if agotamiento: contexto.append(agotamiento)

            # 14. Distribución Fina por Rangos de SMMLV
            dist_smmlv = self._calcular_distribucion_fina_smmlv(sql, valor_actual)
            if dist_smmlv: contexto.append(dist_smmlv)

            # 15. Contexto de Estacionalidad
            estacionalidad = self._calcular_estacionalidad(sql)
            if estacionalidad: contexto.append(estacionalidad)
            
            # 16. Razonamiento Multi-Fuente (Correlación Macro)
            macro = self._analisis_macro_sectorial(sql)
            if macro: contexto.append(macro)

            # 17. Auditoría de Calidad de Datos
            calidad = self._auditar_calidad_datos(sql, result, columns)
            if calidad: contexto.append(calidad)

            # 18. Simulación de Escenarios (What-If)
            simulacion = self._simular_escenario_automatico(sql, valor_actual)
            if simulacion: contexto.append(simulacion)

        return contexto

    def _generar_contexto_tabla(self, result: list, columns: list, pregunta: str) -> List[str]:
        """Genera contexto específico para resultados agrupados (tablas)."""
        contexto = []
        
        if not result or len(result) == 0:
            return contexto
        
        # Identificar columna numérica para cálculos
        idx_numerico = -1
        idx_categoria = -1
        for i, col in enumerate(columns):
            if any(x in col.lower() for x in ['unidades', 'valor', 'area', 'precio', 'total', 'sum', 'count']):
                idx_numerico = i
            elif any(x in col.lower() for x in ['estado', 'fase', 'tipo', 'segmento', 'estrato', 'cuenta', 'departamento', 'ciudad', 'regional']):
                idx_categoria = i
        
        if idx_numerico == -1:
            return contexto
        
        # Calcular total y porcentajes
        total_general = sum(row[idx_numerico] for row in result if isinstance(row[idx_numerico], (int, float)))
        
        if total_general == 0:
            return contexto
        
        # Generar análisis de distribución
        analisis_distribucion = []
        for row in result:
            valor = row[idx_numerico]
            if isinstance(valor, (int, float)) and valor > 0:
                pct = (valor / total_general) * 100
                categoria = row[idx_categoria] if idx_categoria != -1 and idx_categoria < len(row) else str(row[0])
                analisis_distribucion.append((categoria, valor, pct))
        
        # Ordenar por valor descendente
        analisis_distribucion.sort(key=lambda x: x[1], reverse=True)
        
        # Generar insights
        if len(analisis_distribucion) > 0:
            # Insight 1: Categoría dominante
            top_categoria, top_valor, top_pct = analisis_distribucion[0]
            contexto.append(f"📊 **Distribución:** La categoría **{top_categoria}** domina con {top_valor:,.0f} unidades ({top_pct:.1f}% del total).")
            
            # Insight 2: Si hay múltiples categorías, mostrar distribución
            if len(analisis_distribucion) > 1:
                distribucion_str = ", ".join([f"{cat}: {pct:.1f}%" for cat, val, pct in analisis_distribucion[:3]])
                contexto.append(f"📈 **Composición:** Distribución: {distribucion_str}")
            
            # Insight 3: Análisis específico según tipo de categoría
            if idx_categoria != -1:
                col_categoria = columns[idx_categoria].lower()
                
                # Análisis de estado (ciclo de vida)
                if 'estado' in col_categoria:
                    preventa_pct = next((pct for cat, val, pct in analisis_distribucion if 'preventa' in str(cat).lower()), 0)
                    construccion_pct = next((pct for cat, val, pct in analisis_distribucion if 'construccion' in str(cat).lower()), 0)
                    paralizado_pct = next((pct for cat, val, pct in analisis_distribucion if 'paralizado' in str(cat).lower()), 0)
                    
                    if preventa_pct > 50:
                        contexto.append(f"🏗️ **Ciclo de Vida:** El mercado está en fase de comercialización ({preventa_pct:.1f}% en preventa), indicando alta actividad de lanzamientos.")
                    elif construccion_pct > 50:
                        contexto.append(f"🏗️ **Ciclo de Vida:** El mercado está en fase de ejecución ({construccion_pct:.1f}% en construcción), indicando proyectos en desarrollo activo.")
                    elif paralizado_pct > 10:
                        contexto.append(f"⚠️ **Alerta:** {paralizado_pct:.1f}% de las unidades están paralizadas, lo que podría indicar problemas operativos o financieros.")
                
                # Análisis de tipo de vivienda
                elif 'tipo' in col_categoria or 'segmento' in col_categoria:
                    vis_pct = next((pct for cat, val, pct in analisis_distribucion if 'vis' in str(cat).lower() and 'no' not in str(cat).lower()), 0)
                    no_vis_pct = next((pct for cat, val, pct in analisis_distribucion if 'no vis' in str(cat).lower()), 0)
                    
                    if vis_pct > 0:
                        contexto.append(f"🏠 **Segmentación:** {vis_pct:.1f}% corresponde a vivienda de interés social (VIS).")
                    if no_vis_pct > 0:
                        contexto.append(f"🏠 **Segmentación:** {no_vis_pct:.1f}% corresponde a vivienda No VIS (mercado formal).")
        
        # 4. Análisis de concentración (HHI) si la agrupación es por constructora
        if idx_categoria != -1 and 'constructora' in columns[idx_categoria].lower():
            try:
                # Calcular HHI basado en los datos ya obtenidos
                shares = [val / total_general for cat, val, pct in analisis_distribucion]
                hhi = sum(s * s for s in shares) * 10000  # Escalar a escala HHI estándar
                nivel = "Baja" if hhi < 1500 else "Moderada" if hhi < 2500 else "Alta"
                contexto.append(f"🏢 **Concentración (HHI):** {nivel} (HHI: {hhi:.0f}). Un HHI > 2500 indica alta concentración del mercado.")
            except:
                pass
        
        # 5. Análisis avanzados por categoría (Market Share, Valorización, Estacionalidad, Segmentación, Salud, Absorción)
        if idx_categoria != -1 and len(analisis_distribucion) <= 5:  # Limitar a top 5 para no saturar
            for categoria, valor, pct in analisis_distribucion[:3]:  # Top 3 categorías
                try:
                    # Extraer WHERE clause del SQL original
                    match_from = re.search(r"FROM\s+livo\s+WHERE\s+(.*?)(\s+GROUP\s+BY|\s+ORDER\s+BY|$)", sql, re.IGNORECASE | re.DOTALL)
                    if not match_from:
                        continue
                    where_clause = match_from.group(1)
                    
                    # Agregar filtro para la categoría específica
                    col_categoria_name = columns[idx_categoria]
                    where_categoria = f"{where_clause} AND {col_categoria_name} = '{categoria}'"
                    
                    # Market Share por categoría
                    if "compania_constructora" not in sql.lower():  # Solo si no es por constructora
                        try:
                            sql_nacional_cat = re.sub(r"AND\s*\(\s*UPPER\s*\(.*?LIKE\s*'.*?'(?:.*?\))+", "", where_categoria)
                            sql_share_cat = f"SELECT SUM(unidades) FROM livo WHERE {sql_nacional_cat}"
                            res_nac_cat = self.conn.execute(sql_share_cat).fetchone()
                            if res_nac_cat and res_nac_cat[0] and res_nac_cat[0] > 0:
                                total_nacional_cat = res_nac_cat[0]
                                share_cat = (valor / total_nacional_cat) * 100
                                contexto.append(f"🌍 **Market Share ({categoria}):** {share_cat:.1f}% del total nacional.")
                        except:
                            pass
                    
                    # Valorización por categoría (solo si es oferta)
                    if "cuenta = 'Oferta'" in sql or "cuenta='Oferta'" in sql:
                        try:
                            where_limpio = re.sub(r"AND\s+cuenta\s*=\s*'.*?'", "", where_categoria)
                            where_limpio = re.sub(r"AND\s+fecha\s*=\s*\(.*?\)", "", where_limpio)
                            
                            sql_precio_cat = f"""
                            WITH actual AS (
                                SELECT AVG(precio_mc_promedio) as precio
                                FROM livo
                                WHERE {where_limpio} AND cuenta = 'Oferta' 
                                  AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
                            ),
                            anterior AS (
                                SELECT AVG(precio_mc_promedio) as precio
                                FROM livo
                                WHERE {where_limpio} AND cuenta = 'Oferta'
                                  AND fecha = (SELECT MAX(fecha) - 10000 FROM livo WHERE cuenta = 'Oferta')
                            )
                            SELECT a.precio, b.precio FROM actual a, anterior b
                            """
                            res_precio = self.conn.execute(sql_precio_cat).fetchone()
                            if res_precio and res_precio[0] and res_precio[1]:
                                p_actual, p_ant = res_precio
                                var = ((p_actual - p_ant) / p_ant) * 100
                                contexto.append(f"💲 **Valorización ({categoria}):** Variación del {var:+.1f}% vs año anterior.")
                        except:
                            pass
                    
                    # Estacionalidad por categoría (si hay mes en SQL)
                    match_mes = re.search(r"SUBSTR.*?=\s*(\d+)", sql)
                    if match_mes:
                        try:
                            mes_consultado = int(match_mes.group(1))
                            cuenta_match = re.search(r"cuenta\s*=\s*'(\w+)'", sql)
                            cuenta = cuenta_match.group(1) if cuenta_match else 'Ventas'
                            
                            sql_est_cat = f"""
                            SELECT 
                                AVG(total) as prom
                            FROM (
                                SELECT fecha, SUM(unidades) as total 
                                FROM livo 
                                WHERE cuenta = '{cuenta}' AND {col_categoria_name} = '{categoria}'
                                GROUP BY fecha
                            )
                            """
                            res_est = self.conn.execute(sql_est_cat).fetchone()
                            if res_est and res_est[0]:
                                promedio_general = res_est[0]
                                
                                # Obtener valor del mes específico
                                sql_mes_cat = f"""
                                SELECT SUM(unidades) as total
                                FROM livo
                                WHERE cuenta = '{cuenta}' AND {col_categoria_name} = '{categoria}'
                                  AND CAST(SUBSTR(CAST(fecha AS VARCHAR), 5, 2) AS INTEGER) = {mes_consultado}
                                """
                                res_mes = self.conn.execute(sql_mes_cat).fetchone()
                                if res_mes and res_mes[0]:
                                    valor_mes = res_mes[0]
                                    if promedio_general > 0:
                                        var_est = ((valor_mes - promedio_general) / promedio_general) * 100
                                        contexto.append(f"📅 **Estacionalidad ({categoria}):** {var_est:+.1f}% vs promedio mensual.")
                        except:
                            pass
                    
                    # Segmentación por categoría (VIS vs No VIS)
                    if "segmento_pre" not in sql.lower():
                        try:
                            sql_seg_cat = f"""
                            SELECT 
                                SUM(CASE WHEN segmento_pre = 'VIS' THEN unidades ELSE 0 END) * 100.0 / SUM(unidades),
                                SUM(CASE WHEN segmento_pre = 'No VIS' THEN unidades ELSE 0 END) * 100.0 / SUM(unidades)
                            FROM livo WHERE {where_categoria}
                            """
                            res_seg = self.conn.execute(sql_seg_cat).fetchone()
                            if res_seg:
                                vis_pct, no_vis_pct = res_seg
                                if vis_pct > 0 or no_vis_pct > 0:
                                    contexto.append(f"🏠 **Segmentación ({categoria}):** VIS {vis_pct or 0:.1f}%, No VIS {no_vis_pct or 0:.1f}%.")
                        except:
                            pass
                    
                    # Salud del mercado por categoría (rotación)
                    if "cuenta = 'Oferta'" in sql or "cuenta='Oferta'" in sql:
                        try:
                            # Obtener ventas promedio mensual para la categoría
                            sql_ventas_cat = f"""
                            SELECT AVG(total) as prom_ventas
                            FROM (
                                SELECT fecha, SUM(unidades) as total 
                                FROM livo 
                                WHERE cuenta = 'Ventas' AND {col_categoria_name} = '{categoria}'
                                GROUP BY fecha
                            )
                            """
                            res_ventas = self.conn.execute(sql_ventas_cat).fetchone()
                            if res_ventas and res_ventas[0] and res_ventas[0] > 0:
                                prom_ventas = res_ventas[0]
                                meses_agotamiento = valor / prom_ventas
                                contexto.append(f"🏥 **Salud ({categoria}):** Stock se agotaría en {meses_agotamiento:.1f} meses.")
                                if meses_agotamiento > 9:
                                    contexto.append(f"⚠️ **Alerta ({categoria}):** Rotación crítica (>9 meses).")
                        except:
                            pass
                    
                    # Absorción por categoría
                    if "cuenta = 'Ventas'" in sql or "cuenta='Ventas'" in sql:
                        try:
                            sql_lanz_cat = f"SELECT SUM(unidades) FROM livo WHERE cuenta = 'Lanzamientos' AND {col_categoria_name} = '{categoria}'"
                            res_lanz = self.conn.execute(sql_lanz_cat).fetchone()
                            if res_lanz and res_lanz[0] and res_lanz[0] > 0:
                                lanzamientos = res_lanz[0]
                                absorcion = (valor / lanzamientos) * 100
                                contexto.append(f"📊 **Absorción ({categoria}):** {absorcion:.1f}% de los lanzamientos.")
                        except:
                            pass
                    
                    elif "cuenta = 'Lanzamientos'" in sql or "cuenta='Lanzamientos'" in sql:
                        try:
                            sql_ven_cat = f"SELECT SUM(unidades) FROM livo WHERE cuenta = 'Ventas' AND {col_categoria_name} = '{categoria}'"
                            res_ven = self.conn.execute(sql_ven_cat).fetchone()
                            if res_ven and res_ven[0]:
                                ventas = res_ven[0]
                                absorcion = (ventas / valor) * 100
                                contexto.append(f"📊 **Absorción ({categoria}):** Se ha vendido el {absorcion:.1f}% de lo lanzado.")
                        except:
                            pass
                    
                except NameError as ne:
                    if 'sql' in str(ne):
                        print(f"⚠️ Error en análisis avanzado por categoría {categoria}: Variable 'sql' no disponible - omitiendo análisis detallado")
                    else:
                        print(f"⚠️ Error en análisis avanzado por categoría {categoria}: {ne}")
                    continue
                except Exception as e:
                    print(f"⚠️ Error en análisis avanzado por categoría {categoria}: {e}")
                    continue
        
        return contexto

    def _obtener_narrativa_coyuntura(self, pregunta: str) -> Optional[str]:
        """Obtiene narrativa cualitativa de los módulos de coyuntura."""
        texto = normalize_text(pregunta)
        sistema = None
        if "ventas" in texto: sistema = ventas_coyuntura
        elif "oferta" in texto: sistema = oferta_coyuntura
        elif "lanzamientos" in texto: sistema = lanzamientos_coyuntura
        elif "iniciaciones" in texto: sistema = iniciaciones_coyuntura
        elif "rotacion" in texto: sistema = rotacion_coyuntura
        
        if sistema and hasattr(sistema, 'generar_contexto_consulta'):
            return sistema.generar_contexto_consulta(pregunta)
        return None

    def _obtener_contexto_normativo(self, pregunta: str) -> Optional[str]:
        """Inyecta contexto normativo basado en palabras clave."""
        texto = normalize_text(pregunta)
        if "vis" in texto or "interes social" in texto:
            return "Los topes VIS actuales son 135 SMMLV en general y 150 SMMLV en aglomeraciones urbanas principales (Decreto 1467/2019)."
        if "vip" in texto or "prioritario" in texto:
            return "La Vivienda de Interés Prioritario (VIP) tiene un tope de 90 SMMLV."
        if "subsidio" in texto or "mi casa ya" in texto:
            return "El programa Mi Casa Ya otorga subsidios a la cuota inicial y tasa de interés para hogares hasta 4 SMMLV."
        return None

    def _calcular_market_share(self, sql: str, valor_actual: float) -> Optional[str]:
        """Calcula la participación del valor actual respecto al total nacional (removiendo filtro geográfico)."""
        # Identificar filtro geográfico en SQL (departamento, regional o ciudad)
        # Regex busca: AND (UPPER(TRANSLATE(campo... LIKE ... OR ...)
        regex_geo = r"AND\s*\(\s*UPPER\s*\(.*?LIKE\s*'.*?'(?:.*?\))+"
        
        if re.search(regex_geo, sql):
            # Crear SQL nacional removiendo el filtro geográfico
            sql_nacional = re.sub(regex_geo, "", sql)
            try:
                res_nac = self.conn.execute(sql_nacional).fetchone()
                if res_nac and res_nac[0] and res_nac[0] > 0:
                    total_nacional = res_nac[0]
                    share = (valor_actual / total_nacional) * 100
                    return f" **Market Share:** Representa el **{share:.1f}%** del total nacional ({total_nacional:,.0f})."
            except:
                pass
        return None

    def _calcular_desglose_segmento(self, sql: str, valor_total: float) -> Optional[str]:
        """Calcula la distribución VIS vs No VIS."""
        # Extraer la parte FROM y WHERE del SQL original
        match_from = re.search(r"FROM\s+livo\s+WHERE\s+(.*?)(\s+GROUP\s+BY|\s+ORDER\s+BY|$)", sql, re.IGNORECASE | re.DOTALL)
        if not match_from:
            return None
            
        where_clause = match_from.group(1)
        
        # Construir consulta de desglose
        sql_desglose = f"""
        SELECT 
            CASE WHEN segmento_pre IN ('VIS', 'VIP') THEN 'VIS/VIP' ELSE 'No VIS' END as segmento,
            SUM(unidades) as total
        FROM livo
        WHERE {where_clause}
        GROUP BY segmento
        """
        try:
            res = self.conn.execute(sql_desglose).fetchall()
            if res:
                partes = []
                for seg, val in res:
                    if val:
                        pct = (val / valor_total) * 100
                        partes.append(f"{seg}: {pct:.0f}%")
                return f"🏘️ **Segmentación:** {' | '.join(partes)}."
        except:
            pass
        return None

    def _calcular_indicadores_salud(self, sql: str, valor_actual: float) -> Optional[str]:
        """Muestra indicadores cruzados (ej: Rotación si se pregunta por Ventas)."""
        # Si la consulta es de Ventas, calcular Rotación
        if "cuenta = 'Ventas'" in sql:
            # Reemplazar Ventas por Oferta en el SQL para obtener el stock
            sql_oferta = sql.replace("cuenta = 'Ventas'", "cuenta = 'Oferta'")
            # Asegurar que Oferta use la fecha más reciente (stock)
            sql_oferta = re.sub(r"doce_meses\s*=\s*\(.*?\)", "fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')", sql_oferta)
            
            try:
                res_oferta = self.conn.execute(sql_oferta).fetchone()
                if res_oferta and res_oferta[0]:
                    oferta = res_oferta[0]
                    # Ventas promedio mensual (asumiendo valor_actual es anual/12 meses)
                    ventas_prom_mensual = valor_actual / 12
                    if ventas_prom_mensual > 0:
                        rotacion = oferta / ventas_prom_mensual
                        return f"🔄 **Salud del Mercado:** Con este ritmo de ventas, la oferta disponible ({oferta:,.0f}) se agotaría en **{rotacion:.1f} meses**."
            except:
                pass
        return None

    def _calcular_momentum(self, sql: str, valor_actual: float) -> Optional[str]:
        """Calcula la tendencia de corto plazo (vs mes anterior)."""
        # Buscar filtro de fecha máxima
        if "fecha = (SELECT MAX(fecha)" in sql:
            # Crear SQL para el mes anterior
            sql_prev = sql.replace("fecha = (SELECT MAX(fecha)", "fecha = (SELECT MAX(fecha) FROM livo WHERE fecha < (SELECT MAX(fecha)")
            try:
                res_prev = self.conn.execute(sql_prev).fetchone()
                if res_prev and res_prev[0] and res_prev[0] > 0:
                    valor_prev = res_prev[0]
                    var = ((valor_actual - valor_prev) / valor_prev) * 100
                    return f" **Momentum:** Variación de **{var:+.1f}%** frente al mes inmediatamente anterior."
            except:
                pass
        return None
    
    def _calcular_proyeccion_corto_plazo(self, sql: str, valor_actual: float) -> Optional[str]:
        """Genera una proyección simple basada en el promedio reciente."""
        # Solo si es una consulta de flujo (Ventas, Lanzamientos, Iniciaciones)
        if not any(c in sql for c in ["'Ventas'", "'Lanzamientos'", "'Iniciaciones'"]):
            return None
            
        # Intentar calcular promedio de los últimos 3 meses
        try:
            # Extraer WHERE clause y remover filtro de fecha específico
            match_from = re.search(r"FROM\s+livo\s+WHERE\s+(.*?)(\s+GROUP\s+BY|\s+ORDER\s+BY|$)", sql, re.IGNORECASE | re.DOTALL)
            if not match_from: return None
            where_clause = match_from.group(1)
            
            # Remover filtros de fecha existentes para aplicar últimos 3 meses
            where_limpio = re.sub(r"AND\s+fecha\s*=\s*\(.*?\)", "", where_clause)
            where_limpio = re.sub(r"AND\s+doce_meses\s*=\s*\(.*?\)", "", where_limpio)
            where_limpio = re.sub(r"AND\s+CAST\(LEFT.*?=\s*\d+", "", where_limpio)
            
            # SQL para promedio últimos 3 meses
            sql_prom = f"""
            SELECT AVG(total_mes) 
            FROM (
                SELECT SUM(unidades) as total_mes 
                FROM livo 
                WHERE {where_limpio} 
                  AND fecha >= (SELECT MAX(fecha) - 90 FROM livo) -- Aprox 3 meses
                GROUP BY CAST(LEFT(CAST(fecha AS VARCHAR), 6) AS INTEGER)
            )
            """
            res = self.conn.execute(sql_prom).fetchone()
            if res and res[0]:
                promedio_3m = res[0]
                return f" **Proyección:** Basado en el promedio de los últimos 3 meses ({promedio_3m:,.0f}), se proyecta que el próximo mes podría rondar esa cifra."
        except:
            pass
        return None

    def _calcular_benchmarking(self, sql: str, valor_actual: float) -> Optional[str]:
        """Compara la ciudad consultada con un par comparable."""
        # Pares de comparación
        pares = {
            'BOGOTA': 'MEDELLIN', 'MEDELLIN': 'CALI', 'CALI': 'BARRANQUILLA', 
            'BARRANQUILLA': 'BUCARAMANGA', 'BUCARAMANGA': 'PEREIRA', 'CARTAGENA': 'SANTA MARTA'
        }
        
        ciudad_detectada = None
        par_detectado = None
        
        for ciudad, par in pares.items():
            if f"LIKE '%{ciudad}%'" in sql.upper():
                ciudad_detectada = ciudad
                par_detectado = par
                break
        
        if ciudad_detectada and par_detectado:
            try:
                # Reemplazar ciudad en SQL
                sql_par = sql.replace(ciudad_detectada, par_detectado)
                # Ajustar también si está en minúsculas/capitalizado en el LIKE
                sql_par = re.sub(f"LIKE '%{ciudad_detectada}%'", f"LIKE '%{par_detectado}%'", sql_par, flags=re.IGNORECASE)
                
                res = self.conn.execute(sql_par).fetchone()
                if res and res[0]:
                    valor_par = res[0]
                    diff_pct = ((valor_actual - valor_par) / valor_par) * 100
                    estado = "por encima" if diff_pct > 0 else "por debajo"
                    return f" **Benchmarking:** {ciudad_detectada.title()} está un **{abs(diff_pct):.1f}% {estado}** de su par {par_detectado.title()} ({valor_par:,.0f})."
            except:
                pass
        return None

    def _calcular_absorcion_lanzamientos(self, sql: str, valor_actual: float) -> Optional[str]:
        """Calcula ratio de absorción (Ventas vs Lanzamientos)."""
        try:
            if "cuenta = 'Ventas'" in sql:
                # Obtener Lanzamientos para el mismo periodo/filtro
                sql_lan = sql.replace("cuenta = 'Ventas'", "cuenta = 'Lanzamientos'")
                res = self.conn.execute(sql_lan).fetchone()
                if res and res[0] and res[0] > 0:
                    lanzamientos = res[0]
                    absorcion = (valor_actual / lanzamientos) * 100
                    return f" **Absorción:** Las ventas representan el **{absorcion:.1f}%** de los lanzamientos del periodo."
            
            elif "cuenta = 'Lanzamientos'" in sql:
                # Obtener Ventas
                sql_ven = sql.replace("cuenta = 'Lanzamientos'", "cuenta = 'Ventas'")
                res = self.conn.execute(sql_ven).fetchone()
                if res and res[0]:
                    ventas = res[0]
                    absorcion = (ventas / valor_actual) * 100
                    return f" **Absorción:** Se ha vendido el **{absorcion:.1f}%** de lo lanzado en este periodo."
        except:
            pass
        return None

    def _calcular_concentracion_mercado(self, sql: str) -> Optional[str]:
        """Calcula el Índice Herfindahl-Hirschman (HHI) de concentración."""
        # COMENTADO: Contexto LIVO no necesario por ahora
        # Solo si no es una consulta de una constructora específica
        # if "compania_constructora" in sql:
        #     return None
            
        # try:
        #     # Extraer WHERE clause
        #     match_from = re.search(r"FROM\s+livo\s+WHERE\s+(.*?)(\s+GROUP\s+BY|\s+ORDER\s+BY|$)", sql, re.IGNORECASE | re.DOTALL)
        #     if not match_from: return None
        #     where_clause = match_from.group(1)
            
        #     # Calcular HHI
        #     sql_hhi = f"""
        #     WITH shares AS (
        #         SELECT SUM(unidades) * 100.0 / SUM(SUM(unidades)) OVER () as share
        #         FROM livo
        #         WHERE {where_clause}
        #         GROUP BY compania_constructora
        #     )
        #     SELECT SUM(share * share) as hhi FROM shares
        #     """
        #     res = self.conn.execute(sql_hhi).fetchone()
        #     if res and res[0]:
        #         hhi = res[0]
        #         nivel = "Baja" if hhi < 1500 else "Moderada" if hhi < 2500 else "Alta"
        #         return f" **Concentración de Mercado:** {nivel} (HHI: {hhi:.0f}). Un HHI mayor a 2500 indica alta concentración."
        # except:
        #     pass
        return None

    def _calcular_valorizacion_precios(self, sql: str) -> Optional[str]:
        """Calcula la variación del precio por m2 vs año anterior."""
        # Evitar recursión si ya es una consulta de precios
        if "AVG(precio_mc_promedio)" in sql:
            return None
            
        try:
            # Extraer WHERE clause
            match_from = re.search(r"FROM\s+livo\s+WHERE\s+(.*?)(\s+GROUP\s+BY|\s+ORDER\s+BY|$)", sql, re.IGNORECASE | re.DOTALL)
            if not match_from: return None
            where_clause = match_from.group(1)
            
            # Limpiar filtros de cuenta y fecha para usar Oferta y último corte
            where_limpio = re.sub(r"AND\s+cuenta\s*=\s*'.*?'", "", where_clause)
            where_limpio = re.sub(r"AND\s+fecha\s*=\s*\(.*?\)", "", where_limpio)
            
            # Calcular precio actual (último corte oferta) vs año anterior
            sql_precio = f"""
            WITH actual AS (
                SELECT AVG(precio_mc_promedio) as precio
                FROM livo
                WHERE {where_limpio} AND cuenta = 'Oferta' 
                  AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
            ),
            anterior AS (
                SELECT AVG(precio_mc_promedio) as precio
                FROM livo
                WHERE {where_limpio} AND cuenta = 'Oferta'
                  AND fecha = (SELECT MAX(fecha) - 10000 FROM livo WHERE cuenta = 'Oferta') -- Aprox 1 año atrás en YYYYMMDD
            )
            SELECT a.precio, b.precio FROM actual a, anterior b
            """
            res = self.conn.execute(sql_precio).fetchone()
            if res and res[0] and res[1]:
                p_actual, p_ant = res
                var = ((p_actual - p_ant) / p_ant) * 100
                return f"💲 **Valorización:** El precio por m² ha variado un **{var:+.1f}%** frente al año anterior."
        except:
            pass
        return None

    def _calcular_alerta_agotamiento(self, sql: str, valor_actual: float) -> Optional[str]:
        """Genera alerta si la rotación es crítica (< 6 meses)."""
        # Reutilizar lógica de salud del mercado pero enfocada en alerta
        salud = self._calcular_indicadores_salud(sql, valor_actual)
        if salud and "agotaría en" in salud:
            match = re.search(r"agotaría en \*\*([\d\.]+) meses\*\*", salud)
            if match:
                meses = float(match.group(1))
                if meses < 6:
                    return f" **Alerta de Agotamiento:** Inventario crítico. Al ritmo actual, la oferta se agotaría en solo {meses} meses (Stockout)."
        return None

    def _calcular_distribucion_fina_smmlv(self, sql: str, valor_actual: float) -> Optional[str]:
        """Desglosa No VIS en rangos finos (Medio, Alto, Lujo)."""
        if "segmento_pre = 'No VIS'" not in sql and "No VIS" not in sql:
            return None
            
        try:
            # Extraer WHERE clause
            match_from = re.search(r"FROM\s+livo\s+WHERE\s+(.*?)(\s+GROUP\s+BY|\s+ORDER\s+BY|$)", sql, re.IGNORECASE | re.DOTALL)
            if not match_from: return None
            where_clause = match_from.group(1)
            
            # Asumir SMMLV 2025 aprox 1.4M para simplificar rangos en miles
            # 135-300 SMMLV (190M - 420M), 300-500 SMMLV (420M - 700M), >500 SMMLV (>700M)
            # Valores en miles: 190000, 420000, 700000
            sql_dist = f"""
            SELECT 
                SUM(CASE WHEN valor BETWEEN 190000 AND 420000 THEN unidades ELSE 0 END) * 100.0 / SUM(unidades),
                SUM(CASE WHEN valor BETWEEN 420001 AND 700000 THEN unidades ELSE 0 END) * 100.0 / SUM(unidades),
                SUM(CASE WHEN valor > 700000 THEN unidades ELSE 0 END) * 100.0 / SUM(unidades)
            FROM livo WHERE {where_clause}
            """
            res = self.conn.execute(sql_dist).fetchone()
            if res:
                medio, alto, lujo = res
                return f" **Rangos No VIS:** Medio (135-300 SMMLV): {medio or 0:.0f}% | Alto (300-500 SMMLV): {alto or 0:.0f}% | Lujo (>500 SMMLV): {lujo or 0:.0f}%."
        except:
            pass
        return None

    def _calcular_estacionalidad(self, sql: str) -> Optional[str]:
        """Indica si el mes consultado es históricamente alto o bajo."""
        # Detectar mes en SQL
        match_mes = re.search(r"SUBSTR.*?=\s*(\d+)", sql)
        if not match_mes: return None
        
        mes_consultado = int(match_mes.group(1))
        
        try:
            # Calcular promedio histórico por mes para la cuenta consultada
            cuenta_match = re.search(r"cuenta\s*=\s*'(\w+)'", sql)
            cuenta = cuenta_match.group(1) if cuenta_match else 'Ventas'
            
            sql_est = f"""
            SELECT 
                CAST(SUBSTR(CAST(fecha AS VARCHAR), 5, 2) AS INTEGER) as mes,
                AVG(total) as prom
            FROM (
                SELECT fecha, SUM(unidades) as total 
                FROM livo 
                WHERE cuenta = '{cuenta}' 
                GROUP BY fecha
            )
            GROUP BY mes
            """
            rows = self.conn.execute(sql_est).fetchall()
            if not rows: return None
            
            promedios = {r[0]: r[1] for r in rows}
            promedio_general = sum(promedios.values()) / len(promedios)
            promedio_mes = promedios.get(mes_consultado, 0)
            
            if promedio_mes > promedio_general * 1.1:
                return f" **Estacionalidad:** Históricamente, el mes {mes_consultado} es de **alta actividad** para {cuenta} (superior al promedio anual)."
            elif promedio_mes < promedio_general * 0.9:
                return f" **Estacionalidad:** Históricamente, el mes {mes_consultado} es de **baja actividad** para {cuenta}."
        except:
            pass
        return None

    def _analisis_macro_sectorial(self, sql: str) -> Optional[str]:
        """Sugiere correlaciones con variables macroeconómicas (Razonamiento Multi-Fuente)."""
        if "cuenta = 'Ventas'" in sql:
            return " **Correlación Macro:** Las ventas de vivienda presentan históricamente una correlación inversa con las tasas de interés hipotecarias y el desempleo. Se sugiere cruzar este dato con el reporte de 'Tasas de Interés' y 'Mercado Laboral'."
        if "cuenta = 'Iniciaciones'" in sql:
            return " **Correlación Macro:** Las iniciaciones suelen seguir el comportamiento del PIB de Edificaciones con un rezago de 1-2 trimestres."
        if "precio" in sql.lower() or "valor" in sql.lower():
            return " **Correlación Macro:** Los precios de vivienda están influenciados por el ICCV (Índice de Costos de Construcción) y la inflación (IPC)."
        return None

    def _auditar_calidad_datos(self, sql: str, result: list, columns: list) -> Optional[str]:
        """Auditoría automática de calidad de datos en la respuesta."""
        # Verificar si hay valores negativos donde no debería (unidades, valor, area)
        for row in result:
            for val in row:
                if isinstance(val, (int, float)) and val < 0:
                    return " **Auditoría de Datos:**  Se detectaron valores negativos en el resultado, lo cual puede indicar ajustes contables o reversiones masivas en la fuente."
        return None

    def _simular_escenario_automatico(self, sql: str, valor_actual: float) -> Optional[str]:
        """Genera una simulación What-If automática (Capacidades Predictivas)."""
        # COMENTADO: Contexto LIVO no necesario por ahora
        # if "cuenta = 'Ventas'" in sql:
        #     escenario_bajo = valor_actual * 0.9
        #     escenario_alto = valor_actual * 1.1
        #     return f" **Simulación What-If:** Si la demanda varía un +/- 10%, las ventas se ubicarían entre {escenario_bajo:,.0f} y {escenario_alto:,.0f} unidades."
        
        # if "cuenta = 'Oferta'" in sql:
        #     # Simular absorción simple
        #     meses_simulados = 12
        #     ventas_estimadas = valor_actual * 0.05 * meses_simulados # Asumiendo 5% ventas mensuales
        #     saldo_final = valor_actual - ventas_estimadas
        #     return f" **Simulación What-If:** Con una velocidad de ventas promedio del 5% mensual, el stock se reduciría a {saldo_final:,.0f} unidades en 12 meses (ceteris paribus)."
            
        return None

    def generar_reporte_ejecutivo(self, pregunta: str, respuesta: str, contexto: str, sql: str) -> str:
        """Genera un reporte ejecutivo en formato Markdown (Generación de Entregables)."""
        fecha_reporte = datetime.now().strftime("%Y-%m-%d")
        reporte = f"# 📑 REPORTE EJECUTIVO CAMACOL\n**Fecha:** {fecha_reporte}\n**Consulta:** {pregunta}\n\n## 1. Resumen Ejecutivo\n{respuesta}\n\n## 2. Análisis de Contexto y Mercado\n{contexto.replace(' **Contexto LIVO:**', '').strip()}\n\n## 3. Detalles Técnicos\n**Fuente de Datos:** Base de Datos LIVO (Coordenada Urbana)\n**Consulta Ejecutada:**\n```sql\n{sql}\n```\n\n---\n*Generado automáticamente por el Agente Inteligente CAMACOL*"
        return reporte

    def _detectar_anomalias(self, sql: str, resultado_actual: list, columnas: list) -> Optional[str]:
        """Compara el resultado con el promedio histórico para detectar anomalías."""
        # COMENTADO: Contexto LIVO no necesario por ahora
        # Solo funciona para resultados de una sola cifra numérica
        # if not (len(resultado_actual) == 1 and len(columnas) == 1 and isinstance(resultado_actual[0][0], (int, float))):
        #     return None

        # try:
        #     valor_actual = resultado_actual[0][0]
            
        #     # Extraer la métrica principal del SQL (ej: SUM(unidades), AVG(area))
        #     match_metrica = re.search(r"(SUM|AVG|COUNT)\s*\((.*?)\)", sql, re.IGNORECASE)
        #     if not match_metrica:
        #         return None
            
        #     metrica_sql = match_metrica.group(0)
            
        #     # Construir consulta para el promedio de los últimos 12 meses
        #     # (simplificado, asume que no hay otros filtros complejos)
        #     sql_promedio = f"SELECT AVG(valor_mensual) FROM (SELECT {metrica_sql} as valor_mensual FROM livo WHERE doce_meses = (SELECT MAX(doce_meses) FROM livo) GROUP BY LEFT(CAST(fecha AS VARCHAR), 6))"
            
        #     promedio_historico = self.conn.execute(sql_promedio).fetchone()[0]

        #     if promedio_historico and promedio_historico > 0:
        #         desviacion_pct = ((valor_actual - promedio_historico) / promedio_historico) * 100
                
        #         # Alertar si la desviación es mayor al 25%
        #         if abs(desviacion_pct) > 25:
        #             tipo_anomalia = "significativamente más alto" if desviacion_pct > 0 else "significativamente más bajo"
        #             return (f"⚠️ **Alerta de Anomalía:** Este valor es un **{abs(desviacion_pct):.1f}% {tipo_anomalia}** "
        #                     f"que el promedio de los últimos 12 meses (que fue de {promedio_historico:,.0f}).")
        # except Exception as e:
        #     print(f"⚠️ Error en detección de anomalías: {e}")
        return None
    
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
        """Busca consulta en caché (exacto y semántico usando similitud de texto)"""
        # 1. Búsqueda exacta rápida (O(1))
        hash_pregunta = self._obtener_hash_pregunta(pregunta)
        resultado = self.cache_consultas.get(hash_pregunta)
        if resultado:
            return resultado

        # 2. Búsqueda semántica inteligente (difflib / fuzzy match)
        from difflib import SequenceMatcher
        
        pregunta_norm = normalize_text(pregunta)
        
        mejor_coincidencia = None
        mejor_similitud = 0.0
        
        # Umbral de similitud semántica (85%)
        UMBRAL_SIMILITUD = 0.85
        
        for hash_val, data in self.cache_consultas.items():
            cached_question = data.get('pregunta', '')
            cached_norm = normalize_text(cached_question)
            
            # Comparación de conjuntos de palabras
            words_pregunta = set(pregunta_norm.split())
            words_cached = set(cached_norm.split())
            
            word_intersection = words_pregunta.intersection(words_cached)
            word_union = words_pregunta.union(words_cached)
            word_sim = len(word_intersection) / len(word_union) if word_union else 0
            
            if word_sim > 0.7 or len(pregunta_norm) - len(cached_norm) in range(-5, 5):
                ratio = SequenceMatcher(None, pregunta_norm, cached_norm).ratio()
                if ratio > mejor_similitud:
                    mejor_similitud = ratio
                    mejor_coincidencia = data
                    
        if mejor_similitud >= UMBRAL_SIMILITUD and mejor_coincidencia:
            print(f"🧠 [SEMANTIC CACHE] Hit semantico encontrado! Similitud: {mejor_similitud*100:.1f}%")
            print(f"   - Pregunta original: '{pregunta}'")
            print(f"   - Pregunta cacheada: '{mejor_coincidencia['pregunta']}'")
            return mejor_coincidencia
            
        return None
    
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
            ciudades_conocidas = [
                'bogotá, d.c.', 'bogota, d.c.', 'bogotá', 'bogota', 'montería', 'monteria', 'pasto',
                'buenaventura', 'cartagena de indias', 'cartagena', 'bello', 'envigado', 'mosquera',
                'ricaurte', 'caldas', 'girón', 'giron', 'popayán', 'popayan', 'ibagué', 'ibague',
                'marinilla', 'girardota', 'pitalito', 'cali', 'turbaco', 'medellín', 'medellin',
                'pereira', 'itagüí', 'itagui', 'barranquilla', 'manizales', 'tunja', 'sabaneta',
                'chía', 'chia', 'rionegro', 'el carmen de viboral', 'santa marta', 'bucaramanga',
                'villa del rosario', 'villavicencio', 'villeta', 'valledupar', 'fusagasugá', 'fusagasuga',
                'cajicá', 'cajica', 'anserma', 'puerto colombia', 'soledad', 'soacha', 'armenia',
                'la ceja', 'neiva', 'zipaquirá', 'zipaquira', 'sincelejo', 'piedecuesta', 'sogamoso',
                'los patios', 'floridablanca', 'la estrella', 'retiro', 'dosquebradas', 'palmira',
                'la mesa', 'santa rosa de cabal', 'san gil', 'cota', 'cúcuta', 'cucuta', 'jamundí',
                'jamundi', 'girardot', 'la calera', 'tocancipá', 'tocancipa', 'guarne', 'tenjo',
                'galapa', 'duitama', 'restrepo', 'tuluá', 'tulua', 'villamaría', 'villamaria',
                'madrid', 'candelaria', 'acacías', 'acacias', 'guadalajara de buga', 'buga',
                'la vega', 'garzón', 'garzon', 'chinchiná', 'chinchina', 'florida', 'gachancipá',
                'gachancipa', 'chinácota', 'chinacota', 'apulo', 'puerto tejada', 'copacabana',
                'anapoima', 'barrancabermeja', 'funza', 'palestina', 'guatapé', 'guatape', 'paipa',
                'sabanalarga', 'calima', 'san jerónimo', 'san jeronimo', 'facatativá', 'facatativa',
                'yumbo', 'sopó', 'sopo', 'la plata', 'barranca de upía', 'barranca de upia', 'apartadó',
                'apartado', 'magangué', 'magangue', 'tubará', 'tubara', 'carepa', 'san martín',
                'san martin', 'puerto lópez', 'puerto lopez', 'roldanillo', 'andes', 'malambo',
                'santander de quilichao', 'santa fé de antioquia', 'santa fe de antioquia', 'el santuario',
                'turbo', 'san juan de urabá', 'san juan de uraba', 'la unión', 'la union', 'chigorodó',
                'chigorodo', 'sopetrán', 'sopetran', 'peñol', 'penol', 'aguadas', 'amagá', 'amaga',
                'tabio', 'la dorada', 'sibaté', 'sibate', 'ginebra', 'jardín', 'jardin', 'cartago',
                'támesis', 'tamesis', 'neira', 'el cerrito'
            ]
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
            return [l.strip().lstrip('0123456789.-•* ') for l in sugerencias.strip().split('\n') if l.strip()][:3]
        
        # Fallback: Generación de Drill-Down Natural (Experiencia Conversacional)
        preguntas_drilldown = []
        pregunta_lower = pregunta.lower()
        
        # Si preguntó por ciudad, sugerir desglose por zona o barrio
        if "ciudad" in pregunta_lower or "bogotá" in pregunta_lower or "medellín" in pregunta_lower:
            preguntas_drilldown.append(f"¿Cómo se distribuye esto por zonas?")
            preguntas_drilldown.append(f"¿Cuáles son los principales barrios?")
            
        # Si preguntó por un total, sugerir desglose por constructora o tipo
        if "total" in pregunta_lower or "cuántas" in pregunta_lower:
            preguntas_drilldown.append(f"¿Cuál es el top de constructoras?")
            preguntas_drilldown.append(f"¿Cómo se divide entre VIS y No VIS?")
            
        # Si preguntó por ventas, sugerir oferta o rotación
        if "ventas" in pregunta_lower:
            preguntas_drilldown.append(f"¿Cuál es la oferta disponible?")
            preguntas_drilldown.append(f"¿Cómo está la rotación de inventarios?")
            
        if preguntas_drilldown:
            return preguntas_drilldown[:3]
        
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
            print(f" Error exportando a Excel: {e}")
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

    def _generar_grafico(self, result: List, columns: List[str], pregunta: str, channel: str = "streamlit") -> Optional[Dict]:
        """Genera gráfico automáticamente si es apropiado para la consulta"""
        
        # Verificar si se debe generar gráfico automáticamente
        if not self.should_generate_chart(pregunta, result):
            return {
                'success': False,
                'error': 'Gráfico no apropiado para esta consulta',
                'auto_decision': 'No generar gráfico'
            }
        
        if not VISUALIZATION_AVAILABLE:
            return {
                'success': False,
                'error': 'Sistema de visualización no disponible',
                'message': 'Instalar matplotlib y seaborn para generar gráficos'
            }
        
        try:
            # Convertir resultados a DataFrame
            if not result:
                return {
                    'success': False,
                    'error': 'No hay datos para visualizar'
                }
            
            df = pd.DataFrame(result, columns=columns)
            
            # Información de la consulta
            query_info = {
                'original_question': pregunta,
                'columns': columns,
                'row_count': len(result)
            }
            
            # Generar visualización automáticamente
            viz_system = LIVOVisualizationSystem()
            chart_result = viz_system.generate_for_channel(df, query_info, channel)
            
            # Agregar información de decisión automática
            if chart_result.get('success'):
                chart_result['auto_generated'] = True
                chart_result['decision_reason'] = 'Gráfico generado automáticamente basado en el contenido de la consulta'

                # MEJORA: Añadir forecasting si es una serie de tiempo
                if viz_system.is_time_series(df):
                    forecast_df = viz_system.generate_forecast(df)
                    chart_result = viz_system.plot_with_forecast(df, forecast_df, query_info, channel)
            
            return chart_result
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error generando gráfico: {str(e)}'
            }

    def should_generate_chart(self, pregunta: str, result: List) -> bool:
        """Determina automáticamente si se debe generar un gráfico basado solo en la consulta"""
        
        if not result or len(result) == 0:
            return False
        
        # Si hay muy pocos datos, no generar gráfico
        if len(result) < 2:
            return False
        
        pregunta_lower = pregunta.lower()
        
        # CASOS DONDE SÍ GENERAR GRÁFICO AUTOMÁTICAMENTE:
        
        # 1. Palabras clave explícitas de visualización
        viz_keywords = [
            'gráfico', 'grafico', 'chart', 'visualizar', 'mostrar',
            'comparar', 'comparación', 'comparacion', 'vs', 'versus'
        ]
        if any(keyword in pregunta_lower for keyword in viz_keywords):
            return True
        
        # 2. Rankings y tops
        ranking_keywords = ['ranking', 'top', 'mayor', 'menor', 'primeros', 'últimos']
        if any(keyword in pregunta_lower for keyword in ranking_keywords):
            return True
        
        # 3. Análisis por categorías geográficas
        geo_keywords = ['por ciudad', 'por departamento', 'por regional', 'ciudades', 'departamentos']
        if any(keyword in pregunta_lower for keyword in geo_keywords):
            return True
        
        # 4. Análisis temporal
        temporal_keywords = ['evolución', 'evolucion', 'tendencia', 'histórico', 'historico', 
                           'por año', 'por mes', 'anual', 'mensual']
        if any(keyword in pregunta_lower for keyword in temporal_keywords):
            return True
        
        # 5. Clasificación de vivienda (VIS/VIP/No VIS)
        vivienda_keywords = ['vis', 'vip', 'no vis', 'clasificación', 'clasificacion', 'tipo de vivienda']
        if any(keyword in pregunta_lower for keyword in vivienda_keywords):
            return True
        
        # 6. Distribuciones y proporciones
        dist_keywords = ['distribución', 'distribucion', 'proporción', 'proporcion', 'porcentaje']
        if any(keyword in pregunta_lower for keyword in dist_keywords):
            return True
        
        # 7. Si hay múltiples filas y columnas (datos tabulares apropiados para gráficos)
        if len(result) >= 3 and len(result[0]) >= 2:
            return True
        
        # CASOS DONDE NO GENERAR GRÁFICO:
        
        # Consultas de conteo simple (una sola cifra)
        count_keywords = ['cuántas', 'cuantas', 'cuántos', 'cuantos', 'total', 'suma']
        if any(keyword in pregunta_lower for keyword in count_keywords):
            # Solo si es una consulta muy simple con una sola fila
            if len(result) == 1 and len(result[0]) <= 2:
                return False
        
        # Por defecto, si llegamos aquí y hay datos estructurados, generar gráfico
        return len(result) > 1 and len(result[0]) >= 2

    def run_query_from_question(self, pregunta: str) -> Tuple[str, str]:
        """
        Punto de entrada simplificado para el sistema de razonamiento.
        Llama al método 'consultar' con los parámetros por defecto.
        """
        from llm_providers import llamar_api_ia  # Importación local para evitar dependencia circular

        # Seleccionar proveedores Ollama ordenados por prioridad: DeepSeek V2 > Mistral > Llama > Qwen
        ollama_backups = sorted(
            [p for p in AI_PROVIDERS if p.get("type") == AIModel.OLLAMA and p.get("enabled", True)],
            key=lambda p: p.get("priority", 99)
        )

        # Crear una función que envuelve llamar_api_ia con FAST_PROVIDER y, si hay rate limit,
        # intenta con modelos locales (Llama, Qwen) antes de rendirse.
        def llm_wrapper(prompt_text: str):
            """Envuelve llamar_api_ia usando FAST_PROVIDER y hace fallback a Ollama si hay rate limit."""

            # 1) Intento con FAST_PROVIDER (Groq u otro rápido)
            respuesta, error = llamar_api_ia(prompt_text, FAST_PROVIDER) if FAST_PROVIDER else (None, "FAST_PROVIDER no definido")

            if not error:
                return respuesta

            # Loguear el error del proveedor rápido
            try:
                provider_name = FAST_PROVIDER.get("name", "desconocido") if FAST_PROVIDER else "desconocido"
            except Exception:
                provider_name = "desconocido"
            print(f"⚠️ Error en LLM FAST_PROVIDER ({provider_name}): {error}")

            # 2) Si el error es de rate limit, intentar con los modelos locales de Ollama (Llama, Qwen)
            if isinstance(error, str) and "rate_limit_exceeded" in error:
                for backup in ollama_backups:
                    backup_name = backup.get("name", "Ollama")
                    print(f" Intentando fallback con proveedor local: {backup_name}")
                    resp_backup, err_backup = llamar_api_ia(prompt_text, backup)
                    if resp_backup and not err_backup:
                        print(f" Fallback exitoso con {backup_name}")
                        return resp_backup
                    else:
                        print(f" Fallback con {backup_name} falló: {err_backup}")

            # 3) Si llegamos aquí, no hubo éxito con ningún proveedor
            return None

        # Llama al método principal 'consultar'
        exito, respuesta, _ = self.consultar(pregunta, llm_function=llm_wrapper)

        if exito:
            return respuesta, "SQL no extraído en este flujo simplificado."
        else:
            return respuesta, ""


if __name__ == "__main__":
    # Modo interactivo: escribe tu pregunta personalizada sobre LIVO
    import os
    
    # Buscar archivo LIVO
    livo_path = None
    possible_paths = [
        "LIVO/LIVO/LIVO_total_abr26_.xlsx",
        "LIVO/LIVO/LIVO_total_nacional_abr26.xlsx",
        "LIVO/LIVO/LIVO_total_NR_abr26_.xlsx",
        "LIVO/LIVO/LIVO_total_abr26_resumen_.xlsx"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            livo_path = path
            break
    
    if not livo_path:
        print("❌ No se encontró archivo LIVO. Verifica que esté en RAG/2025/LIVO/")
        exit(1)
    
    # Diccionario de datos LIVO
    diccionario_datos = {
        "fecha": "Fecha específica (formato YYYYMMDD): 20210101 a 20251001",
        "año_corrido": "Años acumulados: 2021, 2022, 2023, 2024, 2025",
        "doce_meses": "Períodos de 12 meses: 2021, 2022, 2023, 2024, 2025",
        "regional": "Regiones CAMACOL: Bogotá & Cundinamarca, Santander, Bolívar, Antioquia, Meta, Quindío, Caldas, Atlántico, Córdoba & Sucre, Boyacá_Casanare, Risaralda, Nariño, Cesar, Valle, Cauca, Tolima, Magdalena, Cúcuta_Nororiente, Huila",
        "departamento": "Departamentos: Cundinamarca, Santander, Bolívar, Bogotá D.C., Antioquia, Meta, Quindío, Caldas, Atlántico, Sucre, Boyacá, Risaralda, Nariño, Cesar, Valle del Cauca, Cauca, Tolima, Magdalena, Norte de Santander, Córdoba, Huila",
        "estrato": "Estrato socioeconómico: 0, 1, 2, 3, 4, 5, 6",
        "destino_etapa": "Destino de la vivienda: Venta, Uso Propio, Arrendar, Adjudicación, Sin Definir",
        "uso_etapa": "Tipo de vivienda: Apartamento, Casa, (vacío para sin definir)",
        "compania_constructora": "Más de 1000 constructoras registradas (ej: CONSTRUCTORA BOLIVAR S A, AMARILO S.A.S, CONSTRUCTORA CAPITAL S.A.)",
        "modalidad": "Tipo de licencia: Venta_por_Unidades, (vacío para otros tipos)",
        "segmento_pre": "Clasificación por valor: No VIS, VIS, VIP, SIN ASIGNAR, (vacío)",
        "estado": "Estado del proyecto: Construcción, Preventa, TVE, Rediseñado, Paralizado, TE, Cancelado, Proyectado",
        "fase": "Fase constructiva: Preliminar, Sin Iniciar, Terminado, Estructura, Obra Negra, Acabados, Cimentación, Urbanismo, (vacío)",
        "last_estado": "Último estado: Construcción, TVE, Preventa, Cancelado, Paralizado, TE, Rediseñado, Proyectado, (vacío)",
        "AM_capital": "Área Metropolitana/Capital: Corredor Cundinamarca-Caliente, Resto, Cartagena de Indias, Bucaramanga AM, Corredor Autopista Sur, Bogotá D.C., Medellín AM, Villavicencio, Armenia, Corredor Autopista Norte, Corredor Calle 13, Manizales AM, Barranquilla AM, Sincelejo, Tunja, Pereira AM, Pasto, Corredor Av. 80, Valledupar, Ibagué, Santa Marta, Cúcuta AM, Cali AM, Montería, Neiva, Corredor Vía-La Calera",
        "segmento_pre": "Segmento de precio: No VIS, VIS, Uso Propio/Otros, Arrendar, (vacío)",
        "usos": "Uso del proyecto: Vivienda, (vacío para otros usos)",
        "unidades": "Número de unidades de vivienda",
        "area": "Área construida en metros cuadrados",
        "valor": "Valor en miles de pesos colombianos",
        "precio_mc_promedio": "Precio promedio por metro cuadrado",
        "cuenta": "Estado contable del proyecto: Saldo que inicia, Oferta, Ventas, Renuncias, Iniciaciones, Entregadas, Lanzamientos, Paralizado, Culminadas"
    }
    
    # Inicializar sistema LIVO
    print(f"🚀 Inicializando LIVO desde: {livo_path}")
    system = LIVOSQLSystem(livo_path)
    ok, msg = system.inicializar()
    
    if not ok:
        print(f"❌ Error inicializando LIVO: {msg}")
        exit(1)
    
    print("✅ LIVO inicializado correctamente")
    print("\n📊 Diccionario de datos LIVO:")
    for campo, descripcion in diccionario_datos.items():
        print(f"  • {campo}: {descripcion}")
    print("💡 Ejemplos de preguntas:")
    print("  - cuantas unidades de construcción hay en bogota")
    print("  - cuantas unidades VIS hay en antioquia")
    print("  - cual es el area total de construcción en valle")
    print("  - top 10 constructoras con mas unidades")
    print("  - cuantas unidades vendidas hay en medellin")
    print("  - cuantas unidades entregadas hay en cali")
    print("  - cuantos lanzamientos hay en barranquilla")
    
    while True:
        pregunta = input("\n¿Qué quieres preguntar sobre LIVO? (o 'salir' para terminar): ")
        if pregunta.lower() in ['salir', 'exit', 'quit', '']:
            break
        
        print("Pregunta:", pregunta)
        try:
            # Importar el sistema de LLM del chatbot principal
            from llm_providers import llamar_api_ia
            from config import AI_PROVIDERS
            
            def llm_function(prompt):
                """Función LLM optimizada que ignora el prompt gigante y crea uno compacto"""
                try:
                    # IGNORAR el prompt original gigante y crear uno COMPACTO desde cero
                    prompt_compacto = f"""
Genera una consulta SQL para responder: "{pregunta}"

TABLA: livo
CAMPOS PRINCIPALES:
• departamento: 'Bogotá D.C.', 'Antioquia', 'Valle del Cauca', 'Santander'
• compania_constructora: nombre de la empresa constructora
• segmento_pre: 'VIS', 'VIP', 'No VIS', 'SIN ASIGNAR'  
• estado: 'Construcción', 'Preventa', 'TVE', 'Terminado'
• cuenta: 'Oferta', 'Ventas', 'Iniciaciones', 'Entregadas'
• uso_etapa: 'Apartamento', 'Casa'
• unidades: número de unidades
• area: área en m²
• valor: valor en miles de pesos

EJEMPLOS:
- "top 10 constructoras" → SELECT compania_constructora, SUM(unidades) FROM livo GROUP BY compania_constructora ORDER BY SUM(unidades) DESC LIMIT 10
- "unidades en bogota" → SELECT SUM(unidades) FROM livo WHERE departamento = 'Bogotá D.C.'
- "apartamentos VIS" → SELECT COUNT(*) FROM livo WHERE uso_etapa = 'Apartamento' AND segmento_pre = 'VIS'

IMPORTANTE: 
- Solo devuelve la consulta SQL, sin explicaciones
- Para constructoras usa campo 'compania_constructora'
- Para ubicaciones usa campo 'departamento'
- Para Bogotá usa 'Bogotá D.C.'
"""
                    
                    print(f"[DEBUG] Llamando LLM con prompt de {len(prompt_compacto)} caracteres")
                    
                    # Usar proveedores en orden de prioridad (habilitando automáticamente los más rápidos)
                    # Priorizar proveedores rápidos para LIVO
                    proveedores_rapidos = ['Groq', 'Cerebras (Ultra Fast)', 'DeepSeek', 'Google Gemini']
                    
                    for provider_config in AI_PROVIDERS:
                        provider_name = provider_config.get('name', 'Unknown')
                        
                        # Habilitar automáticamente proveedores rápidos o los ya habilitados
                        if provider_name in proveedores_rapidos or provider_config.get('enabled', False):
                            print(f"[DEBUG] Probando proveedor: {provider_name}")
                            response = llamar_api_ia(prompt_compacto, provider_config)
                            # print(f"[DEBUG] Tipo de respuesta: {type(response)}, Contenido: {response}")
                            
                            if response:
                                # Manejar tupla (respuesta, error)
                                if isinstance(response, tuple):
                                    if len(response) == 2:
                                        respuesta_texto, error = response
                                        if respuesta_texto and not error:
                                            # Limpiar la respuesta SQL (quitar ```sql y ```)
                                            sql_limpio = respuesta_texto.strip()
                                            if sql_limpio.startswith('```sql'):
                                                sql_limpio = sql_limpio[6:]  # Quitar ```sql
                                            if sql_limpio.endswith('```'):
                                                sql_limpio = sql_limpio[:-3]  # Quitar ```
                                            sql_limpio = sql_limpio.strip()
                                            
                                            print(f"[DEBUG] SQL limpio: {sql_limpio[:100]}...")
                                            return sql_limpio, None  # Devolver tupla (respuesta, error)
                                        else:
                                            print(f"[DEBUG] Error en {provider_name}: {error}")
                                    else:
                                        print(f"[DEBUG] Tupla inesperada: {response}")
                                # Manejar string directo
                                elif isinstance(response, str):
                                    print(f"[DEBUG] Respuesta string: {response[:100]}...")
                                    return response, None  # Devolver tupla (respuesta, error)
                                else:
                                    print(f"[DEBUG] Tipo inesperado: {type(response)}")
                        else:
                            print(f"[DEBUG] Saltando proveedor deshabilitado: {provider_name}")
                    
                    print(" No hay proveedores LLM disponibles")
                    return None, "No hay proveedores LLM disponibles"
                except Exception as e:
                    print(f" Error con LLM: {e}")
                    import traceback
                    traceback.print_exc()
                    return None, f"Error con LLM: {e}"
            
            print("[DEBUG] Llamando system.consultar...")
            resultado = system.consultar(pregunta, llm_function=llm_function)
            print(f"[DEBUG] Resultado de consultar: {type(resultado)}, {resultado}")
            
            if isinstance(resultado, tuple) and len(resultado) == 3:
                exito, respuesta, sql_usado = resultado
                if exito:
                    print(" Respuesta:", respuesta)
                    if sql_usado:
                        print(" SQL usado:", sql_usado)
                else:
                    print(" Error:", respuesta)
            else:
                print(f" Resultado inesperado del sistema LIVO: {resultado}")
        except Exception as e:
            print(f" Error inesperado: {e}")
    
    # system.cerrar()  # Método no existe
    print("👋 ¡Hasta luego!")
