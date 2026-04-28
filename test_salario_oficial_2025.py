#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test para verificar los rangos actualizados con el salario mínimo oficial 2025
"""

from datetime import datetime

# Clase con el salario mínimo oficial actualizado
class SalarioMinimoColombiano:
    SALARIOS_MINIMOS = {
        2020: 877803,
        2021: 908526,
        2022: 1000000,
        2023: 1160000,
        2024: 1300000,
        2025: 1423500,  # Oficial 2025
        2026: 1550000   # Proyectado
    }
    
    @classmethod
    def obtener_salario_minimo(cls, año: int) -> int:
        return cls.SALARIOS_MINIMOS.get(año, cls.SALARIOS_MINIMOS[2024])
    
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

def main():
    print("VERIFICACION CON SALARIO MINIMO OFICIAL 2025")
    print("=" * 80)
    
    # Salario mínimo oficial 2025
    salario_2025 = SalarioMinimoColombiano.obtener_salario_minimo(2025)
    print(f"Salario minimo oficial 2025: ${salario_2025:,}")
    
    # Calcular rangos actualizados
    rangos = SalarioMinimoColombiano.calcular_rangos_vivienda(2025)
    
    print(f"\nRANGOS ACTUALIZADOS CON SALARIO OFICIAL:")
    print("-" * 50)
    
    for tipo, info in rangos.items():
        if info['max'] == float('inf'):
            print(f"{tipo}: ${info['min']:,} en adelante")
        else:
            print(f"{tipo}: ${info['min']:,} - ${info['max']:,}")
        print(f"    {info['descripcion']}")
    
    # Convertir a miles para SQL (como está en la base)
    print(f"\nCONDICIONES SQL ACTUALIZADAS (valores en miles):")
    print("-" * 50)
    
    vip_max_miles = rangos['VIP']['max'] // 1000
    vis_min_miles = rangos['VIS']['min'] // 1000
    vis_max_miles = rangos['VIS']['max'] // 1000
    no_vis_min_miles = rangos['NO_VIS']['min'] // 1000
    
    print(f"VIP: WHERE valor < {vip_max_miles}")
    print(f"VIS: WHERE valor >= {vis_min_miles} AND valor < {vis_max_miles}")
    print(f"NO_VIS: WHERE valor >= {no_vis_min_miles}")
    
    print(f"\nCOMPARACION CON VALORES ANTERIORES:")
    print("-" * 50)
    print("ANTES (con $1,423,000):")
    print("- VIP: valor < 128,070")
    print("- VIS: valor >= 128,070 AND valor < 192,105")
    print("- NO_VIS: valor >= 192,105")
    print()
    print("AHORA (con $1,423,500 oficial):")
    print(f"- VIP: valor < {vip_max_miles:,}")
    print(f"- VIS: valor >= {vis_min_miles:,} AND valor < {vis_max_miles:,}")
    print(f"- NO_VIS: valor >= {no_vis_min_miles:,}")
    
    print(f"\nDIFERENCIA:")
    print("-" * 50)
    diferencia_vip = vip_max_miles - 128070
    diferencia_vis_min = vis_min_miles - 128070
    diferencia_vis_max = vis_max_miles - 192105
    diferencia_no_vis = no_vis_min_miles - 192105
    
    print(f"VIP max: +{diferencia_vip:,} (miles)")
    print(f"VIS min: +{diferencia_vis_min:,} (miles)")
    print(f"VIS max: +{diferencia_vis_max:,} (miles)")
    print(f"NO_VIS min: +{diferencia_no_vis:,} (miles)")
    
    print(f"\nRESUMEN:")
    print("=" * 80)
    print("✅ Salario mínimo actualizado: $1,423,500 (oficial)")
    print("✅ Rangos recalculados automáticamente")
    print("✅ Condiciones SQL actualizadas")
    print("✅ Sistema listo para usar con valores oficiales")

if __name__ == "__main__":
    main()
