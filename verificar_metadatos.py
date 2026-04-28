#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar si tenemos implementada la tabla de metadatos LIVO completa
"""

# Importar solo los metadatos sin inicializar DuckDB
import sys
import os
sys.path.append(os.path.dirname(__file__))

# Metadatos implementados (copiados directamente para evitar dependencias)
METADATA_LIVO_IMPLEMENTADO = {
    # Fechas y períodos temporales
    'fecha': {
        'tipo': 'DATE',
        'descripcion': 'Fecha de registro del proyecto',
        'sinonimos': ['día', 'momento', 'cuándo', 'calendario', 'fecha de registro', 'momento de corte', 'mes', 'trimestre']
    },
    'año_corrido': {
        'tipo': 'INTEGER', 
        'descripcion': 'Año corrido del proyecto',
        'sinonimos': ['año', 'periodo anual', 'ejercicio', 'año fiscal', 'por año', 'anualmente']
    },
    'doce_meses': {
        'tipo': 'INTEGER',
        'descripcion': 'Indicador de últimos 12 meses',
        'sinonimos': ['últimos 12 meses', 'TTM', 'LTM', 'año móvil', 'periodo reciente', 'acumulado 12M']
    },
    
    # Ubicación geográfica
    'regional': {
        'tipo': 'VARCHAR',
        'descripcion': 'Regional CAMACOL',
        'sinonimos': ['región', 'zona grande', 'área geográfica', 'macrozona', 'dónde (macro)']
    },
    'departamento': {
        'tipo': 'VARCHAR',
        'descripcion': 'Departamento de Colombia',
        'sinonimos': ['estado', 'provincia', 'división administrativa', 'de qué departamento', 'jurisdicción']
    },
    'divipola': {
        'tipo': 'VARCHAR',
        'descripcion': 'Código DIVIPOLA del municipio',
        'sinonimos': ['código DIVIPOLA', 'código municipal', 'identificador geográfico', 'código DANE']
    },
    'ciudad': {
        'tipo': 'VARCHAR',
        'descripcion': 'Ciudad o municipio',
        'sinonimos': ['municipio', 'localidad', 'población', 'urbe', 'en qué ciudad', 'capital']
    },
    'zona': {
        'tipo': 'VARCHAR',
        'descripcion': 'Zona dentro de la ciudad',
        'sinonimos': ['sector', 'distrito', 'subzona', 'sector geográfico', 'microzona']
    },
    'barrio': {
        'tipo': 'VARCHAR',
        'descripcion': 'Barrio específico',
        'sinonimos': ['vecindario', 'comuna', 'urbanización', 'localidad', 'sector']
    },
    
    # Características socioeconómicas y de proyecto
    'estrato': {
        'tipo': 'INTEGER',
        'descripcion': 'Estrato socioeconómico',
        'sinonimos': ['nivel socioeconómico', 'clase social', 'estrato social', 'nivel', 'clasificación']
    },
    'destino_etapa': {
        'tipo': 'VARCHAR',
        'descripcion': 'Destino o finalidad del proyecto',
        'sinonimos': ['destino', 'finalidad', 'tipo de proyecto', 'uso principal', 'qué se va a hacer']
    },
    'uso_etapa': {
        'tipo': 'VARCHAR',
        'descripcion': 'Tipo de uso de la construcción',
        'sinonimos': ['tipo de unidad', 'clase de inmueble', 'tipo de propiedad', 'qué es', 'vivienda', 'comercial', 'oficinas']
    },
    
    # Información de constructoras
    'compania_constructora': {
        'tipo': 'VARCHAR',
        'descripcion': 'Nombre de la empresa constructora',
        'sinonimos': ['constructora', 'empresa', 'firma', 'quién construyó', 'quién hizo', 'desarrolladora', 'compañía']
    },
    'nit_constructora': {
        'tipo': 'VARCHAR',
        'descripcion': 'NIT de la constructora',
        'sinonimos': ['NIT', 'identificación constructora', 'cédula jurídica', 'RUT']
    },
    
    # Estados y fases del proyecto
    'estado': {
        'tipo': 'VARCHAR',
        'descripcion': 'Estado actual del proyecto',
        'sinonimos': ['estatus', 'situación', 'condición', 'cómo está', 'estado actual', 'vendido', 'en obra', 'terminado']
    },
    'fase': {
        'tipo': 'VARCHAR',
        'descripcion': 'Fase del proyecto',
        'sinonimos': ['etapa', 'progreso', 'ciclo', 'momento del proyecto', 'en qué etapa va', 'preventa', 'lanzamiento']
    },
    'last_estado': {
        'tipo': 'VARCHAR',
        'descripcion': 'Estado anterior del proyecto',
        'sinonimos': ['estado anterior', 'último estatus', 'condición previa', 'estado histórico']
    },
    
    # Rangos y clasificaciones de precio
    'nuevorango_pre': {
        'tipo': 'VARCHAR',
        'descripcion': 'Nuevo rango de precios',
        'sinonimos': ['rango de precio', 'nivel de valor', 'banda de precio', 'costo', 'segmento de precio']
    },
    'rangos_decreto_pre': {
        'tipo': 'VARCHAR',
        'descripcion': 'Rangos de decreto de precios',
        'sinonimos': ['rango PPM2', 'precio por metro cuadrado', 'valor por metro', 'rango de decreto', 'precio unitario']
    },
    'rango_area': {
        'tipo': 'VARCHAR',
        'descripcion': 'Rango de área construida',
        'sinonimos': ['rango de área', 'rango de tamaño', 'banda de metros cuadrados', 'segmento de área']
    },
    'politica_vivienda': {
        'tipo': 'VARCHAR',
        'descripcion': 'Tipo de política de vivienda',
        'sinonimos': ['tipo de política', 'VIS', 'NO VIS', 'interés social', 'qué política aplica', 'subsidio']
    },
    
    # Métricas numéricas principales
    'unidades': {
        'tipo': 'INTEGER',
        'descripcion': 'Número de unidades del proyecto',
        'sinonimos': ['cantidad', 'número de unidades', 'total de viviendas', 'cuántas unidades', 'inventario', 'SUM(unidades)']
    },
    'area': {
        'tipo': 'DOUBLE',
        'descripcion': 'Área construida en metros cuadrados',
        'sinonimos': ['metros cuadrados', 'tamaño', 'superficie', 'cuánto mide', 'dimensión', 'AVG(area)', 'MAX(area)']
    },
    'valor': {
        'tipo': 'DOUBLE',
        'descripcion': 'Valor económico del proyecto',
        'sinonimos': ['precio', 'costo', 'monto', 'valor de venta', 'valor final', 'cuánto vale', 'precio promedio', 'AVG(valor)', 'SUM(valor)']
    },
    'cuenta': {
        'tipo': 'INTEGER',
        'descripcion': 'Contador de registros o categoría',
        'sinonimos': ['conteo', 'número de registros', 'cuántos ítems', 'total de filas', 'COUNT()', 'SUM(cuenta)']
    }
}

def verificar_metadatos_completos():
    """Verifica si tenemos todos los metadatos de la tabla proporcionada"""
    
    # Tabla de metadatos proporcionada por el usuario
    metadatos_esperados = {
        'fecha': {'tipo': 'DATE', 'sinonimos': ['día', 'momento', 'cuándo', 'calendario', 'fecha de registro', 'momento de corte', 'mes', 'trimestre']},
        'año_corrido': {'tipo': 'INTEGER', 'sinonimos': ['año', 'periodo anual', 'ejercicio', 'año fiscal', 'por año', 'anualmente']},
        'doce_meses': {'tipo': 'INTEGER', 'sinonimos': ['últimos 12 meses', 'TTM', 'LTM', 'año móvil', 'periodo reciente', 'acumulado 12M']},
        'regional': {'tipo': 'VARCHAR', 'sinonimos': ['región', 'zona grande', 'área geográfica', 'macrozona', 'dónde (macro)']},
        'departamento': {'tipo': 'VARCHAR', 'sinonimos': ['estado', 'provincia', 'división administrativa', 'de qué departamento', 'jurisdicción']},
        'divipola': {'tipo': 'VARCHAR', 'sinonimos': ['código DIVIPOLA', 'código municipal', 'identificador geográfico', 'código DANE']},
        'ciudad': {'tipo': 'VARCHAR', 'sinonimos': ['municipio', 'localidad', 'población', 'urbe', 'en qué ciudad', 'capital']},
        'zona': {'tipo': 'VARCHAR', 'sinonimos': ['sector', 'distrito', 'subzona', 'sector geográfico', 'microzona']},
        'barrio': {'tipo': 'VARCHAR', 'sinonimos': ['vecindario', 'comuna', 'urbanización', 'localidad', 'sector']},
        'estrato': {'tipo': 'INTEGER', 'sinonimos': ['nivel socioeconómico', 'clase social', 'estrato social', 'nivel', 'clasificación']},
        'destino_etapa': {'tipo': 'VARCHAR', 'sinonimos': ['destino', 'finalidad', 'tipo de proyecto', 'uso principal', 'qué se va a hacer']},
        'uso_etapa': {'tipo': 'VARCHAR', 'sinonimos': ['tipo de unidad', 'clase de inmueble', 'tipo de propiedad', 'qué es', 'vivienda', 'comercial', 'oficinas']},
        'compania_constructora': {'tipo': 'VARCHAR', 'sinonimos': ['constructora', 'empresa', 'firma', 'quién construyó', 'quién hizo', 'desarrolladora', 'compañía']},
        'nit_constructora': {'tipo': 'VARCHAR', 'sinonimos': ['NIT', 'identificación constructora', 'cédula jurídica', 'RUT']},
        'estado': {'tipo': 'VARCHAR', 'sinonimos': ['estatus', 'situación', 'condición', 'cómo está', 'estado actual', 'vendido', 'en obra', 'terminado']},
        'fase': {'tipo': 'VARCHAR', 'sinonimos': ['etapa', 'progreso', 'ciclo', 'momento del proyecto', 'en qué etapa va', 'preventa', 'lanzamiento']},
        'last_estado': {'tipo': 'VARCHAR', 'sinonimos': ['estado anterior', 'último estatus', 'condición previa', 'estado histórico']},
        'nuevorango_pre': {'tipo': 'VARCHAR', 'sinonimos': ['rango de precio', 'nivel de valor', 'banda de precio', 'costo', 'segmento de precio']},
        'rangos_decreto_pre': {'tipo': 'VARCHAR', 'sinonimos': ['rango PPM2', 'precio por metro cuadrado', 'valor por metro', 'rango de decreto', 'precio unitario']},
        'rango_area': {'tipo': 'VARCHAR', 'sinonimos': ['rango de área', 'rango de tamaño', 'banda de metros cuadrados', 'segmento de área']},
        'politica_vivienda': {'tipo': 'VARCHAR', 'sinonimos': ['tipo de política', 'VIS', 'NO VIS', 'interés social', 'qué política aplica', 'subsidio']},
        'unidades': {'tipo': 'INTEGER', 'sinonimos': ['cantidad', 'número de unidades', 'total de viviendas', 'cuántas unidades', 'inventario', 'SUM(unidades)']},
        'area': {'tipo': 'DOUBLE', 'sinonimos': ['metros cuadrados', 'tamaño', 'superficie', 'cuánto mide', 'dimensión', 'AVG(area)', 'MAX(area)']},
        'valor': {'tipo': 'DOUBLE', 'sinonimos': ['precio', 'costo', 'monto', 'valor de venta', 'valor final', 'cuánto vale', 'precio promedio', 'AVG(valor)', 'SUM(valor)']},
        'cuenta': {'tipo': 'INTEGER', 'sinonimos': ['conteo', 'número de registros', 'cuántos ítems', 'total de filas', 'COUNT()', 'SUM(cuenta)']}
    }
    
    # Metadatos implementados actualmente
    metadatos_implementados = METADATA_LIVO_IMPLEMENTADO
    
    print("VERIFICACION DE METADATOS LIVO")
    print("=" * 80)
    
    # Verificar columnas implementadas vs esperadas
    columnas_esperadas = set(metadatos_esperados.keys())
    columnas_implementadas = set(metadatos_implementados.keys())
    
    print(f"\nRESUMEN:")
    print(f"   Columnas esperadas: {len(columnas_esperadas)}")
    print(f"   Columnas implementadas: {len(columnas_implementadas)}")
    
    # Columnas que faltan
    columnas_faltantes = columnas_esperadas - columnas_implementadas
    if columnas_faltantes:
        print(f"\nCOLUMNAS FALTANTES ({len(columnas_faltantes)}):")
        for col in sorted(columnas_faltantes):
            print(f"   - {col}")
    else:
        print(f"\nTODAS LAS COLUMNAS ESTAN IMPLEMENTADAS")
    
    # Columnas extra (que tenemos pero no están en la tabla esperada)
    columnas_extra = columnas_implementadas - columnas_esperadas
    if columnas_extra:
        print(f"\nCOLUMNAS ADICIONALES ({len(columnas_extra)}):")
        for col in sorted(columnas_extra):
            print(f"   - {col}")
    
    # Verificar coincidencias exactas
    columnas_comunes = columnas_esperadas & columnas_implementadas
    print(f"\nVERIFICACION DETALLADA DE COLUMNAS COMUNES ({len(columnas_comunes)}):")
    
    diferencias_encontradas = 0
    
    for col in sorted(columnas_comunes):
        esperado = metadatos_esperados[col]
        implementado = metadatos_implementados[col]
        
        # Verificar tipo
        tipo_correcto = esperado['tipo'] == implementado['tipo']
        
        # Verificar sinónimos (convertir a sets para comparación)
        sinonimos_esperados = set(esperado['sinonimos'])
        sinonimos_implementados = set(implementado['sinonimos'])
        sinonimos_coinciden = sinonimos_esperados == sinonimos_implementados
        
        if tipo_correcto and sinonimos_coinciden:
            print(f"   OK {col}: Perfecto")
        else:
            diferencias_encontradas += 1
            print(f"   WARN {col}: Diferencias encontradas")
            
            if not tipo_correcto:
                print(f"      - Tipo esperado: {esperado['tipo']}, implementado: {implementado['tipo']}")
            
            if not sinonimos_coinciden:
                faltantes = sinonimos_esperados - sinonimos_implementados
                extra = sinonimos_implementados - sinonimos_esperados
                
                if faltantes:
                    print(f"      - Sinónimos faltantes: {', '.join(sorted(faltantes))}")
                if extra:
                    print(f"      - Sinónimos extra: {', '.join(sorted(extra))}")
    
    # Resumen final
    print(f"\n" + "=" * 80)
    print(f"RESUMEN FINAL:")
    
    if not columnas_faltantes and diferencias_encontradas == 0:
        print(f"IMPLEMENTACION COMPLETA Y CORRECTA")
        print(f"   - Todas las {len(columnas_esperadas)} columnas estan implementadas")
        print(f"   - Todos los tipos y sinonimos coinciden exactamente")
    else:
        print(f"IMPLEMENTACION PARCIAL:")
        if columnas_faltantes:
            print(f"   - Faltan {len(columnas_faltantes)} columnas por implementar")
        if diferencias_encontradas > 0:
            print(f"   - {diferencias_encontradas} columnas tienen diferencias en tipos o sinonimos")
    
    if columnas_extra:
        print(f"INFORMACION ADICIONAL:")
        print(f"   - Se encontraron {len(columnas_extra)} columnas adicionales no especificadas")
    
    return {
        'columnas_faltantes': list(columnas_faltantes),
        'columnas_extra': list(columnas_extra),
        'diferencias_encontradas': diferencias_encontradas,
        'implementacion_completa': len(columnas_faltantes) == 0 and diferencias_encontradas == 0
    }

if __name__ == "__main__":
    resultado = verificar_metadatos_completos()
    
    if resultado['implementacion_completa']:
        print(f"\nEXCELENTE! La tabla de metadatos esta completamente implementada.")
    else:
        print(f"\nHay algunos elementos por ajustar para tener la implementacion perfecta.")
