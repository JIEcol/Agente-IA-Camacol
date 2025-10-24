"""
Script de prueba para verificar la configuración local del chatbot CAMACOL
"""

import os
import sys

def check_requirements():
    """Verifica que todas las dependencias estén instaladas"""
    print("🔍 Verificando dependencias...")
    
    required_packages = ['streamlit', 'google.generativeai']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - NO INSTALADO")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  Faltan las siguientes dependencias: {', '.join(missing_packages)}")
        print("Ejecuta: pip install -r requirements.txt")
        return False
    
    print("\n✅ Todas las dependencias están instaladas\n")
    return True

def check_secrets():
    """Verifica que el archivo de secrets esté configurado"""
    print("🔍 Verificando configuración de secrets...")
    
    secrets_path = ".streamlit/secrets.toml"
    
    if not os.path.exists(secrets_path):
        print(f"  ❌ No se encontró {secrets_path}")
        print("\n📝 Pasos para configurar:")
        print("  1. Copia .streamlit/secrets.toml.example a .streamlit/secrets.toml")
        print("  2. Agrega tu API key de Google AI")
        print("  3. Obtén tu API key en: https://makersuite.google.com/app/apikey")
        return False
    
    # Verificar contenido del archivo
    with open(secrets_path, 'r') as f:
        content = f.read()
        
    if 'GOOGLE_API_KEY' not in content or 'tu_clave_de_google_ai_aqui' in content:
        print("  ⚠️  El archivo secrets.toml existe pero necesita configuración")
        print("     Agrega tu API key de Google AI en el archivo")
        return False
    
    print("  ✅ Archivo secrets.toml configurado correctamente\n")
    return True

def check_app_file():
    """Verifica que el archivo principal exista"""
    print("🔍 Verificando archivo principal...")
    
    if os.path.exists("app.py"):
        print("  ✅ app.py encontrado\n")
        return True
    else:
        print("  ❌ app.py no encontrado\n")
        return False

def main():
    """Función principal"""
    print("=" * 60)
    print("🧪 PRUEBA DE CONFIGURACIÓN - Chatbot CAMACOL")
    print("=" * 60)
    print()
    
    all_checks = []
    
    # Verificar archivo principal
    all_checks.append(check_app_file())
    
    # Verificar dependencias
    all_checks.append(check_requirements())
    
    # Verificar secrets
    all_checks.append(check_secrets())
    
    print("=" * 60)
    
    if all(all_checks):
        print("✅ TODO LISTO - Puedes ejecutar la aplicación")
        print("\nPara iniciar la aplicación, ejecuta:")
        print("  streamlit run app.py")
    else:
        print("⚠️  CONFIGURACIÓN INCOMPLETA")
        print("\nPor favor, completa los pasos indicados arriba")
    
    print("=" * 60)

if __name__ == "__main__":
    main()

