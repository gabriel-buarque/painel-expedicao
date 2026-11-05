from caminhos import LOGO_TRANSPARENTE_STR, LOGO_FUNDO_STR ,garantir_pastas, PLANILHA_METAS

import streamlit as st
import pandas as pd
import numpy as np
import warnings
from datetime import datetime, timedelta
import base64

# Buscamos as funções que estão distribuídas nos outros arquivos do projeto
from alertas import configurar_logs, notificar_admin
from interface import renderizar_sidebar
from dados import carregar_dados_sistema, carregar_planilha_metas, STATUS_FONTES
from graficos import (
    plotar_realizado_previsto,
    plotar_grafico_linha,
    plotar_top_clientes,
)

# Cria logs/ e dados_locais/ se ainda não existirem
garantir_pastas()



#  CONFIGURAÇÕES INICIAIS DO SISTEMA
# Desativa avisos visuais chatos do Pandas sobre conexões diretas de SQL
warnings.filterwarnings('ignore', message='.*pandas only supports SQLAlchemy.*')


st.set_page_config(page_title="Painel de Expedição - Nassau", page_icon="🏭", layout="wide")

configurar_logs()

# Dicionário que traduz o nome do mês visual para o número usado nos filtros do banco de dados
MAPA_MESES = {
    "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6, 
    "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12
}

# === FORÇA O STREAMLIT A ZERAR A MEMÓRIA DOS FILTROS ANTIGOS ===
if "limpeza_inicial" not in st.session_state:
    st.session_state.clear() # Limpa resquícios antigos do navegador ao iniciar do zero
    st.session_state["limpeza_inicial"] = True



# 1. Função que lê a imagem e transforma em código Base64
def obter_base64(caminho_arquivo):
    try:
        with open(caminho_arquivo, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""



ESTILO_PAINEL = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* 
   PALETA — trocar aqui muda o painel inteiro
   */
:root {
    --marca:        #E96107;   
    --marca-clara:  #F2A876;
    --sidebar:      #2B2E33; 
    --fundo:        #EFF0F2;
    --cartao:       #FFFFFF;
    --tinta:        #14171A;  
    --tinta-suave:  #6B7280;   
    --linha:        #E3E5E9;
    --positivo:     #17803D;
    --negativo:     #C0342B;
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif !important;
    font-weight: 400;
    -webkit-font-smoothing: antialiased;
}

[data-testid="stAppViewContainer"] h1 {
    font-size: 2.4rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em;
    color: var(--tinta) !important;
    padding-bottom: 0 !important;
}
[data-testid="stAppViewContainer"] h2,
[data-testid="stAppViewContainer"] h3 {
    font-weight: 700 !important;
    letter-spacing: -0.01em;
    color: var(--tinta) !important;
}
[data-testid="stAppViewContainer"] h4 {
    font-weight: 600 !important;
    color: var(--tinta-suave) !important;
}
[data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] p {
    color: var(--tinta) !important;
    font-weight: 400;
}

/* 2. FUNDO E ESPACAMENTO */
.stApp { background-color: var(--fundo) !important; }

.block-container {
    padding-top: 2.2rem !important;
    padding-bottom: 3rem !important;
    max-width: 1600px;
}

/* Divisores mais discretos: a linha separa, nao chama atencao */
[data-testid="stAppViewContainer"] hr {
    border-color: var(--linha) !important;
    margin: 1.4rem 0 !important;
}

.stAppDeployButton,
[data-testid="stElementToolbar"] { display: none !important; }

[data-testid="stHeaderActionElements"],
[data-testid="stMarkdownContainer"] h1 a[href^="#"],
[data-testid="stMarkdownContainer"] h2 a[href^="#"],
[data-testid="stMarkdownContainer"] h3 a[href^="#"] { display: none !important; }
[data-testid="stVegaLiteChart"] details { display: none !important; }

/* 3. CARDS (KPIs e blocos de grafico)
   Faixa laranja no topo dos KPIs: da identidade sem poluir.
   */
[data-testid="stMetric"] {
    background: var(--cartao) !important;
    border: 1px solid var(--linha) !important;
    border-top: 3px solid var(--marca) !important;
    border-radius: 12px !important;
    padding: 18px 20px !important;
    box-shadow: 0 1px 3px rgba(20,23,26,0.04) !important;
    transition: box-shadow .18s ease, transform .18s ease;
    
    }
[data-testid="stMetric"]:hover {
    box-shadow: 0 6px 18px rgba(20,23,26,0.09) !important;
    transform: translateY(-2px);
}

/* Rotulo pequeno em caixa alta: o olho pula direto para o numero */
[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] * {
    color: var(--tinta-suave) !important;
    font-size: 0.92rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] * {
    color: var(--tinta) !important;
    font-size: 2.38rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.03em;
    text-shadow: none !important;
    line-height: 1.2 !important;
}
[data-testid="stMetricDelta"],
[data-testid="stMetricDelta"] * {
    font-size: 0.82rem !important;
    font-weight: 600 !important;
}

/* Blocos com borda (graficos) — mesmo acabamento dos KPIs */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--cartao) !important;
    border: 1px solid var(--linha) !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(20,23,26,0.04) !important;
}

