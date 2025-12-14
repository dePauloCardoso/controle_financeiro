import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime, timedelta
import uuid

# Configuração da página
st.set_page_config(
    page_title="Controle Financeiro",
    page_icon="💰",
    layout="wide"
)

# Configuração de autenticação
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

@st.cache_resource
def get_google_sheets():
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    client = gspread.authorize(credentials)

    # Cole o ID da sua planilha aqui
    spreadsheet = client.open("Controle_Financeiro")

    return {
        'receitas': spreadsheet.worksheet("Receitas"),
        'despesas': spreadsheet.worksheet("Despesas"),
        'categorias': spreadsheet.worksheet("Categorias"),
        'formas_pagamento': spreadsheet.worksheet("Formas_Pagamento"),
        'cartoes': spreadsheet.worksheet("Cartoes")
    }

@st.cache_data(ttl=60)
def load_receitas():
    sheets = get_google_sheets()
    data = sheets['receitas'].get_all_records()
    df = pd.DataFrame(data)
    if not df.empty and len(df) > 0:
        df['Data'] = pd.to_datetime(df['Data'])
        df['Valor'] = pd.to_numeric(df['Valor'])
    return df

@st.cache_data(ttl=60)
def load_despesas():
    sheets = get_google_sheets()
    data = sheets['despesas'].get_all_records()
    df = pd.DataFrame(data)
    if not df.empty and len(df) > 0:
        df['Data'] = pd.to_datetime(df['Data'])
        df['Valor'] = pd.to_numeric(df['Valor'])
    return df

@st.cache_data(ttl=300)
def load_categorias():
    sheets = get_google_sheets()
    data = sheets['categorias'].get_all_records()
    return pd.DataFrame(data)

@st.cache_data(ttl=300)
def load_formas_pagamento():
    sheets = get_google_sheets()
    data = sheets['formas_pagamento'].get_all_records()
    df = pd.DataFrame(data)
    if not df.empty and 'Tipo_Pagamento' in df.columns:
        return df['Tipo_Pagamento'].tolist()
    return []

@st.cache_data(ttl=300)
def load_cartoes():
    sheets = get_google_sheets()
    data = sheets['cartoes'].get_all_records()
    df = pd.DataFrame(data)
    if not df.empty and 'Nome_Cartao' in df.columns:
        return df['Nome_Cartao'].tolist()
    return []

def add_receita(data, tipo_receita, categoria, valor, descricao):
    sheets = get_google_sheets()
    sheet = sheets['receitas']

    # Gera ID único
    receita_id = str(uuid.uuid4())[:8]

    nova_linha = [
        receita_id,
        data.strftime('%Y-%m-%d'),
        categoria,
        tipo_receita,
        valor,
        descricao
    ]

    sheet.append_row(nova_linha)
    st.cache_data.clear()

def add_despesa(data, categoria, forma_pagamento, cartao, valor_total, num_parcelas, descricao):
    sheets = get_google_sheets()
    sheet = sheets['despesas']

    # Gera ID do grupo de parcelas
    grupo_id = str(uuid.uuid4())[:8]

    # Calcula valor de cada parcela
    valor_parcela = valor_total / num_parcelas

    # Adiciona cada parcela
    for i in range(num_parcelas):
        despesa_id = str(uuid.uuid4())[:8]
        data_parcela = data + timedelta(days=30*i)  # Adiciona mês a mês

        # ORDEM CORRETA: ID | Data | Categoria | Forma_Pagamento | Cartao | Valor | Parcelas | Parcela_Atual | ID_Grupo_Parcelado | Descrição
        nova_linha = [
            despesa_id,                                      # ID
            data_parcela.strftime('%Y-%m-%d'),              # Data
            categoria,                                       # Categoria
            forma_pagamento,                                 # Forma_Pagamento
            cartao if cartao else "",                       # Cartao (vazio se não selecionado)
            round(valor_parcela, 2),                        # Valor
            num_parcelas,                                    # Parcelas
            i + 1,                                          # Parcela_Atual
            grupo_id,                                       # ID_Grupo_Parcelado
            f"{descricao} - Parcela {i+1}/{num_parcelas}"  # Descrição
        ]

        sheet.append_row(nova_linha)

    st.cache_data.clear()

