#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test simplificado para verificar la nueva clasificación de vivienda por VALOR
"""

from reasoning_system import ReasoningSystem
from datetime import datetime

# Clase simplificada para salarios mínimos (sin dependencias)
class SalarioMinimoColombiano:
    """Manejo de salarios mínimos de Colombia por año"""
    
    SALARIOS_MINIMOS = {
        2020: 877803,
        2021: 908526,
        2022: 1000000,
        2023: 1160000,
        2024: 1300000,
        2025: 1423000,
        2026: 1550000
    }
    
    @classmethod
    def obtener_salario_minimo(cls, año: int) -> int:
        return cls.SALARIOS_MINIMOS.get(año, cls.SALARIOS_MINIMOS[2024])
    
    @classmethod
    def obtener_salario_actual(cls) -> int:
        año_actual = datetime.now().year
        return cls.obtener_salario_minimo(año_actual)
    
    @classmethod
    def calcular_rangos_vivienda(cls, año: int = None):
        if año is None:
            año = datetime.now().year
        
        salario_minimo = cls.obtener_salario_minimo(año)
        
        return {
            'VIP': {
                'min': 0,
                'max': salario_minimo * 90,
                'descripcion': 'Vivienda de Interés Prioritario (< 90 SMMLV)'
            },
            'VIS': {
                'min': salario_minimo * 90,
                'max': salario_minimo * 135,
                'descripcion': 'Vivienda de Interés Social (90 - 135 SMMLV)'
            },
            'NO_VIS': {
                'min': salario_minimo * 135,
                'max': float('inf'),
                'descripcion': 'Vivienda No VIS (> 135 SMMLV)'
            }
        }

def test_salarios_minimos():
    """Prueba la funcionalidad de salarios mínimos"""
    
    print("PRUEBA: SALARIOS MINIMOS Y RANGOS DE VIVIENDA")
    print("=" * 80)
    
    # Probar salarios por año
    años_prueba = [2023, 2024, 2025]
    
    for año in años_prueba:
        salario = SalarioMinimoColombiano.obtener_salario_minimo(año)
        print(f"Salario minimo {año}: ${salario:,}")
    
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
    
    return True

def generar_condiciones_sql(año=2025):
    """Genera las condiciones SQL para la nueva clasificación"""
    rangos = SalarioMinimoColombiano.calcular_rangos_vivienda(año)
    
    # Convertir a miles (como está en la base de datos)
    vip_max_miles = rangos['VIP']['max'] // 1000
    vis_min_miles = rangos['VIS']['min'] // 1000
    vis_max_miles = rangos['VIS']['max'] // 1000
    no_vis_min_miles = rangos['NO_VIS']['min'] // 1000
    
    return {
        'VIP': f"valor < {vip_max_miles}",
        'VIS': f"valor >= {vis_min_miles} AND valor < {vis_max_miles}",
        'NO_VIS': f"valor >= {no_vis_min_miles}"
    }

def test_deteccion_clasificacion():
    """Prueba que el sistema de razonamiento detecte la nueva clasificación"""
    
    print("\nPRUEBA: DETECCION DE NUEVA CLASIFICACION POR VALOR")
    print("=" * 80)
    
    reasoning_system = ReasoningSystem()
    
    # Casos de prueba
    test_cases = [
        {
            "pregunta": "¿Cuantas unidades VIP hay en Bogota?",
            "esperado": "Debe recomendar usar 'valor' en lugar de 'tipo_vivienda'",
            "tipo": "VIP"
        },
        {
            "pregunta": "Dame las construcciones VIS del ultimo año",
            "esperado": "Debe explicar nueva clasificacion por valor para VIS",
            "tipo": "VIS"
        },
        {
            "pregunta": "¿Que constructoras tienen mas proyectos No VIS?",
            "esperado": "Debe mostrar condicion SQL por valor para No VIS",
            "tipo": "NO_VIS"
        },
        {
            "pregunta": "Quiero filtrar por tipo_vivienda = 'VIS'",
            "esperado": "Debe advertir sobre cambio a clasificacion por valor",
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
            if any(keyword in clean_comment for keyword in ['valor', 'clasificacion', 'salario', 'vip', 'vis', 'no vis', 'cambio']):
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
    
    rangos_sql = generar_condiciones_sql(2025)
    salario_2025 = SalarioMinimoColombiano.obtener_salario_minimo(2025)
    
    print(f"Basado en salario minimo 2025: ${salario_2025:,}")
    print()
    
    ejemplos = [
        {
            "consulta": "Unidades VIP en Bogota",
            "sql_anterior": "WHERE tipo_vivienda = 'VIP' AND ciudad LIKE '%Bogota%'",
            "sql_nuevo": f"WHERE {rangos_sql['VIP']} AND ciudad LIKE '%Bogota%'"
        },
        {
            "consulta": "Constructoras con proyectos VIS",
            "sql_anterior": "WHERE tipo_vivienda = 'VIS'",
            "sql_nuevo": f"WHERE {rangos_sql['VIS']}"
        },
        {
            "consulta": "Area promedio No VIS por ciudad",
            "sql_anterior": "WHERE tipo_vivienda = 'No VIS'",
            "sql_nuevo": f"WHERE {rangos_sql['NO_VIS']}"
        }
    ]
    
    for i, ejemplo in enumerate(ejemplos, 1):
        print(f"{i}. CONSULTA: {ejemplo['consulta']}")
        print(f"   X METODO ANTERIOR: {ejemplo['sql_anterior']}")
        print(f"   V METODO NUEVO:    {ejemplo['sql_nuevo']}")
        print()

def main():
    """Función principal"""
    try:
        print("INICIANDO PRUEBAS DE CLASIFICACION POR VALOR")
        print("Implementando cambio de tipo_vivienda a clasificacion por valor")
        print("=" * 80)
        
        test_salarios_minimos()
        test_deteccion_clasificacion()
        test_ejemplos_sql()
        
        print("\nRESUMEN DEL CAMBIO IMPLEMENTADO:")
        print("=" * 80)
        print("ANTES (metodo anterior):")
        print("- Usar campo 'tipo_vivienda' con valores 'VIS', 'VIP', 'No VIS'")
        print("- Ejemplo: WHERE tipo_vivienda = 'VIS'")
        print()
        print("AHORA (metodo nuevo):")
        print("- Usar campo 'valor' con rangos basados en salarios minimos")
        print("- VIP: valor < 128,070 (< 90 SMMLV)")
        print("- VIS: valor >= 128,070 AND valor < 192,105 (90-135 SMMLV)")  
        print("- No VIS: valor >= 192,105 (> 135 SMMLV)")
        print()
        print("VENTAJAS:")
        print("V Clasificacion automatica basada en valor real")
        print("V Actualizacion automatica con salarios minimos anuales")
        print("V Mas preciso que categorias fijas")
        print("V Informacion estatica (no requiere LLM para salarios)")
        print()
        print("RECOMENDACION: Usar informacion ESTATICA para salarios minimos")
        print("- Mas confiable que consultar LLM")
        print("- Mas rapido en ejecucion")
        print("- Facil de actualizar anualmente")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
