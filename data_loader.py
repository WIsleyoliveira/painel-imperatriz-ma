"""Leitura e parsing dos 4 arquivos-fonte. Nenhum indicador novo é calculado aqui
além de somas simples (para os cards de resumo) — QL, Δ% e totais por seção já
vêm prontos nas planilhas."""

import pandas as pd
import streamlit as st

DATA_DIR = "."

EMPRESAS_ATIVAS_FILE = f"{DATA_DIR}/Empresas_Ativas_Jul26_completo.xlsx"
EMPREGOS_FILE = f"{DATA_DIR}/Estoque_Empregos_RAIS_corrigido.xlsx"
ESTAB_FILE = f"{DATA_DIR}/Estoque_Empresas_RAIS_corrigido.xlsx"
QL_GRUPO_FILE = f"{DATA_DIR}/QL_por_Grupo_CNAE_com_nomes.xlsx"
EMPRESAS_GRUPO_13_FILE = f"{DATA_DIR}/Empresas_por_Grupo_CNAE_RAIS.xlsx"
RENDA_FILES = {
    "Seção": f"{DATA_DIR}/Renda_por_Secao_CNAE_RAIS.xlsx",
    "Divisão": f"{DATA_DIR}/Renda_por_Divisao_CNAE_RAIS.xlsx",
    "Grupo": f"{DATA_DIR}/Renda_por_Grupo_CNAE_RAIS.xlsx",
}

ANOS = [2000, 2005, 2010, 2015, 2020, 2025]
ANOS_13 = [2001, 2003, 2005, 2007, 2009, 2011, 2013, 2015, 2017, 2019, 2021, 2023, 2025]


