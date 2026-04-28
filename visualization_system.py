#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sistema de Visualización Multi-Canal para LIVO
Genera imágenes para Streamlit, Telegram y WhatsApp Business (futuro)
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import io
import base64
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Configuración de estilo
plt.style.use('default')
sns.set_palette("husl")

class LIVOVisualizationSystem:
    """Sistema de visualización multi-canal para datos LIVO"""
    
    def __init__(self):
        self.setup_style()
        self.channel_configs = {
            'streamlit': {
                'dpi': 100,
                'figsize': (12, 8),
                'format': 'png',
                'max_size_mb': 10
            },
            'telegram': {
                'dpi': 150,
                'figsize': (10, 6),
                'format': 'png',
                'max_size_mb': 10
            },
            'whatsapp': {  # Para implementación futura
                'dpi': 200,
                'figsize': (8, 6),
                'format': 'jpeg',
                'max_size_mb': 5,
                'quality': 85
            }
        }
    
    def setup_style(self):
        """Configura el estilo visual para CAMACOL"""
        # Colores corporativos CAMACOL
        self.colors = {
            'primary': '#1f4e79',      # Azul CAMACOL
            'secondary': '#2e75b6',    # Azul claro
            'accent': '#f39c12',       # Naranja
            'success': '#27ae60',      # Verde
            'warning': '#f39c12',      # Amarillo
            'danger': '#e74c3c',       # Rojo
            'vis': '#27ae60',          # Verde para VIS
            'vip': '#f39c12',          # Naranja para VIP
            'no_vis': '#e74c3c'        # Rojo para No VIS
        }
        
        # Configurar matplotlib
        plt.rcParams.update({
            'font.size': 11,
            'font.family': 'sans-serif',
            'axes.titlesize': 14,
            'axes.labelsize': 12,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'legend.fontsize': 10,
            'figure.titlesize': 16
        })
    
    def detect_visualization_type(self, data: pd.DataFrame, query_info: Dict) -> str:
        """Detecta el tipo de visualización más apropiado"""
        
        if data.empty:
            return 'no_data'
        
        # Analizar estructura de datos
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        categorical_cols = data.select_dtypes(include=['object', 'category']).columns
        
        # Detectar por contenido de la consulta
        query_lower = query_info.get('original_question', '').lower()
        
        # Clasificación VIS/VIP/No VIS
        if any(term in query_lower for term in ['vis', 'vip', 'no vis', 'clasificacion', 'tipo vivienda']):
            if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
                return 'classification_pie'
        
        # Comparaciones por ciudad/departamento
        if any(term in query_lower for term in ['ciudad', 'departamento', 'regional']):
            if len(data) <= 15:  # Pocas categorías
                return 'horizontal_bar'
            else:
                return 'top_n_bar'
        
        # Evolución temporal
        if any(term in query_lower for term in ['evolucion', 'tendencia', 'historico', 'años', 'tiempo']):
            return 'time_series'
        
        # Comparaciones
        if any(term in query_lower for term in ['comparar', 'vs', 'versus']):
            return 'comparison_bar'
        
        # Ranking/Top
        if any(term in query_lower for term in ['top', 'ranking', 'mayor', 'menor']):
            return 'ranking_bar'
        
        # Por defecto según estructura
        if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
            if len(data) <= 10:
                return 'bar_chart'
            else:
                return 'horizontal_bar'
        
        return 'table'
    
    def create_visualization(self, data: pd.DataFrame, viz_type: str, 
                           query_info: Dict, channel: str = 'streamlit') -> Dict:
        """Crea la visualización apropiada"""
        
        config = self.channel_configs[channel]
        
        try:
            if viz_type == 'classification_pie':
                return self._create_classification_pie(data, query_info, config)
            elif viz_type == 'horizontal_bar':
                return self._create_horizontal_bar(data, query_info, config)
            elif viz_type == 'bar_chart':
                return self._create_bar_chart(data, query_info, config)
            elif viz_type == 'time_series':
                return self._create_time_series(data, query_info, config)
            elif viz_type == 'comparison_bar':
                return self._create_comparison_bar(data, query_info, config)
            elif viz_type == 'ranking_bar':
                return self._create_ranking_bar(data, query_info, config)
            elif viz_type == 'top_n_bar':
                return self._create_top_n_bar(data, query_info, config)
            elif viz_type == 'table':
                return self._create_table_image(data, query_info, config)
            else:
                return self._create_default_chart(data, query_info, config)
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Error generando visualización: {str(e)}",
                'image_data': None
            }
    
    def _create_classification_pie(self, data: pd.DataFrame, query_info: Dict, config: Dict) -> Dict:
        """Crea gráfico de torta para clasificación VIS/VIP/No VIS"""
        
        fig, ax = plt.subplots(figsize=config['figsize'], dpi=config['dpi'])
        
        # Buscar columna de clasificación
        classification_col = None
        value_col = None
        
        for col in data.columns:
            if any(term in col.lower() for term in ['vis', 'vip', 'clasificacion', 'tipo']):
                classification_col = col
            elif data[col].dtype in ['int64', 'float64']:
                value_col = col
        
        if classification_col and value_col:
            # Agrupar datos
            grouped = data.groupby(classification_col)[value_col].sum()
            
            # Colores específicos para VIS/VIP/No VIS
            colors = []
            for label in grouped.index:
                if 'vip' in str(label).lower():
                    colors.append(self.colors['vip'])
                elif 'vis' in str(label).lower() and 'no' not in str(label).lower():
                    colors.append(self.colors['vis'])
                elif 'no vis' in str(label).lower():
                    colors.append(self.colors['no_vis'])
                else:
                    colors.append(self.colors['primary'])
            
            # Crear gráfico
            wedges, texts, autotexts = ax.pie(grouped.values, labels=grouped.index, 
                                            autopct='%1.1f%%', colors=colors,
                                            startangle=90, textprops={'fontsize': 10})
            
            # Mejorar legibilidad
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
            
            ax.set_title(f'Clasificación de Vivienda - {datetime.now().year}', 
                        fontsize=14, fontweight='bold', pad=20)
            
        else:
            # Fallback a primer gráfico disponible
            return self._create_default_chart(data, query_info, config)
        
        return self._finalize_chart(fig, config, 'Clasificación de Vivienda por Tipo')
    
    def _create_horizontal_bar(self, data: pd.DataFrame, query_info: Dict, config: Dict) -> Dict:
        """Crea gráfico de barras horizontales"""
        
        fig, ax = plt.subplots(figsize=config['figsize'], dpi=config['dpi'])
        
        # Identificar columnas
        categorical_col = data.select_dtypes(include=['object']).columns[0]
        numeric_col = data.select_dtypes(include=[np.number]).columns[0]
        
        # Ordenar datos
        data_sorted = data.sort_values(numeric_col, ascending=True)
        
        # Crear gráfico
        bars = ax.barh(data_sorted[categorical_col], data_sorted[numeric_col], 
                      color=self.colors['primary'], alpha=0.8)
        
        # Agregar valores en las barras
        for i, bar in enumerate(bars):
            width = bar.get_width()
            ax.text(width + width*0.01, bar.get_y() + bar.get_height()/2, 
                   f'{width:,.0f}', ha='left', va='center', fontweight='bold')
        
        ax.set_xlabel(numeric_col.replace('_', ' ').title())
        ax.set_ylabel(categorical_col.replace('_', ' ').title())
        ax.set_title(f'{numeric_col.replace("_", " ").title()} por {categorical_col.replace("_", " ").title()}',
                    fontweight='bold', pad=20)
        
        plt.tight_layout()
        
        return self._finalize_chart(fig, config, f'Análisis por {categorical_col}')
    
    def _create_bar_chart(self, data: pd.DataFrame, query_info: Dict, config: Dict) -> Dict:
        """Crea gráfico de barras verticales"""
        
        fig, ax = plt.subplots(figsize=config['figsize'], dpi=config['dpi'])
        
        categorical_col = data.select_dtypes(include=['object']).columns[0]
        numeric_col = data.select_dtypes(include=[np.number]).columns[0]
        
        # Crear gráfico
        bars = ax.bar(data[categorical_col], data[numeric_col], 
                     color=self.colors['secondary'], alpha=0.8)
        
        # Agregar valores
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                   f'{height:,.0f}', ha='center', va='bottom', fontweight='bold')
        
        ax.set_xlabel(categorical_col.replace('_', ' ').title())
        ax.set_ylabel(numeric_col.replace('_', ' ').title())
        ax.set_title(f'{numeric_col.replace("_", " ").title()} por {categorical_col.replace("_", " ").title()}',
                    fontweight='bold', pad=20)
        
        # Rotar etiquetas si son muchas
        if len(data) > 5:
            plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        
        return self._finalize_chart(fig, config, f'Análisis por {categorical_col}')
    
    def _create_time_series(self, data: pd.DataFrame, query_info: Dict, config: Dict) -> Dict:
        """Crea gráfico de series de tiempo"""
        
        fig, ax = plt.subplots(figsize=config['figsize'], dpi=config['dpi'])
        
        # Buscar columna de fecha
        date_col = None
        for col in data.columns:
            if any(term in col.lower() for term in ['fecha', 'año', 'mes', 'time']):
                date_col = col
                break
        
        if date_col:
            numeric_col = data.select_dtypes(include=[np.number]).columns[0]
            
            ax.plot(data[date_col], data[numeric_col], 
                   marker='o', linewidth=2, markersize=6, 
                   color=self.colors['primary'])
            
            ax.set_xlabel(date_col.replace('_', ' ').title())
            ax.set_ylabel(numeric_col.replace('_', ' ').title())
            ax.set_title(f'Evolución Temporal - {numeric_col.replace("_", " ").title()}',
                        fontweight='bold', pad=20)
            
            # Agregar grid
            ax.grid(True, alpha=0.3)
            
        else:
            return self._create_default_chart(data, query_info, config)
        
        plt.tight_layout()
        
        return self._finalize_chart(fig, config, 'Evolución Temporal')
    
    def _create_ranking_bar(self, data: pd.DataFrame, query_info: Dict, config: Dict) -> Dict:
        """Crea gráfico de ranking (top N)"""
        
        # Tomar solo top 10
        data_top = data.head(10)
        
        fig, ax = plt.subplots(figsize=config['figsize'], dpi=config['dpi'])
        
        categorical_col = data_top.select_dtypes(include=['object']).columns[0]
        numeric_col = data_top.select_dtypes(include=[np.number]).columns[0]
        
        # Ordenar descendente
        data_sorted = data_top.sort_values(numeric_col, ascending=False)
        
        # Crear gradiente de colores
        colors = plt.cm.viridis(np.linspace(0, 1, len(data_sorted)))
        
        bars = ax.bar(range(len(data_sorted)), data_sorted[numeric_col], 
                     color=colors, alpha=0.8)
        
        # Configurar etiquetas
        ax.set_xticks(range(len(data_sorted)))
        ax.set_xticklabels(data_sorted[categorical_col], rotation=45, ha='right')
        
        # Agregar valores
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                   f'{height:,.0f}', ha='center', va='bottom', fontweight='bold')
        
        ax.set_ylabel(numeric_col.replace('_', ' ').title())
        ax.set_title(f'Top {len(data_sorted)} - {numeric_col.replace("_", " ").title()}',
                    fontweight='bold', pad=20)
        
        plt.tight_layout()
        
        return self._finalize_chart(fig, config, f'Ranking Top {len(data_sorted)}')
    
    def _create_table_image(self, data: pd.DataFrame, query_info: Dict, config: Dict) -> Dict:
        """Crea imagen de tabla cuando no es apropiado un gráfico"""
        
        fig, ax = plt.subplots(figsize=config['figsize'], dpi=config['dpi'])
        ax.axis('tight')
        ax.axis('off')
        
        # Limitar filas para legibilidad
        display_data = data.head(15)
        
        # Crear tabla
        table = ax.table(cellText=display_data.values,
                        colLabels=display_data.columns,
                        cellLoc='center',
                        loc='center')
        
        # Estilizar tabla
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.2, 1.5)
        
        # Colorear encabezados
        for i in range(len(display_data.columns)):
            table[(0, i)].set_facecolor(self.colors['primary'])
            table[(0, i)].set_text_props(weight='bold', color='white')
        
        ax.set_title('Resultados de Consulta LIVO', fontweight='bold', pad=20)
        
        return self._finalize_chart(fig, config, 'Tabla de Resultados')
    
    def _create_default_chart(self, data: pd.DataFrame, query_info: Dict, config: Dict) -> Dict:
        """Crea gráfico por defecto cuando no se puede determinar el tipo"""
        
        if len(data.columns) >= 2:
            return self._create_bar_chart(data, query_info, config)
        else:
            return self._create_table_image(data, query_info, config)
    
    def _finalize_chart(self, fig, config: Dict, title: str) -> Dict:
        """Finaliza el gráfico y lo convierte a formato apropiado"""
        
        # Agregar marca de agua CAMACOL
        fig.text(0.99, 0.01, 'CAMACOL - Sistema LIVO', 
                ha='right', va='bottom', fontsize=8, alpha=0.7,
                style='italic')
        
        # Guardar en buffer
        buffer = io.BytesIO()
        
        if config['format'] == 'jpeg':
            fig.savefig(buffer, format='jpeg', dpi=config['dpi'], 
                       bbox_inches='tight', quality=config.get('quality', 95))
        else:
            fig.savefig(buffer, format='png', dpi=config['dpi'], 
                       bbox_inches='tight', facecolor='white')
        
        buffer.seek(0)
        plt.close(fig)  # Liberar memoria
        
        # Verificar tamaño
        size_mb = len(buffer.getvalue()) / (1024 * 1024)
        
        return {
            'success': True,
            'image_data': buffer.getvalue(),
            'image_base64': base64.b64encode(buffer.getvalue()).decode(),
            'size_mb': size_mb,
            'title': title,
            'format': config['format']
        }
    
    def generate_for_channel(self, data: pd.DataFrame, query_info: Dict, 
                           channel: str = 'streamlit') -> Dict:
        """Genera visualización para canal específico"""
        
        if channel not in self.channel_configs:
            channel = 'streamlit'  # Default
        
        # Detectar tipo de visualización
        viz_type = self.detect_visualization_type(data, query_info)
        
        # Crear visualización
        result = self.create_visualization(data, viz_type, query_info, channel)
        
        # Agregar información del canal
        result['channel'] = channel
        result['viz_type'] = viz_type
        
        return result

