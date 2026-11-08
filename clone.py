from caminhos import (
    RAIZ, ARQUIVO_LOG, CACHE_DADOS, PASTA_DADOS_LOCAIS, PLANILHA_METAS,
    LOGO_TRANSPARENTE_STR, garantir_pastas,
)
garantir_pastas()
import streamlit as st
import runpy
import pandas as pd
import numpy as np
import traceback
import smtplib
import logging
import time
import altair as alt
from email.message import EmailMessage
from datetime import datetime, timedelta
from pathlib import Path

#   0. LOG INTERNO ISOLADO DO CLONE

def _configurar_log_clone():
    try:
        log_path = ARQUIVO_LOG
        logger = logging.getLogger("clone")
        logger.setLevel(logging.ERROR)
        if not any(isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_path for h in logger.handlers):
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setLevel(logging.ERROR)
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | [CLONE] %(message)s"))
            logger.addHandler(handler)
        return logger
    except Exception:
        return logging.getLogger("clone")


_log_clone = _configurar_log_clone()


# 1. ALERTA POR E-MAIL

def notificar_erro_oculto(erro):
    detalhe = "".join(traceback.format_exception(type(erro), erro, erro.__traceback__))
    _log_clone.error(f"main.py falhou, clone assumiu o controle. Erro original:\n{detalhe}")

    try:
        cfg = st.secrets.get("alertas", {})
    except Exception as e:
        _log_clone.error(f"Não foi possível ler st.secrets['alertas'] dentro do clone: {e}")
        return

    chaves_obrigatorias = ["smtp_host", "smtp_port", "smtp_user", "smtp_password", "destinatario"]
    chaves_faltando = [k for k in chaves_obrigatorias if not cfg.get(k)]
    if chaves_faltando:
        _log_clone.error(f"Alerta por e-mail do clone desativado: faltam chaves em st.secrets['alertas']: {', '.join(chaves_faltando)}")
        return

    try:
        msg = EmailMessage()
        msg["Subject"] = "🚨 ERRO OCULTO - Painel rodando via Clone de Contingência"
        msg["From"] = cfg.get("remetente", cfg.get("smtp_user"))
        msg["To"] = cfg["destinatario"]
        msg.set_content(
            "O main.py falhou. O clone.py assumiu o controle visual usando o cache local.\n\n"
            f"Detalhes:\n{detalhe}"
        )
        # timeout igual ao alertas.py: sem ele, um SMTP fora do ar congela a tela
        with smtplib.SMTP_SSL(cfg["smtp_host"], int(cfg.get("smtp_port", 465)), timeout=15) as smtp:
            smtp.login(cfg["smtp_user"], cfg["smtp_password"])
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        _log_clone.error(f"Falha de autenticação SMTP no clone (usuário/senha incorretos): {e}")
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError) as e:
        _log_clone.error(f"Falha de conexão com servidor SMTP no clone (host/porta inacessível): {e}")
    except Exception as e:
        _log_clone.error(f"Falha não identificada ao enviar e-mail de alerta pelo clone: {e}")


# 2. CONSTANTES E CSS — CÓPIA FIEL DO main.py

MAPA_MESES = {
    "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6,
    "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12
}

