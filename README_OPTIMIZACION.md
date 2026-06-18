# Optimización de Rendimiento y Control de Timeouts

## Objetivo

Resolver el problema de timeouts de 350 segundos en preguntas sencillas mediante la implementación de:
- Control de timeouts específicos por componente
- Límite máximo de 3 reintentos
- Logging detallado de rendimiento
- Tracking completo en Excel de benchmark

## Archivos Creados

### 1. `llm_providers_optimized.py`
**Mejoras implementadas:**
- ✅ Timeout específico por proveedor (30s base, 60s Ollama, 120s Groq)
- ✅ Máximo 3 reintentos con backoff exponencial
- ✅ Logging detallado de cada llamada
- ✅ Performance tracking para Excel
- ✅ Manejo de errores específicos

**Columnas en Excel:**
- `proveedor`: Nombre del proveedor LLM
- `componente`: Tipo de operación (generación, validación, corrección)
- `total_llamadas`: Número total de llamadas
- `llamadas_exitosas`: Llamadas que completaron exitosamente
- `llamadas_fallidas`: Llamadas que fallaron
- `tiempo_promedio`: Tiempo promedio de respuesta
- `reintentos_totales`: Total de reintentos realizados
- `timeout_configurado`: Timeout configurado para el componente
- `logging_detalles`: Log detallado de errores y métricas

### 2. `livo_sql_optimized.py`
**Mejoras implementadas:**
- ✅ Timeout específico por componente (30s generación, 15s validación)
- ✅ Máximo 3 reintentos por operación
- ✅ Tracking de rendimiento por componente
- ✅ Pipeline completo: generación → validación → corrección → regeneración
- ✅ Logging estructurado de errores

**Componentes trackeados:**
- `generacion_sql`: Generación inicial de SQL
- `validacion_sql`: Validación de sintaxis y coherencia
- `correccion_sql`: Aplicación de correcciones automáticas
- `revalidacion_sql`: Re-validación post-corrección
- `ejecucion_sql`: Ejecución final del query

### 3. `app_optimized.py`
**Mejoras implementadas:**
- ✅ Timeout general de aplicación (350s)
- ✅ Timeout por componente (60s)
- ✅ Tracking de rendimiento de sesión
- ✅ Sidebar con métricas en tiempo real
- ✅ Exportación automática a Excel
- ✅ Interfaz optimizada con logging

## Configuración de Timeouts

### Timeouts por Componente

| Componente | Timeout (segundos) | Reintentos Máximos |
|-------------|-------------------|-------------------|
| LLM Generación | 350 | 3 |
| LLM Validación | 350 | 3 |
| LLM Corrección | 350 | 3 |
| Ollama | 350 | 3 |
| Groq | 350 | 3 |
| DeepSeek | 350 | 3 |
| OpenAI | 350 | 3 |
| Gemini | 350 | 3 |
| Mistral | 350 | 3 |
| SQL Generación | 350 | 3 |
| SQL Validación | 350 | 3 |
| SQL Corrección | 350 | 3 |
| SQL Ejecución | 350 | 1 |
| App General | 350 | - |

## Estructura de Excel de Benchmark

### Columnas Principales

```
pregunta | proveedor_llm | tiempo_generacion | reintentos_generacion | timeout_generacion | logging_generacion | tiempo_validacion | reintentos_validacion | timeout_validacion | logging_validacion | tiempo_correccion | reintentos_correccion | timeout_correccion | logging_correccion | tiempo_total | exito | errores
```

### Columnas de Componentes

Para cada componente (generación, validación, corrección, etc.):
- `tiempo_[componente]`: Tiempo de ejecución
- `reintentos_[componente]`: Número de reintentos
- `timeout_[componente]`: Timeout configurado
- `logging_[componente]`: Detalles de ejecución y errores

## Uso

### 1. Reemplazar archivos originales

```bash
# Backup de archivos originales
cp app.py app_original.py
cp llm_providers.py llm_providers_original.py
cp livo_sql.py livo_sql_original.py

# Usar versiones optimizadas
cp app_optimized.py app.py
cp llm_providers_optimized.py llm_providers.py
cp livo_sql_optimized.py livo_sql.py
```

### 2. Ejecutar aplicación optimizada

```bash
streamlit run app.py
```

### 3. Generar Excel de benchmark

```python
from app_optimized import actualizar_excel_benchmark
actualizar_excel_benchmark("resultados_benchmark_optimizado.xlsx")
```

## Métricas Monitoreadas

### Métricas de Rendimiento

1. **Tiempo de respuesta**: Tiempo total por pregunta
2. **Tasa de éxito**: Porcentaje de preguntas procesadas correctamente
3. **Reintentos**: Número promedio de reintentos por componente
4. **Timeouts**: Frecuencia de timeouts por componente
5. **Errores**: Tipos y frecuencia de errores

### Métricas por Proveedor LLM

1. **Tiempo promedio**: Por proveedor y componente
2. **Tasa de éxito**: Por proveedor y componente
3. **Reintentos**: Por proveedor y componente
4. **Timeouts**: Por proveedor y componente

## Diagnóstico de Problemas

### Identificación de Cuellos de Botella

1. **Logging en tiempo real**: Sidebar muestra métricas actuales
2. **Excel detallado**: Cada componente con sus métricas
3. **Errores recientes**: Últimos 5 errores registrados
4. **Componentes lentos**: Identificados por tiempo promedio

### Acciones Correctivas

1. **Timeouts ajustables**: Modificar constantes en archivos
2. **Reintentos configurables**: Ajustar MAX_REINTENTOS
3. **Proveedores alternativos**: Cambiar orden de proveedores
4. **Componentes deshabilitados**: Omitir componentes problemáticos

## Solución al Problema Original

### Causa del Timeout de 350s

El problema estaba en:
1. **Llamadas al LLM sin timeout específico**
2. **Bucles infinitos de corrección**
3. **Falta de logging para identificar cuellos de botella**
4. **Sin límite de reintentos**

### Solución Implementada

1. **Timeouts específicos**: Cada componente tiene su timeout
2. **Máximo 3 reintentos**: Evita bucles infinitos
3. **Logging detallado**: Identifica rápidamente problemas
4. **Tracking en Excel**: Análisis post-mortem completo
5. **Interfaz optimizada**: Métricas en tiempo real

### Resultado Esperado

- **Tiempo máximo por pregunta**: < 60 segundos
- **Tasa de éxito**: > 95%
- **Identificación de problemas**: < 5 segundos
- **Análisis post-mortem**: Completo en Excel

## Configuración Adicional

### Variables de Entorno

```bash
# Timeouts (segundos)
TIMEOUT_APP=350
TIMEOUT_COMPONENTE=60
TIMEOUT_LLM_BASE=30
TIMEOUT_OLLAMA=60
TIMEOUT_GROQ=120

# Reintentos
MAX_REINTENTOS=3
MAX_REINTENTOS_GENERACION=3
MAX_REINTENTOS_VALIDACION=3
```

### Logging

```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

## Soporte

Para problemas o preguntas:
1. Revisar logs de la aplicación
2. Analizar Excel de benchmark
3. Verificar métricas en sidebar
4. Ajustar timeouts si es necesario

---

**Estado**: Implementado
**Versión**: 1.0 Optimizada
**Fecha**: 2026-06-17
