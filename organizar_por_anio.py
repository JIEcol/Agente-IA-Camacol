#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para organizar automaticamente documentos web scraped por año
Detecta el año en el titulo o contenido del documento
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime

# Procesamiento de documentos
try:
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except:
    PDF_AVAILABLE = False
    print("⚠️ PyPDF2 no disponible. Instala con: pip install PyPDF2")

try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False
    print("⚠️ python-docx no disponible. Instala con: pip install python-docx")

class OrganizadorPorAnio:
    """Organiza documentos web scraped por año automaticamente"""
    
    def __init__(self, rag_folder: str):
        self.rag_folder = Path(rag_folder)
        # Buscar en scraped_content (donde guarda web_scraper.py)
        self.web_scraped_folder = self.rag_folder / "scraped_content"
        
        # Años a detectar (del mas reciente al mas antiguo)
        self.years = ['2025', '2024', '2023', '2022', '2021']
        
        # Patrones para detectar años
        self.year_patterns = [
            r'\b(202[0-5])\b',  # 2020-2025
            r'\b(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)[_\s-]?(2[0-5])\b',  # oct 25, oct-25
            r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)[_\s-]?(202[0-5])\b',  # octubre 2025
            r'\b([0-3]?[0-9])[/_-](0?[1-9]|1[0-2])[/_-](202[0-5])\b',  # 15/10/2025, 15-10-2025
            r'\b(202[0-5])[/_-](0?[1-9]|1[0-2])[/_-]([0-3]?[0-9])\b'   # 2025/10/15, 2025-10-15
        ]
    
    def extraer_texto_pdf(self, archivo: Path, max_pages: int = 3) -> str:
        """Extrae texto de las primeras paginas de un PDF"""
        if not PDF_AVAILABLE:
            return ""
        
        try:
            reader = PdfReader(str(archivo))
            texto = ""
            
            # Leer solo las primeras paginas (donde suele estar el titulo y fecha)
            for i in range(min(max_pages, len(reader.pages))):
                page_text = reader.pages[i].extract_text()
                if page_text:
                    texto += page_text + "\n"
            
            return texto
        except Exception as e:
            print(f"❌ Error al leer PDF {archivo.name}: {e}")
            return ""
    
    def extraer_texto_docx(self, archivo: Path) -> str:
        """Extrae texto de un documento Word"""
        if not DOCX_AVAILABLE:
            return ""
        
        try:
            doc = Document(str(archivo))
            # Extraer primeros 10 parrafos (donde suele estar el titulo y fecha)
            texto = "\n".join([p.text for p in doc.paragraphs[:10] if p.text.strip()])
            return texto
        except Exception as e:
            print(f"❌ Error al leer Word {archivo.name}: {e}")
            return ""
    
    def detectar_anio(self, archivo: Path) -> str:
        """Detecta el año de un documento"""
        
        # 1. Buscar en el nombre del archivo
        nombre = archivo.name
        for patron in self.year_patterns:
            match = re.search(patron, nombre, re.IGNORECASE)
            if match:
                # Extraer el año completo
                anio_encontrado = self._extraer_anio_completo(match)
                if anio_encontrado:
                    print(f"  📄 Año detectado en nombre: {anio_encontrado}")
                    return anio_encontrado
        
        # 2. Leer contenido del archivo
        texto = ""
        ext = archivo.suffix.lower()
        
        if ext == '.pdf' and PDF_AVAILABLE:
            texto = self.extraer_texto_pdf(archivo)
        elif ext in ['.docx', '.doc'] and DOCX_AVAILABLE:
            texto = self.extraer_texto_docx(archivo)
        elif ext == '.txt':
            try:
                with open(archivo, 'r', encoding='utf-8') as f:
                    texto = f.read(2000)  # Primeros 2000 caracteres
            except:
                pass
        
        if not texto:
            print(f"  ⚠️ No se pudo leer el contenido de {archivo.name}")
            return "desconocido"
        
        # 3. Buscar año en el contenido (primero en las primeras lineas)
        lineas = texto.split('\n')
        
        # Buscar en las primeras 20 lineas (donde suele estar el titulo y fecha)
        for i, linea in enumerate(lineas[:20]):
            for patron in self.year_patterns:
                match = re.search(patron, linea, re.IGNORECASE)
                if match:
                    anio_encontrado = self._extraer_anio_completo(match)
                    if anio_encontrado:
                        print(f"  📄 Año detectado en línea {i+1}: {anio_encontrado}")
                        print(f"     Contexto: {linea[:100]}...")
                        return anio_encontrado
        
        # 4. Si no se encuentra en las primeras lineas, buscar en todo el texto
        for patron in self.year_patterns:
            matches = re.finditer(patron, texto, re.IGNORECASE)
            for match in matches:
                anio_encontrado = self._extraer_anio_completo(match)
                if anio_encontrado:
                    print(f"  📄 Año detectado en contenido: {anio_encontrado}")
                    return anio_encontrado
        
        print(f"  ⚠️ No se detectó año en {archivo.name}")
        return "desconocido"
    
    def _extraer_anio_completo(self, match) -> str:
        """Extrae el año completo de un match regex"""
        texto_match = match.group(0)
        
        # Buscar año de 4 digitos
        anio_4_digitos = re.search(r'202[0-5]', texto_match)
        if anio_4_digitos:
            return anio_4_digitos.group(0)
        
        # Buscar año de 2 digitos (20-25)
        anio_2_digitos = re.search(r'\b(2[0-5])\b', texto_match)
        if anio_2_digitos:
            return '20' + anio_2_digitos.group(1)
        
        return None
    
    def organizar_documentos(self, dry_run: bool = False):
        """Organiza los documentos por año"""
        
        if not self.web_scraped_folder.exists():
            print(f"❌ Carpeta no encontrada: {self.web_scraped_folder}")
            return
        
        print("\n" + "="*70)
        print("📂 ORGANIZADOR AUTOMÁTICO DE DOCUMENTOS POR AÑO")
        print("="*70)
        print(f"Carpeta origen: {self.web_scraped_folder}")
        print(f"Modo: {'SIMULACIÓN (no se moverán archivos)' if dry_run else 'REAL (se moverán archivos)'}")
        print("="*70 + "\n")
        
        # Obtener todos los archivos
        archivos = list(self.web_scraped_folder.glob('*.*'))
        archivos = [f for f in archivos if f.is_file()]
        
        if not archivos:
            print("⚠️ No se encontraron archivos en scraped_content/")
            return
        
        print(f"📄 Archivos encontrados: {len(archivos)}\n")
        
        # Estadisticas
        stats = {
            'total': len(archivos),
            'organizados': 0,
            'sin_anio': 0,
            'por_anio': {year: 0 for year in self.years}
        }
        
        # Procesar cada archivo
        for i, archivo in enumerate(archivos, 1):
            print(f"\n[{i}/{len(archivos)}] Procesando: {archivo.name}")
            
            # Detectar año
            anio = self.detectar_anio(archivo)
            
            if anio == "desconocido":
                stats['sin_anio'] += 1
                print(f"  ⚠️ Sin año detectado - se quedará en scraped_content/")
                continue
            
            # Crear carpeta de destino
            carpeta_destino = self.rag_folder / anio / "web_scraped"
            
            if not dry_run:
                carpeta_destino.mkdir(parents=True, exist_ok=True)
            
            # Mover archivo
            archivo_destino = carpeta_destino / archivo.name
            
            if dry_run:
                print(f"  📦 [SIMULACIÓN] Movería a: {carpeta_destino}")
                stats['organizados'] += 1
                stats['por_anio'][anio] += 1
            else:
                try:
                    shutil.move(str(archivo), str(archivo_destino))
                    print(f"  ✅ Movido a: {carpeta_destino}")
                    stats['organizados'] += 1
                    stats['por_anio'][anio] += 1
                except Exception as e:
                    print(f"  ❌ Error al mover: {e}")
        
        # Mostrar resumen
        print("\n" + "="*70)
        print("📊 RESUMEN")
        print("="*70)
        print(f"Total de archivos: {stats['total']}")
        print(f"Organizados: {stats['organizados']}")
        print(f"Sin año detectado: {stats['sin_anio']}")
        print("\nArchivos por año:")
        for year in self.years:
            if stats['por_anio'][year] > 0:
                print(f"  {year}: {stats['por_anio'][year]} archivos")
        print("="*70 + "\n")
        
        if dry_run:
            print("⚠️ Esto fue una SIMULACIÓN. Ejecuta sin --dry-run para mover los archivos.\n")
        else:
            print("✅ Organización completada!\n")
            print("💡 Próximo paso: Ejecuta 'python inicializar_rag.py' para reindexar los documentos.\n")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Organiza documentos web scraped por año')
    parser.add_argument('--rag-folder', type=str, 
                       default=r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG",
                       help='Ruta a la carpeta RAG')
    parser.add_argument('--dry-run', action='store_true',
                       help='Modo simulación (no mueve archivos)')
    
    args = parser.parse_args()
    
    organizador = OrganizadorPorAnio(args.rag_folder)
    organizador.organizar_documentos(dry_run=args.dry_run)

if __name__ == '__main__':
    main()
