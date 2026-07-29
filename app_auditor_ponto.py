import streamlit as st
import pandas as pd
from datetime import datetime
import json
import gspread
from google.oauth2.service_account import Credentials
import re

st.set_page_config(page_title="Auditor de Ponto - ITON", page_icon="🕵️", layout="wide")

@st.cache_resource
def conectar_diario():
    try:
        credenciais_dict = json.loads(st.secrets["google_credentials"])
        creds = Credentials.from_service_account_info(credenciais_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        return client.open_by_url("https://docs.google.com/spreadsheets/d/1oI9pPGXngdE1jrOaQGIRhHMfLnt_Evh9tN_9lQkLaOU/edit").worksheet("DIÁRIO DE OBRA")
    except: return None

aba_diario = conectar_diario()

def formatar_data(d):
    try:
        s = str(d).split(',')[0].strip()
        return datetime.strptime(s, "%d/%m/%Y").strftime("%d/%m/%Y")
    except: return str(d)

st.title("🕵️ Auditor Inteligente")
arquivos_ponto = st.file_uploader("Arraste os Excel:", accept_multiple_files=True)

if arquivos_ponto and st.button("🚀 Iniciar Auditoria"):
    with st.spinner("Processando..."):
        # 1. Pega Diário
        df_diario = pd.DataFrame(aba_diario.get_all_records())
        df_diario.columns = df_diario.columns.str.strip()
        df_diario = df_diario.rename(columns={"1. Data": "Data", "1. Colaboradores Alocados (Marque todos que estiveram presentes no serviço)": "Colaborador"})
        df_diario['Data'] = df_diario['Data'].apply(formatar_data)
        
        # 2. Pega Pontos
        lista_p = []
        for f in arquivos_ponto:
            df = pd.read_excel(f, header=None)
            # Tenta achar o nome do colaborador nas primeiras 15 linhas
            colab = "Desconhecido"
            for r in range(15):
                for c in range(4):
                    if "Colaborador" in str(df.iloc[r, c]):
                        colab = str(df.iloc[r, c+1]).replace("2589 ", "").strip()
            # Varre buscando "Dia"
            for r in range(len(df)):
                if str(df.iloc[r, 0]).strip() == "Dia":
                    for i in range(r+1, len(df)):
                        d = str(df.iloc[i, 0]).strip()
                        if d and d[0].isdigit():
                            horarios = [str(df.iloc[i, c]) for c in [11, 12, 13, 14] if len(str(df.iloc[i, c])) >= 5]
                            if horarios:
                                lista_p.append({"Data": formatar_data(d), "Colaborador": colab, "Entrada": horarios[0][:5], "Saida": horarios[-1][:5]})
        
        df_ponto = pd.DataFrame(lista_p)
        
        if df_ponto.empty:
            st.error("Não consegui ler os horários. Verifique se o formato do Excel é o mesmo do exemplo!")
            st.stop()
            
        # 3. Cruzamento Simples
        todos = sorted(list(set(df_diario['Colaborador'].unique()) | set(df_ponto['Colaborador'].unique())))
        for c in todos:
            with st.expander(f"👷 {c}"):
                p_colab = df_ponto[df_ponto['Colaborador'] == c]
                d_colab = df_diario[df_diario['Colaborador'] == c]
                st.write("Registros encontrados:", len(p_colab))
                st.dataframe(p_colab)
