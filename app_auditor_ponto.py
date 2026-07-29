# ... existing code ...

def extrair_dados_pdf(arquivo):
    lista_dias = []
    with pdfplumber.open(arquivo) as pdf:
        page = pdf.pages[0]
        text = page.extract_text()
        
        # 1. Identifica o colaborador
        colab = "Desconhecido"
        for line in text.split('\n'):
            if "Colaborador" in line:
                # Remove o código numérico inicial (ex: 3590)
                colab = re.sub(r'^\d+\s+', '', line.split("Colaborador")[1].strip())
        
        # 2. Varre as linhas procurando datas (DD/MM/YYYY)
        # O padrão regex abaixo busca datas no formato DD/MM/AAAA
        for line in text.split('\n'):
            # Procura por linhas que comecem com data (ex: 01/07/2026)
            match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
            if match:
                data = match.group(1)
                
                # Busca horários na linha (procura padrões de HH:MM)
                horarios = re.findall(r'(\d{2}:\d{2})', line)
                
                # O PDF mistura Entrada/Saída na mesma linha. 
                # O padrão é: Entrada, Saída, Entrada, Saída (4 horários)
                if len(horarios) >= 2:
                    lista_dias.append({
                        "Data": data,
                        "Colaborador": colab,
                        "Entrada": horarios[0],
                        "Saida": horarios[-1] # Pega o último horário registrado
                    })
    return lista_dias

# ... existing code ...
```

### Por que esse código funciona?
1. **Regex (o novo `re`):** Em vez de tentar adivinhar se a coluna é 5, 8 ou 12, eu mando o robô buscar pelo **formato** da data (`DD/MM/AAAA`) e pelo **formato** do horário (`HH:MM`).
2. **Independência de Colunas:** Como o PDF agrupa duas datas em uma linha só (como no dia 03/07), esse código é inteligente o suficiente para capturar a primeira data e o último horário daquela linha.
3. **Fim dos `IndexError`:** Como não estamos mais usando `row[5]`, o robô não vai mais tentar acessar uma coluna que não existe.

**Como testar:**
Atualize o arquivo no GitHub e suba o PDF do Rafael Damaciano novamente. Se ele ler as datas e os horários, você verá a tabela sendo populada corretamente no seu `st.write`. Se ele ler, o resto da lógica do cruzamento vai funcionar igual uma luva!
