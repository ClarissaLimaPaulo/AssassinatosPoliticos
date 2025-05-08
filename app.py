import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
from folium.plugins import MarkerCluster
from folium.elements import Element

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

df = load_data()

# Se não houver dados, exibe mensagem e para execução
if df.empty:
    st.error("Não foi possível carregar os dados. Verifique o arquivo CSV.")
    st.stop()

# Filtros
st.sidebar.title("Filtros")

# Garante que os filtros só são criados se houver dados
if "Ano" in df.columns and not df["Ano"].isna().all():
    min_year = int(df["Ano"].min()) if not pd.isna(df["Ano"].min()) else 2010
    max_year = int(df["Ano"].max()) if not pd.isna(df["Ano"].max()) else 2023
    year_range = st.sidebar.slider("Ano", min_year, max_year, (min_year, max_year))
else:
    year_range = (2010, 2023)

# Filtros seguros que verificam se a coluna existe
if "Tipo_ação_vítima" in df.columns:
    tipos_disponiveis = df["Tipo_ação_vítima"].dropna().unique().tolist()
    tipo_acao = st.sidebar.multiselect("Tipo de ação", tipos_disponiveis, default=tipos_disponiveis)
else:
    tipo_acao = []

if "Vítima_Gênero/Sexo" in df.columns:
    generos_disponiveis = df["Vítima_Gênero/Sexo"].dropna().unique().tolist()
    genero = st.sidebar.multiselect("Gênero da vítima", generos_disponiveis)
else:
    genero = []

if "Vítimas_Etnia" in df.columns:
    etnias_disponiveis = df["Vítimas_Etnia"].dropna().unique().tolist()
    etnia = st.sidebar.multiselect("Etnia da vítima", etnias_disponiveis)
else:
    etnia = []

# Filtragem segura
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

st.title("Sangue na Política")

# Função de cor por tipo
def get_color(tipo):
    cores = {
        'Assassinato': 'red',
        'Tentativa de assassinato': 'green',
        'Ameaça de assassinato': 'blue'
    }
    return cores.get(tipo, 'gray')

# Mapa
st.subheader("Mapa Interativo")

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
            ).add_to(m)
            
        except Exception as e:
            # Silenciosamente ignora erros ao adicionar marcadores
            continue
    
    # Adiciona legenda ao mapa
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; width: 220px;
    background-color: white; border:2px solid grey; z-index:9999; font-size:14px; padding: 10px;">
    <b>Legenda</b><br>
    <span style="color:red;">●</span> Assassinato<br>
    <span style="color:green;">●</span> Tentativa de assassinato<br>
    <span style="color:blue;">●</span> Ameaça de assassinato
    </div>
    """
    m.get_root().html.add_child(Element(legend_html))
    
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

# Linha do tempo
st.subheader("Linha do Tempo")
df_timeline = filtered[[
    'Ano', 'Mês', 'Tipo_ação_vítima', 'Vítimas_Etnia',
    'Vítimas_Afiliação_1/Grupo', 'Cidade', 'Disputa'
]].copy()

df_timeline = df_timeline.rename(columns={'Ano': 'year', 'Mês': 'month'})
df_timeline['day'] = 1
df_timeline['Data'] = pd.to_datetime(df_timeline[['year', 'month', 'day']], errors='coerce')
df_timeline = df_timeline.dropna(subset=['Data']).sort_values(by='Data')

df_timeline['Descrição'] = (
    "Tipo: " + df_timeline['Tipo_ação_vítima'].fillna("Não informado") + "<br>" +
    "Etnia: " + df_timeline['Vítimas_Etnia'].fillna("Não informada") + "<br>" +
    "Afiliação: " + df_timeline['Vítimas_Afiliação_1/Grupo'].fillna("Não informada") + "<br>" +
    "Cidade: " + df_timeline['Cidade'].fillna("Não informada") + "<br>" +
    "Disputa: " + df_timeline['Disputa'].fillna("Não informada")
)

fig = px.scatter(
    df_timeline,
    x='Data',
    y='Cidade',
    color='Tipo_ação_vítima',
    hover_name='Cidade',
    custom_data=['Descrição'],
    title="Linha do Tempo de Casos",
    labels={'Cidade': 'Local'},
    height=600
)
fig.update_traces(hovertemplate='%{customdata[0]}<extra></extra>')
fig.update_layout(xaxis_title="Data", yaxis_title="Cidade", showlegend=True)
st.plotly_chart(fig)
