import streamlit as st
import pandas as pd
from datetime import datetime
import json
import gspread
from google.oauth2.service_account import Credentials
import traceback
import re # Nova ferramenta para limpar textos (ex: tirar matrícula do nome)

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
st.markdown("Arraste os relatórios de ponto da equipe. O sistema vai extrair os horários (usando a coluna 'Espelho'), cruzar com o Diário de Obras oficial e te dar tudo mastigado.")

@st.cache_resource
def conectar_diario():
    try:
        credenciais_dict = json.loads(st.secrets["google_credentials"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(credenciais_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Link da planilha mestre do Diário
        LINK_DA_PLANILHA = "https://docs.google.com/spreadsheets/d/1oI9pPGXngdE1jrOaQGIRhHMfLnt_Evh9tN_9lQkLaOU/edit?gid=1342849862#gid=1342849862"
        planilha = client.open_by_url(LINK_DA_PLANILHA).worksheet("DIÁRIO DE OBRA")
        return planilha
    except Exception as e:
        st.error("🚨 Erro de conexão com o Diário de Obras.")
        st.code(traceback.format_exc())
        return None

aba_diario = conectar_diario()

def calcular_diferenca_minutos(hora_str1, hora_str2):
    """Calcula a diferença em minutos entre duas strings de hora HH:MM"""
    try:
        if pd.isna(hora_str1) or pd.isna(hora_str2) or hora_str1 == "-" or hora_str2 == "-":
            return 999 
            
        formato = "%H:%M"
        h1 = str(hora_str1).strip()[:5]
        h2 = str(hora_str2).strip()[:5]
        
        t1 = datetime.strptime(h1, formato)
        t2 = datetime.strptime(h2, formato)
        
        diff = abs((t1 - t2).total_seconds() / 60)
        return diff
    except:
        return 999

def formatar_data(data_raw):
    """Garante que a data fique no formato DD/MM/YYYY"""
    try:
        if isinstance(data_raw, datetime):
            return data_raw.strftime("%d/%m/%Y")
        data_str = str(data_raw).strip()
        # Se vier como '01/07/2026, qua', corta na vírgula
        if "," in data_str:
            data_str = data_str.split(",")[0]
        if " " in data_str: 
            data_str = data_str.split(" ")[0]
        if "-" in data_str:
            partes = data_str.split("-")
            if len(partes[0]) == 4: 
                return f"{partes[2]}/{partes[1]}/{partes[0]}"
        return data_str.strip()
    except:
        return str(data_raw)

st.divider()
st.markdown("### 📥 1. Inserir Relatórios do Relógio de Ponto")
arquivos_ponto = st.file_uploader("Arraste os arquivos Excel (pode jogar 10, 20 arquivos de uma vez)", type=['xlsx', 'xls'], accept_multiple_files=True)

if arquivos_ponto:
    st.success(f"✅ {len(arquivos_ponto)} arquivo(s) carregado(s) na memória!")
    
    if st.button("🚀 Iniciar Auditoria Completa", type="primary", use_container_width=True):
        if aba_diario is None:
            st.error("Não foi possível conectar ao Diário. Verifique o Google Sheets.")
            st.stop()
            
        with st.spinner("Lendo relatórios, extraindo horários e cruzando com o Diário de Obras..."):
            
            dados_diario_bruto = aba_diario.get_all_records()
            df_diario = pd.DataFrame(dados_diario_bruto)
            
            # --- NOVA TRAVA DE SEGURANÇA (LIMPEZA DAS COLUNAS) ---
            if not df_diario.empty:
                # 1. Limpa espaços em branco invisíveis de todos os títulos
                df_diario.columns = df_diario.columns.str.strip() 
                
                # 2. Padroniza os nomes caso você tenha digitado diferente na planilha
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
                
                # 3. Verifica se a coluna 'Data' foi encontrada
                if 'Data' not in df_diario.columns:
                    st.error(f"🚨 Não encontrei a coluna 'Data' na aba DIÁRIO DE OBRA. O que eu encontrei foi: {list(df_diario.columns)}")
                    st.stop()
            else:
                st.error("🚨 A aba do Diário de Obras está completamente vazia.")
                st.stop()
            # -----------------------------------------------------
            
            registros_ponto = []
            
            for arquivo in arquivos_ponto:
                try:
                    # Lê o excel "cru", sem cabeçalhos, para nós caçarmos as palavras
                    df_raw = pd.read_excel(arquivo, header=None)
                    
                    # 1. Caçando o Nome do Colaborador (Lendo o cabeçalho bagunçado)
                    colaborador_identificado = "Desconhecido"
                    for linha in range(min(15, len(df_raw))):
                        for coluna in range(4):
                            celula = str(df_raw.iloc[linha, coluna]).strip()
                            if celula == "Colaborador":
                                nome_sujo = str(df_raw.iloc[linha, coluna + 1]).strip()
                                # Tira a matrícula da frente (ex: "2589 Alexandre")
                                nome_limpo = re.sub(r'^\d+\s+', '', nome_sujo).strip()
                                
                                # Acha o nome exato na nossa lista
                                for nome_lista in LISTA_COLABORADORES:
                                    # Pega os dois primeiros nomes para achar
                                    partes_lista = nome_lista.lower().split()
                                    if len(partes_lista) >= 2:
                                        busca = f"{partes_lista[0]} {partes_lista[1]}"
                                        if busca in nome_limpo.lower():
                                            colaborador_identificado = nome_lista
                                            break
                                break
                                
                    # 2. Caçando onde começa a tabela ("Dia")
                    linha_cabecalho_tabela = -1
                    for linha in range(min(30, len(df_raw))):
                        if str(df_raw.iloc[linha, 0]).strip() == "Dia":
                            linha_cabecalho_tabela = linha
                            break
                            
                    if linha_cabecalho_tabela != -1:
                        # 3. Lendo linha por linha dos dias trabalhados
                        for linha in range(linha_cabecalho_tabela + 1, len(df_raw)):
                            row = df_raw.iloc[linha]
                            raw_date = str(row[0]).strip()
                            
                            # Se a data estiver vazia ou não começar com número, pula
                            if raw_date in ["nan", "None", ""] or not raw_date[0].isdigit():
                                continue
                                
                            data_ponto = formatar_data(raw_date)
                            
                            # O TRUQUE DO ESPELHO: Pega as colunas L, M, N, O (Índices 11, 12, 13, 14)
                            # Assim pegamos a hora corrigida pelo RH
                            horarios_validos = []
                            for col_idx in [11, 12, 13, 14]:
                                if col_idx < len(row):
                                    valor = str(row[col_idx]).strip()
                                    # Verifica se parece um horário HH:MM
                                    if len(valor) >= 5 and valor[2] == ':':
                                        horarios_validos.append(valor[:5])
                            
                            # Se achou horários preenchidos nesse dia
                            if len(horarios_validos) >= 2:
                                entrada = horarios_validos[0]
                                saida = horarios_validos[-1] # Pega o último horário registrado
                            elif len(horarios_validos) == 1:
                                entrada = horarios_validos[0]
                                saida = horarios_validos[0]
                            else:
                                continue # Se não tem horário (ausência/falta), não gera ponto
                                
                            registros_ponto.append({
                                "Data": data_ponto,
                                "Colaborador": colaborador_identificado,
                                "Entrada_Ponto": entrada,
                                "Saida_Ponto": saida
                            })
                            
                except Exception as e:
                    st.error(f"Erro ao ler o arquivo {arquivo.name}: {e}")

            df_ponto = pd.DataFrame(registros_ponto)

            if not df_ponto.empty:
                # 1. Padroniza as datas do Diário para garantir que estão em DD/MM/YYYY
                df_diario['Data'] = df_diario['Data'].apply(formatar_data)
                
                # 2. Cria uma coluna invisível de calendário real para fazermos o filtro
                df_ponto['Data_Temp'] = pd.to_datetime(df_ponto['Data'], format='%d/%m/%Y', errors='coerce')
                df_diario['Data_Temp'] = pd.to_datetime(df_diario['Data'], format='%d/%m/%Y', errors='coerce')
                
                # 3. Descobre quais MESES estão dentro dos arquivos de ponto que você subiu
                meses_auditoria = df_ponto['Data_Temp'].dropna().dt.to_period('M').unique()
                
                # 4. A MÁGICA: Corta do Diário de Obras tudo que for de meses antigos/futuros
                df_diario = df_diario[df_diario['Data_Temp'].dt.to_period('M').isin(meses_auditoria)]

            relatorio_colab = {}
            
            todas_datas = set(df_diario['Data'].unique()).union(set(df_ponto['Data'].unique()) if not df_ponto.empty else set())
            todos_colaboradores = set(df_diario['Colaborador'].unique()).union(set(df_ponto['Colaborador'].unique()) if not df_ponto.empty else set())
            
            # Limpando datas zoadas (NaN) que podem ter sobrado
            todas_datas = {d for d in todas_datas if str(d) not in ["nan", "NaT", ""]}
            
            # Ordenar as datas para o relatório ficar cronológico
            todas_datas_ordenadas = sorted(list(todas_datas), key=lambda x: datetime.strptime(x, "%d/%m/%Y") if isinstance(x, str) and len(x) >= 10 else datetime.now())

            for colab in sorted(list(todos_colaboradores)):
                if str(colab) == "" or str(colab) == "Desconhecido": continue
                
                for data in todas_datas_ordenadas:
                    # Busca nos dois mundos
                    tem_no_diario = df_diario[(df_diario['Data'] == data) & (df_diario['Colaborador'] == colab)]
                    tem_no_ponto = df_ponto[(df_ponto['Data'] == data) & (df_ponto['Colaborador'] == colab)] if not df_ponto.empty else pd.DataFrame()
                    
                    if not tem_no_ponto.empty or not tem_no_diario.empty:
                        # Se achou algo, cria a "pastinha" do colaborador no relatório se não existir
                        if colab not in relatorio_colab:
                            relatorio_colab[colab] = {"falta_diario": [], "falta_ponto": [], "divergencia": []}
                    
                    # REGRA 1: Bateu Ponto, mas NÃO está no Diário (Cobrar o Líder)
                    if not tem_no_ponto.empty and tem_no_diario.empty:
                        lider_sugerido = "Líder Desconhecido"
                        historico_diario = df_diario[df_diario['Colaborador'] == colab]
                        if not historico_diario.empty and 'Líder' in historico_diario.columns:
                            lider_sugerido = historico_diario['Líder'].mode()[0]
                            
                        relatorio_colab[colab]["falta_diario"].append(f"**Dia {data}** (Sugestão de cobrança: {lider_sugerido})")
                        
                    # REGRA 2: Está no Diário, mas NÃO bateu Ponto
                    elif not tem_no_diario.empty and tem_no_ponto.empty:
                        lider = tem_no_diario.iloc[0]['Líder'] if 'Líder' in tem_no_diario.columns else "Líder"
                        obra = tem_no_diario.iloc[0]['Obra'] if 'Obra' in tem_no_diario.columns else "Obra"
                        relatorio_colab[colab]["falta_ponto"].append(f"**Dia {data}** (Diário de: {lider} na {obra})")
                        
                    # REGRA 3: Está nos dois. Analisar Tolerância de 5 Minutos.
                    elif not tem_no_diario.empty and not tem_no_ponto.empty:
                        entrada_diario = str(tem_no_diario.iloc[0]['Hora Início']) if 'Hora Início' in tem_no_diario.columns else "00:00"
                        saida_diario = str(tem_no_diario.iloc[0]['Hora Término']) if 'Hora Término' in tem_no_diario.columns else "00:00"
                        
                        entrada_ponto = tem_no_ponto.iloc[0]['Entrada_Ponto']
                        saida_ponto = tem_no_ponto.iloc[0]['Saida_Ponto']
                        
                        diff_entrada = calcular_diferenca_minutos(entrada_ponto, entrada_diario)
                        diff_saida = calcular_diferenca_minutos(saida_ponto, saida_diario)
                        
                        erros_horario = []
                        if diff_entrada > 5 and diff_entrada != 999:
                            erros_horario.append(f"Início (Ponto: {entrada_ponto} | Diário: {entrada_diario})")
                        if diff_saida > 5 and diff_saida != 999:
                            erros_horario.append(f"Fim (Ponto: {saida_ponto} | Diário: {saida_diario})")
                            
                        if erros_horario:
                            relatorio_colab[colab]["divergencia"].append(f"**Dia {data}** -> {', '.join(erros_horario)}")

            st.divider()
            st.markdown("## 📊 Resultados da Auditoria por Colaborador")
            st.caption("Filtro Automático: O sistema filtrou o Diário de Obras apenas para os meses correspondentes aos arquivos de ponto enviados.")
            
            houve_erros = False
            
            for colab, alertas in relatorio_colab.items():
                # Só mostra o colaborador se ele tiver algum tipo de alerta
                if alertas["falta_diario"] or alertas["falta_ponto"] or alertas["divergencia"]:
                    houve_erros = True
                    with st.expander(f"👷 {colab}", expanded=True):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if alertas["falta_diario"]:
                                st.error("❌ **Falta no Diário**\n" + "\n".join([f"- {msg}" for msg in alertas["falta_diario"]]))
                            else:
                                st.success("❌ Falta no Diário\n- Tudo OK")
                                
                        with col2:
                            if alertas["falta_ponto"]:
                                st.warning("👻 **Falta no Ponto**\n" + "\n".join([f"- {msg}" for msg in alertas["falta_ponto"]]))
                            else:
                                st.success("👻 Falta no Ponto\n- Tudo OK")
                                
                        with col3:
                            if alertas["divergencia"]:
                                st.info("⏰ **Divergência de Horário**\n" + "\n".join([f"- {msg}" for msg in alertas["divergencia"]]))
                            else:
                                st.success("⏰ Horários\n- Batendo")

            if not houve_erros:
                st.success("Tudo perfeito! Nenhuma divergência encontrada no período analisado.")
                st.balloons()
