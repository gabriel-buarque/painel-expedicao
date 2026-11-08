import streamlit as st
import pandas as pd
from datetime import datetime

from alertas import notificar_admin
from caminhos import PASTA_DADOS_LOCAIS, CACHE_DADOS, PLANILHA_METAS, garantir_pastas

garantir_pastas()

COLUNAS_PAINEL = [
    "Fábrica", "Data", "Cliente", "Placa",
    "Quantidade (Sacos)", "Item", "Mês_Num", "Dia_Mes",
]

DATA_INICIO = "2026-01-01"




STATUS_FONTES = {}

# Identificação das quatro fábricas SOMENTE pelo código da empresa.
# cod_empresa é a única chave usada no filtro, sem cod_estabel.
CODIGOS_FABRICAS = {
    "ITABIRA": "1",       # ITABIRA-CI no cadastro de empresas
    "ITAPETINGA": "3",
    "ITAPICURU": "5",
    "CIBRASA": "4",
}

# Traduz os números recebidos do banco para os nomes usados no painel.
MAPA_FABRICAS = {codigo: fabrica for fabrica, codigo in CODIGOS_FABRICAS.items()}
CODIGOS_SQL = ", ".join(f"'{codigo}'" for codigo in CODIGOS_FABRICAS.values())
FONTES = {
    "postgres": {
        "tipo": "postgres",
       "query": f"""
            SELECT
                TRIM(CAST(cod_empresa AS TEXT)) AS fabrica,
                dt_emis_nota                    AS data_hora,
                nome_cliente                    AS cliente,
                placa                           AS placa,
                CASE
                    WHEN COALESCE(observacao, '') ILIKE '%NOTA FISCAL COMPL%' THEN '0'
                    ELSE qtd_sacos_50kg
                END                             AS quantidade,
                nr_nota_fis                     AS documento,
                status_nfe                      AS status,
                desc_item                       AS item
            FROM public.esexp001hist
            WHERE dt_emis_nota >= '2026-01-01'
              AND TRIM("familia_produto") IN ('CPI', 'CPII', 'CPIII', 'CPIV', 'CPV')
              AND dt_cancel IS NULL
              AND TRIM(status_nfe) = 'Uso autorizado'
              
              AND (qt_devolucao IS NULL OR TRIM(CAST(qt_devolucao AS TEXT)) = '' OR TRIM(CAST(qt_devolucao AS TEXT)) IN ('0', '0,00', '0.00'))
              AND CAST(cfop AS TEXT) NOT IN (
                  '5151', '6151', '5922', '6922', '5923', '6923', '5949', '6949', 
                  '5911', '6911', '5910', '5924', '6924', '1201', '1208', '1410', 
                  '1910', '2201', '2203', '2410', '2910'
              )
              AND TRIM(CAST(cod_empresa AS TEXT)) IN ({CODIGOS_SQL})
        """,
        "status_validos": ["Uso autorizado", "USO AUTORIZADO"],
        "mapa_fabricas": MAPA_FABRICAS,
        "fabrica_fixa": None,
        "fator_sacos": 1,
        "fator_granel": 1, 
        "fabricas_excluidas": [],
    },
}

# 2. CONEXÕES

@st.cache_resource(show_spinner="Conectando ao Postgres...")
def conectar_postgres():
    """pool_pre_ping testa a conexão antes de usar e reconecta sozinho."""
    try:
        from sqlalchemy import create_engine
        seg = st.secrets["postgres"]
        url = (f"postgresql+psycopg2://{seg['user']}:{seg['password']}"
               f"@{seg['host']}:{seg['port']}/{seg['database']}")
        return create_engine(url, pool_pre_ping=True, pool_recycle=1800)
    except Exception as e:
        notificar_admin("Falha de conexão com o Postgres (CIBRASA)", e)
        return None


# 3. BACKUP — UM ARQUIVO POR FONTE
# Com apenas uma fonte, o backup fica simples e mais confiável.

def criar_dataframe_vazio():
    return pd.DataFrame(columns=COLUNAS_PAINEL)


def _caminho_backup(nome_fonte):
    return PASTA_DADOS_LOCAIS / f"ultimo_{nome_fonte}.csv"