FABRICAS = ["ITABIRA", "ITAPETINGA", "ITAPICURU", "CIBRASA"]

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
/* Ícone de link (🔗) que o Streamlit mostra ao lado dos títulos */
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
    background: linear-gradient(90deg, #C0342B 0%, #E8B10C 50%, #17803D 100%);
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


def secao(titulo, nota=""):
    """Cabeçalho de seção com um traço laranja à esquerda (cópia do main.py)."""
    texto_nota = f'<span class="secao-nota">{nota}</span>' if nota else ""
    st.markdown(
        f'<div class="secao"><div class="secao-barra"></div>'
        f'<span class="secao-texto">{titulo}</span>{texto_nota}</div>',
        unsafe_allow_html=True,
    )



# Cópias do main.py

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
def carregar_feriados_clone():
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
        _log_clone.error(f"Falha ao ler Feriados.xlsx no clone ({caminho}): {e}")
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
    inicio_mes = hoje.replace(day=1)
    ontem = hoje - timedelta(days=1)
    if ontem < inicio_mes:
        return 0.0
    dias = (ontem - inicio_mes).days + 1
    dias_uteis_calendario = sum(PESO_DIA[(inicio_mes + timedelta(days=i)).weekday()] for i in range(dias))
    total_feriados = sum(valor for data, valor in feriados.items() if inicio_mes <= data <= ontem)
    return float(dias_uteis_calendario - total_feriados)


# 3. DADOS LOCAIS (backup gravado pelo dados.py + Metas.xlsx)

COLUNAS_PAINEL = [
    "Fábrica", "Data", "Cliente", "Placa",
    "Quantidade (Sacos)", "Item", "Mês_Num", "Dia_Mes",
]

# Ordem de procura do backup. O dados.py atual grava "ultimo_postgres.csv"
# (um arquivo por fonte); os outros dois são nomes antigos, mantidos só
# para não deixar o clone vazio em instalações que ainda não migraram.
ARQUIVOS_BACKUP = (
    PASTA_DADOS_LOCAIS / "ultimo_postgres.csv",
    CACHE_DADOS,
    RAIZ / "ultimo_df_banco.csv",
)


@st.cache_data(ttl=600, show_spinner=False)
def carregar_cache_local():
    """
    Lê o CSV que o dados.py grava a cada carga bem-sucedida.
    Devolve (DataFrame, data_da_ultima_atualizacao).
    """
    caminho = next((c for c in ARQUIVOS_BACKUP if c.exists()), None)
    if caminho is None:
        return pd.DataFrame(columns=COLUNAS_PAINEL), None

    try:
        df = pd.read_csv(caminho)
        idade = datetime.fromtimestamp(caminho.stat().st_mtime)

        # O CSV perde os tipos: força número onde precisa ser número
        for col in ["Mês_Num", "Dia_Mes"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        if "Quantidade (Sacos)" in df.columns:
            df["Quantidade (Sacos)"] = pd.to_numeric(
                df["Quantidade (Sacos)"], errors="coerce"
            ).fillna(0.0)

        # Descarta as colunas internas (_doc, _fonte) e restos de versões antigas
        df = df[[c for c in COLUNAS_PAINEL if c in df.columns]]

        return df, idade
    except Exception as e:
        _log_clone.error(f"Falha ao ler o cache local do clone ({caminho}): {e}")
        return pd.DataFrame(columns=COLUNAS_PAINEL), None


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_planilha_metas_clone():
    """Mesma leitura de metas do dados.py, sem depender de importação."""
    caminho_excel = PLANILHA_METAS
    if not caminho_excel.exists():
        _log_clone.error(f"Metas.xlsx não encontrado no clone: {caminho_excel}")
        return {}, {}
    try:
        df_excel = pd.read_excel(caminho_excel, engine="openpyxl")
        df_excel.columns = df_excel.columns.astype(str).str.strip()
        df_excel["Unidade"] = df_excel["Unidade"].astype(str).str.strip().str.upper()
        df_excel["Mês"] = pd.to_numeric(df_excel["Mês"], errors="coerce").fillna(0).astype(int)
        df_excel["Vendas"] = pd.to_numeric(df_excel["Vendas"], errors="coerce").fillna(0)

        if "Dias" in df_excel.columns:
            df_excel["Dias"] = pd.to_numeric(df_excel["Dias"], errors="coerce").fillna(22)
        else:
            df_excel["Dias"] = 22

        metas_dinamicas = {}
        for fabrica in df_excel["Unidade"].unique():
            df_fab = df_excel[df_excel["Unidade"] == fabrica].drop_duplicates(subset=["Mês"], keep="last")
            metas_dinamicas[fabrica] = dict(zip(df_fab["Mês"], df_fab["Vendas"]))

        df_dias = df_excel.drop_duplicates(subset=["Mês"], keep="last")
        return metas_dinamicas, dict(zip(df_dias["Mês"], df_dias["Dias"]))
    except Exception as e:
        _log_clone.error(f"Falha ao ler Metas.xlsx no clone: {e}")
        return {}, {}


# 4. SIDEBAR — CÓPIA FIEL DA interface.py (com keys próprias do clone)

def renderizar_sidebar_clone(mapa_meses):
    if "pagina_atual" not in st.session_state:
        st.session_state.pagina_atual = "Painel Geral"

    mes_padrao = datetime.now().month

    for num_mes in mapa_meses.values():
        if f"mes_cl_{num_mes}" not in st.session_state:
            st.session_state[f"mes_cl_{num_mes}"] = (num_mes == mes_padrao)

    with st.sidebar:

        from PIL import Image
        st.image(Image.open("assets/Fundo-transp.png"), width=110)
        st.title("Controle de Expedição")
        st.markdown("---")

        # botao de atualizar dados
        if st.button(":material/sync: Atualizar dados", key="btn_refresh_clone",
                     use_container_width=True,
                     disabled=st.session_state.get("_atualizando_clone", False)):
            st.session_state["_atualizando_clone"] = True

            # Só o cache de dados. A conexão (cache_resource) continua viva.
            st.cache_data.clear()

            # Sai da contingência: o próximo carregamento tenta o main.py de novo
            st.session_state.pop("_contingencia_desde", None)

            # Volta os filtros ao padrão SEM destruir os widgets
            for n_m in mapa_meses.values():
                st.session_state[f"mes_cl_{n_m}"] = (n_m == mes_padrao)
            st.session_state["check_todos_clone"] = False
            st.session_state.pagina_atual = "Painel Geral"

            st.session_state["_atualizando_clone"] = False
            st.toast("Dados atualizados", icon=":material/check_circle:")
            st.rerun()

        st.markdown("---")
        st.markdown("**:material/date_range: Competência temporal**")

        meses_selecionados = []

        with st.expander(str(datetime.now().year), expanded=True):

            # A key do checkbox e a key lida no callback PRECISAM ser a mesma.
            def alterar_todos_meses():
                estado = st.session_state["check_todos_clone"]
                for n_m in mapa_meses.values():
                    st.session_state[f"mes_cl_{n_m}"] = estado

            st.checkbox("Selecionar Todos os Meses", key="check_todos_clone", on_change=alterar_todos_meses)
            st.markdown("---")

            for nome, num in mapa_meses.items():
                if st.checkbox(nome, key=f"mes_cl_{num}"):
                    meses_selecionados.append(num)

        if not meses_selecionados:
            st.warning(":material/error_outline: Selecione pelo menos um mês.")
            st.stop()

        st.markdown("---")
        st.markdown("Escolha a tela que deseja visualizar:")

        if st.button("Painel Geral", icon=":material/space_dashboard:", key="btn_geral_clone",
                     use_container_width=True):
            st.session_state.pagina_atual = "Painel Geral"

        st.markdown("---")
        st.markdown("**:material/domain: Unidades**")

        for fabrica in FABRICAS:
            if st.button(fabrica, key=f"btn_{fabrica}_clone", use_container_width=True):
                st.session_state.pagina_atual = fabrica

        st.markdown("---")
        st.caption("Controle de Expedição · Cimento Nassau")

    return sorted(list(set(meses_selecionados))), st.session_state.pagina_atual


# 5. GRÁFICOS — CÓPIA FIEL DO graficos.py

COR_MARCA = "#E96107"
COR_REALIZADO = "#002CA7"
COR_PREVISTO = "#E08A1E"
CINZA_TEXTO = "#14171A"
CINZA_GRADE = "#DBDBDF"
CINZA_SUAVE = "#6B7280"
COR_BATEU = "#17803D"      # mesmo --positivo do CSS
COR_NAO_BATEU = "#C0342B"  # mesmo --negativo do CSS

MESES_CURTO = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}

SUFIXOS_SOCIETARIOS = (" Ltda", " S/A", " S.A", " Sa")


MESES_LONGO = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}



def _clarear(cor_hex, fator=0.40):
    """Mistura a cor com branco. fator=0 devolve a original, 1 devolve branco."""
    c = cor_hex.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    return "#{:02X}{:02X}{:02X}".format(
        int(r + (255 - r) * fator),
        int(g + (255 - g) * fator),
        int(b + (255 - b) * fator),
    )


def _num_br(valor, casas=0):
    return f"{valor:,.{casas}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def _abreviar(valor, unidade="auto"):
    if unidade == "mi":
        return f"{_num_br(valor / 1_000_000, 2)} mi"
    if unidade == "mil":
        return f"{_num_br(valor / 1_000, 1)} mil"
    if abs(valor) >= 1_000_000:
        return f"{_num_br(valor / 1_000_000, 2)} mi"
    if abs(valor) >= 1_000:
        return f"{_num_br(valor / 1_000, 1)} mil"
    return _num_br(valor, 0)


