#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integración del sistema de visualización con Streamlit
"""

import streamlit as st
import pandas as pd
from io import BytesIO
import base64
from typing import Dict, Optional

def display_chart_in_streamlit(chart_data: Dict) -> None:
    """Muestra gráfico en Streamlit"""
    
    if not chart_data or not chart_data.get('success', False):
        if chart_data and chart_data.get('error'):
            st.error(f"Error generando gráfico: {chart_data['error']}")
        return
    
    # Mostrar título del gráfico
    if chart_data.get('title'):
        st.subheader(f"📊 {chart_data['title']}")
    
    # Mostrar gráfico
    if chart_data.get('image_data'):
        st.image(
            BytesIO(chart_data['image_data']),
            caption=f"Tipo: {chart_data.get('viz_type', 'N/A')} | "
                   f"Tamaño: {chart_data.get('size_mb', 0):.2f} MB",
            use_column_width=True
        )
    
    # Información adicional
    with st.expander("ℹ️ Información del gráfico"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Tipo de visualización:** {chart_data.get('viz_type', 'N/A')}")
            st.write(f"**Canal:** {chart_data.get('channel', 'streamlit')}")
            st.write(f"**Formato:** {chart_data.get('format', 'png').upper()}")
        
        with col2:
            st.write(f"**Tamaño:** {chart_data.get('size_mb', 0):.2f} MB")
            if chart_data.get('image_base64'):
                st.download_button(
                    label="📥 Descargar gráfico",
                    data=base64.b64decode(chart_data['image_base64']),
                    file_name=f"grafico_livo_{chart_data.get('viz_type', 'chart')}.{chart_data.get('format', 'png')}",
                    mime=f"image/{chart_data.get('format', 'png')}"
                )

def add_chart_controls() -> Dict:
    """Agrega controles para configurar gráficos"""
    
    with st.sidebar:
        st.markdown("### 📊 Configuración de Gráficos")
        
        # Control para habilitar/deshabilitar gráficos
        generate_charts = st.checkbox(
            "Generar gráficos automáticamente",
            value=True,
            help="Genera visualizaciones cuando sea apropiado"
        )
        
        # Tipo de gráfico preferido (para implementación futura)
        chart_preference = st.selectbox(
            "Tipo de gráfico preferido",
            ["Automático", "Barras", "Líneas", "Torta", "Tabla"],
            help="El sistema elegirá automáticamente el más apropiado"
        )
        
        # Canal de optimización
        channel = st.selectbox(
            "Optimizar para",
            ["streamlit", "telegram"],  # whatsapp comentado
            help="Optimiza el gráfico para el canal seleccionado"
        )
        
        return {
            'generate_charts': generate_charts,
            'chart_preference': chart_preference.lower(),
            'channel': channel
        }

def show_chart_gallery(charts_history: list) -> None:
    """Muestra galería de gráficos generados"""
    
    if not charts_history:
        st.info("No hay gráficos generados aún.")
        return
    
    st.markdown("### 🖼️ Galería de Gráficos")
    
    # Mostrar en grid
    cols = st.columns(3)
    
    for i, chart_data in enumerate(charts_history[-9:]):  # Últimos 9
        with cols[i % 3]:
            if chart_data.get('success') and chart_data.get('image_data'):
                st.image(
                    BytesIO(chart_data['image_data']),
                    caption=chart_data.get('title', f'Gráfico {i+1}'),
                    use_column_width=True
                )
                
                # Botón para ver detalles
                if st.button(f"Ver detalles", key=f"detail_{i}"):
                    st.session_state[f'show_detail_{i}'] = True
                
                # Mostrar detalles si está seleccionado
                if st.session_state.get(f'show_detail_{i}', False):
                    st.write(f"**Tipo:** {chart_data.get('viz_type')}")
                    st.write(f"**Tamaño:** {chart_data.get('size_mb', 0):.2f} MB")

# Funciones para integración con Telegram (comentadas para implementación futura)

def prepare_chart_for_telegram(chart_data: Dict) -> Optional[BytesIO]:
    """Prepara gráfico para envío por Telegram"""
    
    if not chart_data or not chart_data.get('success', False):
        return None
    
    if chart_data.get('image_data'):
        return BytesIO(chart_data['image_data'])
    
    return None

# COMENTADO PARA IMPLEMENTACIÓN FUTURA - WhatsApp Business
"""
def prepare_chart_for_whatsapp(chart_data: Dict) -> Optional[Dict]:
    '''Prepara gráfico para WhatsApp Business API'''
    
    if not chart_data or not chart_data.get('success', False):
        return None
    
    # Verificar tamaño para WhatsApp (máximo 5MB)
    if chart_data.get('size_mb', 0) > 5:
        return {
            'error': 'Gráfico muy grande para WhatsApp (máximo 5MB)',
            'size_mb': chart_data.get('size_mb', 0)
        }
    
    return {
        'media_type': 'image',
        'media_data': chart_data.get('image_data'),
        'caption': chart_data.get('title', 'Gráfico LIVO'),
        'filename': f"livo_chart.{chart_data.get('format', 'jpeg')}"
    }

