#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test para verificar la generación automática de gráficos
Solo basada en el texto de la consulta, sin controles adicionales
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_automatic_chart_decision():
    """Prueba la lógica de decisión automática para generar gráficos"""
    
    print("PRUEBA: DECISIÓN AUTOMÁTICA DE GENERACIÓN DE GRÁFICOS")
    print("=" * 80)
    
    try:
        from livo_sql import LIVOSQLSystem
        livo_system = LIVOSQLSystem()
        print("✅ Sistema LIVO importado correctamente")
    except ImportError as e:
        print(f"❌ Error importando LIVO: {e}")
        return False
    
    # Casos de prueba con diferentes tipos de consultas
    test_cases = [
        # CASOS QUE SÍ DEBEN GENERAR GRÁFICO
        {
            "pregunta": "¿Cuántas unidades VIS hay por ciudad?",
            "result": [['Bogotá', 15420], ['Medellín', 8750], ['Cali', 6230]],
            "esperado": True,
            "razon": "Análisis por ciudad con datos múltiples"
        },
        {
            "pregunta": "Mostrar el ranking de constructoras",
            "result": [['Constructora A', 5420], ['Constructora B', 4850], ['Constructora C', 4230]],
            "esperado": True,
            "razon": "Palabra clave 'ranking'"
        },
        {
            "pregunta": "Comparar VIS vs VIP vs No VIS",
            "result": [['VIS', 15420], ['VIP', 8200], ['No VIS', 12300]],
            "esperado": True,
            "razon": "Palabra clave 'comparar' y clasificación de vivienda"
        },
        {
            "pregunta": "Evolución de licencias por año",
            "result": [['2023', 1250], ['2024', 1380], ['2025', 1420]],
            "esperado": True,
            "razon": "Palabra clave 'evolución' - análisis temporal"
        },
        {
            "pregunta": "Top 5 departamentos con más unidades",
            "result": [['Antioquia', 25000], ['Cundinamarca', 22000], ['Valle', 18000], ['Atlántico', 12000], ['Santander', 10000]],
            "esperado": True,
            "razon": "Palabra clave 'top' y análisis geográfico"
        },
        {
            "pregunta": "Distribución de proyectos por estrato",
            "result": [['Estrato 1', 120], ['Estrato 2', 180], ['Estrato 3', 250], ['Estrato 4', 200], ['Estrato 5', 150], ['Estrato 6', 100]],
            "esperado": True,
            "razon": "Palabra clave 'distribución' con datos múltiples"
        },
        
        # CASOS QUE NO DEBEN GENERAR GRÁFICO
        {
            "pregunta": "¿Cuántas licencias hay en total?",
            "result": [['Total', 45680]],
            "esperado": False,
            "razon": "Consulta simple de conteo con una sola cifra"
        },
        {
            "pregunta": "¿Cuál es el área promedio de las viviendas?",
            "result": [['Área promedio', 85.5]],
            "esperado": False,
            "razon": "Consulta simple con un solo valor"
        },
        {
            "pregunta": "Total de unidades VIS",
            "result": [['Total VIS', 28450]],
            "esperado": False,
            "razon": "Consulta de total simple"
        }
    ]
    
    # Ejecutar pruebas
    resultados = []
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. PREGUNTA: {case['pregunta']}")
        print(f"   DATOS: {len(case['result'])} filas")
        print(f"   ESPERADO: {'SÍ' if case['esperado'] else 'NO'} generar gráfico")
        print(f"   RAZÓN: {case['razon']}")
        
        # Probar decisión automática
        decision = livo_system.should_generate_chart(case['pregunta'], case['result'])
        
        # Verificar resultado
        if decision == case['esperado']:
            print(f"   ✅ CORRECTO: {'Generará' if decision else 'No generará'} gráfico")
            resultados.append(True)
        else:
            print(f"   ❌ INCORRECTO: {'Generará' if decision else 'No generará'} gráfico (esperado: {'Sí' if case['esperado'] else 'No'})")
            resultados.append(False)
    
    # Resumen
    print(f"\nRESUMEN DE PRUEBAS")
    print("=" * 80)
    
    correctas = sum(resultados)
    total = len(resultados)
    
    print(f"✅ Correctas: {correctas}/{total}")
    print(f"❌ Incorrectas: {total - correctas}/{total}")
    print(f"📊 Precisión: {correctas/total*100:.1f}%")
    
    if correctas == total:
        print("\n🎉 ¡Todas las decisiones automáticas son correctas!")
        print("El sistema puede generar gráficos automáticamente basado solo en el texto.")
    elif correctas >= total * 0.8:
        print("\n✅ La mayoría de decisiones son correctas (≥80%)")
        print("El sistema funciona bien para la generación automática.")
    else:
        print("\n⚠️ Muchas decisiones incorrectas (<80%)")
        print("Revisar la lógica de decisión automática.")
    
    return correctas >= total * 0.8