def _texto_diferenca(valor):
    """Quanto passou (+) ou faltou (-) da meta, curto pro gráfico: +604 mil / -1,04 mi."""
    sinal = "+" if valor >= 0 else "-"
    v = abs(valor)
    if v >= 1_000_000:
        return f"{sinal}{_num_br(v / 1_000_000, 2)} mi"
    if v >= 1_000:
        return f"{sinal}{_num_br(v / 1_000, 0)} mil"
    return f"{sinal}{_num_br(v, 0)} sacos"


def _gradiente(cor, vertical=True, fator=0.38):
    """Gradiente de duas paradas: cor cheia -> cor clareada."""
    stops = [
        alt.GradientStop(color=cor, offset=0),
        alt.GradientStop(color=_clarear(cor, fator), offset=1),
    ]
    if vertical:
        return alt.Gradient(gradient="linear", stops=stops, x1=1, x2=1, y1=1, y2=0)
    return alt.Gradient(gradient="linear", stops=stops, x1=0, x2=1, y1=0, y2=0)


# Altura TOTAL dos dois gráficos lado a lado (Evolução e Top 5), já contando
# os nomes dos meses embaixo. Igual nos dois = o texto de baixo de cada um
# fica exatamente na mesma linha.
ALTURA_LINHA_2 = 320


def _finalizar(grafico, altura, altura_total=False):
    """
    Acabamento comum aos tres graficos: sem borda, fundo transparente.
    altura_total=True: a altura passa a valer para o gráfico inteiro (eixos e
    rótulos incluídos), e não só para a área das barras.
    """
    extra = {"autosize": alt.AutoSizeParams(type="fit", contains="padding")} if altura_total else {}
    return (
        grafico.properties(
            height=altura,
            view=alt.ViewConfig(strokeWidth=0, stroke=None, strokeOpacity=0),
            **extra,
        )
        .configure_view(strokeWidth=0, stroke=None, strokeOpacity=0)
        .configure(background="transparent")
    )


def legenda_bolinhas(itens):
    """
    Legenda "bolinha colorida + texto em negrito", no mesmo estilo da legenda
    do Realizado x Previsto. itens = [(cor, texto), ...]
    """
    partes = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:18px">'
        f'<span style="width:11px;height:11px;border-radius:50%;background:{cor};'
        f'display:inline-block"></span>{texto}</span>'
        for cor, texto in itens
    )
    st.markdown(f'<div style="font-size:0.8rem;font-weight:700;color:{CINZA_TEXTO};'
                f'line-height:1.6">{partes}</div>', unsafe_allow_html=True)


def _falhar_silencioso(titulo, erro, mensagem):
    """Registra o erro sem derrubar a tela (no clone, só no log isolado)."""
    _log_clone.error(f"{titulo}: {erro}")
    st.info(mensagem)


def _preparar_evolucao(df, coluna, mes_corrente, unidade="auto", meta=None):
    """Agrega por mes e cruza com a meta. Devolve no maximo 12 linhas."""
    if df.empty or "Mês_Num" not in df.columns or coluna not in df.columns:
        return pd.DataFrame()

    d = df.groupby("Mês_Num", as_index=False)[coluna].sum()
    d["Mês"] = d["Mês_Num"].map(MESES_CURTO)
    d["Rótulo"] = d[coluna].map(lambda v: _abreviar(v, unidade))

    # Vetorizado, sem apply(axis=1)
    em_andamento = d["Mês_Num"].eq(mes_corrente)
    d["Situação"] = em_andamento.map({True: "Em andamento", False: "Fechado"})
    d["Detalhe"] = d[coluna].map(lambda v: _num_br(v, 1))
    d.loc[em_andamento, "Detalhe"] += " (mês em andamento)"

    # Meta do mês ({mes: meta}); sem meta, o gráfico fica como era antes
    d["Meta"] = d["Mês_Num"].map(meta or {}).fillna(0).astype(float)
    tem_meta = d["Meta"] > 0
    pct = (d[coluna] / d["Meta"]).where(tem_meta)

    # Selo acima da barra: % da meta nos meses fechados, "parcial" no mês atual
    d["Selo"] = ""
    d["Cor_Selo"] = CINZA_SUAVE
    fechado = ~em_andamento & tem_meta
    bateu, nao_bateu = fechado & (pct >= 1), fechado & (pct < 1)
    d.loc[bateu, "Selo"] = "▲ " + (pct[bateu] * 100).round().astype(int).astype(str) + "%"
    d.loc[nao_bateu, "Selo"] = "▼ " + (pct[nao_bateu] * 100).round().astype(int).astype(str) + "%"
    d.loc[bateu, "Cor_Selo"] = COR_BATEU
    d.loc[nao_bateu, "Cor_Selo"] = COR_NAO_BATEU
    d.loc[em_andamento, "Selo"] = "parcial"

    # Diferença em sacos: quanto vendeu a mais (+) ou quanto faltou (-) pra meta.
    # No gráfico só aparece nos meses fechados (os que têm o selo ▲▼);
    # na dica (passando o mouse) aparece também no mês em andamento.
    dif = d[coluna] - d["Meta"]
    d["Dif_Selo"] = ""
    d.loc[fechado, "Dif_Selo"] = dif[fechado].map(_texto_diferenca)
    acima, abaixo = tem_meta & (dif >= 0), tem_meta & (dif < 0)
    d["Dif_Texto"] = "—"
    d.loc[acima, "Dif_Texto"] = dif[acima].map(lambda v: "+" + _num_br(v, 0) + " sacos acima da meta")
    d.loc[abaixo, "Dif_Texto"] = dif[abaixo].map(lambda v: _num_br(-v, 0) + " sacos abaixo da meta")

    # O número fica acima do que for mais alto (barra ou traço da meta),
    # senão ele fica em cima do traço
    d["Topo"] = d[[coluna, "Meta"]].max(axis=1)
    d["Meta_Texto"] = d["Meta"].map(lambda v: _num_br(v, 0) + " sacos" if v > 0 else "sem meta")
    d["Pct_Texto"] = pct.map(lambda v: _num_br(v * 100, 1) + "%" if pd.notna(v) else "—")

    return d.sort_values("Mês_Num")