def get_dados_mensais():
    df_receitas = load_receitas()
    df_despesas = load_despesas()

    # Se ambos estão vazios, retorna DataFrame vazio
    if (df_receitas.empty or len(df_receitas) == 0) and (df_despesas.empty or len(df_despesas) == 0):
        return pd.DataFrame()

    # Agrupa receitas por mês
    if not df_receitas.empty and len(df_receitas) > 0:
        df_receitas_temp = df_receitas.copy()
        df_receitas_temp['Mes'] = df_receitas_temp['Data'].dt.to_period('M')
        receitas_mensais = df_receitas_temp.groupby('Mes')['Valor'].sum()
    else:
        receitas_mensais = pd.Series(dtype=float)

    # Agrupa despesas por mês
    if not df_despesas.empty and len(df_despesas) > 0:
        df_despesas_temp = df_despesas.copy()
        df_despesas_temp['Mes'] = df_despesas_temp['Data'].dt.to_period('M')
        despesas_mensais = df_despesas_temp.groupby('Mes')['Valor'].sum()
    else:
        despesas_mensais = pd.Series(dtype=float)

    # Se ambas as séries estão vazias, retorna DataFrame vazio
    if receitas_mensais.empty and despesas_mensais.empty:
        return pd.DataFrame()

    # Combina dados
    df_mensal = pd.DataFrame({
        'Receitas': receitas_mensais,
        'Despesas': despesas_mensais
    }).fillna(0)

    df_mensal['Saldo'] = df_mensal['Receitas'] - df_mensal['Despesas']
    df_mensal.index = df_mensal.index.astype(str)

    return df_mensal.reset_index().rename(columns={'index': 'Mês'})

# Interface Principal
st.title("💰 Controle Financeiro Pessoal")

# Sidebar para navegação
menu = st.sidebar.selectbox(
    "Menu",
    ["📊 Dashboard", "➕ Nova Receita", "➖ Nova Despesa", "📋 Histórico", "⚙️ Configurações"]
)

