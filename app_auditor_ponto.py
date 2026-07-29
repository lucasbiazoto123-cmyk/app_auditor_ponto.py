import streamlit as st
import pandas as pd
import pdfplumber
import json
import gspread
from google.oauth2.service_account import Credentials
import re

st.set_page_config(page_title="Auditor ITON", layout="wide")

# --- CONEXÃO GOOGLE ---
@st.cache_resource
def carregar_diario():
    cred = json.loads(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(cred, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    client = gspread.authorize(creds)
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1oI9pPGXngdE1jrOaQGIRhHMfLnt_Evh9tN_9lQkLaOU/edit").worksheet("DIÁRIO DE OBRA")
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = df.columns.str.strip()
    mapa = {
        "1. Data": "Data", 
        "1. Colaboradores Alocados (Marque todos que estiveram presentes no serviço)": "Colaborador",
        "1. Horário de Início das Atividades": "Inicio_Diario",
        "2. Horário de Término das Atividades": "Fim_Diario"
    }
    df.rename(columns=mapa, inplace=True)
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True).dt.strftime('%d/%m/%Y')
    return df

# --- EXTRAÇÃO PDF ---
def extrair_pdf(arquivo):
    registros = []
    with pdfplumber.open(arquivo) as pdf:
        text = pdf.pages[0].extract_text()
        colab = next((line.split("Colaborador")[1].strip() for line in text.split('\n') if "Colaborador" in line), "Desconhecido")
        colab = re.sub(r'^\d+\s+', '', colab).strip()
        
        for line in text.split('\n'):
            if re.match(r'\d{2}/\d{2}/\d{4}', line):
                partes = line.split()
                data = partes[0].replace(',', '')
                # Busca horários na linha (assumindo formato HH:MM)
                horas = [p for p in partes if re.match(r'\d{2}:\d{2}', p)]
                if len(horas) >= 2:
                    registros.append({"Data": data, "Colaborador": colab, "Entrada": horas[0], "Saida": horas[-1]})
    return registros

# --- AUDITORIA ---
st.title("🕵️ Auditoria Real: Ponto vs Diário")
arquivos = st.file_uploader("Upload PDFs de Ponto", accept_multiple_files=True)

if arquivos and st.button("Executar Auditoria"):
    df_diario = carregar_diario()
    todos_pontos = pd.DataFrame([item for f in arquivos for item in extrair_pdf(f)])
    
    # Cruzamento
    st.markdown("### 📊 Relatório de Auditoria")
    colab_lista = sorted(list(set(df_diario['Colaborador'].unique()) | set(todos_pontos['Colaborador'].unique())))
    
    for colab in colab_lista:
        diario_c = df_diario[df_diario['Colaborador'] == colab]
        ponto_c = todos_pontos[todos_pontos['Colaborador'] == colab]
        
        erros = []
        # Falta no Diário
        for _, p in ponto_c.iterrows():
            if diario_c[diario_c['Data'] == p['Data']].empty:
                erros.append(f"❌ {p['Data']}: Bateu ponto, mas não está no Diário.")
        # Falta no Ponto
        for _, d in diario_c.iterrows():
            if ponto_c[ponto_c['Data'] == d['Data']].empty:
                erros.append(f"👻 {d['Data']}: Está no Diário, mas não bateu ponto.")
        
        if erros:
            with st.expander(f"👷 {colab} ({len(erros)} pendências)"):
                for erro in erros: st.write(erro)
