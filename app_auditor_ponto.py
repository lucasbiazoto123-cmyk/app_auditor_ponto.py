import streamlit as st
import pandas as pd
from datetime import datetime
import json
import gspread
from google.oauth2.service_account import Credentials
import traceback
import re

st.set_page_config(page_title="Auditor de Ponto - ITON", page_icon="🕵️", layout="wide")

LISTA_COLABORADORES = [
    "Alexandre Balsani", "Danilo Alves de Oliveira", "Diego de Faria Santos", 
    "Diego Sergio Simão", "Evane Jacinto Pacheco", "Flavio Mateus", 
    "Francisco Damazio Moraes", "Hebert Deivison Silveira Pereira", 
    "Jeferson Miranda do Cabo", "Jefferson Santos Nascimento", 
    "Jonathan Araújo Mendonça", "Jorge Esbrisse Martins", 
    "Kauai Darlei dos Santos Vieira", "Marco Aurelio Jesus da Costa", 
    "Paulo Cesar de Souza", "Rafael Damaciano", 
    "Robinson William dos Santos Machado", "Kauã Rodrigues Roza", "Niuleno Alves de Souza"
]
LISTA_COLABORADORES.sort()

st.title("🕵️ Auditor Inteligente: Ponto vs Diário")
st.markdown("Arraste os relatórios de ponto da equipe. O sistema cruzará os dados e filtrará apenas o período enviado.")

@st.cache_resource
def conectar_diario():
    try:
        credenciais_dict = json.loads(st.secrets["google_credentials"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(credenciais_dict, scopes=scopes)
        client = gspread.authorize(creds)
        planilha = client.open_by_url("https://docs.google.com/spreadsheets/d/1oI9pPGXngdE1jrOaQGIRhHMfLnt_Evh9tN_9lQkLaOU/edit?gid=1342849862#gid=1342849862").worksheet("DIÁRIO DE OBRA")
        return planilha
    except Exception as e:
        st.error("🚨 Erro de conexão com o Diário de Obras.")
        return None

aba_diario = conectar_diario()

def calcular_diferenca_minutos(h1, h2):
    try:
        t1 = datetime.strptime(str(h1).strip()[:5], "%H:%M")
        t2 = datetime.strptime(str(h2).strip()[:5], "%H:%M")
        return abs((t1 - t2).total_seconds() / 60)
    except: return 999

def formatar_data(data_raw):
    try:
        data_str = str(data_raw).split(",")[0].split(" ")[0].strip()
        return data_str
    except: return str(data_raw)

arquivos_ponto = st.file_uploader("Arraste os arquivos Excel:", type=['xlsx', 'xls'], accept_multiple_files=True)

if arquivos_ponto and st.button("🚀 Iniciar Auditoria Completa"):
    with st.spinner("Processando..."):
        df_diario = pd.DataFrame(aba_diario.get_all_records())
        df_diario.columns = df_diario.columns.str.strip()
        mapeamento = {"1. Data": "Data", "1. Colaboradores Alocados (Marque todos que estiveram presentes no serviço)": "Colaborador", "2. Supervisor Responsável": "Líder", "3. Cliente / Obra (Selecione a obra atual)": "Obra", "1. Horário de Início das Atividades": "Hora Início", "2. Horário de Término das Atividades": "Hora Término"}
        df_diario.rename(columns=mapeamento, inplace=True)
        df_diario['Data'] = df_diario['Data'].apply(formatar_data)
        
        registros_ponto = []
        for arquivo in arquivos_ponto:
            df_raw = pd.read_excel(arquivo, header=None)
            colaborador = "Desconhecido"
            for r in range(15):
                for c in range(4):
                    if str(df_raw.iloc[r, c]).strip() == "Colaborador":
                        colaborador = re.sub(r'^\d+\s+', '', str(df_raw.iloc[r, c+1])).strip()
            
            for linha in range(len(df_raw)):
                if str(df_raw.iloc[linha, 0]).strip() == "Dia":
                    for l in range(linha + 1, len(df_raw)):
                        raw_date = str(df_raw.iloc[l, 0]).strip()
                        if raw_date and raw_date[0].isdigit():
                            horarios = [str(df_raw.iloc[l, c]).strip()[:5] for c in [11, 12, 13, 14] if len(str(df_raw.iloc[l, c])) >= 5]
                            if horarios:
                                registros_ponto.append({"Data": formatar_data(raw_date), "Colaborador": colaborador, "Entrada_Ponto": horarios[0], "Saida_Ponto": horarios[-1]})
        
        df_ponto = pd.DataFrame(registros_ponto)
        df_ponto['Data'] = df_ponto['Data'].apply(formatar_data)
        
        # Filtro de Mês inteligente baseado nos arquivos carregados
        meses_validos = pd.to_datetime(df_ponto['Data'], dayfirst=True).dt.to_period('M').unique()
        df_diario = df_diario[pd.to_datetime(df_diario['Data'], dayfirst=True).dt.to_period('M').isin(meses_validos)]

        # Cruzamento
        todos_cols = sorted(list(set(df_diario['Colaborador'].unique()).union(set(df_ponto['Colaborador'].unique()))))
        datas = sorted(list(set(df_diario['Data'].unique()).union(set(df_ponto['Data'].unique()))))

        for colab in todos_cols:
            erros = {"diario": [], "ponto": [], "div": []}
            for d in datas:
                d_diario = df_diario[(df_diario['Data'] == d) & (df_diario['Colaborador'] == colab)]
                d_ponto = df_ponto[(df_ponto['Data'] == d) & (df_ponto['Colaborador'] == colab)]
                
                if not d_ponto.empty and d_diario.empty:
                    erros["diario"].append(f"Dia {d}")
                elif not d_diario.empty and d_ponto.empty:
                    erros["ponto"].append(f"Dia {d}")
                elif not d_diario.empty and not d_ponto.empty:
                    ent_d, sai_d = str(d_diario.iloc[0]['Hora Início']), str(d_diario.iloc[0]['Hora Término'])
                    ent_p, sai_p = d_ponto.iloc[0]['Entrada_Ponto'], d_ponto.iloc[0]['Saida_Ponto']
                    if calcular_diferenca_minutos(ent_p, ent_d) > 5 or calcular_diferenca_minutos(sai_p, sai_d) > 5:
                        erros["div"].append(f"Dia {d}: Ponto {ent_p}-{sai_p} vs Diário {ent_d}-{sai_d}")

            if any(erros.values()):
                with st.expander(f"👷 {colab}", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    c1.error(f"❌ Falta Diário: {', '.join(erros['diario']) if erros['diario'] else 'OK'}")
                    c2.warning(f"👻 Falta Ponto: {', '.join(erros['ponto']) if erros['ponto'] else 'OK'}")
                    c3.info(f"⏰ Divergência: {', '.join(erros['div']) if erros['div'] else 'OK'}")