def _preparar_top_clientes(df, quantidade):
    """Ranking. Devolve no maximo 'quantidade' linhas + o total do periodo."""
    if df.empty or "Cliente" not in df.columns:
        return pd.DataFrame(), 0.0

    total = float(df["Quantidade (Sacos)"].sum())

    d = (
        df.groupby("Cliente", as_index=False)["Quantidade (Sacos)"]
        .sum()
        .nlargest(quantidade, "Quantidade (Sacos)")   # nlargest e mais rapido que sort+head
        .reset_index(drop=True)
    )
    if d.empty:
        return d, total

    # Encurta o nome sem perder identificacao
    nomes = d["Cliente"].astype(str).str.title()
    for sufixo in SUFIXOS_SOCIETARIOS:
        nomes = nomes.str.replace(sufixo, "", regex=False)
    nomes = nomes.str.strip()
    nomes = nomes.where(nomes.str.len() <= 28, nomes.str.slice(0, 28) + "…")

    d["Nome"] = (d.index + 1).astype(str) + ". " + nomes

    # Volume + fatia do período ao lado da barra: "41.230 · 18%"
    fatia = d["Quantidade (Sacos)"] / total if total > 0 else 0
    d["Rótulo"] = d["Quantidade (Sacos)"].map(lambda v: _num_br(v, 0))
    d["Exato"] = d["Rótulo"] + " sacos"
    if total > 0:
        d["Rótulo"] = d["Rótulo"] + " · " + (fatia * 100).round().astype(int).astype(str) + "%"
        d["Fatia"] = (fatia * 100).map(lambda v: _num_br(v, 1) + "% do período")
    else:
        d["Fatia"] = "—"

    # Coluna real com o teto da escala. Precisa ser COLUNA e não alt.datum():
    # num gráfico em camadas, uma camada sem campo no eixo X quebra o Vega-Lite
    # (erro "Cannot destructure property 'aggregate'") e o gráfico some da tela.
    # Folga de 45% para o rótulo "volume · %" caber à direita da 1ª barra,
    # mesmo com o gráfico espremido na coluna da direita.
    d["Teto"] = float(d["Quantidade (Sacos)"].max()) * 1.45

    return d, total


def _preparar_cruzado(df, metas_da_selecao, mes_corrente):
    """
    Monta Realizado x Previsto em formato longo, sem laco Python.
    'metas_da_selecao' e um dict {mes: meta} ja resolvido pelo chamador.
    """
    if df.empty or "Mês_Num" not in df.columns:
        return pd.DataFrame()

    real = df.groupby("Mês_Num", as_index=False)["Quantidade (Sacos)"].sum()
    real = real.rename(columns={"Quantidade (Sacos)": "Realizado"})

    meta = pd.DataFrame(
        {"Mês_Num": list(metas_da_selecao.keys()),
         "Previsto": list(metas_da_selecao.values())}
    )

    d = real.merge(meta, on="Mês_Num", how="outer").fillna(0)

    # Meses que ainda não chegaram não têm "Realizado": sem isso a linha azul
    # despencava para 0 em Nov/Dez. Vazio = a linha para no mês atual.
    d.loc[d["Mês_Num"] > mes_corrente, "Realizado"] = None

    # Valor zerado não vira ponto no gráfico (ex.: mês atual ainda sem notas):
    # sem isso aparecia um "0" no chão e a linha despencava até ele
    d[["Realizado", "Previsto"]] = d[["Realizado", "Previsto"]].mask(d[["Realizado", "Previsto"]] == 0)

    # Mes sem realizado E sem meta e mes futuro: nao deve puxar a linha para baixo
    # Só entram os meses que já tiveram venda: mês sem expedição (ainda não
    # vendeu) some do gráfico inteiro, inclusive a meta, até aparecer venda
    d = d[d["Realizado"] > 0]
    if d.empty:
        return d

    d["Mês"] = d["Mês_Num"].map(MESES_CURTO)
    d = d.sort_values("Mês_Num")

    longo = d.melt(
        id_vars=["Mês_Num", "Mês"],
        value_vars=["Realizado", "Previsto"],
        var_name="Tipo",
        value_name="Valor",
    )
    longo = longo.dropna(subset=["Valor"])
    longo["Texto"] = longo["Valor"].map(_abreviar)

    # Quem esta por cima naquele mes recebe o rotulo acima; o outro, abaixo
    maior = longo.groupby("Mês_Num")["Valor"].transform("max")
    longo["Posicao"] = (longo["Valor"] >= maior).map({True: "Topo", False: "Baixo"})
    longo["Parcial"] = longo["Mês_Num"].eq(mes_corrente)

    return longo


# GRAFICO 1 — REALIZADO x PREVISTO

