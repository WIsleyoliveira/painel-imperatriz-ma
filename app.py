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
    page_title="Painel de Oportunidades — Imperatriz, Ananindeua e Capanema",
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
    """Recebe o texto já formatado ('—' ou '12.34') — st.dataframe não aplica
    Styler.format() de forma confiável, então cor e texto são resolvidos juntos
    a partir da mesma string."""
    if val == "—":
        return ""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v > 1:
        return f"background-color: rgba(46,125,50,{min(0.15 + v / 20, 0.55)})"
    return f"background-color: rgba(198,40,40,{min(0.1 + (1 - v), 0.45)})"


def fmt_ql_cell(v):
    return "—" if pd.isna(v) else f"{v:.2f}"


st.sidebar.title("📊 Painel de Oportunidades")
cidade_key = st.sidebar.selectbox("Cidade", list(dl.CITIES.keys()))
cfg = dl.CITIES[cidade_key]
CIDADE = cfg["city_name"]
REF = cfg["ref_geo"]

ea = dl.load_empresas_ativas(cidade_key)
emp_long, emp_delta = dl.load_empregos(cidade_key)
est_long, est_delta = dl.load_estabelecimentos(cidade_key)
ql_dict = dl.load_ql_grupo(cidade_key)

emp_long = emp_long[emp_long["geo"].isin([CIDADE, REF])]
emp_delta = emp_delta[emp_delta["geo"].isin([CIDADE, REF])]

st.sidebar.markdown("---")
st.sidebar.caption("Navegação")
tela = st.sidebar.radio(
    "Navegação",
    [
        "Resumo Executivo",
        "QL por Grupo CNAE",
        "Maiores Altas e Baixas",
        "Empresas por Porte",
        "Comparativo Geográfico",
    ],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
anos_empregos = sorted(emp_long["ano"].unique())
st.sidebar.caption(
    f"**Fontes:** RAIS/MTE — vínculos ({anos_empregos[0]}-{anos_empregos[-1]}) · "
    f"{cfg['fonte_estab']} · "
    "QL calculado localmente a partir desses microdados."
)

# ---------------------------------------------------------------------------
if tela == "Resumo Executivo":
    st.title(f"Resumo Executivo — {cidade_key}")

    ano_ini_emp, ano_fim_emp = min(dl.CNPJ_ANOS), max(dl.CNPJ_ANOS)
    tot_emp_fim = ea.query(
        "geo==@CIDADE and tipo=='Ativas' and secao=='TOTAL' and porte=='Total' and ano==@ano_fim_emp"
    )["valor"].iloc[0]
    tot_emp_ini = ea.query(
        "geo==@CIDADE and tipo=='Ativas' and secao=='TOTAL' and porte=='Total' and ano==@ano_ini_emp"
    )["valor"].iloc[0]
    cresc_emp = (tot_emp_fim - tot_emp_ini) / tot_emp_ini * 100 if tot_emp_ini else None

    ano_ini_v, ano_fim_v = anos_empregos[0], anos_empregos[-1]
    tot_vinc_fim = emp_long.query("geo==@CIDADE and secao=='TOTAL' and ano==@ano_fim_v")["empregos"].iloc[0]
    tot_vinc_ini = emp_long.query("geo==@CIDADE and secao=='TOTAL' and ano==@ano_ini_v")["empregos"].iloc[0]
    cresc_vinc = (tot_vinc_fim - tot_vinc_ini) / tot_vinc_ini * 100 if tot_vinc_ini else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Empresas ativas ({ano_fim_emp})", fmt_int(tot_emp_fim))
    c2.metric(f"Empregos formais ({ano_fim_v})", fmt_int(tot_vinc_fim))
    c3.metric(f"Crescimento de empresas {ano_ini_emp}→{ano_fim_emp}", fmt_pct(cresc_emp))
    c4.metric(f"Crescimento de empregos {ano_ini_v}→{ano_fim_v}", fmt_pct(cresc_vinc))

    st.markdown(f"### Evolução do número de empresas ativas — {CIDADE}")
    serie = ea.query(
        "geo==@CIDADE and tipo=='Ativas' and secao=='TOTAL' and porte=='Total'"
    ).sort_values("ano")
    fig = px.line(
        serie, x="ano", y="valor", markers=True, labels={"ano": "Ano", "valor": "Empresas ativas"}
    )
    fig.update_traces(line_color=AZUL, line_width=3, marker_size=9)
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"### Evolução dos empregos formais — {CIDADE}")
    serie_e = emp_long.query("geo==@CIDADE and secao=='TOTAL'").sort_values("ano")
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
        f"QL > 1: grupo proporcionalmente mais concentrado em {CIDADE} do que na referência. "
        f"QL < 1: sub-representado. '—' indica que o grupo não existia em {CIDADE} ou a "
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

    ano_cols = [f"ql_{a}" for a in dl.CNPJ_ANOS]
    ql_col_labels = [str(a) for a in dl.CNPJ_ANOS] + ["QL Médio"]
    display_df = pagina_df[["codigo", "nome"] + ano_cols + ["ql_medio", "periodos_cresc"]].copy()
    display_df.columns = ["Código", "Grupo"] + ql_col_labels + ["Períodos Cresc."]
    for c in ql_col_labels:
        display_df[c] = display_df[c].apply(fmt_ql_cell)
    styled = display_df.style.map(color_ql, subset=ql_col_labels)
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

            valores = [row[f"ql_{a}"] for a in dl.CNPJ_ANOS]
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=dl.CNPJ_ANOS,
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

            faltantes = [a for a, v in zip(dl.CNPJ_ANOS, valores) if pd.isna(v)]
            if faltantes:
                anos_str = ", ".join(str(a) for a in faltantes)
                st.info(
                    f"Dado indisponível em {anos_str} — grupo não existia em {CIDADE} "
                    "ou na base de comparação neste(s) ano(s)."
                )