def _parse_num(x):
    """'1.104' -> 1104 | '—' -> None | 12.12 -> 12.12"""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s in ("—", "", "nan", "NaN"):
        return None
    s = s.replace("%", "")
    if "." in s and "," not in s and s.count(".") > 0 and not _looks_decimal(s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _looks_decimal(s):
    # QL values like "12.12" or "0.46" — one dot, <=2 digits after it, and the
    # integer part has no thousand grouping (i.e. it's a plain small number).
    parts = s.split(".")
    if len(parts) != 2:
        return False
    intp, decp = parts
    return len(decp) <= 2 and len(intp) <= 3


def _parse_pct(x):
    """'313.0%' -> 313.0 | '-32.9%' -> -32.9 | '9230.0%' -> 9230.0 | '—' -> None
    Percent strings always use '.' as decimal point, never as thousand separator."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace("%", "")
    if s in ("—", "", "nan", "NaN"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


@st.cache_data
def load_empresas_ativas():
    """Retorna DataFrame longo: geo, tipo, secao, descricao, ano, porte, valor."""
    sheet_map = {
        ("Imperatriz", "Ativas"): "IMPERATRIZ — Ativas",
        ("Maranhão", "Ativas"): "MARANHÃO — Ativas",
        ("Brasil", "Ativas"): "BRASIL — Ativas",
        ("Imperatriz", "Todas"): "IMPERATRIZ — Todas criadas",
        ("Maranhão", "Todas"): "MARANHÃO — Todas criadas",
        ("Brasil", "Todas"): "BRASIL — Todas criadas",
    }
    xl = pd.ExcelFile(EMPRESAS_ATIVAS_FILE)
    rows = []
    for (geo, tipo), sheet in sheet_map.items():
        df = xl.parse(sheet, header=None)
        row_anos = df.iloc[2]
        row_porte = df.iloc[3]

        col_info = {}
        ano_atual = None
        for c in range(2, df.shape[1]):
            if pd.notna(row_anos[c]):
                ano_atual = int(row_anos[c])
            porte = row_porte[c]
            col_info[c] = (ano_atual, porte)

        for r in range(4, df.shape[0]):
            secao = df.iat[r, 0]
            descricao = df.iat[r, 1]
            if pd.isna(secao):
                continue
            for c, (ano, porte) in col_info.items():
                valor = _parse_num(df.iat[r, c])
                rows.append(
                    {
                        "geo": geo,
                        "tipo": tipo,
                        "secao": secao,
                        "descricao": descricao if pd.notna(descricao) else "TOTAL GERAL",
                        "ano": ano,
                        "porte": porte,
                        "valor": valor,
                    }
                )
    return pd.DataFrame(rows)


def _load_estoque_file(path, titulo_valor):
    """Para Estoque_Empregos_RAIS_corrigido.xlsx e Estoque_Empresas_RAIS_corrigido.xlsx.
    Retorna (long_df, delta_df) — long_df tem geo/secao/descricao/ano/valor,
    delta_df tem geo/secao/descricao/delta_pct (Δ% já calculado na planilha)."""
    xl = pd.ExcelFile(path)
    long_rows = []
    delta_rows = []
    for geo in xl.sheet_names:
        df = xl.parse(geo, header=None)
        for r in range(3, df.shape[0]):
            secao = df.iat[r, 0]
            descricao = df.iat[r, 1]
            if pd.isna(secao):
                continue
            is_total = secao == "TOTAL"
            descricao = "TOTAL GERAL" if is_total else descricao
            for i, ano in enumerate(ANOS):
                valor = _parse_num(df.iat[r, 2 + i])
                long_rows.append(
                    {
                        "geo": geo,
                        "secao": secao,
                        "descricao": descricao,
                        "ano": ano,
                        titulo_valor: valor,
                    }
                )
            delta = _parse_pct(df.iat[r, 8])
            delta_rows.append(
                {
                    "geo": geo,
                    "secao": secao,
                    "descricao": descricao,
                    "delta_pct": delta,
                    "is_total": is_total,
                }
            )
    return pd.DataFrame(long_rows), pd.DataFrame(delta_rows)


@st.cache_data
def load_empregos():
    return _load_estoque_file(EMPREGOS_FILE, "empregos")


@st.cache_data
def load_estabelecimentos():
    return _load_estoque_file(ESTAB_FILE, "estabelecimentos")


@st.cache_data
def load_ql_grupo():
    """Retorna dict {chave: DataFrame} para as 4 abas do arquivo de QL por grupo."""
    sheet_map = {
        "Empresas Ativas vs Maranhão": "ATIV_vs_MA",
        "Empresas Ativas vs Brasil": "ATIV_vs_BR",
        "Todas as Empresas Criadas vs Maranhão": "TODA_vs_MA",
        "Todas as Empresas Criadas vs Brasil": "TODA_vs_BR",
    }
    xl = pd.ExcelFile(QL_GRUPO_FILE)
    result = {}
    for label, sheet in sheet_map.items():
        df = xl.parse(sheet, header=None)
        header_row = 2
        cols = [
            "codigo",
            "nome",
            "ql_2000",
            "ql_2005",
            "ql_2010",
            "ql_2015",
            "ql_2020",
            "ql_2025",
            "ql_medio",
            "periodos_cresc",
        ]
        data = df.iloc[header_row + 1 :].reset_index(drop=True)
        data.columns = cols
        for c in cols[2:]:
            data[c] = data[c].apply(_parse_num)
        data = data.dropna(subset=["codigo"])
        result[label] = data
    return result


@st.cache_data
def load_empresas_grupo_13():
    """Empresas ativas por Grupo CNAE, série de 13 pontos (2001-2025, Receita
    Federal), já com QL Imperatriz vs Maranhão calculado na planilha."""
    df = pd.read_excel(EMPRESAS_GRUPO_13_FILE, header=3)
    out = pd.DataFrame()
    out["codigo"] = df["Grupo"].astype(int).astype(str).str.zfill(3)
    out["nome"] = df["Nome Grupo"]
    out["secao"] = df["Seção"]
    for a in ANOS_13:
        out[f"ql_{a}"] = df[f"QL {a}"]
        out[f"emp_{a}"] = df[f"Emp. {a}"]
    out["ql_medio"] = df["QL Médio"]
    out["representatividade"] = df["Representat. (%)"]
    out["cresc_5anos"] = df["Cresc. 5 anos (%)"]
    out["periodos_cresc"] = df["Consistência (0-12)"].apply(
        lambda s: int(str(s).split("/")[0]) if pd.notna(s) else None
    )
    return out


@st.cache_data
def load_renda(nivel):
    """Renda média por Seção/Divisão/Grupo CNAE (RAIS 2025) — Imperatriz vs
    Maranhão, com QL de renda já calculado na planilha."""
    df = pd.read_excel(RENDA_FILES[nivel], header=3)
    return df
