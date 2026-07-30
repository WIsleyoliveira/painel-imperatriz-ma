import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import data_loader as dl

AZUL = "#1E2A5E"
VERDE = "#2E7D32"
VERMELHO = "#C62828"
LARANJA = "#EF6C00"

st.set_page_config(
    page_title="Painel de Oportunidades — Imperatriz (MA)",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    f"""
    <style>
    .stApp {{ }}
    h1, h2, h3 {{ color: {AZUL}; }}
    div[data-testid="stMetric"] {{
        background-color: rgba(30, 42, 94, 0.06);
        border-left: 4px solid {AZUL};
        border-radius: 6px;
        padding: 12px 16px;
    }}
    .badge {{
        display: inline-block;
        padding: 3px 12px;
        border-radius: 12px;
        color: white;
        font-weight: 600;
        font-size: 0.85em;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def fmt_int(v):
    if pd.isna(v):
        return "—"
    return f"{v:,.0f}".replace(",", ".")


def fmt_pct(v):
    if pd.isna(v):
        return "—"
    return f"{v:,.1f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def color_ql(val):
    if pd.isna(val):
        return ""
    if val > 1:
        return f"background-color: rgba(46,125,50,{min(0.15 + val / 20, 0.55)})"
    return f"background-color: rgba(198,40,40,{min(0.1 + (1 - val), 0.45)})"


def tabela_colorida(df, value_cols, fmt_func=None):
    """Colore e formata colunas numéricas (ex.: QL) como texto antes de montar o
    Styler — o st.dataframe às vezes ignora Styler.format() para células NaN e
    mostra o "None" do Python cru; convertendo para string primeiro isso não
    acontece, e a cor de fundo continua calculada a partir dos valores originais."""
    if fmt_func is None:
        fmt_func = lambda v: "—" if pd.isna(v) else f"{v:.2f}"
    numeric = df[value_cols]
    disp = df.copy()
    for c in value_cols:
        disp[c] = numeric[c].apply(fmt_func)

    def aplica_cores(_):
        styles = pd.DataFrame("", index=disp.index, columns=disp.columns)
        for c in value_cols:
            styles[c] = numeric[c].apply(color_ql)
        return styles

    return disp.style.apply(aplica_cores, axis=None)


ea = dl.load_empresas_ativas()
emp_long, emp_delta = dl.load_empregos()
est_long, est_delta = dl.load_estabelecimentos()
ql_dict = dl.load_ql_grupo()

st.sidebar.title("📊 Painel Imperatriz (MA)")
tela = st.sidebar.radio(
    "Navegação",
    [
        "Resumo Executivo",
        "QL por Grupo CNAE",
        "Empresas por Grupo (13 pontos)",
        "Renda por Grupo CNAE (2025)",
        "Maiores Altas e Baixas",
        "Empresas por Porte",
        "Comparativo Geográfico",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "**Fontes:** RAIS/MTE (vínculos e estabelecimentos, 2000-2025) · "
    "CNPJ Receita Federal via SERPRO (extração Jul/2026) · "
    "QL calculado previamente a partir desses microdados."
)

# ---------------------------------------------------------------------------
if tela == "Resumo Executivo":
    st.title("Resumo Executivo — Imperatriz (MA)")

    tot_emp_2025 = ea.query(
        "geo=='Imperatriz' and tipo=='Ativas' and secao=='TOTAL' and porte=='Total' and ano==2025"
    )["valor"].iloc[0]
    tot_emp_2000 = ea.query(
        "geo=='Imperatriz' and tipo=='Ativas' and secao=='TOTAL' and porte=='Total' and ano==2000"
    )["valor"].iloc[0]
    cresc_emp = (tot_emp_2025 - tot_emp_2000) / tot_emp_2000 * 100

    tot_vinc_2025 = emp_long.query("geo=='Imperatriz' and secao=='TOTAL' and ano==2025")[
        "empregos"
    ].iloc[0]
    tot_vinc_2000 = emp_long.query("geo=='Imperatriz' and secao=='TOTAL' and ano==2000")[
        "empregos"
    ].iloc[0]
    cresc_vinc = (tot_vinc_2025 - tot_vinc_2000) / tot_vinc_2000 * 100

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Empresas ativas (2025)", fmt_int(tot_emp_2025))
    c2.metric("Empregos formais (2025)", fmt_int(tot_vinc_2025))
    c3.metric("Crescimento de empresas 2000→2025", fmt_pct(cresc_emp))
    c4.metric("Crescimento de empregos 2000→2025", fmt_pct(cresc_vinc))

    st.markdown("### Evolução do número de empresas ativas — Imperatriz")
    serie = ea.query(
        "geo=='Imperatriz' and tipo=='Ativas' and secao=='TOTAL' and porte=='Total'"
    ).sort_values("ano")
    fig = px.line(
        serie, x="ano", y="valor", markers=True, labels={"ano": "Ano", "valor": "Empresas ativas"}
    )
    fig.update_traces(line_color=AZUL, line_width=3, marker_size=9)
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Evolução dos empregos formais — Imperatriz")
    serie_e = emp_long.query("geo=='Imperatriz' and secao=='TOTAL'").sort_values("ano")
    fig2 = px.line(
        serie_e, x="ano", y="empregos", markers=True, labels={"ano": "Ano", "empregos": "Empregos formais"}
    )
    fig2.update_traces(line_color=VERDE, line_width=3, marker_size=9)
    fig2.update_layout(height=420)
    st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
elif tela == "QL por Grupo CNAE":
    st.title("Quociente Locacional — Por Grupo CNAE")
    st.caption(
        "QL > 1: grupo proporcionalmente mais concentrado em Imperatriz do que na referência. "
        "QL < 1: sub-representado. '—' indica que o grupo não existia em Imperatriz ou a "
        "base de comparação era zero naquele ano."
    )

    opcao = st.selectbox("Comparação", list(ql_dict.keys()))
    df = ql_dict[opcao].copy()

    busca = st.text_input("🔎 Buscar grupo por nome ou código")
    if busca:
        mask = df["nome"].str.contains(busca, case=False, na=False) | df["codigo"].astype(
            str
        ).str.contains(busca, case=False, na=False)
        df = df[mask]

    df = df.sort_values("ql_medio", ascending=False).reset_index(drop=True)

    st.markdown(f"**{len(df)} grupos encontrados** — ordenados por QL médio")

    PAGE_SIZE = 20
    total_paginas = max(1, -(-len(df) // PAGE_SIZE))
    pagina = st.number_input(
        "Página", min_value=1, max_value=total_paginas, value=1, step=1
    )
    ini = (pagina - 1) * PAGE_SIZE
    fim = ini + PAGE_SIZE
    pagina_df = df.iloc[ini:fim]

    ano_cols = [f"ql_{a}" for a in dl.ANOS]
    display_df = pagina_df[["codigo", "nome"] + ano_cols + ["ql_medio", "periodos_cresc"]].copy()
    display_df.columns = ["Código", "Grupo"] + [str(a) for a in dl.ANOS] + [
        "QL Médio",
        "Períodos Cresc.",
    ]
    styled = tabela_colorida(display_df, [str(a) for a in dl.ANOS] + ["QL Médio"])
    st.dataframe(styled, use_container_width=True, height=650)

    st.markdown(f"Página {pagina} de {total_paginas}")

    st.markdown("---")
    st.markdown("### Ver detalhe de um grupo")
    opcoes_detalhe = pagina_df.apply(lambda r: f"{r['codigo']} — {r['nome']}", axis=1).tolist()
    if opcoes_detalhe:
        escolha = st.selectbox("Selecione um grupo da página atual", opcoes_detalhe)
        codigo_sel = escolha.split(" — ")[0]
        row = df[df["codigo"].astype(str) == codigo_sel].iloc[0]

        with st.container(border=True):
            st.subheader(f"{row['codigo']} — {row['nome']}")

            periodos = row["periodos_cresc"]
            if pd.isna(periodos):
                cor_selo, texto_periodos = "#9E9E9E", "sem dados suficientes"
            elif periodos >= 4:
                cor_selo, texto_periodos = VERDE, f"cresceu em {int(periodos)} dos 5 períodos analisados"
            elif periodos >= 2:
                cor_selo, texto_periodos = LARANJA, f"cresceu em {int(periodos)} dos 5 períodos analisados"
            else:
                cor_selo, texto_periodos = VERMELHO, f"cresceu em {int(periodos)} dos 5 períodos analisados"
            st.markdown(
                f'<span class="badge" style="background-color:{cor_selo}">{texto_periodos}</span>',
                unsafe_allow_html=True,
            )

            valores = [row[f"ql_{a}"] for a in dl.ANOS]
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=dl.ANOS,
                    y=valores,
                    mode="lines+markers",
                    line=dict(color=AZUL, width=3),
                    marker=dict(size=9),
                    connectgaps=True,
                )
            )
            fig.add_hline(y=1, line_dash="dash", line_color="gray")
            fig.update_layout(
                title="QL ao longo do tempo",
                xaxis_title="Ano",
                yaxis_title="QL",
                height=380,
            )
            st.plotly_chart(fig, use_container_width=True)

            faltantes = [a for a, v in zip(dl.ANOS, valores) if pd.isna(v)]
            if faltantes:
                anos_str = ", ".join(str(a) for a in faltantes)
                st.info(
                    f"Dado indisponível em {anos_str} — grupo não existia em Imperatriz "
                    "ou na base de comparação neste(s) ano(s)."
                )

# ---------------------------------------------------------------------------
elif tela == "Empresas por Grupo (13 pontos)":
    st.title("Empresas Ativas por Grupo CNAE — Série 2001-2025")
    st.caption(
        "Estoque de empresas matriz ativas (Receita Federal), reconstruído por data de "
        "abertura, série completa de 13 pontos (2001 a 2025). QL Imperatriz vs Maranhão."
    )

    df13 = dl.load_empresas_grupo_13()

    busca13 = st.text_input("🔎 Buscar grupo por nome ou código", key="busca_emp13")
    dfv = df13.copy()
    if busca13:
        mask = dfv["nome"].str.contains(busca13, case=False, na=False) | dfv["codigo"].str.contains(
            busca13, case=False, na=False
        )
        dfv = dfv[mask]

    dfv = dfv.sort_values("ql_medio", ascending=False).reset_index(drop=True)
    st.markdown(f"**{len(dfv)} grupos encontrados** — ordenados por QL médio")

    PAGE_SIZE13 = 20
    total_pag13 = max(1, -(-len(dfv) // PAGE_SIZE13))
    pag13 = st.number_input("Página", min_value=1, max_value=total_pag13, value=1, step=1, key="pag_emp13")
    ini13 = (pag13 - 1) * PAGE_SIZE13
    pagina_df13 = dfv.iloc[ini13 : ini13 + PAGE_SIZE13]

    ql_cols13 = [f"ql_{a}" for a in dl.ANOS_13]
    disp13 = pagina_df13[["codigo", "nome"] + ql_cols13 + ["ql_medio"]].copy()
    disp13.columns = ["Código", "Grupo"] + [str(a) for a in dl.ANOS_13] + ["QL Médio"]
    styled13 = tabela_colorida(disp13, [str(a) for a in dl.ANOS_13] + ["QL Médio"])
    st.dataframe(styled13, use_container_width=True, height=650)
    st.markdown(f"Página {pag13} de {total_pag13}")

    st.markdown("---")
    st.markdown("### Ver detalhe de um grupo")
    opcoes13 = pagina_df13.apply(lambda r: f"{r['codigo']} — {r['nome']}", axis=1).tolist()
    if opcoes13:
        escolha13 = st.selectbox("Selecione um grupo da página atual", opcoes13, key="sel_emp13")
        cod13 = escolha13.split(" — ")[0]
        row13 = dfv[dfv["codigo"] == cod13].iloc[0]

        with st.container(border=True):
            st.subheader(f"{row13['codigo']} — {row13['nome']}")
            valores13 = [row13[f"ql_{a}"] for a in dl.ANOS_13]
            fig13 = go.Figure()
            fig13.add_trace(
                go.Scatter(
                    x=dl.ANOS_13,
                    y=valores13,
                    mode="lines+markers",
                    line=dict(color=AZUL, width=3),
                    marker=dict(size=9),
                    connectgaps=True,
                )
            )
            fig13.add_hline(y=1, line_dash="dash", line_color="gray")
            fig13.update_layout(title="QL ao longo do tempo (empresas)", xaxis_title="Ano", yaxis_title="QL", height=380)
            st.plotly_chart(fig13, use_container_width=True)

            c1, c2 = st.columns(2)
            c1.metric("Representatividade (2025)", fmt_pct(row13["representatividade"]))
            c2.metric("Crescimento 2019→2025", fmt_pct(row13["cresc_5anos"]))

# ---------------------------------------------------------------------------
elif tela == "Renda por Grupo CNAE (2025)":
    st.title("Renda Média por Grupo CNAE — RAIS 2025")
    st.caption(
        "Remuneração média nominal do ano (Vl Rem Média Nom), vínculos ativos em 31/12 "
        "com renda > 0. QL Renda = renda média do grupo em Imperatriz ÷ renda média do "
        "grupo no Maranhão (>1 = paga acima da média estadual do setor)."
    )

    st.markdown("### Por Seção CNAE")
    df_renda_secao = dl.load_renda("Seção").sort_values("QL Renda (Imp/MA)", ascending=False)
    fig_r = px.bar(
        df_renda_secao,
        x="Seção",
        y=["Renda Média Imperatriz (R$)", "Renda Média Maranhão (R$)"],
        barmode="group",
        color_discrete_map={
            "Renda Média Imperatriz (R$)": AZUL,
            "Renda Média Maranhão (R$)": VERDE,
        },
        labels={"value": "Renda média (R$)", "variable": ""},
        hover_data=["Nome Seção"],
    )
    fig_r.update_layout(height=440)
    st.plotly_chart(fig_r, use_container_width=True)

    st.markdown("### Detalhamento por Grupo CNAE")
    nivel_renda = st.radio("Nível", ["Grupo", "Divisão", "Seção"], horizontal=True, key="nivel_renda")
    df_renda = dl.load_renda(nivel_renda)

    busca_renda = st.text_input("🔎 Buscar por nome ou código", key="busca_renda")
    if busca_renda:
        nome_col = f"Nome {nivel_renda}"
        cod_col = nivel_renda
        mask = df_renda[nome_col].str.contains(busca_renda, case=False, na=False) | df_renda[
            cod_col
        ].astype(str).str.contains(busca_renda, case=False, na=False)
        df_renda = df_renda[mask]

    df_renda = df_renda.sort_values("QL Renda (Imp/MA)", ascending=False)

    def fmt_reais(v):
        if pd.isna(v):
            return "—"
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    disp_renda = df_renda.copy()
    disp_renda["Vínculos Imperatriz"] = disp_renda["Vínculos Imperatriz"].apply(fmt_int)
    disp_renda["Vínculos Maranhão"] = disp_renda["Vínculos Maranhão"].apply(fmt_int)
    disp_renda["Renda Média Imperatriz (R$)"] = df_renda["Renda Média Imperatriz (R$)"].apply(fmt_reais)
    disp_renda["Renda Média Maranhão (R$)"] = df_renda["Renda Média Maranhão (R$)"].apply(fmt_reais)

    numeric_ql = df_renda["QL Renda (Imp/MA)"]
    disp_renda["QL Renda (Imp/MA)"] = numeric_ql.apply(lambda v: "—" if pd.isna(v) else f"{v:.2f}")

    def aplica_cor_renda(_):
        styles = pd.DataFrame("", index=disp_renda.index, columns=disp_renda.columns)
        styles["QL Renda (Imp/MA)"] = numeric_ql.apply(color_ql)
        return styles

    styled_renda = disp_renda.style.apply(aplica_cor_renda, axis=None)
    st.dataframe(styled_renda, use_container_width=True, height=500)

# ---------------------------------------------------------------------------
elif tela == "Maiores Altas e Baixas":
    st.title("Maiores Altas e Maiores Baixas — Imperatriz")
    st.caption(
        "Baseado no Δ% 2000→2025 já calculado nas planilhas de estoque de "
        "empresas e empregos por seção CNAE (não recalculado)."
    )

    metrica = st.radio("Indicador", ["Empresas (estabelecimentos)", "Empregos formais"], horizontal=True)
    fonte = est_delta if metrica.startswith("Empresas") else emp_delta

    df = fonte.query("geo=='Imperatriz' and is_total==False").dropna(subset=["delta_pct"])

    altas = df.sort_values("delta_pct", ascending=False).head(10)
    baixas = df.sort_values("delta_pct", ascending=True).head(10)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 📈 Top 10 maiores altas")
        fig = px.bar(
            altas.sort_values("delta_pct"),
            x="delta_pct",
            y="descricao",
            orientation="h",
            labels={"delta_pct": "Δ% 2000→2025", "descricao": ""},
        )
        fig.update_traces(marker_color=VERDE)
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### 📉 Top 10 maiores baixas")
        fig2 = px.bar(
            baixas.sort_values("delta_pct", ascending=False),
            x="delta_pct",
            y="descricao",
            orientation="h",
            labels={"delta_pct": "Δ% 2000→2025", "descricao": ""},
        )
        fig2.update_traces(marker_color=VERMELHO)
        fig2.update_layout(height=450)
        st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
elif tela == "Empresas por Porte":
    st.title("Empresas por Porte — Imperatriz (2025)")

    base = ea.query(
        "geo=='Imperatriz' and tipo=='Ativas' and ano==2025 and porte!='Total'"
    )
    total_geral = base.query("secao=='TOTAL'").groupby("porte")["valor"].sum().reset_index()

    col1, col2 = st.columns([1, 1.4])
    with col1:
        fig = px.pie(
            total_geral,
            names="porte",
            values="valor",
            color="porte",
            color_discrete_map={"Grande/Médio": AZUL, "ME/EPP": VERDE, "MEI": LARANJA},
            hole=0.4,
        )
        fig.update_traces(textinfo="percent+label")
        fig.update_layout(height=420, title="Distribuição por porte")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        por_secao = base.query("secao!='TOTAL'").pivot_table(
            index=["secao", "descricao"], columns="porte", values="valor", aggfunc="sum"
        ).reset_index()
        por_secao = por_secao.sort_values("secao")
        st.markdown("#### Detalhamento por seção CNAE")
        st.dataframe(por_secao, use_container_width=True, height=420)

# ---------------------------------------------------------------------------
elif tela == "Comparativo Geográfico":
    st.title("Comparativo Imperatriz × Maranhão × Brasil")

    st.markdown("### Empresas")
    tipo = st.radio("Base", ["Ativas", "Todas"], horizontal=True, key="tipo_geo")
    comp = ea.query(
        "tipo==@tipo and secao=='TOTAL' and porte=='Total'"
    ).sort_values(["geo", "ano"])
    fig = px.bar(
        comp,
        x="ano",
        y="valor",
        color="geo",
        barmode="group",
        color_discrete_map={"Imperatriz": AZUL, "Maranhão": VERDE, "Brasil": LARANJA},
        labels={"ano": "Ano", "valor": "Nº de empresas", "geo": "Região"},
    )
    fig.update_layout(height=450)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"Base: {'apenas empresas ativas em Jul/2026' if tipo=='Ativas' else 'todas as empresas já criadas, incluindo encerradas'}."
    )

    st.markdown("---")
    st.markdown("### Empregos formais — Imperatriz × Maranhão")
    st.info("Sem aba Brasil nesta planilha de origem — comparação disponível apenas entre Imperatriz e Maranhão.")
    comp_emp = emp_long.query("secao=='TOTAL'").sort_values(["geo", "ano"])
    fig2 = px.bar(
        comp_emp,
        x="ano",
        y="empregos",
        color="geo",
        barmode="group",
        color_discrete_map={"Imperatriz": AZUL, "Maranhão": VERDE},
        labels={"ano": "Ano", "empregos": "Empregos formais", "geo": "Região"},
    )
    fig2.update_layout(height=420)
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### Estabelecimentos com empregados — Imperatriz × Maranhão")
    comp_est = est_long.query("secao=='TOTAL'").sort_values(["geo", "ano"])
    fig3 = px.bar(
        comp_est,
        x="ano",
        y="estabelecimentos",
        color="geo",
        barmode="group",
        color_discrete_map={"Imperatriz": AZUL, "Maranhão": VERDE},
        labels={"ano": "Ano", "estabelecimentos": "Estabelecimentos", "geo": "Região"},
    )
    fig3.update_layout(height=420)
    st.plotly_chart(fig3, use_container_width=True)
