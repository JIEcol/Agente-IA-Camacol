#!/usr/bin/env python3
"""
Script de ayuda para automatizar comandos Git del proyecto CAMACOL
"""

import subprocess
import sys
from datetime import datetime

def run_command(command, description):
    """Ejecuta un comando y muestra el resultado"""
    print(f"\n-> {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[OK] {description} completado")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"[ERROR] {result.stderr}")
            return False
    except Exception as e:
        print(f"[ERROR] ejecutando comando: {e}")
        return False

def check_status():
    """Verifica el estado del repositorio"""
    print("\n=== Estado del Repositorio ===")
    print("=" * 50)
    run_command("git status", "Verificando estado")

def add_all():
    """Agrega todos los archivos modificados"""
    run_command("git add .", "Agregando archivos")
    return True

def commit(message=None):
    """Hace commit de los cambios"""
    if not message:
        message = f"Actualizacion automatica - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    run_command(f'git commit -m "{message}"', "Haciendo commit")
    return True

def push():
    """Hace push a GitHub"""
    run_command("git push origin main", "Subiendo a GitHub")
    return True

def pull():
    """Descarga cambios de GitHub"""
    run_command("git pull origin main", "Descargando cambios")
    return True

def show_menu():
    """Muestra el menú principal"""
    print("\n" + "=" * 50)
    print(">> Chatbot CAMACOL - Git Helper")
    print("=" * 50)
    print("\nOpciones:")
    print("1. Ver estado del repositorio")
    print("2. Agregar y hacer commit de todos los cambios")
    print("3. Hacer commit con mensaje personalizado")
    print("4. Subir cambios a GitHub (push)")
    print("5. Descargar cambios de GitHub (pull)")
    print("6. Hacer todo: add + commit + push")
    print("7. Ver historial de commits")
    print("0. Salir")
    print("=" * 50)

def main():
    """Función principal"""
    if len(sys.argv) > 1:
        # Modo automático desde línea de comandos
        action = sys.argv[1]
        
        if action == "status":
            check_status()
        elif action == "push":
            add_all()
            commit()
            push()
        elif action == "quick":
            # Commit rápido
            add_all()
            commit()
            push()
        else:
            print(f"Acción desconocida: {action}")
            print("Usa: python git_helper.py [status|push|quick]")
    
    else:
        # Modo interactivo
        while True:
            show_menu()
            choice = input("\n👉 Selecciona una opción: ").strip()
            
            if choice == "1":
                check_status()
            elif choice == "2":
                add_all()
                commit()
            elif choice == "3":
                message = input("📝 Ingresa el mensaje del commit: ")
                add_all()
                commit(message)
            elif choice == "4":
                push()
            elif choice == "5":
                pull()
            elif choice == "6":
                if add_all() and commit() and push():
                    print("\n[OK] Todo listo! Streamlit Cloud se actualizara automaticamente.")
            elif choice == "7":
                run_command("git log --oneline -10", "Historial reciente")
            elif choice == "0":
                print("\n>> Hasta luego!")
                break
            else:
                print("\n[ERROR] Opcion invalida")

if __name__ == "__main__":
    main()

