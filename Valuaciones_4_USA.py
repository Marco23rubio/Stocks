import pandas as pd
import numpy as np
from datetime import datetime
import re
import sys
import matplotlib.pyplot as plt
from functools import reduce

import glob
import os

ruta = "USA/"
archivos = glob.glob(ruta + "*.xlsx")
tickers = [os.path.splitext(os.path.basename(a))[0] for a in archivos if not os.path.basename(a).startswith("~")]

for ticket in tickers:
    print(f"\n{'='*40}\nProcesando: {ticket}\n{'='*40}")
    try:
        ruta_archivo = ruta + f"{ticket}.xlsx"
        archivo_stock = f"USA/DatosHistoricos/Datos históricos {ticket}"
        archivo_market = "Datos históricos del S&P 500 TR"
        market_risk_premium = 0.07
        archivo_market_bonos = "bonos_usa"
        archivo_inflacion_usa = "inflation_usa"


        df_err = pd.read_excel(ruta_archivo, header=19)

        secciones = [
            'Per Share Data', 'Income Statement', 'Balance Sheet',
            'Cash Flow Statement', 'Valuation Ratios', 'Valuation and Quality',
            'GuruFocus Rankings', 'Ratios'
        ]
        patron = '|'.join(secciones)
        primera_col = df_err.columns[0]
        mask = df_err[primera_col].astype(str).str.contains(patron, case=False, na=False)
        df_err = df_err[~mask].reset_index(drop=True)

        df_err.columns = df_err.iloc[0]
        if '\t' in df_err.columns:
            df_err = df_err.drop(columns=['\t'], errors='ignore')
        df_err = df_err[1:].reset_index(drop=True)


        cols = df_err.columns.tolist()
        ttm_idx = cols.index("TTM/current")
        df_hist = df_err.iloc[:, :ttm_idx].copy() 

        valid_headers = []

        row = df_hist.loc[df_hist["Fiscal Period"].eq("Revenue per Share")].iloc[0]

        valid_headers = [
            col for col in df_hist.columns
            if col != "Fiscal Period"
            and not pd.isna(row[col])
            and not (isinstance(row[col], str) and row[col].strip() == "-")
        ]

        valid_years = [int(h[-4:]) for h in valid_headers]

        last_20_years = valid_years[-20:]

        def calcular_crecimiento_syp(archivo_csv, anio_cierre, periodo_anos=5):
            df = pd.read_csv(f"{archivo_csv}.csv")
            df['Fecha'] = pd.to_datetime(df['Fecha'], format='%d.%m.%Y')
            df['Cierre'] = df['Cierre'].str.replace(',', '').astype(float)
            df = df.sort_values('Fecha')

            # Filtrar datos del año de cierre
            df_ano = df[df['Fecha'].dt.year == anio_cierre]
            if df_ano.empty:
                raise ValueError(f"No hay datos para el año {anio_cierre}")
            fecha_final = df_ano['Fecha'].max()
            fecha_inicio = fecha_final - pd.DateOffset(years=periodo_anos)

            df_filtrado = df[(df['Fecha'] >= fecha_inicio) & (df['Fecha'] <= fecha_final)]
            if df_filtrado.shape[0] < 2:
                raise ValueError("Datos insuficientes para el período solicitado")

            precio_inicial = df_filtrado.iloc[0]['Cierre']
            precio_final = df_filtrado.iloc[-1]['Cierre']

            tasa = ((precio_final / precio_inicial) ** (1 / periodo_anos)) - 1
            return fecha_inicio.date(), fecha_final.date(), tasa 


        crecimiento_syp_porcentaje_años = []

        for año in last_20_years:
            fi, ff, tasa = calcular_crecimiento_syp(archivo_market, año)
            crecimiento_syp_porcentaje_años.append({
                "año_cierre": año,
                "fecha_inicio": fi,
                "fecha_final": ff,
                "CAGR_%": round(tasa, 4)
            })

        data_bonos = pd.read_csv(archivo_market_bonos + '.csv' , header=0)

        data_bonos['observation_date'] = pd.to_datetime(data_bonos['observation_date'], format='%Y-%m-%d')
        data_bonos = data_bonos.rename(columns={data_bonos.columns[1]: 'DGS1'})

        data_bonos = data_bonos[data_bonos['observation_date'].dt.year.isin(last_20_years)]

        promedio_bonos = (
            data_bonos
            .groupby(data_bonos['observation_date'].dt.year)['DGS1']
            .mean()
            .reset_index()
            .rename(columns={'observation_date': 'Año', 'DGS1': 'Promedio_Anual'})
        )
        promedio_bonos['Promedio_Anual'] = promedio_bonos['Promedio_Anual'].round(4)

        data_inflacion_usa = pd.read_csv(archivo_inflacion_usa + ".csv")

        data_inflacion_usa["observation_date"] = pd.to_datetime(
            data_inflacion_usa["observation_date"],
            dayfirst=True,
            errors="coerce"
        )

        data_inflacion_usa["CPIAUCSL_PC1"] = pd.to_numeric(
            data_inflacion_usa["CPIAUCSL_PC1"],
            errors="coerce"
        )

        data_inflacion_usa = data_inflacion_usa[
            data_inflacion_usa["observation_date"].dt.year.isin(last_20_years)
        ]

        df_resultados_inf_usa = (
            data_inflacion_usa
            .assign(Año=data_inflacion_usa["observation_date"].dt.year)
            .groupby("Año", as_index=False)["CPIAUCSL_PC1"]
            .mean()
            .rename(columns={"CPIAUCSL_PC1": "Tasa de Inflación"})
            .sort_values("Año")
            .reset_index(drop=True)
        )

        df_resultados_inf_usa["Tasa de Inflación"] = (
            df_resultados_inf_usa["Tasa de Inflación"] / 100
        ).round(4)

        df_stock  = pd.read_csv(f"{archivo_stock}.csv")
        df_market = pd.read_csv(f"{archivo_market}.csv")

        df_stock['Fecha'] = pd.to_datetime(df_stock['Fecha'], format='%Y-%m-%d', errors='coerce')
        df_stock = df_stock.dropna(subset=['Fecha']).sort_values('Fecha').copy()

        df_stock['Cierre'] = (
            df_stock['Cierre']
            .astype(str)
            .str.replace(',', '', regex=False)
            .str.strip()
        )
        df_stock['Cierre'] = pd.to_numeric(df_stock['Cierre'], errors='coerce')
        df_stock = df_stock.dropna(subset=['Cierre']).copy()

        df_stock['Rend_Stock'] = df_stock['Cierre'].pct_change()
        df_stock = df_stock.dropna(subset=['Rend_Stock']).copy()

        df_market['Fecha'] = pd.to_datetime(df_market['Fecha'], format='%d.%m.%Y', errors='coerce')
        df_market = df_market.dropna(subset=['Fecha']).sort_values('Fecha').copy()

        df_market['Cierre'] = (
            df_market['Cierre']
            .astype(str)
            .str.replace(',', '', regex=False)
            .str.strip()
        )
        df_market['Cierre'] = pd.to_numeric(df_market['Cierre'], errors='coerce')
        df_market = df_market.dropna(subset=['Cierre']).copy()

        df_market['Rend_Market'] = df_market['Cierre'].pct_change()
        df_market = df_market.dropna(subset=['Rend_Market']).copy()

        # Asegurar datetime
        df_stock['Fecha'] = pd.to_datetime(df_stock['Fecha'])
        df_market['Fecha'] = pd.to_datetime(df_market['Fecha'])

        # Nos quedamos solo con lo que necesitamos
        df_stock_beta = df_stock[['Fecha', 'Rend_Stock']].copy()
        df_market_beta = df_market[['Fecha', 'Rend_Market']].copy()

        df_beta = pd.merge_asof(
            df_stock_beta.sort_values('Fecha'),
            df_market_beta.sort_values('Fecha'),
            on='Fecha',
            direction='nearest'
        )

        df_beta['Año'] = df_beta['Fecha'].dt.year

        def beta_anual(grupo):
            if len(grupo) < 10:   
                return np.nan
            cov = grupo['Rend_Stock'].cov(grupo['Rend_Market'])
            var_m = grupo['Rend_Market'].var()
            return cov / var_m if var_m != 0 else np.nan

        df_beta_resultado = (
            df_beta 
            .groupby('Año')
            .apply(beta_anual)
            .reset_index(name='Beta')
        )

        df_beta_resultado = df_beta_resultado.dropna(subset=['Beta'])

        df_beta_20y = df_beta_resultado[df_beta_resultado['Año'].isin(last_20_years)].copy()

        # Obtengo los DF para datos anulaes y trimestrales
        indice_ttm = df_err.columns.get_loc('TTM/current')

        df_anual = df_err.iloc[:, :indice_ttm + 1]
        df_trimestral = df_err.iloc[:, indice_ttm + 1:]
        df_trimestral.insert(0, 'Fiscal Period', df_err['Fiscal Period'])

        columna_anterior = df_anual.columns[indice_ttm - 1]
        anio_anterior = int(columna_anterior[-4:])
        # Identificar las columnas que contienen un año en su nombre
        pattern = re.compile(r'\d{4}')
        columnas_con_anio = [col for col in df_anual.columns if pattern.search(col)]

        anio_limite = min(last_20_years)

        columnas_filtradas = [col for col in columnas_con_anio if int(
            pattern.search(col).group()) >= anio_limite]

        # Asegurarse de incluir 'Fiscal Period' y 'TTM/current' si están presentes
        columnas_especiales = ['Fiscal Period', 'TTM/current']
        columnas_filtradas = [
            col for col in df_anual.columns if col in columnas_especiales] + columnas_filtradas

        df_anual_filtrado = df_anual[columnas_filtradas]

        # Mover la columna 'TTM/current' al final
        if 'TTM/current' in df_anual_filtrado.columns:
            columnas_ordenadas = [
                col for col in df_anual_filtrado.columns if col != 'TTM/current'] + ['TTM/current']
            df_anual_filtrado = df_anual_filtrado[columnas_ordenadas]

        df_anual_filtrado = df_anual_filtrado.fillna(0)

        pattern = re.compile(r"\d{4}")

        columnas_con_anio_trimestral = [
            col for col in df_trimestral.columns
            if col != "Fiscal Period" and pattern.search(str(col))
        ]

        anio_min = min(last_20_years)
        anio_max = max(last_20_years)

        columnas_filtradas_trimestral = [
            col for col in columnas_con_anio_trimestral
            if anio_min <= int(pattern.search(str(col)).group()) <= anio_max
        ]

        # (Opcional) ordenar por año para que queden en secuencia
        columnas_filtradas_trimestral.sort(key=lambda c: int(pattern.search(str(c)).group()))

        columnas_especiales_trimestral = ["Fiscal Period"]

        df_trimestral_filtrado = df_trimestral[columnas_especiales_trimestral + columnas_filtradas_trimestral].copy()
        df_trimestral_filtrado = df_trimestral_filtrado.fillna(0)

        df_anual_filtrado = df_anual_filtrado.drop(columns=["TTM/current"])

        def limpiar_df_financiero(df):
            df = df.copy()

            # Reemplazar '-' por NaN en todo el DF
            df.replace('-', np.nan, inplace=True)

            # Todas las columnas excepto 'Fiscal Period' a numéricas
            cols_datos = df.columns.drop('Fiscal Period')

            df[cols_datos] = df[cols_datos].apply(
                pd.to_numeric, errors='coerce'
            )

            return df

        df_anual_filtrado = limpiar_df_financiero(df_anual_filtrado)
        df_trimestral_filtrado = limpiar_df_financiero(df_trimestral_filtrado)

        df_anual_filtrado = df_anual_filtrado.dropna(axis=1, how='all')
        df_trimestral_filtrado = df_trimestral_filtrado.dropna(axis=1, how='all')

        # Crear DataFrame vacío con las columnas anuales
        razones_financieras = pd.DataFrame(
            columns=['Calculo', 'Explicacion'] + 
                    list(df_anual_filtrado.columns.difference(['Fiscal Period']))
        )

        def agregar_razon_financiera(df_anual_filtrado, fila_numerador, nombre_nueva_fila,
                                     *filas_denominadoras, como_porcentaje=True,
                                     calculo="", explicacion=""):

            global razones_financieras

            if df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == fila_numerador].empty:
                return
            if any(df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == fila].empty for fila in filas_denominadoras):
                return
            fila_num = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == fila_numerador].iloc[0, 1:]
            fila_den = sum(df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == fila].iloc[0, 1:].values
                           for fila in filas_denominadoras)

            razon_financiera = []
            for num, den in zip(fila_num.values, fila_den):
                if den != 0:
                    razon = num / den
                    if como_porcentaje:
                        razon *= 100
                    razon_financiera.append(f"{razon:.2f}")
                else:
                    razon_financiera.append("no deuda")

            razones_financieras.loc[nombre_nueva_fila] = [calculo, explicacion] + razon_financiera

        def agregar_razon_financiera_numerador(df_anual_filtrado, nombre_nueva_fila,
                                               fila_denominador, fila_numerador_1,
                                               fila_numerador_2, como_porcentaje=True,
                                               calculo="", explicacion=""):

            global razones_financieras

            fila_num_1 = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == fila_numerador_1].iloc[0, 1:]
            fila_num_2 = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == fila_numerador_2].iloc[0, 1:]
            fila_den = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == fila_denominador].iloc[0, 1:]

            resta_numeradores = fila_num_1.values - fila_num_2.values

            razon_financiera = []
            for num, den in zip(resta_numeradores, fila_den.values):
                if den != 0:
                    razon = num / den
                    if como_porcentaje:
                        razon *= 100
                    razon_financiera.append(f"{razon:.2f}")
                else:
                    razon_financiera.append("no deuda")

            razones_financieras.loc[nombre_nueva_fila] = [calculo, explicacion] + razon_financiera

        def agregar_fila(df_anual_filtrado, fila_nombre, nombre_nueva_fila,
                         calculo="", explicacion=""):

            global razones_financieras

            if df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == fila_nombre].empty:
                return
            fila = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == fila_nombre].iloc[0, 1:]
            razones_financieras.loc[nombre_nueva_fila] = [calculo, explicacion] + list(fila.values)

        def agregar_crecimiento_anual(fila_nombre, nombre_nueva_fila,
                                      calculo="", explicacion=""):

            global razones_financieras

            fila = razones_financieras.loc[fila_nombre].iloc[2:].astype(float)

            crecimiento_anual = fila.pct_change() * 100
            crecimiento_anual = crecimiento_anual.fillna(0)

            crecimiento_anual_formateado = [f"{x:.2f}" for x in crecimiento_anual]

            razones_financieras.loc[nombre_nueva_fila] = [calculo, explicacion] + crecimiento_anual_formateado

        def dividir_filas_razones_financieras(fila_numerador, fila_denominador,
                                              nombre_nueva_fila, como_porcentaje=True,
                                              calculo="", explicacion=""):

            global razones_financieras

            fila_num = razones_financieras.loc[fila_numerador].iloc[2:].astype(float)
            fila_den = razones_financieras.loc[fila_denominador].iloc[2:].astype(float)

            razon_financiera = fila_num.values / fila_den.values

            if como_porcentaje:
                razon_financiera *= 100

            razon_financiera = pd.Series(razon_financiera).fillna(0).values
            razon_financiera_formateada = [f"{x:.2f}" for x in razon_financiera]

            razones_financieras.loc[nombre_nueva_fila] = [calculo, explicacion] + razon_financiera_formateada


        # Llamadas a la función con el nuevo orden de parámetros
        agregar_razon_financiera(df_anual_filtrado, 'Depreciation, Depletion and Amortization', 'Amortizacion(%)', 'Gross Profit', como_porcentaje=True,calculo="Amortization/ gross profit",explicacion="* Una empresa con menor a 10% es bueno\n* Más del 20% indica mucha competencia en el sector")

        agregar_razon_financiera(df_anual_filtrado, 'Net Income', 'Net Profit Margin(%)', 'Revenue', como_porcentaje=True,calculo="Net income / sales",explicacion="* Algo mayor a 20% indica una ventaja \n* Algo menor a 10% puede indicar mucha competencia\n* empresas que generen entre un 10 al 20% son buenas\n* los bancos suelen tener porcentajes más altos")

        agregar_fila(df_anual_filtrado, 'Net Income', 'Net Income' , calculo="",explicacion="Se busca tendencia alcista")

        agregar_razon_financiera(df_anual_filtrado, 'Gross Profit', 'Gross Profit(%)', 'Revenue', como_porcentaje=True,calculo="Gross profit/sales",explicacion="* Un porcentaje mayor a 40% indica cierta ventaja\n* Porcentajes menores a 40% en un sector significa demasiada competencia y algo menor al 20% en una industria indica dificultad de crear ventaja")

        agregar_razon_financiera(df_anual_filtrado, 'Operating Income', 'Operating Margin(%)', 'Revenue', como_porcentaje=True,calculo="Operating profit/sales",explicacion="Se busca tendencia alcista o estable")

        agregar_razon_financiera(df_anual_filtrado, 'Net Income', 'EPS', 'Shares Outstanding (Diluted Average)', como_porcentaje=False,calculo="Net Income/Shares",explicacion="Se busca tendencia a la alza en los ultimos 5 0 10 años")

        agregar_razon_financiera(df_anual_filtrado, 'Revenue', 'Revenue Per Share', 'Shares Outstanding (Diluted Average)', como_porcentaje=False,calculo="Revenue/Shares",explicacion="Se busca tendencia alcista")

        agregar_fila(df_anual_filtrado, 'Shares Outstanding (Diluted Average)', '# Shares',calculo="",explicacion="Se busca tendencia bajista o que no suba")

        agregar_fila(df_anual_filtrado, 'Revenue', 'Sales',calculo="",explicacion="Se busca tendencia alcista")

        agregar_crecimiento_anual('Net Income', 'Net Income Growth',calculo="Crecimiento vs año pasado",explicacion="Se busca porcentajes estables o en crecimiento")

        agregar_crecimiento_anual('Sales', 'Sales Growth',calculo="Crecimiento vs año pasado",explicacion="Se busca porcentajes estables o en crecimiento")

        agregar_fila(df_anual_filtrado, 'Cost of Goods Sold', 'Cost of Goods Sold',calculo="",explicacion="Se busca tendencia bajista o que incrementen menos que las sales")

        agregar_crecimiento_anual('Cost of Goods Sold', 'Cost of Goods Sold Growth',calculo="Crecimiento vs año pasado",explicacion="Se busca que crezca a menor porcentaje que las Sales")

        agregar_fila(df_anual_filtrado, 'Total Inventories', 'Inventories' , calculo="",explicacion="se busca crecimiento estable")

        agregar_crecimiento_anual('Inventories', 'Inventories Growth',calculo="Crecimiento vs año pasado",explicacion="Se busca crecimiento estable")

        dividir_filas_razones_financieras("Cost of Goods Sold","Inventories","Inventory Turnover Ratio",False,calculo="Cost of Goods Sold / Inventories",explicacion="*Un valor mayor a 8 indica excelencia\n *Un valor entre 4 y 8 indica rango saludable\n*Menor a 4 indica baja rotación")


        agregar_fila(df_anual_filtrado, 'Dividends per Share', 'Dividends per Share',calculo="",explicacion="Buscar tendencia alcista")

        agregar_fila(df_anual_filtrado, 'Free Cash Flow', 'Free Cash Flow',calculo="",explicacion="Buscar una tendencia alcista")

        dividir_filas_razones_financieras('Free Cash Flow', 'Sales', 'Free cash flow to sales(%)',True,calculo="FCF/Sales",explicacion="Si el porcentaje da algo en torno al 15% puede indicar un foso económico")

        dividir_filas_razones_financieras('Free Cash Flow','# Shares','Free cash flow per share',False,calculo="FCF/Shares",explicacion="Se busca tendencia alcista")

        agregar_razon_financiera(df_anual_filtrado,'Free Cash Flow','Free Cash Flow to Debt ratio','Short-Term Debt & Capital Lease Obligation','Long-Term Debt & Capital Lease Obligation',como_porcentaje=False,calculo="FCF/Total Debt",explicacion="Entre más cerca de 1 mejor")


        agregar_razon_financiera(df_anual_filtrado,'Free Cash Flow','FCF/DEBT corto plazo','Short-Term Debt & Capital Lease Obligation',como_porcentaje=False,calculo="FCF/DEBT corto plazo",explicacion="Entre más cerca o alejado de 1 mejor")

        dividir_filas_razones_financieras('Dividends per Share',"EPS",'Dividend Payout Ratio(%)',True,calculo="Dividend earnings per share/ earnings per share",explicacion="Buscar empresas que tenga un ratio de entre 20 y 60%")

        agregar_razon_financiera(df_anual_filtrado,'Net Income','net worth to long-term debt ratio','Long-Term Debt & Capital Lease Obligation',como_porcentaje=False,calculo="Net income/ Long Term Debt",explicacion="Igual a 1 esta bien, pero mayor a 3 indica ventaja competitiva")

        agregar_razon_financiera(df_anual_filtrado,'Total Liabilities','Pasivo/Fondos Propios','Total Equity',como_porcentaje=False,calculo="total liabilities/total equity",explicacion="Si algo es menor a 1 es mejor\n* Para las financiera un relación menor a .80 es una ventaja competitiva")

        agregar_razon_financiera(df_anual_filtrado,'Total Current Assets','Current Ratio','Total Current Liabilities',como_porcentaje=False,explicacion="*En teoría algo mayor a 1 indica solvencia, pero existen empresas con algo menor a 1 que debido a su rentabilidad pueden cubrir el pasivo\n*Algo mayor a 1.5 puede ser muy bueno\n*evitar aquellas menores a .5")

        agregar_razon_financiera(df_anual_filtrado,'Long-Term Debt & Capital Lease Obligation','long-term debt-to-equity(%)','Total Equity',como_porcentaje=True,calculo="Long term debt/equity",explicacion="Se busca un balance de 75% capital, 25% deuda\nSe busca resultados menores a 25%")

        agregar_razon_financiera(df_anual_filtrado,'  Interest Expense','Gasto financiero(%)','Operating Income',como_porcentaje=True,calculo="net interest income(expenses)/operating income",explicacion="* Un gasto menor a 15% indica una ventaja\n* En el area financiera un porcentaje bajo puede ser un 30%\n*En cualquier industria la empresa con la proporción más baja tiene la ventaja") ##Interes Expense viene negativo, tenerlo en cuenta ya que si queda positivo seria malo ya que el operating income es tambien negativo

        agregar_razon_financiera(df_anual_filtrado,'Total Inventories','Inventory to current Assets(%)','Total Current Assets',como_porcentaje=True,calculo="inventories/current asset",explicacion="Buscar compañias con un rango menor al 40% y evitar empresas con algo mayor al 60%")

        agregar_fila(df_anual_filtrado,'Cash Conversion Cycle','Net Trading Cycle',calculo="Rotación de cuentas por cobrar + Rotación de inventarios - Rotación de cuentas por pagar",explicacion="Entre menor sea, mejor, buscar una tendencia bajista,un valor negativo es bueno siempre y cuando el revenue continue subiendo")

        agregar_fila(df_anual_filtrado,'PEG Ratio','PEGY Ratio',calculo="P/E ratio/ EPS growth rate+dividend yield",explicacion="*No es efectivo para empresas que pagan más de un 8% de dividendo,Buscar que sea menor a 1")

        agregar_fila(df_anual_filtrado,'PE Ratio','PER',calculo="Price* shares outstandings / net income",explicacion="* No invertir en acciones con PER promedio mayor a 25\n* PER menor a 9 es bueno y más una acción dentro de un indice\n*una acción se puede vender cuando ofrecer PER mayores a 40, sobre todo en empresas grandes\n*Cuando una empresa crece al mismo risto pero su PER promedio baja puede ser interesante")

        agregar_fila(df_anual_filtrado,'PS Ratio','P/S Ratio',calculo="market cap / sales",explicacion="*Se usa en empresas con perdidas temporales\n* solo usarlo para comparar entre la misma empresa\n*si el ratio es bajo con respecto a su promedio historico podria ser buena opción de compra\n*Entre mayor sea indica que los inversionistas estan dispuestos a pagar más por cada venta y por ende aumentara el precio de la accion")

        agregar_razon_financiera(df_anual_filtrado,'  Accounts Receivable','Receivable to Current Assets(%)','Total Current Assets',como_porcentaje=True,calculo="accounts receivable/current asset",explicacion="Buscar compañias con un rango menor al 40% y evitar empresas con algo mayor al 60%")

        agregar_fila(df_anual_filtrado,'ROA %','ROA%',calculo="net income 2020/((total assets 2019+total assets 2020)/2)",explicacion="* Una empresa no financiera que genere un ROA del 7% es buena\n* Un ROA mayor al 20% es Excelente")

        agregar_fila(df_anual_filtrado,'ROE %','ROE%',calculo="net income 2020/((shareholders equity 2019+shareholders equity 2020)/2)",explicacion="*Un ROE mayor a 15% es bueno si es mayor al 20% puede indicar un gran foso\n* Las financieras se debe buscar algo mayor al 12%")

        agregar_razon_financiera(df_anual_filtrado,'Total Assets','ROB','Total Equity',como_porcentaje=False,calculo="Total assets 2020/ ((shareholders equity 2019+shareholders equity 2020)/2)",explicacion="ratios mayores a 4.5 vuelve a las empresas riesgosas")

        agregar_fila(df_anual_filtrado,'ROIC %','ROIC %',calculo="Operating income * (1-tax rate %) / ((total assets - accounts payable y acrued expense - (cash, cash equivalents y marketable securities - max(0,total current liabilities - total current assets + cash,cash equivalents, marketable securities))",explicacion="Si es mayor a su WACC indica que genera más dinero que lo que paga por el\nSi tiene un ROIC mayor al 15% tiene una ventaja competitiva")

        agregar_fila(df_anual_filtrado,'WACC %','WACC %',calculo="",explicacion="Costo que tiene la obtencion del capital, entre menor sea mejor,debe ser menor al ROIC")

        agregar_razon_financiera_numerador(df_anual_filtrado,'Test de Acidez','Total Current Liabilities','Total Current Assets','Total Inventories',como_porcentaje=False, calculo="(Current assets-inventory)/current liabilities",explicacion="Un indice mayor a 1 coloca a la empresa en buena posición")

        agregar_fila(df_anual_filtrado,'Book Value per Share','Valor en libros',calculo="Stockholders equity - preferred stock / average shares outstanding",explicacion="*Comprar acciones que no pase su valor en 1.5\n* Mas util en financiera debido a lo activo de sus liquidos\n*Una empresa con un Valor en libros bajo, pero un ROE alto puede ser una ganga")

        agregar_fila(df_anual_filtrado,'Piotroski F-Score','Piotrivski F-Score',calculo="",explicacion="* Un buen score es en 7,8,9 sobre su estabilidad finaciera\n* las zonas grises esta entre 4,5,6\n* Mal o bajo score entre 0,1,2,3")

        agregar_fila(df_anual_filtrado,'Altman Z-Score','Altman Z score',calculo="",explicacion="*Algo menor a 1.8 es malo ya que indica que la empresa podria entrar en bancarrota en los proximos dos años\n* entre 1.8 y 3 es zona griss\n* mayor a 3 es zona segura e indica una alta fuerza financiera")

        agregar_fila(df_anual_filtrado,'Beneish M-Score','Beneish M-Score',calculo="",explicacion="* Menor a 1.78 indica que podrian manipular sus estados financieros.\n* Mayor a 1.78, podria indicar que no manipulan sus estados financieros")


        ratios_absolutos = [
            "Beneish M-Score",
            "Gasto financiero(%)",
        ]

        # Aplicar abs solo a columnas numéricas (desde la 3ra en adelante)
        razones_financieras.loc[ratios_absolutos, razones_financieras.columns[2:]] = (
            razones_financieras.loc[ratios_absolutos, razones_financieras.columns[2:]]
            .astype(float)
            .abs()
        )

        cols_numericas = razones_financieras.columns[2:]

        razones_financieras[cols_numericas] = (
            razones_financieras[cols_numericas]
            .apply(pd.to_numeric, errors="coerce")
        )

        # ## Book Value per Share

        total_assets = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Total Assets'].iloc[0, 1:]
        total_liabilities = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Total Liabilities'].iloc[0, 1:]
        total_shares = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Shares Outstanding (Basic Average)'].iloc[0, 1:]

        book_value = total_assets - total_liabilities

        book_value_per_share = book_value / total_shares

        book_value_per_share_anual = pd.DataFrame({
            'Book Value': book_value,
            'Book Value per Share': book_value_per_share
        }, index=total_assets.index)


        # ## Liquidation Value

        # Utilizable con empresas a la baja, si el precio se encuentra por debajo de este,podria ser una oportunidad

        # 1️⃣ Ratio de Recuperación del Efectivo (
        # 𝑅
        # 𝐸
        # R 
        # E
        # ​
        #  )
        # (Normalmente 100%)
        # Se incluyen todas las cuentas que representan efectivo o equivalentes de efectivo, que son altamente líquidos.
        # 
        # Cuentas relevantes:
        # 
        # Cash And Cash Equivalents
        # Marketable Securities
        # Cash, Cash Equivalents, Marketable Securities (si está consolidado)
        # 2️⃣ Ratio de Recuperación de Cuentas por Cobrar (
        # 𝑅
        # 𝐶
        # R 
        # C
        # ​
        #  )
        # (Usualmente entre 70-90%)
        # Se incluyen todas las cuentas por cobrar, notas por cobrar y otros montos adeudados a la empresa.
        # 
        # Cuentas relevantes:
        # 
        # Accounts Receivable
        # Notes Receivable
        # Loans Receivable
        # Other Current Receivables
        # Total Receivables (si está consolidado)
        # 3️⃣ Ratio de Recuperación de Inventarios (
        # 𝑅
        # 𝐼
        # R 
        # I
        # ​
        #  )
        # (Suele ser 50-80%)
        # Incluye todos los bienes en inventario que la empresa posee, como materia prima, productos en proceso y productos terminados.
        # 
        # Cuentas relevantes:
        # 
        # Inventories, Raw Materials & Components
        # Inventories, Work In Process
        # Inventories, Finished Goods
        # Inventories, Other
        # Total Inventories (si está consolidado)
        # 4️⃣ Ratio de Recuperación de Propiedades, Planta y Equipos (
        # 𝑅
        # 𝑃
        # R 
        # P
        # ​
        #  )
        # (Usualmente 60-90%)
        # Incluye activos fijos tangibles como edificios, maquinaria y terrenos.
        # 
        # Cuentas relevantes:
        # 
        # Land And Improvements
        # Buildings And Improvements
        # Machinery, Furniture, Equipment
        # Construction In Progress
        # Other Gross PPE
        # Gross Property, Plant and Equipment
        # Property, Plant and Equipment (si está consolidado)
        # ⚠️ Acumulated Depreciation → Se resta porque representa la pérdida de valor de los activos.
        # 5️⃣ Ratio de Recuperación de Otros Activos Tangibles (
        # 𝑅
        # 𝑂
        # R 
        # O
        # ​
        #  )
        # (Depende del tipo de activo, entre 10-80%)
        # Incluye otros activos físicos que no encajan en las categorías anteriores, como infraestructura, vehículos y mobiliario.
        # 
        # Cuentas relevantes:
        # 
        # Investments And Advances (si contiene activos tangibles)
        # Other Long Term Assets (si son tangibles)
        # Otros activos que no sean intangibles o Goodwill
        # ⚠️ No se incluyen:
        # 
        # Intangible Assets (valor de marca, patentes, etc.)
        # Goodwill (ya que en liquidación normalmente no tiene valor)

        ratio_recuperacion_efectivo = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Cash, Cash Equivalents, Marketable Securities'].iloc[0, 1:] * 0.95

        ratio_recuperacion_cc = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Total Receivables'].iloc[0, 1:] * 0.75

        ratio_recuperacion_inv = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Total Inventories'].iloc[0, 1:] * 0.60

        ratio_recuperacion_ppe = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Property, Plant and Equipment'].iloc[0, 1:] * 0.70

        ratio_recuperacion_act_tangibles =df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Investments And Advances'].iloc[0, 1:] + df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Other Long Term Assets'].iloc[0, 1:] *.30

        total_liabilities = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Total Liabilities'].iloc[0, 1:]

        liquidation_value = ratio_recuperacion_efectivo + ratio_recuperacion_cc + ratio_recuperacion_inv + ratio_recuperacion_ppe + ratio_recuperacion_act_tangibles - total_liabilities

        liquidation_value_per_share = liquidation_value / total_shares


        # ## EPV

        margen_operativo = (
            razones_financieras
                .loc["Operating Margin(%)"]
                .drop(["Calculo", "Explicacion"])
                .copy()
        )

        margen_operativo.index = margen_operativo.index.str.extract(r'(\d{4})').astype(int)[0]

        df_margen = margen_operativo.to_frame(name="Margen_Operativo")
        df_margen["Margen_Operativo"] = pd.to_numeric(df_margen["Margen_Operativo"], errors="coerce")

        df_margen = df_margen.sort_index()
        df_margen.index = df_margen.index.astype(int)

        # Promedio móvil de 5 años hacia atrás (excluye año actual)
        serie_promedios = (
            df_margen["Margen_Operativo"]
                .shift(1)                          
                .rolling(window=5, min_periods=1)
                .mean()
        )


        df_promedios_ebit = (
            serie_promedios
                .round(2)
                .div(100)                          
                .to_frame(name="Promedio_Margen_Operativo")
                .reset_index()
                .rename(columns={"index": "Año"})
        )

        ventas = (
            razones_financieras
                .loc["Sales"]
                .drop(["Calculo", "Explicacion"])
                .copy()
        )

        ventas.index = ventas.index.str.extract(r'(\d{4})').astype(int)[0]

        df_ventas = ventas.to_frame(name="Ventas")
        df_ventas["Ventas"] = pd.to_numeric(df_ventas["Ventas"], errors="coerce")

        df_ventas = df_ventas.sort_index()
        df_ventas.index = df_ventas.index.astype(int)

        serie_promedios = (
            df_ventas["Ventas"]
                .shift(1)                          
                .rolling(window=5, min_periods=1)
                .mean()
        )


        df_promedios_ventas = (
            serie_promedios
                .round(2)
                .to_frame(name="Promedio_Ventas")
                .reset_index()
                .rename(columns={"index": "Año"})
        )

        SGyA = df_trimestral_filtrado[df_trimestral_filtrado['Fiscal Period'] == 'Selling, General, & Admin. Expense'].iloc[0, 1:]
        SGyA.index = pd.to_datetime(SGyA.index, format="%b%Y")

        df_sgya = SGyA.astype(str).str.replace(",", "").astype(float).to_frame(name="SGyA")
        df_sgya["Año"] = df_sgya.index.year

        mes_map = {
            "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
            "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
            "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
        }

        headers_df = pd.DataFrame({"Header": valid_headers})
        headers_df["Mes"] = headers_df["Header"].str[:3].map(mes_map)
        headers_df["Año"] = headers_df["Header"].str[-4:].astype(int)

        # fecha base del cierre (primer día del mes del header)
        headers_df["Fecha_base"] = pd.to_datetime(
            headers_df["Año"].astype(str) + "-" + headers_df["Mes"].astype(str).str.zfill(2) + "-01"
        )

        # corte = 1 mes después del mes de cierre fiscal
        headers_df["Cutoff"] = headers_df["Fecha_base"] + pd.DateOffset(months=1)

        cutoff_por_anio = dict(zip(headers_df["Año"], headers_df["Cutoff"]))

        # 3) Años a calcular (sin filtro de 4 trimestres)
        anios = sorted(df_sgya["Año"].unique())
        ultimos_20_anios = anios[-20:]

        # 4) Promedios de los últimos 20 trimestres antes del cutoff fiscal de cada año
        promedios_sgya = {}
        for año in ultimos_20_anios:
            cutoff = cutoff_por_anio.get(año, pd.to_datetime(f"{año}-01-01"))  # fallback

            datos_previos = df_sgya[df_sgya.index < cutoff].tail(20)
            promedio = round((datos_previos["SGyA"] * 0.75).mean(), 2) if len(datos_previos) else 0
            promedios_sgya[año] = promedio

        df_promedios_sgya = (
            pd.DataFrame.from_dict(promedios_sgya, orient="index", columns=["Promedio_SG&A_ajustado"])
            .rename_axis("Año")
            .reset_index()
        )

        # Asegurar que la primera columna se llame "Año"
        df_promedios_ventas = df_promedios_ventas.rename(
            columns={df_promedios_ventas.columns[0]: "Año"}
        ).sort_values("Año").reset_index(drop=True)

        df_promedios_ebit = df_promedios_ebit.rename(
            columns={df_promedios_ebit.columns[0]: "Año"}
        ).sort_values("Año").reset_index(drop=True)

        df_promedios_sgya = df_promedios_sgya.rename(
            columns={df_promedios_sgya.columns[0]: "Año"}
        ).sort_values("Año").reset_index(drop=True)


        # Extraer columnas
        ventas = df_promedios_ventas["Promedio_Ventas"]
        margen = df_promedios_ebit["Promedio_Margen_Operativo"]
        sgya = df_promedios_sgya["Promedio_SG&A_ajustado"]

        # Calcular EBIT normalizado
        ebit_normalizado = round((ventas * margen) + sgya, 2)


        df_ebit_normalizado = pd.DataFrame({
            "Año": df_promedios_ventas["Año"],
            "EBIT_normalizado": ebit_normalizado
        })

        tax_rate = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Tax Rate %'].iloc[0, 1:]

        tax_rate.index = tax_rate.index.str.extract(r'(\d{4})').astype(int)[0]

        df_tax = tax_rate.to_frame(name="Tax_Rate")
        df_tax["Tax_Rate"] = pd.to_numeric(df_tax["Tax_Rate"], errors="coerce")

        promedios_tax = {}
        for año in ultimos_20_anios:
            ultimos_5 = df_tax[df_tax.index < año].tail(5)
            positivos = ultimos_5[ultimos_5["Tax_Rate"] >= 0]
            promedio = round(positivos["Tax_Rate"].mean(), 2) / 100
            promedios_tax[año] = promedio

        df_promedios_tax = pd.DataFrame.from_dict(promedios_tax, orient='index', columns=['Promedio_Tasa_Impuestos'])
        df_promedios_tax.index.name = 'Año'
        df_promedios_tax = df_promedios_tax.reset_index().fillna(0)

        df_ebit_normalizado = df_ebit_normalizado.sort_values("Año").reset_index(drop=True)
        df_promedios_tax = df_promedios_tax.sort_values("Año").reset_index(drop=True)

        ebit = df_ebit_normalizado["EBIT_normalizado"]
        tax = df_promedios_tax["Promedio_Tasa_Impuestos"]

        after_tax_ebit = ebit * (1 - tax)

        df_after_tax_ebit = pd.DataFrame({
            "Año": df_ebit_normalizado["Año"],
            "After_Tax_EBIT": after_tax_ebit.round(2)
        })


        DDA = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Depreciation, Depletion and Amortization'].iloc[0, 1:]

        DDA.index = DDA.index.str.extract(r'(\d{4})').astype(int)[0]

        df_dda = DDA.to_frame(name="DDA")
        df_dda["DDA"] = pd.to_numeric(df_dda["DDA"], errors="coerce")


        promedios_dda = {}
        for año in last_20_years:
            ultimos_5 = df_dda[df_dda.index < año].tail(5)
            promedio = round(ultimos_5["DDA"].mean(), 2)
            promedios_dda[año] = promedio

        df_promedios_dda = pd.DataFrame.from_dict(promedios_dda, orient='index', columns=['Promedio_DDA'])
        df_promedios_dda.index.name = 'Año'
        df_promedios_dda = df_promedios_dda.reset_index()

        df_promedios_dda = df_promedios_dda.sort_values("Año").reset_index(drop=True)
        df_promedios_tax = df_promedios_tax.sort_values("Año").reset_index(drop=True)

        dda = df_promedios_dda["Promedio_DDA"]
        tax = df_promedios_tax["Promedio_Tasa_Impuestos"]

        # Calcular Depreciación en exceso
        depreciacion_exceso = dda * 0.5 * tax

        df_depreciacion_exceso = pd.DataFrame({
            "Año": df_promedios_dda["Año"],
            "Depreciacion_en_exceso": depreciacion_exceso.round(2)
        })


        df_after_tax_ebit = df_after_tax_ebit.sort_values("Año").reset_index(drop=True)
        df_depreciacion_exceso = df_depreciacion_exceso.sort_values("Año").reset_index(drop=True)

        after_tax = df_after_tax_ebit["After_Tax_EBIT"]
        dep_exceso = df_depreciacion_exceso["Depreciacion_en_exceso"]

        # Calcular earnings normalizados
        normalized_earnings = after_tax + dep_exceso

        df_normalized_earnings = pd.DataFrame({
            "Año": df_after_tax_ebit["Año"],
            "Normalized_earnings": normalized_earnings.round(2)
        })

        accumulated_depreciation = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == '  Accumulated Depreciation'].iloc[0, 1:]
        gppe = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Gross Property, Plant and Equipment'].iloc[0, 1:]

        accumulated_depreciation.index = accumulated_depreciation.index.str.extract(r'(\d{4})').astype(int)[0]
        gppe.index = gppe.index.str.extract(r'(\d{4})').astype(int)[0]

        accumulated_depreciation = pd.to_numeric(accumulated_depreciation, errors='coerce').abs()
        gppe = pd.to_numeric(gppe, errors='coerce')

        # Unir en DataFrame
        df_ppe = pd.DataFrame({
            "Gross_PPE": gppe,
            "Accumulated_Depreciation": accumulated_depreciation
        })

        # Calcular Net PPE
        df_ppe["Net_PPE"] = df_ppe["Gross_PPE"] - df_ppe["Accumulated_Depreciation"]

        df_net_ppe = df_ppe.loc[ultimos_20_anios].copy()
        df_net_ppe["Año"] = df_net_ppe.index
        df_net_ppe = df_net_ppe.reset_index(drop=True)

        capex = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Capital Expenditure'].iloc[0, 1:]
        revenue = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Revenue'].iloc[0, 1:]

        capex.index = capex.index.str.extract(r'(\d{4})').astype(int)[0]
        revenue.index = revenue.index.str.extract(r'(\d{4})').astype(int)[0]

        capex = pd.to_numeric(capex, errors='coerce').abs()
        revenue = pd.to_numeric(revenue, errors='coerce')

        df_capex_revenue = pd.DataFrame({
            "Año": capex.index,
            "Capital_Expenditure": capex.values,
            "Revenue": revenue.values
        })

        df_capex_revenue = df_capex_revenue.sort_values("Año").reset_index(drop=True)

        df_capex_revenue["Crecimiento_Revenue"] = df_capex_revenue["Revenue"].pct_change()

        # Calcular el promedio de los 5 años anteriores para cada año
        promedios_crecimiento = {}
        for año in ultimos_20_anios:
            fila = df_capex_revenue[df_capex_revenue["Año"].between(año - 5, año - 1)]
            promedio = fila["Crecimiento_Revenue"].mean()
            promedios_crecimiento[año] = round(promedio, 4)

        df_promedio_crecimiento_revenue = pd.DataFrame.from_dict(
            promedios_crecimiento, orient='index', columns=["Promedio_Crecimiento_Revenue"]
        ).reset_index().rename(columns={"index": "Año"})

        df_net_ppe = df_net_ppe.sort_values("Año").reset_index(drop=True)
        df_capex_revenue = df_capex_revenue.sort_values("Año").reset_index(drop=True)
        df_promedio_crecimiento_revenue = df_promedio_crecimiento_revenue.sort_values("Año").reset_index(drop=True)

        df_inputs = df_capex_revenue.merge(df_net_ppe[["Año", "Net_PPE"]], on="Año")
        df_inputs = df_inputs.merge(df_promedio_crecimiento_revenue, on="Año")

        # 1. Calcular growth_capex solo si hay crecimiento positivo
        df_inputs["Growth_Capex"] = (df_inputs["Net_PPE"] / df_inputs["Revenue"]) * \
                                    (df_inputs["Promedio_Crecimiento_Revenue"] * df_inputs["Revenue"])
        df_inputs["Growth_Capex"] = df_inputs["Growth_Capex"].where(df_inputs["Promedio_Crecimiento_Revenue"] > 0, 0)

        # 2. Calcular mantenimiento preliminar
        df_inputs["Maintenance_Capex"] = df_inputs["Capital_Expenditure"] - df_inputs["Growth_Capex"]

        # 3. Si crecimiento fue negativo o resultado fue negativo, se usa todo el CAPEX
        df_inputs["Maintenance_Capex"] = df_inputs["Maintenance_Capex"].where(
            (df_inputs["Promedio_Crecimiento_Revenue"] > 0) & (df_inputs["Maintenance_Capex"] >= 0),
            df_inputs["Capital_Expenditure"]
        )

        df_maintenance_capex = df_inputs[["Año", "Maintenance_Capex"]].copy()

        maintenance_capex_promedio = round(df_maintenance_capex["Maintenance_Capex"], 2)

        # WACC=( 
        # V
        # E
        # ​
        #  ×r 
        # e
        # ​
        #  )+( 
        # V
        # D
        # ​
        #  ×r 
        # d
        # ​
        #  ×(1−t))
        #  

        total_shares.index = total_shares.index.str.extract(r'(\d{4})').astype(int)[0]

        df_total_shares = total_shares.to_frame(name="Total_Shares")

        df_total_shares["Total_Shares"] = pd.to_numeric(df_total_shares["Total_Shares"], errors="coerce")

        df_total_shares["Año"] = df_total_shares.index

        data_stock = pd.read_csv(archivo_stock + '.csv')
        data_stock['Fecha'] = pd.to_datetime(data_stock['Fecha'], format='%Y-%m-%d')
        data_stock['Cierre'] = data_stock['Cierre'].astype(str).str.replace(',', '').astype(float)
        data_stock = data_stock.dropna(subset=['Cierre'])
        data_stock["Año"] = data_stock["Fecha"].dt.year


        # Calcular promedio y mediana por año
        resumen_cierre = data_stock.groupby("Año")["Cierre"].agg(
            Promedio_Cierre="mean",
            Mediana_Cierre="median"
        ).reset_index()
        resumen_cierre


        resumen_cierre_filtrado = resumen_cierre[resumen_cierre["Año"].isin(ultimos_20_anios)].copy()
        df_total_shares = df_total_shares.sort_values("Año").reset_index(drop=True)

        precio_accion = (
            resumen_cierre_filtrado[["Año", "Promedio_Cierre", "Mediana_Cierre"]]
            .assign(Precio_Accion=lambda df: df[["Promedio_Cierre", "Mediana_Cierre"]].min(axis=1))
            [["Año", "Precio_Accion"]]
            .reset_index(drop=True)
        )

        df_total_shares = df_total_shares[["Año", "Total_Shares"]].copy()
        df_total_shares["Año"] = df_total_shares["Año"].astype(int)

        precio_accion = precio_accion.rename(columns={"Precio_Accion": "Precio_Accion_Min"}).copy()
        precio_accion["Año"] = precio_accion["Año"].astype(int)

        df_equity = df_total_shares.merge(precio_accion, on="Año", how="inner")

        df_equity["E"] = (df_equity["Total_Shares"] * df_equity["Precio_Accion_Min"]).round(2)

        Deuda_corto_plazo = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Short-Term Debt & Capital Lease Obligation'].iloc[0, 1:]
        Deuda_largo_plazo = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Long-Term Debt & Capital Lease Obligation'].iloc[0, 1:]

        Deuda_corto_plazo.index = Deuda_corto_plazo.index.str.extract(r'(\d{4})').astype(int)[0]
        df_deuda_cp = Deuda_corto_plazo.to_frame(name="Deuda_Corto_Plazo")
        df_deuda_cp["Deuda_Corto_Plazo"] = pd.to_numeric(df_deuda_cp["Deuda_Corto_Plazo"], errors="coerce")
        df_deuda_cp["Año"] = df_deuda_cp.index  # <-- esta línea es clave
        df_deuda_cp = df_deuda_cp.loc[ultimos_20_anios].reset_index(drop=True)

        Deuda_largo_plazo.index = Deuda_largo_plazo.index.str.extract(r'(\d{4})').astype(int)[0]
        df_deuda_lp = Deuda_largo_plazo.to_frame(name="Deuda_Largo_Plazo")
        df_deuda_lp["Deuda_Largo_Plazo"] = pd.to_numeric(df_deuda_lp["Deuda_Largo_Plazo"], errors="coerce")
        df_deuda_lp["Año"] = df_deuda_lp.index  # <-- también clave aquí
        df_deuda_lp = df_deuda_lp.loc[ultimos_20_anios].reset_index(drop=True)

        df_deuda_cp = df_deuda_cp.sort_values("Año").reset_index(drop=True)
        df_deuda_lp = df_deuda_lp.sort_values("Año").reset_index(drop=True)

        # Calcular deuda total (D)
        df_deuda_total = pd.DataFrame({
            "Año": df_deuda_cp["Año"],
            "Deuda_Total": df_deuda_cp["Deuda_Corto_Plazo"] + df_deuda_lp["Deuda_Largo_Plazo"]
        })


        df_crecimiento_syp = pd.DataFrame(crecimiento_syp_porcentaje_años)[['año_cierre', 'CAGR_%']]

        df_crecimiento_syp.columns = ['Año_Cierre', 'Crecimiento_IPC_%5_años']

        # Asegurar que las columnas clave para el merge sean iguales
        df_crecimiento_syp.columns = ['Año', 'Crecimiento_IPC']
        df_beta_resultado.columns = ['Año', 'Beta']
        promedio_bonos.columns = ['Año', 'CETES']

        # Unir los tres DataFrames por año
        df_r = df_crecimiento_syp.merge(df_beta_resultado, on='Año') \
                                 .merge(promedio_bonos, on='Año')

        # Calcular 'r' usando la fórmula
        df_r['r'] = df_r['CETES'] + df_r['Beta'] * (df_r['Crecimiento_IPC'] - df_r['CETES'])

        df_r["Cost_of_Equity"] = df_r["CETES"] + df_r["Beta"] * market_risk_premium

        df_r["Cost_of_Equity"] = df_r["Cost_of_Equity"].round(5)

        interest_expense = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == '  Interest Expense'].iloc[0, 1:].abs()

        interest_expense.index = interest_expense.index.str.extract(r'(\d{4})').astype(int)[0]

        df_interest_expense = interest_expense.to_frame(name="Interest_Expense")
        df_interest_expense["Año"] = df_interest_expense.index
        df_interest_expense["Interest_Expense"] = pd.to_numeric(df_interest_expense["Interest_Expense"], errors="coerce")

        df_interest_expense = (
            df_interest_expense
                .loc[ultimos_20_anios]
                .reset_index()
                .rename(columns={"index": "Año"})
        )

        # Asegurar orden y resetear índices
        df_interest_expense = df_interest_expense.sort_values("Año").reset_index(drop=True)
        df_deuda_total = df_deuda_total.sort_values("Año").reset_index(drop=True)

        # Calcular rd
        df_cost_of_debt = pd.DataFrame({
            "Año": df_interest_expense["Año"],
            "Cost_of_Debt": df_interest_expense["Interest_Expense"] / df_deuda_total["Deuda_Total"]
        })

        df_cost_of_debt["Cost_of_Debt"] = df_cost_of_debt["Cost_of_Debt"].round(5)

        df_tax.index = df_tax.index.astype(int)

        # Mover el índice a una columna 'Año'
        df_tax["Año"] = df_tax.index

        # Reiniciar índice y ordenar
        df_tax = df_tax.reset_index(drop=True).sort_values("Año")

        df_tax["Tax_Rate"] = pd.to_numeric(df_tax["Tax_Rate"], errors="coerce") / 100

        # Asegurar que todos los DataFrames estén alineados por Año y ordenados
        df_equity = df_equity.sort_values("Año").reset_index(drop=True)
        df_deuda_total = df_deuda_total.sort_values("Año").reset_index(drop=True)
        df_r = df_r.sort_values("Año").reset_index(drop=True)
        df_cost_of_debt = df_cost_of_debt.sort_values("Año").reset_index(drop=True)
        df_tax = df_tax.sort_values("Año").reset_index(drop=True)

        # Extraer columnas necesarias
        E = df_equity["E"]
        D = df_deuda_total["Deuda_Total"]
        cost_of_equity = df_r["Cost_of_Equity"]
        rd = df_cost_of_debt["Cost_of_Debt"]
        tax_rate = df_tax["Tax_Rate"]

        # Calcular WACC
        wacc = (E / (E + D)) * cost_of_equity + (D / (E + D)) * rd * (1 - tax_rate)

        df_wacc = pd.DataFrame({
            "Año": df_equity["Año"],
            "WACC": wacc.round(5)
        })

        df_wacc = df_wacc.dropna().reset_index(drop=True)

        ne = df_normalized_earnings[["Año", "Normalized_earnings"]].copy()
        mc = df_maintenance_capex[["Año", "Maintenance_Capex"]].copy()
        wa = df_wacc[["Año", "WACC"]].copy()

        for d in (ne, mc, wa):
            d["Año"] = d["Año"].astype(int)

        df_epv_base = (
            ne.merge(mc, on="Año", how="outer")
              .merge(wa, on="Año", how="outer")
              .sort_values("Año")
              .reset_index(drop=True)
        )

        df_epv_base["EPV_Business_Operation"] = np.where(
            (df_epv_base["WACC"].notna()) & (df_epv_base["WACC"] != 0),
            (df_epv_base["Normalized_earnings"] - df_epv_base["Maintenance_Capex"]) / df_epv_base["WACC"],
            np.nan
        )
        df_epv = df_epv_base[["Año", "EPV_Business_Operation"]].copy()
        df_epv["EPV_Business_Operation"] = df_epv["EPV_Business_Operation"].round(2)


        cash_and_equivalents = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Cash, Cash Equivalents, Marketable Securities'].iloc[0, 1:]

        cash_and_equivalents.index = cash_and_equivalents.index.str.extract(r'(\d{4})').astype(int)[0]

        df_cash = cash_and_equivalents.to_frame(name="Cash_and_Equivalents")

        df_cash["Cash_and_Equivalents"] = pd.to_numeric(df_cash["Cash_and_Equivalents"], errors="coerce")

        df_cash["Año"] = df_cash.index

        df_cash = df_cash[df_cash["Año"].isin(ultimos_20_anios)].reset_index(drop=True)

        df_epv = df_epv.sort_values("Año").reset_index(drop=True)
        df_cash = df_cash.sort_values("Año").reset_index(drop=True)
        df_deuda_total = df_deuda_total.sort_values("Año").reset_index(drop=True)
        df_total_shares = df_total_shares.sort_values("Año").reset_index(drop=True)

        epv_ops = df_epv["EPV_Business_Operation"]
        cash = df_cash["Cash_and_Equivalents"]
        deuda = df_deuda_total["Deuda_Total"]
        shares = df_total_shares["Total_Shares"]

        # Calcular EPV final por acción
        epv_final = (epv_ops + cash - deuda) / shares

        df_epv_final = pd.DataFrame({
            "Año": df_epv["Año"],
            "EPV_Final_Por_Accion": epv_final.round(2)
        })

        print(df_epv_final)

        # ## NET CURRENT ASSET VALUE

        # Mas usado para empresas con altos valores de current assets

        total_current_assets = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Total Current Assets'].iloc[0, 1:]
        total_liabilities = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Total Liabilities'].iloc[0, 1:]
        minority_interest = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Minority Interest'].iloc[0, 1:]
        prefered_stock = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Preferred Stock'].iloc[0, 1:]


        total_current_assets.index = total_current_assets.index.str.extract(r'(\d{4})').astype(int)[0]
        total_liabilities.index = total_liabilities.index.str.extract(r'(\d{4})').astype(int)[0]
        minority_interest.index = minority_interest.index.str.extract(r'(\d{4})').astype(int)[0]
        prefered_stock.index = prefered_stock.index.str.extract(r'(\d{4})').astype(int)[0]

        total_current_assets = pd.to_numeric(total_current_assets, errors='coerce')
        total_liabilities = pd.to_numeric(total_liabilities, errors='coerce')
        minority_interest = pd.to_numeric(minority_interest, errors='coerce')
        prefered_stock = pd.to_numeric(prefered_stock, errors='coerce')

        df_balance_resumen = pd.DataFrame({
            "Total_Current_Assets": total_current_assets,
            "Total_Liabilities": total_liabilities,
            "Minority_Interest": minority_interest,
            "Preferred_Stock": prefered_stock
        })

        df_balance_resumen["Año"] = df_balance_resumen.index
        df_balance_resumen = df_balance_resumen.reset_index(drop=True)

        df_balance_resumen = df_balance_resumen[df_balance_resumen["Año"].isin(ultimos_20_anios)]

        # Calcular Net Current Asset Value
        df_balance_resumen["Net_Current_Asset_Value"] = (
            df_balance_resumen["Total_Current_Assets"]
            - df_balance_resumen["Total_Liabilities"]
            - df_balance_resumen["Minority_Interest"]
            - df_balance_resumen["Preferred_Stock"]
        ).round(2)

        print(df_balance_resumen[["Año", "Net_Current_Asset_Value"]])

        # Asegurar orden
        df_balance_resumen = df_balance_resumen.sort_values("Año").reset_index(drop=True)
        df_total_shares = df_total_shares.sort_values("Año").reset_index(drop=True)

        # Calcular NCAV por acción
        ncav_per_share = df_balance_resumen["Net_Current_Asset_Value"] / df_total_shares["Total_Shares"]

        df_ncav_per_share = pd.DataFrame({
            "Año": df_balance_resumen["Año"],
            "NCAV_Per_Share": ncav_per_share.round(2)
        })

        # ## Tangicle Book Value

        total_equity = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Total Stockholders Equity'].iloc[0, 1:]
        prefered_stock = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Preferred Stock'].iloc[0, 1:]
        intagible_assets = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Intangible Assets'].iloc[0, 1:]

        total_equity.index = total_equity.index.str.extract(r'(\d{4})').astype(int)[0]
        prefered_stock.index = prefered_stock.index.str.extract(r'(\d{4})').astype(int)[0]
        intagible_assets.index = intagible_assets.index.str.extract(r'(\d{4})').astype(int)[0]



        total_equity = pd.to_numeric(total_equity, errors='coerce')
        prefered_stock = pd.to_numeric(prefered_stock, errors='coerce')
        intagible_assets = pd.to_numeric(intagible_assets, errors='coerce')

        df_equity_base = pd.DataFrame({
            "Total_Equity": total_equity,
            "Preferred_Stock": prefered_stock,
            "Intangible_Assets": intagible_assets
        })

        df_equity_base["Año"] = df_equity_base.index
        df_equity_base = df_equity_base.reset_index(drop=True)

        df_equity_base = df_equity_base[df_equity_base["Año"].isin(ultimos_20_anios)]

        # Calcular Tangible Book Value
        df_equity_base["Tangible_Book_Value"] = (
            df_equity_base["Total_Equity"] -
            df_equity_base["Preferred_Stock"] -
            df_equity_base["Intangible_Assets"]
        ).round(2)

        # Asegurar orden y reinicio de índice
        df_equity_base = df_equity_base.sort_values("Año").reset_index(drop=True)
        df_total_shares = df_total_shares.sort_values("Año").reset_index(drop=True)

        # Calcular valor por acción
        valor_por_accion = df_equity_base["Tangible_Book_Value"] / df_total_shares["Total_Shares"]

        df_tangible_book_value_per_share = pd.DataFrame({
            "Año": df_equity_base["Año"],
            "Tangible_Book_Value_Per_Share": valor_por_accion.round(2)
        })

        # ## Projected Free Cash Flow

        ebitda = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'EBITDA'].iloc[0, 1:]
        free_cash_flow = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Free Cash Flow'].iloc[0, 1:]
        revenue = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Revenue'].iloc[0, 1:]

        # --- Limpiar índice a años ---
        ebitda.index = ebitda.index.str.extract(r'(\d{4})').astype(int)[0]
        free_cash_flow.index = free_cash_flow.index.str.extract(r'(\d{4})').astype(int)[0]

        df_ebitda = ebitda.to_frame(name="EBITDA")
        df_ebitda["EBITDA"] = pd.to_numeric(df_ebitda["EBITDA"], errors="coerce")
        df_ebitda["Año"] = df_ebitda.index
        df_ebitda = df_ebitda.reset_index(drop=True)

        df_fcf = free_cash_flow.to_frame(name="Free_Cash_Flow")
        df_fcf["Free_Cash_Flow"] = pd.to_numeric(df_fcf["Free_Cash_Flow"], errors="coerce")
        df_fcf["Año"] = df_fcf.index
        df_fcf = df_fcf.reset_index(drop=True)

        revenue.index = revenue.index.str.extract(r'(\d{4})').astype(int)[0]

        df_revenue = revenue.to_frame(name="Revenue")
        df_revenue["Revenue"] = pd.to_numeric(df_revenue["Revenue"], errors="coerce")
        df_revenue["Año"] = df_revenue.index
        df_revenue = df_revenue.reset_index(drop=True)

        def crecimiento_5_anios(df, columna):
            df = df.sort_values("Año").reset_index(drop=True)
            resultados = []

            for i in range(5, len(df)):
                año = df.loc[i, "Año"]
                datos_previos = df.loc[i-5:i-1, columna]

                pct = datos_previos.pct_change()

                # eliminar inf, -inf y NaN
                pct = pct.replace([np.inf, -np.inf], np.nan).dropna()

                crecimiento = pct.mean() if not pct.empty else 0

                resultados.append({
                    "Año": año,
                    f"{columna}_crecimiento": round(crecimiento, 3)
                })

            return pd.DataFrame(resultados)


        df_ebitda_crecimiento = crecimiento_5_anios(df_ebitda, "EBITDA")
        df_fcf_crecimiento = crecimiento_5_anios(df_fcf, "Free_Cash_Flow")
        df_revenue_crecimiento = crecimiento_5_anios(df_revenue, "Revenue")

        df_crecimientos = df_ebitda_crecimiento \
            .merge(df_fcf_crecimiento, on="Año") \
            .merge(df_revenue_crecimiento, on="Año")

        def calcular_cagr_por_año(df, columna):
            df = df.sort_values("Año").reset_index(drop=True)
            resultados = []

            for i in range(5, len(df)):
                año_final = df.loc[i, "Año"]
                valor_inicial = df.loc[i - 5, columna]
                valor_final = df.loc[i, columna]

                if valor_inicial > 0 and valor_final > 0:
                    cagr = (valor_final / valor_inicial) ** (1/5) - 1
                else:
                    cagr = 0

                resultados.append({
                    "Año": año_final,
                    f"CAGR_{columna}": round(cagr, 3)
                })

            return pd.DataFrame(resultados)

        df_cagr_ebitda = calcular_cagr_por_año(df_ebitda, "EBITDA")
        df_cagr_fcf = calcular_cagr_por_año(df_fcf, "Free_Cash_Flow")
        df_cagr_revenue = calcular_cagr_por_año(df_revenue, "Revenue")

        df_cagr_todo = df_cagr_ebitda \
            .merge(df_cagr_fcf, on="Año") \
            .merge(df_cagr_revenue, on="Año")


        df_crecimientos_final = df_crecimientos.merge(df_cagr_todo, on="Año")

        # Definir columnas numéricas a evaluar
        columnas_crecimiento = [col for col in df_crecimientos_final.columns if col != "Año"]

        # Calcular el valor mínimo válido por fila
        valores_filtrados = []
        for _, fila in df_crecimientos_final.iterrows():
            valores_validos = [
                fila[col] for col in columnas_crecimiento
                if isinstance(fila[col], (int, float)) and 0.04 <= fila[col] <= 0.11
            ]
            valor_final = min(valores_validos) if valores_validos else 0.05
            valores_filtrados.append(round(valor_final, 3))

        df_min_crecimiento = pd.DataFrame({
            "Año": df_crecimientos_final["Año"],
            "Crecimiento_Seleccionado": valores_filtrados
        })

        # Calcular growth_assumption y growth_multiple
        df_min_crecimiento["Growth_Assumption"] = df_min_crecimiento["Crecimiento_Seleccionado"] * 100
        df_min_crecimiento["Growth_Multiple"] = 8.3459 * (1.07 ** (df_min_crecimiento["Growth_Assumption"] - 4))

        df_min_crecimiento["Growth_Assumption"] = df_min_crecimiento["Growth_Assumption"].round(2)
        df_min_crecimiento["Growth_Multiple"] = df_min_crecimiento["Growth_Multiple"].round(2)

        df_fcf = free_cash_flow.to_frame(name="Free_Cash_Flow")

        # Asegurar que los valores sean numéricos
        df_fcf["Free_Cash_Flow"] = pd.to_numeric(df_fcf["Free_Cash_Flow"], errors="coerce")

        # Crear columna 'Año' desde el índice 
        df_fcf["Año"] = df_fcf.index

        # Resetear índice
        df_fcf = df_fcf.reset_index(drop=True)

        # Asegurar orden por año
        df_fcf = df_fcf.sort_values("Año").reset_index(drop=True)

        promedios_fcf = []

        # Calcular promedio de los 5 años anteriores para cada año
        for i in range(5, len(df_fcf)):
            año = df_fcf.loc[i, "Año"]
            valores_previos = df_fcf.loc[i-5:i-1, "Free_Cash_Flow"]
            promedio = round(valores_previos.mean(), 2)
            promedios_fcf.append({"Año": año, "FCF_5y_Promedio": promedio})

        df_fcf_5y_promedio = pd.DataFrame(promedios_fcf)

        free_cash_flow_4trimestres = df_trimestral_filtrado[df_trimestral_filtrado['Fiscal Period'] == 'Free Cash Flow'].iloc[0, 1:]

        # Asegurar que la Serie tenga su índice correctamente
        free_cash_flow_4trimestres.index.name = "Periodo"  #

        df_fcf_trim = free_cash_flow_4trimestres.to_frame(name="FCF_4T").reset_index()

        # Extraer el año del índice 'Periodo'
        df_fcf_trim["Año"] = df_fcf_trim["Periodo"].str.extract(r'(\d{4})').astype(int)

        df_fcf_trim["FCF_4T"] = pd.to_numeric(df_fcf_trim["FCF_4T"], errors="coerce")

        # Agrupar por año y obtener promedio
        df_fcf_anual_promedio = df_fcf_trim.groupby("Año")["FCF_4T"].mean().reset_index()
        df_fcf_anual_promedio = df_fcf_anual_promedio.rename(columns={"FCF_4T": "FCF_Promedio_Anual_4T"})
        df_fcf_anual_promedio["FCF_Promedio_Anual_4T"] = df_fcf_anual_promedio["FCF_Promedio_Anual_4T"].round(2)

        # Asegurar que el índice sea string y contenga el año
        total_stockholders_equity = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Total Stockholders Equity'].iloc[0, 1:]

        total_stockholders_equity.index.name = "Periodo"

        # Convertir a DataFrame
        df_total_equity = total_stockholders_equity.to_frame(name="Total_Stockholders_Equity").reset_index()

        # Extraer el año de 'Periodo'
        df_total_equity["Año"] = df_total_equity["Periodo"].astype(str).str.extract(r'(\d{4})').astype(int)

        # Convertir valores a numérico
        df_total_equity["Total_Stockholders_Equity"] = pd.to_numeric(
            df_total_equity["Total_Stockholders_Equity"], errors="coerce"
        )

        # Limpiar el DataFrame final
        df_total_equity = df_total_equity[["Año", "Total_Stockholders_Equity"]]

        # Asegurar que ambas tablas estén ordenadas y listas
        df_fcf_5y_promedio = df_fcf_5y_promedio.sort_values("Año").reset_index(drop=True)
        df_fcf_anual_promedio = df_fcf_anual_promedio.sort_values("Año").reset_index(drop=True)

        # Hacer merge solo donde haya coincidencia de años
        df_fcf_ajustado = df_fcf_5y_promedio.merge(df_fcf_anual_promedio, on="Año", how="inner")

        # Aplicar la fórmula
        df_fcf_ajustado["FCF_Ajustado"] = (
            (6 * df_fcf_ajustado["FCF_5y_Promedio"] + 0.75 * df_fcf_ajustado["FCF_Promedio_Anual_4T"]) / 6.75
        ).round(2)

        df_resultados_inf_usa["Tasa de Inflación"] = pd.to_numeric(
            df_resultados_inf_usa["Tasa de Inflación"], errors="coerce"
        )

        # Calcular el factor de inflación a 3 años para cada año
        df_resultados_inf_usa["Factor_Inflacion"] = (
            (1 + df_resultados_inf_usa["Tasa de Inflación"]) ** 3
        ).round(4)

        df_fcf_ajustado = df_fcf_ajustado.sort_values("Año").reset_index(drop=True)
        df_resultados_inf_usa = df_resultados_inf_usa.sort_values("Año").reset_index(drop=True)

        df_fcf_ajustado_inflacion = df_fcf_ajustado.merge(
            df_resultados_inf_usa[["Año", "Factor_Inflacion"]],
            on="Año",
            how="inner"
        )

        # Calcular FCF ajustado con inflación
        df_fcf_ajustado_inflacion["FCF_Ajustado_Inflacion"] = (
            df_fcf_ajustado_inflacion["FCF_Ajustado"] * df_fcf_ajustado_inflacion["Factor_Inflacion"]
        ).round(2)

        df_min_crecimiento = df_min_crecimiento.sort_values("Año").reset_index(drop=True)
        df_fcf_ajustado_inflacion = df_fcf_ajustado_inflacion.sort_values("Año").reset_index(drop=True)
        df_total_equity = df_total_equity.sort_values("Año").reset_index(drop=True)
        df_total_shares = df_total_shares.sort_values("Año").reset_index(drop=True)

        # Unir todos por año
        df_intrinsic = df_min_crecimiento.merge(
            df_fcf_ajustado_inflacion[["Año", "FCF_Ajustado_Inflacion"]], on="Año", how="inner"
        ).merge(
            df_total_equity[["Año", "Total_Stockholders_Equity"]], on="Año", how="inner"
        ).merge(
            df_total_shares[["Año", "Total_Shares"]], on="Año", how="inner"
        )

        # Aplicar fórmula
        df_intrinsic["Intrinsic_Value"] = (
            (df_intrinsic["Growth_Multiple"] * df_intrinsic["FCF_Ajustado_Inflacion"] +
             0.7 * df_intrinsic["Total_Stockholders_Equity"]) /
            df_intrinsic["Total_Shares"]
        ).round(2)

        print(df_intrinsic[["Año", "Intrinsic_Value"]])


        # ## Median PS value


        revenue_serie = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Revenue'].iloc[0, 1:]
        revenue_serie.index = revenue_serie.index.astype(str)

        revenue_serie = pd.to_numeric(revenue_serie, errors='coerce').dropna()

        revenue_serie.index = [int(str(i)[-4:]) for i in revenue_serie.index]

        shares_serie = df_anual_filtrado[
            df_anual_filtrado['Fiscal Period'] == 'Shares Outstanding (Basic Average)'
        ].iloc[0, 1:]
        shares_serie.index = shares_serie.index.astype(str)

        shares_serie = pd.to_numeric(shares_serie, errors='coerce').dropna()

        shares_serie.index = [int(str(i)[-4:]) for i in shares_serie.index]

        revenue_per_share = revenue_serie / shares_serie

        data_stock['Fecha'] = pd.to_datetime(data_stock['Fecha'], format='%d.%m.%Y')

        data_stock = data_stock.sort_values('Fecha')

        # Convertir la columna 'Cierre' a tipo numérico, eliminando caracteres no válidos
        data_stock['Cierre'] = data_stock['Cierre'].astype(str).str.replace(',', '').astype(float)

        # Verificar valores nulos y eliminarlos
        data_stock = data_stock.dropna(subset=['Cierre'])
        data_stock['Año'] = data_stock['Fecha'].dt.year
        promedio_cierre_por_anio = data_stock.groupby('Año')['Cierre'].mean()
        mediana_cierre_por_anio = data_stock.groupby('Año')['Cierre'].median()


        ratio_ps_anual_promedio = promedio_cierre_por_anio / revenue_per_share
        ratio_ps_anual_mediana = mediana_cierre_por_anio / revenue_per_share

        ratio_ps_anual_promedio = ratio_ps_anual_promedio.dropna()
        ratio_ps_anual_mediana = ratio_ps_anual_mediana.dropna()

        ratio_ps_anual_promedio = ratio_ps_anual_promedio.sort_index()
        ratio_ps_anual_mediana  = ratio_ps_anual_mediana.sort_index()

        ratio_ps_anual_promedio.index = ratio_ps_anual_promedio.index.astype(int)
        ratio_ps_anual_mediana.index  = ratio_ps_anual_mediana.index.astype(int)

        # Mediana móvil 10 años (incluye el año actual)
        df_mediana_10y_promedio = (
            ratio_ps_anual_promedio
                .rolling(window=10, min_periods=1)
                .median()
                .dropna()
        )

        df_mediana_10y_mediana = (
            ratio_ps_anual_mediana
                .rolling(window=10, min_periods=1)
                .median()
                .dropna()
        )


        Median_ps_value_promedio = df_mediana_10y_promedio * revenue_per_share

        Median_ps_value_promedio_mediana = df_mediana_10y_mediana * revenue_per_share

        Median_ps_value_promedio = Median_ps_value_promedio.dropna()
        Median_ps_value_promedio_mediana = Median_ps_value_promedio_mediana.dropna()

        # ## Graham Number

        eps_without_nri = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'EPS without NRI'].iloc[0, 1:]

        df_tangible_book_value_per_share = df_tangible_book_value_per_share.astype(float)
        eps_without_nri = eps_without_nri.astype(float)

        eps_without_nri.index = (
            eps_without_nri.index.astype(str)
            .str.extract(r'(\d{4})')[0]
            .astype(int)
        )

        df_eps = eps_without_nri.to_frame(name="EPS")
        df_eps["Año"] = df_eps.index

        # Reordenar columnas
        df_eps = df_eps[["Año", "EPS"]].reset_index(drop=True)


        df_tangible_book_value_per_share["Año"] = df_tangible_book_value_per_share["Año"].astype(int)
        df_tangible_book_value_per_share["Tangible_Book_Value_Per_Share"] = pd.to_numeric(
            df_tangible_book_value_per_share["Tangible_Book_Value_Per_Share"], errors="coerce"
        )

        df_eps["Año"] = df_eps["Año"].astype(int)
        df_eps["EPS"] = pd.to_numeric(df_eps["EPS"], errors="coerce")

        df_graham = df_tangible_book_value_per_share.merge(df_eps, on="Año", how="inner")

        # Calcular Graham Number por año
        df_graham["Graham_Number"] = np.where(
            df_graham["EPS"] > 0,
            np.sqrt(22.5 * df_graham["Tangible_Book_Value_Per_Share"] * df_graham["EPS"]),
            0
        )

        df_graham = df_graham[["Año", "Graham_Number"]].reset_index(drop=True)


        # ## Peter Lynch Fair Value

        # El Valor Justo según Peter Lynch se aplica a empresas en crecimiento. El rango ideal para la tasa de crecimiento es entre 10% y 20% anual.
        # 
        # Peter Lynch considera que el valor justo del P/E (relación precio/utilidad) para una empresa en crecimiento es igual a su tasa de crecimiento, es decir, que el PEG = 1.
        # 
        # Las ganancias utilizadas en este cálculo son las del último año (TTM – trailing twelve months).
        # 
        # Para empresas que no son bancos, la tasa de crecimiento que se usa es el promedio de crecimiento del EBITDA por acción en los últimos 5 años.
        # 
        # Para bancos, se usa el promedio de crecimiento del Valor en Libros por acción en los últimos 5 años.
        # 
        # Si la tasa de crecimiento a 5 años es mayor al 25% anual, se limita a 25%.
        # Si la tasa de crecimiento a 5 años es menor al 5% anual, no se calcula el Valor Justo de Peter Lynch.

        peg_ratio = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'PEG Ratio'].iloc[0, 1:]
        ebitda5anios = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'EBITDA'].iloc[0, 1:]


        ebitda5anios = ebitda5anios.sort_index()

        # Crecimiento promedio móvil de 5 años (en %)
        crecimiento_5y = (
            pd.to_numeric(ebitda5anios, errors="coerce")
              .pct_change()
              .rolling(window=5, min_periods=1)
              .mean()
              .round(3)
              * 100
        )

        # Convertir índice DecYYYY -> año y dejarlo como índice
        anios = pd.to_datetime(crecimiento_5y.index.astype(str), format="%b%Y").year
        df_crecimiento_ebitda_5y = crecimiento_5y.copy()
        df_crecimiento_ebitda_5y.index = anios
        df_crecimiento_ebitda_5y.index.name = "Año"

        # DataFrame final (índice = Año)
        df_crecimiento_ebitda_5y = df_crecimiento_ebitda_5y.to_frame(name="Crecimiento_EBITDA_5Y").dropna()

        eps_without_nri = pd.to_numeric(eps_without_nri, errors="coerce")
        df_crecimiento_ebitda_5y["Crecimiento_EBITDA_5Y"] = pd.to_numeric(
            df_crecimiento_ebitda_5y["Crecimiento_EBITDA_5Y"], errors="coerce"
        )

        df_peter = df_crecimiento_ebitda_5y.join(
            eps_without_nri.rename("EPS"),
            how="inner"
        )

        # Peter Lynch Value por año (1 * crecimiento * EPS)
        df_peter["Peter_Lynch_Value_1"] = 1 * df_peter["Crecimiento_EBITDA_5Y"] * df_peter["EPS"]

        df_peter = df_peter[["Peter_Lynch_Value_1"]]

        # Convertir PEG ratio a numérico
        peg_ratio = pd.to_numeric(peg_ratio, errors="coerce")

        # Pasar índice DecYYYY -> Año
        peg_ratio.index = pd.to_datetime(
            peg_ratio.index.astype(str),
            format="%b%Y"
        ).year

        # Unir crecimiento EBITDA + EPS + PEG ratio
        df_peter_2 = (
            df_crecimiento_ebitda_5y
                .join(eps_without_nri.rename("EPS"), how="inner")
                .join(peg_ratio.rename("PEG_Ratio"), how="inner")
        )

        # Calcular Peter Lynch Value 2
        df_peter_2["Peter_Lynch_Value_2"] = (
            df_peter_2["PEG_Ratio"]
            * df_peter_2["Crecimiento_EBITDA_5Y"]
            * df_peter_2["EPS"]
        )

        df_peter_2 = df_peter_2[["Peter_Lynch_Value_2"]]

        # ## DCF (FCF BASED)

        discount_rate = promedio_bonos.assign(
            Discount_Rate=promedio_bonos["CETES"] + market_risk_premium
        )[["Año", "Discount_Rate"]]

        fcf_per_share = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Free Cash Flow per Share'].iloc[0, 1:]
        growth_rates = fcf_per_share.pct_change().dropna()

        growth_rates = pd.to_numeric(growth_rates, errors="coerce").sort_index()

        # Mediana móvil: hasta 10 años hacia atrás (usa lo que haya)
        mediana_growth_10y = (
            growth_rates
                .rolling(window=10, min_periods=1)
                .median()
        )

        # Convertir índice DecYYYY -> Año
        mediana_growth_10y.index = pd.to_datetime(
            mediana_growth_10y.index.astype(str),
            format="%b%Y"
        ).year
        mediana_growth_10y.index.name = "Año"

        # Año inicial dinámico (primer año disponible)
        anio_inicio = mediana_growth_10y.index.min()

        df_mediana_growth_10y = (
            mediana_growth_10y
                .to_frame(name="Mediana_Growth_10Y")
                .loc[anio_inicio:]
        )


        # --- Limpiar growth_rates: DecYYYY -> Año (int) ---
        growth_rates = pd.to_numeric(growth_rates, errors="coerce")
        growth_rates.index = pd.to_datetime(
            growth_rates.index.astype(str),
            format="%b%Y"
        ).year
        growth_rates.index.name = "Año"

        free_cash_flow = pd.to_numeric(free_cash_flow, errors="coerce")
        if free_cash_flow.index.dtype != "int64" and free_cash_flow.index.dtype != "int32":
            free_cash_flow.index = pd.to_datetime(
                free_cash_flow.index.astype(str),
                format="%b%Y"
            ).year
        free_cash_flow.index.name = "Año"

        # --- Pesos: FCF del año anterior ---
        weights = free_cash_flow.shift(1)

        # --- Weighted growth móvil de 10 años (1 valor por año) ---
        weighted_growth_10y = (
            (growth_rates * weights).rolling(window=10, min_periods=1).sum()
            / weights.rolling(window=10, min_periods=1).sum()
        )

        df_weighted_growth_10y = weighted_growth_10y.to_frame(name="Weighted_Growth_10Y")

        # df_weighted_growth_10y
        df_weighted_growth_10y["Weighted_Growth_10Y"] = (
            df_weighted_growth_10y["Weighted_Growth_10Y"]
                .clip(lower=0.05, upper=0.25)
        )

        df_mediana_growth_10y["Mediana_Growth_10Y"] = (
            df_mediana_growth_10y["Mediana_Growth_10Y"]
                .clip(lower=0.05, upper=0.25)
        )

        def crecimiento_10_anios(df, columna):
            df = df.sort_values("Año").reset_index(drop=True).copy()
            df[columna] = pd.to_numeric(df[columna], errors="coerce")

            resultados = []
            for i in range(1, len(df)):
                año = int(df.loc[i, "Año"])

                inicio = max(0, i - 10)
                datos_previos = df.loc[inicio:i-1, columna]

                if len(datos_previos) >= 2:
                    pct = datos_previos.pct_change()

                    # quitar inf/-inf que salen por división entre 0, y NaN
                    pct = pct.replace([np.inf, -np.inf], np.nan).dropna()

                    crecimiento = pct.mean() if not pct.empty else 0

                    resultados.append({
                        "Año": año,
                        f"{columna}_crecimiento": round(float(crecimiento), 3)
                    })

            return pd.DataFrame(resultados)

        def calcular_cagr_por_año(df, columna, ventana_max=10, min_anios=2):
            df = df.sort_values("Año").reset_index(drop=True)
            resultados = []

            for i in range(1, len(df)):
                año_final = df.loc[i, "Año"]
                valor_final = df.loc[i, columna]

                inicio = max(0, i - ventana_max)

                j = inicio
                while j < i and (pd.isna(df.loc[j, columna]) or df.loc[j, columna] <= 0):
                    j += 1

                año_inicial_candidato = df.loc[inicio, "Año"]
                n_anios_min = año_final - año_inicial_candidato

                if n_anios_min < min_anios:
                    continue

                if pd.isna(valor_final) or valor_final <= 0 or j >= i:
                    cagr = 0
                else:
                    año_inicial = df.loc[j, "Año"]
                    valor_inicial = df.loc[j, columna]
                    n_anios = año_final - año_inicial

                    if n_anios < min_anios:
                        cagr = 0
                    else:
                        cagr = (valor_final / valor_inicial) ** (1 / n_anios) - 1

                resultados.append({"Año": año_final, f"CAGR_{columna}": round(float(cagr), 3)})

            return pd.DataFrame(resultados)


        df_fcf_crecimiento_10 = crecimiento_10_anios(df_fcf, "Free_Cash_Flow")
        df_cagr_fcf_10 = calcular_cagr_por_año(df_fcf, "Free_Cash_Flow")

        # df_fcf_crecimiento
        col = df_fcf_crecimiento_10.columns[1]
        df_fcf_crecimiento_10[col] = df_fcf_crecimiento_10[col].clip(lower=0.05, upper=0.25)

        # df_cagr_fcf
        col = df_cagr_fcf_10.columns[1]
        df_cagr_fcf_10[col] = df_cagr_fcf_10[col].clip(lower=0.05, upper=0.25)


        y1 = 10
        g2 = 0.04
        y2 = 10
        fcf_per_share = df_anual_filtrado[df_anual_filtrado['Fiscal Period'] == 'Free Cash Flow per Share'].iloc[0, 1:]

        df_y = discount_rate.copy()
        df_y["y"] = (1 + g2) / (1 + df_y["Discount_Rate"])

        df_y = df_y[["Año", "y"]]

        def calcular_x(df_g, df_discount):

            # --- Normalizar df_g a tener Año como columna ---
            df = df_g.copy()

            if "Año" not in df.columns:
                df = df.reset_index().rename(columns={df.index.name or "index": "Año"})

            # Tomar la columna de crecimiento (segunda columna)
            col_g = [c for c in df.columns if c != "Año"][0]

            df = df[["Año", col_g]]

            # --- Normalizar discount_rate ---
            df_d = df_discount.copy()
            df_d["Año"] = df_d["Año"].astype(int)

            # --- Merge por Año ---
            df_merge = df.merge(df_d, on="Año", how="inner")

            # --- Calcular x ---
            df_merge["x"] = (1 + df_merge[col_g]) / (1 + df_merge["Discount_Rate"])

            # --- Resultado final ---
            return df_merge[["Año", "x"]]


        x_weighted = calcular_x(df_weighted_growth_10y, discount_rate)
        x_mediana  = calcular_x(df_mediana_growth_10y, discount_rate)
        x_fcf_avg  = calcular_x(df_fcf_crecimiento_10, discount_rate)
        x_cagr_fcf = calcular_x(df_cagr_fcf_10, discount_rate)

        fcf_per_share = pd.to_numeric(fcf_per_share, errors="coerce")
        fcf_per_share.index = pd.to_datetime(fcf_per_share.index.astype(str), format="%b%Y").year
        fcf_per_share.index.name = "Año"

        df_fcf_per_share = fcf_per_share.to_frame(name="FCF_per_Share")

        df_y = df_y.copy()
        if "Año" in df_y.columns:
            df_y["Año"] = df_y["Año"].astype(int)
            df_y = df_y.set_index("Año")
        df_y.index.name = "Año"
        df_y["y"] = pd.to_numeric(df_y["y"], errors="coerce")

        # Función robusta: acepta df_x con Año como índice o columna 
        def calcular_intrinsic_value_fcf(df_x, df_y, df_fcf_per_share):
            dx = df_x.copy()

            # Si Año viene como columna, pasarlo a índice
            if "Año" in dx.columns:
                dx["Año"] = dx["Año"].astype(int)
                dx = dx.set_index("Año")
            dx.index.name = "Año"

            # Identificar columna de x (si solo hay una, toma esa)
            col_x = dx.columns[0]
            dx[col_x] = pd.to_numeric(dx[col_x], errors="coerce")

            # Unir por Año
            base = (
                df_fcf_per_share
                    .join(dx[[col_x]].rename(columns={col_x: "x"}), how="inner")
                    .join(df_y[["y"]], how="inner")
            )

            x = base["x"]
            y = base["y"]
            f = base["FCF_per_Share"]

            # Fórmula
            term1 = x * (1 - x**10) / (1 - x)
            term2 = (x**10) * y * (1 - y**10) / (1 - y)

            base["Intrinsic_Value_FCF"] = f * (term1 + term2)

            return base[["Intrinsic_Value_FCF"]]

        df_intrinsic_weighted = calcular_intrinsic_value_fcf(x_weighted, df_y, df_fcf_per_share)
        df_intrinsic_mediana  = calcular_intrinsic_value_fcf(x_mediana,  df_y, df_fcf_per_share)
        df_intrinsic_fcf_avg  = calcular_intrinsic_value_fcf(x_fcf_avg,  df_y, df_fcf_per_share)
        df_intrinsic_cagr_fcf = calcular_intrinsic_value_fcf(x_cagr_fcf, df_y, df_fcf_per_share)


        # ## DCF(Earnigs Based)

        growth_rates_eps = eps_without_nri.pct_change().dropna()

        growth_rates_eps = pd.to_numeric(growth_rates_eps, errors="coerce").sort_index()

        # Mediana móvil: hasta 10 años hacia atrás (usa lo que haya)
        mediana_growth_10y_eps = (
            growth_rates_eps
                .rolling(window=10, min_periods=1)
                .median()
        )

        # Año inicial dinámico (primer año disponible)
        anio_inicio = mediana_growth_10y_eps.index.min()

        df_mediana_growth_10y_eps = (
            mediana_growth_10y_eps
                .to_frame(name="Mediana_Growth_10Y_eps")
                .loc[anio_inicio:]
        )

        df_mediana_growth_10y_eps.index.name = "Año"

        # Asegurar free_cash_flow numérico (mismo índice por año)
        eps_without_nri = pd.to_numeric(eps_without_nri, errors="coerce")
        if eps_without_nri.index.dtype != "int64" and eps_without_nri.index.dtype != "int32":
            eps_without_nri.index = pd.to_datetime(
                eps_without_nri.index.astype(str),
                format="%b%Y"
            ).year
        eps_without_nri.index.name = "Año"

        # Pesos: FCF del año anterior 
        weights = eps_without_nri.shift(1)

        # Weighted growth móvil de 10 años (1 valor por año)
        weighted_growth_10y_eps = (
            (growth_rates_eps * weights).rolling(window=10, min_periods=1).sum()
            / weights.rolling(window=10, min_periods=1).sum()
        )

        # DataFrame final
        df_weighted_growth_10y_eps = weighted_growth_10y_eps.to_frame(name="Weighted_Growth_10Y_eps")

        # df_weighted_growth_10y
        df_weighted_growth_10y_eps["Weighted_Growth_10Y_eps"] = (
            df_weighted_growth_10y_eps["Weighted_Growth_10Y_eps"]
                .clip(lower=0.05, upper=0.20)
        )

        df_mediana_growth_10y_eps["Mediana_Growth_10Y_eps"] = (
            df_mediana_growth_10y_eps["Mediana_Growth_10Y_eps"]
                .clip(lower=0.05, upper=0.20)
        )

        df_eps_crecimiento_10 = crecimiento_10_anios(df_eps, "EPS")
        df_cagr_eps_10 = calcular_cagr_por_año(df_eps, "EPS")

        # df_fcf_crecimiento
        col = df_eps_crecimiento_10.columns[1]
        df_eps_crecimiento_10[col] = df_eps_crecimiento_10[col].clip(lower=0.05, upper=0.20)

        # df_cagr_fcf
        col = df_cagr_eps_10.columns[1]
        df_cagr_eps_10[col] = df_cagr_eps_10[col].clip(lower=0.05, upper=0.20)

        y1 = 10
        g2 = 0.04
        y2 = 10


        df_weighted_growth_10y_eps_x = calcular_x(df_weighted_growth_10y_eps, discount_rate)
        df_mediana_growth_10y_eps_x = calcular_x(df_mediana_growth_10y_eps, discount_rate)
        df_eps_crecimiento_10_x = calcular_x(df_eps_crecimiento_10, discount_rate)
        df_cagr_eps_10_x = calcular_x(df_cagr_eps_10, discount_rate)

        eps_without_nri = pd.to_numeric(eps_without_nri, errors="coerce")
        eps_without_nri.index.name = "Año"

        df_eps_without_nri = eps_without_nri.to_frame(name="EPS_without_NRI")

        def calcular_intrinsic_value_eps(df_x, df_y, df_eps):
            # Normalizar df_x
            dx = df_x.copy()
            if "Año" in dx.columns:
                dx["Año"] = dx["Año"].astype(int)
                dx = dx.set_index("Año")
            dx.index.name = "Año"

            col_x = dx.columns[0]
            dx[col_x] = pd.to_numeric(dx[col_x], errors="coerce")

            deps = df_eps.copy()
            if "Año" in deps.columns:
                deps["Año"] = deps["Año"].astype(int)
                deps = deps.set_index("Año")
            deps.index.name = "Año"
            deps["EPS"] = pd.to_numeric(deps["EPS"], errors="coerce")

            dy = df_y.copy()
            if "Año" in dy.columns:
                dy["Año"] = dy["Año"].astype(int)
                dy = dy.set_index("Año")
            dy.index.name = "Año"
            dy["y"] = pd.to_numeric(dy["y"], errors="coerce")

            # --- Unir por Año ---
            base = (
                deps
                    .join(dx[[col_x]].rename(columns={col_x: "x"}), how="inner")
                    .join(dy[["y"]], how="inner")
            )

            x = base["x"]
            y = base["y"]
            f = base["EPS"]

            # --- Fórmula ---
            term1 = x * (1 - x**10) / (1 - x)
            term2 = (x**10) * y * (1 - y**10) / (1 - y)

            base["Intrinsic_Value_eps"] = f * (term1 + term2)

            return base[["Intrinsic_Value_eps"]]


        df_weighted_growth_10y_eps_value = calcular_intrinsic_value_eps(df_weighted_growth_10y_eps_x,df_y ,df_eps)
        df_mediana_growth_10y_eps_value = calcular_intrinsic_value_eps(df_mediana_growth_10y_eps_x, df_y ,df_eps)
        df_eps_crecimiento_10_value = calcular_intrinsic_value_eps(df_eps_crecimiento_10_x, df_y ,df_eps)
        df_cagr_eps_10_value = calcular_intrinsic_value_eps(df_cagr_eps_10_x, df_y ,df_eps)

        # ## Tabla con valores de acciones y limpieza de df

        # Copia para no modificar el original
        df_bvps = book_value_per_share_anual.copy()

        # Convertir índice a datetime y extraer año
        df_bvps["Año"] = pd.to_datetime(
            df_bvps.index.astype(str),
            format="%b%Y",
            errors="coerce"
        ).year

        # Convertir Book Value per Share a numérico
        df_bvps["Book_Value_per_Share"] = pd.to_numeric(
            df_bvps["Book Value per Share"], errors="coerce"
        )

        # Quitar filas donde no se pudo extraer el año (ej. fila vacía inicial)
        df_bvps = df_bvps.dropna(subset=["Año"])

        # Quedarse solo con las dos columnas finales y sin índice
        df_bvps = (
            df_bvps[["Año", "Book_Value_per_Share"]]
                .reset_index(drop=True)
        )

        def serie_a_df_anual(serie, nombre_columna):

            s = pd.to_numeric(serie, errors="coerce")

            # Extraer año del índice (funciona si el índice es 'Dec2005', '2005', etc.)
            anios = (
                s.index.astype(str)
                .str.extract(r'(\d{4})')[0]
            )

            df = pd.DataFrame({
                "Año": pd.to_numeric(anios, errors="coerce").astype("Int64"),
                nombre_columna: s.values
            })

            # Quitar filas donde no se pudo obtener año y dejar sin índice
            df = df.dropna(subset=["Año"])
            df["Año"] = df["Año"].astype(int)
            df = df.reset_index(drop=True)

            return df


        df_intrinsic_limpio = df_intrinsic[["Año", "Intrinsic_Value"]].copy()

        df_liquidation_value_per_share = serie_a_df_anual(liquidation_value_per_share, "Liquidation_Value_Per_Share")
        df_Median_ps_value_promedio = serie_a_df_anual(Median_ps_value_promedio, "Median_PS_Value_Promedio")
        df_Median_ps_value_promedio_mediana = serie_a_df_anual(Median_ps_value_promedio_mediana, "Median_PS_Value_Promedio_Mediana")

        df_peter  = df_peter.reset_index().rename(columns={df_peter.index.name or "index": "Año"})
        df_peter_2 = df_peter_2.reset_index().rename(columns={df_peter_2.index.name or "index": "Año"})
        df_intrinsic_weighted = df_intrinsic_weighted.reset_index().rename(columns={df_intrinsic_weighted.index.name or "index": "Año"})
        df_intrinsic_mediana  = df_intrinsic_mediana.reset_index().rename(columns={df_intrinsic_mediana.index.name or "index": "Año"})
        df_intrinsic_fcf_avg  = df_intrinsic_fcf_avg.reset_index().rename(columns={df_intrinsic_fcf_avg.index.name or "index": "Año"})
        df_intrinsic_cagr_fcf = df_intrinsic_cagr_fcf.reset_index().rename(columns={df_intrinsic_cagr_fcf.index.name or "index": "Año"})
        df_weighted_growth_10y_eps_value = df_weighted_growth_10y_eps_value.reset_index().rename(columns={df_weighted_growth_10y_eps_value.index.name or "index": "Año"})
        df_mediana_growth_10y_eps_value = df_mediana_growth_10y_eps_value.reset_index().rename(columns={df_mediana_growth_10y_eps_value.index.name or "index": "Año"})
        df_eps_crecimiento_10_value = df_eps_crecimiento_10_value.reset_index().rename(columns={df_eps_crecimiento_10_value.index.name or "index": "Año"})
        df_cagr_eps_10_value = df_cagr_eps_10_value.reset_index().rename(columns={df_cagr_eps_10_value.index.name or "index": "Año"})

        df_intrinsic_weighted  = df_intrinsic_weighted.rename(
            columns={df_intrinsic_weighted.columns[1]: "Intrinsic_Weighted"}
        )

        df_intrinsic_mediana   = df_intrinsic_mediana.rename(
            columns={df_intrinsic_mediana.columns[1]: "Intrinsic_Mediana"}
        )

        df_intrinsic_fcf_avg   = df_intrinsic_fcf_avg.rename(
            columns={df_intrinsic_fcf_avg.columns[1]: "Intrinsic_FCF_Avg"}
        )

        df_intrinsic_cagr_fcf  = df_intrinsic_cagr_fcf.rename(
            columns={df_intrinsic_cagr_fcf.columns[1]: "Intrinsic_CAGR_FCF"}
        )

        df_weighted_growth_10y_eps_value  = df_weighted_growth_10y_eps_value.rename(
            columns={df_weighted_growth_10y_eps_value.columns[1]: "Intrinsic_EPS_Weighted"}
        )

        df_mediana_growth_10y_eps_value   = df_mediana_growth_10y_eps_value.rename(
            columns={df_mediana_growth_10y_eps_value.columns[1]: "Intrinsic_EPS_Mediana"}
        )

        df_eps_crecimiento_10_value   = df_eps_crecimiento_10_value.rename(
            columns={df_eps_crecimiento_10_value.columns[1]: "Intrinsic_EPS_Avg"}
        )

        df_cagr_eps_10_value  = df_cagr_eps_10_value.rename(
            columns={df_cagr_eps_10_value.columns[1]: "Intrinsic_CAGR_EPS"}
        )

        def obtener_serie_fiscal(df, fiscal_period, nombre_columna):

            tmp = df.loc[df["Fiscal Period"] == fiscal_period]

            if tmp.empty:
                years_cols = df.columns[1:]
                serie_vacia = pd.Series(0, index=years_cols)
                return serie_a_df_anual(serie_vacia, nombre_columna)

            serie = tmp.iloc[0, 1:]
            return serie_a_df_anual(serie, nombre_columna)


        df_book_value_guru = obtener_serie_fiscal(
            df_anual_filtrado,
            "Book Value per Share",
            "Book_Value_per_Share_Guru"
        )

        df_tangible_book_value_guru = obtener_serie_fiscal(
            df_anual_filtrado,
            "Tangible Book per Share",
            "Tangible_Book_Value_per_Share_Guru"
        )

        df_projected_fcf_guru = obtener_serie_fiscal(
            df_anual_filtrado,
            "Intrinsic Value: Projected FCF",
            "Projected_FCF_Guru"
        )

        df_median_ps_guru = obtener_serie_fiscal(
            df_anual_filtrado,
            "Median PS Value",
            "Median_PS_Value_Guru"
        )

        df_peter_lynch_fair_value_guru = obtener_serie_fiscal(
            df_anual_filtrado,
            "Peter Lynch Fair Value",
            "Peter_Lynch_Fair_Value_Guru"
        )

        df_graham_number_guru = obtener_serie_fiscal(
            df_anual_filtrado,
            "Graham Number",
            "Graham_Number_Guru"
        )

        df_earnings_power_value_guru = obtener_serie_fiscal(
            df_anual_filtrado,
            "Earnings Power Value (EPV)",
            "Earnings_Power_Value_Guru"
        )

        df_gf_value_guru = obtener_serie_fiscal(
            df_anual_filtrado,
            "GF Value",
            "GF_Value_Guru"
        )



        # Lista "candidata" por nombre (evita NameError si alguno no existe)
        df_names = [
            "df_bvps",
            "df_liquidation_value_per_share",
            "df_epv_final",
            "df_ncav_per_share",
            "df_tangible_book_value_per_share",
            "df_intrinsic_limpio",
            "df_Median_ps_value_promedio",
            "df_Median_ps_value_promedio_mediana",
            "df_graham",
            "df_peter",
            "df_peter_2",
            "df_intrinsic_weighted",
            "df_intrinsic_mediana",
            "df_intrinsic_fcf_avg",
            "df_intrinsic_cagr_fcf",
            "df_weighted_growth_10y_eps_value",
            "df_mediana_growth_10y_eps_value",
            "df_eps_crecimiento_10_value",
            "df_cagr_eps_10_value",
            "df_book_value_guru",
            "df_tangible_book_value_guru",
            "df_projected_fcf_guru",
            "df_median_ps_guru",
            "df_peter_lynch_fair_value_guru",
            "df_graham_number_guru",
            "df_earnings_power_value_guru",
            "df_gf_value_guru",
        ]

        dfs_validos = []
        for name in df_names:
            df = globals().get(name, None)  # si no existe, regresa None

            # validar que sea DataFrame y que tenga la columna Año
            if isinstance(df, pd.DataFrame) and (not df.empty) and ("Año" in df.columns):
                dfs_validos.append(df)

        # Si no hay nada, crea df base vacío con Año para evitar error
        if not dfs_validos:
            df_valuaciones = pd.DataFrame(columns=["Año"])
        else:
            df_valuaciones = reduce(
                lambda left, right: pd.merge(left, right, on="Año", how="outer"),
                dfs_validos
            )

        # Ordenar por año (si existe Año)
        if "Año" in df_valuaciones.columns and not df_valuaciones.empty:
            df_valuaciones = df_valuaciones.sort_values("Año").reset_index(drop=True)

        # Quitar primeras 5 filas si aplica
        if len(df_valuaciones) > 5:
            df_valuaciones = df_valuaciones.iloc[5:].reset_index(drop=True)


        # ## Modelo de Targets

        data_stock_modelo = pd.read_csv(archivo_stock + '.csv')
        data_stock_modelo.drop(columns=["Vol.","Cierre","Apertura"],axis=1, inplace=True)
        data_stock_modelo["Fecha"] = pd.to_datetime(
            data_stock_modelo["Fecha"],
            format="%Y-%m-%d"
        )

        prices = data_stock_modelo.copy()

        prices["Fecha"] = pd.to_datetime(prices["Fecha"])

        prices = prices.sort_values("Fecha").reset_index(drop=True)

        prices.head()

        mes_map = {
            "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
            "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
            "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
        }

        headers_df = pd.DataFrame({
            "Header": valid_headers
        })

        headers_df["Mes"] = headers_df["Header"].str[:3].map(mes_map)
        headers_df["Año"] = headers_df["Header"].str[-4:].astype(int)

        # Fecha base = primer día del mes del header
        headers_df["Fecha_base"] = pd.to_datetime(
            headers_df["Año"].astype(str) + "-" +
            headers_df["Mes"].astype(str).str.zfill(2) + "-01"
        )

        headers_df["Fecha_teorica"] = headers_df["Fecha_base"] + pd.DateOffset(months=1)

        valuations = df_valuaciones.copy()

        valuations = valuations.merge(
            headers_df[["Año", "Fecha_teorica"]],
            on="Año",
            how="left"
        )

        price_dates = prices[["Fecha"]]

        valuations = pd.merge_asof(
            valuations.sort_values("Fecha_teorica"),
            price_dates.sort_values("Fecha"),
            left_on="Fecha_teorica",
            right_on="Fecha",
            direction="forward"
        )

        valuations = valuations.rename(columns={"Fecha": "Fecha_base"})

        valuations[["Año", "Fecha_teorica", "Fecha_base"]].head()


        id_cols = ["Año", "Fecha_base"]

        # Asegúrate de no tener columnas duplicadas
        valuations = valuations.loc[:, ~valuations.columns.duplicated()].copy()

        # Seleccionar SOLO columnas de métodos (numéricas) y excluir id_cols
        method_cols = [
            c for c in valuations.columns
            if c not in id_cols and pd.api.types.is_numeric_dtype(valuations[c])
        ]

        valuations_long = valuations.melt(
            id_vars=id_cols,
            value_vars=method_cols,
            var_name="Metodo",
            value_name="Valor"
        )

        # Forzar a numérico y limpiar
        valuations_long["Valor"] = pd.to_numeric(valuations_long["Valor"], errors="coerce")
        valuations_long = valuations_long.dropna(subset=["Valor"])


        tol = 0.05
        H = 156

        prices["Fecha"] = pd.to_datetime(prices["Fecha"])
        prices = prices.sort_values("Fecha").reset_index(drop=True)

        # Ajusta estos nombres 
        HIGH_COL = "Máximo"
        LOW_COL  = "Mínimo"

        # Chequeos rápidos
        assert prices["Fecha"].is_monotonic_increasing
        assert {HIGH_COL, LOW_COL}.issubset(prices.columns)
        assert {"Fecha_base", "Metodo", "Valor"}.issubset(valuations_long.columns)

        valuations_long["L"] = valuations_long["Valor"] * (1 - tol)
        valuations_long["U"] = valuations_long["Valor"] * (1 + tol)


        valuations_long["Fecha_fin"] = valuations_long["Fecha_base"] + pd.to_timedelta(H, unit="W")

        prices["Fecha"] = pd.to_datetime(prices["Fecha"], errors="coerce")

        # Limpieza: quitar comas de miles y convertir a float
        for c in [HIGH_COL, LOW_COL]: 
            prices[c] = (
                prices[c]
                .astype(str)
                .str.replace(",", "", regex=False) 
                .str.replace(" ", "", regex=False)
            )
            prices[c] = pd.to_numeric(prices[c], errors="coerce")


        prices = prices.dropna(subset=["Fecha", HIGH_COL, LOW_COL]).sort_values("Fecha").reset_index(drop=True)

        def first_hit(fecha_base, fecha_fin, valor, L, U):
            if valor is None or pd.isna(valor) or valor <= 0:
                return np.nan, np.nan, pd.NaT, pd.NA

            w = prices.loc[
                (prices["Fecha"] >= fecha_base) & (prices["Fecha"] <= fecha_fin),
                ["Fecha", HIGH_COL, LOW_COL]
            ]

            if w.empty:
                return False, np.nan, pd.NaT, pd.NA

            hit_mask = (w[LOW_COL] <= U) & (w[HIGH_COL] >= L)
            if not hit_mask.any():
                # side basado en p_base aunque no haya hit
                base_high = w.iloc[0][HIGH_COL]
                base_low  = w.iloc[0][LOW_COL]
                p_base = (base_high + base_low) / 2
                if p_base < L:
                    side = "long"
                elif p_base > U:
                    side = "short"
                else:
                    side = "at_target"
                return False, np.nan, pd.NaT, side

            first_pos = int(np.argmax(hit_mask.to_numpy()))
            hit_date = w.iloc[first_pos]["Fecha"]
            tth_weeks = first_pos

            if first_pos == 0:
                side = "at_target"
            else:
                base_high = w.iloc[0][HIGH_COL]
                base_low  = w.iloc[0][LOW_COL]
                p_base = (base_high + base_low) / 2
                if p_base < L:
                    side = "long"
                elif p_base > U:
                    side = "short"
                else:
                    side = "at_target"

            return True, tth_weeks, hit_date, side


        hits = valuations_long.apply(
            lambda r: first_hit(r["Fecha_base"], r["Fecha_fin"], r["Valor"], r["L"], r["U"]),
            axis=1,
            result_type="expand"
        )

        hits.columns = ["hit", "tth_weeks", "hit_date", "side"]
        valuations_long[["hit", "tth_weeks", "hit_date", "side"]] = hits


        valuations_long[["Año","Metodo","Valor","Fecha_base","hit","tth_weeks","hit_date"]]

        # Convertir NaT -> NaN en hit (y cualquier cosa rara)
        valuations_long["hit"] = valuations_long["hit"].replace({pd.NaT: np.nan})

        # Fuerza dtype booleano nullable (permite True/False/<NA>)
        valuations_long["hit"] = valuations_long["hit"].astype("boolean")


        summary = (
            valuations_long
            .groupby("Metodo", as_index=False)
            .agg(
                targets=("hit", "count"),       
                hits=("hit", "sum"),              
                hit_rate=("hit", "mean"),        
                median_tth=("tth_weeks", "median"),
                avg_tth=("tth_weeks", "mean"),
            )
        )

        for years, weeks in [(1, 52), (2, 104), (3, 156)]:
            col = f"hit_le_{years}y"

            tmp = valuations_long["hit"] & (valuations_long["tth_weeks"] <= weeks)

            summary[col] = (
                valuations_long
                .assign(_tmp=tmp)
                .groupby("Metodo")["_tmp"]
                .mean()            
                .values
            )

        summary = summary.sort_values(
            ["hit_rate", "median_tth"],
            ascending=[False, True]
        ).reset_index(drop=True)


        metodos_top = summary.loc[summary["hit_rate"] >= 0.70, "Metodo"]

        df_hits_por_anio = (
            valuations_long
            .loc[
                valuations_long["Metodo"].isin(metodos_top),
                ["Año", "Metodo", "Valor", "hit", "tth_weeks", "hit_date","side"]
            ]
            .sort_values(["Metodo", "Año"])
            .reset_index(drop=True)
        )

        df_hits_por_anio['Mes'] = headers_df['Mes'].iloc[0]

        df_hits_por_anio.to_excel(f'Valuaciones_USA/{ticket}_valuaciones_hits_por_anio.xlsx', index=False)

        # ## Calificacion ratios

        ratios_a_eliminar = [
            "Net Income",
            "Sales",
            "Net Income Growth",
            "Cost of Goods Sold",
            "Inventories",
            "Inventories Growth",
            "Free Cash Flow",
            "Free cash flow per share",
            "FCF/DEBT corto plazo",
            "Sales Growth",
            "Cost of Goods Sold Growth",
            "Valor en libros"
        ]

        razones_financieras_ratios = razones_financieras.drop(index=ratios_a_eliminar, errors="ignore")

        # SISTEMA DE PONDERACIÓN - Importancias y funciones de scoring

        year_cols = [c for c in razones_financieras_ratios.columns if str(c)[:3] in mes_map]

        importancia_dict = {
            'Amortizacion(%)':                   1,
            'Net Profit Margin(%)':              5,
            'Gross Profit(%)':                   4,
            'Operating Margin(%)':               3,
            'EPS':                               4,
            'Revenue Per Share':                 2,
            '# Shares':                          0.5,
            'Inventory Turnover Ratio':          2,
            'Dividends per Share':               1,
            'Free cash flow to sales(%)':        8,
            'Free Cash Flow to Debt ratio':      5,
            'Dividend Payout Ratio(%)':          1,
            'net worth to long-term debt ratio': 3,
            'Pasivo/Fondos Propios':             3,
            'Current Ratio':                     1,
            'long-term debt-to-equity(%)':       5,
            'Gasto financiero(%)':               3,
            'Inventory to current Assets(%)':    1,
            'Net Trading Cycle':                 3,
            'PEGY Ratio':                        3,
            'PER':                               5,
            'P/S Ratio':                         2,
            'Receivable to Current Assets(%)':   1,
            'ROA%':                              4,
            'ROE%':                              6,
            'ROB':                               1.5,
            'ROIC %':                            10,
            'WACC %':                            0,
            'Test de Acidez':                    1,
            'Piotrivski F-Score':                5,
            'Altman Z score':                    5,
            'Beneish M-Score':                   1,
        }


        def _slope(series, idx, window=5):
            """Pendiente lineal de los últimos `window` años hasta idx."""
            start = max(0, idx - window + 1)
            vals = series.iloc[start:idx+1].dropna()
            if len(vals) < 2:
                return np.nan
            x = np.arange(len(vals), dtype=float)
            return np.polyfit(x, vals.values.astype(float), 1)[0]


        def _score_trend(series, idx, bajista=False, window=5):
            s = _slope(series, idx, window)
            if pd.isna(s):
                return np.nan
            start = max(0, idx - window + 1)
            ref = abs(series.iloc[start:idx+1].dropna().mean()) or 1
            norm = (s / ref) * (-1 if bajista else 1)
            if norm > 0.02:
                return 1.0
            if norm >= -0.02:
                return 0.5
            return 0.0

        def calcular_score(ratio, val, series, idx, wacc_val=np.nan):
            """Devuelve score 0-1 para un valor dado según los criterios del ratio."""
            if pd.isna(val):
                return np.nan

            # Amortizacion: <10% bueno, 10-20% neutro, >20% malo
            if ratio == 'Amortizacion(%)':
                return 1.0 if val < 10 else (0.5 if val <= 20 else 0.0)

            # Net Profit Margin: >20% ventaja, 10-20% bueno, 0-10% bajo, <0 malo
            if ratio == 'Net Profit Margin(%)':
                if val > 20:  return 1.0
                if val >= 10: return 0.50
                if val >= 0:  return 0.25
                return 0.0

            # Gross Profit: >40% ventaja, 20-40% neutro, <20% malo
            if ratio == 'Gross Profit(%)':
                return 1.0 if val > 40 else (0.5 if val >= 20 else 0.0)

            # Ratios con tendencia alcista deseable
            if ratio in ('Operating Margin(%)', 'EPS', 'Revenue Per Share',
                     'Dividends per Share', 'Free cash flow to sales(%)', 'Valor en libros'):
                # Si el ratio es dividendos y todos los valores recientes son 0 → no hay crecimiento
                if ratio == 'Dividends per Share':
                    start = max(0, idx - 4)
                    window_vals = series.iloc[start:idx+1].fillna(0)
                    if (window_vals == 0).all():
                        return 0.0
                return _score_trend(series, idx)

            #  Shares: tendencia bajista deseable (recompras = bueno)
            if ratio == '# Shares':
                return _score_trend(series, idx, bajista=True)

            # Inventory Turnover: >8 excelente, 4-8 saludable, <4 bajo
            if ratio == 'Inventory Turnover Ratio':
                return 1.0 if val > 8 else (0.5 if val >= 4 else 0.0)

            if ratio == 'Free cash flow to sales(%)':
                if val >= 15.0:   return 1.0
                if val >= 10.0: return 0.75
                if val >= 5.0:   return 0.25
                return 0.0

            # FCF to Debt: >=1 excelente, decreciente hacia 0 peor
            if ratio == 'Free Cash Flow to Debt ratio':
                if val >= 1:   return 1.0
                if val >= 0.8: return 0.75
                if val >= 0.6:   return 0.25
                if val >= 0.4 : return 0.10
                return 0.0

            # Dividend Payout: 20-60% óptimo; sin dividendo → neutro
            if ratio == 'Dividend Payout Ratio(%)':
                if 20 <= val <= 60: return 1.0
                return 0.0

            # Net Income / LT Debt: >=3 excelente, >=1 bueno
            if ratio == 'net worth to long-term debt ratio':
                if val >= 3: return 1.0
                if val >= 2: return 0.75
                if val >= 1: return 0.5
                if val >= 0.5: return 0.25
                return 0.0

            # Pasivo/FP: <=1 es mejor, pero si es negativo o 0 se penaliza (puede indicar problemas contables o insolvencia)
            if ratio == 'Pasivo/Fondos Propios':
                if val <= 1: return 1.0
                if val <= 0: return 0
                if val > 1 : return 0
                return 0.0

            # Current Ratio: >=1.5 muy bueno, >=1 solvente, >=0.5 cuidado, <0.5 evitar
            if ratio == 'Current Ratio':
                if val >= 1.5: return 1.0
                if val >= 1.0: return 0.75
                if val >= 0.5: return 0.25
                return 0.0

            # LT Debt-to-Equity: <25% bueno, <45% neutro, >=75% alto apalancamiento
            if ratio == 'long-term debt-to-equity(%)':
                if val < 0: return 0.0
                return 1.0 if val < 25 else (0.5 if val < 45 else 0.0)

            # Gasto financiero: <15% ventaja, <30% aceptable, >=30% alto
            if ratio == 'Gasto financiero(%)':
                return 1.0 if val < 15 else (0.5 if val < 30 else 0.0)

            # Inventory / Current Assets: <40% bueno, <60% neutro, >=60% evitar
            if ratio == 'Inventory to current Assets(%)':
                return 1.0 if val < 40 else (0.25 if val < 60 else 0.0)

            # Net Trading Cycle: negativo = bueno; más negativo + revenue creciente = mejor
            if ratio == 'Net Trading Cycle':
                if val < 0:
                    # Negativo es bueno siempre que Revenue Per Share esté creciendo
                    rps = pd.to_numeric(razones_financieras_ratios.loc['Revenue Per Share', year_cols], errors='coerce')
                    rps_trend = _score_trend(rps, idx)
                    return 1.0 if rps_trend == 1.0 else 0.5
                else:
                    # Positivo: buscamos tendencia bajista o estable
                    trend = _score_trend(series, idx, bajista=True)
                    return 0.0 if trend == 0.0 else 0.5

            # PEGY: <1 bueno, 1-2 neutro, >1.75 caro; 0 = sin datos (EPS negativo)
            if ratio == 'PEGY Ratio':
                if val == 0: return np.nan
                return 1.0 if val < 1 else (0.5 if val <= 1.75 else 0.0)

            # PER: <9 excelente, 9-25 bueno, 25-40 caro, >40 muy caro
            if ratio == 'PER':
                if val <= 0: return np.nan
                if val < 9:   return 1.0
                if val <= 25: return 0.75
                if val <= 40: return 0.25
                return 0.0

            # P/S: bajo vs promedio histórico = buena señal de compra
            if ratio == 'P/S Ratio':
                if val == 0: return np.nan
                start = max(0, idx - 5)
                hist_avg = series.replace(0, np.nan).iloc[start:idx].mean()
                if pd.isna(hist_avg) or hist_avg == 0: return 0.5
                rel = val / hist_avg
                return 1.0 if rel < 0.8 else (0.5 if rel <= 1.2 else 0.0)


            # Receivable / Current Assets: <40% bueno, <60% neutro, >=60% evitar
            if ratio == 'Receivable to Current Assets(%)':
                return 1.0 if val < 40 else (0.5 if val < 60 else 0.0)

            # ROA: >20% excelente, 7-20% bueno, 0-7% bajo, <0 pérdida
            if ratio == 'ROA%':
                if val > 20:  return 1.0
                if val >= 7:  return 0.50
                if val >= 0:  return 0.25
                return 0.0

            # ROE: >20% excelente, 15-20% bueno, 0-15% bajo, <0 pérdida
            if ratio == 'ROE%':
                if val > 20:  return 1.0

                if val >= 15: return 0.75
                if val >= 0:  return 0.25
                return 0.0

            # ROB: <4.5 seguro, >=4.5 apalancamiento riesgoso
            if ratio == 'ROB':
                return 1.0 if val < 4.5 else 0.0

            # ROIC: supera WACC y >15% = ventaja competitiva
            if ratio == 'ROIC %':
                beat_wacc = (not pd.isna(wacc_val)) and val > wacc_val
                if beat_wacc and val > 15: return 1.0
                if beat_wacc:              return 0.50
                return 0.0

            # WACC: no se califica (importancia=0)
            if ratio == 'WACC %':
                return np.nan

            # Test de Acidez: >=1 bueno, 0.5-1 cuidado, <0.5 riesgo
            if ratio == 'Test de Acidez':
                return 1.0 if val >= 1 else (0.5 if val >= 0.5 else 0.0)

            # Piotroski F-Score: 7-9 bueno, 4-6 gris, 0-3 malo
            if ratio == 'Piotrivski F-Score':
                return 1.0 if val >= 7 else (0.5 if val >= 4 else 0.0)

            # Altman Z: >3 zona segura, 1.8-3 zona gris, <1.8 peligro de quiebra
            if ratio == 'Altman Z score':
                return 1.0 if val > 3 else (0.5 if val >= 1.8 else 0.0)

            # Beneish M-Score: >3 sin manipulación, 1.8-3 zona gris, <1.8 alerta
            if ratio == 'Beneish M-Score':
                return 1.0 if val >= 1.78 else 0.0

            return np.nan


        # APLICAR SCORING Y CALCULAR PONDERACIÓN

        # Fila de WACC para comparar con ROIC
        wacc_row = (
            pd.to_numeric(razones_financieras_ratios.loc['WACC %', year_cols], errors='coerce')
            if 'WACC %' in razones_financieras_ratios.index
            else pd.Series(np.nan, index=year_cols)
        )

        # Calcular scores 0-1 por ratio y año
        df_scores = pd.DataFrame(index=razones_financieras_ratios.index, columns=year_cols, dtype=float)

        for ratio in razones_financieras_ratios.index:
            row_vals = pd.to_numeric(razones_financieras_ratios.loc[ratio, year_cols], errors='coerce')
            for i, yr in enumerate(year_cols):
                val    = row_vals.iloc[i]
                wacc_v = wacc_row.get(yr, np.nan)
                df_scores.loc[ratio, yr] = calcular_score(ratio, val, row_vals, i, wacc_v)

        df_scores = df_scores.astype(float)

        # Agregar columna de importancia
        pesos = pd.Series(importancia_dict).reindex(df_scores.index).fillna(0)
        df_scores.insert(0, '% importancia', pesos)

        # Scores ponderados = score × importancia
        df_scores_ponderados = df_scores[year_cols].multiply(pesos, axis=0)
        df_scores_ponderados.insert(0, '% importancia', pesos)

        # Score total por año: suma ponderada normalizada 0-100
        score_total = {}
        for yr in year_cols:
            col  = df_scores[yr]
            mask = col.notna() & (pesos > 0)
            if mask.sum() == 0:
                score_total[yr] = np.nan
            else:
                score_total[yr] = round(
                    (col[mask] * pesos[mask]).sum() / pesos[mask].sum() * 100, 1
                )

        df_score_total = pd.Series(score_total, name='Score Total (%)')



        # Agregar fila Score Total al df_scores_ponderados
        score_total_row = df_scores_ponderados[year_cols].sum(skipna=True)
        score_total_row["% importancia"] = pesos.sum()
        df_scores_ponderados_con_total = pd.concat([
            df_scores_ponderados,
            score_total_row.rename("Score Total").to_frame().T
        ])


        df_scores_ponderados_con_total.to_excel(f"Valuaciones_USA/{ticket}_score_ponderados.xlsx")
        razones_financieras.to_excel(f"Valuaciones_USA/{ticket}_razones_financieras.xlsx")

    except Exception as e:
        print(f"ERROR en {ticket}: {e}")
        import traceback
        traceback.print_exc()
        continue
