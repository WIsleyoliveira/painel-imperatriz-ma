"""Escaneia os arquivos ESTABELE (Brasil inteiro) uma única vez, junta com SIMPLES
(para status MEI) e com o mapa CNAE do IBGE (subclasse -> grupo -> seção), e grava
um parquet compacto com só as colunas necessárias. Depois disso, todas as agregações
(Ananindeua, Capanema, Pará, Brasil) rodam rápido em cima desse parquet."""

import duckdb
import time

CNPJ_DIR = "/Volumes/WISKET/cnpj"
ESTABELE_UTF8_DIR = "/Volumes/WISKET/painel-imperatriz-ma-main/etl_para/staging/cnpj_utf8"
REFS_DIR = "/Volumes/WISKET/painel-imperatriz-ma-main/etl_para/refs"
OUT_DIR = "/Volumes/WISKET/painel-imperatriz-ma-main/etl_para/staging"

ESTABELE_COLS = [
    "cnpj_basico", "cnpj_ordem", "cnpj_dv", "matriz_filial", "nome_fantasia",
    "situacao_cadastral", "data_situacao", "motivo_situacao", "cidade_exterior",
    "pais", "data_inicio", "cnae_principal", "cnae_secundaria", "tipo_logr",
    "logradouro", "numero", "complemento", "bairro", "cep", "uf", "municipio",
    "ddd1", "tel1", "ddd2", "tel2", "dddfax", "fax", "email", "sit_especial",
    "data_sit_especial",
]
ESTABELE_COLS_SQL = ", ".join(f"'{c}':'VARCHAR'" for c in ESTABELE_COLS)

SIMPLES_COLS = [
    "cnpj_basico", "opcao_simples", "data_opcao_simples", "data_exclusao_simples",
    "opcao_mei", "data_opcao_mei", "data_exclusao_mei",
]
SIMPLES_COLS_SQL = ", ".join(f"'{c}':'VARCHAR'" for c in SIMPLES_COLS)

def main():
    t0 = time.time()
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='6GB'")
    con.execute("PRAGMA threads=6")

    con.execute(f"""
        CREATE VIEW cnae_map AS
        SELECT * FROM read_csv('{REFS_DIR}/cnae_map.csv', header=True, AUTO_DETECT=FALSE,
            columns={{'subclasse':'VARCHAR','grupo_codigo':'VARCHAR','grupo_nome':'VARCHAR',
                      'divisao_codigo':'VARCHAR','secao_codigo':'VARCHAR','secao_nome':'VARCHAR'}})
    """)

    con.execute(f"""
        CREATE VIEW simples AS
        SELECT
            cnpj_basico,
            (opcao_mei = 'S' AND data_exclusao_mei = '00000000') AS is_mei
        FROM read_csv('{CNPJ_DIR}/F.K03200$W.SIMPLES.CSV.D60711', delim=';', header=False,
            quote='"', encoding='latin-1', columns={{{SIMPLES_COLS_SQL}}})
    """)

    print("Lendo ESTABELE (glob dos 10 arquivos) e agregando em staging parquet...", flush=True)

    con.execute(f"""
        COPY (
            SELECT
                e.municipio,
                e.uf,
                cm.grupo_codigo,
                cm.secao_codigo,
                (e.situacao_cadastral = '02') AS is_ativa,
                TRY_CAST(SUBSTR(e.data_inicio, 1, 4) AS INTEGER) AS ano_abertura,
                COALESCE(s.is_mei, FALSE) AS is_mei
            FROM read_csv(
                '{ESTABELE_UTF8_DIR}/K3241.K03200Y*.D60711.ESTABELE.utf8',
                delim=';', header=False, quote='"',
                columns={{{ESTABELE_COLS_SQL}}}, strict_mode=False, ignore_errors=True
            ) e
            LEFT JOIN cnae_map cm ON cm.subclasse = e.cnae_principal
            LEFT JOIN simples s ON s.cnpj_basico = e.cnpj_basico
        ) TO '{OUT_DIR}/estabele_staging.parquet' (FORMAT PARQUET)
    """)

    n = con.execute(f"SELECT COUNT(*) FROM read_parquet('{OUT_DIR}/estabele_staging.parquet')").fetchone()[0]
    print(f"OK: {n:,} linhas gravadas em estabele_staging.parquet — {time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    main()
