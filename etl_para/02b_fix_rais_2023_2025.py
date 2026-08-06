"""Reprocessa só 2023 e 2025 (formato novo: delimitador vírgula, cabeçalho
com nomes ligeiramente diferentes) e substitui essas linhas no parquet
já gerado por 02_build_rais_vinculos.py."""

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

FILES = [
    (2023, "RAIS_VINC_PUB_NORTE2023.7z"),
    (2025, "RAIS_VINC_PUB_NORTE2025.7z"),
]


def get_header_and_delim(archive_path):
    proc = subprocess.run(
        ["7z", "e", "-y", str(archive_path), "-so"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True,
    )
    first_line_bytes = proc.stdout[:40000].split(b"\n")[0]
    text = first_line_bytes.decode("latin-1")
    delim = "," if text.count(",") > text.count(";") else ";"
    header = next(csv.reader(io.StringIO(text), delimiter=delim))
    return header, delim


def find_col(header, *needles, exclude=()):
    for i, h in enumerate(header):
        h_norm = h.strip().lower()
        if all(n.lower() in h_norm for n in needles) and not any(e.lower() in h_norm for e in exclude):
            return i
    raise ValueError(f"Coluna não encontrada para {needles} (excl {exclude}) em {header}")


def extract_txt(archive_path, dest_txt):
    with open(dest_txt, "wb") as f:
        p7z = subprocess.Popen(["7z", "e", "-y", str(archive_path), "-so"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        subprocess.run(["iconv", "-f", "ISO-8859-1", "-t", "UTF-8"], stdin=p7z.stdout, stdout=f, check=True)
        p7z.wait()


def main():
    con = duckdb.connect()
    con.execute("PRAGMA threads=6")
    con.execute(f"""
        CREATE VIEW cnae_map AS
        SELECT * FROM read_csv('{REFS_DIR}/cnae_map.csv', header=True, AUTO_DETECT=FALSE,
            columns={{'subclasse':'VARCHAR','grupo_codigo':'VARCHAR','grupo_nome':'VARCHAR',
                      'divisao_codigo':'VARCHAR','secao_codigo':'VARCHAR','secao_nome':'VARCHAR'}})
    """)

    new_frames = []
    for ano, fname in FILES:
        t0 = time.time()
        archive_path = DOWNLOADS / fname
        header, delim = get_header_and_delim(archive_path)
        print(f"[{ano}] delimitador detectado: {delim!r}", flush=True)
        idx_ativo = find_col(header, "vínculo ativo")
        idx_munic = find_col(header, "município", exclude=("trab",))
        idx_cnae = find_col(header, "cnae 2.0", "subclasse")

        txt_path = WORK_DIR / f"tmp_fix_{ano}.txt"
        print(f"[{ano}] extraindo {fname} ...", flush=True)
        extract_txt(archive_path, txt_path)

        col_names = [f"c{i}" for i in range(len(header))]
        cols_sql = ", ".join(f"'{c}':'VARCHAR'" for c in col_names)

        query = f"""
            SELECT
                {ano} AS ano,
                CASE WHEN TRIM(c{idx_munic}) IN ({','.join(f"'{m}'" for m in MUNICIPIOS)})
                     THEN TRIM(c{idx_munic}) ELSE 'PARA' END AS municipio,
                cm.grupo_codigo,
                cm.secao_codigo,
                COUNT(*) AS empregos
            FROM read_csv('{txt_path}', delim='{delim}', header=True, quote='"', encoding='latin-1',
                columns={{{cols_sql}}}, strict_mode=False, ignore_errors=True)
            LEFT JOIN cnae_map cm ON cm.subclasse = TRIM(c{idx_cnae})
            WHERE TRIM(c{idx_ativo}) = '1'
            GROUP BY 1, 2, 3, 4
        """
        df = con.execute(query).df()
        new_frames.append(df)
        txt_path.unlink()
        print(f"[{ano}] OK — {len(df)} linhas agregadas — {time.time()-t0:.0f}s", flush=True)

    new_df = pd.concat(new_frames, ignore_index=True)

    old = pd.read_parquet(OUT_PARQUET)
    old = old[~old["ano"].isin([2023, 2025])]
    combined = pd.concat([old, new_df], ignore_index=True)
    combined.to_parquet(OUT_PARQUET, index=False)
    print(f"Parquet atualizado: {len(combined)} linhas totais (era {len(old)} + novas {len(new_df)})")


if __name__ == "__main__":
    main()
