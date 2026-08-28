# -*- coding: utf-8 -*-
"""
comparar_sertec.py
==================================================================
Compara dos archivos HISTORICO_SERTEC (Excel) y genera un reporte de
CAMBIOS DE ESTADO entre el archivo anterior y el nuevo, ademas de un
cruce en la hoja "Base SF" que detecta OST_NUM / F11_NUM dentro de la
columna DESCRIPCION y los asocia al SS_NRO.

QUE HACE
------------------------------------------------------------------
1) Empareja cada orden por OST_NUM entre los dos archivos.
2) Compara las columnas de estado que definas y clasifica cada orden:
      - NUEVA          : aparece solo en el archivo nuevo
      - DESAPARECIDA   : estaba en el anterior y ya no esta en el nuevo
      - CAMBIO_ESTADO  : cambio al menos una columna de estado
      - SIN_CAMBIO     : sigue igual
3) En "Base SF" busca dentro de DESCRIPCION los OST_NUM / F11_NUM reales
   (validados contra la Base SERTEC del archivo nuevo) y arma una tabla
   que enlaza SS_NRO  <->  OST_NUM / F11_NUM.

COMO SE USA
------------------------------------------------------------------
    python comparar_sertec.py  ARCHIVO_ANTERIOR.xlsx  ARCHIVO_NUEVO.xlsx
    python comparar_sertec.py  ARCHIVO_ANTERIOR.xlsx  ARCHIVO_NUEVO.xlsx  salida.xlsx

Si no pasas nombre de salida, se crea "reporte_cambios_sertec.xlsx".

REQUISITOS
------------------------------------------------------------------
    pip install pandas openpyxl
==================================================================
"""

import sys
import re
import unicodedata
import pandas as pd


# ==================================================================
#  CONFIGURACION  (aqui pones "los parametros que tu le des")
# ==================================================================

# Nombres de las hojas dentro del Excel.
HOJA_SERTEC = "Base SERTEC"
HOJA_SF     = "Base SF"

# Columna que identifica de forma unica cada orden (la llave para emparejar).
LLAVE = "OST_NUM"

# Columnas de estado que se comparan entre el archivo anterior y el nuevo.
# Agrega o quita las que te interesen.
COLUMNAS_ESTADO = [
    "F11_ESTADO",
    "OST_ESTADO",
    "OST_SUBESTADO",
    "OST_ESTADO_GESTION_PRODUCTO",
    "SUB_ESTADO_EXTERNO",
]

# Columnas extra que quieras arrastrar al reporte para dar contexto
# (se toman del archivo nuevo). Deja la lista vacia si no quieres ninguna.
COLUMNAS_CONTEXTO = [
    "F11_NUM",
    "PROD_NOMBRE",
    "PROD_MARCA",
    "OST_CREADOR_SUCURSAL",
    "DIAS_SERTEC",
    "RANGO_SERTEC",
]

# --- Filtros opcionales sobre el archivo NUEVO -------------------
# Deja el diccionario vacio {} para no filtrar.
# Ejemplo: {"F11_ESTADO": ["INGRESADO", "DESPACHADO"]}
# Solo se incluyen filas cuyo valor este dentro de la lista.
FILTROS = {}

# Si True, en la hoja "SF_cruce" solo se muestran las filas donde SI se
# encontro al menos un OST_NUM o F11_NUM en la descripcion.
SF_SOLO_CON_COINCIDENCIA = False


# ==================================================================
#  UTILIDADES
# ==================================================================

def _norm_texto(x):
    """Pasa a mayusculas y quita acentos, para buscar sin sorpresas."""
    if x is None:
        return ""
    s = str(x)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.upper()


def _norm_llave(x):
    """Normaliza la llave a texto limpio (14405.0 -> '14405', '<NA>' -> '')."""
    if x is None:
        return ""
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    s = str(x).strip()
    if s.lower() in ("nan", "none", "<na>", ""):
        return ""
    return s


