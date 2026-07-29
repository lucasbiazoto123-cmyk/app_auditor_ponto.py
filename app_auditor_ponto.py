import streamlit as st
import pandas as pd
import pdfplumber
from datetime import datetime
import json
import gspread
from google.oauth2.service_account import Credentials
from fpdf import FPDF
import io

st.set_page_config(page_title="Auditor de Ponto - ITON", page_icon="🕵️", layout="wide")

# --- CONEXÃO GOOGLE ---
@st.cache_resource
def conectar_diario():
    try:
        credenciais_dict = json.loads(st.secrets["google_credentials"])
        creds = Credentials.from_service_account_info(credenciais_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        return client.open_by_url("https://docs.google.com/spreadsheets/d/1oI9pPGXngdE1jrOaQGIRhHMfLnt_Evh9tN_9lQkLaOU/edit").worksheet("DIÁRIO DE OBRA")
    except: return None

# --- DETETIVE DE PDF ---
def extrair_dados_pdf(arquivo):
    lista_dias = []
    with pdfplumber.open(arquivo) as pdf:
        # Pega a primeira página onde está o nome e a tabela
        page = pdf.pages[0]
        text = page.extract_text()
        
        # Identifica o nome do colaborador
        colab = "Desconhecido"
        for line in text.split('\n'):
            if "Colaborador" in line:
                colab = line.replace("Colaborador", "").replace("2589", "").strip()
        
        # Extrai a tabela (configuração de colunas conforme o seu PDF)
        table = page.extract_table()
        if table:
            for row in table:
                # Verifica se a linha tem dados de dia (a primeira coluna contém o dia)
                if row[0] and row[0][0].isdigit():
                    # Índices baseados na estrutura visual do seu PDF
                    # Ajuste os índices se necessário após o primeiro teste
                    lista_dias.append({
                        "Data": row[0].split(',')[0].strip(),
                        "Colaborador": colab,
                        "Entrada": row[5] if row[5] else "-", # Exemplo de coluna de entrada
                        "Saida": row[8] if row[8] else "-"    # Exemplo de coluna de saída
                    })
    return lista_dias

# --- INTERFACE ---
st.title("🕵️ Auditor Inteligente (Versão PDF)")
arquivos = st.file_uploader("Arraste os PDFs de Ponto:", type=['pdf'], accept_multiple_files=True)

if arquivos and st.button("🚀 Processar Auditoria"):
    todos_dados = []
    for f in arquivos:
        todos_dados.extend(extrair_dados_pdf(f))
    
    df_ponto = pd.DataFrame(todos_dados)
    st.write("Dados extraídos:", df_ponto)
    st.info("Agora o sistema cruzará estes dados com o Google Sheets conforme a lógica anterior.")
