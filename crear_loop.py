import os

def crear_loop():
    with open('Valuaciones_4_USA.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    out_lines = []
    in_loop = False
    
    for line in lines:
        if line.startswith('ticket = "ADBE"'):
            out_lines.append("import os\n")
            out_lines.append("import glob\n\n")
            out_lines.append("archivos_xlsx = glob.glob('USA/*.xlsx')\n")
            out_lines.append("tickets = [os.path.basename(f).replace('.xlsx', '') for f in archivos_xlsx if not os.path.basename(f).startswith('~')]\n\n")
            out_lines.append("for ticket in tickets:\n")
            out_lines.append("    print(f'\\n========================================')\n")
            out_lines.append("    print(f'Procesando ticket: {ticket}')\n")
            out_lines.append("    print(f'========================================')\n")
            out_lines.append("    try:\n")
            in_loop = True
            continue
        
        if in_loop:
            if line.strip() == '':
                out_lines.append(line)
            else:
                out_lines.append("        " + line)
        else:
            out_lines.append(line)

    # Añadir el except al final
    out_lines.append("\n        print(f'>>> Ticket {ticket} procesado con éxito.')\n")
    out_lines.append("    except Exception as e:\n")
    out_lines.append("        print(f'>>> Error procesando {ticket}: {e}')\n")

    with open('Valuaciones_5_USA_loop.py', 'w', encoding='utf-8') as f:
        f.writelines(out_lines)
    
    print("Archivo Valuaciones_5_USA_loop.py creado con éxito.")

if __name__ == '__main__':
    crear_loop()
