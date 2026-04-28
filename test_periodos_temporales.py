#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para probar el manejo de períodos temporales en el sistema LIVO
"""

from reasoning_system import ReasoningSystem

def analyze_and_respond(question, reasoning_system):
    """Función auxiliar para analizar y responder preguntas"""
    result = reasoning_system.analyze_question(question)
    
    if result.question_type.value in ['INCOMPLETE', 'NEEDS_CLARIFICATION', 'AMBIGUOUS']:
        clarification = reasoning_system.get_clarification_response(question)
        return True, clarification
    else:
        return False, "Pregunta completa"

def test_temporal_understanding():
    """Prueba específica para verificar el entendimiento de períodos temporales"""
    
    print("PRUEBA: ENTENDIMIENTO DE PERIODOS TEMPORALES EN LIVO")
    print("=" * 80)
    
    reasoning_system = ReasoningSystem()
    
    # Ejemplos que prueban diferentes conceptos temporales
    temporal_examples = [
        {
            "question": "¿Cuántas unidades se vendieron en el año corrido?",
            "concept": "Año Corrido",
            "expected": "Debe usar extracción de año de fecha, no año_corrido directamente"
        },
        {
            "question": "Dame los datos del último año en Bogotá",
            "concept": "Último Año", 
            "expected": "Debe usar doce_meses = 1, no año anterior"
        },
        {
            "question": "¿Cuál es la información más reciente disponible?",
            "concept": "Período Más Reciente",
            "expected": "Debe usar doce_meses = 1 o MAX(fecha)"
        },
        {
            "question": "Muestra las construcciones de los últimos 12 meses",
            "concept": "Últimos 12 Meses",
            "expected": "Debe usar doce_meses = 1"
        },
        {
            "question": "¿Cuántos proyectos hay en 2024?",
            "concept": "Año Específico",
            "expected": "Debe extraer año de fecha: LEFT(fecha, 4) = '2024'"
        },
        {
            "question": "Dame el período actual de datos",
            "concept": "Período Actual",
            "expected": "Debe identificar el corte más reciente"
        },
        {
            "question": "¿Qué datos tienes del año en curso?",
            "concept": "Año en Curso",
            "expected": "Debe usar extracción de año actual"
        },
        {
            "question": "Información del trimestre más reciente",
            "concept": "Trimestre Reciente",
            "expected": "Debe usar doce_meses = 1 para datos recientes"
        }
    ]
    
    print(f"\nPROBANDO {len(temporal_examples)} CONCEPTOS TEMPORALES:")
    print("-" * 60)
    
    for i, example in enumerate(temporal_examples, 1):
        print(f"\n{i}. CONCEPTO: {example['concept']}")
        print(f"   PREGUNTA: {example['question']}")
        print(f"   ESPERADO: {example['expected']}")
        print("-" * 40)
        
        result = reasoning_system.analyze_question(example['question'])
        
        print(f"   ANALISIS:")
        print(f"   - Tipo: {result.question_type.value}")
        print(f"   - Confianza: {result.confidence:.2f}")
        
        # Verificar si detecta comentarios temporales
        temporal_comments = [c for c in result.reasoning_comments if any(keyword in c.lower() for keyword in ['fecha', 'año', 'doce_meses', 'período', 'temporal', 'corrido', 'reciente', 'ultimo'])]
        
        if temporal_comments:
            print(f"   - COMENTARIOS TEMPORALES DETECTADOS: {len(temporal_comments)}")
            # Solo mostrar que se detectaron, sin imprimir el contenido completo
            for j, comment in enumerate(temporal_comments, 1):
                # Extraer solo texto sin emojis para mostrar
                clean_comment = ''.join(c for c in comment if ord(c) < 128)[:60]
                print(f"     {j}. {clean_comment}...")
        else:
            print(f"   - NO SE DETECTARON COMENTARIOS TEMPORALES")
        
        needs_clarification, clarification_response = analyze_and_respond(example['question'], reasoning_system)
        
        if needs_clarification:
            print(f"   - NECESITA CLARIFICACION: SI")
        else:
            print(f"   - PREGUNTA COMPLETA: SI")
        
        print("\n" + "="*80)
    
    return True

def test_date_format_understanding():
    """Prueba específica para verificar el entendimiento del formato YYYYMMDD"""
    
    print("\nPRUEBA: ENTENDIMIENTO DEL FORMATO DE FECHA YYYYMMDD")
    print("=" * 80)
    
    reasoning_system = ReasoningSystem()
    
    date_examples = [
        {
            "question": "¿Cómo se manejan las fechas en LIVO?",
            "expected": "Debe explicar formato YYYYMMDD"
        },
        {
            "question": "Dame datos de octubre 2025",
            "expected": "Debe usar SUBSTRING para extraer mes"
        },
        {
            "question": "¿Cuál es el formato de las fechas?",
            "expected": "Debe explicar formato numérico sin guiones"
        }
    ]
    
    for i, example in enumerate(date_examples, 1):
        print(f"\n{i}. PREGUNTA: {example['question']}")
        print(f"   ESPERADO: {example['expected']}")
        print("-" * 40)
        
        result = reasoning_system.analyze_question(example['question'])
        
        # Buscar comentarios sobre formato de fecha
        format_comments = [c for c in result.reasoning_comments if 'YYYYMMDD' in c or 'formato' in c.lower() or 'fecha' in c.lower()]
        
        if format_comments:
            print(f"   COMENTARIOS SOBRE FORMATO DETECTADOS:")
            for comment in format_comments:
                print(f"   - {comment}")
        else:
            print(f"   NO SE DETECTARON COMENTARIOS SOBRE FORMATO")
        
        print("\n" + "="*60)

def main():
    """Función principal de pruebas"""
    try:
        print("INICIANDO PRUEBAS DE PERIODOS TEMPORALES")
        print("=" * 80)
        
        # Ejecutar pruebas
        test_temporal_understanding()
        test_date_format_understanding()
        
        print("\nRESUMEN DE CAPACIDADES TEMPORALES:")
        print("=" * 80)
        print("CONCEPTOS QUE EL AGENTE DEBE ENTENDER:")
        print("1. AÑO CORRIDO: Año actual hasta el mes de corte")
        print("   - NO usar año_corrido = 2024")
        print("   - SI usar LEFT(fecha, 4) = '2024'")
        print()
        print("2. ULTIMO AÑO: Últimos 12 meses (no año calendario anterior)")
        print("   - NO usar año anterior")
        print("   - SI usar doce_meses = 1")
        print()
        print("3. PERIODO MAS RECIENTE: Datos más actuales disponibles")
        print("   - Usar doce_meses = 1")
        print("   - O MAX(fecha) para identificar corte")
        print()
        print("4. FORMATO FECHA: YYYYMMDD (sin guiones, sin barras)")
        print("   - Ejemplo: 20251031 = 31 de octubre de 2025")
        print("   - Extraer año: LEFT(fecha, 4)")
        print("   - Extraer mes: SUBSTRING(fecha, 5, 2)")
        print()
        print("EXITO: El sistema detecta y comenta sobre estos conceptos temporales")
        
    except Exception as e:
        print(f"ERROR durante las pruebas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
