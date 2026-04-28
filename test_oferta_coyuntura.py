"""
Tests para el sistema de coyuntura de oferta LIVO.

Este archivo contiene pruebas unitarias para verificar el correcto funcionamiento
del sistema de datos pre-cargados de oferta del mercado de vivienda.
"""

import unittest
from datetime import datetime
import sys
import os

# Agregar el directorio actual al path para importar los módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from oferta_coyuntura import OfertaCoyunturaSystem, OfertaMensual, oferta_coyuntura
except ImportError as e:
    print(f"Error importando oferta_coyuntura: {e}")
    oferta_coyuntura = None

class TestOfertaCoyunturaSystem(unittest.TestCase):
    """Pruebas para el sistema de coyuntura de oferta."""
    
    def setUp(self):
        """Configuración inicial para cada test."""
        if oferta_coyuntura is None:
            self.skipTest("Sistema de oferta no disponible")
        self.sistema = oferta_coyuntura
    
    def test_inicializacion_sistema(self):
        """Test: Verificar que el sistema se inicializa correctamente."""
        self.assertIsNotNone(self.sistema)
        self.assertIsInstance(self.sistema, OfertaCoyunturaSystem)
        self.assertTrue(len(self.sistema.datos_historicos) > 0)
        self.assertEqual(len(self.sistema.departamentos), 19)
        
    def test_estructura_datos_historicos(self):
        """Test: Verificar estructura de datos históricos."""
        # Verificar que hay datos
        self.assertTrue(len(self.sistema.datos_historicos) > 0)
        
        # Verificar estructura de primer registro
        primer_dato = self.sistema.datos_historicos[0]
        self.assertIsInstance(primer_dato, OfertaMensual)
        self.assertIsInstance(primer_dato.fecha, str)
        self.assertIsInstance(primer_dato.departamento, str)
        self.assertIsInstance(primer_dato.vip, int)
        self.assertIsInstance(primer_dato.vis_total, int)
        self.assertIsInstance(primer_dato.no_vis, int)
        self.assertIsInstance(primer_dato.total, int)
        
        # Verificar coherencia de datos
        for dato in self.sistema.datos_historicos[:10]:  # Verificar primeros 10
            self.assertGreaterEqual(dato.total, 0)
            self.assertGreaterEqual(dato.vip, 0)
            self.assertGreaterEqual(dato.vis_total, 0)
            self.assertGreaterEqual(dato.no_vis, 0)
            # El total debe ser la suma de VIS + NO VIS (aproximadamente)
            suma_componentes = dato.vis_total + dato.no_vis
            self.assertAlmostEqual(dato.total, suma_componentes, delta=100)
    
    def test_departamentos_validos(self):
        """Test: Verificar que todos los departamentos son válidos."""
        departamentos_esperados = [
            'Antioquia', 'Atlántico', 'Bogotá & Cundinamarca', 'Bolívar', 'Boyacá',
            'Caldas', 'Huila', 'Nariño', 'Norte de Santander', 'Risaralda',
            'Santander', 'Tolima', 'Valle', 'Cesar', 'Meta', 'Córdoba & Sucre',
            'Magdalena', 'Quindío', 'Cauca'
        ]
        
        self.assertEqual(set(self.sistema.departamentos), set(departamentos_esperados))
        
        # Verificar que todos los departamentos en datos están en la lista
        departamentos_en_datos = set(d.departamento for d in self.sistema.datos_historicos)
        self.assertTrue(departamentos_en_datos.issubset(set(departamentos_esperados)))
    
    def test_agregaciones_regionales(self):
        """Test: Verificar agregaciones regionales."""
        agregaciones = self.sistema.agregaciones_regionales
        
        self.assertIn('5_regionales', agregaciones)
        self.assertIn('13_regionales', agregaciones)
        self.assertIn('18_regionales', agregaciones)
        self.assertIn('19_regionales', agregaciones)
        
        # Verificar tamaños
        self.assertEqual(len(agregaciones['5_regionales']), 5)
        self.assertEqual(len(agregaciones['13_regionales']), 13)
        self.assertEqual(len(agregaciones['18_regionales']), 18)
        self.assertEqual(len(agregaciones['19_regionales']), 19)
    
    def test_obtener_contexto_periodo_completo(self):
        """Test: Obtener contexto para período completo."""
        contexto = self.sistema.obtener_contexto_periodo()
        
        self.assertIsInstance(contexto, dict)
        self.assertIn('periodo', contexto)
        self.assertIn('totales', contexto)
        self.assertIn('distribucion', contexto)
        self.assertIn('top_departamentos', contexto)
        self.assertIn('promedio_mensual', contexto)
        
        # Verificar totales
        totales = contexto['totales']
        self.assertGreater(totales['oferta'], 0)
        self.assertGreater(totales['vis'], 0)
        self.assertGreater(totales['no_vis'], 0)
        
        # Verificar distribución
        distribucion = contexto['distribucion']
        self.assertIn('VIS', distribucion)
        self.assertIn('NO_VIS', distribucion)
        self.assertIn('VIP', distribucion)
        
        # Los porcentajes deben sumar aproximadamente 100%
        total_porcentaje = (distribucion['VIS']['porcentaje'] + 
                          distribucion['NO_VIS']['porcentaje'] + 
                          distribucion['VIP']['porcentaje'])
        self.assertAlmostEqual(total_porcentaje, 100.0, delta=1.0)
    
    def test_obtener_contexto_periodo_filtrado(self):
        """Test: Obtener contexto para período específico."""
        contexto = self.sistema.obtener_contexto_periodo('oct-25', 'oct-25')
        
        self.assertIsInstance(contexto, dict)
        self.assertIn('periodo', contexto)
        
        # Debe tener datos solo para octubre 2025
        periodo = contexto['periodo']
        self.assertEqual(periodo['inicio'], 'oct-25')
        self.assertEqual(periodo['fin'], 'oct-25')
    
    def test_obtener_tendencia_reciente(self):
        """Test: Obtener tendencias recientes."""
        tendencias = self.sistema.obtener_tendencia_reciente(6)
        
        self.assertIsInstance(tendencias, dict)
        self.assertIn('periodo_analizado', tendencias)
        self.assertIn('tendencias_mensuales', tendencias)
        self.assertIn('variacion_mensual', tendencias)
        
        # Verificar período analizado
        periodo = tendencias['periodo_analizado']
        self.assertLessEqual(periodo['meses'], 6)
        self.assertIsNotNone(periodo['desde'])
        self.assertIsNotNone(periodo['hasta'])
        
        # Verificar tendencias mensuales
        tendencias_mensuales = tendencias['tendencias_mensuales']
        self.assertIsInstance(tendencias_mensuales, dict)
        self.assertGreater(len(tendencias_mensuales), 0)
        
        # Verificar estructura de cada mes
        for fecha, datos in tendencias_mensuales.items():
            self.assertIn('total', datos)
            self.assertIn('vip', datos)
            self.assertIn('vis', datos)
            self.assertIn('no_vis', datos)
            self.assertIn('vip_pct', datos)
            self.assertIn('vis_pct', datos)
            self.assertIn('no_vis_pct', datos)
    
    def test_obtener_comparacion_departamental(self):
        """Test: Obtener comparación departamental."""
        comparacion = self.sistema.obtener_comparacion_departamental(10)
        
        self.assertIsInstance(comparacion, dict)
        self.assertIn('ranking_total', comparacion)
        self.assertIn('ranking_vis', comparacion)
        self.assertIn('ranking_no_vis', comparacion)
        self.assertIn('estadisticas_completas', comparacion)
        self.assertIn('total_nacional', comparacion)
        
        # Verificar rankings
        ranking_total = comparacion['ranking_total']
        self.assertLessEqual(len(ranking_total), 10)
        self.assertGreater(len(ranking_total), 0)
        
        # Verificar que está ordenado descendentemente
        for i in range(len(ranking_total) - 1):
            self.assertGreaterEqual(
                ranking_total[i][1]['total_oferta'], 
                ranking_total[i+1][1]['total_oferta']
            )
        
        # Verificar estadísticas completas
        stats_completas = comparacion['estadisticas_completas']
        self.assertIsInstance(stats_completas, dict)
        
        for depto, stats in stats_completas.items():
            self.assertIn('total_oferta', stats)
            self.assertIn('vip', stats)
            self.assertIn('vis', stats)
            self.assertIn('no_vis', stats)
            self.assertIn('vip_pct', stats)
            self.assertIn('vis_pct', stats)
            self.assertIn('no_vis_pct', stats)
    
    def test_generar_contexto_consulta_tendencias(self):
        """Test: Generar contexto para consultas de tendencias."""
        consulta = "¿Cuáles son las tendencias recientes de oferta en 2025?"
        contexto = self.sistema.generar_contexto_consulta(consulta)
        
        self.assertIsInstance(contexto, str)
        if contexto:  # Si hay contexto generado
            self.assertIn('CONTEXTO OFERTA', contexto.upper())
    
    def test_generar_contexto_consulta_departamental(self):
        """Test: Generar contexto para consultas departamentales."""
        consulta = "¿Cómo está la oferta en Antioquia?"
        contexto = self.sistema.generar_contexto_consulta(consulta)
        
        self.assertIsInstance(contexto, str)
        if contexto:  # Si hay contexto generado
            self.assertIn('ANTIOQUIA', contexto.upper())
    
    def test_generar_contexto_consulta_clasificacion(self):
        """Test: Generar contexto para consultas de clasificación."""
        consulta = "¿Cuál es la distribución VIS y No VIS de la oferta?"
        contexto = self.sistema.generar_contexto_consulta(consulta)
        
        self.assertIsInstance(contexto, str)
        if contexto:  # Si hay contexto generado
            self.assertIn('VIS', contexto.upper())
    
    def test_generar_contexto_consulta_ranking(self):
        """Test: Generar contexto para consultas de ranking."""
        consulta = "¿Cuáles son los departamentos con mayor oferta?"
        contexto = self.sistema.generar_contexto_consulta(consulta)
        
        self.assertIsInstance(contexto, str)
        if contexto:  # Si hay contexto generado
            self.assertIn('RANKING', contexto.upper())
    
    def test_obtener_estadisticas_generales(self):
        """Test: Obtener estadísticas generales del sistema."""
        stats = self.sistema.obtener_estadisticas_generales()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_registros', stats)
        self.assertIn('periodo_cobertura', stats)
        self.assertIn('departamentos_cubiertos', stats)
        self.assertIn('total_oferta_historica', stats)
        self.assertIn('agregaciones_disponibles', stats)
        
        # Verificar valores
        self.assertGreater(stats['total_registros'], 0)
        self.assertEqual(stats['departamentos_cubiertos'], 19)
        self.assertGreater(stats['total_oferta_historica'], 0)
        
        # Verificar período de cobertura
        periodo = stats['periodo_cobertura']
        self.assertIn('desde', periodo)
        self.assertIn('hasta', periodo)
        self.assertIn('meses_totales', periodo)
        self.assertIsNotNone(periodo['desde'])
        self.assertIsNotNone(periodo['hasta'])
        self.assertGreater(periodo['meses_totales'], 0)
    
    def test_coherencia_datos_totales(self):
        """Test: Verificar coherencia en los datos totales."""
        # Obtener estadísticas generales
        stats = self.sistema.obtener_estadisticas_generales()
        
        # Calcular total manual
        total_manual = sum(d.total for d in self.sistema.datos_historicos)
        
        # Debe coincidir con el total reportado
        self.assertEqual(stats['total_oferta_historica'], total_manual)
    
    def test_fechas_validas(self):
        """Test: Verificar que todas las fechas son válidas."""
        fechas_encontradas = set()
        
        for dato in self.sistema.datos_historicos:
            fecha = dato.fecha
            fechas_encontradas.add(fecha)
            
            # Verificar formato de fecha (mmm-yy)
            self.assertRegex(fecha, r'^[a-z]{3}-\d{2}$')
            
            # Verificar que el mes es válido
            mes = fecha[:3]
            meses_validos = ['ene', 'feb', 'mar', 'abr', 'may', 'jun',
                           'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
            self.assertIn(mes, meses_validos)
        
        # Debe haber múltiples fechas
        self.assertGreater(len(fechas_encontradas), 1)
    
    def test_cobertura_departamental(self):
        """Test: Verificar cobertura departamental en los datos."""
        # Obtener departamentos con datos
        departamentos_con_datos = set(d.departamento for d in self.sistema.datos_historicos)
        
        # Debe haber datos para múltiples departamentos
        self.assertGreater(len(departamentos_con_datos), 1)
        
        # Los departamentos principales deben tener datos
        departamentos_principales = ['Antioquia', 'Atlántico', 'Bogotá & Cundinamarca', 'Valle']
        for depto in departamentos_principales:
            self.assertIn(depto, departamentos_con_datos)

class TestIntegracionOfertaCoyuntura(unittest.TestCase):
    """Pruebas de integración para el sistema de oferta."""
    
    def setUp(self):
        """Configuración inicial."""
        if oferta_coyuntura is None:
            self.skipTest("Sistema de oferta no disponible")
        self.sistema = oferta_coyuntura
    
    def test_flujo_completo_analisis(self):
        """Test: Flujo completo de análisis de oferta."""
        # 1. Obtener estadísticas generales
        stats = self.sistema.obtener_estadisticas_generales()
        self.assertIsInstance(stats, dict)
        
        # 2. Obtener tendencias recientes
        tendencias = self.sistema.obtener_tendencia_reciente(3)
        self.assertIsInstance(tendencias, dict)
        
        # 3. Obtener comparación departamental
        comparacion = self.sistema.obtener_comparacion_departamental(5)
        self.assertIsInstance(comparacion, dict)
        
        # 4. Generar contexto para consulta
        contexto = self.sistema.generar_contexto_consulta("¿Cómo está la oferta en Colombia?")
        self.assertIsInstance(contexto, str)
        
        # Todo debe funcionar sin errores
        self.assertTrue(True)
    
    def test_consistencia_entre_metodos(self):
        """Test: Verificar consistencia entre diferentes métodos."""
        # Obtener datos de diferentes métodos
        stats_generales = self.sistema.obtener_estadisticas_generales()
        contexto_completo = self.sistema.obtener_contexto_periodo()
        comparacion = self.sistema.obtener_comparacion_departamental()
        
        # El total debe ser consistente
        total_stats = stats_generales['total_oferta_historica']
        total_contexto = contexto_completo['totales']['oferta']
        total_comparacion = comparacion['total_nacional']
        
        self.assertEqual(total_stats, total_contexto)
        self.assertEqual(total_stats, total_comparacion)

def run_tests():
    """Ejecutar todas las pruebas."""
    print("🧪 Ejecutando pruebas del sistema de coyuntura de oferta...")
    
    # Crear suite de pruebas
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Agregar pruebas
    suite.addTests(loader.loadTestsFromTestCase(TestOfertaCoyunturaSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegracionOfertaCoyuntura))
    
    # Ejecutar pruebas
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Resumen
    print(f"\n📊 Resumen de pruebas:")
    print(f"✅ Exitosas: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ Fallidas: {len(result.failures)}")
    print(f"🚨 Errores: {len(result.errors)}")
    
    if result.failures:
        print(f"\n❌ Pruebas fallidas:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError: ')[-1].split('\\n')[0]}")
    
    if result.errors:
        print(f"\n🚨 Errores:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('\\n')[-2]}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
