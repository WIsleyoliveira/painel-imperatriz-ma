"""Leitura e parsing dos arquivos-fonte de cada cidade. Nenhum indicador novo
é calculado aqui além de somas simples (para os cards de resumo) — QL, Δ% e
totais por seção já vêm prontos nas planilhas.

Duas cidades (Ananindeua, Capanema) usam uma metodologia um pouco diferente
de Imperatriz porque a fonte de dados é outra (CNPJ Receita Federal bruto +
RAIS Vínculos bruto, processados localmente, em vez de planilhas já prontas):
- Porte: só MEI vs Demais (não há ME/EPP vs Grande/Médio, arquivo EMPRESAS
  da Receita com essa info não foi baixado).
- RAIS Vínculos: série 2001-2025 (13 pontos) em vez de 2000-2025 (6 pontos),
  e "estabelecimentos" vem do CNPJ (não do RAIS ESTAB, que não foi baixado).
"""

import re

import pandas as pd
import streamlit as st

DATA_DIR = "."

CNPJ_ANOS = [2000, 2005, 2010, 2015, 2020, 2025]

CITIES = {
    "Imperatriz (MA)": {
        "city_name": "Imperatriz",
        "ref_geo": "Maranhão",
        "ref_abbr": "MA",
        "empresas_ativas_file": f"{DATA_DIR}/Empresas_Ativas_Jul26_completo.xlsx",
        "empregos_file": f"{DATA_DIR}/Estoque_Empregos_RAIS_corrigido.xlsx",
        "estab_file": f"{DATA_DIR}/Estoque_Empresas_RAIS_corrigido.xlsx",
        "ql_file": f"{DATA_DIR}/QL_por_Grupo_CNAE_com_nomes.xlsx",
        "portes": ["Grande/Médio", "ME/EPP", "MEI"],
        "porte_colors": {"Grande/Médio": "#1E2A5E", "ME/EPP": "#2E7D32", "MEI": "#EF6C00"},
        "tem_brasil_empregos": False,
        "fonte_estab": "RAIS ESTAB/MTE — estabelecimentos com pelo menos 1 empregado formal.",
    },
    "Ananindeua (PA)": {
        "city_name": "Ananindeua",
        "ref_geo": "Pará",
        "ref_abbr": "PA",
        "empresas_ativas_file": f"{DATA_DIR}/Empresas_Ativas_Ananindeua_completo.xlsx",
        "empregos_file": f"{DATA_DIR}/Estoque_Empregos_RAIS_Ananindeua_Capanema.xlsx",
        "estab_file": f"{DATA_DIR}/Estoque_Empresas_Ananindeua_Capanema.xlsx",
        "ql_file": f"{DATA_DIR}/QL_por_Grupo_CNAE_Ananindeua.xlsx",
        "empregos_sheet": "Ananindeua",
        "portes": ["MEI", "Demais"],
        "porte_colors": {"MEI": "#EF6C00", "Demais": "#1E2A5E"},
        "tem_brasil_empregos": False,
        "fonte_estab": "CNPJ Receita Federal — todo CNPJ ativo (RAIS ESTAB não disponível nesta série; "
        "conceito diferente: inclui empresas sem empregados, ex. MEI).",
    },
    "Capanema (PA)": {
        "city_name": "Capanema",
        "ref_geo": "Pará",
        "ref_abbr": "PA",
        "empresas_ativas_file": f"{DATA_DIR}/Empresas_Ativas_Capanema_completo.xlsx",
        "empregos_file": f"{DATA_DIR}/Estoque_Empregos_RAIS_Ananindeua_Capanema.xlsx",
        "estab_file": f"{DATA_DIR}/Estoque_Empresas_Ananindeua_Capanema.xlsx",
        "ql_file": f"{DATA_DIR}/QL_por_Grupo_CNAE_Capanema.xlsx",
        "empregos_sheet": "Capanema",
        "portes": ["MEI", "Demais"],
        "porte_colors": {"MEI": "#EF6C00", "Demais": "#1E2A5E"},
        "tem_brasil_empregos": False,
        "fonte_estab": "CNPJ Receita Federal — todo CNPJ ativo (RAIS ESTAB não disponível nesta série; "
        "conceito diferente: inclui empresas sem empregados, ex. MEI).",
    },
}