def send_chart_whatsapp(chart_data: Dict, phone_number: str, whatsapp_api_token: str):
    '''Envía gráfico por WhatsApp Business API (implementación futura)'''
    
    # Esta función se implementará cuando se tenga acceso a WhatsApp Business API
    prepared_chart = prepare_chart_for_whatsapp(chart_data)
    
    if not prepared_chart or prepared_chart.get('error'):
        return False, prepared_chart.get('error', 'Error preparando gráfico')
    
    # TODO: Implementar llamada a WhatsApp Business API
    # headers = {
    #     'Authorization': f'Bearer {whatsapp_api_token}',
    #     'Content-Type': 'application/json'
    # }
    # 
    # payload = {
    #     'messaging_product': 'whatsapp',
    #     'to': phone_number,
    #     'type': 'image',
    #     'image': {
    #         'link': 'data:image/jpeg;base64,' + base64.b64encode(prepared_chart['media_data']).decode(),
    #         'caption': prepared_chart['caption']
    #     }
    # }
    # 
    # response = requests.post(
    #     'https://graph.facebook.com/v17.0/YOUR_PHONE_NUMBER_ID/messages',
    #     headers=headers,
    #     json=payload
    # )
    
    return True, "Gráfico enviado por WhatsApp (simulado)"
"""

# Funciones de utilidad

def get_chart_stats(charts_history: list) -> Dict:
    """Obtiene estadísticas de gráficos generados"""
    
    if not charts_history:
        return {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'avg_size_mb': 0,
            'most_common_type': 'N/A'
        }
    
    successful = [c for c in charts_history if c.get('success', False)]
    failed = len(charts_history) - len(successful)
    
    # Tamaño promedio
    sizes = [c.get('size_mb', 0) for c in successful if c.get('size_mb')]
    avg_size = sum(sizes) / len(sizes) if sizes else 0
    
    # Tipo más común
    types = [c.get('viz_type') for c in successful if c.get('viz_type')]
    most_common = max(set(types), key=types.count) if types else 'N/A'
    
    return {
        'total': len(charts_history),
        'successful': len(successful),
        'failed': failed,
        'success_rate': len(successful) / len(charts_history) * 100 if charts_history else 0,
        'avg_size_mb': avg_size,
        'most_common_type': most_common
    }

def show_chart_stats(charts_history: list) -> None:
    """Muestra estadísticas de gráficos en Streamlit"""
    
    stats = get_chart_stats(charts_history)
    
    st.markdown("### 📈 Estadísticas de Gráficos")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total generados", stats['total'])
    
    with col2:
        st.metric("Exitosos", stats['successful'])
    
    with col3:
        st.metric("Tasa de éxito", f"{stats['success_rate']:.1f}%")
    
    with col4:
        st.metric("Tamaño promedio", f"{stats['avg_size_mb']:.2f} MB")
    
    if stats['most_common_type'] != 'N/A':
        st.write(f"**Tipo más común:** {stats['most_common_type']}")

# Ejemplo de uso en app.py
def example_integration():
    """Ejemplo de cómo integrar en app.py"""
    
    # En el archivo app.py, agregar:
    """
    # Importar al inicio
    from streamlit_integration import display_chart_in_streamlit, add_chart_controls
    
    # En la función principal, después de obtener la respuesta LIVO:
    
    # Controles de gráficos
    chart_config = add_chart_controls()
    
    # Consulta LIVO con gráficos
    if chart_config['generate_charts']:
        exito, respuesta, chart_data = livo_system.consultar(
            pregunta, 
            obtener_respuesta_ia, 
            usuario="streamlit_user",
            generate_chart=True,
            channel=chart_config['channel']
        )
    else:
        exito, respuesta = livo_system.consultar(pregunta, obtener_respuesta_ia)
        chart_data = None
    
    # Mostrar respuesta
    st.write(respuesta)
    
    # Mostrar gráfico si existe
    if chart_data:
        display_chart_in_streamlit(chart_data)
        
        # Guardar en historial de gráficos
        if 'charts_history' not in st.session_state:
            st.session_state.charts_history = []
        st.session_state.charts_history.append(chart_data)
    """

if __name__ == "__main__":
    st.title("🧪 Prueba de Integración de Gráficos")
    st.write("Este archivo contiene las funciones de integración.")
    st.write("Importar en app.py para usar las funcionalidades.")
    
    # Mostrar ejemplo de configuración
    st.code(example_integration.__doc__, language='python')