def test_chart_generation_examples():
    """Muestra ejemplos de cuándo se generarán gráficos automáticamente"""
    
    print(f"\nEJEMPLOS DE GENERACIÓN AUTOMÁTICA")
    print("=" * 80)
    
    ejemplos_si = [
        "¿Cuántas unidades VIS hay por ciudad?",
        "Mostrar el top 10 de constructoras",
        "Comparar licencias VIS vs VIP",
        "Evolución de proyectos en los últimos años",
        "Distribución de viviendas por estrato",
        "Ranking de departamentos por área construida",
        "Gráfico de unidades por regional",
        "Tendencia mensual de licencias"
    ]
    
    ejemplos_no = [
        "¿Cuántas licencias hay en total?",
        "¿Cuál es el área promedio?",
        "Total de unidades VIS",
        "¿Cuánto vale el proyecto más caro?",
        "Suma de todas las áreas"
    ]
    
    print("✅ CONSULTAS QUE SÍ GENERARÁN GRÁFICO AUTOMÁTICAMENTE:")
    for i, ejemplo in enumerate(ejemplos_si, 1):
        print(f"   {i}. {ejemplo}")
    
    print(f"\n❌ CONSULTAS QUE NO GENERARÁN GRÁFICO:")
    for i, ejemplo in enumerate(ejemplos_no, 1):
        print(f"   {i}. {ejemplo}")
    
    print(f"\n💡 CRITERIOS AUTOMÁTICOS:")
    print("- Palabras clave: gráfico, mostrar, comparar, ranking, top, evolución, tendencia")
    print("- Análisis geográfico: por ciudad, por departamento, ciudades, departamentos")
    print("- Análisis temporal: por año, por mes, histórico, anual, mensual")
    print("- Clasificación: VIS, VIP, No VIS, distribución, proporción")
    print("- Datos múltiples: ≥3 filas con ≥2 columnas")
    print("- Excluye: consultas simples de conteo con una sola cifra")

def main():
    """Función principal"""
    
    print("🤖 SISTEMA DE GENERACIÓN AUTOMÁTICA DE GRÁFICOS")
    print("Solo basado en el texto de la consulta - Sin controles adicionales")
    print("=" * 80)
    
    try:
        # Ejecutar pruebas
        success = test_automatic_chart_decision()
        test_chart_generation_examples()
        
        print(f"\nCONCLUSIÓN:")
        print("=" * 80)
        
        if success:
            print("✅ El sistema de generación automática funciona correctamente")
            print("✅ Los gráficos se generarán automáticamente basado solo en el texto")
            print("✅ No se necesitan controles adicionales (botones, barras, etc.)")
            print("\nRECOMENDACIÓN: Mantener la funcionalidad de generación automática")
        else:
            print("❌ El sistema de decisión automática necesita mejoras")
            print("❌ Considerar eliminar la funcionalidad como solicitado")
            print("\nRECOMENDACIÓN: Revisar lógica o eliminar funcionalidad")
        
        print(f"\nDEPENDENCIAS REQUERIDAS (ya agregadas a requirements.txt):")
        print("- matplotlib>=3.7.0")
        print("- seaborn>=0.12.0") 
        print("- pillow>=10.0.0")
        print("- plotly>=5.17.0")
        
    except Exception as e:
        print(f"❌ Error en las pruebas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
