"""RAIS Vínculos -> estoque de empregos formais por seção/grupo CNAE,
Ananindeua, Capanema e Pará, ano a ano.

Anos 2001/2003/2005: a RAIS só populou "CNAE 2.0" a partir de 2007, então
usamos "CNAE 95 Classe" + tabela de correspondência oficial IBGE (CNAE 1.0 x
CNAE 2.0) para chegar no grupo CNAE 2.0 (cobre ~95% dos vínculos; o resto
fica como "Não classificado", igual a um "—" nas outras tabelas).
Anos 2007+: usamos "CNAE 2.0 Subclasse" direto, sem crosswalk.

Extrai cada .7z para a própria WISKET (não no disco interno, que está com
pouco espaço livre), localiza dinamicamente as colunas de interesse pelo
cabeçalho (a posição varia entre arquivos), agrega com duckdb e apaga o
.txt extraído em seguida.
"""

import csv
import io
import subprocess
import time
from pathlib import Path

import duckdb
import pandas as pd

DOWNLOADS = Path("/Users/wisley/Downloads")
WORK_DIR = Path("/Volumes/WISKET/painel-imperatriz-ma-main/etl_para/staging")
REFS_DIR = Path("/Volumes/WISKET/painel-imperatriz-ma-main/etl_para/refs")
OUT_PARQUET = WORK_DIR / "rais_vinculos_agregado.parquet"

MUNICIPIOS = {"150080": "Ananindeua", "150293": "Capanema"}

CNAE95_YEARS = {2001, 2003, 2005}

FILES = [
    (2001, "PA2001.7z"),
    (2003, "PA2003.7z"),
    (2005, "PA2005.7z"),
    (2007, "PA2007.7z"),
    (2009, "PA2009.7z"),
    (2011, "PA2011.7z"),
    (2013, "PA2013.7z"),
    (2015, "PA2015.7z"),
    (2017, "PA2017.7z"),
    (2019, "RAIS_VINC_PUB_NORTE2019.7z"),
    (2021, "RAIS_VINC_PUB_NORTE2021.7z"),
    (2023, "RAIS_VINC_PUB_NORTE2023.7z"),
    (2025, "RAIS_VINC_PUB_NORTE2025.7z"),
]


def get_header(archive_path):
    proc = subprocess.run(
        ["7z", "e", "-y", str(archive_path), "-so"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True,
    )
    first_line = proc.stdout[:20000].split(b"\n")[0]
    text = first_line.decode("latin-1")
    return next(csv.reader(io.StringIO(text), delimiter=";"))


def find_col(header, *needles, exclude=()):
    for i, h in enumerate(header):
        h_norm = h.strip().lower()
        if all(n.lower() in h_norm for n in needles) and not any(e.lower() in h_norm for e in exclude):
            return i
    raise ValueError(f"Coluna não encontrada para {needles} (excl {exclude}) em {header}")


def extract_txt(archive_path, dest_txt):
    with open(dest_txt, "wb") as f:
        subprocess.run(["7z", "e", "-y", str(archive_path), "-so"], stdout=f, check=True)


def main():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=6")
    con.execute(f"""
        CREATE VIEW cnae_map AS
        SELECT * FROM read_csv('{REFS_DIR}/cnae_map.csv', header=True, AUTO_DETECT=FALSE,
            columns={{'subclasse':'VARCHAR','grupo_codigo':'VARCHAR','grupo_nome':'VARCHAR',
                      'divisao_codigo':'VARCHAR','secao_codigo':'VARCHAR','secao_nome':'VARCHAR'}})
    """)
    con.execute(f"""
        CREATE VIEW cnae95_map AS
        SELECT * FROM read_csv('{REFS_DIR}/cnae95_to_cnae20.csv', header=True, AUTO_DETECT=FALSE,
            columns={{'cnae95_classe':'VARCHAR','cnae20_classe':'VARCHAR','grupo_codigo':'VARCHAR'}})
    """)
    con.execute(f"""
        CREATE VIEW grupo_secao AS
        SELECT * FROM read_csv('{REFS_DIR}/grupo_secao.csv', header=True, AUTO_DETECT=FALSE,
            columns={{'grupo_codigo':'VARCHAR','grupo_nome':'VARCHAR','secao_codigo':'VARCHAR','secao_nome':'VARCHAR'}})
    """)

    all_frames = []
    t_total = time.time()

    for ano, fname in FILES:
        t0 = time.time()
        archive_path = DOWNLOADS / fname
        header = get_header(archive_path)
        idx_ativo = find_col(header, "vínculo ativo")
        idx_munic = find_col(header, "município")

        usa_crosswalk = ano in CNAE95_YEARS
        if usa_crosswalk:
            idx_cnae = find_col(header, "cnae 95", "classe")
        else:
            idx_cnae = find_col(header, "cnae 2.0", "subclasse")

        txt_path = WORK_DIR / f"tmp_{ano}.txt"
        print(f"[{ano}] extraindo {fname} (modo={'CNAE95+crosswalk' if usa_crosswalk else 'CNAE2.0 direto'}) ...", flush=True)
        extract_txt(archive_path, txt_path)

        col_names = [f"c{i}" for i in range(len(header))]
        cols_sql = ", ".join(f"'{c}':'VARCHAR'" for c in col_names)

        if usa_crosswalk:
            join_clause = f"""
                LEFT JOIN cnae95_map cm95 ON cm95.cnae95_classe = TRIM(c{idx_cnae})
                LEFT JOIN grupo_secao gs ON gs.grupo_codigo = cm95.grupo_codigo
            """
            grupo_expr = "gs.grupo_codigo"
            secao_expr = "gs.secao_codigo"
        else:
            join_clause = f"LEFT JOIN cnae_map cm ON cm.subclasse = TRIM(c{idx_cnae})"
            grupo_expr = "cm.grupo_codigo"
            secao_expr = "cm.secao_codigo"

        query = f"""
            SELECT
                {ano} AS ano,
                CASE WHEN TRIM(c{idx_munic}) IN ({','.join(f"'{m}'" for m in MUNICIPIOS)})
                     THEN TRIM(c{idx_munic}) ELSE 'PARA' END AS municipio,
                {grupo_expr} AS grupo_codigo,
                {secao_expr} AS secao_codigo,
                COUNT(*) AS empregos
            FROM read_csv('{txt_path}', delim=';', header=True, quote='"', encoding='latin-1',
                columns={{{cols_sql}}}, strict_mode=False, ignore_errors=True)
            {join_clause}
            WHERE TRIM(c{idx_ativo}) = '1'
            GROUP BY 1, 2, 3, 4
        """
        df = con.execute(query).df()
        all_frames.append(df)
        txt_path.unlink()
        print(f"[{ano}] OK — {len(df)} linhas agregadas — {time.time()-t0:.0f}s", flush=True)

    result = pd.concat(all_frames, ignore_index=True)
    result.to_parquet(OUT_PARQUET, index=False)
    print(f"TOTAL: {time.time()-t_total:.0f}s — gravado em {OUT_PARQUET}")


if __name__ == "__main__":
    main()
