# scripts/comparar_sertec.py

Compara dos archivos `HISTORICO_SERTEC` (Excel) y genera un reporte de
**cambios de estado** entre el archivo anterior y el nuevo, mas un **cruce**
que enlaza `SS_NRO` con los `OST_NUM` / `F11_NUM` que aparecen dentro de la
columna `DESCRIPCION` de la hoja `Base SF`.

## Instalacion (una sola vez)

```bash
pip install pandas openpyxl
```

## Uso

```bash
python scripts/comparar_sertec.py  ANTERIOR.xlsx  NUEVO.xlsx  [salida.xlsx]
```

- `ANTERIOR.xlsx`: el historico previo.
- `NUEVO.xlsx`: el historico mas reciente.
- `salida.xlsx` (opcional): nombre del reporte. Por defecto
  `reporte_cambios_sertec.xlsx`.

## Que entrega el reporte (4 hojas)

| Hoja | Contenido |
|------|-----------|
| `Resumen` | Totales: ordenes comparadas, con cambio, nuevas, filas SF cruzadas. |
| `Cambios_de_estado` | Solo las ordenes cuyo estado cambio, con el detalle `antes -> ahora`. |
| `Comparacion_completa` | Todas las ordenes con su clasificacion (NUEVA / DESAPARECIDA / CAMBIO_ESTADO / SIN_CAMBIO). |
| `SF_cruce` | Cada `SS_NRO` con los `OST_NUM` / `F11_NUM` hallados en su `DESCRIPCION`. |

## Parametros (editar arriba del script)

En el bloque **CONFIGURACION** de `comparar_sertec.py`:

- `LLAVE`: columna para emparejar ordenes (por defecto `OST_NUM`).
- `COLUMNAS_ESTADO`: que columnas de estado comparar.
- `COLUMNAS_CONTEXTO`: columnas extra para dar contexto en el reporte.
- `FILTROS`: filtrar el archivo nuevo, ej. `{"F11_ESTADO": ["INGRESADO"]}`.
- `SF_SOLO_CON_COINCIDENCIA`: `True` para mostrar en `SF_cruce` solo las
  filas donde si se encontro un OST/F11.

## Notas del cruce OST/F11

- Los `F11_NUM` (numeros largos de ~10 digitos) se detectan y se validan
  contra la lista real de F11 del archivo nuevo, asi que no hay falsos
  positivos aunque vengan pegados (`F1162444336`) o sueltos (`F11 1162358848`).
- Los `OST_NUM` (numeros cortos) se buscan junto a la etiqueta `OST` y tambien
  se validan contra la lista real, evitando confundirlos con guias, boletas,
  SKU o codigos de local.
