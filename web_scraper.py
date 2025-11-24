#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Web Scraper para CAMACOL
Extrae documentos del repositorio documental y páginas web
"""

import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Tuple, List, Dict
from urllib.parse import urljoin
import re
import time

class CoordenadaUrbanaScraper:
    """Scraper para el repositorio documental de Coordenada Urbana"""
    
    def __init__(self, output_folder: str = "./scraped_data"):
        self.base_url = "https://ww2.coordenadaurbana.com"
        self.login_url = f"{self.base_url}/Autenticacion/GestDocumental"
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def extraer_metadata(self) -> Tuple[bool, List[Dict]]:
        """
        Extrae metadata de documentos disponibles
        
        Returns:
            Tuple[bool, List[Dict]]: (éxito, lista de documentos)
        """
        try:
            print("🔍 Extrayendo metadata de Coordenada Urbana...")
            
            response = self.session.get(self.login_url, timeout=10)
            
            if response.status_code != 200:
                return False, []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar enlaces a documentos
            documentos = []
            
            # Buscar PDFs
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '.pdf' in href.lower():
                    documentos.append({
                        'tipo': 'PDF',
                        'url': href if href.startswith('http') else f"{self.base_url}{href}",
                        'titulo': link.get_text(strip=True)
                    })
            
            print(f"✅ Encontrados {len(documentos)} documentos")
            return True, documentos
            
        except Exception as e:
            print(f"❌ Error al extraer metadata: {e}")
            return False, []
    
    def guardar_info(self, documentos: List[Dict]) -> Tuple[bool, str]:
        """
        Guarda información de documentos en archivo
        
        Args:
            documentos: Lista de documentos
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            output_file = self.output_folder / "coordenada_urbana_docs.txt"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("# Documentos de Coordenada Urbana\n\n")
                f.write(f"Total de documentos: {len(documentos)}\n\n")
                
                for i, doc in enumerate(documentos, 1):
                    f.write(f"## Documento {i}\n")
                    f.write(f"Título: {doc['titulo']}\n")
                    f.write(f"Tipo: {doc['tipo']}\n")
                    f.write(f"URL: {doc['url']}\n\n")
            
            return True, f"✅ Información guardada en {output_file}"
            
        except Exception as e:
            return False, f"❌ Error al guardar: {str(e)}"

