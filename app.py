import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
from folium.plugins import MarkerCluster
from branca.element import MacroElement
from jinja2 import Template

# Configuração da página
st.set_page_config(
    page_title="Assassinatos Políticos no Brasil",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialização do estado da sessão para navegação persistente
if 'current_page' not in st.session_state:
    st.session_state.current_page = "home"

# Função para mudar de página
def change_page(page):
    st.session_state.current_page = page

# Função para corrigir coordenadas
def corrigir_coordenada(valor):
    if isinstance(valor, str):
        valor = valor.replace(",", ".")
        # Remove caracteres não numéricos, exceto ponto e sinal de menos
        valor = "".join([c if c.isdigit() or c in ['.', '-'] else "" for c in valor])
        partes = valor.split(".")
        if len(partes) > 2:
            valor = partes[0] + "." + "".join(partes[1:])
        try:
            valor_float = float(valor)
            # Corrige valores que estão fora dos limites normais de coordenadas
            if abs(valor_float) > 180:
                valor_float /= 100000
            return valor_float
        except ValueError:
            return None
    return valor

# Carregar e preparar os dados
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("assassinatos_com_coordenadas (1) (1).csv")
        df.rename(columns=lambda x: x.strip(), inplace=True)
        
        # Corrige coordenadas
        df["Latitude"] = df["Latitude"].apply(corrigir_coordenada)
        df["Longitude"] = df["Longitude"].apply(corrigir_coordenada)
        
        # Remove registros sem coordenadas válidas
        df = df.dropna(subset=["Latitude", "Longitude"])
        
        # Converte ano para inteiro
        df["Ano"] = pd.to_numeric(df["Ano"], errors='coerce').astype('Int64')
        
        # Formata a data
        def formatar_data(row):
            if pd.isna(row["Ano"]):
                return "Data desconhecida"
            if str(row["Dia"]).strip() == "SI" or str(row["Mês"]).strip() == "SI":
                return str(row["Ano"])
            return f"{row['Dia']}/{row['Mês']}/{row['Ano']}"
        
        df["data_formatada"] = df.apply(formatar_data, axis=1)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

# Função de cor por tipo
def get_color(tipo):
    cores = {
        'Assassinato': 'red',
        'Tentativa de assassinato': 'green',
        'Ameaça de assassinato': 'blue'
    }
    return cores.get(tipo, 'gray')

# Criar classe de legenda personalizada para o mapa
class Legend(MacroElement):
    def __init__(self):
        super(Legend, self).__init__()
        self._template = Template("""
            {% macro script(this, kwargs) %}
                var legend = L.control({position: 'bottomleft'});
                legend.onAdd = function (map) {
                    var div = L.DomUtil.create('div', 'info legend');
                    div.style.padding = '6px 8px';
                    div.style.background = 'rgba(255,255,255,0.9)';
                    div.style.border = 'solid 1px #aaa';
                    div.style.borderRadius = '3px';
                    div.style.fontSize = '14px';
                    div.style.lineHeight = '18px';
                    div.style.color = '#333';
                    div.style.fontFamily = 'Arial, sans-serif';
                    div.innerHTML += '<div style="font-weight: bold; margin-bottom: 5px;">Legenda</div>';
                    div.innerHTML += '<div><span style="color: red; font-size: 16px;">●</span> <span style="color: black">Assassinato</span></div>';
                    div.innerHTML += '<div><span style="color: green; font-size: 16px;">●</span> <span style="color: black">Tentativa de assassinato</span></div>';
                    div.innerHTML += '<div><span style="color: blue; font-size: 16px;">●</span> <span style="color: black">Ameaça de assassinato</span></div>';
                    return div;
                };
                legend.addTo({{ this._parent.get_name() }});
            {% endmacro %}
        """)

# Função para aplicar filtros
def aplicar_filtros(df, year_range, tipo_acao, genero, etnia):
    filtered = df.copy()
    if "Ano" in df.columns:
        filtered = filtered[
            (filtered["Ano"] >= year_range[0]) & 
            (filtered["Ano"] <= year_range[1])
        ]

    if tipo_acao and "Tipo_ação_vítima" in df.columns:
        filtered = filtered[filtered["Tipo_ação_vítima"].isin(tipo_acao)]
    if genero and "Vítima_Gênero/Sexo" in df.columns:
        filtered = filtered[filtered["Vítima_Gênero/Sexo"].isin(genero)]
    if etnia and "Vítimas_Etnia" in df.columns:
        filtered = filtered[filtered["Vítimas_Etnia"].isin(etnia)]
    
    return filtered

# Definir navegação
pages = {
    "Home": "home",
    "Mapa Interativo": "mapa",
    "Linha do Tempo": "timeline"
}

# Barra lateral com navegação
st.sidebar.title("Navegação")

# Cria radio buttons para navegação - eles manterão o estado
selected_page = st.sidebar.radio(
    "Selecione uma página:",
    list(pages.keys()),
    index=list(pages.values()).index(st.session_state.current_page)
)

# Atualiza a página atual com base na seleção
current_page = pages[selected_page]
st.session_state.current_page = current_page

# Carregar dados (comum a todas as páginas)
df = load_data()

# Se não houver dados, exibe mensagem e para execução
if df.empty:
    st.error("Não foi possível carregar os dados. Verifique o arquivo CSV.")
    st.stop()

# Filtros (se não estiver na home)
if current_page != "home":
    st.sidebar.title("Filtros")
    
    # Garante que os filtros só são criados se houver dados
    if "Ano" in df.columns and not df["Ano"].isna().all():
        min_year = int(df["Ano"].min()) if not pd.isna(df["Ano"].min()) else 2010
        max_year = int(df["Ano"].max()) if not pd.isna(df["Ano"].max()) else 2023
        year_range = st.sidebar.slider("Ano", min_year, max_year, (min_year, max_year), key="year_slider")
    else:
        year_range = (2010, 2023)

    # Filtros seguros que verificam se a coluna existe
    if "Tipo_ação_vítima" in df.columns:
        tipos_disponiveis = df["Tipo_ação_vítima"].dropna().unique().tolist()
        tipo_acao = st.sidebar.multiselect("Tipo de ação", tipos_disponiveis, default=tipos_disponiveis, key="tipo_acao")
    else:
        tipo_acao = []

    if "Vítima_Gênero/Sexo" in df.columns:
        generos_disponiveis = df["Vítima_Gênero/Sexo"].dropna().unique().tolist()
        genero = st.sidebar.multiselect("Gênero da vítima", generos_disponiveis, key="genero")
    else:
        genero = []

    if "Vítimas_Etnia" in df.columns:
        etnias_disponiveis = df["Vítimas_Etnia"].dropna().unique().tolist()
        etnia = st.sidebar.multiselect("Etnia da vítima", etnias_disponiveis, key="etnia")
    else:
        etnia = []
    
    # Aplica filtros ao dataframe
    filtered = aplicar_filtros(df, year_range, tipo_acao, genero, etnia)
else:
    # Para a página inicial, não é necessário filtrar
    filtered = df

# Conteúdo com base na página selecionada
if current_page == "home":
    # Página inicial
    st.title("Assassinatos Políticos no Brasil")
    st.subheader("Angela Alonso (USP/Cebrap)")
    
    st.markdown("""
    ### Descrição
    
    Levantamento e análise de letalidade política no Brasil, com objetivo de observar uma relação 
    entre violência política e hierarquia social, além de padrões recorrentes de violência política 
    que se cristalizam em estilos de assassinato político.
    """)
    
    # Adicionar dados resumidos
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total de Casos", len(df))
    
    with col2:
        if "Tipo_ação_vítima" in df.columns:
            assassinatos = df[df["Tipo_ação_vítima"] == "Assassinato"].shape[0]
            st.metric("Assassinatos", assassinatos)
    
    with col3:
        if "Ano" in df.columns:
            periodo = f"{df['Ano'].min()}-{df['Ano'].max()}"
            st.metric("Período", periodo)
    
    # Adicionar imagem ilustrativa se desejar
    # st.image("imagem_ilustrativa.jpg", caption="Imagem Ilustrativa", use_column_width=True)

elif current_page == "mapa":
    # Página do mapa
    st.title("Monitor de Assassinatos Políticos no Brasil")
    st.subheader("Mapa Interativo de Casos")
    
    # Verifica se há pontos válidos para plotar
    if len(filtered) == 0 or not all(col in filtered.columns for col in ['Latitude', 'Longitude']):
        st.warning("Não há dados para exibir no mapa com os filtros atuais.")
    else:
        # Calcula o centro do mapa com base nos dados filtrados
        center_lat = filtered['Latitude'].mean()
        center_lon = filtered['Longitude'].mean()
        
        # Cria o mapa com base nos dados filtrados
        m = folium.Map(
            location=[center_lat, center_lon] if not pd.isna(center_lat) else [-14.235, -51.9253],
            zoom_start=5,
            tiles='CartoDB positron'
        )
        
        # Cria um cluster de marcadores para melhor visualização
        marker_cluster = MarkerCluster().add_to(m)
        
        # Adiciona marcadores individuais ao mapa
        for _, row in filtered.iterrows():
            try:
                # Verifica se as coordenadas são válidas
                lat, lon = row['Latitude'], row['Longitude']
                if pd.isna(lat) or pd.isna(lon) or abs(lat) > 90 or abs(lon) > 180:
                    continue
                    
                # Prepara informações para o popup
                nome = row.get('Vítima_Nome Civil_(Apelido/Nome Social)', 'Nome não disponível')
                descricao = row.get('Descrição', 'Descrição não disponível')
                data = row.get('data_formatada', 'Data não disponível')
                instrumento = row.get('Instrumento_1', 'Não informado')
                disputa = row.get('Disputa', 'Não informada')
                tipo = row.get('Tipo_ação_vítima', 'Tipo não informado')
                
                popup_info = f"""<b>Vítima:</b> {nome}<br>
                <b>Descrição:</b> {descricao}<br>
                <b>Data:</b> {data}<br>
                <b>Instrumento:</b> {instrumento}<br>
                <b>Disputa:</b> {disputa}<br>
                """
                
                # Adiciona o marcador ao cluster
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=5,
                    color=get_color(tipo),
                    fill=True,
                    fill_color=get_color(tipo),
                    fill_opacity=0.7,
                    popup=folium.Popup(popup_info, max_width=300)
                ).add_to(marker_cluster)
                
            except Exception as e:
                # Silenciosamente ignora erros ao adicionar marcadores
                continue
        
        # Adicionar a legenda ao mapa
        m.add_child(Legend())
        
        # Ajusta os limites do mapa para mostrar todos os pontos
        try:
            sw = [filtered['Latitude'].min(), filtered['Longitude'].min()]
            ne = [filtered['Latitude'].max(), filtered['Longitude'].max()]
            m.fit_bounds([sw, ne])
        except:
            # Se não for possível ajustar os limites, usa o padrão do Brasil
            m.fit_bounds([[-33.75, -73.99], [5.27, -34.0]])
        
        # Renderiza o mapa
        st_folium(m, width=800, height=600)

