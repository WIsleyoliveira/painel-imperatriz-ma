#!/bin/bash
set -e
SRC="/Volumes/WISKET/cnpj"
DST="/Volumes/WISKET/painel-imperatriz-ma-main/etl_para/staging/cnpj_utf8"
for i in 0 1 2 3 4 5 6 7 8 9; do
  f="K3241.K03200Y${i}.D60711.ESTABELE"
  echo "convertendo $f ..."
  iconv -f ISO-8859-1 -t UTF-8 "$SRC/$f" > "$DST/$f.utf8" 2>"$DST/$f.err" || echo "AVISO: $f teve erros parciais (ver $f.err)"
  echo "  -> $(wc -l < "$DST/$f.utf8") linhas"
done
echo "TODOS CONVERTIDOS"