/*  4. BARRA DA META (HTML próprio, ver barra_meta())
   Trilho neutro + preenchimento laranja + marcador do ritmo esperado.
   O trilho antigo era verde: a parte que FALTAVA parecia concluída. */
.meta-barra { margin: 0.9rem 0 0.2rem; }
.meta-topo {
    display: flex;
    align-items: baseline;
    gap: 6px;
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--tinta-suave);
    margin-bottom: 8px;
}
.meta-pct {
    font-size: 1.15rem;
    font-weight: 800;
    letter-spacing: -0.01em;
}
.meta-dir { margin-left: auto; }
.meta-trilho {
    position: relative;
    height: 12px;
    background: var(--linha);
    border-radius: 99px;
    margin-bottom: 30px;
}
.meta-preench {
    height: 100%;
    border-radius: 99px;
    /* Degradê preso à largura da BARRA INTEIRA (background-size vem do Python):
       com 40% da meta aparece só vermelho -> laranja; perto de 100%, chega no verde */
    background: linear-gradient(90deg, #C0342B 0%, #E8B10C 80%, #17803D 100%);
    transition: width .6s ease;
}
.meta-ritmo {
    position: absolute;
    top: -5px;
    bottom: -5px;
    width: 3px;
    margin-left: -1.5px;
    background: var(--tinta);
    border-radius: 2px;
}
.meta-ritmo span {
    position: absolute;
    top: 26px;
    left: 50%;
    transform: translateX(-50%);
    white-space: nowrap;
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--tinta-suave);
}
.meta-ritmo.inicio span { left: 0; transform: none; }
.meta-ritmo.fim span { left: auto; right: 0; transform: none; }

