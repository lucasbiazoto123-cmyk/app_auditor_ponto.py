import streamlit as st
import pandas as pd
import pdfplumber
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re
import traceback

st.set_page_config(page_title="Auditor de Ponto - ITON", page_icon="🕵️", layout="wide")

st.title("🕵️ Auditor Inteligente: Ponto vs Diário")
st.markdown("Arraste os arquivos em **PDF** do relógio de ponto. O sistema vai extrair os horários, cruzar com o Diário de Obras oficial e listar apenas as pendências.")

@st.cache_resource
def conectar_diario():
    try:
        credenciais_dict = json.loads(st.secrets["google_credentials"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(credenciais_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Acessa a planilha oficial
        LINK_DA_PLANILHA = "https://docs.google.com/spreadsheets/d/1oI9pPGXngdE1jrOaQGIRhHMfLnt_Evh9tN_9lQkLaOU/edit?gid=1342849862#gid=1342849862"
        planilha = client.open_by_url(LINK_DA_PLANILHA).worksheet("DIÁRIO DE OBRA")
        return planilha
    except Exception as e:
        st.error("🚨 Erro de conexão com o Diário de Obras.")
        st.code(traceback.format_exc())
        return None

aba_diario = conectar_diario()

def extrair_dados_pdf(arquivo):
    registros = []
    try:
        with pdfplumber.open(arquivo) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"
            
            if not text.strip(): return registros
            
            # Caça o nome do Colaborador no texto
            colab = "Desconhecido"
            for line in text.split('\n'):
                if "Colaborador" in line:
                    # Remove o nome "Colaborador", números de matrícula e limpa espaços
                    nome_sujo = line.replace("Colaborador", "")
                    colab = re.sub(r'^\d+\s+', '', nome_sujo).strip()
                    break
            
            # Caça as datas e horários
            for line in text.split('\n'):
                # Busca uma data no formato DD/MM/AAAA
                match_data = re.search(r'(\d{2}/\d{2}/\d{4})', line)
                if match_data:
                    data_str = match_data.group(1)
                    
                    # Busca todos os horários (HH:MM) na mesma linha
                    tempos = re.findall(r'\d{2}:\d{2}', line)
                    if tempos:
                        # O menor horário costuma ser a entrada, e o maior a saída do dia
                        entrada = min(tempos)
                        saida = max(tempos)
                        registros.append({
                            "Data_Str": data_str,
                            "Colaborador": colab,
                            "Entrada": entrada,
                            "Saida": saida
                        })
    except Exception as e:
        st.error(f"Erro ao processar o PDF {arquivo.name}: {e}")
    
    return registros

st.divider()
st.markdown("### 📥 1. Inserir Relatórios de Ponto (PDF)")
arquivos_ponto = st.file_uploader("Selecione os arquivos em PDF", type=['pdf'], accept_multiple_files=True)

if arquivos_ponto:
    st.success(f"✅ {len(arquivos_ponto)} arquivo(s) carregado(s) na memória!")
    
    if st.button("🚀 Iniciar Auditoria", type="primary", use_container_width=True):
        if aba_diario is None:
            st.error("Conexão com Google Sheets falhou.")
            st.stop()
            
        with st.spinner("Lendo relatórios, extraindo horários e cruzando com o Diário de Obras..."):
            
            dados_diario_bruto = aba_diario.get_all_records()
            df_diario = pd.DataFrame(dados_diario_bruto)
            
            if df_diario.empty:
                st.error("Diário de obras vazio.")
                st.stop()
                
            # Limpa colunas invisíveis e padroniza
            df_diario.columns = df_diario.columns.str.strip()
            mapeamento = {
                "1. Data": "Data",
                "1. Colaboradores Alocados (Marque todos que estiveram presentes no serviço)": "Colaborador",
                "2. Supervisor Responsável": "Líder",
                "3. Cliente / Obra (Selecione a obra atual)": "Obra",
                "1. Horário de Início das Atividades": "Hora Início",
                "2. Horário de Término das Atividades": "Hora Término",
                "Colaboradores": "Colaborador",
                "Supervisor": "Líder",
                "Início": "Hora Início",
                "Término": "Hora Término"
            }
            df_diario.rename(columns=mapeamento, inplace=True)
            
            # A GRANDE SACADA: Separar os nomes grudados ("João, Maria, José") em linhas únicas
            if 'Colaborador' in df_diario.columns:
                df_diario['Colaborador'] = df_diario['Colaborador'].astype(str).str.split(',')
                df_diario = df_diario.explode('Colaborador')
                df_diario['Colaborador'] = df_diario['Colaborador'].str.strip()
            
            # Formata a data para objeto datetime real
            df_diario['Data_Temp'] = pd.to_datetime(df_diario['Data'], format='%d/%m/%Y', errors='coerce')
            
            todos_registros = []
            for arquivo in arquivos_ponto:
                todos_registros.extend(extrair_dados_pdf(arquivo))
                
            df_ponto = pd.DataFrame(todos_registros)
            
            if df_ponto.empty:
                st.error("Não consegui extrair dados dos PDFs. Verifique o formato.")
                st.stop()
                
            df_ponto['Data_Temp'] = pd.to_datetime(df_ponto['Data_Str'], format='%d/%m/%Y', errors='coerce')
            
            # O FILTRO INTELIGENTE: Pega apenas os meses presentes nos PDFs
            meses_ponto = df_ponto['Data_Temp'].dropna().dt.to_period('M').unique()
            df_diario = df_diario[df_diario['Data_Temp'].dt.to_period('M').isin(meses_ponto)]
            
            relatorio = {}
            # Pega lista única de pessoas de ambos os arquivos (já separados)
            colaboradores = sorted(list(set(df_diario['Colaborador'].dropna().unique()) | set(df_ponto['Colaborador'].dropna().unique())))
            
            for colab in colaboradores:
                if colab in ["", "nan", "Desconhecido"]: continue
                
                # Separa os dados apenas dessa pessoa
                diario_c = df_diario[df_diario['Colaborador'] == colab]
                ponto_c = df_ponto[df_ponto['Colaborador'] == colab]
                
                # Lista todos os dias que ela apareceu no mês (seja no ponto ou no diário)
                datas_trabalhadas = sorted(list(set(diario_c['Data_Temp'].dropna()) | set(ponto_c['Data_Temp'].dropna())))
                
                erros_falta_diario = []
                erros_falta_ponto = []
                erros_horario = []
                
                for d in datas_trabalhadas:
                    d_str = d.strftime("%d/%m/%Y")
                    in_diario = not diario_c[diario_c['Data_Temp'] == d].empty
                    in_ponto = not ponto_c[ponto_c['Data_Temp'] == d].empty
                    
                    if in_ponto and not in_diario:
                        erros_falta_diario.append(f"Dia {d_str} (Não foi lançado por nenhum Líder)")
                        
                    elif in_diario and not in_ponto:
                        lider = diario_c[diario_c['Data_Temp'] == d]['Líder'].iloc[0]
                        obra = diario_c[diario_c['Data_Temp'] == d]['Obra'].iloc[0]
                        erros_falta_ponto.append(f"Dia {d_str} (Lançado por: {lider} na Obra: {obra})")
                        
                    elif in_diario and in_ponto:
                        # Compara horários básicos
                        ent_diario = str(diario_c[diario_c['Data_Temp'] == d]['Hora Início'].iloc[0])[:5]
                        sai_diario = str(diario_c[diario_c['Data_Temp'] == d]['Hora Término'].iloc[0])[:5]
                        ent_ponto = str(ponto_c[ponto_c['Data_Temp'] == d]['Entrada'].iloc[0])[:5]
                        sai_ponto = str(ponto_c[ponto_c['Data_Temp'] == d]['Saida'].iloc[0])[:5]
                        
                        if ent_diario != ent_ponto or sai_diario != sai_ponto:
                            erros_horario.append(f"Dia {d_str} -> Ponto: [{ent_ponto} as {sai_ponto}] | Diário: [{ent_diario} as {sai_diario}]")
                            
                # Se encontrou qualquer erro, adiciona ao relatório
                if erros_falta_diario or erros_falta_ponto or erros_horario:
                    relatorio[colab] = {
                        "falta_diario": erros_falta_diario,
                        "falta_ponto": erros_falta_ponto,
                        "horario": erros_horario
                    }

            st.divider()
            st.markdown("## 📊 Resultados da Auditoria")
            st.caption(f"Filtro aplicado: Analisando apenas os meses encontrados nos PDFs ({', '.join([str(m) for m in meses_ponto])}). Nomes separados no Diário foram processados individualmente.")
            
            if not relatorio:
                st.success("Tudo perfeito! Nenhuma divergência encontrada no período analisado.")
                st.balloons()
            else:
                for colab, alertas in relatorio.items():
                    with st.expander(f"👷 {colab} ({len(alertas['falta_diario']) + len(alertas['falta_ponto']) + len(alertas['horario'])} pendências)", expanded=True):
                        c1, c2, c3 = st.columns(3)
                        
                        with c1:
                            st.markdown("❌ **Falta no Diário**")
                            st.caption("(Bateu ponto, mas não tá no Diário)")
                            for erro in alertas["falta_diario"]: st.error(erro)
                            if not alertas["falta_diario"]: st.write("Tudo OK ✅")
                                
                        with c2:
                            st.markdown("👻 **Falta no Ponto**")
                            st.caption("(Tá no Diário, mas não bateu ponto)")
                            for erro in alertas["falta_ponto"]: st.warning(erro)
                            if not alertas["falta_ponto"]: st.write("Tudo OK ✅")
                                
                        with c3:
                            st.markdown("⏰ **Divergência de Horário**")
                            st.caption("(Horários não batem)")
                            for erro in alertas["horario"]: st.info(erro)
                            if not alertas["horario"]: st.write("Tudo OK ✅")