def plotar_realizado_previsto(df_banco, metas, unidades, altura=390,
                              chave="seletor_fabrica_grafico_topo_clone"):

    col_titulo, col_filtro, col_periodo = st.columns([2.2, 1, 1])
    with col_titulo:
        st.markdown("### :material/trending_up: META VS REALIZADO (SACOS DE 50KG)")
    with col_filtro:
        escolha = st.selectbox("Filtrar Unidade:", ["TODAS (CONSOLIDADO)"] + list(unidades), key=chave)

    try:
        df_topo = df_banco
        if escolha != "TODAS (CONSOLIDADO)" and "Fábrica" in df_banco.columns:
            df_topo = df_banco[df_banco["Fábrica"].str.upper().str.contains(escolha.upper(), na=False)]

        # Resolve a meta ANTES de chamar a funcao cacheada (dict e barato de hashear)
        if escolha == "TODAS (CONSOLIDADO)":
            metas_sel = {}
            for por_mes in metas.values():
                for m, v in por_mes.items():
                    metas_sel[m] = metas_sel.get(m, 0) + v
        else:
            chave_meta = next((k for k in metas if escolha.upper() in k), None)
            metas_sel = dict(metas.get(chave_meta, {})) if chave_meta else {}

        dados = _preparar_cruzado(df_topo, metas_sel, datetime.now().month)
        if dados.empty:
            st.info("Sem dados suficientes para exibir o gráfico cruzado.")
            return

        # Mesma correção da ordem: lista explícita, sem repetir mês (o melt duplica)
        ordem_x = list(dict.fromkeys(dados["Mês"].tolist()))

        # Filtro de período: UMA caixa só com os meses que têm dados.
        # "Todos os meses" vem marcado; a key leva a unidade (cada uma tem seus meses).
        meses = sorted(int(m) for m in dados["Mês_Num"].unique())
        opcoes = ["Todos os meses"] + [MESES_LONGO[m] for m in meses]
        periodo = col_periodo.selectbox("Período:", opcoes, index=0,
                                        key=f"{chave}_periodo_{escolha}")
        if periodo != "Todos os meses":
            mes_escolhido = meses[opcoes.index(periodo) - 1]
            dados = dados[dados["Mês_Num"] == mes_escolhido]
            ordem_x = [MESES_CURTO[mes_escolhido]]

        escala_cor = alt.Scale(domain=["Realizado", "Previsto"],
                               range=[COR_REALIZADO, COR_PREVISTO])

        base = alt.Chart(dados)

        eixo_x = alt.X("Mês:N", sort=ordem_x, title=None,
                       axis=alt.Axis(labelAngle=0, labelFontSize=15, labelFontWeight="bold",
                                     labelColor=CINZA_TEXTO, grid=False,
                                     domain=False, ticks=False))
        # Sem eixo, começar do zero só deixava a metade de baixo vazia: a escala
        # acompanha os dados e os números escritos em cada ponto evitam leitura errada
        eixo_y = alt.Y("Valor:Q", title=None,
                       scale=alt.Scale(zero=False, padding=45),
                       axis=None)   # sem eixo e sem grade: os valores já estão nos rótulos

        linhas = base.mark_line(
            strokeWidth=3.5, point=alt.OverlayMarkDef(size=85, filled=True)
        ).encode(
            x=eixo_x, y=eixo_y,
            color=alt.Color("Tipo:N", scale=escala_cor,
                            legend=alt.Legend(orient="bottom", title=None, labelFontSize=13,
                                              labelFontWeight="bold", labelColor=CINZA_TEXTO,
                                              symbolSize=110)),
            tooltip=[alt.Tooltip("Mês:N", title="Mês"),
                     alt.Tooltip("Tipo:N", title="Indicador"),
                     alt.Tooltip("Valor:Q", title="Volume (sacos)", format=",.0f")],
        )

        def _rotulo(posicao, deslocamento, ancora):
            """Contorno branco + texto na MESMA cor da linha (antes eram cores distintas)."""
            filtro = base.transform_filter(alt.datum.Posicao == posicao)
            comum = dict(align="center", baseline=ancora, dy=deslocamento,
                         fontSize=16, fontWeight=900)
            contorno = filtro.mark_text(
                stroke="#FFFFFF", strokeWidth=3.5, strokeJoin="round", **comum
            ).encode(x=eixo_x, y=eixo_y, text="Texto:N")
            texto = filtro.mark_text(**comum).encode(
                x=eixo_x, y=eixo_y, text="Texto:N",
                color=alt.Color("Tipo:N", scale=escala_cor, legend=None),
            )
            return contorno, texto

        topo_contorno, topo_texto = _rotulo("Topo", -26, "bottom")
        baixo_contorno, baixo_texto = _rotulo("Baixo", 26, "top")

        grafico = alt.layer(linhas, topo_contorno, topo_texto, baixo_contorno, baixo_texto)
        st.altair_chart(_finalizar(grafico, altura), use_container_width=True, theme=None)
        

    except Exception as e:
        _falhar_silencioso("Erro no gráfico Realizado x Previsto", e,
                           "Gráfico comparativo temporariamente indisponível.")


# GRAFICO 2 — EVOLUCAO MENSAL (barras)

def plotar_grafico_linha(df, dias_eixo=None, dias_passados=None,
                         coluna="Sacos (em Milhares)", titulo="",
                         cor_linha=COR_MARCA, meta=None, altura=ALTURA_LINHA_2,
                         unidade="mi"):
    """
    Barras mensais com gradiente, mes corrente marcado como parcial e,
    quando 'meta' ({mes: meta}) vem preenchida, traço da meta e valores em sacos.
    Assinatura preservada para nao quebrar as chamadas existentes.
    """
    eh_fisico = "SACO" in str(coluna).upper() or "FÍSIC" in str(titulo).upper()
    st.markdown(
        "**:material/bar_chart: RESUMO DE EVOLUÇÃO FÍSICA**" if eh_fisico
        else "**:material/monitoring: RESUMO DE EVOLUÇÃO FINANCEIRA**"
    )

    try:
        dados = _preparar_evolucao(df, coluna, datetime.now().month, unidade, meta)
        if dados.empty:
            st.info("Sem dados suficientes para gerar evolução.")
            return

        # Evolução física: somente volumes/diferenças em sacos, sem porcentagem.
        # Outras modalidades mantêm o tooltip original.
        if eh_fisico:
            dados = dados.copy()
            dados["Detalhe"] = dados[coluna].map(lambda v: f"{_num_br(v, 0)} sacos")
            dados.loc[dados["Situação"].eq("Em andamento"), "Detalhe"] += " (mês em andamento)"

        teto = float(dados[[coluna, "Meta"]].max().max()) * 1.42 or 1
        base = alt.Chart(dados)

        # Ordem EXPLÍCITA (Jan, Fev, Mar...). EncodingSortField não funciona em
        # gráfico de camadas: o Vega-Lite não resolve por qual camada ordenar e
        # cai na ordem alfabética (Abr, Ago, Fev, Jan...).
        ordem_meses = dados["Mês"].tolist()
        eixo_x = alt.X("Mês:N", sort=ordem_meses, title=None,
                       axis=alt.Axis(labelAngle=0, domain=False, ticks=False, grid=False,
                                     labelFontSize=15, labelPadding=10,
                                     labelColor=CINZA_TEXTO, labelFontWeight="bold"))
        escala_y = alt.Scale(domain=[0, teto], nice=False)
        eixo_y = alt.Y(f"{coluna}:Q", title=None, scale=escala_y,
                       axis=alt.Axis(labels=False, domain=False, ticks=False,
                                     gridColor=CINZA_GRADE, gridDash=[2, 4], gridOpacity=0.7))
        y_topo = alt.Y("Topo:Q", scale=escala_y, title=None)

        dica = [alt.Tooltip("Mês:N", title="Mês"),
                alt.Tooltip("Detalhe:N", title="Expedido"),
                alt.Tooltip("Meta_Texto:N", title="Meta")]
        if not eh_fisico:
            dica.append(alt.Tooltip("Pct_Texto:N", title="% da meta"))
        dica.append(alt.Tooltip("Dif_Texto:N", title="Diferença"))

        sombra = base.mark_bar(color="#000000", opacity=0.07, size=44,
                               cornerRadiusTopLeft=6, cornerRadiusTopRight=6,
                               xOffset=3, yOffset=3).encode(x=eixo_x, y=eixo_y)

        barras = base.mark_bar(
            size=44, cornerRadiusTopLeft=6, cornerRadiusTopRight=6,
            color=_gradiente(cor_linha, vertical=True),
        ).encode(
            x=eixo_x, y=eixo_y,
            opacity=alt.Opacity("Situação:N",
                                scale=alt.Scale(domain=["Fechado", "Em andamento"],
                                                range=[1.0, 0.45]),
                                legend=None),
            tooltip=dica,
        )

        # Traço da meta: um pouco mais largo que a barra para "abraçar" o topo dela
        traco_meta = base.transform_filter(alt.datum.Meta > 0).mark_tick(
            thickness=3, size=58, color=CINZA_TEXTO, opacity=0.85, cornerRadius=2,
        ).encode(x=eixo_x, y=alt.Y("Meta:Q", scale=escala_y, title=None), tooltip=dica)

        linha_base = base.mark_rule(color=CINZA_TEXTO, strokeWidth=1.5,
                                    opacity=0.25).encode(y=alt.datum(0))

        rotulos = base.mark_text(align="center", baseline="bottom", dy=-9,
                                 color=CINZA_TEXTO, fontSize=13,
                                 fontWeight="bold").encode(x=eixo_x, y=y_topo, text="Rótulo:N")

        # Selo percentual: exibido apenas em gráficos que não são de evolução física.
        selo = base.transform_filter(alt.datum.Selo != "").mark_text(
            align="center", baseline="bottom", dy=-26, fontSize=11, fontWeight="bold",
        ).encode(x=eixo_x, y=y_topo, text="Selo:N",
                 color=alt.Color("Cor_Selo:N", scale=None, legend=None))

        # Diferença em sacos (+63 mil / -1,04 mi) perto do volume das barras.
        # Sem o selo percentual na evolução física, aproximamos essa linha.
        diferenca = base.transform_filter(alt.datum.Dif_Selo != "").mark_text(
            align="center", baseline="bottom", dy=-26 if eh_fisico else -40,
            fontSize=11, fontWeight="bold",
        ).encode(x=eixo_x, y=y_topo, text="Dif_Selo:N",
                 color=alt.Color("Cor_Selo:N", scale=None, legend=None))

        camadas = [sombra, barras, traco_meta, linha_base, rotulos]
        if not eh_fisico:
            camadas.append(selo)
        camadas.append(diferenca)
        grafico = alt.layer(*camadas)
        st.altair_chart(_finalizar(grafico, altura, altura_total=True),
                        use_container_width=True, theme=None)

        itens = [(cor_linha, "Qtd de sacos")]
        if (dados["Meta"] > 0).any():
            itens.append((CINZA_TEXTO, "Meta"))
        legenda_bolinhas(itens)

    except Exception as e:
        _falhar_silencioso("Erro no gráfico mensal", e,
                           "Visualização gráfica temporariamente indisponível.")


