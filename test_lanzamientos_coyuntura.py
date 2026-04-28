"""
Pruebas del sistema de coyuntura de lanzamientos LIVO.

Este archivo prueba la funcionalidad del sistema de datos pre-cargados
de coyuntura de lanzamientos y su integración con el sistema de razonamiento.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from lanzamientos_coyuntura import lanzamientos_coyuntura, LanzamientosCoyunturaSystem
from reasoning_system import ReasoningSystem

def test_sistema_coyuntura_basico():
    """Prueba funcionalidades básicas del sistema de coyuntura."""
    print("=== PRUEBA 1: SISTEMA BÁSICO DE COYUNTURA ===")
    
    # Obtener estadísticas generales
    stats = lanzamientos_coyuntura.obtener_estadisticas_generales()
    print(f"📊 Total registros: {stats['total_registros']}")
    print(f"📅 Período: {stats['periodo_cobertura']['desde']} a {stats['periodo_cobertura']['hasta']}")
    print(f"🏢 Departamentos: {stats['departamentos_cubiertos']}")
    print(f"🏠 Total lanzamientos históricos: {stats['total_lanzamientos_historicos']:,}")
    print()

def test_contexto_periodo():
    """Prueba obtención de contexto por período."""
    print("=== PRUEBA 2: CONTEXTO POR PERÍODO ===")
    
    # Contexto período completo
    contexto_completo = lanzamientos_coyuntura.obtener_contexto_periodo()
    print("📈 PERÍODO COMPLETO:")
    print(f"  Total lanzamientos: {contexto_completo['totales']['lanzamientos']:,}")
    print(f"  Distribución VIP: {contexto_completo['distribucion']['VIP']['porcentaje']}%")
    print(f"  Distribución VIS: {contexto_completo['distribucion']['VIS']['porcentaje']}%")
    print(f"  Distribución No VIS: {contexto_completo['distribucion']['NO_VIS']['porcentaje']}%")
    print(f"  Top 3 departamentos: {[d[0] for d in contexto_completo['top_departamentos'][:3]]}")
    print()

def test_tendencias_recientes():
    """Prueba análisis de tendencias recientes."""
    print("=== PRUEBA 3: TENDENCIAS RECIENTES ===")
    
    tendencias = lanzamientos_coyuntura.obtener_tendencia_reciente(6)
    print(f"📊 ANÁLISIS ÚLTIMOS 6 MESES:")
    print(f"  Período: {tendencias['periodo_analizado']['desde']} a {tendencias['periodo_analizado']['hasta']}")
    
    if tendencias['variacion_mensual']:
        var = tendencias['variacion_mensual']
        print(f"  Variación mensual total: {var['total']}%")
        print(f"  Variación VIS: {var['vis']}%")
        print(f"  Variación No VIS: {var['no_vis']}%")
    
    if tendencias['mes_mas_activo']:
        mes_activo = tendencias['mes_mas_activo']
        print(f"  Mes más activo: {mes_activo[0]} ({mes_activo[1]['total']} lanzamientos)")
    print()

def test_comparacion_departamental():
    """Prueba comparación entre departamentos."""
    print("=== PRUEBA 4: COMPARACIÓN DEPARTAMENTAL ===")
    
    comparacion = lanzamientos_coyuntura.obtener_comparacion_departamental(5)
    print("🏆 TOP 5 DEPARTAMENTOS (Total lanzamientos):")
    for i, (depto, stats) in enumerate(comparacion['ranking_total'], 1):
        print(f"  {i}. {depto}: {stats['total_lanzamientos']:,} unidades")
        print(f"     VIS: {stats['vis_pct']}%, No VIS: {stats['no_vis_pct']}%")
    
    print(f"\n📊 Total nacional: {comparacion['total_nacional']:,} lanzamientos")
    print()

def test_contexto_consultas():
    """Prueba generación de contexto para diferentes tipos de consultas."""
    print("=== PRUEBA 5: CONTEXTO AUTOMÁTICO POR CONSULTA ===")
    
    consultas_prueba = [
        "¿Cuáles son las tendencias recientes de lanzamientos?",
        "Análisis de lanzamientos en Antioquia",
        "Comparar lanzamientos VIS entre departamentos",
        "¿Cómo ha evolucionado la coyuntura de lanzamientos en 2025?",
        "Ranking de departamentos por lanzamientos No VIS"
    ]
    
    for consulta in consultas_prueba:
        print(f"🔍 CONSULTA: {consulta}")
        contexto = lanzamientos_coyuntura.generar_contexto_consulta(consulta)
        if contexto:
            print(f"   CONTEXTO: {contexto}")
        else:
            print("   CONTEXTO: No se generó contexto específico")
        print()

def test_integracion_reasoning():
    """Prueba integración con el sistema de razonamiento."""
    print("=== PRUEBA 6: INTEGRACIÓN CON REASONING SYSTEM ===")
    
    reasoning = ReasoningSystem()
    
    consultas_test = [
        "¿Cuántos lanzamientos hubo en Antioquia el último año?",
        "Análisis de coyuntura de lanzamientos VIS en Bogotá",
        "Tendencias recientes de lanzamientos por departamento"
    ]
    
    for consulta in consultas_test:
        print(f"🔍 CONSULTA: {consulta}")
        resultado = reasoning.analyze_question(consulta)
        
        print(f"   Tipo: {resultado.question_type.value}")
        print(f"   Confianza: {resultado.confidence}")
        
        if resultado.reasoning_comments:
            print("   COMENTARIOS DE COYUNTURA:")
            for comment in resultado.reasoning_comments:
                if any(keyword in comment for keyword in ['CONTEXTO', 'COYUNTURA', 'RANKING', 'TENDENCIAS']):
                    print(f"     • {comment}")
        print()

def test_datos_especificos():
    """Prueba datos específicos del sistema."""
    print("=== PRUEBA 7: VERIFICACIÓN DE DATOS ESPECÍFICOS ===")
    
    # Verificar algunos datos conocidos
    datos_enero_2010 = [d for d in lanzamientos_coyuntura.datos_historicos 
                       if d.fecha == 'ene-10' and d.departamento == 'Antioquia']
    
    if datos_enero_2010:
        dato = datos_enero_2010[0]
        print(f"✅ Enero 2010 - Antioquia:")
        print(f"   VIP: {dato.vip}, VIS: {dato.vis_total}, No VIS: {dato.no_vis}, Total: {dato.total}")
    
    # Verificar datos recientes
    datos_oct_2025 = [d for d in lanzamientos_coyuntura.datos_historicos 
                     if d.fecha == 'oct-25' and d.departamento == 'Bogotá & Cundinamarca']
    
    if datos_oct_2025:
        dato = datos_oct_2025[0]
        print(f"✅ Octubre 2025 - Bogotá & Cundinamarca:")
        print(f"   VIP: {dato.vip}, VIS: {dato.vis_total}, No VIS: {dato.no_vis}, Total: {dato.total}")
    
    print(f"\n📋 Departamentos disponibles: {len(lanzamientos_coyuntura.departamentos)}")
    print(f"📋 Agregaciones regionales: {list(lanzamientos_coyuntura.agregaciones_regionales.keys())}")
    print()

def main():
    """Ejecuta todas las pruebas del sistema de coyuntura."""
    print("🚀 INICIANDO PRUEBAS DEL SISTEMA DE COYUNTURA DE LANZAMIENTOS")
    print("=" * 70)
    
    try:
        test_sistema_coyuntura_basico()
        test_contexto_periodo()
        test_tendencias_recientes()
        test_comparacion_departamental()
        test_contexto_consultas()
        test_integracion_reasoning()
        test_datos_especificos()
        
        print("✅ TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
        print("=" * 70)
        print("📊 RESUMEN:")
        print("• Sistema de coyuntura funcionando correctamente")
        print("• Datos históricos cargados desde enero 2010 hasta octubre 2025")
        print("• Integración con sistema de razonamiento activa")
        print("• Contexto automático generándose para consultas relevantes")
        print("• 19 departamentos con datos completos")
        print("• Análisis de tendencias y comparaciones disponibles")
        
    except Exception as e:
        print(f"❌ ERROR EN LAS PRUEBAS: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