# Arquivos "por Seção/Divisão/Grupo" (série 2001-2025, matriz, QL vs estado
# só) — só existem para Ananindeua e Capanema, não para Imperatriz.
NIVEIS_ANOS = [2001, 2003, 2005, 2007, 2009, 2011, 2013, 2015, 2017, 2019, 2021, 2023, 2025]

NIVEIS_FILES = {
    "Ananindeua (PA)": {
        "Empregos": {
            "Seção": f"{DATA_DIR}/Empregos_por_Secao_CNAE_RAIS_Ananindeua.xlsx",
            "Divisão": f"{DATA_DIR}/Empregos_por_Divisao_CNAE_RAIS_Ananindeua.xlsx",
            "Grupo": f"{DATA_DIR}/Empregos_por_Grupo_CNAE_RAIS_Ananindeua.xlsx",
        },
        "Empresas": {
            "Seção": f"{DATA_DIR}/Empresas_por_Secao_CNAE_RAIS_Ananindeua.xlsx",
            "Divisão": f"{DATA_DIR}/Empresas_por_Divisao_CNAE_RAIS_Ananindeua.xlsx",
            "Grupo": f"{DATA_DIR}/Empresas_por_Grupo_CNAE_RAIS_Ananindeua.xlsx",
        },
    },
    "Capanema (PA)": {
        "Empregos": {
            "Seção": f"{DATA_DIR}/Empregos_por_Secao_CNAE_RAIS_Capanema.xlsx",
            "Divisão": f"{DATA_DIR}/Empregos_por_Divisao_CNAE_RAIS_Capanema.xlsx",
            "Grupo": f"{DATA_DIR}/Empregos_por_Grupo_CNAE_RAIS_Capanema.xlsx",
        },
        "Empresas": {
            "Seção": f"{DATA_DIR}/Empresas_por_Secao_CNAE_RAIS_Capanema.xlsx",
            "Divisão": f"{DATA_DIR}/Empresas_por_Divisao_CNAE_RAIS_Capanema.xlsx",
            "Grupo": f"{DATA_DIR}/Empresas_por_Grupo_CNAE_RAIS_Capanema.xlsx",
        },
    },
}

_NIVEL_ID_COLS = {
    "Seção": ["secao", "nome_secao"],
    "Divisão": ["secao", "nome_secao", "divisao", "nome_divisao"],
    "Grupo": ["secao", "nome_secao", "divisao", "nome_divisao", "grupo", "nome_grupo"],
}


@st.cache_data
def load_nivel(city_key, fonte, nivel):
    """fonte: 'Empregos' | 'Empresas'. nivel: 'Seção' | 'Divisão' | 'Grupo'.
    Retorna DataFrame com colunas de identificação + valor_<ano> + ql_<ano> +
    ql_medio, representat, cresc5, consistencia."""
    path = NIVEIS_FILES[city_key][fonte][nivel]
    sheet = fonte
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    id_cols = _NIVEL_ID_COLS[nivel]
    cols = id_cols + [f"valor_{a}" for a in NIVEIS_ANOS] + [f"ql_{a}" for a in NIVEIS_ANOS] + [
        "ql_medio", "representat", "cresc5", "consistencia"
    ]
    data = df.iloc[4:].reset_index(drop=True)
    data.columns = cols
    for c in [f"valor_{a}" for a in NIVEIS_ANOS] + [f"ql_{a}" for a in NIVEIS_ANOS] + ["ql_medio", "representat", "cresc5"]:
        data[c] = data[c].apply(_parse_num)
    data = data.dropna(subset=[id_cols[0]])
    return data


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
    parts = s.split(".")
    if len(parts) != 2:
        return False
    intp, decp = parts
    return len(decp) <= 2 and len(intp) <= 3


