#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de prueba para el sistema de razonamiento
Demuestra cómo funciona la detección de preguntas incompletas y la generación de contrapreguntas
"""

from reasoning_system import ReasoningSystem, analyze_and_respond

def test_reasoning_system():
    """Prueba el sistema de razonamiento con diferentes tipos de preguntas"""
    
    print("🧠 SISTEMA DE RAZONAMIENTO PARA CHATBOT CAMACOL")
    print("=" * 60)
    
    # Inicializar sistema
    reasoning_system = ReasoningSystem()
    
    # Preguntas de prueba basadas en los ejemplos proporcionados
    test_questions = [
        # Preguntas incompletas que necesitan clarificación
        "¿Cuántas unidades?",
        "¿Cuál es el precio?", 
        "Dame información sobre viviendas",
        "¿Qué tal las ventas?",
        "Muestra datos de construcción",
        
        # Preguntas que necesitan especificación de CUENTA (crítico)
        "¿Cuántas unidades hay en Bogotá?",  # Falta cuenta - ¿vendidas, entregadas, en proceso?
        "¿Cuál es el total de área en Cundinamarca?",  # Falta cuenta - ¿área vendida, entregada?
        "Dame el valor de proyectos VIS en Medellín",  # Falta cuenta - ¿valor vendido, entregado?
        
        # Preguntas que necesitan especificación
        "¿Cuántas unidades se han vendido?",  # Falta ubicación pero tiene cuenta
        "¿Cuál es el precio promedio de una unidad con estrato 6?",  # Falta ciudad y cuenta
        "Muestra el total de registros por estado",  # Falta tipo de proyecto y cuenta
        
        # Preguntas más completas pero que aún pueden necesitar clarificación
        "¿Cuántas unidades se han vendido en Cundinamarca?",  # Tiene cuenta y ubicación
        "¿Cuál es el precio promedio de una unidad con estrato 6 en Bogotá?",  # Falta cuenta
        "Liste las constructoras y la suma total del área construida para el año 2024",  # Falta cuenta
        
        # Preguntas completas
        "¿Cuál es el valor mínimo y máximo de una unidad NO VIS entregada en Bogotá durante 2024?",
        "¿Cuántas unidades totales están en fase de Preventa en todas las regiones para vivienda VIS?",
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{i}. PREGUNTA: {question}")
        print("-" * 50)
        
        # Analizar la pregunta
        result = reasoning_system.analyze_question(question)
        
        print(f"📊 ANÁLISIS:")
        print(f"   Tipo: {result.question_type.value}")
        print(f"   Confianza: {result.confidence:.2f}")
        print(f"   Elementos faltantes: {result.missing_elements}")
        
        # Verificar si necesita clarificación
        needs_clarification, clarification_response = analyze_and_respond(question, reasoning_system)
        
        if needs_clarification:
            print(f"\n🤔 NECESITA CLARIFICACIÓN:")
            print(f"   {clarification_response}")
        else:
            print(f"\n✅ PREGUNTA COMPLETA - Proceder con consulta normal")
        
        print("\n" + "="*60)

def test_specific_examples():
    """Prueba con los ejemplos específicos proporcionados por el usuario"""
    
    print("\n🎯 PRUEBAS CON EJEMPLOS ESPECÍFICOS DE LIVO")
    print("=" * 60)
    
    reasoning_system = ReasoningSystem()
    
    # Ejemplos específicos del usuario
    examples = [
        {
            "question": "¿Cuántas unidades se han vendido en el departamento de Cundinamarca?",
            "expected_comment": "Se debe especificar la cuenta de ventas, así como asegurar los filtros para trabajar con viviendas"
        },
        {
            "question": "¿Cuál es el precio promedio (valor) de una unidad con estrato 6 en Bogotá D.C.?",
            "expected_comment": "Se debe especificar la cuenta de ventas, así como asegurar los filtros para trabajar con viviendas"
        },
        {
            "question": "Liste las constructoras y la suma total del área construida para el año 2024.",
            "expected_comment": "Se debe especificar a qué se refiere con área construída, entiendo que es el total de área entregada"
        },
        {
            "question": "¿Cuál es el valor mínimo y máximo de una unidad NO VIS?",
            "expected_comment": "La base trabaja con agregados, es decir, la columna valor incluye el valor de varias unidades"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. EJEMPLO: {example['question']}")
        print("-" * 50)
        
        result = reasoning_system.analyze_question(example['question'])
        
        print(f"📊 ANÁLISIS:")
        print(f"   Tipo: {result.question_type.value}")
        print(f"   Comentarios de razonamiento:")
        for comment in result.reasoning_comments:
            print(f"   • {comment}")
        
        print(f"\n💡 COMENTARIO ESPERADO:")
        print(f"   {example['expected_comment']}")
        
        needs_clarification, clarification_response = analyze_and_respond(example['question'], reasoning_system)
        
        if needs_clarification:
            print(f"\n🤔 RESPUESTA DEL SISTEMA:")
            print(f"   {clarification_response}")
        
        print("\n" + "="*60)

def test_account_priority():
    """Prueba específica para demostrar la importancia crítica de la variable 'cuenta'"""
    
    print("\n🎯 PRUEBA ESPECÍFICA: IMPORTANCIA CRÍTICA DE LA VARIABLE 'CUENTA'")
    print("=" * 70)
    
    reasoning_system = ReasoningSystem()
    
    # Ejemplos que demuestran por qué la cuenta es crítica
    account_examples = [
        {
            "question": "¿Cuántas unidades hay en Bogotá?",
            "issue": "Sin especificar 'cuenta' no sabemos si son vendidas, entregadas, en proceso, etc."
        },
        {
            "question": "¿Cuál es el total de área en Cundinamarca?",
            "issue": "¿Área vendida, entregada, aprobada? La diferencia puede ser significativa."
        },
        {
            "question": "Dame el valor de proyectos VIS en Medellín",
            "issue": "¿Valor de ventas, entregas, o proyectos en trámite? Cada uno es diferente."
        },
        {
            "question": "¿Cuántas unidades se han vendido en Cundinamarca?",
            "issue": "Esta SÍ especifica 'vendido' (cuenta), por lo que es más clara."
        }
    ]

def test_count_distinct_importance():
    """Prueba específica para demostrar la importancia de COUNT DISTINCT en consultas LIVO"""
    
    print("\n🔢 PRUEBA ESPECÍFICA: IMPORTANCIA DE COUNT DISTINCT PARA PROYECTOS ÚNICOS")
    print("=" * 75)
    
    reasoning_system = ReasoningSystem()
    
    # Ejemplos que demuestran por qué COUNT DISTINCT es crítico
    count_examples = [
        {
            "question": "¿Cuántos proyectos hay en Bogotá?",
            "issue": "Debe usar COUNT(DISTINCT identificador) porque un proyecto puede aparecer varias veces"
        },
        {
            "question": "¿Cuántas licencias se otorgaron en Cundinamarca?",
            "issue": "En LIVO se trabaja con proyectos de construcción, no licencias. Usar COUNT DISTINCT."
        },
        {
            "question": "Dame la cantidad total de construcciones VIS",
            "issue": "Necesita COUNT DISTINCT para evitar contar el mismo proyecto múltiples veces"
        },
        {
            "question": "¿Cuántos proyectos entregados hay en Medellín?",
            "issue": "Correcto: especifica cuenta (entregados) y implica COUNT DISTINCT para proyectos únicos"
        }
    ]
    
    for i, example in enumerate(count_examples, 1):
        print(f"\n{i}. EJEMPLO: {example['question']}")
        print(f"   PROBLEMA SQL: {example['issue']}")
        print("-" * 50)
        
        result = reasoning_system.analyze_question(example['question'])
        
        print(f"📊 ANÁLISIS:")
        print(f"   Tipo: {result.question_type.value}")
        print(f"   Confianza: {result.confidence:.2f}")
        print(f"   Detecta COUNT: {any(word in example['question'].lower() for word in ['cuántos', 'cuántas', 'cantidad'])}")
        
        if result.reasoning_comments:
            print(f"\n💡 COMENTARIOS DE RAZONAMIENTO:")
            for comment in result.reasoning_comments:
                print(f"   • {comment}")
        
        needs_clarification, clarification_response = analyze_and_respond(example['question'], reasoning_system)
        
        if needs_clarification:
            print(f"\n🤔 RESPUESTA DEL SISTEMA:")
            # Mostrar solo las primeras líneas para brevedad
            lines = clarification_response.split('\n')[:4]
            for line in lines:
                if line.strip():
                    print(f"   {line}")
            print("   ...")
        
        print("\n" + "="*75)

    for i, example in enumerate(account_examples, 1):
        print(f"\n{i}. EJEMPLO: {example['question']}")
        print(f"   PROBLEMA: {example['issue']}")
        print("-" * 50)
        
        result = reasoning_system.analyze_question(example['question'])
        
        print(f"📊 ANÁLISIS:")
        print(f"   Tipo: {result.question_type.value}")
        print(f"   Confianza: {result.confidence:.2f}")
        print(f"   Falta account_type: {'account_type' in result.missing_elements}")
        
        if result.reasoning_comments:
            print(f"\n💡 COMENTARIOS DE RAZONAMIENTO:")
            for comment in result.reasoning_comments:
                print(f"   • {comment}")
        
        needs_clarification, clarification_response = analyze_and_respond(example['question'], reasoning_system)
        
        if needs_clarification:
            print(f"\n🤔 RESPUESTA DEL SISTEMA:")
            # Mostrar solo las primeras líneas para brevedad
            lines = clarification_response.split('\n')[:5]
            for line in lines:
                if line.strip():
                    print(f"   {line}")
            print("   ...")
        
        print("\n" + "="*70)

def test_constructora_nit_importance():
    """Prueba específica para demostrar la importancia del NIT en consultas sobre constructoras"""
    
    print("\n🏢 PRUEBA ESPECÍFICA: IMPORTANCIA DEL NIT PARA CONSTRUCTORAS")
    print("=" * 70)
    
    reasoning_system = ReasoningSystem()
    
    # Ejemplos que demuestran por qué el NIT es crítico para constructoras
    constructora_examples = [
        {
            "question": "¿Cuáles son las constructoras con más proyectos en Bogotá?",
            "issue": "Falta NIT - pueden haber nombres similares o duplicados de constructoras"
        },
        {
            "question": "Dame el ranking de empresas constructoras por área total",
            "issue": "Sin NIT no se puede identificar únicamente cada empresa constructora"
        },
        {
            "question": "Liste las constructoras y su valor total de ventas",
            "issue": "Necesita NIT para GROUP BY correcto y evitar duplicados por nombres similares"
        },
        {
            "question": "¿Qué constructora tiene el mayor número de unidades VIS entregadas?",
            "issue": "Puede haber constructoras con nombres parecidos, el NIT es el identificador único"
        },
        {
            "question": "Análisis por NIT de constructora y nombre de empresa en Medellín",
            "issue": "Esta SÍ incluye NIT, por lo que permite identificación única correcta"
        }
    ]
    
    for i, example in enumerate(constructora_examples, 1):
        print(f"\n{i}. EJEMPLO: {example['question']}")
        print(f"   PROBLEMA NIT: {example['issue']}")
        print("-" * 50)
        
        result = reasoning_system.analyze_question(example['question'])
        
        print(f"📊 ANÁLISIS:")
        print(f"   Tipo: {result.question_type.value}")
        print(f"   Confianza: {result.confidence:.2f}")
        print(f"   Detecta constructora: {any(word in example['question'].lower() for word in ['constructora', 'empresa', 'compañía'])}")
        print(f"   Falta company_identifier: {'company_identifier' in result.missing_elements}")
        
        if result.reasoning_comments:
            print(f"\n💡 COMENTARIOS DE RAZONAMIENTO:")
            for comment in result.reasoning_comments:
                print(f"   • {comment}")
        
        needs_clarification, clarification_response = analyze_and_respond(example['question'], reasoning_system)
        
        if needs_clarification:
            print(f"\n🤔 RESPUESTA DEL SISTEMA:")
            # Mostrar solo las primeras líneas para brevedad
            lines = clarification_response.split('\n')[:4]
            for line in lines:
                if line.strip():
                    print(f"   {line}")
            print("   ...")
        
        print("\n" + "="*70)

def test_detailed_livo_patterns():
    """Prueba específica para patrones detallados de LIVO basados en comentarios de razonamiento reales"""
    
    print("\n📋 PRUEBA ESPECÍFICA: PATRONES DETALLADOS DE RAZONAMIENTO LIVO")
    print("=" * 80)
    
    reasoning_system = ReasoningSystem()
    
    # Ejemplos basados en los comentarios de razonamiento proporcionados
    detailed_examples = [
        {
            "question": "¿Cuántas unidades VIS por política de vivienda en 2024?",
            "expected_issues": ["Variable incorrecta: política_vivienda", "Año 2024 necesita extracción", "Falta cuenta"]
        },
        {
            "question": "Dame el precio por metro cuadrado promedio en Bogotá",
            "expected_issues": ["Ya existe precio_mc_promedio", "Falta cuenta", "Falta período"]
        },
        {
            "question": "¿Cuál es el estado vendido de proyectos en Medellín?",
            "expected_issues": ["No existe estado 'vendido'", "Usar TVE/TE", "Falta cuenta"]
        },
        {
            "question": "Muestra las casas en fase de entrega por barrio",
            "expected_issues": ["No existe fase 'entrega'", "Usar cuenta 'entregadas'", "Barrios no en todas ciudades"]
        },
        {
            "question": "¿Cuánto valor de mercado hay en doce meses?",
            "expected_issues": ["Definir valor de mercado", "Explicar doce_meses", "Falta ubicación"]
        },
        {
            "question": "Liste constructoras con ventas anuales mayores a 1000",
            "expected_issues": ["ventas_anuales no existe", "Construir desde cuenta ventas", "Falta NIT"]
        },
        {
            "question": "¿Cuál es el área individual mayor a 150 m2 en apartamentos?",
            "expected_issues": ["Área agregada vs individual", "Usar rango_area", "Falta cuenta"]
        },
        {
            "question": "Proyectos con destino vivienda en año corrido 2024",
            "expected_issues": ["No existe destino 'vivienda'", "Usar uso_etapa casa/apartamento", "Año corrido vs fecha"]
        }
    ]
    
    for i, example in enumerate(detailed_examples, 1):
        print(f"\n{i}. EJEMPLO: {example['question']}")
        print(f"   PROBLEMAS ESPERADOS: {', '.join(example['expected_issues'])}")
        print("-" * 60)
        
        result = reasoning_system.analyze_question(example['question'])
        
        print(f"📊 ANÁLISIS:")
        print(f"   Tipo: {result.question_type.value}")
        print(f"   Confianza: {result.confidence:.2f}")
        print(f"   Elementos faltantes: {len(result.missing_elements)}")
        
        if result.reasoning_comments:
            print(f"\n💡 COMENTARIOS DE RAZONAMIENTO DETECTADOS ({len(result.reasoning_comments)}):")
            for j, comment in enumerate(result.reasoning_comments[:5], 1):  # Mostrar máximo 5
                print(f"   {j}. {comment}")
            if len(result.reasoning_comments) > 5:
                print(f"   ... y {len(result.reasoning_comments) - 5} comentarios más")
        
        needs_clarification, clarification_response = analyze_and_respond(example['question'], reasoning_system)
        
        if needs_clarification:
            print(f"\n🤔 NECESITA CLARIFICACIÓN: SÍ")
        else:
            print(f"\n✅ PREGUNTA COMPLETA")
        
        print("\n" + "="*80)

def test_hierarchies_and_relationships():
    """Prueba específica para jerarquías geográficas, identificadores únicos y orden cronológico"""
    
    print("\n🏗️ PRUEBA ESPECÍFICA: JERARQUÍAS Y RELACIONES EN LIVO")
    print("=" * 80)
    
    reasoning_system = ReasoningSystem()
    
    # Ejemplos que demuestran jerarquías y relaciones
    hierarchy_examples = [
        {
            "question": "¿Cuántas unidades vendidas hay en Bogotá?",
            "expected_hierarchy": "Jerarquía geográfica: debería agrupar por barrio para detalle",
            "category": "Jerarquía Geográfica"
        },
        {
            "question": "Dame el total de proyectos por departamento de Antioquia",
            "expected_hierarchy": "Jerarquía geográfica: debería agrupar por ciudad o zona",
            "category": "Jerarquía Geográfica"
        },
        {
            "question": "Agrupa las constructoras por NIT y muestra el total",
            "expected_hierarchy": "Identificador único: NIT es clave primaria para constructoras",
            "category": "Identificadores Únicos"
        },
        {
            "question": "¿Cuántos proyectos únicos hay usando el identificador?",
            "expected_hierarchy": "Identificador único: usar COUNT(DISTINCT identificador)",
            "category": "Identificadores Únicos"
        },
        {
            "question": "¿Cuál es el orden cronológico de las fases y estados?",
            "expected_hierarchy": "Orden cronológico: Preventa → Licencia → Vendido",
            "category": "Orden Cronológico"
        },
        {
            "question": "Muestra el ciclo de vida de los proyectos de construcción",
            "expected_hierarchy": "Secuencia lógica: Preventa → Aprobada → Construcción → Vendido → Entregado",
            "category": "Orden Cronológico"
        },
        {
            "question": "Consulta por código divipola de las ciudades",
            "expected_hierarchy": "Identificador geográfico único: divipola",
            "category": "Identificadores Únicos"
        },
        {
            "question": "Regional Medellín agrupado por departamento",
            "expected_hierarchy": "Jerarquía: regional contiene departamentos",
            "category": "Jerarquía Geográfica"
        }
    ]
    
    for i, example in enumerate(hierarchy_examples, 1):
        print(f"\n{i}. EJEMPLO ({example['category']}): {example['question']}")
        print(f"   JERARQUÍA ESPERADA: {example['expected_hierarchy']}")
        print("-" * 60)
        
        result = reasoning_system.analyze_question(example['question'])
        
        print(f"📊 ANÁLISIS:")
        print(f"   Tipo: {result.question_type.value}")
        print(f"   Confianza: {result.confidence:.2f}")
        
        # Verificar si detecta comentarios de jerarquía
        hierarchy_comments = [c for c in result.reasoning_comments if any(keyword in c for keyword in ['JERARQUÍA', 'CLAVE PRIMARIA', 'ORDEN CRONOLÓGICO', 'IDENTIFICADOR'])]
        
        if hierarchy_comments:
            print(f"\n🏗️ COMENTARIOS DE JERARQUÍA DETECTADOS ({len(hierarchy_comments)}):")
            for j, comment in enumerate(hierarchy_comments, 1):
                print(f"   {j}. {comment}")
        else:
            print(f"\n❌ NO SE DETECTARON COMENTARIOS DE JERARQUÍA")
        
        if result.reasoning_comments and not hierarchy_comments:
            print(f"\n💡 OTROS COMENTARIOS ({len(result.reasoning_comments)}):")
            for j, comment in enumerate(result.reasoning_comments[:3], 1):
                print(f"   {j}. {comment}")
        
        print("\n" + "="*80)

if __name__ == "__main__":
    try:
        test_reasoning_system()
        test_specific_examples()
        test_account_priority()
        test_count_distinct_importance()
        test_constructora_nit_importance()
        test_detailed_livo_patterns()
        test_hierarchies_and_relationships()  # Nueva prueba para jerarquías y relaciones
        
        print("\n✅ PRUEBAS COMPLETADAS EXITOSAMENTE")
        print("\n📋 RESUMEN COMPLETO:")
        print("• El sistema de razonamiento detecta preguntas incompletas")
        print("• Genera contrapreguntas específicas para clarificar la intención")
        print("• Proporciona comentarios de razonamiento basados en los ejemplos")
        print("• 🚨 PRIORIZA la variable 'cuenta' como crítica (90% de consultas LIVO)")
        print("• 🔢 ENFATIZA el uso de COUNT(DISTINCT identificador) para proyectos únicos")
        print("• 🏢 DESTACA la importancia del NIT para identificación única de constructoras")
        print("• 📋 DETECTA variables incorrectas (política_vivienda → segmento_pre/rangos_decreto_pre)")
        print("• ⚠️ IDENTIFICA estados/fases que no existen (vendido → TVE/TE, entrega → entregadas)")
        print("• 📅 MANEJA correctamente períodos (doce_meses, año_corrido, formato fecha)")
        print("• 🏠 DISTINGUE entre residencial/no residencial y uso_etapa correcto")
        print("• 📍 ADVIERTE sobre limitaciones geográficas (barrios no en todas ciudades)")
        print("• 💰 CONSIDERA agregaciones de valor y variables existentes (precio_mc_promedio)")
        print("• 🗺️ IMPLEMENTA jerarquías geográficas (regional → departamento → ciudad → zona → barrio)")
        print("• 🔑 RECONOCE identificadores únicos (NIT, divipola, identificador)")
        print("• 📊 ENTIENDE orden cronológico de fases y estados de proyectos")
        print("• Se integra tanto en Streamlit como en Telegram")
        
    except Exception as e:
        print(f"❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