/* Selo de atualização embaixo do título */
.selo {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 4px 11px;
    border-radius: 99px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-top: 0.2rem;
}
.selo-ponto { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.selo-ok { background: #E7F5EC; color: var(--positivo); }
.selo-ok .selo-ponto { animation: pulso 2s ease-in-out infinite; }
.selo-backup { background: #FDF1E7; color: #B54A04; }
@keyframes pulso {
    0%, 100% { box-shadow: 0 0 0 0 rgba(23,128,61,0.45); }
    50%      { box-shadow: 0 0 0 5px rgba(23,128,61,0); }
}

/* 5. FILTROS */
div[data-baseweb="select"] > div,
div[data-baseweb="base-input"] > div,
div[data-testid="stDateInput"] input {
    background: var(--cartao) !important;
    border: 1px solid var(--linha) !important;
    border-radius: 10px !important;
    min-height: 42px;
    transition: border-color .15s ease, box-shadow .15s ease;
}
div[data-baseweb="select"] > div:hover,
div[data-testid="stDateInput"] input:hover { border-color: #C2C6CD !important; }

div[data-baseweb="select"] > div:focus-within,
div[data-testid="stDateInput"] input:focus {
    border-color: var(--marca) !important;
    box-shadow: 0 0 0 3px rgba(233,97,7,0.12) !important;
}

div[data-baseweb="select"] *,
div[data-baseweb="base-input"] input,
div[data-testid="stDateInput"] input {
    color: var(--tinta) !important;
    -webkit-text-fill-color: var(--tinta) !important;
    opacity: 1 !important;
    font-weight: 500 !important;
}

[data-testid="stWidgetLabel"] p {
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    color: var(--tinta-suave) !important;
}

/* Etiquetas dos filtros multiselect na cor da marca */
span[data-baseweb="tag"] {
    background-color: var(--marca) !important;
    border-radius: 6px !important;
}
span[data-baseweb="tag"] span { color: #FFFFFF !important; }

/* 6. MENUS FLUTUANTES E CALENDARIO
   Arredonda o quadrado do popover. overflow:hidden e o que faz o canto
   interno acompanhar — sem ele o container arredonda e o conteudo nao.
     */
div[data-baseweb="popover"] > div,
div[data-baseweb="calendar"] {
    border-radius: 12px !important;
    overflow: hidden !important;
    box-shadow: 0 8px 28px rgba(20,23,26,0.14) !important;
    border: 1px solid var(--linha) !important;
}
div[data-baseweb="popover"] *,
div[data-baseweb="menu"] *,
ul[role="listbox"] * {
    background-color: var(--cartao);
    color: var(--tinta) !important;
    -webkit-text-fill-color: var(--tinta) !important;
    opacity: 1 !important;
}
ul[role="listbox"] li:hover,
li[role="option"]:hover {
    background-color: var(--marca) !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    border-radius: 6px !important;
}
div[data-baseweb="calendar"] [role="gridcell"] > div { border-radius: 8px !important; }
div[data-baseweb="calendar"] [aria-selected="true"] {
    background-color: var(--marca) !important;
    color: #FFFFFF !important;
}

/*  7. SIDEBAR
   Grafite em vez de vinho: tira o terceiro vermelho da tela e deixa o logo
   e as barras laranja serem os unicos pontos de cor.
     */
[data-testid="stSidebar"] {
    background-color: var(--sidebar) !important;
    border-right: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stSidebar"] * { color: #E8EAED !important; }

[data-testid="stSidebar"] h1 {
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.01em;
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.10) !important;
    margin: 0.85rem 0 !important;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] label *,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] [data-testid="stExpander"] summary,
[data-testid="stSidebar"] [data-testid="stExpander"] summary *,
[data-testid="stSidebar"] button p,
[data-testid="stSidebar"] button span {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    opacity: 1 !important;
}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {
    color: rgba(255,255,255,0.55) !important;
    -webkit-text-fill-color: rgba(255,255,255,0.55) !important;
    font-size: 0.72rem !important;
}

/* Botoes: alinhados a esquerda, com barra laranja aparecendo no hover */
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    border-left: 3px solid transparent !important;
    border-radius: 8px !important;
    text-align: left !important;
    justify-content: flex-start !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    padding: 0.5rem 0.75rem !important;
    transition: background .15s ease, border-color .15s ease;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(233,97,7,0.16) !important;
    border-left-color: var(--marca) !important;
}
[data-testid="stSidebar"] .stButton > button:active,
[data-testid="stSidebar"] .stButton > button:focus {
    background: rgba(233,97,7,0.24) !important;
    border-left-color: var(--marca) !important;
    box-shadow: none !important;
}

/* Cabeçalho do expander da sidebar (a caixa "2026")
   O config.toml define secondaryBackgroundColor = branco, e o Streamlit usa
   essa cor no cabeçalho do expander. Somado à regra que força TODO texto da
   sidebar para branco, o ano ficava branco sobre branco — invisível. */
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    background-color: rgba(255,255,255,0.06) !important;
    border-radius: 10px !important;
    padding: 0.4rem 0.7rem !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
    background-color: rgba(233,97,7,0.16) !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
[data-testid="stSidebar"] [data-testid="stExpander"] summary span,
[data-testid="stSidebar"] [data-testid="stExpander"] summary div {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
    fill: #FFFFFF !important;
    color: #FFFFFF !important;
}

/* Caixa dos meses */
[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: rgba(0,0,0,0.18) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
}
[data-testid="stSidebar"] [data-baseweb="checkbox"] span[data-baseweb="checkbox"] > div:first-child,
[data-testid="stSidebar"] input[type="checkbox"] + div {
    border-radius: 5px !important;
}

/* 8. TABELA */
[data-testid="stDataFrame"] {
    border: 1px solid var(--linha) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}

/* 9. BOTAO DE DOWNLOAD */
[data-testid="stDownloadButton"] > button {
    background: var(--cartao) !important;
    border: 1px solid var(--linha) !important;
    border-radius: 10px !important;
    color: var(--tinta) !important;
    font-weight: 600 !important;
    transition: border-color .15s ease, color .15s ease;
}
[data-testid="stDownloadButton"] > button:hover {
    border-color: var(--marca) !important;
    color: var(--marca) !important;
}

/* Graficos sem fundo proprio */
.vega-embed, canvas { background-color: transparent !important; }

/* Faixa de secao: pequeno tracinho laranja antes do titulo */
.secao {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 0.4rem 0 0.9rem;
}
.secao-barra {
    width: 4px; height: 20px;
    background: var(--marca);
    border-radius: 99px;
}
.secao-texto {
    font-size: 1.02rem;
    font-weight: 700;
    color: var(--tinta);
    letter-spacing: -0.01em;
}
.secao-nota {
    font-size: 0.78rem;
    font-weight: 500;
    color: var(--tinta-suave);
    margin-left: auto;
}
</style>
"""

st.markdown(ESTILO_PAINEL, unsafe_allow_html=True)


def secao(titulo, nota=""):
    """
    Cabeçalho de seção com um traço laranja à esquerda.
    Substitui o st.subheader: separa os blocos da tela sem precisar de mais
    uma linha horizontal, que já é usada em vários lugares.
    """
    texto_nota = f'<span class="secao-nota">{nota}</span>' if nota else ""
    st.markdown(
        f'<div class="secao"><div class="secao-barra"></div>'
        f'<span class="secao-texto">{titulo}</span>{texto_nota}</div>',
        unsafe_allow_html=True,
    )


def pct_br(valor):
    """0.993 -> '99,3%' (vírgula decimal, como no resto do painel)."""
    return f"{valor:.1%}".replace(".", ",")


def cor_da_meta(pct, escurecer=0.15):
    """
    Cor do degradê da barra (vermelho 0% -> amarelo 50% -> verde 100%) no ponto
    'pct'. É a mesma cor que aparece na ponta da barra. Escurece 15% para o
    texto continuar legível no fundo claro (amarelo puro some no branco).
    """
    p = max(0.0, min(float(pct), 1.0))
    vermelho, amarelo, verde = (0xC0, 0x34, 0x2B), (0xE8, 0xB1, 0x0C), (0x17, 0x80, 0x3D)
    inicio, fim, t = (vermelho, amarelo, p / 0.5) if p <= 0.5 else (amarelo, verde, (p - 0.5) / 0.5)
    rgb = [round((a + (b - a) * t) * (1 - escurecer)) for a, b in zip(inicio, fim)]
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def caixa_com_chave(coluna, chave):
    """Container com key (vira a classe CSS .st-key-<chave>); Streamlit antigo ignora."""
    try:
        return coluna.container(key=chave)
    except TypeError:
        return coluna.container()


def css_delta(chave, cor):
    """
    CSS que pinta o selo de baixo de um st.metric (o "70,9% da Meta").
    Vai junto com o HTML da barra da meta: um st.markdown só com <style>
    dentro da coluna empurrava o card Expedido para baixo dos outros.
    """
    return (
        f"<style>.st-key-{chave} [data-testid='stMetricDelta']"
        f"{{color:{cor} !important; background:{cor}1F !important;}}"
        f".st-key-{chave} [data-testid='stMetricDelta'] *{{color:{cor} !important;}}"
        # só a seta: o ícone tem um quadrado transparente (fill="none") por trás,
        # que virava um quadrado colorido quando o fill era aplicado em tudo
        f".st-key-{chave} [data-testid='stMetricDelta'] svg path:not([fill='none'])"
        f"{{fill:{cor} !important;}}</style>"
    )


def barra_meta(pct_feito, pct_ritmo, dias_restantes, chave_card=None):
    """
    Substitui o st.progress: mostra quanto da meta já saiu E onde deveria
    estar hoje (traço escuro). O preenchimento vai de vermelho (0%) a verde
    (100% da meta) e o % usa a mesma cor da ponta da barra (cor_da_meta).
    O HTML vai em UMA linha: no markdown, linha com 4 espaços vira bloco de código.
    """
    feito = max(0.0, min(pct_feito, 1.0)) * 100
    ritmo = max(0.0, min(pct_ritmo, 1.0)) * 100
    tamanho_degrade = f"background-size:{100 / feito * 100:.0f}% 100%;" if feito > 0 else ""
    lado = "inicio" if ritmo < 12 else ("fim" if ritmo > 88 else "")
    dias = int(dias_restantes)
    chaves = [chave_card] if isinstance(chave_card, str) else list(chave_card or [])
    estilo_card = "".join(css_delta(c, cor_da_meta(pct_feito)) for c in chaves)
    st.markdown(
        estilo_card +
        f'<div class="meta-barra">'
        f'<div class="meta-topo"><span class="meta-pct" style="color:{cor_da_meta(pct_feito)}">{pct_br(pct_feito)}</span>'
        f'<span>da meta atingida</span>'
        f'<span class="meta-dir">restam {dias} dia{"s" if dias != 1 else ""} úte{"is" if dias != 1 else "l"}</span></div>'
        f'<div class="meta-trilho"><div class="meta-preench" style="width:{feito:.2f}%;{tamanho_degrade}"></div>'
        f'<div class="meta-ritmo {lado}" style="left:{ritmo:.2f}%">'
        f'<span>ritmo esperado hoje: {pct_br(pct_ritmo)}</span></div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def metas_por_mes(metas, pagina):
    """{mes: meta} da tela atual: soma de todas as unidades ou só a fábrica."""
    if pagina == "Painel Geral":
        total = {}
        for por_mes in metas.values():
            for m, v in por_mes.items():
                total[m] = total.get(m, 0) + v
        return total
    chave = next((k for k in metas if pagina.upper() in k), None)
    return dict(metas.get(chave, {})) if chave else {}


# DIAS TRABALHADOS — CÓPIA DA MEDIDA DAX "Dias trabalhados" DO POWER BI
# Peso de cada dia no Calendário (coluna "Útil"): seg a sex = 1, sábado = 0,5, domingo = 0
PESO_DIA = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 0.5, 6: 0.0}


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_feriados():
    """
    Lê a Feriados.xlsx (mesma pasta da Metas.xlsx).
    Devolve {FÁBRICA: {data: valor da coluna FERIADO}}.
    """
    caminho = PLANILHA_METAS.parent / "Feriados.xlsx"
    try:
        df = pd.read_excel(caminho, engine="openpyxl")
        df.columns = df.columns.astype(str).str.strip()
        df["Data"] = pd.to_datetime(df["DATA FERIADO"], dayfirst=True, errors="coerce").dt.date
        df["FERIADO"] = pd.to_numeric(df["FERIADO"], errors="coerce").fillna(0)
        df = df.dropna(subset=["Data"])
        return {
            str(fab).strip().upper(): dict(zip(g["Data"], g["FERIADO"]))
            for fab, g in df.groupby("Corporação")
        }
    except Exception as e:
        notificar_admin("Falha ao ler Feriados.xlsx", e)
        return {}


def feriados_da_pagina(feriados, pagina):
    """Feriados da fábrica da tela. No Painel Geral junta todas (cada data conta uma vez só)."""
    if pagina != "Painel Geral":
        chave = next((k for k in feriados if pagina.upper() in k or k in pagina.upper()), None)
        return feriados.get(chave, {})
    juntos = {}
    for por_data in feriados.values():
        for data, valor in por_data.items():
            juntos[data] = max(juntos.get(data, 0), valor)
    return juntos


def dias_trabalhados_no_mes(hoje, feriados):
    """
    Igual à medida DAX "Dias trabalhados":
      IF(Ontem < InicioMes, 0,
         SUM(Calendario[Útil]) - SUM(Feriados[FERIADO])   entre o dia 1º e ontem)
    Como no DAX, cada feriado tira o valor inteiro da coluna FERIADO,
    mesmo que caia num sábado ou domingo.
    """
    """VAR Hoje      = TODAY()
VAR InicioMes = DATE(YEAR(Hoje), MONTH(Hoje), 1)
VAR Ontem     = Hoje - 1
RETURN
IF(
    Ontem < InicioMes,
    0,
    VAR DiasUteisCalendario    = CALCULATE(SUM('Calendario'[Útil]),  DATESBETWEEN(..., InicioMes, Ontem))
    VAR TotalFeriadosNoPeriodo = CALCULATE(SUM(Feriados[FERIADO]),   DATESBETWEEN(..., InicioMes, Ontem))
    RETURN DiasUteisCalendario - COALESCE(TotalFeriadosNoPeriodo, 0)
)"""
    inicio_mes = hoje.replace(day=1)
    ontem = hoje - timedelta(days=1)
    if ontem < inicio_mes:
        return 0.0
    dias = (ontem - inicio_mes).days + 1
    dias_uteis_calendario = sum(PESO_DIA[(inicio_mes + timedelta(days=i)).weekday()] for i in range(dias))
    total_feriados = sum(valor for data, valor in feriados.items() if inicio_mes <= data <= ontem)
    return float(dias_uteis_calendario - total_feriados)


# FUNÇÃO PRINCIPAL DE EXECUÇÃO 
def executar_app():
    
    # 1. CARREGAMENTO DE DADOS OFICIAIS 
    # Busca as notas fiscais no MariaDB e as metas/dias úteis no arquivo Excel
    df_banco = carregar_dados_sistema()
    METAS_2026, DIAS_UTEIS_MES = carregar_planilha_metas()
    
    # Se o arquivo do Excel falhar ou sumir, exibe um aviso flutuante seguro na tela
    if not METAS_2026:
        st.toast("**Aviso:** Não foi possível carregar o arquivo de Metas. O painel está operando temporariamente com metas zeradas.", icon=":material/warning:")
  
    # RENDERIZAÇÃO DA BARRA LATERAL (MENU) 
    # Envia o mapa de meses e recebe os meses checados e a fábrica ativa selecionada pelo usuário
    meses_selecionados, pagina = renderizar_sidebar(MAPA_MESES)

    #  INTELIGÊNCIA TEMPORAL E CÁLCULO DE DIAS ÚTEIS ---
    hoje = datetime.now()
    mes_atual = hoje.month
    feriados_pagina = feriados_da_pagina(carregar_feriados(), pagina)
    DIAS_PASSADOS_MES = {}
    
    # Varre os 12 meses do ano para saber o andamento dei dias comerciais
    for m in range(1, 13):
        if m < mes_atual:
            # Meses passados: o tempo comercial já encerrou, então puxa os dias úteis totais daquele mês
            DIAS_PASSADOS_MES[m] = DIAS_UTEIS_MES.get(m, 22)
        elif m == mes_atual:
            # Mês presente: igual à medida DAX "Dias trabalhados" do Power BI
            # (dia 1º até ontem, sábado = 0,5, menos os feriados da Feriados.xlsx)
            DIAS_PASSADOS_MES[m] = dias_trabalhados_no_mes(hoje.date(), feriados_pagina)
        else:
            # Meses futuros: 0 dias passados
            DIAS_PASSADOS_MES[m] = 0.0

    # Consolida as métricas de tempo com base estritamente no bloco de meses marcados na barra lateral
    dias_uteis_totais = sum(DIAS_UTEIS_MES.get(m, 22) for m in meses_selecionados)
    dias_ja_passados = sum(DIAS_PASSADOS_MES.get(m, 0) for m in meses_selecionados)
    dias_restantes = max(0.0, dias_uteis_totais - dias_ja_passados)

    #  4. FILTRAGEM DINÂMICA DOS DADOS ---
    # Aplica o filtro dos meses selecionados nas notas fiscais importadas do banco
    if "Mês_Num" in df_banco.columns:
        df_filtrado_mes = df_banco[df_banco["Mês_Num"].isin(meses_selecionados)]
    else:
        df_filtrado_mes = df_banco

    # Regra de negócio: Define se a visualização é Consolidada ou individual por fábrica
    if pagina == "Painel Geral":
        df_filtrado = df_filtrado_mes
        # Soma a meta de todas as unidades cadastradas no Excel para os meses selecionados
        meta_do_mes = sum(sum(METAS_2026.get(fab, {}).get(m, 0) for m in meses_selecionados) for fab in METAS_2026)
        titulo_pg = "🏭 SAÍDA DIÁRIA DE CIMENTO — PERFORMANCE DE VENDAS"
        sub_pg = "### *Consolidado de Operação Geral*"
    else:
        # Filtra apenas as linhas pertencentes à fábrica selecionada (Ex: ITABIRA)
        if not df_filtrado_mes.empty and "Fábrica" in df_filtrado_mes.columns:
            df_filtrado = df_filtrado_mes[df_filtrado_mes["Fábrica"].str.upper().str.contains(pagina.upper(), na=False)]
        else:
            df_filtrado = df_filtrado_mes
            
        # Busca a meta individual da fábrica ativa na barra lateral
        chave_meta = next((k for k in METAS_2026.keys() if pagina.upper() in k), None)
        meta_do_mes = sum(METAS_2026[chave_meta].get(m, 0) for m in meses_selecionados) if chave_meta else 0
        titulo_pg = f":material/domain: Unidade operacional — {pagina}"
        sub_pg = f"#### Dados de saída em tempo real da fábrica {pagina}"

    # --- 5. CÁLCULO MATEMÁTICO DOS INDICADORES CRÍTICOS (KPIs) ---           
    
    faturado_ate_ontem = df_filtrado["Quantidade (Sacos)"].sum() if "Quantidade (Sacos)" in df_filtrado.columns else 0
    pct_tempo_passado = (dias_ja_passados / dias_uteis_totais) if dias_uteis_totais > 0 else 0
    
    # Formulas de cálculo dos indicadores de perfomance
    deveria_ter_faturado = meta_do_mes * pct_tempo_passado
    gap_atraso = deveria_ter_faturado - faturado_ate_ontem
    o_que_falta = meta_do_mes - faturado_ate_ontem
    media_diaria = (o_que_falta / dias_restantes) if dias_restantes > 0 else 0  
    pct_deveria = (deveria_ter_faturado / meta_do_mes) if meta_do_mes > 0 else 0
    pct_faturado = (faturado_ate_ontem / meta_do_mes) if meta_do_mes > 0 else 0

    # 6. RENDERIZAÇÃO DO CABEÇALHO
    col_t, col_l = st.columns([4, 1])
    with col_t:
        st.title(titulo_pg)

        st.markdown(sub_pg)
        # Carimbo de atualização: deixa claro que o dado tem hora, e não é "ao vivo"

    with col_l:
        st.image(LOGO_TRANSPARENTE_STR, width=170)

    st.markdown("---")
    secao(
        "Indicadores de vendas e performance",
        f"{len(meses_selecionados)} mês(es) selecionado(s)",
    )
    
    # --- 7. CARDS DE MÉTRICAS VISUAIS ---
    c1, c2, c3 = st.columns(3)
    with c1.container():
        # delta_color="off": "Dias úteis" é informação, não deveria vir com seta verde
        st.metric(":material/flag: Meta consolidada", f"{int(meta_do_mes):,} sacos".replace(",", "."), f":material/event_available: Dias úteis: {dias_uteis_totais}", delta_color="off")
    with caixa_com_chave(c2, "card_expedido"):
        # delta_color="off": a cor vem do css_delta (junto da barra da meta)
        st.metric(":material/inventory_2: Expedido", f"{int(faturado_ate_ontem):,} sacos".replace(",", "."), f"{pct_br(pct_faturado)} da Meta", delta_color="off")
    with caixa_com_chave(c3, "card_ritmo"):
        # Exibe em tempo real se a operação está no vermelho (Atraso) ou no verde (Adiantado)
        if gap_atraso > 0:
            delta_str = f"-{int(gap_atraso):,} sacos atrás do ritmo"
        else:
            delta_str = f"+{int(abs(gap_atraso)):,} sacos à frente do ritmo"
        st.metric(
            f":material/speed: Ritmo esperado",
            f"{int(deveria_ter_faturado):,} sacos".replace(",", "."),
            delta_str.replace(",", "."),
            delta_color="off",   # a cor vem do css_delta: a mesma da barra e do Expedido
            help="Quanto já deveria ter saído até hoje para fechar a meta no prazo: "
                 "meta × dias úteis que já passaram ÷ dias úteis do período. ")        
    c4, c5 = st.columns(2)
    with c4.container():
        st.metric(":material/pending_actions: Falta expedir", f"{int(max(0, o_que_falta)):,} sacos".replace(",", "."))
    with c5.container():
        st.metric(":material/bolt: Média diária necessária", f"{int(max(0, media_diaria)):,} sacos/dia".replace(",", "."))

    
    barra_meta(pct_faturado, pct_deveria, dias_restantes,
               chave_card=("card_expedido", "card_ritmo"))
    st.markdown("---")
    secao("Evolução e desempenho")

   # --- 8. BLOCO DOS GRÁFICOS DIÁRIOS ---
    dias_eixo = list(range(1, int(dias_uteis_totais) + 1))

    # TRUQUE VISUAL: Mostrar todos os meses no gráfico, independente do filtro lateral
    # Em vez de usar df_filtrado, puxamos os dados completos do df_banco
    if pagina == "Painel Geral":
        df_grafico = df_banco.copy()
    else:
  # Se estiver em uma fábrica específica, filtra apenas ela no banco geral
        df_grafico = df_banco[df_banco["Fábrica"].str.upper().str.contains(pagina.upper(), na=False)].copy()

    # LINHA 1 DE GRÁFICOS — Realizado x Previsto (só no consolidado)
    if pagina == "Painel Geral":
        with st.container(height=520, border=True):
            plotar_realizado_previsto(
                df_banco,
                METAS_2026,
                ["ITABIRA", "ITAPETINGA", "ITAPICURU", "CIBRASA"],
            )

    # LINHA 2 DE GRÁFICOS — evolução mensal + top clientes
    # Fora do if: estes dois valem tanto para o consolidado quanto para cada fábrica
    col_baixo1, col_baixo2 = st.columns([1, 1])

    with col_baixo1:
        with st.container(height=450, border=True):
            plotar_grafico_linha(
                df_grafico, dias_eixo, dias_ja_passados,
                "Quantidade (Sacos)", "", "#E96107",
                meta=metas_por_mes(METAS_2026, pagina),
                unidade="mi",
            )

    with col_baixo2:
        with st.container(height=450, border=True):
            plotar_top_clientes(df_filtrado)






    st.markdown("---")
    secao("Visão detalhada das saídas")
    
    # 1. Cria uma cópia limpa dos dados APENAS para a tabela
    df_tabela = df_filtrado.drop(columns=["Mês_Num", "Dia_Mes"], errors="ignore")

    if "Data" in df_tabela.columns:
        df_tabela["Data_Filtro"] = pd.to_datetime(df_tabela["Data"], format="%d/%m/%Y", errors="coerce").dt.date
    # 2. Agora criamos 4 colunas (uma a mais para acomodar a Data)
    col_t1, col_t2, col_t3, col_t4 = st.columns(4)

    # --- FILTRO 1: PERÍODO (DATA) ---
    if "Data_Filtro" in df_tabela.columns:
        min_date = df_tabela["Data_Filtro"].min()
        max_date = df_tabela["Data_Filtro"].max()
        
        # Verifica se as datas existem para não quebrar o painel
        if pd.notna(min_date) and pd.notna(max_date):
            filtro_data = col_t1.date_input(
                "Filtrar Período:",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                format="DD/MM/YYYY"
            )
            # Se o usuário escolheu data inicial e data final
            if isinstance(filtro_data, tuple) and len(filtro_data) == 2:
                data_inicio, data_fim = filtro_data
                df_tabela = df_tabela[(df_tabela["Data_Filtro"] >= data_inicio) & (df_tabela["Data_Filtro"] <= data_fim)]

    # --- FILTRO 2: CLIENTE ---
    if "Cliente" in df_tabela.columns:
        lista_cli = sorted(df_tabela["Cliente"].dropna().unique())
        filtro_cli = col_t2.multiselect("Filtrar Cliente:", lista_cli, placeholder="Todos os clientes...")
        if filtro_cli:
            df_tabela = df_tabela[df_tabela["Cliente"].isin(filtro_cli)]

    # --- FILTRO 3: PRODUTO ---
    if "Item" in df_tabela.columns:
        lista_item = sorted(df_tabela["Item"].dropna().unique())
        filtro_item = col_t3.multiselect("Filtrar Produto:", lista_item, placeholder="Todos os produtos...")
        if filtro_item:
            df_tabela = df_tabela[df_tabela["Item"].isin(filtro_item)]

    # --- FILTRO 4: STATUS ou PLACA ---
    if "Status" in df_tabela.columns:
        lista_status = sorted(df_tabela["Status"].dropna().unique())
        filtro_status = col_t4.multiselect("Filtrar Status:", lista_status, placeholder="Todos os status...")
        if filtro_status:
            df_tabela = df_tabela[df_tabela["Status"].isin(filtro_status)]
    elif "Placa" in df_tabela.columns:
        lista_placa = sorted(df_tabela["Placa"].dropna().unique())
        filtro_placa = col_t4.multiselect("Filtrar Placa:", lista_placa, placeholder="Todas as placas...")
        if filtro_placa:
            df_tabela = df_tabela[df_tabela["Placa"].isin(filtro_placa)]

    # Limpeza final antes de mostrar na tela (remove a coluna temporária de calendário)
    if "Data_Filtro" in df_tabela.columns:
        df_tabela = df_tabela.drop(columns=["Data_Filtro"])


    total_registros = len(df_tabela)

    if total_registros == 0:
        st.info("Nenhum registro encontrado para os filtros selecionados.")
    else:
        
        st.dataframe(
            df_tabela,
            use_container_width=True,
            hide_index=True,
            height=480,
            column_config={
                "Quantidade (Sacos)": st.column_config.NumberColumn(
                    "Quantidade (Sacos)", format="%.0f"
                ),
            },
        )

        col_info, col_baixar = st.columns([3, 1])
        with col_info:
            st.caption(f"{total_registros:,} registros no filtro atual.".replace(",", "."))
        with col_baixar:
            st.download_button(
                ":material/file_download: Baixar CSV",
                data=df_tabela.to_csv(index=False).encode("utf-8-sig"),
                file_name="expedicao.csv",
                mime="text/csv",
                use_container_width=True,
            )

    
# Ponto de partida inicial do Python
if __name__ == "__main__":
    executar_app()