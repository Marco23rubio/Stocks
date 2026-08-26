import os

def modify_file():
    with open('Valuaciones_2_ttm.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    in_loop = False
    skip_next = 0
    
    for line in lines:
        if skip_next > 0:
            skip_next -= 1
            continue
            
        if line.startswith('ticket = "ADBE"'):
            new_lines.extend([
                "import os\n",
                "\n",
                "ruta_usa = 'USA/'\n",
                "archivos_usa = [f for f in os.listdir(ruta_usa) if f.endswith('.xlsx') and not f.startswith('~$')]\n",
                "\n",
                "for archivo_excel in archivos_usa:\n",
                "    ticket = archivo_excel.replace('.xlsx', '')\n",
                "    print(f'\\n========================================')\n",
                "    print(f'Iniciando cálculo para: {ticket}')\n",
                "    print(f'========================================')\n",
                "    \n",
                "    try:\n",
                "        ruta = ruta_usa\n",
                "        archivo = f'{ticket}.xlsx'\n",
                "        ruta_archivo = ruta + archivo\n",
                "        archivo_stock = f'USA/DatosHistoricos/Datos históricos {ticket}'\n",
                "        \n",
                "        if not os.path.exists(f'{archivo_stock}.csv'):\n",
                "            print(f'  -> No se encontró {archivo_stock}.csv. Saltando ticket...')\n",
                "            continue\n"
            ])
            in_loop = True
            skip_next = 4  # skip the next 4 lines
        else:
            if in_loop:
                if line.strip() == '':
                    new_lines.append('\n')
                else:
                    new_lines.append('        ' + line)
            else:
                new_lines.append(line)

    if in_loop:
        new_lines.append("\n    except Exception as e:\n")
        new_lines.append("        import traceback\n")
        new_lines.append("        print(f'  -> Error al procesar {ticket}: {e}')\n")
        new_lines.append("        traceback.print_exc()\n")

    with open('Valuaciones_2_ttm.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

if __name__ == '__main__':
    modify_file()