# GRAFICO 3 — TOP CLIENTES

def plotar_top_clientes(df_filtrado, cor=COR_MARCA, quantidade=5, altura=ALTURA_LINHA_2):
    """Ranking de clientes com posicao numerada, volume e fatia do periodo."""
    st.markdown(f"**:material/trophy: TOP {quantidade} CLIENTES (VOLUME EM SACOS)**")

    try:
        dados, total = _preparar_top_clientes(df_filtrado, quantidade)
        if dados.empty:
            st.info("Dados de clientes indisponíveis para o filtro selecionado.")
            return

        # A folga no teto e o que impede o rotulo da 1a barra de ser cortado na borda
        teto = float(dados["Teto"].iloc[0])
        escala_x = alt.Scale(domain=[0, teto], nice=False)
        eixo_sem_marcas = alt.Axis(labels=False, domain=False, grid=False, ticks=False)
        base = alt.Chart(dados)

        # Ordem EXPLÍCITA pela lista de nomes (os dados já vêm ordenados).
        # sort="-x" quebra em gráfico de camadas: o Vega-Lite não consegue
        # resolver qual "x" usar e o gráfico inteiro deixa de renderizar.
        eixo_y = alt.Y("Nome:N", sort=dados["Nome"].tolist(), title=None,
                       axis=alt.Axis(grid=False, domain=False, ticks=False, labelLimit=320,
                                     labelFontSize=13, labelFontWeight="bold",
                                     labelColor=CINZA_TEXTO, labelPadding=12))
        eixo_x = alt.X("Quantidade (Sacos):Q", title=None,
                       scale=escala_x, axis=eixo_sem_marcas)

        # Trilho de fundo: da a nocao de quanto cada um representa do lider
        trilho = base.mark_bar(color="#000000", opacity=0.05, size=30,
                               cornerRadiusTopRight=6,
                               cornerRadiusBottomRight=6).encode(
            y=eixo_y,
            x=alt.X("Teto:Q", scale=escala_x, title=None, axis=eixo_sem_marcas))

        barras = base.mark_bar(
            size=30, cornerRadiusTopRight=6, cornerRadiusBottomRight=6,
            color=_gradiente(cor, vertical=False, fator=0.35),
        ).encode(
            y=eixo_y, x=eixo_x,
            tooltip=[alt.Tooltip("Cliente:N", title="Razão Social"),
                     alt.Tooltip("Exato:N", title="Volume"),
                     alt.Tooltip("Fatia:N", title="Participação")],
        )

        rotulos = base.mark_text(align="left", baseline="middle", dx=10,
                                 color=CINZA_TEXTO, fontSize=13,
                                 fontWeight="bold").encode(y=eixo_y, x=eixo_x, text="Rótulo:N")

        grafico = alt.layer(trilho, barras, rotulos)
        st.altair_chart(_finalizar(grafico, altura, altura_total=True),
                        use_container_width=True, theme=None)

        if total > 0:
            fatia = float(dados["Quantidade (Sacos)"].sum()) / total
            st.caption(f"Os {len(dados)} maiores concentram "
                       f"{_num_br(fatia * 100, 1)}% do volume do período.")

    except Exception as e:
        _falhar_silencioso("Erro no Top de clientes", e,
                           "Ranking temporariamente indisponível.")


# 6. PAINEL COMPLETO OFFLINE — ESPELHO DO executar_app() do main.py

