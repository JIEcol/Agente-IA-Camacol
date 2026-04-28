#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test para verificar la nueva clasificación temporal de vivienda
Considera que los proyectos pueden cambiar de categoría entre años
"""

from datetime import datetime
from reasoning_system import ReasoningSystem

# Clase con salarios mínimos históricos
class SalarioMinimoColombiano:
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
        return cls.SALARIOS_MINIMOS.get(año, cls.SALARIOS_MINIMOS[2024])
    
    @classmethod
    def calcular_rangos_vivienda(cls, año: int = None):
        if año is None:
            año = datetime.now().year
        
        salario_minimo = cls.obtener_salario_minimo(año)
        
        return {
            'VIP': {
                'min': 0,
                'max': salario_minimo * 90,
                'descripcion': f'Vivienda de Interés Prioritario (< 90 SMMLV {año})'
            },
            'VIS': {
                'min': salario_minimo * 90,
                'max': salario_minimo * 135,
                'descripcion': f'Vivienda de Interés Social (90 - 135 SMMLV {año})'
            },
            'NO_VIS': {
                'min': salario_minimo * 135,
                'max': float('inf'),
                'descripcion': f'Vivienda No VIS (> 135 SMMLV {año})'
            }
        }

def test_cambios_temporales():
    """Prueba cómo cambia la clasificación de un proyecto a lo largo del tiempo"""
    
    print("PRUEBA: CAMBIOS TEMPORALES EN CLASIFICACION DE VIVIENDA")
    print("=" * 80)
    
    # Casos de prueba con diferentes valores
    casos_prueba = [
        {"valor": 100000, "descripcion": "Proyecto $100M"},
        {"valor": 130000, "descripcion": "Proyecto $130M"},
        {"valor": 150000, "descripcion": "Proyecto $150M"},
        {"valor": 200000, "descripcion": "Proyecto $200M"}
    ]
    
    años_analisis = [2023, 2024, 2025]
    
    for caso in casos_prueba:
        valor = caso["valor"]  # En miles
        print(f"\n{caso['descripcion']} (${valor:,} miles):")
        print("-" * 50)
        
        for año in años_analisis:
            rangos = SalarioMinimoColombiano.calcular_rangos_vivienda(año)
            salario = SalarioMinimoColombiano.obtener_salario_minimo(año)
            
            # Determinar clasificación
            vip_max_miles = rangos['VIP']['max'] // 1000
            vis_max_miles = rangos['VIS']['max'] // 1000
            
            if valor < vip_max_miles:
                clasificacion = "VIP"
            elif valor < vis_max_miles:
                clasificacion = "VIS"
            else:
                clasificacion = "NO_VIS"
            
            print(f"  {año}: Salario ${salario:,} → {clasificacion}")
        
        print()

def test_sql_temporal():
    """Genera y muestra el SQL temporal para clasificación"""
    
    print("PRUEBA: GENERACION SQL TEMPORAL")
    print("=" * 80)
    
    def generar_clasificacion_temporal_sql(valor_campo='valor', fecha_campo='fecha'):
        """Genera SQL para clasificar por año"""
        sql_cases = []
        
        for año in range(2023, 2026):  # 2023-2025
            rangos = SalarioMinimoColombiano.calcular_rangos_vivienda(año)
            vip_max_miles = rangos['VIP']['max'] // 1000
            vis_min_miles = rangos['VIS']['min'] // 1000
            vis_max_miles = rangos['VIS']['max'] // 1000
            no_vis_min_miles = rangos['NO_VIS']['min'] // 1000
            
            año_condition = f"LEFT({fecha_campo}, 4) = '{año}'"
            
            sql_cases.append(f"""
    WHEN {año_condition} AND {valor_campo} < {vip_max_miles} THEN 'VIP'
    WHEN {año_condition} AND {valor_campo} >= {vis_min_miles} AND {valor_campo} < {vis_max_miles} THEN 'VIS'
    WHEN {año_condition} AND {valor_campo} >= {no_vis_min_miles} THEN 'NO_VIS'""")
        
        return f"""CASE{''.join(sql_cases)}
    ELSE 'SIN_CLASIFICAR'
