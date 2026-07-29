import streamlit as st
import pandas as pd
import pdfplumber
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Auditoria ITON", layout="wide")

# 1. CONEXÃO GOOGLE (DIÁRIO DE OBRAS)
@st.cache_resource
def carregar_diario():
    cred = json.loads(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(cred, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    client = gspread.authorize(creds)
    # Busca a planilha de Diário de Obras
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1oI9pPGXngdE1jrOaQGIRhHMfLnt_Evh9tN_9lQkLaOU/edit").worksheet("DIÁRIO DE OBRA")
    df = pd.DataFrame(sheet.get_all_records())
    # Renomear para colunas padrão: 'Data', 'Colaborador', 'Entrada', 'Saida'
    # Ajuste conforme os nomes exatos das suas colunas no Google Sheets
    return df

# 2. LEITURA PRECISA DO PDF (Apenas linhas com data)
def ler_pdf_ponto(arquivo):
    registros = []
    with pdfplumber.open(arquivo) as pdf:
        nome_colaborador = ""
        for page in pdf.pages:
            text = page.extract_text()
            if not nome_colaborador:
                for line in text.split('\n'):
                    if "Colaborador" in line:
                        nome_colaborador = line.split("Colaborador")[1].strip()
            
            # Pega a tabela de pontos
            for table in page.extract_tables():
                for row in table:
                    # Verifica se a linha começa com data (DD/MM/AAAA)
                    if row[0] and len(row[0]) >= 10 and row[0][2] == '/':
                        data = row[0][:10]
                        # Aqui extraímos o horário de Entrada e Saída da linha
                        # Ajuste os índices conforme a estrutura que você me enviou
                        entrada = row[7] if row[7] else "Ausente"
                        saida = row[8] if row[8] else "Ausente"
                        registros.append({"Data": data, "Colaborador": nome_colaborador, "Entrada": entrada, "Saida": saida})
    return registros

# 3. INTERFACE E LÓGICA DE AUDITORIA
st.title("🕵️ Auditoria Real: Ponto vs Diário")
arquivos = st.file_uploader("Upload dos PDFs de Ponto", accept_multiple_files=True)

if arquivos and st.button("Executar Auditoria"):
    df_diario = carregar_diario()
    todos_pontos = []
    for f in arquivos:
        todos_pontos.extend(ler_pdf_ponto(f))
    df_ponto = pd.DataFrame(todos_pontos)
    
    st.write("### Comparativo")
    # A lógica aqui será: cruzar df_ponto com df_diario e mostrar as divergências
    # Você quer ver: "Fulano trabalhou na obra dia X, mas no ponto consta Y"
    st.dataframe(df_ponto) 
```

**Por favor, me confirme:**
1. A tabela que aparece agora no seu app está mostrando corretamente o Nome, Data, Entrada e Saída?
2. Se estiver, o próximo passo é eu terminar a função de cruzamento que vai listar, para cada pessoa, as datas que estão no Diário mas não no Ponto (e vice-versa). **É exatamente isso que você quer ver agora?**
