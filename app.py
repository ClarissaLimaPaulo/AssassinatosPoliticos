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
        valor = "".join([c if c.isdigit() or c in ['.', '-'] else "" for c in valor])
        partes = valor.split(".")
        if len(partes) > 2:
            valor = partes[0] + "." + "".join(partes[1:])
        try:
            valor_float = float(valor)
            if abs(valor_float) > 1000:
                valor_float /= 100000
            return valor_float
        except ValueError:
            return None
    return valor

# Carregar e preparar os dados
@st.cache_data
def load_data():
    df = pd.read_csv("assassinatos_com_coordenadas (1) (1).csv")
    df.rename(columns=lambda x: x.strip(), inplace=True)
    df["Latitude"] = df["Latitude"].apply(corrigir_coordenada)
    df["Longitude"] = df["Longitude"].apply(corrigir_coordenada)
    df = df.dropna(subset=["Latitude", "Longitude"])
    df["Ano"] = df["Ano"].astype(int)

    def formatar_data(row):
        if row["Dia"] == "SI" or row["Mês"] == "SI":
            return str(row["Ano"])
        return f"{row['Dia']}/{row['Mês']}/{row['Ano']}"
    df["data_formatada"] = df.apply(formatar_data, axis=1)
    return df

df = load_data()

# Filtros
st.sidebar.title("Filtros")
year_range = st.sidebar.slider("Ano", int(df["Ano"].min()), int(df["Ano"].max()), (2010, 2023))
tipo_acao = st.sidebar.multiselect("Tipo de ação", df["Tipo_ação_vítima"].dropna().unique(), default=df["Tipo_ação_vítima"].dropna().unique())
genero = st.sidebar.multiselect("Gênero da vítima", df["Vítima_Gênero/Sexo"].dropna().unique())
etnia = st.sidebar.multiselect("Etnia da vítima", df["Vítimas_Etnia"].dropna().unique())

filtered = df[
    (df["Ano"] >= year_range[0]) &
    (df["Ano"] <= year_range[1]) &
    (df["Tipo_ação_vítima"].isin(tipo_acao)) &
    (df["Vítima_Gênero/Sexo"].isin(genero) if genero else True) &
    (df["Vítimas_Etnia"].isin(etnia) if etnia else True)
]

st.title("Monitor de Assassinatos Políticos no Brasil")

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
m = folium.Map(
    location=[-14.235, -51.9253],
    zoom_start=4,
    tiles='CartoDB positron',
    max_bounds=True,
    min_zoom=4
)
m.fit_bounds([[-33.75, -73.99], [5.27, -34.0]])

# Grupos
todos_os_casos = folium.FeatureGroup(name='Todos os casos', show=True).add_to(m)
grupo_genero = {}
grupo_etnia = {}

for g in filtered['Vítima_Gênero/Sexo'].dropna().unique():
    grupo = folium.FeatureGroup(name=f"GÊNERO | {g}", show=False)
    grupo_genero[g] = grupo
    grupo.add_to(m)

for e in filtered['Vítimas_Etnia'].dropna().unique():
    grupo = folium.FeatureGroup(name=f"ETNIA | {e}", show=False)
    grupo_etnia[e] = grupo
    grupo.add_to(m)

# Adicionar marcadores
for _, row in filtered.iterrows():
    popup_info = f"""<b>Vítima:</b> {row['Vítima_Nome Civil*(Apelido/Nome Social)']}<br>
<b>Descrição:</b> {row['Descrição']}<br>
<b>Data:</b> {row['data_formatada']}<br>
<b>Instrumento:</b> {row['Instrumento_1']}<br>
<b>Disputa:</b> {row['Disputa']}<br>
"""
    marker = folium.CircleMarker(
        location=[row['Latitude'], row['Longitude']],
        radius=5,
        color=get_color(row['Tipo_ação_vítima']),
        fill=True,
        fill_color=get_color(row['Tipo_ação_vítima']),
        fill_opacity=0.7,
        popup=folium.Popup(popup_info, max_width=300)
    )
    marker.add_to(todos_os_casos)

    g = row['Vítima_Gênero/Sexo']
    if g in grupo_genero:
        marker.add_to(grupo_genero[g])
    
    e = row['Vítimas_Etnia']
    if e in grupo_etnia:
        marker.add_to(grupo_etnia[e])

folium.LayerControl(collapsed=False).add_to(m)

legend_html = """
<div style="position: fixed; bottom: 50px; left: 50px; width: 200px;
background-color: white; border:2px solid grey; z-index:9999; font-size:14px; padding: 10px;">
<b>Legenda</b><br>
<span style="color:red;">●</span> Assassinato<br>
<span style="color:green;">●</span> Tentativa de assassinato<br>
<span style="color:blue;">●</span> Ameaça de assassinato
</div>
"""
m.get_root().html.add_child(Element(legend_html))

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
