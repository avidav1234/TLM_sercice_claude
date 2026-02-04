import sqlite3
import pandas as pd
import os
import sys

# Importiamo init_db e DB_NAME dal nuovo app.py
from app import init_db, DB_NAME

# Nomi dei file CSV (devono essere nella stessa cartella)
FILE_IN_MACCHINA = "Database_DMG160U_utensili_in_macchina.csv"
FILE_SMONTATI = "Database_DMG160U_utensili_smontati.csv"

# Nome della macchina a cui assegnare questi dati
DEFAULT_MACHINE_NAME = "DMG MORI (Import)"

def import_csv():
    print("🚀 Inizio importazione DATI V6 (Multi-Macchina)...")

    # 1. GESTIONE DATABASE ESISTENTE
    if os.path.exists(DB_NAME):
        print(f"⚠️  Rilevato database '{DB_NAME}' esistente.")
        print("    Poiché la struttura è cambiata, è consigliato cancellare il DB vecchio.")
        choice = input("    Vuoi cancellare il DB e ricrearlo da zero? (s/n): ")
        if choice.lower() == 's':
            try:
                os.remove(DB_NAME)
                print("🗑️  Database vecchio rimosso.")
            except PermissionError:
                print("❌ Errore: Chiudi il programma principale 'app.py' prima di importare!")
                return
    
    # 2. INIZIALIZZA NUOVO DB
    print("🏗️  Creazione struttura database V6...")
    init_db()
    
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON") 
    cursor = conn.cursor()

    # 3. CREA O RECUPERA LA MACCHINA DI DESTINAZIONE
    cursor.execute("SELECT id FROM machines WHERE name = ?", (DEFAULT_MACHINE_NAME,))
    row = cursor.fetchone()
    
    if row:
        machine_id = row[0]
        print(f"ℹ️  Usando macchina esistente: '{DEFAULT_MACHINE_NAME}' (ID: {machine_id})")
    else:
        print(f"🆕 Creazione macchina default: '{DEFAULT_MACHINE_NAME}'...")
        cursor.execute("INSERT INTO machines (name, description) VALUES (?, ?)", 
                       (DEFAULT_MACHINE_NAME, "Macchina importata da CSV"))
        machine_id = cursor.lastrowid
        conn.commit()
        print(f"✅ Macchina creata con ID: {machine_id}")

    tools_added = 0
    errors = 0

    # 4. IMPORTA UTENSILI IN MACCHINA
    if os.path.exists(FILE_IN_MACCHINA):
        print(f"\n📂 Leggo {FILE_IN_MACCHINA}...")
        try:
            df = pd.read_csv(FILE_IN_MACCHINA, sep='\t', on_bad_lines='skip')
            df.columns = [c.strip() for c in df.columns]
            
            if 'Alias' in df.columns:
                df = df.dropna(subset=['Alias'])
                
                for index, row in df.iterrows():
                    try:
                        # Gestione Posizione
                        raw_pos = row.get('Posizione', None)
                        if pd.isna(raw_pos) or str(raw_pos).strip() == '':
                            pos = None 
                        else:
                            pos = int(float(raw_pos))

                        alias = str(row['Alias']).strip().upper()
                        
                        # Gestione Duplo
                        duplo = 1
                        if 'Duplo' in row:
                            raw_duplo = row['Duplo']
                            if not pd.isna(raw_duplo) and str(raw_duplo).strip() != '':
                                duplo = int(float(raw_duplo))

                        # CORREZIONE QUI: Rimosso 'current_life_minutes'
                        cursor.execute('''
                            INSERT INTO tools (machine_id, alias, duplo, position, target_life_minutes) 
                            VALUES (?, ?, ?, ?, ?)
                        ''', (machine_id, alias, duplo, pos, 100))
                        
                        tools_added += 1
                        
                    except sqlite3.IntegrityError:
                        pass
                    except Exception as e:
                        print(f"   ❌ Errore riga {index}: {e}")
                        errors += 1
            else:
                print("⚠️ Colonna 'Alias' non trovata nel file.")
                
        except Exception as e:
            print(f"⚠️ Errore lettura file CSV: {e}")
    else:
        print(f"⚠️ File '{FILE_IN_MACCHINA}' non trovato.")

    # 5. IMPORTA UTENSILI SMONTATI (MAGAZZINO)
    if os.path.exists(FILE_SMONTATI):
        print(f"\n📂 Leggo {FILE_SMONTATI}...")
        try:
            df = pd.read_csv(FILE_SMONTATI, sep='\t', on_bad_lines='skip')
            df.columns = [c.strip() for c in df.columns]
            
            col_alias = 'Alias_Utensile' if 'Alias_Utensile' in df.columns else 'Alias'
            
            if col_alias in df.columns:
                df = df.dropna(subset=[col_alias])
                unique_tools = df[col_alias].unique()
                
                for alias_raw in unique_tools:
                    alias = str(alias_raw).strip().upper()
                    try:
                        # CORREZIONE QUI: Rimosso 'current_life_minutes'
                        cursor.execute('''
                            INSERT INTO tools (machine_id, alias, duplo, position, target_life_minutes) 
                            VALUES (?, ?, ?, ?, ?)
                        ''', (machine_id, alias, 1, None, 100))
                        
                        tools_added += 1
                    except sqlite3.IntegrityError:
                        pass 
            else:
                print(f"⚠️ Colonna '{col_alias}' non trovata nel file smontati.")

        except Exception as e:
            print(f"⚠️ Errore lettura file smontati: {e}")

    conn.commit()
    conn.close()
    
    print("\n" + "="*50)
    print(f"🎉 IMPORTAZIONE COMPLETATA!")
    print(f"📍 Macchina: {DEFAULT_MACHINE_NAME}")
    print(f"🔧 Utensili aggiunti: {tools_added}")
    if errors > 0:
        print(f"⚠️ Errori ignorati: {errors}")
    print("="*50)
    print("   Ora puoi avviare 'python app.py'")

if __name__ == "__main__":
    import_csv()