def renderizar_painel_offline(idade_cache):
    df_banco, _ = carregar_cache_local()
    METAS_2026, DIAS_UTEIS_MES = carregar_planilha_metas_clone()

    if not METAS_2026:
        st.toast("**Aviso:** Não foi possível carregar o arquivo de Metas. O painel está operando temporariamente com metas zeradas.", icon=":material/warning:")

    meses_selecionados, pagina = renderizar_sidebar_clone(MAPA_MESES)

    # --- INTELIGÊNCIA TEMPORAL (idêntica ao main.py) ---
    hoje = datetime.now()
    mes_atual = hoje.month
    feriados_pagina = feriados_da_pagina(carregar_feriados_clone(), pagina)
    DIAS_PASSADOS_MES = {}

    for m in range(1, 13):
        if m < mes_atual:
            DIAS_PASSADOS_MES[m] = DIAS_UTEIS_MES.get(m, 22)
        elif m == mes_atual:
            # Mês presente: igual à medida DAX "Dias trabalhados" do Power BI
            # (dia 1º até ontem, sábado = 0,5, menos os feriados da Feriados.xlsx)
            DIAS_PASSADOS_MES[m] = dias_trabalhados_no_mes(hoje.date(), feriados_pagina)
        else:
            DIAS_PASSADOS_MES[m] = 0.0

    dias_uteis_totais = sum(DIAS_UTEIS_MES.get(m, 22) for m in meses_selecionados)
    dias_ja_passados = sum(DIAS_PASSADOS_MES.get(m, 0) for m in meses_selecionados)
    dias_restantes = max(0.0, dias_uteis_totais - dias_ja_passados)

    # --- FILTRAGEM ---
    if "Mês_Num" in df_banco.columns:
        df_filtrado_mes = df_banco[df_banco["Mês_Num"].isin(meses_selecionados)]
    else:
        df_filtrado_mes = df_banco

    if pagina == "Painel Geral":
        df_filtrado = df_filtrado_mes
        meta_do_mes = sum(sum(METAS_2026.get(fab, {}).get(m, 0) for m in meses_selecionados) for fab in METAS_2026)
        titulo_pg = "🏭 SAÍDA DIÁRIA DE CIMENTO — PERFORMANCE DE VENDAS"
        sub_pg = "### *Consolidado de Operação Geral*"
    else:
        if not df_filtrado_mes.empty and "Fábrica" in df_filtrado_mes.columns:
            df_filtrado = df_filtrado_mes[df_filtrado_mes["Fábrica"].str.upper().str.contains(pagina.upper(), na=False)]
        else:
            df_filtrado = df_filtrado_mes

        chave_meta = next((k for k in METAS_2026.keys() if pagina.upper() in k), None)
        meta_do_mes = sum(METAS_2026[chave_meta].get(m, 0) for m in meses_selecionados) if chave_meta else 0
        titulo_pg = f":material/domain: Unidade operacional — {pagina}"
        sub_pg = f"#### Dados de saída em tempo real da fábrica {pagina}"

    # --- KPIs ---
    faturado_ate_ontem = df_filtrado["Quantidade (Sacos)"].sum() if "Quantidade (Sacos)" in df_filtrado.columns else 0
    pct_tempo_passado = (dias_ja_passados / dias_uteis_totais) if dias_uteis_totais > 0 else 0

    deveria_ter_faturado = meta_do_mes * pct_tempo_passado
    gap_atraso = deveria_ter_faturado - faturado_ate_ontem
    o_que_falta = meta_do_mes - faturado_ate_ontem
    media_diaria = (o_que_falta / dias_restantes) if dias_restantes > 0 else 0
    pct_deveria = (deveria_ter_faturado / meta_do_mes) if meta_do_mes > 0 else 0
    pct_faturado = (faturado_ate_ontem / meta_do_mes) if meta_do_mes > 0 else 0

    # --- CABEÇALHO ---
    col_t, col_l = st.columns([4, 1])
    with col_t:
        st.title(titulo_pg)
        st.markdown(sub_pg)
    with col_l:
        from PIL import Image
        st.image(Image.open("assets/Fundo-transp.png"), width=170)

    st.markdown("---")
    secao(
        "Indicadores de vendas e performance",
        f"{len(meses_selecionados)} mês(es) selecionado(s)",
    )

    # --- CARDS DE MÉTRICAS ---
    c1, c2, c3 = st.columns(3)
    with c1.container():
        st.metric(":material/flag: Meta consolidada", f"{int(meta_do_mes):,} sacos".replace(",", "."), f":material/event_available: Dias úteis: {dias_uteis_totais}", delta_color="off")
    with caixa_com_chave(c2, "card_expedido_clone"):
        # delta_color="off": a cor vem do css_delta (junto da barra da meta)
        st.metric(":material/inventory_2: Expedido", f"{int(faturado_ate_ontem):,} sacos".replace(",", "."), f"{pct_br(pct_faturado)} da Meta", delta_color="off")
    with caixa_com_chave(c3, "card_ritmo_clone"):
        if gap_atraso > 0:
            delta_str = f"-{int(gap_atraso):,} sacos atrás do ritmo"
        else:
            delta_str = f"+{int(abs(gap_atraso)):,} sacos à frente do ritmo"
        st.metric(
            f":material/speed: Ritmo esperado · {pct_br(pct_deveria)} do tempo",
            f"{int(deveria_ter_faturado):,} sacos".replace(",", "."),
            delta_str.replace(",", "."),
            delta_color="off",   # a cor vem do css_delta: a mesma da barra e do Expedido
            help="Quanto já deveria ter saído até hoje para fechar a meta no prazo: "
                 "meta × dias úteis que já passaram ÷ dias úteis do período. "
                 "Ex.: meta de 220.000 e 11 de 22 dias úteis passados = 110.000 sacos.",
        )

    c4, c5 = st.columns(2)
    with c4.container():
        st.metric(":material/pending_actions: Falta expedir", f"{int(max(0, o_que_falta)):,} sacos".replace(",", "."))
    with c5.container():
        st.metric(":material/bolt: Média diária necessária", f"{int(max(0, media_diaria)):,} sacos/dia".replace(",", "."))

    barra_meta(pct_faturado, pct_deveria, dias_restantes,
               chave_card=("card_expedido_clone", "card_ritmo_clone"))
    st.markdown("---")
    secao("Evolução e desempenho")

    # --- BLOCO DOS GRÁFICOS ---
    dias_eixo = list(range(1, int(dias_uteis_totais) + 1))

    if pagina == "Painel Geral":
        df_grafico = df_banco.copy()
    elif "Fábrica" in df_banco.columns:
        df_grafico = df_banco[df_banco["Fábrica"].str.upper().str.contains(pagina.upper(), na=False)].copy()
    else:
        df_grafico = df_banco.copy()

    # LINHA 1 — Realizado x Previsto (só no consolidado)
    if pagina == "Painel Geral":
        with st.container(height=520, border=True):
            plotar_realizado_previsto(df_banco, METAS_2026, FABRICAS)

    # LINHA 2 — evolução mensal + top clientes
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

    # --- TABELA DETALHADA ---
    st.markdown("---")
    secao("Visão detalhada das saídas")

    df_tabela = df_filtrado.drop(columns=["Mês_Num", "Dia_Mes"], errors="ignore")

    if "Data" in df_tabela.columns:
        df_tabela["Data_Filtro"] = pd.to_datetime(df_tabela["Data"], format="%d/%m/%Y", errors="coerce").dt.date

    col_t1, col_t2, col_t3, col_t4 = st.columns(4)

    # FILTRO 1: PERÍODO
    if "Data_Filtro" in df_tabela.columns:
        min_date = df_tabela["Data_Filtro"].min()
        max_date = df_tabela["Data_Filtro"].max()
        if pd.notna(min_date) and pd.notna(max_date):
            filtro_data = col_t1.date_input(
                "Filtrar Período:",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                format="DD/MM/YYYY",
                key="filtro_data_clone",
            )
            if isinstance(filtro_data, tuple) and len(filtro_data) == 2:
                data_inicio, data_fim = filtro_data
                df_tabela = df_tabela[(df_tabela["Data_Filtro"] >= data_inicio) & (df_tabela["Data_Filtro"] <= data_fim)]

    # FILTRO 2: CLIENTE
    if "Cliente" in df_tabela.columns:
        lista_cli = sorted(df_tabela["Cliente"].dropna().unique())
        filtro_cli = col_t2.multiselect("Filtrar Cliente:", lista_cli,
                                        placeholder="Todos os clientes...", key="filtro_cli_clone")
        if filtro_cli:
            df_tabela = df_tabela[df_tabela["Cliente"].isin(filtro_cli)]

    # FILTRO 3: PRODUTO
    if "Item" in df_tabela.columns:
        lista_item = sorted(df_tabela["Item"].dropna().unique())
        filtro_item = col_t3.multiselect("Filtrar Produto:", lista_item,
                                         placeholder="Todos os produtos...", key="filtro_item_clone")
        if filtro_item:
            df_tabela = df_tabela[df_tabela["Item"].isin(filtro_item)]

    # FILTRO 4: STATUS ou PLACA
    if "Status" in df_tabela.columns:
        lista_status = sorted(df_tabela["Status"].dropna().unique())
        filtro_status = col_t4.multiselect("Filtrar Status:", lista_status,
                                           placeholder="Todos os status...", key="filtro_status_clone")
        if filtro_status:
            df_tabela = df_tabela[df_tabela["Status"].isin(filtro_status)]
    elif "Placa" in df_tabela.columns:
        lista_placa = sorted(df_tabela["Placa"].dropna().unique())
        filtro_placa = col_t4.multiselect("Filtrar Placa:", lista_placa,
                                          placeholder="Todas as placas...", key="filtro_placa_clone")
        if filtro_placa:
            df_tabela = df_tabela[df_tabela["Placa"].isin(filtro_placa)]

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
                key="btn_csv_clone",
            )