# Funciones de integración para diferentes canales

def generate_streamlit_chart(data: pd.DataFrame, query_info: Dict) -> Dict:
    """Genera gráfico para Streamlit"""
    viz_system = LIVOVisualizationSystem()
    return viz_system.generate_for_channel(data, query_info, 'streamlit')

def generate_telegram_chart(data: pd.DataFrame, query_info: Dict) -> Dict:
    """Genera gráfico para Telegram"""
    viz_system = LIVOVisualizationSystem()
    return viz_system.generate_for_channel(data, query_info, 'telegram')

# PREPARADO PARA WHATSAPP BUSINESS - Descomentar cuando tengas acceso a API
def generate_whatsapp_chart(data: pd.DataFrame, query_info: Dict) -> Dict:
    """Genera gráfico para WhatsApp Business (preparado para implementación)"""
    viz_system = LIVOVisualizationSystem()
    return viz_system.generate_for_channel(data, query_info, 'whatsapp')

# Función de prueba
def test_visualization_system():
    """Prueba el sistema de visualización"""
    
    # Datos de ejemplo
    sample_data = pd.DataFrame({
        'ciudad': ['Bogotá', 'Medellín', 'Cali', 'Barranquilla', 'Cartagena'],
        'unidades_vis': [15420, 8750, 6230, 4180, 2950],
        'unidades_vip': [8200, 4500, 3100, 2200, 1800],
        'unidades_no_vis': [12300, 6800, 4900, 3200, 2100]
    })
    
    query_info = {
        'original_question': 'Unidades VIS por ciudad en 2025',
        'sql_generated': 'SELECT ciudad, SUM(unidades) FROM livo WHERE clasificacion = "VIS"'
    }
    
    # Probar diferentes canales
    channels = ['streamlit', 'telegram', 'whatsapp']  # WhatsApp preparado
    
    for channel in channels:
        print(f"\nProbando canal: {channel}")
        viz_system = LIVOVisualizationSystem()
        result = viz_system.generate_for_channel(sample_data, query_info, channel)
        
        if result['success']:
            print(f"✅ Visualización generada: {result['title']}")
            print(f"   Tipo: {result['viz_type']}")
            print(f"   Tamaño: {result['size_mb']:.2f} MB")
            print(f"   Formato: {result['format']}")
        else:
            print(f"❌ Error: {result['error']}")

if __name__ == "__main__":
    test_visualization_system()