def _parse_pct(x):
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
def load_empresas_ativas(city_key):
    """Retorna DataFrame longo: geo, tipo, secao, descricao, ano, porte, valor."""
    cfg = CITIES[city_key]
    geo_name_map = {
        cfg["city_name"].upper(): cfg["city_name"],
        cfg["ref_geo"].upper(): cfg["ref_geo"],
        "BRASIL": "Brasil",
    }
    xl = pd.ExcelFile(cfg["empresas_ativas_file"])
    rows = []
    for sheet in xl.sheet_names:
        raw_geo, _, raw_tipo = sheet.partition("—")
        geo = geo_name_map.get(raw_geo.strip(), raw_geo.strip())
        tipo = "Ativas" if "Ativas" in raw_tipo else "Todas"

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


def _detect_year_cols(header_row2):
    """Lê a linha de cabeçalho (ex: 'Empregos\\n2001') e devolve {col_idx: ano}.
    Ignora a coluna de Δ% (que também menciona anos, ex: '2000→2025')."""
    year_cols = {}
    for c, val in header_row2.items():
        if pd.isna(val):
            continue
        s = str(val)
        if "Δ" in s or "→" in s or "acum" in s.lower():
            continue
        m = re.search(r"(20\d{2})", s)
        if m:
            year_cols[c] = int(m.group(1))
    return year_cols


def _load_estoque_file(path, titulo_valor):
    """Para arquivos no padrão Estoque_Empregos/Estoque_Empresas: detecta os
    anos disponíveis dinamicamente pelo cabeçalho (a série varia por cidade).
    Retorna (long_df, delta_df)."""
    xl = pd.ExcelFile(path)
    long_rows = []
    delta_rows = []
    for geo in xl.sheet_names:
        df = xl.parse(geo, header=None)
        header_row2 = df.iloc[2]
        year_cols = _detect_year_cols(header_row2)
        delta_col = max(year_cols.keys()) + 1 if year_cols else None

        for r in range(3, df.shape[0]):
            secao = df.iat[r, 0]
            descricao = df.iat[r, 1]
            if pd.isna(secao):
                continue
            is_total = secao == "TOTAL"
            descricao = "TOTAL GERAL" if is_total else descricao
            for c, ano in year_cols.items():
                valor = _parse_num(df.iat[r, c])
                long_rows.append(
                    {"geo": geo, "secao": secao, "descricao": descricao, "ano": ano, titulo_valor: valor}
                )
            delta = _parse_pct(df.iat[r, delta_col]) if delta_col is not None else None
            delta_rows.append(
                {"geo": geo, "secao": secao, "descricao": descricao, "delta_pct": delta, "is_total": is_total}
            )
    return pd.DataFrame(long_rows), pd.DataFrame(delta_rows)


@st.cache_data
def load_empregos(city_key):
    cfg = CITIES[city_key]
    return _load_estoque_file(cfg["empregos_file"], "empregos")


@st.cache_data
def load_estabelecimentos(city_key):
    cfg = CITIES[city_key]
    return _load_estoque_file(cfg["estab_file"], "estabelecimentos")


@st.cache_data
def load_ql_grupo(city_key):
    """Retorna dict {chave: DataFrame} para as 4 abas do arquivo de QL por grupo."""
    cfg = CITIES[city_key]
    abbr = cfg["ref_abbr"]
    sheet_map = {
        f"Empresas Ativas vs {cfg['ref_geo']}": f"ATIV_vs_{abbr}",
        "Empresas Ativas vs Brasil": "ATIV_vs_BR",
        f"Todas as Empresas Criadas vs {cfg['ref_geo']}": f"TODA_vs_{abbr}",
        "Todas as Empresas Criadas vs Brasil": "TODA_vs_BR",
    }
    xl = pd.ExcelFile(cfg["ql_file"])
    result = {}
    for label, sheet in sheet_map.items():
        df = xl.parse(sheet, header=None)
        header_row = 2
        cols = ["codigo", "nome"] + [f"ql_{a}" for a in CNPJ_ANOS] + ["ql_medio", "periodos_cresc"]
        data = df.iloc[header_row + 1 :].reset_index(drop=True)
        data.columns = cols
        for c in cols[2:]:
            data[c] = data[c].apply(_parse_num)
        data = data.dropna(subset=["codigo"])
        result[label] = data
    return result
