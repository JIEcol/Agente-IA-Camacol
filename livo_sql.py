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
        
        # Estados y fases del proyecto
        'estado': {
            'tipo': 'VARCHAR',
            'descripcion': 'Estado actual del proyecto',
            'sinonimos': ['estatus', 'situación', 'condición', 'cómo está', 'estado actual', 'vendido', 'en obra', 'terminado'],
            'valores_completos': ['Construcción', 'Preventa', 'TVE', 'Rediseñado', 'Paralizado', 'TE', 'Cancelado', 'Proyectado']
        },
        'fase': {
            'tipo': 'VARCHAR',
            'descripcion': 'Fase del proyecto',
            'sinonimos': ['etapa', 'progreso', 'ciclo', 'momento del proyecto', 'en qué etapa va', 'preventa', 'lanzamiento']
        },
        'last_estado': {
            'tipo': 'VARCHAR',
            'descripcion': 'Estado anterior del proyecto',
            'sinonimos': ['estado anterior', 'último estatus', 'condición previa', 'estado histórico']
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
        'tipo_vivienda': {
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
        
        # 1. Cargar caché de consultas
        self.cache_consultas = {}
        self.cache_file = Path('cache_livo_consultas.json')
        self._cargar_cache()
        
        # 2. Inicializar caché semántico (si está disponible)
        self.semantic_cache_embeddings = None
        if SEMANTIC_CACHE_AVAILABLE:
            self.semantic_cache_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            self.semantic_cache_embeddings = self._build_semantic_cache_embeddings()
        
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
                    
                    df = pd.read_excel(self.livo_path)
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
        - Si hay una sola celda numérica: devuelve directamente ese valor en texto.
        - En otros casos: construye una tabla básica texto con encabezados.
        """
        # Sin filas
        if not result:
            return f"No se encontraron resultados para la consulta. SQL: {sql}"

        # Una fila, una o dos columnas (caso típico de SUM o AVG, o comparación anual)
        if len(result) == 1 and len(columns) in [1, 2]:
            valor = result[0][0]
            # Formatear la respuesta de una o dos columnas
            respuesta_formateada = []
            for i, col_name in enumerate(columns):
                valor_celda = result[0][i]
                nombre_columna_limpio = col_name.replace('_', ' ')
                if isinstance(valor_celda, (int, float)):
                    respuesta_formateada.append(f"**{nombre_columna_limpio}:** {valor_celda:,.0f}")
                else:
                    respuesta_formateada.append(f"**{nombre_columna_limpio}:** {valor_celda}")
            return "\n".join(respuesta_formateada)

        # Tabla sencilla
        lineas = []
        # Encabezados
        column_names = [str(c).replace('_', ' ') for c in columns]
        encabezado = " | ".join(column_names)
        separador = " | ".join(["-" * len(c) for c in column_names])
        lineas.append(encabezado)
        lineas.append(separador)
        # Filas
        for fila in result:
            lineas.append(" | ".join(str(v) for v in fila))

        return "\n".join(lineas)

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
        # DEBUG: mostrar cómo se normaliza la pregunta
        try:
            print(f"[DEBUG LIVO reglas] Pregunta original: {pregunta}")
            print(f"[DEBUG LIVO reglas] Pregunta normalizada: {texto}")
        except Exception:
            pass

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

        # --- DETECCIÓN DE MÉTRICA ---
        # Por defecto unidades, pero cambia si piden valor o precio m2
        metrica_sql = "COALESCE(SUM(unidades), 0)"
        alias_sql = "unidades_filtradas"
        
        if any(x in texto for x in ['metro cuadrado', 'm2', 'precio promedio m2']):
            metrica_sql = "AVG(precio_mc_promedio)"
            alias_sql = "precio_m2_promedio"
        elif any(x in texto for x in ['valor', 'precio', 'pesos', 'monetario', 'costo', 'dinero', 'plata']):
            metrica_sql = "COALESCE(SUM(valor), 0)"
            alias_sql = "valor_total"
        elif "proyecto" in texto: # Detectar conteo de proyectos
            metrica_sql = "COUNT(DISTINCT identificador)"
            alias_sql = "total_proyectos"
        
        # Detección de intención temporal general (para saber si filtrar por último periodo o no)
        temporal_keywords = [
            '201', '202', # Años 201x, 202x
            'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
            'mes', 'anio', 'ano', 'trimestre', 'semestre', 'ultimo', 'reciente', 'actual'
        ]
        tiene_tiempo = any(k in texto for k in temporal_keywords)

        # Detección de año explícito
        anio_match = re.search(r"(20[0-9]{2})", texto)
        anio_filtro = f" AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {anio_match.group(1)}" if anio_match else ""

        # Detección de mes explícito
        mes_filtro = ""
        meses_map_regex = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
            'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
        }
        for mes_nombre, mes_num in meses_map_regex.items():
            if mes_nombre in texto:
                mes_filtro = f" AND CAST(SUBSTR(CAST(fecha AS VARCHAR), 5, 2) AS INTEGER) = {mes_num}"
                break

        # Decidir el filtro final
        filtro_temporal = ""
        if anio_filtro and mes_filtro:
            filtro_temporal = f"{anio_filtro} {mes_filtro}"
        elif anio_filtro or mes_filtro:
            filtro_temporal = anio_filtro or mes_filtro
        
        # Si no hay filtro explícito y no se menciona tiempo, usar el último periodo disponible
        if not filtro_temporal and not tiene_tiempo:
            filtro_temporal = " AND fecha = (SELECT MAX(fecha) FROM livo)"
            
        # Manejo explícito de "último año" o "últimos 12 meses"
        if "ultimo ano" in texto or "ultimo año" in texto or "ultimos 12 meses" in texto:
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

        elif not filtro_temporal: # Si no hay filtro de año o mes, y no es "ultimo año", usar el de fecha máxima
            # Evitar usar MAX(fecha) si hay cualquier otra palabra temporal
            temporal_keywords_genericas = ['año', 'mes', 'trimestre', 'semestre', 'periodo', 'fecha', 'cuándo', 'reciente', 'actual']
            if not any(k in texto for k in temporal_keywords_genericas):
                filtro_temporal = " AND fecha = (SELECT MAX(fecha) FROM livo)"

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

        # --- LÓGICA ESPECIAL PARA OFERTA (STOCK) ---
        # Si piden oferta y un año, NO sumar todo el año. Tomar el último corte.
        # EXCEPCIÓN: Si se menciona un mes específico, dejar que el LLM maneje la consulta puntual.
        meses_especificos = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 
                           'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        tiene_mes = any(m in texto for m in meses_especificos)

        if "oferta" in texto and not tiene_mes:
            if anio_match:
                anio = int(anio_match.group(1))
                region = self._extraer_region_general(texto)
                if region:
                    region_cond = self._condicion_region_general(region)
                    
                    # SQL para Promedio y Cierre
                    sql = f"""
                    WITH mensual AS (
                        SELECT CAST(SUBSTR(CAST(fecha AS VARCHAR), 5, 2) AS INTEGER) as mes, SUM(unidades) as total_mensual
                        FROM livo
                        WHERE cuenta = 'Oferta' 
                          AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = {anio}
                          AND {region_cond}
                          AND uso_etapa IN ('Casa', 'Apartamento')
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
                          AND uso_etapa IN ('Casa', 'Apartamento')
                    )
                    SELECT 
                        CAST(p.val AS INTEGER) as "Oferta Promedio {anio}", 
                        CAST(c.val AS INTEGER) as "Oferta Cierre {anio}"
                    FROM promedio p, cierre c
                    """
                    try:
                        print(f"[DEBUG LIVO reglas] SQL generado (Oferta Stock Anual Completo): {sql}")
                        return sql
                    except Exception:
                        pass

        # --- TIER 1: REGLAS DE NEGOCIO INDEPENDIENTES Y ESPECÍFICAS ---
        # Estas reglas tienen lógica de negocio implícita (ej: filtrar por vivienda para venta)
        # y se ejecutan primero para las preguntas más comunes.

        # 0) Rotación de Inventarios (PRIORIDAD ALTA)
        if "rotacion" in texto or "rotación" in texto:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # SQL para calcular rotación (Meses de oferta)
            # Fórmula: Oferta Actual / Promedio Ventas (últimos 12 meses)
            sql = f"""
            WITH oferta_actual AS (
                SELECT COALESCE(SUM(unidades), 0) as oferta
                FROM livo
                WHERE cuenta = 'Oferta'
                  AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')
                  AND {region_cond}
                  AND uso_etapa IN ('Casa', 'Apartamento')
            ),
            ventas_12m AS (
                SELECT CAST(SUBSTR(CAST(fecha AS VARCHAR), 1, 6) AS INTEGER) as mes_anio, SUM(unidades) as total_mensual
                FROM livo
                WHERE cuenta = 'Ventas'
                  AND doce_meses = (SELECT MAX(doce_meses) FROM livo)
                  AND {region_cond}
                  AND uso_etapa IN ('Casa', 'Apartamento')
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

        # 0b) Top Constructoras (Ranking) - PRIORIDAD ALTA
        if ("top" in texto or "ranking" in texto or "mejores" in texto) and ("constructora" in texto or "empresa" in texto):
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Intentar detectar número (top 5, top 10)
            limit = 5
            match_num = re.search(r"top\s+(\d+)", texto)
            if match_num:
                limit = int(match_num.group(1))
            
            # Definir métrica (por defecto Ventas último año si no se especifica oferta)
            if "oferta" in texto:
                cuenta_filtro = "cuenta = 'Oferta'"
                # Para oferta usamos la fecha más reciente (stock)
                tiempo_filtro = "AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')"
            else:
                # Por defecto Ventas (acumulado 12 meses)
                cuenta_filtro = "cuenta = 'Ventas'"
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
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_vis_sin_vip "
                    "FROM livo "
                    f"WHERE tipo_vivienda = 'VIS' AND {region_cond} "
                    "AND uso_etapa IN ('Casa', 'Apartamento') "
                    "AND destino_etapa = 'Venta'"
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
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_vis "
                    "FROM livo "
                    "WHERE tipo_vivienda IN ('VIS', 'VIP') "
                    f"AND {region_cond} "
                    "AND uso_etapa IN ('Casa', 'Apartamento') "
                    "AND destino_etapa = 'Venta'"
                    f"{filtro_temporal}"
                )
                try:
                    print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (VIS total): {sql}")
                    return sql
                except Exception:
                    pass

        # 3) Unidades totales de vivienda No VIS por región
        if "no vis" in texto and "unidades" in texto:
            region = self._extraer_region_general(texto)
            if region:
                region_cond = self._condicion_region_general(region)
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_no_vis "
                    "FROM livo "
                    f"WHERE tipo_vivienda = 'No VIS' AND {region_cond} "
                    "AND uso_etapa IN ('Casa', 'Apartamento') "
                    "AND destino_etapa = 'Venta'"
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
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_vip "
                    "FROM livo "
                    f"WHERE tipo_vivienda = 'VIP' AND {region_cond} "
                    "AND uso_etapa IN ('Casa', 'Apartamento') "
                    "AND destino_etapa = 'Venta'"
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
        ):
            region = self._extraer_region_general(texto)
            if region:
                region_cond = self._condicion_region_general(region)
                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_totales "
                    "FROM livo "
                    f"WHERE {region_cond} "
                    "AND uso_etapa IN ('Casa', 'Apartamento') "
                    "AND destino_etapa = 'Venta'"
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

                anio = _extraer_anio(texto)
                rangos = SalarioMinimoColombiano.calcular_rangos_vivienda(anio)
                salario = SalarioMinimoColombiano.obtener_salario_minimo(anio)

                vis_min_miles = rangos['VIS']['min'] // 1000
                limite_500_miles = (salario * 500) // 1000

                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_precio_vis_a_500_smmlv "
                    "FROM livo "
                    f"WHERE {region_cond} "
                    f"AND valor >= {vis_min_miles} "
                    f"AND valor <= {limite_500_miles} "
                    "AND uso_etapa IN ('Casa', 'Apartamento') "
                    "AND destino_etapa = 'Venta'"
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

                anio = _extraer_anio(texto)
                salario = SalarioMinimoColombiano.obtener_salario_minimo(anio)
                limite_500_miles = (salario * 500) // 1000

                sql = (
                    f"SELECT {metrica_sql} AS {alias_sql}_precio_mayor_500_smmlv "
                    "FROM livo "
                    f"WHERE {region_cond} "
                    f"AND valor > {limite_500_miles} "
                    "AND uso_etapa IN ('Casa', 'Apartamento') "
                    "AND destino_etapa = 'Venta'"
                    f"{filtro_temporal}"
                )
                try:
                    print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (precio > 500 SMMLV): {sql}")
                    return sql
                except Exception:
                    pass

        # 8) Lanzamientos de vivienda (VIP, VIS, No VIS o Total)
        if "lanzamientos" in texto or "lanzadas" in texto:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Determinar tipo de vivienda
            tipo_filtro = ""
            if "vip" in texto:
                tipo_filtro = "AND tipo_vivienda = 'VIP'"
            elif "no vis" in texto:
                tipo_filtro = "AND tipo_vivienda = 'No VIS'"
            elif "vis" in texto: # VIS total (incluye VIP si no se dice 'sin vip')
                if "sin vip" in texto:
                    tipo_filtro = "AND tipo_vivienda = 'VIS'"
                else:
                    tipo_filtro = "AND tipo_vivienda IN ('VIS', 'VIP')"
            
            sql = (
                f"SELECT {metrica_sql} AS {alias_sql}_lanzamientos "
                "FROM livo "
                f"WHERE cuenta = 'Lanzamientos' "
                f"AND {region_cond} "
                f"{tipo_filtro} "
                "AND uso_etapa IN ('Casa', 'Apartamento') "
                "AND destino_etapa = 'Venta'"
                f"{filtro_temporal}"
            )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Lanzamientos): {sql}")
                return sql
            except Exception:
                pass

        # 9) Iniciaciones de vivienda (VIP, VIS, No VIS o Total)
        if "iniciaciones" in texto or "iniciadas" in texto:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Determinar tipo de vivienda
            tipo_filtro = ""
            if "vip" in texto:
                tipo_filtro = "AND tipo_vivienda = 'VIP'"
            elif "no vis" in texto:
                tipo_filtro = "AND tipo_vivienda = 'No VIS'"
            elif "vis" in texto: # VIS total (incluye VIP si no se dice 'sin vip')
                if "sin vip" in texto:
                    tipo_filtro = "AND tipo_vivienda = 'VIS'"
                else:
                    tipo_filtro = "AND tipo_vivienda IN ('VIS', 'VIP')"
            
            sql = (
                f"SELECT {metrica_sql} AS {alias_sql}_iniciaciones "
                "FROM livo "
                f"WHERE cuenta = 'Iniciaciones' "
                f"AND {region_cond} "
                f"{tipo_filtro} "
                "AND uso_etapa IN ('Casa', 'Apartamento') "
                "AND destino_etapa = 'Venta'"
                f"{filtro_temporal}"
            )
            try:
                print(f"[DEBUG LIVO reglas] SQL INDEPENDIENTE (Iniciaciones): {sql}")
                return sql
            except Exception:
                pass

        # 10) Ventas totales (Definición estricta: Cuenta=Ventas + Región + Tiempo, sin filtros extra)
        if "ventas totales" in texto:
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
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

        # 11) Oferta disponible/total (Definición estricta: Cuenta=Oferta + Región + Tiempo, sin filtros extra)
        if "oferta disponible" in texto or "oferta total" in texto:
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
        if "oferta" in texto and any(t in texto for t in ["vip", "vis", "no vis"]):
            region = self._extraer_region_general(texto)
            region_cond = self._condicion_region_general(region) if region else "1=1"
            
            # Determinar tipo
            tipo_filtro = ""
            if "vip" in texto:
                tipo_filtro = "AND tipo_vivienda = 'VIP'"
            elif "no vis" in texto:
                tipo_filtro = "AND tipo_vivienda = 'No VIS'"
            elif "vis" in texto:
                if "sin vip" in texto:
                    tipo_filtro = "AND tipo_vivienda = 'VIS'"
                else:
                    tipo_filtro = "AND tipo_vivienda IN ('VIS', 'VIP')"
            
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
            
            # Usar último corte de oferta para precios actuales
            final_temporal = " AND fecha = (SELECT MAX(fecha) FROM livo WHERE cuenta = 'Oferta')"
            
            sql = (
                f"SELECT AVG(precio_mc_promedio) AS {alias_sql} "
                "FROM livo "
                f"WHERE cuenta = 'Oferta' "
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
        if region:
            filtros.append(self._condicion_region_general(region))
            
        # 2. Temporalidad (Año/Fecha)
        if filtro_temporal:
            clean_temporal = filtro_temporal.strip()
            if clean_temporal.upper().startswith("AND "):
                clean_temporal = clean_temporal[4:].strip()
            filtros.append(clean_temporal)

        # 3. Tipo de Vivienda (VIS/VIP/No VIS)
        tipos_interes = []
        
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
            if len(tipos_interes) == 1:
                filtros.append(f"tipo_vivienda = {tipos_interes[0]}")
            else:
                filtros.append(f"tipo_vivienda IN ({', '.join(tipos_interes)})")
                # Si hay múltiples tipos o intención de comparar, preparar agrupación
                if len(tipos_interes) > 1 or any(x in texto for x in ['comparar', 'vs', 'diferencia', 'distribucion']):
                    if "tipo_vivienda" not in group_by_cols:
                        group_by_cols.append("tipo_vivienda")

        # 4. Cuenta (Estado contable)
        cuentas_map = {
            # Saldo que inicia
            'saldo que inicia': 'Saldo que inicia', 'saldo inicial': 'Saldo que inicia', 'inventario inicial': 'Saldo que inicia',
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

        # --- CONSTRUCCIÓN FINAL DEL SQL ---
        # Solo construir si se detectó al menos un filtro
        if filtros:
            # --- LÓGICA DE NEGOCIO ADICIONAL (Contexto de Vivienda para Venta) ---
            # Palabras clave que implican una consulta sobre el mercado de vivienda para la venta
            housing_sale_keywords = [
                'vis', 'vip', 'no vis', 'vivienda de interes', 
            'precio entre', 'precio mayor', 'unidades totales de vivienda',
            'ventas', 'lanzamientos', 'lanzadas', 'iniciaciones', 'iniciadas', 'oferta'
            ]
            is_housing_sale_query = any(k in texto for k in housing_sale_keywords)
            
            # Verificar si ya se aplicaron filtros de uso o destino
            has_uso_filter = any('uso_etapa' in f for f in filtros)
            has_destino_filter = any('destino_etapa' in f for f in filtros)

            # Aplicar filtros por defecto si es una consulta de vivienda para venta y no se especificó lo contrario
            if is_housing_sale_query:
                if not has_uso_filter:
                    filtros.append("uso_etapa IN ('Casa', 'Apartamento')")
                if not has_destino_filter:
                    # Solo aplicar destino venta si es vivienda (o si no se especificó uso)
                    # Si se especificó un uso no residencial, no forzar destino venta a menos que sea explícito
                    if not has_uso_filter or any(k in texto for k in ['venta', 'vendida', 'comercializada', 'lanzadas', 'lanzamientos']):
                        filtros.append("destino_etapa = 'Venta'")

            where_clause = " AND ".join(filtros)
            
            # --- PROTECCIÓN OFERTA: NO SUMAR ENTRE PERIODOS ---
            # Si se consulta 'Oferta', forzar que sea solo del último periodo disponible dentro del rango filtrado.
            if any("cuenta = 'Oferta'" in f for f in filtros):
                # Subconsulta para encontrar la fecha máxima que cumple con los filtros actuales
                subquery_max_fecha = f"(SELECT MAX(fecha) FROM livo WHERE {where_clause})"
                where_clause += f" AND fecha = {subquery_max_fecha}"
            
            # Construcción de SELECT y GROUP BY
            cols_select = [f"{metrica_sql} AS {alias_sql}"]
            group_by_clause = ""
            
            if group_by_cols:
                cols_select = group_by_cols + cols_select
                group_by_clause = f" GROUP BY {', '.join(group_by_cols)} ORDER BY {alias_sql} DESC"

            sql = (
                f"SELECT {', '.join(cols_select)} "
                "FROM livo "
                f"WHERE {where_clause}"
                f"{group_by_clause}"
            )
            try:
                print(f"[DEBUG LIVO reglas] SQL Combinatorio (con lógica de negocio) generado: {sql}")
                return sql
            except Exception:
                pass

        # Si no se reconoce el patrón, no generamos SQL
        return None

    def _extraer_region_general(self, texto_local: str) -> Optional[str]:
        """Extrae región usando lista conocida (más robusto que regex "en ...")"""
        ubicaciones = [
            'bogota d.c.', 'bogota', 'antioquia', 'valle del cauca', 'valle',
            'atlantico', 'cundinamarca', 'bolivar', 'santander', 'norte de santander',
            'caldas', 'risaralda', 'quindio', 'huila', 'tolima', 'narino', 'cauca',
            'cesar', 'cordoba', 'sucre', 'magdalena', 'meta', 'boyaca', 'cucuta', 
            'boyaca_casanare', 'cucuta_nororiente', 'nacional', 'colombia', 'pais', 'todo el pais',
            # Ciudades capitales y principales
            'medellin', 'cali', 'barranquilla', 'cartagena', 'bucaramanga', 'pereira',
            'manizales', 'ibague', 'santa marta', 'villavicencio', 'pasto', 'monteria',
            'valledupar', 'popayan', 'armenia', 'neiva', 'tunja', 'riohacha', 'sincelejo',
            'florencia', 'yopal', 'quibdo', 'san andres', 'leticia', 'mocoa', 'mitu',
            'puerto carreno', 'inirida', 'san jose del guaviare', 'arauca'
        ]
        # Ordenar por longitud descendente para coincidir "valle del cauca" antes que "valle"
        ubicaciones.sort(key=len, reverse=True)
        
        for ubicacion in ubicaciones:
            if re.search(r'\b' + re.escape(ubicacion) + r'\b', texto_local):
                return ubicacion
        return None

    def _condicion_region_general(self, region_fragmento: str) -> str:
        """Genera condición SQL para región."""
        # Para evitar problemas de tildes, normalizamos ambos lados.
        # 1) Normalizamos el fragmento en Python (sin tildes, minúsculas)
        frag_norm = normalize_text(region_fragmento).replace(' y ', ' & ').replace(' - ', ' & ').upper()
        
        # Caso especial: espacio simple "BOGOTA CUNDINAMARCA" -> "BOGOTA & CUNDINAMARCA"
        frag_norm = frag_norm.replace('BOGOTA CUNDINAMARCA', 'BOGOTA & CUNDINAMARCA')
        frag_norm = frag_norm.replace('CORDOBA SUCRE', 'CORDOBA & SUCRE')

        # Si es una referencia nacional, no filtrar (traer todo)
        if frag_norm in ['NACIONAL', 'COLOMBIA', 'PAIS', 'TODO EL PAIS']:
            return "1=1"

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
            
            # --- NUEVO: Generar Contexto LIVO (Análisis automático) ---
            contexto_livo = []
            
            # 1. Análisis Comparativo (Año anterior)
            comp = self._realizar_analisis_comparativo(sql, result, columns)
            if comp: contexto_livo.append(comp)
            
            # 2. Anomalías (vs Promedio)
            anom = self._detectar_anomalias(sql, result, columns)
            if anom: contexto_livo.append(anom)
            
            # 3. Contexto Avanzado (Market Share, Segmentos, Coyuntura, Salud, Momentum, Normativa)
            avanzado = self._generar_contexto_avanzado(sql, result, columns, pregunta)
            contexto_livo.extend(avanzado)
            
            if contexto_livo:
                respuesta += "\n\n📝 **Contexto LIVO:**\n" + "\n".join(contexto_livo)
            
            respuesta += f"\n\n🛠️ **Query:** `{sql}`"
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
                  AND LEFT(fecha, 4) = ?
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
    AND LEFT(fecha, 4) = '{anio_str}'
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
   - Uso: WHERE LEFT(fecha, 4) = '2025' para obtener todo el año 2025
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
   - Para filtrar por año: WHERE LEFT(fecha, 4) = '2024'
   - Para filtrar por mes: WHERE SUBSTRING(fecha, 5, 2) = '10'

🔹 ÚLTIMOS N MESES:
   - Proceso: 1) Identificar mes más reciente con MAX(fecha)
   - Proceso: 2) Contar hacia atrás N meses desde esa fecha
   - Ejemplo: Si corte es octubre 2025 (20251031), últimos 4 meses:
     * Octubre 2025 (202510xx)
     * Septiembre 2025 (202509xx) 
     * Agosto 2025 (202508xx)
     * Julio 2025 (202507xx)
   - SQL: WHERE LEFT(fecha, 6) IN ('202510', '202509', '202508', '202507')