elif current_page == "timeline":
    # Página da linha do tempo
    st.title("Monitor de Assassinatos Políticos no Brasil")
    st.subheader("Linha do Tempo Interativa")
    
    if len(filtered) > 0:
        # Seleciona colunas relevantes
        colunas_disponiveis = ['Ano', 'Mês', 'Tipo_ação_vítima', 'Vítimas_Etnia',
                            'Vítimas_Afiliação_1/Grupo', 'Cidade', 'Disputa']
        colunas_existentes = [col for col in colunas_disponiveis if col in filtered.columns]
        
        if len(colunas_existentes) >= 3:  # Mínimo necessário para criar a timeline
            df_timeline = filtered[colunas_existentes].copy()
            
            # Renomeia colunas para processamento de data
            if 'Ano' in df_timeline.columns:
                df_timeline = df_timeline.rename(columns={'Ano': 'year'})
            if 'Mês' in df_timeline.columns:
                df_timeline = df_timeline.rename(columns={'Mês': 'month'})
                
            # Adiciona coluna de dia para criar datetime
            df_timeline['day'] = 1
            
            # Cria coluna de data
            try:
                date_cols = [col for col in ['year', 'month', 'day'] if col in df_timeline.columns]
                if len(date_cols) > 0:
                    df_timeline['Data'] = pd.to_datetime(df_timeline[date_cols], errors='coerce')
                    df_timeline = df_timeline.dropna(subset=['Data']).sort_values(by='Data')
                    
                    # Cria coluna de descrição para hover
                    descricao_parts = []
                    if 'Tipo_ação_vítima' in df_timeline.columns:
                        descricao_parts.append("Tipo: " + df_timeline['Tipo_ação_vítima'].fillna("Não informado"))
                    if 'Vítimas_Etnia' in df_timeline.columns:
                        descricao_parts.append("Etnia: " + df_timeline['Vítimas_Etnia'].fillna("Não informada"))
                    if 'Vítimas_Afiliação_1/Grupo' in df_timeline.columns:
                        descricao_parts.append("Afiliação: " + df_timeline['Vítimas_Afiliação_1/Grupo'].fillna("Não informada"))
                    if 'Cidade' in df_timeline.columns:
                        descricao_parts.append("Cidade: " + df_timeline['Cidade'].fillna("Não informada"))
                    if 'Disputa' in df_timeline.columns:
                        descricao_parts.append("Disputa: " + df_timeline['Disputa'].fillna("Não informada"))
                    
                    df_timeline['Descrição'] = ["<br>".join([p for p in row]) for row in zip(*[parts for parts in descricao_parts])]
                    
                    # Cria gráfico
                    if 'Cidade' in df_timeline.columns and 'Tipo_ação_vítima' in df_timeline.columns:
                        fig = px.scatter(
                            df_timeline,
                            x='Data',
                            y='Cidade',
                            color='Tipo_ação_vítima',
                            hover_name='Cidade',
                            custom_data=['Descrição'],
                            title="Linha do Tempo de Casos (2003-2023)",
                            labels={'Cidade': 'Local', 'Data': 'Data', 'Tipo_ação_vítima': 'Tipo de Ação'},
                            height=700,
                            width=1000
                        )
                        fig.update_traces(hovertemplate='%{customdata[0]}<extra></extra>', marker=dict(size=10))
                        fig.update_layout(
                            xaxis_title="Data",
                            yaxis_title="Cidade",
                            showlegend=True,
                            legend_title="Tipo de Ação",
                            font=dict(size=12),
                            hovermode="closest"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("Dados insuficientes para criar a linha do tempo.")
                else:
                    st.warning("Colunas de data necessárias não encontradas para criar a linha do tempo.")
            except Exception as e:
                st.error(f"Erro ao criar a linha do tempo: {e}")
        else:
            st.warning("Dados insuficientes para criar a linha do tempo.")
    else:
        st.warning("Não há dados para exibir na linha do tempo com os filtros atuais.")

# Adiciona informações de rodapé
st.sidebar.markdown("---")
st.sidebar.markdown("**Desenvolvido por:** Equipe de Pesquisa")
st.sidebar.markdown("**Contato:** pesquisa@exemplo.com")
