import streamlit as st
import pandas as pd
import pdfplumber
from datetime import datetime
import json
import gspread
from google.oauth2.service_account import Credentials
import re

st.set_page_config(page_title="Auditor de Ponto", layout="wide")

# --- CONEXÃO GOOGLE ---
@st.cache_resource
def conectar_diario():
    try:
        credenciais_dict = json.loads(st.secrets["google_credentials"])
        creds = Credentials.from_service_account_info(credenciais_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        return client.open_by_url("https://docs.google.com/spreadsheets/d/1oI9pPGXngdE1jrOaQGIRhHMfLnt_Evh9tN_9lQkLaOU/edit").worksheet("DIÁRIO DE OBRA")
    except: return None

aba_diario = conectar_diario()

# --- FUNÇÃO DE LEITURA ROBUSTA ---
def extrair_dados_pdf(arquivo):
    lista_dias = []
    with pdfplumber.open(arquivo) as pdf:
        page = pdf.pages[0]
        text = page.extract_text()
        
        colab = "Desconhecido"
        for line in text.split('\n'):
            if "Colaborador" in line:
                colab = re.sub(r'^\d+\s+', '', line.split("Colaborador")[1].strip())
        
        # O padrão regex busca data DD/MM/AAAA e horários HH:MM
        for line in text.split('\n'):
            match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
            if match:
                data = match.group(1)
                horarios = re.findall(r'(\d{2}:\d{2})', line)
                
                if len(horarios) >= 2:
                    lista_dias.append({
                        "Data": data,
                        "Colaborador": colab,
                        "Entrada": horarios[0],
                        "Saida": horarios[-1]
                    })
    return lista_dias

# --- INTERFACE ---
st.title("🕵️ Auditor Inteligente")
arquivos = st.file_uploader("Arraste os PDFs:", type=['pdf'], accept_multiple_files=True)

if arquivos and st.button("🚀 Processar Auditoria"):
    todos_dados = []
    for f in arquivos:
        todos_dados.extend(extrair_dados_pdf(f))
    
    df_ponto = pd.DataFrame(todos_dados)
    st.success("Dados extraídos com sucesso!")
    st.dataframe(df_ponto)