🔹 OFERTA (cuenta = 'Oferta') - REGLA CRÍTICA:
   - Las ofertas NO se suman entre meses.
   - "Oferta de septiembre 2025" → usar SOLO registros de septiembre 2025.
   - "Oferta del año 2025" → usar SOLO la oferta del último mes disponible de 2025
     (no sumar enero–diciembre, sino tomar únicamente el último corte).
   - Ejemplo de último período de oferta para 2025 (auto-detectado):
     {ejemplo_oferta_2025}
   - SQL típico para elegir el último período de oferta de un año:
     SELECT MAX(fecha) FROM livo
     WHERE cuenta = 'Oferta' AND LEFT(fecha, 4) = '2025';
     -- Luego filtrar SOLO por ese código de fecha en la consulta principal.

═══ EJEMPLOS DE CONSULTAS TEMPORALES CORRECTAS ═══

❌ INCORRECTO:
   WHERE año_corrido = 2024

✅ CORRECTO:
   WHERE año_corrido = 1                    -- Para año corrido (oct 2024 - oct 2025)
   WHERE LEFT(fecha, 4) = '2025'           -- Para último año (todo 2025)
   WHERE doce_meses = (SELECT MAX(doce_meses) FROM livo) -- Para últimos 12 meses móviles
   WHERE LEFT(fecha, 6) IN ('202510', '202509', '202508', '202507')  -- Últimos 4 meses

