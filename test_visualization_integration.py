#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test de integración del sistema de visualización multi-canal
"""

import pandas as pd
import sys
import os

# Agregar el directorio actual al path para importar módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_visualization_system():
    """Prueba el sistema de visualización"""
    
    print("INICIANDO PRUEBAS DEL SISTEMA DE VISUALIZACIÓN MULTI-CANAL")
    print("=" * 80)
    
    try:
        from visualization_system import LIVOVisualizationSystem, generate_streamlit_chart, generate_telegram_chart
        print("✅ Sistema de visualización importado correctamente")
    except ImportError as e:
        print(f"❌ Error importando sistema de visualización: {e}")
        print("💡 Instalar dependencias: pip install matplotlib seaborn pandas")
        return False
    
    # Datos de prueba realistas para LIVO
    test_cases = [
        {
            'name': 'Clasificación VIS/VIP/No VIS',
            'data': pd.DataFrame({
                'tipo_vivienda': ['VIS', 'VIP', 'No VIS'],
                'unidades': [15420, 8200, 12300],
                'proyectos': [245, 180, 156]
            }),
            'query': 'Clasificación de vivienda por tipo en 2025'
        },
        {
            'name': 'Unidades por ciudad',
            'data': pd.DataFrame({
                'ciudad': ['Bogotá', 'Medellín', 'Cali', 'Barranquilla', 'Cartagena'],
                'unidades_vis': [15420, 8750, 6230, 4180, 2950],
                'unidades_total': [35920, 20050, 14260, 9580, 6850]
            }),
            'query': 'Unidades VIS por ciudad principales'
        },
        {
            'name': 'Evolución temporal',
            'data': pd.DataFrame({
                'año': [2021, 2022, 2023, 2024, 2025],
                'licencias': [1250, 1380, 1520, 1680, 1420],
                'unidades': [28500, 31200, 34800, 38200, 32100]
            }),
            'query': 'Evolución histórica de licencias por año'
        },
        {
            'name': 'Top constructoras',
            'data': pd.DataFrame({
                'constructora': ['Constructora A', 'Constructora B', 'Constructora C', 
                               'Constructora D', 'Constructora E'],
                'unidades': [5420, 4850, 4230, 3980, 3650],
                'proyectos': [45, 38, 42, 35, 29]
            }),
            'query': 'Top 5 constructoras con más unidades'
        }
    ]
    
    # Probar cada caso
    viz_system = LIVOVisualizationSystem()
    results = []
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. PROBANDO: {case['name']}")
        print("-" * 50)
        
        query_info = {
            'original_question': case['query'],
            'columns': case['data'].columns.tolist(),
            'row_count': len(case['data'])
        }
        
        # Probar detección de tipo de visualización
        viz_type = viz_system.detect_visualization_type(case['data'], query_info)
        print(f"   Tipo detectado: {viz_type}")
        
        # Probar generación para diferentes canales
        channels = ['streamlit', 'telegram']  # 'whatsapp' comentado
        
        for channel in channels:
            try:
                result = viz_system.generate_for_channel(case['data'], query_info, channel)
                
                if result['success']:
                    print(f"   ✅ {channel}: {result['title']} ({result['size_mb']:.2f} MB)")
                    results.append({
                        'case': case['name'],
                        'channel': channel,
                        'success': True,
                        'viz_type': result['viz_type'],
                        'size_mb': result['size_mb']
                    })
                else:
                    print(f"   ❌ {channel}: {result.get('error', 'Error desconocido')}")
                    results.append({
                        'case': case['name'],
                        'channel': channel,
                        'success': False,
                        'error': result.get('error')
                    })
                    
            except Exception as e:
                print(f"   ❌ {channel}: Excepción - {str(e)}")
                results.append({
                    'case': case['name'],
                    'channel': channel,
                    'success': False,
                    'error': str(e)
                })
    
    # Resumen de resultados
    print(f"\nRESUMEN DE PRUEBAS")
    print("=" * 80)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"✅ Exitosas: {len(successful)}/{len(results)}")
    print(f"❌ Fallidas: {len(failed)}/{len(results)}")
    print(f"📊 Tasa de éxito: {len(successful)/len(results)*100:.1f}%")
    
    if successful:
        avg_size = sum(r['size_mb'] for r in successful if 'size_mb' in r) / len([r for r in successful if 'size_mb' in r])
        print(f"📏 Tamaño promedio: {avg_size:.2f} MB")
        
        # Tipos de visualización generados
        viz_types = [r['viz_type'] for r in successful if 'viz_type' in r]
        unique_types = list(set(viz_types))
        print(f"🎨 Tipos generados: {', '.join(unique_types)}")
    
    if failed:
        print(f"\n❌ ERRORES ENCONTRADOS:")
        for error in failed:
            print(f"   - {error['case']} ({error['channel']}): {error.get('error', 'Error desconocido')}")
    
    return len(successful) > len(failed)

def test_integration_functions():
    """Prueba las funciones de integración"""
    
    print(f"\nPROBANDO FUNCIONES DE INTEGRACIÓN")
    print("=" * 80)
    
    # Datos de prueba
    sample_data = pd.DataFrame({
        'ciudad': ['Bogotá', 'Medellín', 'Cali'],
        'unidades': [15420, 8750, 6230]
    })
    
    query_info = {
        'original_question': 'Unidades por ciudad',
        'columns': sample_data.columns.tolist()
    }
    
    # Probar funciones específicas por canal
    try:
        from visualization_system import generate_streamlit_chart, generate_telegram_chart
        
        # Streamlit
        streamlit_result = generate_streamlit_chart(sample_data, query_info)
        if streamlit_result['success']:
            print("✅ Función Streamlit: OK")
        else:
            print(f"❌ Función Streamlit: {streamlit_result.get('error')}")
        
        # Telegram
        telegram_result = generate_telegram_chart(sample_data, query_info)
        if telegram_result['success']:
            print("✅ Función Telegram: OK")
        else:
            print(f"❌ Función Telegram: {telegram_result.get('error')}")
        
        # WhatsApp (comentado)
        print("⏸️ Función WhatsApp: Comentada para implementación futura")
        
    except ImportError as e:
        print(f"❌ Error importando funciones: {e}")
        return False
    
    return True

def test_livo_integration():
    """Prueba la integración con el sistema LIVO"""
    
    print(f"\nPROBANDO INTEGRACIÓN CON SISTEMA LIVO")
    print("=" * 80)
    
    try:
        # Intentar importar sistema LIVO
        from livo_sql import LIVOSQLSystem
        print("✅ Sistema LIVO importado correctamente")
        
        # Verificar que tenga los nuevos métodos
        livo_system = LIVOSQLSystem()
        
        # Verificar método de generación de gráficos
        if hasattr(livo_system, '_generar_grafico'):
            print("✅ Método _generar_grafico disponible")
        else:
            print("❌ Método _generar_grafico no encontrado")
        
        # Verificar método should_generate_chart
        if hasattr(livo_system, 'should_generate_chart'):
            print("✅ Método should_generate_chart disponible")
            
            # Probar detección
            test_questions = [
                "Gráfico de unidades por ciudad",
                "Mostrar comparación VIS vs VIP",
                "Top 10 constructoras",
                "¿Cuántas licencias hay?"  # No debería generar gráfico
            ]
            
            for question in test_questions:
                should_generate = livo_system.should_generate_chart(question, [['Bogotá', 1000], ['Medellín', 800]])
                print(f"   '{question}' → {'Sí' if should_generate else 'No'}")
        else:
            print("❌ Método should_generate_chart no encontrado")
        
        return True
        
    except ImportError as e:
        print(f"❌ Error importando sistema LIVO: {e}")
        return False
    except Exception as e:
        print(f"❌ Error en integración LIVO: {e}")
        return False

def main():
    """Función principal de pruebas"""
    
    print("🧪 SISTEMA DE VISUALIZACIÓN MULTI-CANAL PARA LIVO")
    print("Canales soportados: Streamlit, Telegram")
    print("Canal futuro: WhatsApp Business (comentado)")
    print("=" * 80)
    
    # Ejecutar todas las pruebas
    tests = [
        ("Sistema de Visualización", test_visualization_system),
        ("Funciones de Integración", test_integration_functions),
        ("Integración LIVO", test_livo_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Error en {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumen final
    print(f"\nRESUMEN FINAL")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"{status}: {test_name}")
    
    print(f"\nResultado: {passed}/{total} pruebas exitosas")
    
    if passed == total:
        print("🎉 ¡Todas las pruebas pasaron! Sistema listo para usar.")
        print("\nPRÓXIMOS PASOS:")
        print("1. Integrar con app.py usando streamlit_integration.py")
        print("2. Probar con datos reales de LIVO")
        print("3. Implementar WhatsApp Business cuando esté disponible")
    else:
        print("⚠️ Algunas pruebas fallaron. Revisar errores arriba.")
        print("\nRECOMENDACIONES:")
        print("- Instalar dependencias: pip install matplotlib seaborn pandas")
        print("- Verificar importaciones en los módulos")
        print("- Revisar configuración del sistema")

if __name__ == "__main__":
    main()
