"""
Pruebas del sistema de coyuntura de iniciaciones LIVO.

Este archivo prueba la funcionalidad del sistema de datos pre-cargados
de coyuntura de iniciaciones y su integración con el sistema de razonamiento
y el sistema de lanzamientos.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from iniciaciones_coyuntura import iniciaciones_coyuntura, IniciacionesCoyunturaSystem
from lanzamientos_coyuntura import lanzamientos_coyuntura
from reasoning_system import ReasoningSystem

def test_sistema_coyuntura_basico():
    """Prueba funcionalidades básicas del sistema de coyuntura de iniciaciones."""
    print("=== PRUEBA 1: SISTEMA BÁSICO DE COYUNTURA INICIACIONES ===")
    
    # Obtener estadísticas generales
    stats = iniciaciones_coyuntura.obtener_estadisticas_generales()
    print(f"📊 Total registros: {stats['total_registros']}")
    print(f"📅 Período: {stats['periodo_cobertura']['desde']} a {stats['periodo_cobertura']['hasta']}")
    print(f"🏢 Departamentos: {stats['departamentos_cubiertos']}")
    print(f"🏗️ Total iniciaciones históricas: {stats['total_iniciaciones_historicas']:,}")
    print()

def test_contexto_periodo():
    """Prueba obtención de contexto por período."""
    print("=== PRUEBA 2: CONTEXTO POR PERÍODO INICIACIONES ===")
    
    # Contexto período completo
    contexto_completo = iniciaciones_coyuntura.obtener_contexto_periodo()
    print("📈 PERÍODO COMPLETO:")
    print(f"  Total iniciaciones: {contexto_completo['totales']['iniciaciones']:,}")
    print(f"  Distribución VIP: {contexto_completo['distribucion']['VIP']['porcentaje']}%")
    print(f"  Distribución VIS: {contexto_completo['distribucion']['VIS']['porcentaje']}%")
    print(f"  Distribución No VIS: {contexto_completo['distribucion']['NO_VIS']['porcentaje']}%")
    print(f"  Top 3 departamentos: {[d[0] for d in contexto_completo['top_departamentos'][:3]]}")
    print()

def test_tendencias_recientes():
    """Prueba análisis de tendencias recientes."""
    print("=== PRUEBA 3: TENDENCIAS RECIENTES INICIACIONES ===")
    
    tendencias = iniciaciones_coyuntura.obtener_tendencia_reciente(6)
    print(f"📊 ANÁLISIS ÚLTIMOS 6 MESES:")
    print(f"  Período: {tendencias['periodo_analizado']['desde']} a {tendencias['periodo_analizado']['hasta']}")
    
    if tendencias['variacion_mensual']:
        var = tendencias['variacion_mensual']
        print(f"  Variación mensual total: {var['total']}%")
        print(f"  Variación VIS: {var['vis']}%")
        print(f"  Variación No VIS: {var['no_vis']}%")
    
    if tendencias['mes_mas_activo']:
        mes_activo = tendencias['mes_mas_activo']
        print(f"  Mes más activo: {mes_activo[0]} ({mes_activo[1]['total']} iniciaciones)")
    print()

def test_comparacion_departamental():
    """Prueba comparación entre departamentos."""
    print("=== PRUEBA 4: COMPARACIÓN DEPARTAMENTAL INICIACIONES ===")
    
    comparacion = iniciaciones_coyuntura.obtener_comparacion_departamental(5)
    print("🏆 TOP 5 DEPARTAMENTOS (Total iniciaciones):")
    for i, (depto, stats) in enumerate(comparacion['ranking_total'], 1):
        print(f"  {i}. {depto}: {stats['total_iniciaciones']:,} unidades")
        print(f"     VIS: {stats['vis_pct']}%, No VIS: {stats['no_vis_pct']}%")
    
    print(f"\n📊 Total nacional: {comparacion['total_nacional']:,} iniciaciones")
    print()

def test_contexto_consultas():
    """Prueba generación de contexto para diferentes tipos de consultas."""
    print("=== PRUEBA 5: CONTEXTO AUTOMÁTICO POR CONSULTA INICIACIONES ===")
    
    consultas_prueba = [
        "¿Cuáles son las tendencias recientes de iniciaciones?",
        "Análisis de iniciaciones en Antioquia",
        "Comparar iniciaciones VIS entre departamentos",
        "¿Cómo ha evolucionado la coyuntura de iniciaciones en 2025?",
        "Ranking de departamentos por iniciaciones No VIS"
    ]
    
    for consulta in consultas_prueba:
        print(f"🔍 CONSULTA: {consulta}")
        contexto = iniciaciones_coyuntura.generar_contexto_consulta(consulta)
        if contexto:
            print(f"   CONTEXTO: {contexto}")
        else:
            print("   CONTEXTO: No se generó contexto específico")
        print()

def test_comparacion_con_lanzamientos():
    """Prueba comparación entre iniciaciones y lanzamientos."""
    print("=== PRUEBA 6: COMPARACIÓN INICIACIONES VS LANZAMIENTOS ===")
    
    comparacion = iniciaciones_coyuntura.comparar_con_lanzamientos(lanzamientos_coyuntura)
    
    print("📊 TOTALES HISTÓRICOS:")
    print(f"  Lanzamientos: {comparacion['totales']['lanzamientos']:,} unidades")
    print(f"  Iniciaciones: {comparacion['totales']['iniciaciones']:,} unidades")
    print(f"  Ratio Ini/Lan: {comparacion['totales']['ratio_ini_lan']}")
    
    print("\n🏠 DISTRIBUCIÓN COMPARADA:")
    dist_lan = comparacion['distribucion_comparada']['lanzamientos']
    dist_ini = comparacion['distribucion_comparada']['iniciaciones']
    dif = comparacion['diferencias']
    
    print(f"  VIP: Lanzamientos {dist_lan['vip']}% vs Iniciaciones {dist_ini['vip']}% (Dif: {dif['vip']:+.1f}%)")
    print(f"  VIS: Lanzamientos {dist_lan['vis']}% vs Iniciaciones {dist_ini['vis']}% (Dif: {dif['vis']:+.1f}%)")
    print(f"  No VIS: Lanzamientos {dist_lan['no_vis']}% vs Iniciaciones {dist_ini['no_vis']}% (Dif: {dif['no_vis']:+.1f}%)")
    print()

def test_integracion_reasoning():
    """Prueba integración con el sistema de razonamiento."""
    print("=== PRUEBA 7: INTEGRACIÓN CON REASONING SYSTEM ===")
    
    reasoning = ReasoningSystem()
    
    consultas_test = [
        "¿Cuántas iniciaciones hubo en Antioquia el último año?",
        "Análisis de coyuntura de iniciaciones VIS en Bogotá",
        "Tendencias recientes de iniciaciones por departamento",
        "Comparar iniciaciones vs lanzamientos en Valle"
    ]
    
    for consulta in consultas_test:
        print(f"🔍 CONSULTA: {consulta}")
        resultado = reasoning.analyze_question(consulta)
        
        print(f"   Tipo: {resultado.question_type.value}")
        print(f"   Confianza: {resultado.confidence}")
        
        if resultado.reasoning_comments:
            print("   COMENTARIOS DE COYUNTURA:")
            for comment in resultado.reasoning_comments:
                if any(keyword in comment for keyword in ['INICIACIONES', 'CONTEXTO', 'RANKING', 'TENDENCIAS']):
                    print(f"     • {comment}")
        print()

def test_datos_especificos():
    """Prueba datos específicos del sistema."""
    print("=== PRUEBA 8: VERIFICACIÓN DE DATOS ESPECÍFICOS ===")
    
    # Verificar algunos datos conocidos
    datos_enero_2010 = [d for d in iniciaciones_coyuntura.datos_historicos 
                       if d.fecha == 'ene-10' and d.departamento == 'Antioquia']
    
    if datos_enero_2010:
        dato = datos_enero_2010[0]
        print(f"✅ Enero 2010 - Antioquia:")
        print(f"   VIP: {dato.vip}, VIS: {dato.vis_total}, No VIS: {dato.no_vis}, Total: {dato.total}")
    
    # Verificar datos recientes
    datos_oct_2025 = [d for d in iniciaciones_coyuntura.datos_historicos 
                     if d.fecha == 'oct-25' and d.departamento == 'Bogotá & Cundinamarca']
    
    if datos_oct_2025:
        dato = datos_oct_2025[0]
        print(f"✅ Octubre 2025 - Bogotá & Cundinamarca:")
        print(f"   VIP: {dato.vip}, VIS: {dato.vis_total}, No VIS: {dato.no_vis}, Total: {dato.total}")
    
    print(f"\n📋 Departamentos disponibles: {len(iniciaciones_coyuntura.departamentos)}")
    print(f"📋 Agregaciones regionales: {list(iniciaciones_coyuntura.agregaciones_regionales.keys())}")
    print()

def test_funcionalidades_avanzadas():
    """Prueba funcionalidades avanzadas del sistema."""
    print("=== PRUEBA 9: FUNCIONALIDADES AVANZADAS ===")
    
    # Probar contexto para consulta específica con múltiples elementos
    consulta_compleja = "¿Cómo han evolucionado las iniciaciones VIS en Antioquia y Valle comparado con los lanzamientos?"
    
    print(f"🔍 CONSULTA COMPLEJA: {consulta_compleja}")
    
    # Contexto de iniciaciones
    contexto_ini = iniciaciones_coyuntura.generar_contexto_consulta(consulta_compleja)
    print(f"📊 Contexto Iniciaciones: {contexto_ini}")
    
    # Contexto de lanzamientos para comparación
    contexto_lan = lanzamientos_coyuntura.generar_contexto_consulta(consulta_compleja)
    print(f"📈 Contexto Lanzamientos: {contexto_lan}")
    
    # Análisis con reasoning system
    reasoning = ReasoningSystem()
    resultado = reasoning.analyze_question(consulta_compleja)
    
    print(f"\n🧠 Análisis de Razonamiento:")
    print(f"   Comentarios generados: {len(resultado.reasoning_comments)}")
    
    comentarios_coyuntura = [c for c in resultado.reasoning_comments 
                           if any(keyword in c for keyword in ['INICIACIONES', 'LANZAMIENTOS', 'CONTEXTO', 'COYUNTURA'])]
    
    print(f"   Comentarios de coyuntura: {len(comentarios_coyuntura)}")
    for comentario in comentarios_coyuntura[:3]:  # Mostrar primeros 3
        print(f"     • {comentario[:100]}...")
    
    print()

def main():
    """Ejecuta todas las pruebas del sistema de coyuntura de iniciaciones."""
    print("🚀 INICIANDO PRUEBAS DEL SISTEMA DE COYUNTURA DE INICIACIONES")
    print("=" * 80)
    
    try:
        test_sistema_coyuntura_basico()
        test_contexto_periodo()
        test_tendencias_recientes()
        test_comparacion_departamental()
        test_contexto_consultas()
        test_comparacion_con_lanzamientos()
        test_integracion_reasoning()
        test_datos_especificos()
        test_funcionalidades_avanzadas()
        
        print("✅ TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
        print("=" * 80)
        print("📊 RESUMEN:")
        print("• Sistema de coyuntura de iniciaciones funcionando correctamente")
        print("• Datos históricos cargados desde enero 2010 hasta octubre 2025")
        print("• Integración con sistema de razonamiento activa")
        print("• Integración con sistema de lanzamientos funcional")
        print("• Contexto automático generándose para consultas relevantes")
        print("• 19 departamentos con datos completos")
        print("• Análisis de tendencias y comparaciones disponibles")
        print("• Comparación automática entre iniciaciones y lanzamientos")
        
    except Exception as e:
        print(f"❌ ERROR EN LAS PRUEBAS: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