def cargar_hoja(ruta, hoja):
    df = pd.read_excel(ruta, sheet_name=hoja, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    return df


# ==================================================================
#  1) COMPARACION DE ESTADOS ENTRE LOS DOS ARCHIVOS
# ==================================================================

def comparar_estados(df_ant, df_new):
    # Normaliza la llave en ambos.
    df_ant = df_ant.copy()
    df_new = df_new.copy()
    df_ant["_LLAVE"] = df_ant[LLAVE].map(_norm_llave)
    df_new["_LLAVE"] = df_new[LLAVE].map(_norm_llave)
    df_ant = df_ant[df_ant["_LLAVE"] != ""]
    df_new = df_new[df_new["_LLAVE"] != ""]

    # Aplica filtros opcionales sobre el archivo nuevo.
    for col, valores in FILTROS.items():
        if col in df_new.columns:
            df_new = df_new[df_new[col].isin(valores)]

    # Si hay llaves repetidas nos quedamos con la ultima aparicion.
    df_ant = df_ant.drop_duplicates("_LLAVE", keep="last").set_index("_LLAVE")
    df_new = df_new.drop_duplicates("_LLAVE", keep="last").set_index("_LLAVE")

    llaves = sorted(set(df_ant.index) | set(df_new.index))
    estados_presentes = [c for c in COLUMNAS_ESTADO if c in df_new.columns or c in df_ant.columns]
    contexto_presentes = [c for c in COLUMNAS_CONTEXTO if c in df_new.columns]

    filas = []
    for k in llaves:
        en_ant = k in df_ant.index
        en_new = k in df_new.index
        fila = {LLAVE: k}

        # Contexto (desde el archivo nuevo si existe, si no del anterior).
        origen_ctx = df_new.loc[k] if en_new else df_ant.loc[k]
        for c in contexto_presentes:
            fila[c] = origen_ctx.get(c, "")

        if en_ant and not en_new:
            clasificacion = "DESAPARECIDA"
        elif en_new and not en_ant:
            clasificacion = "NUEVA"
        else:
            clasificacion = "SIN_CAMBIO"

        cambios = []
        for col in estados_presentes:
            va = df_ant.loc[k].get(col, "") if en_ant else ""
            vn = df_new.loc[k].get(col, "") if en_new else ""
            va = "" if pd.isna(va) else str(va)
            vn = "" if pd.isna(vn) else str(vn)
            fila[f"{col}__ANTES"] = va
            fila[f"{col}__AHORA"] = vn
            if en_ant and en_new and va != vn:
                cambios.append(f"{col}: {va or '(vacio)'} -> {vn or '(vacio)'}")

        if clasificacion == "SIN_CAMBIO" and cambios:
            clasificacion = "CAMBIO_ESTADO"

        fila["CLASIFICACION"] = clasificacion
        fila["DETALLE_CAMBIOS"] = " | ".join(cambios)
        filas.append(fila)

    cols = ([LLAVE] + contexto_presentes + ["CLASIFICACION", "DETALLE_CAMBIOS"]
            + [f"{c}__ANTES" for c in estados_presentes]
            + [f"{c}__AHORA" for c in estados_presentes])
    df_out = pd.DataFrame(filas)
    df_out = df_out[[c for c in cols if c in df_out.columns]]
    return df_out


# ==================================================================
#  2) CRUCE EN BASE SF:  DESCRIPCION -> OST_NUM / F11_NUM -> SS_NRO
# ==================================================================

# OST: numeros cortos (2-7 digitos) que aparecen despues de la etiqueta "OST".
# Se permiten algunos caracteres no numericos en medio (ej: "OST (numero 47202)",
# "OST:48296", "OST - 5966"). El resultado igual se valida contra la lista real.
_RE_OST = re.compile(r"OST\D{0,12}?(\d{2,7})", re.IGNORECASE)

# F11: los numeros F11 son largos y distintivos (10 digitos, parten con 116...).
# En vez de depender de la etiqueta (viene pegado como "F1162444336" o suelto
# como "F11 1162358848"), extraemos todos los numeros de 9-12 digitos y los
# validamos contra la lista real de F11_NUM. Asi no hay falsos positivos.
_RE_NUM_LARGO = re.compile(r"\d{9,12}")


def cruzar_sf(df_sf, df_sertec_new):
    # Conjuntos de valores reales para validar lo que extraemos del texto.
    set_ost = set(df_sertec_new[LLAVE].map(_norm_llave)) - {""}
    set_f11 = set()
    if "F11_NUM" in df_sertec_new.columns:
        set_f11 = set(df_sertec_new["F11_NUM"].map(_norm_llave)) - {""}

    filas = []
    for _, r in df_sf.iterrows():
        desc = r.get("DESCRIPCION", "")
        desc = "" if pd.isna(desc) else str(desc)

        ost_encontrados, f11_encontrados = [], []
        for m in _RE_OST.finditer(desc):
            n = m.group(1).lstrip("0") or m.group(1)
            if n in set_ost and n not in ost_encontrados:
                ost_encontrados.append(n)
        for m in _RE_NUM_LARGO.finditer(desc):
            n = m.group(0)
            if n in set_f11 and n not in f11_encontrados:
                f11_encontrados.append(n)

        hay = bool(ost_encontrados or f11_encontrados)
        filas.append({
            "SS_NRO": _norm_llave(r.get("SS_NRO", "")),
            "TIENE_COINCIDENCIA": "SI" if hay else "NO",
            "OST_ENCONTRADOS": ", ".join(ost_encontrados),
            "F11_ENCONTRADOS": ", ".join(f11_encontrados),
            "ESTADO": r.get("ESTADO", ""),
            "DESCRIPCION": desc,
        })

    df_out = pd.DataFrame(filas)
    if SF_SOLO_CON_COINCIDENCIA:
        df_out = df_out[df_out["TIENE_COINCIDENCIA"] == "SI"]
    return df_out


# ==================================================================
#  RESUMEN
# ==================================================================

def construir_resumen(df_cambios, df_sf):
    conteo = df_cambios["CLASIFICACION"].value_counts()
    filas = [{"METRICA": f"Ordenes {k}", "VALOR": int(v)} for k, v in conteo.items()]
    filas.insert(0, {"METRICA": "Total ordenes comparadas", "VALOR": int(len(df_cambios))})
    filas.append({"METRICA": "Filas Base SF revisadas", "VALOR": int(len(df_sf))})
    filas.append({"METRICA": "Filas SF con OST/F11 encontrado",
                  "VALOR": int((df_sf["TIENE_COINCIDENCIA"] == "SI").sum())})
    return pd.DataFrame(filas)


# ==================================================================
#  MAIN
# ==================================================================

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("ERROR: faltan argumentos. Uso:")
        print("  python comparar_sertec.py ANTERIOR.xlsx NUEVO.xlsx [salida.xlsx]")
        sys.exit(1)

    ruta_ant = sys.argv[1]
    ruta_new = sys.argv[2]
    ruta_out = sys.argv[3] if len(sys.argv) > 3 else "reporte_cambios_sertec.xlsx"

    print(f"Archivo ANTERIOR : {ruta_ant}")
    print(f"Archivo NUEVO    : {ruta_new}")

    sertec_ant = cargar_hoja(ruta_ant, HOJA_SERTEC)
    sertec_new = cargar_hoja(ruta_new, HOJA_SERTEC)
    sf_new     = cargar_hoja(ruta_new, HOJA_SF)

    df_cambios = comparar_estados(sertec_ant, sertec_new)
    df_sf      = cruzar_sf(sf_new, sertec_new)
    df_resumen = construir_resumen(df_cambios, df_sf)

    # Vista aparte solo con los cambios de estado, para ir directo al grano.
    df_solo_cambios = df_cambios[df_cambios["CLASIFICACION"] == "CAMBIO_ESTADO"]

    with pd.ExcelWriter(ruta_out, engine="openpyxl") as xw:
        df_resumen.to_excel(xw, sheet_name="Resumen", index=False)
        df_solo_cambios.to_excel(xw, sheet_name="Cambios_de_estado", index=False)
        df_cambios.to_excel(xw, sheet_name="Comparacion_completa", index=False)
        df_sf.to_excel(xw, sheet_name="SF_cruce", index=False)

    print("\n=== RESUMEN ===")
    for _, r in df_resumen.iterrows():
        print(f"  {r['METRICA']}: {r['VALOR']}")
    print(f"\nListo. Reporte generado en: {ruta_out}")


if __name__ == "__main__":
    main()