# 7. ESCUDO INTERCEPTADOR

def _e_controle_do_streamlit(erro):
    """
    st.stop() e st.rerun() funcionam LEVANTANDO exceção internamente.
    Se o clone engolir essas duas, ele assume o controle sempre que o usuário
    clicar em 'Atualizar' ou desmarcar todos os meses — o que faria o painel
    entrar em contingência sem nenhum problema real ter acontecido.
    A checagem é pelo NOME da classe para não depender da versão do Streamlit.
    """
    nomes_de_controle = {"RerunException", "StopException", "RerunData", "NoSessionContext"}
    for classe in type(erro).__mro__:
        if classe.__name__ in nomes_de_controle:
            return True
    return False


# Por quanto tempo a sessão fica no clone antes de tentar o main.py de novo.
# O botão "Atualizar dados" do clone também força uma nova tentativa na hora.
TEMPO_CONTINGENCIA = 10 * 60  # segundos


def _em_contingencia():
    desde = st.session_state.get("_contingencia_desde")
    return desde is not None and (time.time() - desde) < TEMPO_CONTINGENCIA


def _renderizar_clone():
    # Nesta execução o main.py não rodou, então esta é a primeira chamada.
    # O try fica só por garantia: um set_page_config repetido não pode
    # derrubar justamente a tela de contingência.
    try:
        st.set_page_config(page_title="Painel de Expedição - Nassau", page_icon="🏭", layout="wide")
    except Exception:
        pass
    st.markdown(ESTILO_PAINEL, unsafe_allow_html=True)

    _, _idade = carregar_cache_local()

    try:
        renderizar_painel_offline(_idade)
    except Exception as erro_fatal:
        if _e_controle_do_streamlit(erro_fatal):
            raise
        _log_clone.error(f"O próprio clone falhou ao renderizar: {erro_fatal}")
        st.error(
            "🚨 O painel principal falhou e o modo de contingência também não conseguiu "
            "montar a tela. Verifique se o backup 'dados_locais/ultimo_postgres.csv' existe e se a "
            "planilha 'Metas.xlsx' está acessível. O erro completo foi gravado em app_errors.log."
        )


if _em_contingencia():
    # Sessão já marcada: nem tenta o main.py, desenha só o clone
    _renderizar_clone()
else:
    try:
        # Caminho feliz: roda o painel principal normalmente
        runpy.run_path(str(RAIZ / "main.py"), run_name="__main__")

    except Exception as e:
        # Deixa passar os sinais internos do Streamlit (não são falhas)
        if _e_controle_do_streamlit(e):
            raise

        # A partir daqui é falha de verdade: registra e avisa
        notificar_erro_oculto(e)

        # Mesma limpeza de sessão do main.py, feita ANTES de marcar a
        # contingência (senão o clear() apagaria a própria marcação)
        if "limpeza_inicial" not in st.session_state:
            st.session_state.clear()
            st.session_state["limpeza_inicial"] = True

        # Se o main caiu no meio, metade da tela dele já está desenhada.
        # Desenhar o clone por baixo deixaria duas sidebars e dois cabeçalhos.
        # Em vez disso, marca a sessão e recomeça a execução: o Streamlit
        # descarta o que sobrou do main e só o clone aparece.
        st.session_state["_contingencia_desde"] = time.time()
        st.rerun()