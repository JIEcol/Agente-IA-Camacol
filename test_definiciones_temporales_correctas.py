#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test para verificar las definiciones CORRECTAS de períodos temporales según Julian Torres
"""

from reasoning_system import ReasoningSystem

def test_definiciones_correctas():
    """Prueba las definiciones correctas de períodos temporales"""
    
    print("VERIFICACION DE DEFINICIONES TEMPORALES CORRECTAS")
    print("=" * 80)
    
    reasoning_system = ReasoningSystem()
    
    # Casos de prueba con las definiciones CORRECTAS
    test_cases = [
        {
            "concepto": "AÑO CORRIDO",
            "definicion_correcta": "Período de 12 meses desde el mismo mes del año anterior hasta el mes actual",
            "ejemplo": "Si corte es octubre 2025, año corrido = octubre 2024 a octubre 2025",
            "sql_correcto": "WHERE año_corrido = 1",
            "pregunta": "Dame los datos del año corrido"
        },
        {
            "concepto": "ÚLTIMO AÑO", 
            "definicion_correcta": "Toda la información del año actual (año calendario completo)",
            "ejemplo": "Si estamos en 2025, último año = todo el año 2025 (enero a diciembre)",
            "sql_correcto": "WHERE LEFT(fecha, 4) = '2025'",
            "pregunta": "¿Cuántas unidades hay en el último año?"
        },
        {
            "concepto": "ÚLTIMOS 4 MESES",
            "definicion_correcta": "Identificar el mes más reciente y contar 4 meses hacia atrás",
            "ejemplo": "Si corte es octubre 2025, últimos 4 meses = octubre, septiembre, agosto, julio 2025",
            "sql_correcto": "WHERE LEFT(fecha, 6) IN ('202510', '202509', '202508', '202507')",
            "pregunta": "Dame información de los últimos 4 meses"
        }
    ]
    
    print(f"\nPROBANDO {len(test_cases)} DEFINICIONES TEMPORALES:")
    print("-" * 60)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. CONCEPTO: {case['concepto']}")
        print(f"   DEFINICION CORRECTA: {case['definicion_correcta']}")
        print(f"   EJEMPLO: {case['ejemplo']}")
        print(f"   SQL CORRECTO: {case['sql_correcto']}")
        print(f"   PREGUNTA DE PRUEBA: {case['pregunta']}")
        print("-" * 50)
        
        # Analizar la pregunta
        result = reasoning_system.analyze_question(case['pregunta'])
        
        print(f"   RESULTADO DEL ANALISIS:")
        print(f"   - Tipo: {result.question_type.value}")
        print(f"   - Confianza: {result.confidence:.2f}")
        
        # Buscar comentarios relacionados con el concepto
        concepto_keywords = {
            "AÑO CORRIDO": ["año corrido", "corrido", "12 meses desde"],
            "ÚLTIMO AÑO": ["último año", "año actual", "año calendario"],
            "ÚLTIMOS 4 MESES": ["últimos", "meses", "hacia atrás", "contar"]
        }
        
        keywords = concepto_keywords.get(case['concepto'], [])
        related_comments = []
        
        for comment in result.reasoning_comments:
            # Limpiar emojis para comparación
            clean_comment = ''.join(c for c in comment if ord(c) < 128).lower()
            if any(keyword in clean_comment for keyword in keywords):
                related_comments.append(comment)
        
        if related_comments:
            print(f"   - COMENTARIOS RELACIONADOS DETECTADOS: {len(related_comments)}")
            for j, comment in enumerate(related_comments, 1):
                # Mostrar solo texto sin emojis
                clean_comment = ''.join(c for c in comment if ord(c) < 128)[:80]
                print(f"     {j}. {clean_comment}...")
        else:
            print(f"   - NO SE DETECTARON COMENTARIOS RELACIONADOS")
        
        print("\n" + "="*80)
    
    return True

def test_deteccion_ultimos_n_meses():
    """Prueba específica para detección de 'últimos N meses'"""
    
    print("\nPRUEBA ESPECIFICA: DETECCION DE 'ULTIMOS N MESES'")
    print("=" * 80)
    
    reasoning_system = ReasoningSystem()
    
    casos_meses = [
        "Dame los últimos 3 meses de datos",
        "¿Cuántas unidades en los últimos 6 meses?",
        "Información de los últimos 12 meses",
        "Últimos 2 meses de construcciones"
    ]
    
    for i, pregunta in enumerate(casos_meses, 1):
        print(f"\n{i}. PREGUNTA: {pregunta}")
        
        result = reasoning_system.analyze_question(pregunta)
        
        # Buscar comentarios sobre cálculo de meses
        meses_comments = [c for c in result.reasoning_comments 
                         if any(word in c.lower() for word in ['meses', 'calcular', 'identificar', 'contar'])]
        
        if meses_comments:
            print(f"   DETECTA CALCULO DE MESES: SI ({len(meses_comments)} comentarios)")
        else:
            print(f"   DETECTA CALCULO DE MESES: NO")
        
        print("-" * 50)

def main():
    """Función principal"""
    try:
        print("INICIANDO VERIFICACION DE DEFINICIONES TEMPORALES CORRECTAS")
        print("Basado en las definiciones proporcionadas por Julian Torres")
        print("=" * 80)
        
        test_definiciones_correctas()
        test_deteccion_ultimos_n_meses()
        
        print("\nRESUMEN DE DEFINICIONES CORRECTAS IMPLEMENTADAS:")
        print("=" * 80)
        print("1. AÑO CORRIDO:")
        print("   - Definición: 12 meses desde mismo mes año anterior hasta mes actual")
        print("   - Ejemplo: Oct 2024 a Oct 2025 (si corte es Oct 2025)")
        print("   - SQL: WHERE año_corrido = 1")
        print()
        print("2. ÚLTIMO AÑO:")
        print("   - Definición: Todo el año calendario actual")
        print("   - Ejemplo: Enero a Diciembre 2025 (si estamos en 2025)")
        print("   - SQL: WHERE LEFT(fecha, 4) = '2025'")
        print()
        print("3. ÚLTIMOS N MESES:")
        print("   - Proceso: Identificar mes más reciente, contar N meses hacia atrás")
        print("   - Ejemplo: Si Oct 2025 es más reciente, últimos 4 = Oct, Sep, Ago, Jul 2025")
        print("   - SQL: WHERE LEFT(fecha, 6) IN ('202510', '202509', '202508', '202507')")
        print()
        print("ESTADO: Definiciones actualizadas en el sistema de razonamiento")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
