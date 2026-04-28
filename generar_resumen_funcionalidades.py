#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para generar un resumen ejecutivo de las capacidades del Agente CAMACOL.
Genera un archivo Excel para entregar a usuarios no técnicos.
"""

import pandas as pd
from pathlib import Path

def generar_tabla_capacidades():
    print("🚀 Generando tabla de capacidades del agente...")
    
    # Hoja 1: Resumen General
    data_general = [
        {
            "Categoría": "Indicadores de Mercado",
            "Funcionalidad": "Indicadores Rápidos de Mercado (Coyuntura)",
            "Tipo de Fuente": "Coyuntura (Datos Agregados Oficiales)",
            "Ruta de Aplicación (Prioridad)": "1. Prioridad Máxima (Reglas)",
            "Tipos de Preguntas": "¿Ventas en Antioquia el mes pasado? / ¿Oferta en Bogotá? / ¿Rotación en Cali?",
            "Tipo de Respuesta": "Dato oficial consolidado + Comparación anual + Contexto de ranking departamental."
        },
        {
            "Categoría": "Análisis de Proyectos",
            "Funcionalidad": "Consultas Detalladas de Proyectos (LIVO)",
            "Tipo de Fuente": "LIVO (Base de Datos Proyecto a Proyecto)",
            "Ruta de Aplicación (Prioridad)": "2. Prioridad Alta (Reglas de Negocio)",
            "Tipos de Preguntas": "Top 5 constructoras en Medellín / Precio promedio m2 en Barranquilla / Unidades por estado.",
            "Tipo de Respuesta": "Cálculo exacto en tiempo real + Market Share + Segmentación VIS/No VIS + Auditoría."
        },
        {
            "Categoría": "Inteligencia Artificial",
            "Funcionalidad": "Análisis Complejo y Flexible (IA)",
            "Tipo de Fuente": "LIVO (Base de Datos Proyecto a Proyecto)",
            "Ruta de Aplicación (Prioridad)": "3. Prioridad Media (Inteligencia Artificial)",
            "Tipos de Preguntas": "Comparar el área promedio de VIS vs No VIS en estrato 3 / Tendencia de ventas últimos 6 meses.",
            "Tipo de Respuesta": "SQL generado dinámicamente + Análisis de tendencias + Detección de anomalías + Gráficos."
        },
        {
            "Categoría": "Normativa",
            "Funcionalidad": "Consultas Normativas y Jurídicas",
            "Tipo de Fuente": "RAG (Documentos PDF, Decretos, Leyes)",
            "Ruta de Aplicación (Prioridad)": "4. Complementaria / Fallback",
            "Tipos de Preguntas": "¿Qué dice la resolución de subsidios? / Requisitos para vivienda VIS / Normativa sismorresistente.",
            "Tipo de Respuesta": "Resumen textual basado en documentos + Citas de fuentes + Contexto normativo."
        },
        {
            "Categoría": "Macroeconomía",
            "Funcionalidad": "Indicadores Macroeconómicos",
            "Tipo de Fuente": "Excel Dinámico (Proyecciones, PIB, Empleo)",
            "Ruta de Aplicación (Prioridad)": "2. Paralela (Si detecta palabras clave)",
            "Tipos de Preguntas": "¿Cuál es la proyección del PIB 2025? / Tasa de desempleo en construcción / Inflación esperada.",
            "Tipo de Respuesta": "Dato puntual extraído de reportes externos + Fuente del dato."
        }
    ]

    # Hoja 2: Analítica Avanzada (Nuevas funcionalidades)
    data_analitica = [
        {"Análisis": "Proyecciones (Forecasting)", "Descripción": "Proyecta cifras futuras basándose en promedios móviles recientes.", "Valor": "Anticipación de tendencias a corto plazo."},
        {"Análisis": "Benchmarking Automático", "Descripción": "Compara la ciudad consultada con su par económico más cercano.", "Valor": "Contexto competitivo inmediato."},
        {"Análisis": "Absorción de Lanzamientos", "Descripción": "Calcula qué porcentaje de lo lanzado se ha vendido.", "Valor": "Medición de la salud de la demanda."},
        {"Análisis": "Concentración (HHI)", "Descripción": "Calcula el índice Herfindahl-Hirschman para medir competencia.", "Valor": "Identificación de mercados saturados o monopolizados."},
        {"Análisis": "Valorización", "Descripción": "Calcula la variación del precio por m² frente al año anterior.", "Valor": "Análisis de plusvalía y rentabilidad."},
        {"Análisis": "Alertas de Agotamiento", "Descripción": "Detecta si el inventario (rotación) está en niveles críticos (< 6 meses).", "Valor": "Alerta temprana de escasez (Stockout)."},
        {"Análisis": "Segmentación Fina", "Descripción": "Desglosa No VIS en rangos de precios (Medio, Alto, Lujo).", "Valor": "Entendimiento profundo del segmento No VIS."},
        {"Análisis": "Estacionalidad", "Descripción": "Indica si el mes consultado es históricamente alto o bajo.", "Valor": "Contexto temporal para la toma de decisiones."},
        {"Análisis": "Simulación (What-If)", "Descripción": "Simula escenarios hipotéticos (ej: caída de demanda).", "Valor": "Planeación estratégica y gestión de riesgos."},
        {"Análisis": "Auditoría de Datos", "Descripción": "Detecta automáticamente valores anómalos o negativos.", "Valor": "Confiabilidad y calidad de la información."},
        {"Análisis": "Correlación Macro", "Descripción": "Sugiere relaciones con tasas de interés o desempleo.", "Valor": "Visión holística del mercado."},
        {"Análisis": "Market Share", "Descripción": "Calcula la participación porcentual respecto al total nacional.", "Valor": "Perspectiva de importancia relativa."}
    ]

    # Hoja 3: Experiencia y UX
    data_ux = [
        {"Característica": "Memoria Conversacional", "Detalle": "Recuerda el contexto de preguntas anteriores para 'drill-down'."},
        {"Característica": "Reportes Ejecutivos", "Detalle": "Genera resúmenes estructurados en formato Markdown listos para copiar."},
        {"Característica": "Gráficos Automáticos", "Detalle": "Genera visualizaciones cuando la data lo permite (en entornos soportados)."},
        {"Característica": "Feedback y Aprendizaje", "Detalle": "Sistema de retroalimentación para mejora continua del modelo."},
        {"Característica": "Perfilamiento", "Detalle": "Adapta respuestas según el perfil inferido del usuario."},
        {"Característica": "Detección de Idioma", "Detalle": "Traduce automáticamente preguntas en otros idiomas al español."},
        {"Característica": "Escudo de Seguridad", "Detalle": "Filtra preguntas maliciosas o fuera del alcance ético."}
    ]
    
    output_path = Path("resumen_capacidades_agente.xlsx")
    
    try:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            pd.DataFrame(data_general).to_excel(writer, sheet_name='Resumen General', index=False)
            pd.DataFrame(data_analitica).to_excel(writer, sheet_name='Analítica Avanzada', index=False)
            pd.DataFrame(data_ux).to_excel(writer, sheet_name='Experiencia y UX', index=False)
            
            # Ajustar ancho de columnas (intento básico)
            for sheet_name in writer.sheets:
                sheet = writer.sheets[sheet_name]
                for column in sheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = (max_length + 2) if max_length < 50 else 50
                    sheet.column_dimensions[column_letter].width = adjusted_width

        print(f"✅ Archivo generado exitosamente con 3 hojas detalladas: {output_path.absolute()}")
    except Exception as e:
        print(f"❌ Error generando el archivo Excel: {e}")

if __name__ == "__main__":
    generar_tabla_capacidades()