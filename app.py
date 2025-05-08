import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
from folium.plugins import MarkerCluster
from branca.element import MacroElement
from jinja2 import Template
import time

# Código da linha do tempo animada (colar a função render_timeline_page aqui)
def render_timeline_animated_page(df_filtered):
    st.title("Linha do Tempo Animada")
    st.subheader("Visualização temporal dos casos")
    
    if len(df_filtered) == 0:
        st.warning("Não há dados para exibir com os filtros atuais.")
        return
    
    # Certifique-se de que temos a coluna Ano
    if 'Ano' not in df_filtered.columns or df_filtered['Ano'].isna().all():
        st.error("Dados de ano não disponíveis para animação.")
        return
    
    # Prepara os dados para a animação
    df_anim = df_filtered.copy()
    anos_disponíveis = sorted(df_anim['Ano'].dropna().unique())
    
    # Controles de animação
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        velocidade = st.slider("Velocidade da animação (segundos por ano)", 0.5, 5.0, 2.0)
    with col2:
        iniciar = st.button("Iniciar animação")
    with col3:
        parar = st.button("Parar animação")
    
    # Container para o mapa animado
    mapa_container = st.empty()
    info_container = st.empty()
    
    # Função para criar o mapa de um ano específico
    def create_year_map(ano):
        dados_ano = df_anim[df_anim['Ano'] == ano]
        
        # Cria o mapa
        m = folium.Map(
            location=[-14.235, -51.9253],
            zoom_start=4,
            tiles='CartoDB positron'
        )
        
        # Adiciona marcadores para cada caso
        for _, row in dados_ano.iterrows():
            try:
                lat, lon = row['Latitude'], row['Longitude']
                if pd.isna(lat) or pd.isna(lon) or abs(lat) > 90 or abs(lon) > 180:
                    continue
                
                # Prepara informações para o popup
                nome = row.get('Vítima_Nome Civil_(Apelido/Nome Social)', 'Nome não disponível')
                tipo = row.get('Tipo_ação_vítima', 'Tipo não informado')
                
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=8,
                    color=get_color(tipo),
                    fill=True,
                    fill_color=get_color(tipo),
                    fill_opacity=0.7,
                    popup=nome
                ).add_to(m)
            except:
                continue
                
        # Adiciona legenda
        m.add_child(Legend())
        return m, len(dados_ano)
    
    # Estado da animação
    if iniciar:
        st.session_state.animating = True
    if parar:
        st.session_state.animating = False
    
    # Inicializa o estado se não existir
    if 'animating' not in st.session_state:
        st.session_state.animating = False
    
    # Executar a animação
    if st.session_state.animating:
        for ano in anos_disponíveis:
            if not st.session_state.animating:
                break
                
            # Cria e exibe o mapa do ano atual
            mapa_ano, num_casos = create_year_map(ano)
            with mapa_container:
                st_folium(mapa_ano, width=700, height=500)
            
            # Exibe informações sobre o ano
            with info_container:
                st.markdown(f"### Ano: {ano}")
                st.markdown(f"**Número de casos:** {num_casos}")
            
            # Pausa para o próximo ano
            time.sleep(velocidade)
    else:
        # Mostra o mapa com todos os dados quando não está animando
        if anos_disponíveis:
            ano_inicial = anos_disponíveis[0]
            mapa_inicial, num_casos = create_year_map(ano_inicial)
            with mapa_container:
                st_folium(mapa_inicial, width=700, height=500)
            with info_container:
                st.markdown(f"### Ano: {ano_inicial}")
                st.markdown(f"**Número de casos:** {num_casos}")
                st.markdown("Clique em 'Iniciar animação' para visualizar a evolução temporal.")