# ---------------------------------------------------------------------------
elif tela == "Maiores Altas e Baixas":
    st.title(f"Maiores Altas e Maiores Baixas — {CIDADE}")
    st.caption(
        "Baseado no Δ% já calculado nas planilhas de estoque de "
        "empresas e empregos por seção CNAE (não recalculado)."
    )

    metrica = st.radio("Indicador", ["Empresas (estabelecimentos)", "Empregos formais"], horizontal=True)
    fonte = est_delta if metrica.startswith("Empresas") else emp_delta

    df = fonte.query("geo==@CIDADE and is_total==False").dropna(subset=["delta_pct"])

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
            labels={"delta_pct": "Δ%", "descricao": ""},
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
            labels={"delta_pct": "Δ%", "descricao": ""},
        )
        fig2.update_traces(marker_color=VERMELHO)
        fig2.update_layout(height=450)
        st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
elif tela == "Empresas por Porte":
    ano_ref = max(dl.CNPJ_ANOS)
    st.title(f"Empresas por Porte — {CIDADE} ({ano_ref})")
    if len(cfg["portes"]) == 2:
        st.caption(
            "Esta base não distingue ME/EPP de Grande/Médio (arquivo EMPRESAS da Receita não "
            "disponível) — porte limitado a MEI vs Demais."
        )

    base = ea.query("geo==@CIDADE and tipo=='Ativas' and ano==@ano_ref and porte!='Total'")
    total_geral = base.query("secao=='TOTAL'").groupby("porte")["valor"].sum().reset_index()

    col1, col2 = st.columns([1, 1.4])
    with col1:
        fig = px.pie(
            total_geral,
            names="porte",
            values="valor",
            color="porte",
            color_discrete_map=cfg["porte_colors"],
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
    st.title(f"Comparativo {CIDADE} × {REF} × Brasil")

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
        color_discrete_map={CIDADE: AZUL, REF: VERDE, "Brasil": LARANJA},
        labels={"ano": "Ano", "valor": "Nº de empresas", "geo": "Região"},
    )
    fig.update_layout(height=450)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"Base: {'apenas empresas ativas em Jul/2026' if tipo=='Ativas' else 'todas as empresas já criadas, incluindo encerradas'}."
    )

    st.markdown("---")
    st.markdown(f"### Empregos formais — {CIDADE} × {REF}")
    st.info(f"Sem dado de Brasil nesta série — comparação disponível apenas entre {CIDADE} e {REF}.")
    comp_emp = emp_long.query("secao=='TOTAL'").sort_values(["geo", "ano"])
    fig2 = px.bar(
        comp_emp,
        x="ano",
        y="empregos",
        color="geo",
        barmode="group",
        color_discrete_map={CIDADE: AZUL, REF: VERDE},
        labels={"ano": "Ano", "empregos": "Empregos formais", "geo": "Região"},
    )
    fig2.update_layout(height=420)
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown(f"### Estabelecimentos — {CIDADE} × {REF}")
    comp_est = est_long.query("secao=='TOTAL' and geo in [@CIDADE, @REF]").sort_values(["geo", "ano"])
    fig3 = px.bar(
        comp_est,
        x="ano",
        y="estabelecimentos",
        color="geo",
        barmode="group",
        color_discrete_map={CIDADE: AZUL, REF: VERDE},
        labels={"ano": "Ano", "estabelecimentos": "Estabelecimentos", "geo": "Região"},
    )
    fig3.update_layout(height=420)
    st.plotly_chart(fig3, use_container_width=True)
