import streamlit as st
import pandas as pd
import pdfplumber
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Auditor ITON", layout="wide")

# 1. CONEXÃO GOOGLE
@st.cache_resource
def carregar_diario():
    cred = json.loads(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(cred, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    client = gspread.authorize(creds)
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1oI9pPGXngdE1jrOaQGIRhHMfLnt_Evh9tN_9lQkLaOU/edit").worksheet("DIÁRIO DE OBRA")
    df = pd.DataFrame(sheet.get_all_records())
    # Limpeza e Padronização
    df.columns = df.columns.str.strip()
    mapa = {"1. Data": "Data", "1. Colaboradores Alocados (Marque todos que estiveram presentes no serviço)": "Colaborador"}
    df.rename(columns=mapa, inplace=True)
    return df

# 2. LEITURA PDF (A prova de falhas)
def ler_pdf_ponto(arquivo):
    registros = []
    with pdfplumber.open(arquivo) as pdf:
        text = pdf.pages[0].extract_text()
        colab = "Desconhecido"
        # Busca nome do colaborador no texto
        if "Colaborador" in text:
            for line in text.split('\n'):
                if "Colaborador" in line:
                    colab = line.split("Colaborador")[1].strip()
        
        # Extração de linhas de data (formato DD/MM/AAAA)
        for line in text.split('\n'):
            if "/" in line and len(line) >= 10:
                partes = line.split()
                # Tenta achar a data (ex: 01/07/2026)
                for p in partes:
                    if "/" in p and len(p) == 10:
                        registros.append({
                            "Data": p[:10],
                            "Colaborador": colab,
                            "Entrada": "07:00", # Placeholder para ajuste
                            "Saida": "17:00"
                        })
    return registros

# 3. AUDITORIA
st.title("🕵️ Auditoria Real: Ponto vs Diário")
arquivos = st.file_uploader("Upload dos PDFs", accept_multiple_files=True)

if arquivos and st.button("Executar Auditoria"):
    df_diario = carregar_diario()
    
    todos_pontos = []
    for f in arquivos:
        todos_pontos.extend(ler_pdf_ponto(f))
    
    df_ponto = pd.DataFrame(todos_pontos)
    
    if 'Colaborador' not in df_ponto.columns:
        st.error("Não encontrei nomes nos PDFs. Verifique se o formato é legível.")
        st.stop()

    df_ponto['Colaborador'] = df_ponto['Colaborador'].str.strip()
    df_diario['Colaborador'] = df_diario['Colaborador'].str.strip()
    
    st.write("### Comparativo")
    st.dataframe(df_ponto)
    
    st.write("### Divergências")
    # Cruzamento simples garantido
    try:
        divergencias = df_ponto[~df_ponto.set_index(['Data', 'Colaborador']).index.isin(df_diario.set_index(['Data', 'Colaborador']).index)]
        st.dataframe(divergencias)
    except Exception as e:
        st.write("Erro no cruzamento:", e)
