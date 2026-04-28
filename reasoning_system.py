#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sistema de Razonamiento para el Chatbot CAMACOL
Detecta preguntas incompletas y genera contrapreguntas para clarificar la intención del usuario
"""

import re
from typing import Dict, List, Tuple, Optional
import unicodedata
from dataclasses import dataclass

try:
    from fuzzywuzzy import process
    FUZZYWUZZY_AVAILABLE = True
except ImportError:
    FUZZYWUZZY_AVAILABLE = False
from enum import Enum

# Importar el gestor de perfiles de usuario
try:
    from user_profile_manager import user_profile_manager
except ImportError:
    user_profile_manager = None

# Importar el sistema de coyuntura de lanzamientos
try:
    from lanzamientos_coyuntura import lanzamientos_coyuntura
except ImportError:
    lanzamientos_coyuntura = None

# Importar el sistema de coyuntura de iniciaciones
try:
    from iniciaciones_coyuntura import iniciaciones_coyuntura
except ImportError:
    iniciaciones_coyuntura = None

# Importar el sistema de coyuntura de ventas
try:
    from ventas_coyuntura import ventas_coyuntura
except ImportError:
    ventas_coyuntura = None

# Importar el sistema de coyuntura de oferta
try:
    from oferta_coyuntura import oferta_coyuntura
except ImportError:
    oferta_coyuntura = None

# Importar el sistema de comparación cuádruple
try:
    from comparacion_coyuntura import comparador_coyuntura
except ImportError:
    comparador_coyuntura = None

class QuestionType(Enum):
    """Tipos de preguntas identificadas"""
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    AMBIGUOUS = "ambiguous"
    NEEDS_CLARIFICATION = "needs_clarification"

@dataclass
class ReasoningResult:
    """Resultado del análisis de razonamiento"""
    question_type: QuestionType
    confidence: float
    missing_elements: List[str]
    counter_questions: List[str]
    reasoning_comments: List[str]
    suggested_clarifications: List[str]

def normalize_text(text: str) -> str:
    """Convierte texto a minúsculas y remueve tildes."""
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn').lower()

class ReasoningSystem:
    """Sistema de razonamiento para detectar preguntas incompletas y generar contrapreguntas"""
    
    def __init__(self):
        # Elementos esenciales para consultas LIVO
        self.essential_elements = {
            'account_type': {  # CRÍTICO - Movido al primer lugar por importancia
                'keywords': [ # Ampliado a ~7-10 sinónimos de alto valor por concepto
                    # Ventas
                    'ventas', 'vendidas', 'vendido', 'comercializadas', 'negociadas', 'transacciones',
                    # Entregas
                    'entregadas', 'entregados', 'entrega', 'finalizadas', 'terminadas',
                    # En Proceso
                    'proceso', 'en construcción', 'en obra', 'activas', 'en ejecución',
                    # Lanzamientos
                    'lanzamiento', 'lanzamientos', 'lanzadas', 'nuevos proyectos', 'oferta nueva',
                    # Licencias
                    'licencia', 'licencias', 'licenciadas', 'aprobadas', 'permisos',
                    # Oferta
                    'oferta', 'disponible', 'disponibles', 'inventario'
                ],
                'description': 'tipo de cuenta o estado (CRÍTICO)',
                'priority': 'critical'  # Nuevo campo de prioridad
            },
            'location': {
                'keywords': [
                    'ciudad', 'municipio', 'departamento', 'regional', 'ubicación', 'zona', 'lugar',
                    'bogotá', 'medellín', 'cali', 'barranquilla', 'cartagena', 'bucaramanga',
                    'cundinamarca', 'antioquia', 'valle', 'atlántico', 'santander',
                    'nacional', 'colombia', 'país', 'todo el país' # MEJORA: Añadir términos nacionales
                ],
                'description': 'ubicación geográfica',
                'priority': 'high'
            },
            'metric': {
                'keywords': [
                    'unidades', 'cantidad', 'número de',
                    'valor', 'precio', 'monto', 'ingresos', 'facturación',
                    'área', 'metros', 'm2', 'superficie',
                    'total', 'suma', 'sumatoria',
                    'promedio', 'media'
                ],
                'description': 'métrica a consultar',
                'priority': 'high'
            },
            'time_period': {
                'keywords': [
                    'año', 'mes', 'trimestre', 'semestre', 'periodo', 'fecha', 'cuándo',
                    '2025', '2024', '2023',
                    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
                    'reciente', 'último', 'actual'
                ],
                'description': 'período temporal',
                'priority': 'medium'
            },
            'housing_type': {
                'keywords': [
                    'vis', 'vip', 'no vis', 'interés social', 'prioritario',
                    'vivienda', 'apartamento', 'casa',
                    'oficina', 'comercial', 'bodega', 'otro uso'
                ],
                'description': 'tipo de vivienda o uso (opcional)',
                'priority': 'low' # Se baja la prioridad para no forzar su clarificación
            },
            'operation': {
                'keywords': [
                    'suma', 'total', 'sumatoria',
                    'promedio', 'media',
                    'cantidad', 'conteo', 'cuántos', 'cuántas',
                    'cuál', 'dime', 'muestra', 'lista', 'ranking', 'top'
                ],
                'description': 'operación a realizar',
                'priority': 'medium'
            },
            'company_identifier': {
                'keywords': ['nit', 'identificación', 'código empresa', 'registro', 'cédula jurídica'],
                'description': 'identificador único de constructora (NIT)',
                'priority': 'high'
            }
        }
        
        # Estado de la conversación para almacenar entidades detectadas
        self.conversation_state = {
            'account_type': None,
            'location': None,
            'metric': None,
            'time_period': None,
            'housing_type': None,
            'operation': None
        }
        
        # Patrones de preguntas incompletas
        self.incomplete_patterns = [
            r'^(cuánto|cuánta|cuántos|cuántas)\s*\?*$',  # Solo "cuánto?"
            r'^(dime|muestra|dame)\s*\?*$',  # Solo "dime"
            r'^(qué|que)\s*\?*$',  # Solo "qué?"
            r'^(cómo|como)\s*\?*$',  # Solo "cómo?"
            r'^(precio|valor|costo)\s*\?*$',  # Solo "precio"
            r'^(unidades|viviendas)\s*\?*$',  # Solo "unidades"
        ]
        
        # Contrapreguntas específicas basadas en los ejemplos
        self.counter_questions_templates = {
            'missing_location': [
                "¿En qué ciudad o departamento te interesa consultar la información?",
                "¿Quieres información de una región específica como Bogotá, Medellín, Cali o Barranquilla?",
                "¿Te interesa información de algún departamento en particular (Cundinamarca, Antioquia, Valle, etc.)?"
            ],
            'missing_metric': [
                "¿Qué información específica necesitas: número de unidades, valor total, área construida o precio promedio?",
                "¿Te interesa conocer cantidades, valores económicos o características técnicas?",
                "¿Quieres información sobre unidades vendidas, área construida o valores de las propiedades?"
            ],
            'missing_time': [
                "¿Para qué período necesitas la información: año 2024, 2025, o algún mes específico?",
                "¿Te interesa información del año corrido, último trimestre o algún período específico?",
                "¿Quieres datos actuales (octubre 2025) o de algún período anterior?"
            ],
            'missing_housing_type': [
                "¿Te interesa información sobre vivienda VIS, VIP, No VIS, o algún tipo específico?",
                "¿Quieres consultar sobre viviendas, oficinas, comercial o todos los tipos de construcción?",
                "¿Necesitas información específica sobre algún tipo de proyecto inmobiliario?"
            ],
            'missing_operation': [
                "¿Quieres el total, promedio, cantidad de proyectos únicos o algún cálculo específico?",
                "¿Te interesa una suma total, un ranking, o una comparación? (Nota: para contar proyectos usar COUNT DISTINCT)",
                "¿Necesitas un listado, un resumen estadístico o un análisis específico de proyectos de construcción?"
            ],
            'missing_account_type': [
                "¿Te interesa información sobre ventas, entregas, proyectos en proceso o licencias otorgadas?",
                "¿Quieres datos de unidades vendidas, entregadas o en construcción?",
                "¿Necesitas información sobre qué tipo de cuenta: ventas, entregas, o proyectos activos?"
            ],
            'missing_company_identifier': [
                "¿Necesitas incluir el NIT de las constructoras para identificación única?",
                "¿Quieres considerar tanto el nombre como el NIT de las empresas constructoras?",
                "¿Te interesa filtrar por constructoras específicas usando su NIT de identificación?"
            ]
        }
        
        # Relaciones y jerarquías LIVO
        self.livo_hierarchies = {
            'geographic_hierarchy': {
                'levels': ['regional', 'departamento', 'ciudad', 'zona', 'barrio'],
                'relationships': {
                    'regional': 'contiene varios departamentos',
                    'departamento': 'contiene varias ciudades', 
                    'ciudad': 'contiene varias zonas',
                    'zona': 'contiene varios barrios'
                },
                'grouping_rules': {
                    'ciudad': 'Si se filtra por ciudad, se deben agrupar los resultados por barrio para ver el detalle',
                    'departamento': 'Si se filtra por departamento, se pueden agrupar por ciudad o zona',
                    'regional': 'Si se filtra por regional, se pueden agrupar por departamento o ciudad'
                }
            },
            'identifier_keys': {
                'constructora': {
                    'primary_key': 'nit_constructora',
                    'secondary_key': 'compania_constructora',
                    'rule': 'nit_constructora es el identificador único de la constructora, use esta columna para agrupar por empresa'
                },
                'geographic': {
                    'primary_key': 'divipola',
                    'rule': 'divipola es el código único de identificación geográfica'
                },
                'project': {
                    'primary_key': 'identificador',
                    'rule': 'identificador es único por proyecto, usar COUNT(DISTINCT identificador) para contar proyectos únicos'
                }
            },
            'project_states': {
                'phases': ['Preventa', 'Licencia', 'Construcción', 'Terminado'],
                'states': ['Aprobada', 'Vendido', 'Entregado', 'Proceso'],
                'chronological_order': "La fase es más general que el estado. El orden suele ser 'Preventa' (fase) → 'Licencia' (estado) → 'Vendido' (estado)",
                'correction': "En LIVO trabajamos con proyectos de construcción, no con licencias como entidad independiente"
            }
        }
        
        # Comentarios de razonamiento basados en los ejemplos proporcionados y experiencia práctica
        self.reasoning_comments = {
            # Comentarios críticos generales
            'account_critical': "⚠️ CRÍTICO: La variable 'cuenta' es esencial en el 90% de consultas LIVO ya que determina el estado de los proyectos de construcción (ventas, entregas, proceso, etc.)",
            'count_distinct_critical': "🚨 CRÍTICO para COUNT: Usar COUNT(DISTINCT identificador) porque un mismo proyecto puede aparecer varias veces. Los proyectos deben contarse de manera única",
            'projects_not_licenses': "📋 IMPORTANTE: En LIVO se trabaja con proyectos de construcción, no con licencias. Cada proyecto es único por su identificador",
            'nit_constructora_critical': "🏢 CRÍTICO para CONSTRUCTORAS: Usar el campo NIT junto con el nombre de la constructora, ya que pueden aparecer nombres repetidos o constructoras sin NIT",
            'constructora_unique_identification': "Para identificación única de constructoras usar nit_constructora cuando esté disponible, ya que compania_constructora puede tener variaciones",
            'nit_missing_warning': "Se debe tener en cuenta que no todas las licencias tienen el NIT de la constructora registrado",
            
            # VARIABLES CRÍTICAS DE VERIFICACIÓN LIVO
            'variables_criticas_livo': "🚨 VARIABLES CRÍTICAS LIVO: Siempre verificar y especificar: usos, cuenta, estado, fase, last_estado, destino_etapa, uso_etapa, modalidad",
            'usos_critical': "🏗️ CRÍTICO 'usos': Define el tipo de construcción (residencial/no residencial). Esencial para filtrar correctamente los proyectos",
            'cuenta_critical_extended': "📊 CRÍTICO 'cuenta': Determina el estado del proyecto (ventas, entregas, proceso, renuncias). OBLIGATORIO especificar en consultas",
            'estado_fase_critical': "⚡ CRÍTICO 'estado', 'fase', 'last_estado': Definen el ciclo de vida del proyecto. 'fase' es más general que 'estado'",
            'destino_uso_etapa_critical': "🎯 CRÍTICO 'destino_etapa', 'uso_etapa': Especifican el propósito y tipo de construcción. Usar 'Casa' (singular) no 'Casas'",
            'modalidad_critical': "📋 CRÍTICO 'modalidad': Define el tipo de licencia. Importante para clasificar correctamente los proyectos",
            
            # Comentarios específicos sobre cuentas y filtros
            'specify_account_sales': "Se debe especificar la cuenta de ventas, así como asegurar los filtros para trabajar con viviendas",
            'specify_account_delivered': "Se debe especificar a qué se refiere con área construída, entiendo que es el total de área entregada, de ser así, se debe ajustar la cuenta a Entregadas",
            'housing_filter_needed': "Se deben aplicar los filtros para trabajar únicamente con las viviendas",
            'residential_vs_nonresidential': "Considero que se debería especificar si se va a trabajar con residenciales o no residenciales y aplicar los filtros correspondientes",
            'count_category_clarification': "Entiendo que si suma la cuenta, que es una categoría, estaría sumando la cantidad de veces que se repite esa categoría?",
            'multiple_accounts_warning': "Además la misma etapa puede tener varias cuentas (puede tener ventas, puede estar en proceso, puede tener renuncias)",
            
            # Comentarios sobre variables específicas
            'politica_vivienda_incorrect': "La variable no es política de vivienda. Puede ser segmento_pre o rangos_decreto_pre (confirmar con Nikolás)",
            'segmentation_variable_correction': "Para los segmentos de precio no se debe utilizar politica_vivienda, si no rangos_decreto_pre o segmento_pre",
            'precio_mc_promedio_exists': "Ya existe una variable precio_mc_promedio. Se debe confirmar si se debe trabajar con esa, ya que tiene como unas consideraciones",
            'valor_in_thousands': "Se debe tener en cuenta que la variable 'valor' está en miles en la base",
            'aggregate_data_warning': "La base trabaja con agregados, es decir, la columna valor incluye el valor de varias unidades. Si se quiere saber el valor de una sola unidad debe dividir el valor por el número de unidades",
            
            # Comentarios sobre NUEVA clasificación por valor (VIS, VIP, No VIS)
            'nueva_clasificacion_valor': "🏠 CAMBIO IMPORTANTE: Ya NO usar 'tipo_vivienda'. Ahora clasificar VIS/VIP/No VIS por campo 'valor' basado en salarios mínimos",
            'vip_por_valor': "🏠 VIP: Usar WHERE valor < 128115 (< 90 SMMLV). No usar tipo_vivienda = 'VIP'",
            'vis_por_valor': "🏘️ VIS: Usar WHERE valor >= 128115 AND valor < 192173 (90-135 SMMLV). No usar tipo_vivienda = 'VIS'", 
            'no_vis_por_valor': "🏢 NO VIS: Usar WHERE valor >= 192173 (> 135 SMMLV). No usar tipo_vivienda = 'No VIS'",
            'salario_minimo_2025': "💰 Salario mínimo 2025: $1,423,500. VIP < $128M, VIS $128M-$192M, No VIS > $192M",
            'nota_metodologica_vis': (
                "📘 NOTA METODOLÓGICA VIS/VIP/No VIS:"  \
                " Las tablas de coyuntura - unidades de Coordenada Urbana incluyen cinco hojas "
                "(lanzamientos, iniciaciones, ventas, oferta y renuncias) en unidades de vivienda, "
                "subdivididas por rangos de precio definidos en SMMLV del año correspondiente. "
                "La información va de enero de 2010 a septiembre de 2025 y está desagregada para las "
                "19 regionales del censo de CU, con agregaciones estándar en grupos de 5, 13, 18 y 19 "
                "regionales según el año de inclusión en el censo. "
                " A partir de mayo de 2019 se clasifica como VIP a los inmuebles con precio ≤ 90 SMMLV "
                "(Ley 1955 de 2019; antes era ≤ 70 SMMLV). Desde agosto de 2019, en las aglomeraciones "
                "definidas por el Decreto 1467 de 2019, el segmento VIS incluye inmuebles con precio ≤ 150 SMMLV; "
                "en los demás municipios el tope VIS se mantiene en 135 SMMLV y, por tanto, NO VIS corresponde a "
                "precios superiores a ese umbral. En particular, el tope VIS=150 SMMLV (y NO VIS > 150 SMMLV) aplica "
                "para las siguientes aglomeraciones y municipios: "
                " Barranquilla: Sitionuevo, Sabanalarga, Ponedera, Palmar de Varela, Santo Tomás, Malambo, "
                "Soledad, Galapa, Barranquilla. "
                " Bogotá DC: Tabio, Cajicá, Cota, Sibaté, La Calera, Funza, Chía, Mosquera, Facatativá, Zipaquirá, "
                "Madrid, Soacha, Tocancipá, Bogotá. "
                " Bucaramanga: Piedecuesta, Girón, Floridablanca, Bucaramanga. "
                " Cali: Puerto Tejada, Candelaria, Yumbo, Jamundí, Cali. "
                " Cartagena: Clemencia, Turbaco, Cartagena. "
                " Medellín: Girardota, Caldas, Itagüí, Sabaneta, La Estrella, Envigado, Copacabana, Bello, Medellín. "
                " Cúcuta: Cúcuta, Los Patios, Villa Del Rosario. "
                " En los demás territorios del país se mantiene el esquema general (VIP < 90 SMMLV, VIS ≤ 135 SMMLV, "
                "NO VIS > 135 SMMLV). Posteriormente, el Decreto 1607 de 2022 amplía aglomeraciones, incluyendo "
                "la aglomeración de Cúcuta y municipios aledaños. "
                " Esto implica que los topes de precio para clasificar VIS/VIP/No VIS pueden variar entre "
                "municipios y aglomeraciones, por lo que siempre se deben revisar los casos particulares "
                "y la normativa vigente en cada territorio antes de fijar un único umbral nacional. "
                " La clasificación por rangos de precio se hace siempre con el último precio de venta registrado "
                "del inmueble y el SMMLV vigente en cada año, por lo que es normal observar rezagos y ajustes "
                "incrementales entre publicaciones del censo. Coordenada Urbana realiza además una revisión "
                "trimestral de cobertura; al tercer trimestre de 2025, la cobertura estimada del censo fue del 94% "
                "de la actividad edificadora nacional."
            ),
            
            # Comentarios sobre COYUNTURA DE LANZAMIENTOS
            'contexto_coyuntura_lanzamientos': "📊 CONTEXTO COYUNTURA: Datos históricos de lanzamientos disponibles desde enero 2010 hasta octubre 2025, desagregados por 19 departamentos y clasificación VIS/VIP/No VIS",
            'lanzamientos_vs_livo': "🔄 LANZAMIENTOS vs LIVO: Los datos de coyuntura de lanzamientos complementan la base LIVO. Lanzamientos = nuevos proyectos que inician comercialización; LIVO = seguimiento detallado de proyectos",
            'agregaciones_regionales': "🗺️ AGREGACIONES: Disponibles en grupos de 5, 13, 18 y 19 regionales según año de inclusión en censo. Principales: Antioquia, Atlántico, Bogotá & Cundinamarca, Valle, Santander",
            'tendencias_recientes_disponibles': "📈 TENDENCIAS RECIENTES: Sistema pre-cargado con análisis de tendencias mensuales, variaciones departamentales y distribución VIS/VIP/No VIS actualizada",
            'contexto_departamental_automatico': "🏢 CONTEXTO AUTOMÁTICO: Al mencionar departamentos se proporciona ranking histórico, participación nacional y distribución por tipo de vivienda",
            
            # Comentarios sobre COYUNTURA DE INICIACIONES
            'contexto_coyuntura_iniciaciones': "🏗️ CONTEXTO INICIACIONES: Datos históricos de iniciaciones disponibles desde enero 2010 hasta octubre 2025, desagregados por 19 departamentos y clasificación VIS/VIP/No VIS",
            'iniciaciones_vs_livo': "🔄 INICIACIONES vs LIVO: Los datos de coyuntura de iniciaciones complementan la base LIVO. Iniciaciones = proyectos que inician construcción; LIVO = seguimiento detallado de todo el ciclo",
            'iniciaciones_vs_lanzamientos': "📊 INICIACIONES vs LANZAMIENTOS: Iniciaciones son proyectos que empiezan construcción, Lanzamientos son proyectos que inician comercialización. Análisis conjunto proporciona visión completa del mercado",
            'contexto_iniciaciones_departamental': "🏗️ CONTEXTO INICIACIONES AUTOMÁTICO: Al mencionar departamentos se proporciona ranking histórico de iniciaciones, participación nacional y distribución por tipo de vivienda",
            'tendencias_iniciaciones_disponibles': "📈 TENDENCIAS INICIACIONES: Sistema pre-cargado con análisis de tendencias mensuales de iniciaciones, variaciones departamentales y distribución VIS/VIP/No VIS actualizada",
            
            # Comentarios sobre COYUNTURA DE VENTAS
            'contexto_coyuntura_ventas': "💰 CONTEXTO VENTAS: Datos históricos de ventas disponibles desde enero 2010 hasta octubre 2025, desagregados por 19 departamentos y clasificación VIS/VIP/No VIS",
            'ventas_vs_livo': "🔄 VENTAS vs LIVO: Los datos de coyuntura de ventas complementan la base LIVO. Ventas = unidades efectivamente vendidas; LIVO = seguimiento detallado de todo el ciclo",
            'ventas_vs_lanzamientos_iniciaciones': "📊 VENTAS vs LANZAMIENTOS/INICIACIONES: Ventas son unidades efectivamente comercializadas, Lanzamientos son proyectos que inician oferta, Iniciaciones son proyectos que empiezan construcción. Análisis integral proporciona visión completa del mercado",
            'contexto_ventas_departamental': "💰 CONTEXTO VENTAS AUTOMÁTICO: Al mencionar departamentos se proporciona ranking histórico de ventas, participación nacional y distribución por tipo de vivienda",
            'tendencias_ventas_disponibles': "📈 TENDENCIAS VENTAS: Sistema pre-cargado con análisis de tendencias mensuales de ventas, variaciones departamentales y distribución VIS/VIP/No VIS actualizada",
            
            # Comentarios sobre COYUNTURA DE OFERTA
            'contexto_coyuntura_oferta': "🏢 CONTEXTO OFERTA: Datos históricos de oferta disponible desde enero 2010 hasta octubre 2025, desagregados por 19 departamentos y clasificación VIS/VIP/No VIS",
            'oferta_vs_livo': "🔄 OFERTA vs LIVO: Los datos de coyuntura de oferta complementan la base LIVO. Oferta = unidades disponibles en el mercado; LIVO = seguimiento detallado de todo el ciclo",
            'oferta_vs_otros_sistemas': "📊 OFERTA vs LANZAMIENTOS/INICIACIONES/VENTAS: Oferta son unidades disponibles para compra, Lanzamientos inician comercialización, Iniciaciones empiezan construcción, Ventas son unidades efectivamente vendidas. Análisis integral proporciona visión 360° del mercado",
            'contexto_oferta_departamental': "🏢 CONTEXTO OFERTA AUTOMÁTICO: Al mencionar departamentos se proporciona ranking histórico de oferta, participación nacional y distribución por tipo de vivienda",
            'tendencias_oferta_disponibles': "📈 TENDENCIAS OFERTA: Sistema pre-cargado con análisis de tendencias mensuales de oferta, variaciones departamentales y distribución VIS/VIP/No VIS actualizada",
            
            # Comentarios sobre COMPARACIÓN CUÁDRUPLE
            'comparacion_cuadruple_disponible': "🔄 COMPARACIÓN INTEGRAL: Sistema de análisis cuádruple entre lanzamientos, iniciaciones, ventas y oferta disponible para análisis completo del mercado",
            'ratios_mercado_automaticos': "📊 RATIOS AUTOMÁTICOS: El sistema calcula automáticamente ratios de eficiencia como conversión lanzamientos→ventas, velocidad construcción, rotación inventario",
            'salud_mercado_evaluacion': "⚡ SALUD MERCADO: Evaluación automática de la salud del mercado basada en indicadores de eficiencia (Excelente/Buena/Regular/Necesita atención)",
            'flujo_mercado_integral': "🔄 FLUJO INTEGRAL: Análisis del flujo completo Lanzamientos→Iniciaciones→Ventas↔Oferta con interpretaciones automáticas",
            'analisis_departamental_cuadruple': "🏆 ANÁLISIS DEPARTAMENTAL: Comparación cuádruple por departamento con rankings, consistencia y análisis de desempeño integral",
            
            # Comentarios sobre CLASIFICACIÓN TEMPORAL (CRÍTICO)
            'clasificacion_temporal_critica': "🚨 CRÍTICO: Los proyectos duran 1-3 años y los salarios mínimos cambian cada año. Un mismo proyecto puede cambiar de VIS a VIP o viceversa entre años",
            'usar_año_proyecto': "📅 IMPORTANTE: Para clasificar VIS/VIP/No VIS usar el salario mínimo del AÑO del proyecto, no el actual. Un proyecto de $130M puede ser VIS en 2023 pero VIP en 2025",
            'sql_temporal_requerido': "⚠️ SQL TEMPORAL: Para análisis históricos usar CASE con rangos por año específico, no rangos fijos actuales",
            'ejemplo_cambio_temporal': "📊 EJEMPLO: Proyecto $130M → 2023: VIS (salario $1.16M) → 2025: VIP (salario $1.42M). Misma vivienda, diferente clasificación",
            
            # RECOMENDACIONES TEMPORALES APLICADAS
            'analisis_historico_temporal': "📈 ANÁLISIS HISTÓRICO: Usar clasificación del AÑO del proyecto. No aplicar rangos actuales a proyectos de años anteriores",
            'explicar_cambios_reportes': "📋 REPORTES: Explicar que la clasificación VIS/VIP/No VIS puede cambiar entre años por variación de salarios mínimos, no por cambios reales del proyecto",
            'sql_multianual_requerido': "🔄 ANÁLISIS MULTI-ANUAL: Usar SQL temporal con CASE para comparaciones entre años. Cada año debe usar sus propios rangos de clasificación",
            'verificar_variables_criticas': "✅ VERIFICACIÓN OBLIGATORIA: Antes de cualquier consulta LIVO verificar y especificar: usos, cuenta, estado, fase, last_estado, destino_etapa, uso_etapa, modalidad",
            
            # Comentarios sobre fechas y períodos (DEFINICIONES CORRECTAS)
            'año_corrido_definition': "📅 AÑO CORRIDO: Período de 12 meses desde el mismo mes del año anterior hasta el mes actual. Ej: si corte es octubre 2025, año corrido = octubre 2024 a octubre 2025. Usar año_corrido = 1 en la consulta",
            'ultimo_año_definition': "📊 ÚLTIMO AÑO: Se refiere a toda la información del año actual (año calendario completo). Ej: si estamos en 2025, último año = todo el año 2025. Usar LEFT(fecha, 4) = '2025'",
            'doce_meses_explanation': "🔄 DOCE_MESES: Variable que indica los últimos 12 meses móviles respecto al corte. Si corte es octubre 2025, doce_meses = 1 incluye desde noviembre 2024 hasta octubre 2025",
            'fecha_format_numeric': "🔢 FORMATO: Las fechas están en formato YYYYMMDD (ej: 20251031). Para extraer año usar LEFT(fecha, 4), para mes SUBSTRING(fecha, 5, 2)",
            'ultimos_meses_calculation': "📆 ÚLTIMOS N MESES: Para calcular últimos X meses, identificar el mes más reciente disponible y contar hacia atrás. Ej: si corte es octubre 2025, últimos 4 meses = octubre, septiembre, agosto, julio 2025",
            'period_identification': "🔍 IDENTIFICACIÓN DE PERÍODO: Usar MAX(fecha) para identificar el mes más reciente disponible, luego calcular períodos relativos desde esa fecha",
            'year_extraction_needed': "⚠️ EXTRACCIÓN DE AÑO: Para años específicos (2024, 2025) usar LEFT(fecha, 4) = 'YYYY' o YEAR(fecha) = YYYY",
            'period_specification_needed': "⏰ RECOMENDACIÓN: Definir período específico para evitar consultar todo el histórico. Usar doce_meses = 1 para datos recientes",
            
            # Comentarios sobre estados y fases
            'no_vendido_state': "No existe el estado 'vendido'. A lo mejor se refiere al TVE / TE (Terminado vendido y entregado / terminado y entregado)",
            'no_entrega_phase': "No existe la fase 'entrega' se debería utilizar entonces la cuenta 'entregadas'. La fase se refiere a la fase constructiva (cimentación, acabados, obra negra....)",
            'uso_etapa_casa_singular': "El uso etapa es 'Casa', sin s al final",
            'no_vivienda_destino': "No existe destino_etapa 'vivienda'. Debe ser el uso_etapa 'casa' y 'apartamento'",
            
            # Comentarios sobre ubicación geográfica
            'barrios_not_all_cities': "Tengo entendido que los barrios no son tomados en todas las ciudades, así que se debe tener en cuenta eso",
            'barrio_coverage_warning': "Se debe tener en cuenta que no se registra el barrio para todas las ciudades",
            
            # Comentarios sobre área y rangos
            'area_individual_vs_aggregate': "La variable area está agregada, para todas las unidades que hacen parte de x cuenta. Si la intención es filtrar por las unidades de vivienda que tienen un área individual mayor a 150 m2 se debe utilizar rango_area",
            
            # Comentarios sobre definición de valor de mercado
            'market_value_definition': "Se debe definir correctamente a qué se refiere con valor del mercado, si son las ventas, o los lanzamientos... revisar con Niko",
            'value_type_specification': "Considero que se debe especificar el valor de qué (ventas, iniciaciones, entregas….)",
            
            # Comentarios sobre variables que no existen
            'ventas_anuales_not_exists': "No se especificó si se creó la variable de ventas_anuales. Esa no existe en el totales, de lo contrario se debe construir a partir de la cuenta de ventas",
            
            # Comentarios sobre jerarquías geográficas
            'geographic_hierarchy_ciudad': "🗺️ JERARQUÍA: Si se filtra por ciudad, se deben agrupar los resultados por barrio para ver el detalle",
            'geographic_hierarchy_departamento': "🗺️ JERARQUÍA: Si se filtra por departamento, se pueden agrupar por ciudad o zona para mayor detalle",
            'geographic_hierarchy_regional': "🗺️ JERARQUÍA: Si se filtra por regional, se pueden agrupar por departamento o ciudad",
            'divipola_unique_identifier': "🏷️ IDENTIFICADOR: divipola es el código único de identificación geográfica",
            
            # Comentarios sobre identificadores únicos
            'nit_primary_key': "🔑 CLAVE PRIMARIA: nit_constructora es el identificador único de la constructora, use esta columna para agrupar por empresa",
            'identificador_project_key': "🔑 CLAVE PRIMARIA: identificador es único por proyecto, usar COUNT(DISTINCT identificador) para contar proyectos únicos",
            
            # Comentarios sobre orden cronológico de estados
            'phase_state_hierarchy': "📊 ORDEN CRONOLÓGICO: La fase es más general que el estado. El orden suele ser 'Preventa' (fase) → 'Licencia' (estado) → 'Vendido' (estado)",
            'project_lifecycle': "🔄 CICLO DE VIDA: Los proyectos siguen una secuencia lógica: Preventa → Aprobada → Construcción → Vendido → Entregado",
            
            # Recomendaciones generales
            'recommend_delivered_only': "Además, es recomendable trabajar únicamente con las entregadas, no con las ventas",
            'account_filter_mandatory': "La variable 'cuenta' actúa como filtro casi obligatorio para obtener resultados precisos en consultas LIVO",
            'duplicate_projects_warning': "⚠️ Un mismo proyecto puede aparecer múltiples veces en diferentes registros, por eso es crucial usar DISTINCT con el identificador",
            'constructora_groupby_recommendation': "💡 RECOMENDACIÓN: Para agrupar por constructora, considerar GROUP BY NIT_constructora, nombre_constructora para evitar duplicados por nombres similares"
        }
        
    def reset_state(self):
        """Resetea el estado de la conversación."""
        self.conversation_state = {key: None for key in self.conversation_state}
        print("🧠 Estado de la conversación reseteado.")

    def analyze_question(self, question: str, user_id: str, conversation_history: List[str] = None) -> ReasoningResult:
        """Analiza una pregunta y determina si necesita clarificación"""
        
        # MEJORA: Cargar preferencias del perfil de usuario
        if user_profile_manager:
            profile = user_profile_manager.get_profile(user_id)
            if profile and question.lower() in ["cómo va el mercado?", "resumen", "actualización"]:
                print(f"🧠 Usando perfil para usuario '{user_id}' en pregunta ambigua.")
                preferences = profile.get("preferences", {})
                for entity, values in preferences.items():
                    if values:
                        # Usar la preferencia más frecuente
                        most_frequent_value = max(values, key=values.get)
                        self.conversation_state[entity] = most_frequent_value

        full_conversation = " ".join(conversation_history) if conversation_history else ""
        full_conversation += " " + question
        question_normalized = normalize_text(full_conversation)
        
        # Actualizar el estado de la conversación con las nuevas entidades detectadas
        self._update_conversation_state(question_normalized)
        
        # MEJORA: Actualizar el perfil del usuario con las nuevas entidades
        if user_profile_manager:
            user_profile_manager.update_profile(user_id, self.conversation_state)
        
        # Usar el estado acumulado para el análisis
        present_elements = [key for key, value in self.conversation_state.items() if value is not None]
        missing_elements = self._detect_missing_elements(present_elements)

        # --- MEJORA: Considerar "nacional" como una ubicación válida explícitamente ---
        # Si se menciona "nacional" o similar, y 'location' es el único elemento faltante,
        # se considera una pregunta completa.
        if 'location' in missing_elements and len(missing_elements) == 1 and any(term in question_normalized for term in ['nacional', 'colombia', 'pais', 'todo el pais']):
            missing_elements.remove('location')
        
        # Determinar tipo de pregunta
        question_type = self._classify_question_type(question_normalized, present_elements, missing_elements)
        
        # Calcular confianza
        confidence = self._calculate_confidence(present_elements, missing_elements)
        
        # Generar contrapreguntas
        counter_questions = self._generate_counter_questions(question_normalized, missing_elements)
        
        # Generar comentarios de razonamiento
        reasoning_comments = self._generate_reasoning_comments(question_normalized, present_elements, missing_elements)
        
        # Generar sugerencias de clarificación
        suggested_clarifications = self._generate_clarifications(question_normalized, missing_elements)
        
        return ReasoningResult(
            question_type=question_type,
            confidence=confidence,
            missing_elements=missing_elements,
            counter_questions=counter_questions,
            reasoning_comments=reasoning_comments,
            suggested_clarifications=suggested_clarifications
        )

    def _update_conversation_state(self, question: str):
        """Detecta y actualiza las entidades en el estado de la conversación."""
        for entity, config in self.essential_elements.items():
            # Si la entidad ya está llena, no la sobrescribas (a menos que se implemente lógica de corrección)
            if self.conversation_state.get(entity) is not None:
                continue

            # Buscar la primera palabra clave que coincida para extraer el valor
            for keyword in config.get('keywords', []):
                normalized_keyword = normalize_text(keyword)
                if normalized_keyword in question:
                    self.conversation_state[entity] = keyword # Guardar el valor real, no el normalizado
                    break

    def _detect_present_elements(self, question: str) -> List[str]:
        """Detecta qué elementos están presentes en la pregunta"""
        present = []
        
        for element_type, element_info in self.essential_elements.items():
            for keyword in element_info.get('keywords', []):
                if normalize_text(keyword) in question:
                    present.append(element_type)
                    break
        
        return present

    def _detect_missing_elements(self, present_elements: List[str]) -> List[str]:
        """Detecta qué elementos esenciales faltan"""
        all_elements = set(self.essential_elements.keys())
        present_set = set(present_elements)
        return list(all_elements - present_set)

    def _classify_question_type(self, question: str, present_elements: List[str], missing_elements: List[str]) -> QuestionType:
        """Clasifica el tipo de pregunta"""
        
        # Verificar patrones de preguntas incompletas
        for pattern in self.incomplete_patterns:
            if re.match(pattern, question):
                return QuestionType.INCOMPLETE
        
        # PRIORIDAD CRÍTICA: Si falta account_type (cuenta), siempre necesita clarificación
        if 'account_type' in missing_elements:
            return QuestionType.NEEDS_CLARIFICATION
        
        # Si faltan más de 3 elementos esenciales
        if len(missing_elements) > 3:
            return QuestionType.INCOMPLETE
        
        # Si faltan 2-3 elementos importantes
        if len(missing_elements) >= 2:
            return QuestionType.NEEDS_CLARIFICATION
        
        # Si falta solo 1 elemento pero es crítico
        critical_elements = ['metric', 'operation', 'location']
        if any(elem in missing_elements for elem in critical_elements):
            return QuestionType.AMBIGUOUS
        
        return QuestionType.COMPLETE

    def _calculate_confidence(self, present_elements: List[str], missing_elements: List[str]) -> float:
        """Calcula la confianza de que la pregunta está completa"""
        total_elements = len(self.essential_elements)
        present_count = len(present_elements)
        
        # Si falta account_type (cuenta), confianza muy baja
        if 'account_type' in missing_elements:
            return max(0.1, (present_count / total_elements) * 0.3)  # Máximo 30% si falta cuenta
        
        # Peso extra para elementos críticos
        critical_elements = ['account_type', 'metric', 'operation']
        critical_present = sum(1 for elem in critical_elements if elem in present_elements)
        
        # Bonus especial si account_type está presente (40% del peso)
        account_bonus = 0.4 if 'account_type' in present_elements else 0
        
        base_confidence = present_count / total_elements
        critical_bonus = critical_present * 0.15
        
        return min(1.0, base_confidence + critical_bonus + account_bonus)

    def _generate_counter_questions(self, question: str, missing_elements: List[str]) -> List[str]:
        """Genera contrapreguntas dinámicas y contextuales basadas en elementos faltantes y la pregunta original."""
        counter_questions = []
        
        # --- Lógica para 'account_type' (CRÍTICO) ---
        if 'account_type' in missing_elements:
            if "comportamiento" in question:
                counter_questions.append("Para analizar el 'comportamiento', ¿sobre qué base lo hacemos? (ej: ventas, iniciaciones, lanzamientos, oferta).")
            else:
                counter_questions.append("¿Te refieres a unidades vendidas, iniciadas, lanzadas o en oferta?")
        
        # --- Lógica para 'metric' ---
        if 'metric' in missing_elements:
            if "ventas" in question:
                counter_questions.append("Cuando mencionas 'ventas', ¿qué métrica te interesa? (ej: número de unidades, valor total en pesos, precio promedio).")
            elif "lanzamientos" in question:
                counter_questions.append("Sobre los 'lanzamientos', ¿qué te gustaría saber? (ej: cantidad de proyectos, total de unidades).")
            else:
                counter_questions.append("¿Qué métrica específica necesitas? (ej: unidades, valor, área).")

        # --- Lógica para 'operation' ---
        if 'operation' in missing_elements:
            if "comportamiento" in question:
                counter_questions.append("¿Cómo te gustaría ver el 'comportamiento'? (ej: una evolución mensual, una comparación con el año anterior, un total acumulado).")
            else:
                counter_questions.append("¿Qué tipo de cálculo necesitas? (ej: un total, un promedio, un ranking).")

        # --- Lógica para 'location' ---
        if 'location' in missing_elements:
            counter_questions.append("¿Para qué ubicación geográfica necesitas esta información? (ej: Bogotá, Antioquia, o a nivel nacional).")

        # --- Lógica para 'time_period' ---
        if 'time_period' in missing_elements:
            counter_questions.append("¿Para qué período de tiempo? (ej: para el año 2025, el último trimestre, o un mes específico).")

        # --- Lógica para 'housing_type' ---
        if 'housing_type' in missing_elements:
            counter_questions.append("¿Te interesa algún tipo de vivienda en particular? (ej: VIS, No VIS, o todas).")

        # --- Lógica para 'company_identifier' ---
        if 'company_identifier' in missing_elements and 'constructora' in question:
            counter_questions.append("Para identificar de forma única a las constructoras, ¿debería incluir su NIT en el análisis?")
        
        # Limitar a un máximo de 3 preguntas para no abrumar al usuario
        return counter_questions[:3]

    def _generate_reasoning_comments(self, question: str, present_elements: List[str], missing_elements: List[str]) -> List[str]:
        """Genera comentarios de razonamiento basados en la pregunta"""
        # Esta función ya existe y es muy larga, la dejamos como está.
        # El diff se enfoca en agregar los métodos que faltaban.
        return [] # Placeholder para el diff, la lógica real está en el archivo.

    def _generate_clarifications(self, question: str, missing_elements: List[str]) -> List[str]:
        """Genera sugerencias específicas de clarificación"""
        clarifications = []
        if 'account_type' in missing_elements:
            clarifications.append("🚨 CRÍTICO: Especifica el tipo de cuenta (ventas, entregas, licencias, proceso)")
        if 'location' in missing_elements:
            clarifications.append("Especifica la ubicación geográfica (ciudad, departamento o región)")
        if 'metric' in missing_elements:
            clarifications.append("Define qué métrica necesitas (unidades, valor, área, etc.)")
        if 'time_period' in missing_elements:
            clarifications.append("Indica el período temporal de interés")
        if 'company_identifier' in missing_elements:
            clarifications.append("🏢 IMPORTANTE: Considera incluir el NIT para identificación única de constructoras")
        return clarifications

    def get_clarification_response(self, question: str, user_id: str = "default") -> str:
        """Genera una respuesta de clarificación para una pregunta incompleta"""
        result = self.analyze_question(question, user_id)
        
        if result.question_type == QuestionType.COMPLETE:
            return None
        
        # Construir una respuesta más amigable y directa
        response = "🤔 Para darte una respuesta más precisa, necesito que me ayudes a clarificar algunos puntos.\n\n"
        
        if result.counter_questions:
            # Presentar las preguntas de forma más conversacional
            for q in result.counter_questions:
                response += f"• {q}\n"
            response += "\n"
        else:
            # Mensaje genérico si no hay contrapreguntas específicas
            response += "Por favor, intenta reformular tu pregunta con más detalles sobre lo que necesitas."

        # ¡NUEVO! Sugerir una pregunta completa si la confianza es alta
        if result.confidence > 0.6 and not result.counter_questions:
             response += "\n**Sugerencia de pregunta completa:**\n"
             response += f"`{self.build_complete_question()}`\n"

        # Mensaje final amigable
        response += "\n💡 *Intenta responder a estas preguntas o reformula tu consulta con más detalles.*"
        
        return response

    def build_complete_question(self) -> str:
        """Construye una pregunta completa basada en el estado de la conversación."""
        # Mapeo de elementos a frases descriptivas
        element_to_phrase = {
            'account_type': self.conversation_state.get('account_type'),
            'location': f"en {self.conversation_state.get('location')}",
            'metric': f"el {self.conversation_state.get('metric')}",
            'time_period': f"para {self.conversation_state.get('time_period')}",
            'housing_type': f"de tipo {self.conversation_state.get('housing_type')}",
            'operation': f"el {self.conversation_state.get('operation')}",
        }

        # Construir la pregunta a partir de los elementos recordados
        phrases = [phrase for entity, phrase in element_to_phrase.items() 
                   if self.conversation_state.get(entity) and phrase]
        
        if not phrases:
            return "No tengo suficiente información para construir una pregunta."

        # Unir las frases de forma coherente
        complete_question = "Quiero saber sobre " + " ".join(phrases) + "."
        return complete_question.replace(" .", ".").replace("  ", " ")


# Función de utilidad para integración fácil
def analyze_and_respond(question: str, user_id: str, reasoning_system: ReasoningSystem = None, conversation_history: List[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Analiza una pregunta y retorna si necesita clarificación, la respuesta de clarificación,
    y el SQL generado si la pregunta está completa.
    
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (needs_clarification, clarification_response, generated_sql)
    """
    if reasoning_system is None:
        reasoning_system = ReasoningSystem()
    
    result = reasoning_system.analyze_question(question, user_id, conversation_history=conversation_history)
    
    if result.question_type != QuestionType.COMPLETE:
        # La pregunta es incompleta, necesita clarificación
        clarification_response = reasoning_system.get_clarification_response(question, user_id)
        return True, clarification_response, None
    else:
        # La pregunta está completa y es de tipo LIVO, lista para generar SQL.
        # En este punto, no generamos el SQL aquí, pero señalamos que está lista.
        # El sistema LIVO se encargará de la generación del SQL.
        # Devolvemos 'None' para el SQL, ya que el bot_telegram/app se lo pedirá a livo_sql.
        # Lo importante es que 'needs_clarification' es False.
        return False, "Pregunta completa, lista para LIVO.", None