class CamacolAgendaScraper:
    """Scraper para extraer documentos de páginas de CAMACOL"""
    
    def __init__(self):
        self.base_url = "https://camacol.co"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def extraer_urls_documentos(self, url_pagina: str, max_paginas: int = 15) -> List[str]:
        """
        Extrae todas las URLs de documentos de una página de CAMACOL con paginación
        
        Args:
            url_pagina: URL de la página principal
            max_paginas: Número máximo de páginas a procesar
        
        Returns:
            Lista de URLs de documentos encontrados
        """
        urls_encontradas = set()
        
        print(f"🌐 Extrayendo URLs de: {url_pagina}")
        print("")
        
        # Procesar cada página de paginación
        for pagina in range(max_paginas):
            if pagina == 0:
                url = url_pagina
            else:
                url = f"{url_pagina}?page={pagina}"
            
            try:
                print(f"📚 Procesando página {pagina + 1}...")
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Buscar enlaces que apunten a /descargable/
                enlaces = soup.find_all('a', href=re.compile(r'/descargable/'))
                
                if not enlaces:
                    print(f"   ⚠️ No se encontraron más documentos en página {pagina + 1}")
                    break
                
                for enlace in enlaces:
                    href = enlace.get('href')
                    if href:
                        # Convertir a URL completa
                        url_completa = urljoin(self.base_url, href)
                        
                        # Intentar obtener la URL directa del PDF
                        try:
                            # Hacer request a la página del descargable
                            resp_desc = self.session.get(url_completa, timeout=10, allow_redirects=True)
                            
                            # Si redirige a un PDF, usar esa URL
                            if resp_desc.url.endswith('.pdf'):
                                urls_encontradas.add(resp_desc.url)
                                print(f"   ✅ PDF: {resp_desc.url.split('/')[-1][:60]}")
                            else:
                                # Buscar enlace directo al PDF en la página
                                soup_desc = BeautifulSoup(resp_desc.content, 'html.parser')
                                pdf_links = soup_desc.find_all('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
                                
                                if pdf_links:
                                    for pdf_link in pdf_links:
                                        pdf_url = urljoin(self.base_url, pdf_link.get('href'))
                                        urls_encontradas.add(pdf_url)
                                        print(f"   ✅ PDF: {pdf_url.split('/')[-1][:60]}")
                                else:
                                    # Si no hay PDF directo, guardar la URL del descargable
                                    urls_encontradas.add(url_completa)
                                    titulo = enlace.get_text(strip=True)[:50]
                                    print(f"   📄 Descargable: {titulo}...")
                        
                        except Exception as e:
                            print(f"   ⚠️ Error: {str(e)[:50]}")
                
                # Pausa para no sobrecargar el servidor
                time.sleep(1)
                
            except Exception as e:
                print(f"   ❌ Error en página {pagina + 1}: {e}")
                break
        
        return sorted(list(urls_encontradas))
    
    def agregar_urls_a_archivo(self, urls: List[str], archivo: str = 'urls_documentos.txt', seccion: str = "Documentos") -> int:
        """
        Agrega URLs al archivo urls_documentos.txt sin duplicados
        
        Args:
            urls: Lista de URLs a agregar
            archivo: Nombre del archivo
            seccion: Nombre de la sección (ej: "Agendas Legislativas")
        
        Returns:
            Número de URLs nuevas agregadas
        """
        # Leer URLs existentes
        urls_existentes = set()
        try:
            with open(archivo, 'r', encoding='utf-8') as f:
                for linea in f:
                    linea = linea.strip()
                    if linea and not linea.startswith('#'):
                        urls_existentes.add(linea)
        except FileNotFoundError:
            pass
        
        # Agregar nuevas URLs
        urls_nuevas = [url for url in urls if url not in urls_existentes]
        
        if urls_nuevas:
            with open(archivo, 'a', encoding='utf-8') as f:
                f.write(f"\n# {seccion} (extraídas automáticamente el {time.strftime('%Y-%m-%d %H:%M:%S')})\n")
                for url in urls_nuevas:
                    f.write(f"{url}\n")
            
            print(f"\n✅ {len(urls_nuevas)} URLs nuevas agregadas a {archivo}")
        else:
            print(f"\nℹ️ No hay URLs nuevas para agregar")
        
        return len(urls_nuevas)

class CamacolContentScraper:
    """Scraper para extraer contenido HTML de páginas de CAMACOL"""
    
    def __init__(self, output_folder: str = "./RAG/scraped_content"):
        self.base_url = "https://camacol.co"
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def extraer_contenido_html(self, url: str) -> Tuple[bool, str]:
        """
        Extrae el contenido principal de una página HTML
        
        Args:
            url: URL de la página
        
        Returns:
            Tuple[bool, str]: (éxito, contenido extraído)
        """
        try:
            print(f"🌐 Extrayendo contenido de: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Eliminar scripts, estilos, navegación, footer
            for elemento in soup(['script', 'style', 'nav', 'footer', 'header']):
                elemento.decompose()
            
            # Extraer título
            titulo = soup.find('title')
            titulo_texto = titulo.get_text(strip=True) if titulo else url.split('/')[-1]
            
            # Extraer contenido principal
            contenido = []
            contenido.append(f"# {titulo_texto}\n")
            contenido.append(f"**Fuente:** {url}\n\n")
            
            # Buscar el contenido principal (main, article, o divs con clase content)
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|main', re.IGNORECASE))
            
            if main_content:
                # Extraer encabezados y párrafos
                for elemento in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'blockquote']):
                    texto = elemento.get_text(strip=True)
                    if texto and len(texto) > 10:  # Filtrar textos muy cortos
                        if elemento.name.startswith('h'):
                            nivel = int(elemento.name[1])
                            contenido.append(f"\n{'#' * nivel} {texto}\n")
                        elif elemento.name == 'li':
                            contenido.append(f"- {texto}\n")
                        elif elemento.name == 'blockquote':
                            contenido.append(f"> {texto}\n\n")
                        else:
                            contenido.append(f"{texto}\n\n")
            else:
                # Si no hay contenido principal, extraer todos los párrafos
                for p in soup.find_all('p'):
                    texto = p.get_text(strip=True)
                    if texto and len(texto) > 10:
                        contenido.append(f"{texto}\n\n")
            
            contenido_final = ''.join(contenido)
            
            if len(contenido_final) > 100:
                print(f"   ✅ Extraídos {len(contenido_final)} caracteres")
                return True, contenido_final
            else:
                print(f"   ⚠️ Contenido insuficiente")
                return False, ""
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False, ""
    
    def guardar_contenido(self, url: str, contenido: str) -> bool:
        """
        Guarda el contenido extraído en un archivo de texto
        
        Args:
            url: URL de origen
            contenido: Contenido extraído
        
        Returns:
            bool: Éxito de la operación
        """
        try:
            # Crear nombre de archivo desde la URL
            nombre = url.split('/')[-1] or 'index'
            nombre = re.sub(r'[^\w\-]', '_', nombre)
            archivo = self.output_folder / f"{nombre}.txt"
            
            with open(archivo, 'w', encoding='utf-8') as f:
                f.write(contenido)
            
            print(f"   💾 Guardado en: {archivo.name}")
            return True
            
        except Exception as e:
            print(f"   ❌ Error al guardar: {e}")
            return False

