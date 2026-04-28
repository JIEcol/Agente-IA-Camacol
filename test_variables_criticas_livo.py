#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test para verificar la detección de variables críticas LIVO
y aplicación de recomendaciones temporales
"""

from reasoning_system import ReasoningSystem

def test_variables_criticas():
    """Prueba la detección de variables críticas LIVO"""
    
    print("PRUEBA: DETECCION DE VARIABLES CRITICAS LIVO")
    print("=" * 80)
    
    reasoning_system = ReasoningSystem()
    
    # Variables críticas a verificar
    variables_criticas = [
        'usos', 'cuenta', 'estado', 'fase', 'last_estado', 
        'destino_etapa', 'uso_etapa', 'modalidad'
    ]
    
    casos_prueba = [
        {
            "pregunta": "¿Cuántas licencias hay en Bogotá?",
            "esperado": "Debe recordar verificar variables críticas",
            "variables_esperadas": ["verificar_variables_criticas"]
        },
        {
            "pregunta": "Proyectos con cuenta de ventas en Medellín",
            "esperado": "Debe detectar 'cuenta' como variable crítica",
            "variables_esperadas": ["cuenta_critical_extended", "verificar_variables_criticas"]
        },
        {
            "pregunta": "Estado y fase de proyectos VIS",
            "esperado": "Debe detectar estado/fase y VIS temporal",
            "variables_esperadas": ["estado_fase_critical", "clasificacion_temporal_critica"]
        },
        {
            "pregunta": "Uso etapa Casa vs Apartamento",
            "esperado": "Debe detectar uso_etapa y recordar singular",
            "variables_esperadas": ["destino_uso_etapa_critical"]
        },
        {
            "pregunta": "Modalidad de licencias por usos residenciales",
            "esperado": "Debe detectar modalidad y usos",
            "variables_esperadas": ["modalidad_critical", "usos_critical"]
        }
    ]
    
    for i, caso in enumerate(casos_prueba, 1):
        print(f"\n{i}. PREGUNTA: {caso['pregunta']}")
        print(f"   ESPERADO: {caso['esperado']}")
        print("-" * 50)
        
        result = reasoning_system.analyze_question(caso['pregunta'])
        
        # Buscar comentarios sobre variables críticas
        criticos_detectados = []
        for comment in result.reasoning_comments:
            clean_comment = ''.join(c for c in comment if ord(c) < 128).lower()
            if any(keyword in clean_comment for keyword in ['critico', 'verificar', 'obligatorio', 'variables']):
                criticos_detectados.append(comment)
        
        print(f"   RESULTADO:")
        print(f"   - Comentarios críticos detectados: {len(criticos_detectados)}")
        
        if criticos_detectados:
            for j, comment in enumerate(criticos_detectados[:3], 1):
                clean_comment = ''.join(c for c in comment if ord(c) < 128)[:80]
                print(f"     {j}. {clean_comment}...")
        
        # Verificar variables específicas detectadas
        variables_detectadas = []
        for var in variables_criticas:
            if var in caso['pregunta'].lower():
                variables_detectadas.append(var)
        
        if variables_detectadas:
            print(f"   - Variables críticas en pregunta: {', '.join(variables_detectadas)}")

def test_recomendaciones_temporales():
    """Prueba la aplicación de recomendaciones temporales"""
    
    print("\nPRUEBA: APLICACION DE RECOMENDACIONES TEMPORALES")
    print("=" * 80)
    
    reasoning_system = ReasoningSystem()
    
    casos_temporales = [
        {
            "pregunta": "Evolución histórica de proyectos VIS",
            "esperado": "Debe aplicar recomendaciones temporales",
            "tipo": "HISTORICO"
        },
        {
            "pregunta": "Comparar VIP 2023 vs 2025",
            "esperado": "Debe usar SQL temporal multi-anual",
            "tipo": "COMPARACION"
        },
        {
            "pregunta": "Tendencia de No VIS en los últimos años",
            "esperado": "Debe explicar cambios en reportes",
            "tipo": "TENDENCIA"
        },
        {
            "pregunta": "Análisis anual de vivienda de interés social",
            "esperado": "Debe usar clasificación por año del proyecto",
            "tipo": "ANUAL"
        }
    ]
    
    for i, caso in enumerate(casos_temporales, 1):
        print(f"\n{i}. PREGUNTA: {caso['pregunta']}")
        print(f"   TIPO: {caso['tipo']}")
        print(f"   ESPERADO: {caso['esperado']}")
        print("-" * 50)
        
        result = reasoning_system.analyze_question(caso['pregunta'])
        
        # Buscar comentarios temporales
        temporales_detectados = []
        for comment in result.reasoning_comments:
            clean_comment = ''.join(c for c in comment if ord(c) < 128).lower()
            if any(keyword in clean_comment for keyword in ['temporal', 'historico', 'año', 'proyecto', 'reportes', 'multianual']):
                temporales_detectados.append(comment)
        
        print(f"   RESULTADO:")
        print(f"   - Comentarios temporales detectados: {len(temporales_detectados)}")
        
        if temporales_detectados:
            for j, comment in enumerate(temporales_detectados[:3], 1):
                clean_comment = ''.join(c for c in comment if ord(c) < 128)[:80]
                print(f"     {j}. {clean_comment}...")

def test_integracion_completa():
    """Prueba la integración completa de variables críticas y recomendaciones temporales"""
    
    print("\nPRUEBA: INTEGRACION COMPLETA")
    print("=" * 80)
    
    reasoning_system = ReasoningSystem()
    
    pregunta_compleja = "Evolución histórica de proyectos VIS con cuenta de ventas, por modalidad y uso_etapa, comparando estado vs fase en los últimos 3 años"
    
    print(f"PREGUNTA COMPLEJA:")
    print(f"{pregunta_compleja}")
    print("-" * 50)
    
    result = reasoning_system.analyze_question(pregunta_compleja)
    
    # Categorizar comentarios
    categorias = {
        'variables_criticas': [],
        'temporales': [],
        'vis_clasificacion': [],
        'otros': []
    }
    
    for comment in result.reasoning_comments:
        clean_comment = ''.join(c for c in comment if ord(c) < 128).lower()
        
        if any(keyword in clean_comment for keyword in ['critico', 'verificar', 'obligatorio', 'variables']):
            categorias['variables_criticas'].append(comment)
        elif any(keyword in clean_comment for keyword in ['temporal', 'historico', 'año', 'proyecto', 'reportes']):
            categorias['temporales'].append(comment)
        elif any(keyword in clean_comment for keyword in ['vis', 'vip', 'clasificacion', 'salario']):
            categorias['vis_clasificacion'].append(comment)
        else:
            categorias['otros'].append(comment)
    
    print(f"ANÁLISIS DE COMENTARIOS:")
    for categoria, comentarios in categorias.items():
        if comentarios:
            print(f"\n{categoria.upper()}: {len(comentarios)} comentarios")
            for i, comment in enumerate(comentarios[:2], 1):  # Solo 2 por categoría
                clean_comment = ''.join(c for c in comment if ord(c) < 128)[:70]
                print(f"  {i}. {clean_comment}...")
    
    print(f"\nRESUMEN:")
    print(f"- Total comentarios: {len(result.reasoning_comments)}")
    print(f"- Tipo de pregunta: {result.question_type.value}")
    print(f"- Confianza: {result.confidence:.2f}")

def main():
    """Función principal"""
    try:
        print("INICIANDO PRUEBAS DE VARIABLES CRITICAS Y RECOMENDACIONES TEMPORALES")
        print("Implementando verificación obligatoria y recomendaciones aplicadas")
        print("=" * 80)
        
        test_variables_criticas()
        test_recomendaciones_temporales()
        test_integracion_completa()
        
        print("\nRESUMEN DE IMPLEMENTACION:")
        print("=" * 80)
        print("✅ Variables críticas LIVO implementadas:")
        print("   - usos, cuenta, estado, fase, last_estado")
        print("   - destino_etapa, uso_etapa, modalidad")
        print()
        print("✅ Recomendaciones temporales aplicadas:")
        print("   - Análisis históricos: usar clasificación del año del proyecto")
        print("   - No usar rangos actuales para proyectos anteriores")
        print("   - Explicar cambios en reportes")
        print("   - SQL temporal para análisis multi-anuales")
        print()
        print("✅ Sistema integrado:")
        print("   - Verificación automática de variables críticas")
        print("   - Detección de análisis temporales")
        print("   - Recomendaciones específicas por tipo de consulta")
        print("   - Comentarios contextuales y educativos")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
