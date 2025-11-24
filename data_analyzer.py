#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo de análisis de datos para Chatbot CAMACOL
Implementa dos estrategias con failover automático:
1. LangChain Pandas Agent (primaria)
2. PandasAI (respaldo)
"""

import pandas as pd
import os
from typing import Tuple, Any, Optional
import re

class DataAnalyzer:
    """Analizador de datos con múltiples estrategias"""
    
    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self.df = None
        self.sheet_names = []
        self.current_sheet = None
        
        # Flags para estrategias disponibles
        self.langchain_available = False
        self.pandasai_available = False
        
        # Intentar importar LangChain
        try:
            from langchain_experimental.agents import create_pandas_dataframe_agent
            from langchain_openai import ChatOpenAI
            self.create_pandas_dataframe_agent = create_pandas_dataframe_agent
            self.ChatOpenAI = ChatOpenAI
            self.langchain_available = True
            print("✅ LangChain disponible")
        except Exception as e:
            print(f"⚠️ LangChain no disponible: {e}")
        
        # Intentar importar PandasAI
        try:
            from pandasai import SmartDataframe
            from pandasai.llm import OpenAI as PandasAI_OpenAI
            self.SmartDataframe = SmartDataframe
            self.PandasAI_OpenAI = PandasAI_OpenAI
            self.pandasai_available = True
            print("✅ PandasAI disponible")
        except Exception as e:
            print(f"⚠️ PandasAI no disponible: {e}")
    
    def cargar_datos(self, sheet_name: Optional[str] = None) -> Tuple[bool, str]:
        """Carga datos del archivo Excel"""
        try:
            if not os.path.exists(self.excel_path):
                return False, f"❌ Archivo no encontrado: {self.excel_path}"
            
            # Obtener hojas disponibles
            excel_file = pd.ExcelFile(self.excel_path)
            self.sheet_names = excel_file.sheet_names
            
            # Seleccionar hoja
            if sheet_name and sheet_name in self.sheet_names:
                self.current_sheet = sheet_name
            else:
                self.current_sheet = self.sheet_names[0]
            
            # Cargar datos
            print(f"📂 Cargando hoja: {self.current_sheet}...")
            self.df = pd.read_excel(self.excel_path, sheet_name=self.current_sheet)
            
            info = f"✅ **Datos cargados exitosamente**\n\n"
            info += f"📊 **Hoja:** {self.current_sheet}\n"
            info += f"📈 **Filas:** {len(self.df):,}\n"
            info += f"📋 **Columnas:** {len(self.df.columns)}\n\n"
            info += f"**Primeras columnas:** {', '.join(self.df.columns.tolist()[:10])}"
            if len(self.df.columns) > 10:
                info += f"... (+{len(self.df.columns) - 10} más)"
            
            return True, info
            
        except Exception as e:
            return False, f"❌ Error al cargar datos: {str(e)}"
    
    def consultar(self, pregunta: str, api_key: str, estrategia: str = "auto") -> Tuple[bool, str, str]:
        """
        Ejecuta una consulta sobre los datos
        
        Args:
            pregunta: Pregunta del usuario
            api_key: API key de OpenAI
            estrategia: "langchain", "pandasai" o "auto" (failover)
            
        Returns:
            Tuple[bool, str, str]: (éxito, resultado, estrategia_usada)
        """
        if self.df is None:
            return False, "❌ No hay datos cargados", "none"
        
        # Estrategia automática con failover
        if estrategia == "auto":
            # Intentar LangChain primero
            if self.langchain_available:
                exito, resultado = self._consultar_langchain(pregunta, api_key)
                if exito:
                    return True, resultado, "langchain"
                print("⚠️ LangChain falló, intentando PandasAI...")
            
            # Fallback a PandasAI
            if self.pandasai_available:
                exito, resultado = self._consultar_pandasai(pregunta, api_key)
                if exito:
                    return True, resultado, "pandasai"
            
            return False, "❌ Todas las estrategias fallaron", "none"
        
        # Estrategia específica
        elif estrategia == "langchain":
            if not self.langchain_available:
                return False, "❌ LangChain no está disponible", "none"
            exito, resultado = self._consultar_langchain(pregunta, api_key)
            return exito, resultado, "langchain" if exito else "none"
        
        elif estrategia == "pandasai":
            if not self.pandasai_available:
                return False, "❌ PandasAI no está disponible", "none"
            exito, resultado = self._consultar_pandasai(pregunta, api_key)
            return exito, resultado, "pandasai" if exito else "none"
        
        else:
            return False, "❌ Estrategia no válida", "none"
    
    def _consultar_langchain(self, pregunta: str, api_key: str) -> Tuple[bool, str]:
        """Estrategia 1: LangChain Pandas Agent"""
        try:
            print("🔄 Usando LangChain Pandas Agent...")
            
            # Crear LLM
            llm = self.ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                openai_api_key=api_key
            )
            
            # Crear agente
            agent = self.create_pandas_dataframe_agent(
                llm,
                self.df,
                verbose=True,
                allow_dangerous_code=True,
                agent_type="openai-tools"
            )
            
            # Ejecutar consulta
            resultado = agent.invoke(pregunta)
            
            # Extraer respuesta
            if isinstance(resultado, dict) and 'output' in resultado:
                respuesta = resultado['output']
            else:
                respuesta = str(resultado)
            
            return True, f"🤖 **LangChain Agent:**\n\n{respuesta}"
            
        except Exception as e:
            print(f"❌ Error en LangChain: {e}")
            return False, f"Error: {str(e)}"
    
    def _consultar_pandasai(self, pregunta: str, api_key: str) -> Tuple[bool, str]:
        """Estrategia 2: PandasAI"""
        try:
            print("🔄 Usando PandasAI...")
            
            # Crear LLM de PandasAI
            llm = self.PandasAI_OpenAI(api_token=api_key)
            
            # Crear SmartDataframe
            sdf = self.SmartDataframe(self.df, config={"llm": llm})
            
            # Ejecutar consulta
            resultado = sdf.chat(pregunta)
            
            # Formatear resultado
            resultado_formateado = self._formatear_resultado(resultado)
            
            return True, f"🐼 **PandasAI:**\n\n{resultado_formateado}"
            
        except Exception as e:
            print(f"❌ Error en PandasAI: {e}")
            return False, f"Error: {str(e)}"
    
    def _formatear_resultado(self, resultado: Any) -> str:
        """Formatea el resultado para mostrarlo"""
        if resultado is None:
            return "Sin resultado"
        
        if isinstance(resultado, pd.DataFrame):
            if len(resultado) == 0:
                return "No se encontraron resultados"
            
            limite = min(len(resultado), 20)
            texto = f"**Total:** {len(resultado):,} resultados (mostrando {limite})\n\n"
            texto += resultado.head(limite).to_markdown(index=False)
            
            if len(resultado) > limite:
                texto += f"\n\n... y {len(resultado) - limite:,} filas más"
            
            return texto
        
        elif isinstance(resultado, pd.Series):
            if len(resultado) == 0:
                return "No se encontraron resultados"
            
            limite = min(len(resultado), 20)
            texto = f"**Total:** {len(resultado):,} resultados\n\n"
            texto += resultado.head(limite).to_markdown()
            
            if len(resultado) > limite:
                texto += f"\n\n... y {len(resultado) - limite:,} más"
            
            return texto
        
        elif isinstance(resultado, (int, float)):
            if isinstance(resultado, float):
                return f"**Resultado:** {resultado:,.2f}"
            else:
                return f"**Resultado:** {resultado:,}"
        
        elif isinstance(resultado, dict):
            texto = "**Resultado:**\n\n"
            for key, value in resultado.items():
                if isinstance(value, (int, float)):
                    texto += f"- **{key}:** {value:,.2f}\n"
                else:
                    texto += f"- **{key}:** {value}\n"
            return texto
        
        else:
            return f"{str(resultado)}"
    
    def obtener_info(self) -> str:
        """Obtiene información del dataset"""
        if self.df is None:
            return "❌ No hay datos cargados"
        
        info = f"📊 **Información del Dataset LIVO**\n\n"
        info += f"- **Hoja actual:** {self.current_sheet}\n"
        info += f"- **Total de filas:** {len(self.df):,}\n"
        info += f"- **Total de columnas:** {len(self.df.columns)}\n\n"
        
        info += "**Columnas disponibles:**\n"
        for i, col in enumerate(self.df.columns[:20], 1):
            dtype = str(self.df[col].dtype)
            info += f"{i}. `{col}` ({dtype})\n"
        
        if len(self.df.columns) > 20:
            info += f"\n... y {len(self.df.columns) - 20} columnas más\n"
        
        # Muestra de datos
        info += f"\n**Muestra de datos (primeras 3 filas):**\n\n"
        info += self.df.head(3).to_markdown(index=False)
        
        return info
    
    def obtener_estadisticas(self, columna: str) -> Tuple[bool, str]:
        """Obtiene estadísticas de una columna"""
        if self.df is None:
            return False, "❌ No hay datos cargados"
        
        if columna not in self.df.columns:
            return False, f"❌ Columna '{columna}' no encontrada"
        
        try:
            stats = self.df[columna].describe()
            resultado = f"📊 **Estadísticas de '{columna}':**\n\n"
            resultado += stats.to_markdown()
            return True, resultado
        except Exception as e:
            return False, f"❌ Error: {str(e)}"