═══ DETECCIÓN AUTOMÁTICA DE PERÍODOS ═══
- "año corrido" → Usar año_corrido = 1 (período de 12 meses desde mismo mes año anterior)
- "último año" → Usar LEFT(fecha, 4) = '2025' (año calendario completo actual)
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

⚠️ CAMBIO IMPORTANTE: Ya NO usar campo 'tipo_vivienda'. Ahora clasificar por campo 'valor'

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
   WHERE tipo_vivienda = 'VIS'

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

1. 🚀 **LANZAMIENTO (Preventa):** Salida al mercado sobre planos. Aumenta la oferta.
2. 💰 **VENTA (Cierre de Negocio):** Cierre de promesas de compraventa. Reduce la oferta.
3. 🏗️ **INICIACIÓN (Inicio de Obra):** Comienzo de la construcción física. Es un INDICADOR REZAGADO. Las iniciaciones de hoy reflejan las ventas de hace 6 a 12 meses. No afecta directamente la oferta comercial disponible (se puede vender algo no iniciado).
4. 🏢 **OFERTA (Inventario):** Unidades remanentes que no se han vendido. Es el resultado final del ciclo.
"""

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
    
    def consultar(self, pregunta: str, llm_function, usuario: str = "default", 
                 generate_chart: bool = False, channel: str = "streamlit") -> Tuple[bool, str, Optional[Dict]]:
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
        
        # MEJORA: Intentar respuesta directa de Coyuntura (Prioridad Alta)
        respuesta_coyuntura = self._consultar_coyuntura_directa(pregunta)
        if respuesta_coyuntura:
            return True, respuesta_coyuntura, None

        # MEJORA: Intentar primero con reglas (sin LLM) para consultas comunes
        # Esto ahorra tokens y es más rápido para preguntas estándar
        sql_reglas = self._generar_sql_sin_llm(pregunta)
        if sql_reglas:
            print(f"⚡ Usando SQL generado por reglas (sin LLM): {sql_reglas}")
            try:
                result = self.conn.execute(sql_reglas).fetchall()
                columns = [desc[0] for desc in self.conn.description]
                
                # Formatear resultados
                respuesta = self._formatear_resultados(result, columns, sql_reglas)
                
                # Verificar si se usó filtro geográfico en el SQL generado por reglas
                # Si no hay filtro de departamento/regional, asumimos nacional y agregamos el tip
                if "departamento" not in sql_reglas.lower() and "regional" not in sql_reglas.lower():
                    respuesta += "\n\n💡 *Tip:* También puedo darte este dato por departamento o ciudad (ej: 'en Antioquia' o 'en Bogotá')."
                
                # Agregar badge
                # Determinar si es contexto de vivienda (Coyuntura) o general (LIVO)
                es_coyuntura_vivienda = any(p in pregunta.lower() for p in ["mes anterior", "mes pasado"])
                
                # Si se mencionan usos no residenciales, NO es coyuntura de vivienda
                non_res_keywords = ['oficina', 'local', 'bodega', 'lote', 'consultorio', 'hotel', 'hospital', 'educacion', 'comercio', 'industria']
                if any(k in normalize_text(pregunta) for k in non_res_keywords):
                    es_coyuntura_vivienda = False

                if es_coyuntura_vivienda:
                    respuesta = f"⚡ **Respuesta rápida (Estimación LIVO)**\n\n{respuesta}\n\n🔍 *Fuente: Base de datos LIVO (Simulando reglas de Coyuntura)*"
                else:
                    respuesta = f"⚡ **Respuesta rápida (LIVO)**\n\n{respuesta}\n\n🔍 *Fuente: Base de datos LIVO (Cálculo directo)*"
                respuesta += f"\n\n🛠️ **Query:** `{sql_reglas}`"
                
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
            try:
                result = self.conn.execute(sql_cacheado).fetchall()
                columns = [desc[0] for desc in self.conn.description]
                
                # Formatear resultados
                respuesta = self._formatear_resultados(result, columns, sql_cacheado)
                
                # Agregar badge de caché
                respuesta = f"⚡ **Resultado cacheado (ultra rápido)**\n\n{respuesta}\n\n🔍 *Fuente: Base de datos LIVO (Caché)*"
                respuesta += f"\n\n🛠️ **Query:** `{sql_cacheado}`"
                
                # MEJORA 4: Explicación del SQL
                explicacion = self.explicar_sql(sql_cacheado, llm_function)
                respuesta += f"\n\n💡 **Qué hice:** {explicacion}"
                
                # MEJORA 5: Sugerencias de preguntas relacionadas
                sugerencias = self.generar_preguntas_relacionadas(pregunta, respuesta, llm_function)
                if sugerencias:
                    respuesta += "\n\n💭 **Preguntas relacionadas que podrías hacer:**\n"
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
1. DESAMBIGUACIÓN (REGIONAL vs DEPARTAMENTO):
   - Si el usuario pide "departamento de Antioquia", usa `WHERE departamento = 'Antioquia'`.
   - Si el usuario pide "regional Antioquia", usa `WHERE regional = 'Antioquia'`.
   - Si solo dice "en Antioquia", y la pregunta es sobre datos agregados (oferta, ventas), asume `regional`. Si es sobre detalles (proyectos, constructoras), asume `departamento`.
   - ¡Recuerda que los nombres pueden variar! 'Bogotá & Cundinamarca' es una regional, mientras que 'Bogotá D.C.' y 'Cundinamarca' son departamentos.
   - Si el usuario escribe "y" para unir regiones (ej: "Bogotá y Cundinamarca"), conviértelo a "&" para que coincida con la base de datos (ej: "Bogotá & Cundinamarca").
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
  AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2024

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
    EXTRACT(YEAR FROM fecha_date) as anio,
    EXTRACT(MONTH FROM fecha_date) as mes,
    DATE_TRUNC('month', fecha_date) as periodo,
    COUNT(*) as num_licencias,
    SUM(unidades) as total_unidades
  FROM livo
  WHERE tipo_vivienda = 'VIS'
    AND UPPER(ciudad) LIKE UPPER('%Bogotá%')
    AND fecha_date >= CURRENT_DATE - INTERVAL '12 months'
  GROUP BY anio, mes, periodo
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
  WHERE CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2023 AND tipo_vivienda = 'VIS'
  GROUP BY ciudad
),
unidades_2024 AS (
  SELECT ciudad, SUM(unidades) as unidades_2024
  FROM livo
  WHERE CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2024 AND tipo_vivienda = 'VIS'
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
    EXTRACT(YEAR FROM fecha_date) as anio,
    QUARTER(fecha_date) as trimestre,
    COUNT(*) as num_licencias,
    SUM(unidades) as total_unidades
  FROM livo
  WHERE fecha_date >= CURRENT_DATE - INTERVAL '3 years'
  GROUP BY anio, trimestre
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
    CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) as anio,
    ciudad,
    SUM(unidades) as total_unidades
  FROM livo
  WHERE CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) >= 2020
  GROUP BY anio, ciudad
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
    CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) as anio,
    compania_constructora,
    SUM(unidades) as unidades_constructora
  FROM livo
  WHERE CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) >= 2020
  GROUP BY anio, compania_constructora
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
    CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) as anio,
    SUM(unidades) as total_unidades
  FROM livo
  WHERE tipo_vivienda = 'VIS'
    AND CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) BETWEEN 2021 AND 2024
  GROUP BY anio
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
    SUM(CASE WHEN CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2024 THEN unidades ELSE 0 END) as unidades_2024,
    SUM(CASE WHEN CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2023 THEN unidades ELSE 0 END) as unidades_2023,
    ROUND((SUM(CASE WHEN CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2024 THEN unidades ELSE 0 END) - 
           SUM(CASE WHEN CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2023 THEN unidades ELSE 0 END)) * 100.0 / 
           NULLIF(SUM(CASE WHEN CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) = 2023 THEN unidades ELSE 0 END), 0), 2) as tasa_crecimiento
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
    CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) as anio,
    SUM(unidades) as total_unidades
  FROM livo
  WHERE CAST(LEFT(CAST(fecha AS VARCHAR), 4) AS INTEGER) >= 2022
    AND ciudad IN ('Bogotá', 'Medellín', 'Cali', 'Barranquilla')
  GROUP BY ciudad, tipo_vivienda, estrato, anio
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
    AND doce_meses = (SELECT MAX(doce_meses) FROM livo)
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
        
        # --- MEJORA: Manejar el caso en que todos los LLM fallen ---
        if not respuesta_llm:
            return False, "❌ No se pudo generar la consulta SQL porque todos los proveedores de IA fallaron. Por favor, revisa los límites de tu API.", None
            
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
            
            # Formatear la respuesta principal
            respuesta = self._formatear_resultados(result, columns, sql)
            respuesta += "\n\n🔍 *Fuente: Base de datos LIVO (SQL Generado)*"
            respuesta += f"\n\n🛠️ **Query:** `{sql}`"

            # --- Generación de Contexto Unificado (Consistente con reglas) ---
            contexto_items = []
            
            # 1. Análisis Comparativo
            comp = self._realizar_analisis_comparativo(sql, result, columns)
            if comp: contexto_items.append(comp)

            # 2. Anomalías
            anom = self._detectar_anomalias(sql, result, columns)
            if anom: contexto_items.append(anom)
            
            # 3. Contexto Avanzado (Market Share, Segmentos, Coyuntura, Salud, Momentum, Normativa)
            avanzado = self._generar_contexto_avanzado(sql, result, columns, pregunta)
            if avanzado: contexto_items.extend(avanzado)

            if contexto_items:
                respuesta += "\n\n📝 **Contexto LIVO:**\n" + "\n".join(contexto_items)

            # MEJORA: Visualización Automática y Contextual
            chart_data = None
            if generate_chart:
                chart_data = self._generar_grafico(result, columns, pregunta, channel)

            return True, respuesta, chart_data
            
        except Exception as e:
            return False, f"❌ Error SQL: {str(e)}", None

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
        
        # Solo procesar si tenemos un resultado numérico único
        es_dato_unico = len(result) == 1 and len(columns) == 1 and isinstance(result[0][0], (int, float))
        valor_actual = result[0][0] if es_dato_unico else 0
        
        # 1. Integración Narrativa de Coyuntura
        if COYUNTURA_AVAILABLE:
            narrativa = self._obtener_narrativa_coyuntura(pregunta)
            if narrativa: contexto.append(f"📊 **Coyuntura:** {narrativa}")

        # 2. Contexto Normativo Proactivo
        normativo = self._obtener_contexto_normativo(pregunta)
        if normativo: contexto.append(f"⚖️ **Normativa:** {normativo}")

        if es_dato_unico and valor_actual > 0:
            # 3. Market Share (Participación)
            share = self._calcular_market_share(sql, valor_actual)
            if share: contexto.append(share)

            # 4. Desglose por Segmento (VIS vs No VIS)
            # Solo si no está filtrado ya por tipo específico en el SQL
            if "tipo_vivienda =" not in sql and "tipo_vivienda IN" not in sql:
                desglose = self._calcular_desglose_segmento(sql, valor_actual)
                if desglose: contexto.append(desglose)
            
            # 5. Indicadores Cruzados (Salud del Mercado)
            salud = self._calcular_indicadores_salud(sql, valor_actual)
            if salud: contexto.append(salud)
            
            # 6. Tendencia de Corto Plazo (Momentum)
            momentum = self._calcular_momentum(sql, valor_actual)
            if momentum: contexto.append(momentum)
            
            # 7. Proyecciones a Corto Plazo (Forecasting)
            forecast = self._calcular_proyeccion_corto_plazo(sql, valor_actual)
            if forecast: contexto.append(forecast)

            # 8. Benchmarking Automático (Comparación entre Pares)
            benchmark = self._calcular_benchmarking(sql, valor_actual)
            if benchmark: contexto.append(benchmark)

            # 9. Análisis de Absorción de Lanzamientos
            absorcion = self._calcular_absorcion_lanzamientos(sql, valor_actual)
            if absorcion: contexto.append(absorcion)

            # 10. Índice de Concentración de Mercado (HHI)
            concentracion = self._calcular_concentracion_mercado(sql)
            if concentracion: contexto.append(concentracion)

            # 11. Contexto de Valorización (Precios)
            valorizacion = self._calcular_valorizacion_precios(sql)
            if valorizacion: contexto.append(valorizacion)

            # 12. Alertas de Agotamiento (Stockout)
            agotamiento = self._calcular_alerta_agotamiento(sql, valor_actual)
            if agotamiento: contexto.append(agotamiento)

            # 13. Distribución Fina por Rangos de SMMLV
            dist_smmlv = self._calcular_distribucion_fina_smmlv(sql, valor_actual)
            if dist_smmlv: contexto.append(dist_smmlv)

            # 14. Contexto de Estacionalidad
            estacionalidad = self._calcular_estacionalidad(sql)
            if estacionalidad: contexto.append(estacionalidad)
            
            # 15. Razonamiento Multi-Fuente (Correlación Macro)
            macro = self._analisis_macro_sectorial(sql)
            if macro: contexto.append(macro)

            # 16. Auditoría de Calidad de Datos
            calidad = self._auditar_calidad_datos(sql, result, columns)
            if calidad: contexto.append(calidad)

            # 17. Simulación de Escenarios (What-If)
            simulacion = self._simular_escenario_automatico(sql, valor_actual)
            if simulacion: contexto.append(simulacion)

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
                    return f"🌍 **Market Share:** Representa el **{share:.1f}%** del total nacional ({total_nacional:,.0f})."
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
            CASE WHEN tipo_vivienda IN ('VIS', 'VIP') THEN 'VIS/VIP' ELSE 'No VIS' END as segmento,
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
                    return f"🚀 **Momentum:** Variación de **{var:+.1f}%** frente al mes inmediatamente anterior."
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
                return f"🔮 **Proyección:** Basado en el promedio de los últimos 3 meses ({promedio_3m:,.0f}), se proyecta que el próximo mes podría rondar esa cifra."
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
                    return f"🤼 **Benchmarking:** {ciudad_detectada.title()} está un **{abs(diff_pct):.1f}% {estado}** de su par {par_detectado.title()} ({valor_par:,.0f})."
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
                    return f"🧽 **Absorción:** Las ventas representan el **{absorcion:.1f}%** de los lanzamientos del periodo."
            
            elif "cuenta = 'Lanzamientos'" in sql:
                # Obtener Ventas
                sql_ven = sql.replace("cuenta = 'Lanzamientos'", "cuenta = 'Ventas'")
                res = self.conn.execute(sql_ven).fetchone()
                if res and res[0]:
                    ventas = res[0]
                    absorcion = (ventas / valor_actual) * 100
                    return f"🧽 **Absorción:** Se ha vendido el **{absorcion:.1f}%** de lo lanzado en este periodo."
        except:
            pass
        return None

    def _calcular_concentracion_mercado(self, sql: str) -> Optional[str]:
        """Calcula el Índice Herfindahl-Hirschman (HHI) de concentración."""
        # Solo si no es una consulta de una constructora específica
        if "compania_constructora" in sql:
            return None
            
        try:
            # Extraer WHERE clause
            match_from = re.search(r"FROM\s+livo\s+WHERE\s+(.*?)(\s+GROUP\s+BY|\s+ORDER\s+BY|$)", sql, re.IGNORECASE | re.DOTALL)
            if not match_from: return None
            where_clause = match_from.group(1)
            
            # Calcular HHI
            sql_hhi = f"""
            WITH shares AS (
                SELECT SUM(unidades) * 100.0 / SUM(SUM(unidades)) OVER () as share
                FROM livo
                WHERE {where_clause}
                GROUP BY compania_constructora
            )
            SELECT SUM(share * share) as hhi FROM shares
            """
            res = self.conn.execute(sql_hhi).fetchone()
            if res and res[0]:
                hhi = res[0]
                nivel = "Baja" if hhi < 1500 else "Moderada" if hhi < 2500 else "Alta"
                return f"🏗️ **Concentración de Mercado:** {nivel} (HHI: {hhi:.0f}). Un HHI mayor a 2500 indica alta concentración."
        except:
            pass
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
                    return f"🚨 **Alerta de Agotamiento:** Inventario crítico. Al ritmo actual, la oferta se agotaría en solo {meses} meses (Stockout)."
        return None

    def _calcular_distribucion_fina_smmlv(self, sql: str, valor_actual: float) -> Optional[str]:
        """Desglosa No VIS en rangos finos (Medio, Alto, Lujo)."""
        if "tipo_vivienda = 'No VIS'" not in sql and "No VIS" not in sql:
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
                return f"📏 **Rangos No VIS:** Medio (135-300 SMMLV): {medio or 0:.0f}% | Alto (300-500 SMMLV): {alto or 0:.0f}% | Lujo (>500 SMMLV): {lujo or 0:.0f}%."
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
                return f"📅 **Estacionalidad:** Históricamente, el mes {mes_consultado} es de **alta actividad** para {cuenta} (superior al promedio anual)."
            elif promedio_mes < promedio_general * 0.9:
                return f"📅 **Estacionalidad:** Históricamente, el mes {mes_consultado} es de **baja actividad** para {cuenta}."
        except:
            pass
        return None

    def _analisis_macro_sectorial(self, sql: str) -> Optional[str]:
        """Sugiere correlaciones con variables macroeconómicas (Razonamiento Multi-Fuente)."""
        if "cuenta = 'Ventas'" in sql:
            return "📉 **Correlación Macro:** Las ventas de vivienda presentan históricamente una correlación inversa con las tasas de interés hipotecarias y el desempleo. Se sugiere cruzar este dato con el reporte de 'Tasas de Interés' y 'Mercado Laboral'."
        if "cuenta = 'Iniciaciones'" in sql:
            return "🏗️ **Correlación Macro:** Las iniciaciones suelen seguir el comportamiento del PIB de Edificaciones con un rezago de 1-2 trimestres."
        if "precio" in sql.lower() or "valor" in sql.lower():
            return "💲 **Correlación Macro:** Los precios de vivienda están influenciados por el ICCV (Índice de Costos de Construcción) y la inflación (IPC)."
        return None

    def _auditar_calidad_datos(self, sql: str, result: list, columns: list) -> Optional[str]:
        """Auditoría automática de calidad de datos en la respuesta."""
        # Verificar si hay valores negativos donde no debería (unidades, valor, area)
        for row in result:
            for val in row:
                if isinstance(val, (int, float)) and val < 0:
                    return "🛡️ **Auditoría de Datos:** ⚠️ Se detectaron valores negativos en el resultado, lo cual puede indicar ajustes contables o reversiones masivas en la fuente."
        return None

    def _simular_escenario_automatico(self, sql: str, valor_actual: float) -> Optional[str]:
        """Genera una simulación What-If automática (Capacidades Predictivas)."""
        if "cuenta = 'Ventas'" in sql:
            escenario_bajo = valor_actual * 0.9
            escenario_alto = valor_actual * 1.1
            return f"🔮 **Simulación What-If:** Si la demanda varía un +/- 10%, las ventas se ubicarían entre {escenario_bajo:,.0f} y {escenario_alto:,.0f} unidades."
        
        if "cuenta = 'Oferta'" in sql:
            # Simular absorción simple
            meses_simulados = 12
            ventas_estimadas = valor_actual * 0.05 * meses_simulados # Asumiendo 5% ventas mensuales
            saldo_final = valor_actual - ventas_estimadas
            return f"🔮 **Simulación What-If:** Con una velocidad de ventas promedio del 5% mensual, el stock se reduciría a {saldo_final:,.0f} unidades en 12 meses (ceteris paribus)."
            
        return None

    def generar_reporte_ejecutivo(self, pregunta: str, respuesta: str, contexto: str, sql: str) -> str:
        """Genera un reporte ejecutivo en formato Markdown (Generación de Entregables)."""
        fecha_reporte = datetime.now().strftime("%Y-%m-%d")
        reporte = f"# 📑 REPORTE EJECUTIVO CAMACOL\n**Fecha:** {fecha_reporte}\n**Consulta:** {pregunta}\n\n## 1. Resumen Ejecutivo\n{respuesta}\n\n## 2. Análisis de Contexto y Mercado\n{contexto.replace('📝 **Contexto LIVO:**', '').strip()}\n\n## 3. Detalles Técnicos\n**Fuente de Datos:** Base de Datos LIVO (Coordenada Urbana)\n**Consulta Ejecutada:**\n```sql\n{sql}\n```\n\n---\n*Generado automáticamente por el Agente Inteligente CAMACOL*"
        return reporte

    def _detectar_anomalias(self, sql: str, resultado_actual: list, columnas: list) -> Optional[str]:
        """Compara el resultado con el promedio histórico para detectar anomalías."""
        # Solo funciona para resultados de una sola cifra numérica
        if not (len(resultado_actual) == 1 and len(columnas) == 1 and isinstance(resultado_actual[0][0], (int, float))):
            return None

        try:
            valor_actual = resultado_actual[0][0]
            
            # Extraer la métrica principal del SQL (ej: SUM(unidades), AVG(area))
            match_metrica = re.search(r"(SUM|AVG|COUNT)\s*\((.*?)\)", sql, re.IGNORECASE)
            if not match_metrica:
                return None
            
            metrica_sql = match_metrica.group(0)
            
            # Construir consulta para el promedio de los últimos 12 meses
            # (simplificado, asume que no hay otros filtros complejos)
            sql_promedio = f"SELECT AVG(valor_mensual) FROM (SELECT {metrica_sql} as valor_mensual FROM livo WHERE doce_meses = (SELECT MAX(doce_meses) FROM livo) GROUP BY LEFT(CAST(fecha AS VARCHAR), 6))"
            
            promedio_historico = self.conn.execute(sql_promedio).fetchone()[0]

            if promedio_historico and promedio_historico > 0:
                desviacion_pct = ((valor_actual - promedio_historico) / promedio_historico) * 100
                
                # Alertar si la desviación es mayor al 25%
                if abs(desviacion_pct) > 25:
                    tipo_anomalia = "significativamente más alto" if desviacion_pct > 0 else "significativamente más bajo"
                    return (f"⚠️ **Alerta de Anomalía:** Este valor es un **{abs(desviacion_pct):.1f}% {tipo_anomalia}** "
                            f"que el promedio de los últimos 12 meses (que fue de {promedio_historico:,.0f}).")
        except Exception as e:
            print(f"⚠️ Error en detección de anomalías: {e}")
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

        # Seleccionar proveedores locales de respaldo (Llama, Qwen vía Ollama)
        ollama_backups = [
            p for p in AI_PROVIDERS
            if p.get("type") == AIModel.OLLAMA and p.get("enabled", True)
        ]

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
                    print(f"🔁 Intentando fallback con proveedor local: {backup_name}")
                    resp_backup, err_backup = llamar_api_ia(prompt_text, backup)
                    if resp_backup and not err_backup:
                        print(f"✅ Fallback exitoso con {backup_name}")
                        return resp_backup
                    else:
                        print(f"⚠️ Fallback con {backup_name} falló: {err_backup}")

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
        "RAG/2025/Coordenada Urbana/LIVO_total_nov25_.xlsx",
        "RAG/2025/LIVO/LIVO_2025_Consolidado.xlsx",
        "RAG/2025/LIVO/LIVO_2025.xlsx",
        "LIVO_2025_Consolidado.xlsx",
        "LIVO_2025.xlsx"
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
        "tipo_vivienda": "Clasificación por valor: No VIS, VIS, VIP, SIN ASIGNAR, (vacío)",
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
• tipo_vivienda: 'VIS', 'VIP', 'No VIS', 'SIN ASIGNAR'  
• estado: 'Construcción', 'Preventa', 'TVE', 'Terminado'
• cuenta: 'Oferta', 'Ventas', 'Iniciaciones', 'Entregadas'
• uso_etapa: 'Apartamento', 'Casa'
• unidades: número de unidades
• area: área en m²
• valor: valor en miles de pesos

EJEMPLOS:
- "top 10 constructoras" → SELECT compania_constructora, SUM(unidades) FROM livo GROUP BY compania_constructora ORDER BY SUM(unidades) DESC LIMIT 10
- "unidades en bogota" → SELECT SUM(unidades) FROM livo WHERE departamento = 'Bogotá D.C.'
- "apartamentos VIS" → SELECT COUNT(*) FROM livo WHERE uso_etapa = 'Apartamento' AND tipo_vivienda = 'VIS'

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
                    
                    print("⚠️ No hay proveedores LLM disponibles")
                    return None, "No hay proveedores LLM disponibles"
                except Exception as e:
                    print(f"⚠️ Error con LLM: {e}")
                    import traceback
                    traceback.print_exc()
                    return None, f"Error con LLM: {e}"
            
            print("[DEBUG] Llamando system.consultar...")
            resultado = system.consultar(pregunta, llm_function=llm_function)
            print(f"[DEBUG] Resultado de consultar: {type(resultado)}, {resultado}")
            
            if isinstance(resultado, tuple) and len(resultado) == 3:
                exito, respuesta, sql_usado = resultado
                if exito:
                    print("✅ Respuesta:", respuesta)
                    if sql_usado:
                        print("📝 SQL usado:", sql_usado)
                else:
                    print("❌ Error:", respuesta)
            else:
                print(f"❌ Resultado inesperado del sistema LIVO: {resultado}")
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
    
    # system.cerrar()  # Método no existe
    print("👋 ¡Hasta luego!")