# Configuração da página
st.set_page_config(
    page_title="Assassinatos Políticos no Brasil",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialização do estado da sessão para navegação persistente
if 'current_page' not in st.session_state:
    st.session_state.current_page = "home"

# Função para mudar de página
def change_page(page):
    st.session_state.current_page = page

# Função para corrigir coordenada
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

# Definir navegação com a nova página de linha do tempo animada
pages = {
    "Home": "home",
    "Mapa Interativo": "mapa",
    "Linha do Tempo": "timeline",
    "Linha do Tempo Animada": "timeline_animada"  # Nova página adicionada
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
    st.title("Assassinatos Políticos no Brasil: padrões longitudinais e casos típicos (2003-2023)")
    st.subheader("Angela Alonso (USP/Cebrap)")
    
    st.markdown("""
    Levantamento e análise de letalidade política no Brasil, com objetivo de observar uma relação 
    entre violência política e hierarquia social, além de padrões recorrentes de violência política 
    que se cristalizam em estilos de assassinato político.
    """)
    # Adicionar imagem ilustrativa se desejar
    # st.image("imagem_ilustrativa.jpg", caption="Imagem Ilustrativa", use_column_width=True)

elif current_page == "mapa":
    # Página do mapa
    st.title("Assassinatos Políticos no Brasil")
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
        st_folium(m, width=700, height=500)

elif current_page == "timeline":
    # Página da linha do tempo original
    st.title("Assassinatos Políticos no Brasil")
    
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
                        descricao_parts.append("Tipo: " + df_timeline['Tipo_ação_vítima'].astype(str))
                    if 'Vítimas_Etnia' in df_timeline.columns:
                        descricao_parts.append("Etnia: " + df_timeline['Vítimas_Etnia'].astype(str))
                    if 'Vítimas_Afiliação_1/Grupo' in df_timeline.columns:
                        descricao_parts.append("Grupo: " + df_timeline['Vítimas_Afiliação_1/Grupo'].astype(str))
                    if 'Cidade' in df_timeline.columns:
                        descricao_parts.append("Cidade: " + df_timeline['Cidade'].astype(str))
                    if 'Disputa' in df_timeline.columns:
                        descricao_parts.append("Disputa: " + df_timeline['Disputa'].astype(str))
                    
                    df_timeline['Descrição'] = ""
                    for i, parts in enumerate(zip(*[df_timeline[part.split(": ")[0]] for part in descricao_parts])):
                        desc = "<br>".join([f"{name.split(': ')[0]}: {value}" for name, value in zip(descricao_parts, parts)])
                        df_timeline.loc[df_timeline.index[i], 'Descrição'] = desc
                    
                    # Cria o gráfico da linha do tempo
                    fig = px.scatter(
                        df_timeline, 
                        x='Data', 
                        y='Tipo_ação_vítima' if 'Tipo_ação_vítima' in df_timeline.columns else 'Disputa',
                        color='Tipo_ação_vítima' if 'Tipo_ação_vítima' in df_timeline.columns else None,
                        hover_name='Descrição',
                        title='Linha do Tempo de Assassinatos Políticos',
                        height=600,
                        size_max=15,
                        size=[10] * len(df_timeline)
                    )
                    
                    # Configura o layout
                    fig.update_layout(
                        xaxis_title='Data',
                        yaxis_title='Tipo de Ação',
                        legend_title='Tipo',
                        hovermode='closest'
                    )
                    
                    # Exibe o gráfico
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("Não foi possível criar a linha do tempo: faltam dados de data.")
            except Exception as e:
                st.error(f"Erro ao criar a linha do tempo: {e}")
        else:
            st.warning("Não há colunas suficientes para criar a linha do tempo.")
    else:
        st.warning("Não há dados para exibir com os filtros atuais.")

elif current_page == "timeline_animada":
    # Renderiza a página de linha do tempo animada
    render_timeline_animated_page(filtered)

# Adiciona informações de rodapé
st.sidebar.markdown("---")
st.sidebar.markdown("**Desenvolvido por:** Equipe de Pesquisa")
st.sidebar.markdown("**Contato:** email@exemplo.com")
