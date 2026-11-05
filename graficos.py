import altair as alt
import pandas as pd
import streamlit as st
from datetime import datetime

# PALETA E CONSTANTES

COR_MARCA = "#E96107"      
COR_REALIZADO = "#002CA7"  
COR_METAS = "#E08A1E"   
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



# UTILITÁRIOS

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
    """Registra o erro sem derrubar a tela."""
    try:
        from alertas import notificar_admin
        notificar_admin(titulo, erro)
    except Exception:
        pass
    st.info(mensagem)


# PREPARACAO DE DADOS (cacheada — e aqui que mora o ganho de desempenho)

# Sem @st.cache_data de propósito: o hash do DataFrame que o cache exige
# custa mais (~36 ms) do que o groupby desta função (~5 ms).
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


# Sem @st.cache_data de propósito: o hash do DataFrame que o cache exige
# custa mais (~36 ms) do que o groupby desta função (~5 ms).
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
         "Metas": list(metas_da_selecao.values())}
    )

    d = real.merge(meta, on="Mês_Num", how="outer").fillna(0)

    # Meses que ainda não chegaram não têm "Realizado": sem isso a linha azul
    # despencava para 0 em Nov/Dez. Vazio = a linha para no mês atual.
    d.loc[d["Mês_Num"] > mes_corrente, "Realizado"] = None

    # Valor zerado não vira ponto no gráfico (ex.: mês atual ainda sem notas):
    # sem isso aparecia um "0" no chão e a linha despencava até ele
    d[["Realizado", "Metas"]] = d[["Realizado", "Metas"]].mask(d[["Realizado", "Metas"]] == 0)

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
        value_vars=["Realizado", "Metas"],
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


#  GRAFICO 1 — REALIZADO x METAS

def plotar_realizado_previsto(df_banco, metas, unidades, altura=390,
                              chave="seletor_fabrica_grafico_topo"):

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

        escala_cor = alt.Scale(domain=["Realizado", "Metas"],
                               range=[COR_REALIZADO, COR_METAS])

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