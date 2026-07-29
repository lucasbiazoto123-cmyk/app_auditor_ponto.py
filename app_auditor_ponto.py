import streamlit as st
import pandas as pd
import pdfplumber
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Auditor ITON", layout="wide")

# 1. CONEXÃO GOOGLE (DIÁRIO DE OBRAS)
@st.cache_resource
def carregar_diario():
    cred = json.loads(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(cred, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    client = gspread.authorize(creds)
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1oI9pPGXngdE1jrOaQGIRhHMfLnt_Evh9tN_9lQkLaOU/edit").worksheet("DIÁRIO DE OBRA")
    df = pd.DataFrame(sheet.get_all_records())
    # Renomear para colunas que o robô entende
    df.rename(columns={"1. Data": "Data", "1. Colaboradores Alocados (Marque todos que estiveram presentes no serviço)": "Colaborador"}, inplace=True)
    return df

# 2. LEITURA PRECISA DO PDF (Apenas linhas com data)
def ler_pdf_ponto(arquivo):
    registros = []
    with pdfplumber.open(arquivo) as pdf:
        nome_colaborador = "Desconhecido"
        for page in pdf.pages:
            text = page.extract_text()
            if "Colaborador" in text:
                for line in text.split('\n'):
                    if "Colaborador" in line:
                        nome_colaborador = line.split("Colaborador")[1].strip()
            
            for table in page.extract_tables():
                for row in table:
                    # Verifica se a primeira coluna parece uma data (DD/MM/AAAA)
                    if row[0] and "/" in str(row[0]) and len(str(row[0])) >= 10:
                        data = str(row[0]).split(',')[0].strip()
                        # Acha entrada e saída (ajuste conforme colunas do PDF)
                        # O PDF mostra horários nas últimas colunas da linha
                        entradas = [c for c in row if c and ":" in str(c)]
                        if len(entradas) >= 2:
                            registros.append({
                                "Data": data, 
                                "Colaborador": nome_colaborador, 
                                "Entrada": entradas[0], 
                                "Saida": entradas[-1]
                            })
    return registros

# 3. AUDITORIA
st.title("🕵️ Auditoria Real: Ponto vs Diário")
arquivos = st.file_uploader("Upload dos PDFs de Ponto", accept_multiple_files=True)

if arquivos and st.button("Executar Auditoria"):
    with st.spinner("Lendo PDFs e cruzando com o Diário..."):
        df_diario = carregar_diario()
        todos_pontos = []
        for f in arquivos:
            todos_pontos.extend(ler_pdf_ponto(f))
        df_ponto = pd.DataFrame(todos_pontos)
        
        # Cruzamento simples
        st.write("### Comparativo de Registros")
        
        # Limpeza para comparar nomes
        df_ponto['Colaborador'] = df_ponto['Colaborador'].str.strip()
        df_diario['Colaborador'] = df_diario['Colaborador'].str.strip()
        
        st.dataframe(df_ponto)
        
        st.write("### Divergências Encontradas")
        # Exemplo de lógica: listar quem está no ponto mas não no diário
        divergencias = df_ponto[~df_ponto.set_index(['Data', 'Colaborador']).index.isin(df_diario.set_index(['Data', 'Colaborador']).index)]
        st.dataframe(divergencias)