def salvar_backup(nome_fonte, df):
    if df.empty:
        return
    try:
        destino = _caminho_backup(nome_fonte)
        temporario = destino.with_suffix(".tmp")
        df.to_csv(temporario, index=False)
        temporario.replace(destino)
    except Exception as e:
        notificar_admin(f"Erro ao salvar backup da fonte {nome_fonte}", e)


def ler_backup(nome_fonte):
    caminho = _caminho_backup(nome_fonte)

    # Compatibilidade: em versões antigas o backup pode estar em nome de fonte
    # anterior. Se vier do legado, tenta usar o arquivo único antigo.
    if not caminho.exists() and nome_fonte == "postgres" and CACHE_DADOS.exists():
        caminho = CACHE_DADOS

    if not caminho.exists():
        return criar_dataframe_vazio(), None

    try:
        df = pd.read_csv(caminho)
        df = df[[c for c in COLUNAS_PAINEL if c in df.columns]]
        for col in ("Mês_Num", "Dia_Mes"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        if "Quantidade (Sacos)" in df.columns:
            df["Quantidade (Sacos)"] = pd.to_numeric(
                df["Quantidade (Sacos)"], errors="coerce"
            ).fillna(0.0)
        return df, datetime.fromtimestamp(caminho.stat().st_mtime)
    except Exception as e:
        notificar_admin(f"Erro ao ler backup da fonte {nome_fonte}", e)
        return criar_dataframe_vazio(), None


# 4. NORMALIZAÇÃO — o funil por onde TODA fonte passa

def normalizar(df_bruto, nome_fonte, cfg):
    """Converte o resultado cru de qualquer banco para as 8 colunas do painel."""
    df = df_bruto.copy()

    # --- Limpeza de texto (precisa vir ANTES do filtro de status) ---
    for col in ("fabrica", "cliente", "item", "status", "placa"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.upper().str.strip()

    # --- Só notas válidas (cada ERP tem seu vocabulário de status) ---
    validos = [s.upper() for s in cfg.get("status_validos", [])]
    if "status" in df.columns and validos:
        df = df[df["status"].isin(validos)]

    # --- Nome da fábrica padronizado (é o que faz a meta casar) ---
    # A consulta entrega o cod_empresa como texto (1, 3, 5 ou 4).
    # Aqui convertemos esses números para os nomes exibidos no painel.
    mapa = cfg.get("mapa_fabricas") or {}
    if "fabrica" in df.columns:
        df["fabrica"] = df["fabrica"].astype(str).str.upper().str.strip()
    if mapa:
        df["fabrica"] = df["fabrica"].map(lambda v: mapa.get(v, v))

    # Fonte de fábrica única: o código do estabelecimento é irrelevante, tudo
    # vira o nome oficial. Resolve de uma vez os 57 códigos e também a
    # duplicidade de caixa no banco (k00 minúsculo x K00 maiúsculo).
    if cfg.get("fabrica_fixa"):
        df["fabrica"] = cfg["fabrica_fixa"]

    # --- Unidades que não entram por esta fonte ---
    for excluida in cfg.get("fabricas_excluidas", []):
        df = df[~df["fabrica"].str.contains(excluida.upper(), na=False)]

    # --- Quantidade ---
    # No Postgres a quantidade também é texto, então precisa ser convertida.
    # A regra é: só trata como padrão brasileiro ("1.234,50") quando existe
    # VÍRGULA no valor. Sem vírgula, o ponto é decimal e fica como está.
    # Sem essa distinção, "1250.5" viraria 12505 — erro de fator 10.
    fator = cfg.get("fator_sacos", 1)
    bruta = df.get("quantidade")
    if bruta is not None and not pd.api.types.is_numeric_dtype(bruta):
        bruta = bruta.astype(str).str.strip()
        formato_br = bruta.str.contains(",", na=False)
        if formato_br.any():
            bruta = bruta.mask(
                formato_br,
                bruta.str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
            )
    df["quantidade"] = pd.to_numeric(bruta, errors="coerce").fillna(0) * fator

    # --- Data ---
    # O formato é declarado por fonte. Sem ele, "02/01/26" seria lido como
    # 1 de fevereiro em vez de 2 de janeiro.
    formato = cfg.get("formato_data")
    if formato:
        df["data_hora"] = pd.to_datetime(df.get("data_hora"), format=formato, errors="coerce")
    else:
        df["data_hora"] = pd.to_datetime(df.get("data_hora"), errors="coerce")

    # Linha sem data válida não pertence a mês nenhum
    df = df.dropna(subset=["data_hora"])

    # Corte de data feito AQUI, com data de verdade — e não no SQL, onde a
    
    df = df[df["data_hora"] >= pd.Timestamp(DATA_INICIO)]

    if df.empty:
        saida = criar_dataframe_vazio()
        saida["_doc"] = pd.Series(dtype="object")
        saida["_fonte"] = pd.Series(dtype="object")
        return saida

    saida = pd.DataFrame({
        "Fábrica": df["fabrica"],
        "Data": df["data_hora"].dt.strftime("%d/%m/%Y"),
        "Cliente": df["cliente"],
        "Placa": df.get("placa", "").astype(str),
        "Quantidade (Sacos)": df["quantidade"].astype(float),
        "Item": df["item"],
        "Mês_Num": df["data_hora"].dt.month.astype(int),
        "Dia_Mes": df["data_hora"].dt.day.astype(int),
    })

    # Guardados só para o anti-duplicidade — não vão para a tela
    saida["_doc"] = df["documento"].astype(str) if "documento" in df.columns else ""
    saida["_fonte"] = nome_fonte
    # Indica linhas que tiveram ajuste de granel (True/False)
    saida["_granel_ajustado"] = df.get("_granel_ajustado", pd.Series(False, index=df.index))

    # Rede de proteção: se faltar coluna, o erro aparece AQUI e não três telas
    # depois na forma de um KPI errado.
    faltando = [c for c in COLUNAS_PAINEL if c not in saida.columns]
    if faltando:
        raise ValueError(f"A fonte '{nome_fonte}' não entregou as colunas: {faltando}")

    return saida


 # 5. CARGA POR FONTE — falha isolada

@st.cache_data(ttl=600, max_entries=5, show_spinner=False)
def carregar_fonte(nome_fonte):
    """Devolve (DataFrame, status). Uma fonte cair não derruba a outra."""
    cfg = FONTES[nome_fonte]
    try:
        from sqlalchemy import text
        engine = conectar_postgres()
        if engine is None:
            raise ConnectionError("Sem conexão com o Postgres")
        with engine.connect() as conn:
            bruto = pd.read_sql(text(cfg["query"]), conn,
                                params=cfg.get("params") or {})

        # Consulta vazia NÃO sobrescreve o backup bom
        if bruto.empty:
            raise RuntimeError("A consulta retornou zero linhas")

        df = normalizar(bruto, nome_fonte, cfg)
        # Contagem de ajustes de granel (interno criado em normalizar)
        granel_count = int(df.get("_granel_ajustado", pd.Series(False, index=df.index)).sum())
        # Remover a coluna interna antes de salvar/retornar
        if "_granel_ajustado" in df.columns:
            df = df.drop(columns=["_granel_ajustado"])
        salvar_backup(nome_fonte, df)
        return df, {"estado": "ok", "quando": datetime.now(), "linhas": len(df), "granel_ajustadas": granel_count}

    except Exception as e:
        notificar_admin(f"Falha na fonte '{nome_fonte}'. Usando backup local.", e)
        df, quando = ler_backup(nome_fonte)
        if not df.empty:
            df["_doc"] = ""
            df["_fonte"] = nome_fonte
        return df, {"estado": "backup" if not df.empty else "vazio",
                    "quando": quando, "linhas": len(df)}


@st.cache_data(ttl=600, max_entries=5,
               show_spinner="Consolidando notas fiscais das unidades...")
def carregar_dados_sistema():
    """Junta as fontes. Mesmas colunas de antes — o main.py não muda."""
    partes, status = [], {}
    # --- ADICIONE ESTA CHAVE NO TOPO DO ARQUIVO OU AQUI ---
MODO_TESTE = True

@st.cache_data(ttl=600, max_entries=5,
               show_spinner="Consolidando notas fiscais das unidades...")
def carregar_dados_sistema():
    """Junta as fontes ou gera dados fictícios para teste seguro."""
MODO_TESTE = True

@st.cache_data(ttl=600, max_entries=5,
               show_spinner="Consolidando notas fiscais das unidades...")
def carregar_dados_sistema():
    """Junta as fontes ou gera dados fictícios para teste seguro."""
    
    if MODO_TESTE:
        # Lê a base de expedição fictícia massiva da pasta dados_locais
        caminho_csv = PASTA_DADOS_LOCAIS / "dados_expedicao_ficticios.csv"
        df = pd.read_csv(caminho_csv, sep=";", encoding="utf-8-sig")
        return df

    # --- SE O MODO_TESTE FOR FALSE, RODA O SEU CÓDIGO ORIGINAL ---
    partes, status = [], {}
    # ... (o resto do teu código continua igual para baixo)
    # --- SE O MODO_TESTE FOR FALSE, RODA O SEU CÓDIGO ORIGINAL ---
    partes, status = [], {}

    for nome, cfg in FONTES.items():
        df, st_fonte = carregar_fonte(nome)
        status[nome] = st_fonte
        if not df.empty:
            partes.append(df)

    STATUS_FONTES.clear()
    STATUS_FONTES.update(status)

    if not partes:
        return criar_dataframe_vazio()

    df = pd.concat(partes, ignore_index=True)

    tem_doc = df["_doc"].astype(str).str.strip().ne("")
    if tem_doc.any():
        com = df[tem_doc].drop_duplicates(subset=["_fonte", "Fábrica", "_doc"], keep="last")
        df = pd.concat([com, df[~tem_doc]], ignore_index=True)

    return df[COLUNAS_PAINEL]
    for nome, cfg in FONTES.items():
        df, st_fonte = carregar_fonte(nome)
        status[nome] = st_fonte
        if not df.empty:
            partes.append(df)

    # Guarda num dicionário do módulo, não em st.session_state: escrita de
    # session_state dentro de função cacheada só acontece na primeira execução
    # e não vale para as outras sessões.
    STATUS_FONTES.clear()
    STATUS_FONTES.update(status)

    if not partes:
        return criar_dataframe_vazio()

    df = pd.concat(partes, ignore_index=True)

    # Anti-dupla-contagem: mesma nota, mesma fábrica, mesma fonte entra uma vez.
    # Só age onde existe número de nota — sem ele, não há como distinguir uma
    # duplicata de duas cargas legítimas iguais no mesmo dia.
    tem_doc = df["_doc"].astype(str).str.strip().ne("")
    if tem_doc.any():
        com = df[tem_doc].drop_duplicates(subset=["_fonte", "Fábrica", "_doc"], keep="last")
    
        df = pd.concat([com, df[~tem_doc]], ignore_index=True)

    return df[COLUNAS_PAINEL]


#  6. METAS
@st.cache_data(ttl=3600, max_entries=5, show_spinner="Carregando metas...")
def carregar_planilha_metas():
    """Extrai os volumes ideais (metas) e dias úteis do Metas.xlsx."""
    if not PLANILHA_METAS.exists():
        return {}, {}

    try:
        df_excel = pd.read_excel(PLANILHA_METAS, engine="openpyxl")

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
            df_fab = df_excel[df_excel["Unidade"] == fabrica].drop_duplicates(
                subset=["Mês"], keep="last"
            )
            metas_dinamicas[fabrica] = dict(zip(df_fab["Mês"], df_fab["Vendas"]))

        df_dias = df_excel.drop_duplicates(subset=["Mês"], keep="last")
        return metas_dinamicas, dict(zip(df_dias["Mês"], df_dias["Dias"]))

    except Exception as e:
        notificar_admin("Erro ao ler a planilha de Metas", e)
        return {}, {}


def listar_fabricas(df):
    """Fonte única da verdade para os menus — substitui as listas fixas."""
    if df.empty or "Fábrica" not in df.columns:
        return []
    return sorted(df["Fábrica"].dropna().astype(str).unique().tolist())