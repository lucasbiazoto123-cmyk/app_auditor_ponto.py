import streamlit as st
import pandas as pd
from datetime import datetime
import json
import gspread
from google.oauth2.service_account import Credentials
import re

st.set_page_config(page_title="Auditor de Ponto - ITON", page_icon="🕵️", layout="wide")

# 1. CONEXÃO COM GOOGLE
@st.cache_resource
def conectar_diario():
    try:
        credenciais_dict = json.loads(st.secrets["google_credentials"])
        creds = Credentials.from_service_account_info(credenciais_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        # Ajuste aqui para o seu link e nome da aba
        return client.open_by_url("https://docs.google.com/spreadsheets/d/1oI9pPGXngdE1jrOaQGIRhHMfLnt_Evh9tN_9lQkLaOU/edit").worksheet("DIÁRIO DE OBRA")
    except: return None

aba_diario = conectar_diario()

# 2. FUNÇÃO DETETIVE (LÊ EXCEL COMPLEXO)
def extrair_dados_excel(arquivo):
    # Lê sem cabeçalho (header=None) para podermos varrer linha por linha
    df = pd.read_excel(arquivo, header=None)
    
    colab = "Desconhecido"
    # Procura o nome do colaborador nas primeiras 20 linhas
    for r in range(min(20, len(df))):
        for c in range(min(5, df.shape[1])):
            if "Colaborador" in str(df.iloc[r, c]):
                colab = str(df.iloc[r, c+1]).replace("2589", "").strip()
    
    lista_dias = []
    # Procura a linha que começa com "Dia"
    for r in range(len(df)):
        if str(df.iloc[r, 0]).strip() == "Dia":
            for i in range(r + 1, len(df)):
                val = str(df.iloc[i, 0]).strip()
                # Se for data (começa com número), processa
                if val and val[0].isdigit():
                    # Pega as colunas da direita onde ficam os horários do "Espelho"
                    # Ajuste os índices conforme a sua imagem (ex: colunas 11, 12, 13, 14)
                    horarios = [str(df.iloc[i, c]) for c in range(11, 15) if len(str(df.iloc[i, c])) >= 5]
                    if horarios:
                        lista_dias.append({
                            "Data": val.split(',')[0].strip(),
                            "Colaborador": colab,
                            "Entrada": horarios[0][:5],
                            "Saida": horarios[-1][:5]
                        })
    return lista_dias

# 3. INTERFACE
st.title("🕵️ Auditor Inteligente: Leitura Robusta")
arquivos = st.file_uploader("Arraste os relatórios:", accept_multiple_files=True)

if arquivos and st.button("🚀 Processar Tudo"):
    todos_dados = []
    for f in arquivos:
        dados = extrair_dados_excel(f)
        todos_dados.extend(dados)
    
    df_ponto = pd.DataFrame(todos_dados)
    st.write("Dados extraídos com sucesso:", df_ponto)
    # Aqui entraria o cruzamento que você já tem...