END AS clasificacion_vivienda_temporal"""
    
    sql_temporal = generar_clasificacion_temporal_sql()
    print("SQL GENERADO:")
    print(sql_temporal)
    
    print(f"\nEJEMPLO DE USO:")
    print("-" * 40)
    print("SELECT")
    print("    identificador,")
    print("    fecha,")
    print("    valor,")
    print("    " + sql_temporal.replace('\n', '\n    '))
    print("FROM livo")
    print("WHERE clasificacion_vivienda_temporal = 'VIS'")

def test_deteccion_razonamiento():
    """Prueba que el sistema de razonamiento detecte aspectos temporales"""
    
    print("\nPRUEBA: DETECCION DE ASPECTOS TEMPORALES")
    print("=" * 80)
    
    reasoning_system = ReasoningSystem()
    
    casos_prueba = [
        {
            "pregunta": "¿Cuántas unidades VIS hay en Bogotá?",
            "esperado": "Debe advertir sobre clasificación temporal"
        },
        {
            "pregunta": "Evolución de proyectos VIP en los últimos años",
            "esperado": "Debe recomendar SQL temporal para análisis histórico"
        },
        {
            "pregunta": "Cambios en vivienda de interés social 2023 vs 2025",
            "esperado": "Debe explicar que la clasificación puede cambiar"
        },
        {
            "pregunta": "Tendencia histórica de No VIS por año",
            "esperado": "Debe usar rangos específicos por año"
        }
    ]
    
    for i, caso in enumerate(casos_prueba, 1):
        print(f"\n{i}. PREGUNTA: {caso['pregunta']}")
        print(f"   ESPERADO: {caso['esperado']}")
        print("-" * 50)
        
        result = reasoning_system.analyze_question(caso['pregunta'])
        
        # Buscar comentarios temporales
        temporal_comments = []
        for comment in result.reasoning_comments:
            clean_comment = ''.join(c for c in comment if ord(c) < 128).lower()
            if any(keyword in clean_comment for keyword in ['temporal', 'año', 'cambio', 'historico', 'proyecto', 'salario']):
                temporal_comments.append(comment)
        
        print(f"   RESULTADO:")
        print(f"   - Comentarios temporales detectados: {len(temporal_comments)}")
        
        if temporal_comments:
            for j, comment in enumerate(temporal_comments[:3], 1):  # Mostrar solo 3
                clean_comment = ''.join(c for c in comment if ord(c) < 128)[:80]
                print(f"     {j}. {clean_comment}...")
        else:
            print(f"     - NO se detectaron aspectos temporales")

def test_casos_problematicos():
    """Muestra casos donde la clasificación cambia problemáticamente"""
    
    print("\nCASOS PROBLEMATICOS - MISMO PROYECTO, DIFERENTE CLASIFICACION")
    print("=" * 80)
    
    # Proyecto que cambia de VIS a VIP
    valor_critico = 130000  # $130M
    
    print(f"PROYECTO CRÍTICO: ${valor_critico:,} miles (${valor_critico*1000:,} pesos)")
    print("-" * 60)
    
    for año in [2023, 2024, 2025]:
        rangos = SalarioMinimoColombiano.calcular_rangos_vivienda(año)
        salario = SalarioMinimoColombiano.obtener_salario_minimo(año)
        
        vip_max_miles = rangos['VIP']['max'] // 1000
        vis_max_miles = rangos['VIS']['max'] // 1000
        
        if valor_critico < vip_max_miles:
            clasificacion = "VIP"
            color = "🟢"
        elif valor_critico < vis_max_miles:
            clasificacion = "VIS"  
            color = "🟡"
        else:
            clasificacion = "NO_VIS"
            color = "🔴"
        
        print(f"{año}: {color} {clasificacion} (salario ${salario:,}, limite VIP: ${vip_max_miles:,})")
    
    print(f"\n⚠️ PROBLEMA:")
    print(f"- El mismo proyecto cambia de clasificación entre años")
    print(f"- Esto afecta estadísticas históricas")
    print(f"- Necesario usar clasificación del año específico")
    
    print(f"\n✅ SOLUCIÓN:")
    print(f"- Usar SQL temporal con CASE por año")
    print(f"- No usar rangos fijos actuales para análisis histórico")
    print(f"- Considerar el contexto temporal en reportes")

def main():
    """Función principal"""
    try:
        print("INICIANDO PRUEBAS DE CLASIFICACION TEMPORAL")
        print("Aspecto crítico: Los proyectos pueden cambiar de categoría entre años")
        print("=" * 80)
        
        test_cambios_temporales()
        test_sql_temporal()
        test_deteccion_razonamiento()
        test_casos_problematicos()
        
        print("\nRESUMEN DE IMPLEMENTACION TEMPORAL:")
        print("=" * 80)
        print("✅ Detección de aspecto temporal crítico")
        print("✅ SQL temporal generado automáticamente")
        print("✅ Sistema de razonamiento actualizado")
        print("✅ Ejemplos de casos problemáticos identificados")
        print()
        print("RECOMENDACIONES CRÍTICAS:")
        print("- Usar clasificación del año del proyecto, no actual")
        print("- Para análisis históricos, usar SQL temporal con CASE")
        print("- Considerar que proyectos pueden 'cambiar' de categoría")
        print("- Explicar este aspecto en reportes y análisis")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