def procesar_paginas_camacol():
    """
    Procesa todas las páginas de CAMACOL configuradas
    """
    print("="*70)
    print("🔍 EXTRACTOR COMPLETO DE CONTENIDO CAMACOL")
    print("="*70)
    print("")
    
    # PÁGINAS CON DOCUMENTOS DESCARGABLES (con paginación automática)
    paginas_documentos = [
        # Información Jurídica
        ("https://camacol.co/nuestro-sector/informacion-juridica/informes-juridicos", "Informes Jurídicos"),
        ("https://camacol.co/nuestro-sector/informacion-juridica/normas-sectoriales", "Normas Sectoriales"),
        ("https://camacol.co/nuestro-sector/informacion-juridica/agenda-legislativa", "Agenda Legislativa"),
        
        # Información Técnica
        ("https://camacol.co/nuestro-sector/informacion-tecnica/informe-de-actualizacion-tecnica", "Informes Técnicos"),
        ("https://camacol.co/nuestro-sector/informacion-tecnica/agenda-regulatoria-tecnica-sectorial", "Agenda Regulatoria"),
        
        # Estudios Económicos y Técnicos
        ("https://camacol.co/estudios-economicos-y-tecnicos/investigaciones-sectoriales", "Investigaciones Sectoriales"),
        ("https://camacol.co/estudios-economicos-y-tecnicos/informes-economicos", "Informes Económicos"),
        ("https://camacol.co/estudios-economicos-y-tecnicos/datos-que-construyen", "Datos que Construyen"),
        ("https://camacol.co/estudios-economicos-y-tecnicos/prospectiva-edificadora", "Prospectiva Edificadora"),
        ("https://camacol.co/estudios-economicos-y-tecnicos/tendencias-de-la-construccion", "Tendencias de la Construcción"),
        
        # Actualidad
        ("https://camacol.co/actualidad/boletines", "Boletines"),
    ]
    
    # PÁGINAS CON CONTENIDO HTML
    paginas_contenido = [
        # Productividad Sectorial
        "https://camacol.co/productividad-sectorial/camacol-verde",
        "https://camacol.co/productividad-sectorial/linea-de-accion-gremial",
        "https://camacol.co/productividad-sectorial/mesa-de-construccion-sostenible",
        "https://camacol.co/productividad-sectorial/vis-40",
        "https://camacol.co/productividad-sectorial/sostenido",
        "https://camacol.co/productividad-sectorial/ruta-circular",
        "https://camacol.co/productividad-sectorial/green-hub",
        "https://camacol.co/productividad-sectorial/encadena-mejores-proveedores",
        "https://camacol.co/productividad-sectorial/ruta-nacional-camacol-verde",
        "https://camacol.co/productividad-sectorial/edge-buildings",
        "https://camacol.co/productividad-sectorial/modernizacion-empresarial",
        "https://camacol.co/productividad-sectorial/responsabilidad-social",
        "https://camacol.co/productividad-sectorial/transformacion-digital",
        
        # Temas Sectoriales
        "https://camacol.co/temas/vivienda",
        "https://camacol.co/temas/construccion",
        "https://camacol.co/temas/guillermo-herrera",
        "https://camacol.co/temas/materiales-sostenibles",
        "https://camacol.co/temas/construccion-sostenible",
        "https://camacol.co/temas/bim",
        "https://camacol.co/temas/genero",
        
        # Institucional
        "https://camacol.co/nosotros/historia",
        "https://camacol.co/nosotros/equipo",
        "https://camacol.co/nosotros/afiliados",
        "https://camacol.co/nosotros/regionales",
        "https://camacol.co/nosotros/informes-de-gestion",
        "https://camacol.co/nosotros/asamblea-ordinaria-nacional",
        "https://camacol.co/nosotros/premios-camacol",
        
        # Fuentes Externas - Investigaciones Económicas
        "https://www.camacol.co/investigaciones-economicas/participacion-en-revistas-indexadas",
        "https://www.banrep.gov.co/es/publicaciones-investigaciones",
    ]
    
    scraper_docs = CamacolAgendaScraper()
    scraper_content = CamacolContentScraper()
    
    total_urls = 0
    total_contenido = 0
    
    # PASO PREVIO: Agregar PDFs directos conocidos
    print("📄 PASO PREVIO: AGREGANDO PDFs DIRECTOS")
    print("="*70)
    pdfs_directos = [
        "https://camacol.co/sites/default/files/descargables/Catálogo-Oferta-de-Valor-Camacol-Oct-2025.pdf",
    ]
    
    if pdfs_directos:
        nuevas = scraper_docs.agregar_urls_a_archivo(pdfs_directos, seccion="PDFs Directos")
        total_urls += nuevas
    print("")
    
    # FASE 1: Extraer URLs de documentos Y contenido HTML de las páginas
    print("📄 FASE 1: EXTRAYENDO URLs DE DOCUMENTOS + CONTENIDO HTML")
    print("="*70)
    for url, nombre in paginas_documentos:
        print(f"\n📚 {nombre}...")
        try:
            # 1A. Extraer URLs de documentos (PDFs, Word, Excel)
            # max_paginas=15 asegura que capture TODAS las páginas con paginación
            urls = scraper_docs.extraer_urls_documentos(url, max_paginas=15)
            if urls:
                nuevas = scraper_docs.agregar_urls_a_archivo(urls, seccion=nombre)
                total_urls += nuevas
            
            # 1B. TAMBIÉN extraer contenido HTML de la página principal
            print(f"   🌐 Extrayendo contenido HTML de la página...")
            exito, contenido = scraper_content.extraer_contenido_html(url)
            if exito:
                if scraper_content.guardar_contenido(url, contenido):
                    total_contenido += 1
            
            time.sleep(2)  # Pausa entre páginas
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # FASE 2: Extraer contenido HTML de páginas de productividad
    print("\n")
    print("🌐 FASE 2: EXTRAYENDO CONTENIDO HTML (PÁGINAS DE PRODUCTIVIDAD)")
    print("="*70)
    for url in paginas_contenido:
        try:
            exito, contenido = scraper_content.extraer_contenido_html(url)
            if exito:
                if scraper_content.guardar_contenido(url, contenido):
                    total_contenido += 1
            time.sleep(2)  # Pausa entre páginas
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # RESUMEN
    print("\n")
    print("="*70)
    print("📊 RESUMEN FINAL")
    print("="*70)
    print(f"✅ URLs de documentos agregadas: {total_urls}")
    print(f"✅ Páginas HTML procesadas: {total_contenido}")
    print(f"📁 Contenido HTML guardado en: ./RAG/scraped_content/")
    print("")
    print("💡 PRÓXIMOS PASOS:")
    print("1. Revisa 'urls_documentos.txt' (URLs de PDFs/Word/Excel)")
    print("2. Revisa './RAG/scraped_content/' (contenido HTML extraído)")
    print("3. Ejecuta: python inicializar_rag.py")
    print("4. Todo se indexará automáticamente en el RAG")
    print("")

if __name__ == "__main__":
    procesar_paginas_camacol()