# Dashboard
if menu == "📊 Dashboard":
    st.header("Visão Geral")

    # Carrega dados
    df_receitas = load_receitas()
    df_despesas = load_despesas()
    df_mensal = get_dados_mensais()

    # Métricas do mês atual
    mes_atual = datetime.now().strftime('%Y-%m')

    col1, col2, col3 = st.columns(3)

    with col1:
        if not df_receitas.empty and len(df_receitas) > 0:
            receitas_mes = df_receitas[df_receitas['Data'].dt.strftime('%Y-%m') == mes_atual]['Valor'].sum()
        else:
            receitas_mes = 0
        st.metric("💵 Receitas (Mês Atual)", f"R$ {receitas_mes:,.2f}")

    with col2:
        if not df_despesas.empty and len(df_despesas) > 0:
            despesas_mes = df_despesas[df_despesas['Data'].dt.strftime('%Y-%m') == mes_atual]['Valor'].sum()
        else:
            despesas_mes = 0
        st.metric("💸 Despesas (Mês Atual)", f"R$ {despesas_mes:,.2f}")

    with col3:
        saldo_mes = receitas_mes - despesas_mes
        st.metric("💰 Saldo (Mês Atual)", f"R$ {saldo_mes:,.2f}", 
                 delta=f"R$ {saldo_mes:,.2f}")

    # Gráfico de evolução mensal
    if not df_mensal.empty and len(df_mensal) > 0 and 'Mês' in df_mensal.columns:
        st.subheader("📈 Evolução Mensal")

        fig = go.Figure()

        fig.add_trace(go.Bar(
            name='Receitas',
            x=df_mensal['Mês'],
            y=df_mensal['Receitas'],
            marker_color='green'
        ))

        fig.add_trace(go.Bar(
            name='Despesas',
            x=df_mensal['Mês'],
            y=df_mensal['Despesas'],
            marker_color='red'
        ))

        fig.add_trace(go.Scatter(
            name='Saldo',
            x=df_mensal['Mês'],
            y=df_mensal['Saldo'],
            mode='lines+markers',
            line=dict(color='blue', width=3)
        ))

        fig.update_layout(
            barmode='group',
            height=400,
            xaxis_title="Mês",
            yaxis_title="Valor (R$)",
            hovermode='x unified'
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📊 Adicione transações para visualizar os gráficos")

    # Gráficos de categorias e formas de pagamento
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Receitas por Categoria")
        if not df_receitas.empty and len(df_receitas) > 0 and 'Categoria' in df_receitas.columns:
            receitas_cat = df_receitas.groupby('Categoria')['Valor'].sum().reset_index()
            fig_rec = px.pie(receitas_cat, values='Valor', names='Categoria', 
                            color_discrete_sequence=px.colors.sequential.Greens_r)
            st.plotly_chart(fig_rec, use_container_width=True)
        else:
            st.info("Nenhuma receita cadastrada ainda")

    with col2:
        st.subheader("📊 Despesas por Categoria")
        if not df_despesas.empty and len(df_despesas) > 0 and 'Categoria' in df_despesas.columns:
            despesas_cat = df_despesas.groupby('Categoria')['Valor'].sum().reset_index()
            fig_desp = px.pie(despesas_cat, values='Valor', names='Categoria',
                             color_discrete_sequence=px.colors.sequential.Reds_r)
            st.plotly_chart(fig_desp, use_container_width=True)
        else:
            st.info("Nenhuma despesa cadastrada ainda")

    # Gráficos adicionais
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💵 Receitas: Fixas vs Variáveis")
        if not df_receitas.empty and len(df_receitas) > 0 and 'Tipo_Receita' in df_receitas.columns:
            receitas_tipo = df_receitas.groupby('Tipo_Receita')['Valor'].sum().reset_index()
            if not receitas_tipo.empty:
                fig_tipo = px.bar(receitas_tipo, x='Tipo_Receita', y='Valor',
                                 color='Tipo_Receita',
                                 color_discrete_map={'Fixa': 'darkgreen', 'Variável': 'lightgreen'})
                st.plotly_chart(fig_tipo, use_container_width=True)
            else:
                st.info("Adicione receitas para visualizar")
        else:
            st.info("Adicione receitas para visualizar")

    with col2:
        st.subheader("💳 Despesas por Forma de Pagamento")
        if not df_despesas.empty and len(df_despesas) > 0 and 'Forma_Pagamento' in df_despesas.columns:
            despesas_forma = df_despesas.groupby('Forma_Pagamento')['Valor'].sum().reset_index()
            if not despesas_forma.empty:
                fig_forma = px.pie(despesas_forma, values='Valor', names='Forma_Pagamento',
                                  color_discrete_sequence=px.colors.sequential.Oranges_r)
                st.plotly_chart(fig_forma, use_container_width=True)
            else:
                st.info("Adicione despesas para visualizar")
        else:
            st.info("Adicione despesas para visualizar")

    # Despesas por cartão (apenas crédito)
    if not df_despesas.empty and len(df_despesas) > 0 and 'Cartao' in df_despesas.columns:
        despesas_credito = df_despesas[(df_despesas['Forma_Pagamento'] == 'Crédito') & (df_despesas['Cartao'] != '')]
        if not despesas_credito.empty and len(despesas_credito) > 0:
            st.subheader("💳 Despesas por Cartão de Crédito")
            despesas_cartao = despesas_credito.groupby('Cartao')['Valor'].sum().reset_index()
            fig_cartao = px.bar(despesas_cartao, x='Cartao', y='Valor',
                               color='Cartao',
                               color_discrete_sequence=px.colors.sequential.Blues)
            st.plotly_chart(fig_cartao, use_container_width=True)

# Nova Receita
elif menu == "➕ Nova Receita":
    st.header("Adicionar Nova Receita")

    df_categorias = load_categorias()

    if not df_categorias.empty and len(df_categorias) > 0:
        categorias_receita = df_categorias[df_categorias['Tipo'] == 'Receita']['Nome_Categoria'].tolist()
    else:
        categorias_receita = []
        st.warning("⚠️ Configure as categorias na aba 'Categorias' do Google Sheets primeiro!")

    with st.form("form_receita"):
        col1, col2 = st.columns(2)

        with col1:
            data_receita = st.date_input("Data", value=datetime.now())
            tipo_receita = st.selectbox("Tipo", ["Fixa", "Variável"])

        with col2:
            if categorias_receita:
                categoria_receita = st.selectbox("Categoria", categorias_receita)
            else:
                categoria_receita = st.text_input("Categoria")
            valor_receita = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")

        descricao_receita = st.text_area("Descrição")

        submitted = st.form_submit_button("💾 Salvar Receita", use_container_width=True)

        if submitted:
            if valor_receita > 0 and categoria_receita:
                add_receita(data_receita, tipo_receita, categoria_receita, 
                           valor_receita, descricao_receita)
                st.success("✅ Receita adicionada com sucesso!")
                st.balloons()
            else:
                st.error("⚠️ Preencha todos os campos obrigatórios")

# Nova Despesa
elif menu == "➖ Nova Despesa":
    st.header("Adicionar Nova Despesa")

    df_categorias = load_categorias()
    formas_pagamento = load_formas_pagamento()
    cartoes = load_cartoes()

    if not df_categorias.empty and len(df_categorias) > 0:
        categorias_despesa = df_categorias[df_categorias['Tipo'] == 'Despesa']['Nome_Categoria'].tolist()
    else:
        categorias_despesa = []
        st.warning("⚠️ Configure as categorias na aba 'Categorias' do Google Sheets primeiro!")

    if not formas_pagamento:
        st.warning("⚠️ Configure as formas de pagamento na aba 'Formas_Pagamento' do Google Sheets!")
        formas_pagamento = ["PIX", "Dinheiro", "Débito", "Crédito"]

    if not cartoes:
        st.warning("⚠️ Configure os cartões na aba 'Cartoes' do Google Sheets!")
        cartoes = ["Nubank", "Inter", "Outro"]

    # Adiciona opção em branco no início da lista de cartões
    cartoes_com_branco = [""] + cartoes

    with st.form("form_despesa"):
        col1, col2, col3 = st.columns(3)

        with col1:
            data_despesa = st.date_input("Data da Primeira Parcela", value=datetime.now())
            if categorias_despesa:
                categoria_despesa = st.selectbox("Categoria", categorias_despesa)
            else:
                categoria_despesa = st.text_input("Categoria")

        with col2:
            forma_pagamento = st.selectbox("Forma de Pagamento", formas_pagamento)
            valor_total = st.number_input("Valor Total (R$)", min_value=0.0, format="%.2f")

        with col3:
            # Sempre mostra o campo de cartão, com opção em branco
            cartao_selecionado = st.selectbox(
                "Cartão", 
                cartoes_com_branco,
                help="Deixe em branco para PIX/Dinheiro/Débito. Obrigatório para Crédito."
            )
            num_parcelas = st.number_input("Número de Parcelas", min_value=1, max_value=120, value=1)

        descricao_despesa = st.text_area("Descrição")

        # Preview das parcelas
        if valor_total > 0 and num_parcelas > 0:
            st.info(f"💡 Serão criadas **{num_parcelas} parcelas** de **R$ {valor_total/num_parcelas:.2f}** cada")

        submitted = st.form_submit_button("💾 Salvar Despesa", use_container_width=True)

        if submitted:
            if valor_total > 0 and categoria_despesa and forma_pagamento:
                # Valida se cartão foi selecionado quando for crédito
                if forma_pagamento == "Crédito" and not cartao_selecionado:
                    st.error("⚠️ Selecione um cartão para pagamento em crédito")
                else:
                    add_despesa(data_despesa, categoria_despesa, forma_pagamento, 
                               cartao_selecionado, valor_total, num_parcelas, descricao_despesa)
                    st.success(f"✅ Despesa adicionada com sucesso! ({num_parcelas} parcela(s) criada(s))")
                    st.balloons()
            else:
                st.error("⚠️ Preencha todos os campos obrigatórios")

# Histórico
elif menu == "📋 Histórico":
    st.header("Histórico de Transações")

    tab1, tab2 = st.tabs(["💵 Receitas", "💸 Despesas"])

    with tab1:
        df_receitas = load_receitas()
        if not df_receitas.empty and len(df_receitas) > 0:
            df_receitas_display = df_receitas.sort_values('Data', ascending=False).copy()
            df_receitas_display['Data'] = df_receitas_display['Data'].dt.strftime('%d/%m/%Y')
            df_receitas_display['Valor'] = df_receitas_display['Valor'].apply(lambda x: f"R$ {x:,.2f}")

            # Seleciona colunas para exibição
            colunas_exibir = ['Data', 'Categoria', 'Tipo_Receita', 'Valor', 'Descrição']
            colunas_disponiveis = [col for col in colunas_exibir if col in df_receitas_display.columns]

            st.dataframe(df_receitas_display[colunas_disponiveis], width='stretch', hide_index=True)

            # Totais
            st.metric("💰 Total de Receitas", f"R$ {df_receitas['Valor'].sum():,.2f}")
        else:
            st.info("Nenhuma receita cadastrada")

    with tab2:
        df_despesas = load_despesas()
        if not df_despesas.empty and len(df_despesas) > 0:
            df_despesas_display = df_despesas.sort_values('Data', ascending=False).copy()
            df_despesas_display['Data'] = df_despesas_display['Data'].dt.strftime('%d/%m/%Y')
            df_despesas_display['Valor'] = df_despesas_display['Valor'].apply(lambda x: f"R$ {x:,.2f}")

            # Seleciona colunas para exibição
            colunas_exibir = ['Data', 'Categoria', 'Forma_Pagamento', 'Cartao', 'Valor', 'Parcela_Atual', 'Parcelas', 'Descrição']
            colunas_disponiveis = [col for col in colunas_exibir if col in df_despesas_display.columns]

            st.dataframe(df_despesas_display[colunas_disponiveis], width='stretch', hide_index=True)

            # Totais
            col1, col2 = st.columns(2)
            with col1:
                st.metric("💸 Total de Despesas", f"R$ {df_despesas['Valor'].sum():,.2f}")

            with col2:
                if 'Forma_Pagamento' in df_despesas.columns:
                    despesas_credito = df_despesas[df_despesas['Forma_Pagamento'] == 'Crédito']['Valor'].sum()
                    st.metric("💳 Total em Crédito", f"R$ {despesas_credito:,.2f}")
        else:
            st.info("Nenhuma despesa cadastrada")

# Configurações
elif menu == "⚙️ Configurações":
    st.header("Configurações")

    st.subheader("📂 Categorias")

    df_categorias = load_categorias()

    if not df_categorias.empty and len(df_categorias) > 0:
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Categorias de Receita:**")
            cat_receita = df_categorias[df_categorias['Tipo'] == 'Receita']['Nome_Categoria'].tolist()
            if cat_receita:
                for cat in cat_receita:
                    st.write(f"✅ {cat}")
            else:
                st.info("Nenhuma categoria de receita configurada")

        with col2:
            st.write("**Categorias de Despesa:**")
            cat_despesa = df_categorias[df_categorias['Tipo'] == 'Despesa']['Nome_Categoria'].tolist()
            if cat_despesa:
                for cat in cat_despesa:
                    st.write(f"✅ {cat}")
            else:
                st.info("Nenhuma categoria de despesa configurada")
    else:
        st.warning("⚠️ Nenhuma categoria configurada!")

    st.divider()

    # Formas de Pagamento e Cartões
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💳 Formas de Pagamento")
        formas = load_formas_pagamento()
        if formas:
            for forma in formas:
                st.write(f"✅ {forma}")
        else:
            st.info("Configure na aba 'Formas_Pagamento'")

    with col2:
        st.subheader("💳 Cartões Cadastrados")
        cartoes = load_cartoes()
        if cartoes:
            for cartao in cartoes:
                st.write(f"✅ {cartao}")
        else:
            st.info("Configure na aba 'Cartoes'")

    st.divider()

    st.subheader("📊 Estrutura das Planilhas")

    with st.expander("📋 Estrutura da aba 'Receitas'"):
        st.code("""
ID | Data | Categoria | Tipo_Receita | Valor | Descrição
        """)

    with st.expander("📋 Estrutura da aba 'Despesas'"):
        st.code("""
ID | Data | Categoria | Forma_Pagamento | Cartao | Valor | Parcelas | Parcela_Atual | ID_Grupo_Parcelado | Descrição
        """)

    with st.expander("📋 Estrutura da aba 'Categorias'"):
        st.code("""
Tipo | Nome_Categoria
Receita | Salário
Receita | Freelance
Despesa | Alimentação
Despesa | Transporte
        """)

    with st.expander("📋 Estrutura da aba 'Formas_Pagamento'"):
        st.code("""
Tipo_Pagamento
PIX
Dinheiro
Débito
Crédito
        """)

    with st.expander("📋 Estrutura da aba 'Cartoes'"):
        st.code("""
Nome_Cartao
Nubank
Inter
Itaú
C6 Bank
Outro
        """)

    st.info("💡 Para adicionar ou editar, edite diretamente as abas no Google Sheets")

    st.divider()

    st.subheader("🔄 Atualizar Cache")
    if st.button("Limpar Cache e Recarregar Dados"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("✅ Cache limpo! Recarregando...")
        st.rerun()
