#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test para verificar la nueva clasificación de vivienda por VALOR
"""

from reasoning_system import ReasoningSystem
from livo_sql import SalarioMinimoColombiano, LIVOSQLSystem

def test_salarios_minimos():
    """Prueba la funcionalidad de salarios mínimos"""
    
    print("PRUEBA: SALARIOS MINIMOS Y RANGOS DE VIVIENDA")
    print("=" * 80)
    
    # Probar salarios por año
    años_prueba = [2023, 2024, 2025]
    
    for año in años_prueba:
        salario = SalarioMinimoColombiano.obtener_salario_minimo(año)
        print(f"Salario mínimo {año}: ${salario:,}")
    
    print(f"\nSalario actual: ${SalarioMinimoColombiano.obtener_salario_actual():,}")
    
    # Probar rangos de vivienda
    print("\nRANGOS DE VIVIENDA 2025:")
    print("-" * 40)
    
    rangos = SalarioMinimoColombiano.calcular_rangos_vivienda(2025)
    
    for tipo, info in rangos.items():
        if info['max'] == float('inf'):
            print(f"{tipo}: ${info['min']:,} en adelante")
        else:
            print(f"{tipo}: ${info['min']:,} - ${info['max']:,}")
        print(f"    {info['descripcion']}")
    
    # Probar rangos SQL
    print("\nCONDICIONES SQL GENERADAS:")
    print("-" * 40)
    
    rangos_sql = LIVOSQLSystem.obtener_rangos_vivienda_sql(2025)
    
    for tipo in ['VIP', 'VIS', 'NO_VIS']:
        print(f"{tipo}: WHERE {rangos_sql[tipo]}")
    
    return True

def test_deteccion_clasificacion():
    """Prueba que el sistema de razonamiento detecte la nueva clasificación"""
    
    print("\nPRUEBA: DETECCION DE NUEVA CLASIFICACION POR VALOR")
    print("=" * 80)
    
    reasoning_system = ReasoningSystem()
    
    # Casos de prueba
    test_cases = [
        {
            "pregunta": "¿Cuántas unidades VIP hay en Bogotá?",
            "esperado": "Debe recomendar usar 'valor' en lugar de 'tipo_vivienda'",
            "tipo": "VIP"
        },
        {
            "pregunta": "Dame las construcciones VIS del último año",
            "esperado": "Debe explicar nueva clasificación por valor para VIS",
            "tipo": "VIS"
        },
        {
            "pregunta": "¿Qué constructoras tienen más proyectos No VIS?",
            "esperado": "Debe mostrar condición SQL por valor para No VIS",
            "tipo": "NO_VIS"
        },
        {
            "pregunta": "Quiero filtrar por tipo_vivienda = 'VIS'",
            "esperado": "Debe advertir sobre cambio a clasificación por valor",
            "tipo": "CAMPO_ANTERIOR"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. PREGUNTA: {case['pregunta']}")
        print(f"   TIPO: {case['tipo']}")
        print(f"   ESPERADO: {case['esperado']}")
        print("-" * 50)
        
        result = reasoning_system.analyze_question(case['pregunta'])
        
        # Buscar comentarios sobre clasificación por valor
        valor_comments = []
        for comment in result.reasoning_comments:
            clean_comment = ''.join(c for c in comment if ord(c) < 128).lower()
            if any(keyword in clean_comment for keyword in ['valor', 'clasificacion', 'salario', 'vip', 'vis', 'no vis']):
                valor_comments.append(comment)
        
        print(f"   RESULTADO:")
        print(f"   - Tipo: {result.question_type.value}")
        print(f"   - Confianza: {result.confidence:.2f}")
        
        if valor_comments:
            print(f"   - COMENTARIOS SOBRE VALOR DETECTADOS: {len(valor_comments)}")
            for j, comment in enumerate(valor_comments, 1):
                # Mostrar solo texto sin emojis
                clean_comment = ''.join(c for c in comment if ord(c) < 128)[:70]
                print(f"     {j}. {clean_comment}...")
        else:
            print(f"   - NO SE DETECTARON COMENTARIOS SOBRE VALOR")
        
        print("\n" + "="*80)

def test_ejemplos_sql():
    """Muestra ejemplos de SQL con la nueva clasificación"""
    
    print("\nEJEMPLOS SQL CON NUEVA CLASIFICACION POR VALOR")
    print("=" * 80)
    
    rangos_sql = LIVOSQLSystem.obtener_rangos_vivienda_sql(2025)
    salario_info = rangos_sql['info']
    
    print(f"Basado en salario mínimo 2025: ${salario_info['salario_minimo']:,}")
    print()
    
    ejemplos = [
        {
            "consulta": "Unidades VIP en Bogotá",
            "sql_anterior": "WHERE tipo_vivienda = 'VIP' AND ciudad LIKE '%Bogotá%'",
            "sql_nuevo": f"WHERE {rangos_sql['VIP']} AND ciudad LIKE '%Bogotá%'"
        },
        {
            "consulta": "Constructoras con proyectos VIS",
            "sql_anterior": "WHERE tipo_vivienda = 'VIS'",
            "sql_nuevo": f"WHERE {rangos_sql['VIS']}"
        },
        {
            "consulta": "Área promedio No VIS por ciudad",
            "sql_anterior": "WHERE tipo_vivienda = 'No VIS'",
            "sql_nuevo": f"WHERE {rangos_sql['NO_VIS']}"
        }
    ]
    
    for i, ejemplo in enumerate(ejemplos, 1):
        print(f"{i}. CONSULTA: {ejemplo['consulta']}")
        print(f"   ❌ MÉTODO ANTERIOR: {ejemplo['sql_anterior']}")
        print(f"   ✅ MÉTODO NUEVO:    {ejemplo['sql_nuevo']}")
        print()

def main():
    """Función principal"""
    try:
        print("INICIANDO PRUEBAS DE CLASIFICACION POR VALOR")
        print("Implementando cambio de tipo_vivienda a clasificación por valor")
        print("=" * 80)
        
        test_salarios_minimos()
        test_deteccion_clasificacion()
        test_ejemplos_sql()
        
        print("\nRESUMEN DEL CAMBIO IMPLEMENTADO:")
        print("=" * 80)
        print("ANTES (método anterior):")
        print("- Usar campo 'tipo_vivienda' con valores 'VIS', 'VIP', 'No VIS'")
        print("- Ejemplo: WHERE tipo_vivienda = 'VIS'")
        print()
        print("AHORA (método nuevo):")
        print("- Usar campo 'valor' con rangos basados en salarios mínimos")
        print("- VIP: valor < 117,000 (< 90 SMMLV)")
        print("- VIS: valor >= 117,000 AND valor < 175,500 (90-135 SMMLV)")  
        print("- No VIS: valor >= 175,500 (> 135 SMMLV)")
        print()
        print("VENTAJAS:")
        print("✅ Clasificación automática basada en valor real")
        print("✅ Actualización automática con salarios mínimos anuales")
        print("✅ Más preciso que categorías fijas")
        print("✅ Información estática (no requiere LLM para salarios)")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
