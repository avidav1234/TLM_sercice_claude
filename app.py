import sqlite3
import numpy as np
from flask import Flask, render_template, request, jsonify, g, Response
import os
import sys
import webview
import threading
from datetime import datetime, timedelta
import csv
import io
import shutil

# === CONFIGURAZIONE BACKUP ===
BACKUP_PATH = r"H:\0CellaMikron\0Cella_DMG-Test\Backup Archivi\TLM_service"
BACKUP_RETENTION_DAYS = 30  # Mantiene backup degli ultimi 30 giorni

def backup_database():
    """Esegue backup giornaliero del database"""
    try:
        if not os.path.exists(DB_NAME):
            print("[BACKUP] Database non trovato, skip backup")
            return False
        
        # Crea cartella backup se non esiste
        if not os.path.exists(BACKUP_PATH):
            os.makedirs(BACKUP_PATH)
            print(f"[BACKUP] Creata cartella: {BACKUP_PATH}")
        
        # Nome file con data
        today = datetime.now().strftime("%Y-%m-%d")
        backup_filename = f"tlm_data_backup_{today}.db"
        backup_filepath = os.path.join(BACKUP_PATH, backup_filename)
        
        # Se il backup di oggi esiste già, skip
        if os.path.exists(backup_filepath):
            print(f"[BACKUP] Backup di oggi già esistente: {backup_filename}")
            return True
        
        # Copia il database
        shutil.copy2(DB_NAME, backup_filepath)
        print(f"[BACKUP] Backup completato: {backup_filepath}")
        
        # Pulizia vecchi backup
        cleanup_old_backups()
        
        return True
    except Exception as e:
        print(f"[BACKUP] Errore: {e}")
        return False

def cleanup_old_backups():
    """Rimuove backup più vecchi di BACKUP_RETENTION_DAYS giorni"""
    try:
        if not os.path.exists(BACKUP_PATH):
            return
        
        cutoff_date = datetime.now() - timedelta(days=BACKUP_RETENTION_DAYS)
        
        for filename in os.listdir(BACKUP_PATH):
            if filename.startswith("tlm_data_backup_") and filename.endswith(".db"):
                # Estrai data dal nome file
                try:
                    date_str = filename.replace("tlm_data_backup_", "").replace(".db", "")
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    if file_date < cutoff_date:
                        filepath = os.path.join(BACKUP_PATH, filename)
                        os.remove(filepath)
                        print(f"[BACKUP] Rimosso vecchio backup: {filename}")
                except:
                    pass
    except Exception as e:
        print(f"[BACKUP] Errore pulizia: {e}")

# Configurazione path per PyInstaller
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

template_folder = resource_path('templates')
app = Flask(__name__, template_folder=template_folder)
DB_NAME = "tlm_data.db"

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_NAME, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        
        # 1. Tabella Macchine (NUOVA)
        db.execute('''CREATE TABLE IF NOT EXISTS machines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # 2. Tabella Utensili (con machine_id)
        db.execute('''CREATE TABLE IF NOT EXISTS tools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id INTEGER NOT NULL,
                alias TEXT NOT NULL,
                duplo INTEGER DEFAULT 1,
                position INTEGER,
                target_life_minutes INTEGER DEFAULT 100,
                FOREIGN KEY(machine_id) REFERENCES machines(id) ON DELETE CASCADE,
                UNIQUE(machine_id, alias, duplo))''')
        
        # 3. Tabella Materiali (per macchina)
        db.execute('''CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id INTEGER,
                name TEXT NOT NULL,
                factor REAL DEFAULT 1.0,
                FOREIGN KEY(machine_id) REFERENCES machines(id) ON DELETE CASCADE,
                UNIQUE(machine_id, name))''')
        
        # 4. Tabella Storico Operativo (Corrente)
        db.execute('''CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_id INTEGER,
                action_type TEXT DEFAULT 'WORK', 
                delta_minutes REAL,
                material_factor REAL,
                material_name TEXT,
                final_norm_usage REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(tool_id) REFERENCES tools(id) ON DELETE CASCADE)''')
        
        # 5. Tabella Cicli Conclusi (con machine_id per storico)
        db.execute('''CREATE TABLE IF NOT EXISTS completed_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id INTEGER,
                alias TEXT,
                duplo INTEGER,
                total_real_minutes REAL,
                total_norm_minutes REAL,
                target_at_time REAL,
                end_status TEXT, 
                end_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(machine_id) REFERENCES machines(id))''')
        
        # Migrazione: aggiungi machine_id se tabelle esistono già senza
        try:
            db.execute("ALTER TABLE tools ADD COLUMN machine_id INTEGER DEFAULT 1")
        except:
            pass
        
        try:
            db.execute("ALTER TABLE completed_cycles ADD COLUMN machine_id INTEGER DEFAULT 1")
        except:
            pass
        
        try:
            db.execute("ALTER TABLE materials ADD COLUMN machine_id INTEGER DEFAULT NULL")
        except:
            pass
        
        # Migrazione: assegna materiali senza machine_id a tutte le macchine esistenti
        try:
            orphan_materials = db.execute("SELECT * FROM materials WHERE machine_id IS NULL").fetchall()
            if orphan_materials:
                machines = db.execute("SELECT id FROM machines").fetchall()
                for machine in machines:
                    for mat in orphan_materials:
                        # Verifica se il materiale esiste già per questa macchina
                        exists = db.execute(
                            "SELECT id FROM materials WHERE machine_id = ? AND name = ?",
                            (machine['id'], mat['name'])
                        ).fetchone()
                        if not exists:
                            db.execute(
                                "INSERT INTO materials (machine_id, name, factor) VALUES (?, ?, ?)",
                                (machine['id'], mat['name'], mat['factor'])
                            )
                # Elimina materiali orfani
                db.execute("DELETE FROM materials WHERE machine_id IS NULL")
        except Exception as e:
            print(f"[MIGRAZIONE] Errore assegnazione materiali: {e}")
            
        db.commit()

# --- HELPER VALIDAZIONE ---
def validate_positive_number(value, field_name, allow_zero=False):
    try:
        num = float(value)
        if allow_zero and num < 0:
            return None, f"{field_name} non può essere negativo"
        if not allow_zero and num <= 0:
            return None, f"{field_name} deve essere maggiore di zero"
        return num, None
    except (TypeError, ValueError):
        return None, f"{field_name} deve essere un numero valido"

def validate_required_string(value, field_name):
    if not value or not str(value).strip():
        return None, f"{field_name} è obbligatorio"
    return str(value).strip(), None

# --- LOGICA CALCOLO ---
def get_tool_status_logic(tool_id, base_target):
    db = get_db()
    logs = db.execute("SELECT * FROM history WHERE tool_id = ?", (tool_id,)).fetchall()
    
    used_norm = 0.0
    used_real = 0.0
    extensions_norm = 0.0
    
    for log in logs:
        mins = log['delta_minutes']
        fact = log['material_factor'] if log['material_factor'] else 1.0
        
        if log['action_type'] == 'WORK':
            used_norm += (mins * fact)
            used_real += mins
        elif log['action_type'] == 'EXT':
            extensions_norm += (mins * fact)

    total_capacity = base_target + extensions_norm
    remaining_norm = total_capacity - used_norm
    
    percent = (remaining_norm / total_capacity) * 100 if total_capacity > 0 else 0
    is_overtime = remaining_norm < 0
        
    return {
        "used_norm": round(used_norm, 1),
        "used_real": round(used_real, 1),
        "extensions_norm": round(extensions_norm, 1),
        "total_capacity": round(total_capacity, 1),
        "remaining_norm": round(remaining_norm, 1),
        "percent": round(percent, 1),
        "base_target": base_target,
        "is_overtime": is_overtime
    }

# --- ROUTES API ---

@app.route('/')
def index(): 
    return render_template('index.html')

# =====================================================
# API MACCHINE (NUOVE)
# =====================================================

@app.route('/api/machines', methods=['GET'])
def get_machines():
    """Lista tutte le macchine con statistiche"""
    try:
        db = get_db()
        machines = db.execute("SELECT * FROM machines ORDER BY name ASC").fetchall()
        
        result = []
        for m in machines:
            # Conta utensili e stati
            tools = db.execute("SELECT * FROM tools WHERE machine_id = ?", (m['id'],)).fetchall()
            
            critical = 0
            warning = 0
            ok = 0
            overtime = 0
            
            for t in tools:
                status = get_tool_status_logic(t['id'], t['target_life_minutes'])
                if status['is_overtime']:
                    overtime += 1
                elif status['percent'] < 20:
                    critical += 1
                elif status['percent'] < 50:
                    warning += 1
                else:
                    ok += 1
            
            result.append({
                'id': m['id'],
                'name': m['name'],
                'description': m['description'],
                'created_at': m['created_at'],
                'stats': {
                    'total_tools': len(tools),
                    'critical': critical,
                    'warning': warning,
                    'ok': ok,
                    'overtime': overtime
                }
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/machines', methods=['POST'])
def add_machine():
    """Aggiungi nuova macchina con materiali default"""
    data = request.json
    
    name, err = validate_required_string(data.get('name'), 'Nome macchina')
    if err: return jsonify({"error": err}), 400
    
    description = data.get('description', '')
    
    try:
        db = get_db()
        cursor = db.execute("INSERT INTO machines (name, description) VALUES (?, ?)", (name, description))
        machine_id = cursor.lastrowid
        
        # Crea materiali default per questa macchina
        default_materials = [
            ('Titanio / Inconel (Worst Case)', 1.0),
            ('Acciaio Inox (Hard)', 0.6),
            ('Acciaio C45 (Medium)', 0.4),
            ('Alluminio / Plastica (Soft)', 0.25)
        ]
        for mat_name, factor in default_materials:
            db.execute("INSERT INTO materials (machine_id, name, factor) VALUES (?, ?, ?)", 
                      (machine_id, mat_name, factor))
        
        db.commit()
        return jsonify({"success": True, "machine_id": machine_id})
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Macchina '{name}' già esistente"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/machines/<int:id>', methods=['PUT'])
def update_machine(id):
    """Modifica macchina"""
    data = request.json
    
    name, err = validate_required_string(data.get('name'), 'Nome macchina')
    if err: return jsonify({"error": err}), 400
    
    description = data.get('description', '')
    
    try:
        db = get_db()
        result = db.execute("UPDATE machines SET name = ?, description = ? WHERE id = ?", 
                           (name, description, id))
        if result.rowcount == 0:
            return jsonify({"error": "Macchina non trovata"}), 404
        db.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Nome '{name}' già in uso"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/machines/<int:id>', methods=['DELETE'])
def delete_machine(id):
    """Elimina macchina e tutti i suoi utensili"""
    try:
        db = get_db()
        
        machine = db.execute("SELECT * FROM machines WHERE id = ?", (id,)).fetchone()
        if not machine:
            return jsonify({"error": "Macchina non trovata"}), 404
        
        # Conta utensili
        tools_count = db.execute("SELECT COUNT(*) as c FROM tools WHERE machine_id = ?", (id,)).fetchone()['c']
        
        # Elimina (CASCADE eliminerà anche tools e history)
        db.execute("DELETE FROM machines WHERE id = ?", (id,))
        db.commit()
        
        return jsonify({"success": True, "deleted_tools": tools_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/machines/<int:id>', methods=['GET'])
def get_machine(id):
    """Dettagli singola macchina"""
    try:
        db = get_db()
        machine = db.execute("SELECT * FROM machines WHERE id = ?", (id,)).fetchone()
        if not machine:
            return jsonify({"error": "Macchina non trovata"}), 404
        return jsonify(dict(machine))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# API TOOLS (Modificate per machine_id)
# =====================================================

@app.route('/api/machines/<int:machine_id>/tools', methods=['GET'])
def get_tools(machine_id):
    """Lista utensili di una macchina"""
    try:
        db = get_db()
        tools = db.execute("SELECT * FROM tools WHERE machine_id = ? ORDER BY position ASC", 
                          (machine_id,)).fetchall()
        tools_list = []
        for t in tools:
            status = get_tool_status_logic(t['id'], t['target_life_minutes'])
            tool_dict = dict(t)
            tool_dict['status_data'] = status
            tools_list.append(tool_dict)
        return jsonify(tools_list)
    except Exception as e:
        return jsonify({"error": f"Errore caricamento utensili: {str(e)}"}), 500

@app.route('/api/machines/<int:machine_id>/tools', methods=['POST'])
def add_tool(machine_id):
    """Aggiungi utensile a una macchina"""
    data = request.json
    
    alias, err = validate_required_string(data.get('alias'), 'Alias')
    if err: return jsonify({"error": err}), 400
    
    try:
        duplo = int(data.get('duplo', 1))
        if duplo < 1: duplo = 1
    except (TypeError, ValueError):
        duplo = 1
    
    position = data.get('position')
    if position is not None and position != '':
        try:
            position = int(position)
        except (TypeError, ValueError):
            position = None
    else:
        position = None
    
    target, err = validate_positive_number(data.get('target', 100), 'Target')
    if err: return jsonify({"error": err}), 400
    
    db = get_db()
    try:
        # Verifica che la macchina esista
        machine = db.execute("SELECT id FROM machines WHERE id = ?", (machine_id,)).fetchone()
        if not machine:
            return jsonify({"error": "Macchina non trovata"}), 404
        
        db.execute("INSERT INTO tools (machine_id, alias, duplo, position, target_life_minutes) VALUES (?, ?, ?, ?, ?)",
                   (machine_id, alias, duplo, position, target))
        db.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Utensile {alias} D{duplo} già esistente su questa macchina"}), 400
    except Exception as e: 
        return jsonify({"error": str(e)}), 400

@app.route('/api/tools/<int:id>/update_target', methods=['POST'])
def update_target(id):
    data = request.json
    
    new_target, err = validate_positive_number(data.get('target'), 'Target')
    if err: return jsonify({"error": err}), 400
    
    try:
        db = get_db()
        result = db.execute("UPDATE tools SET target_life_minutes = ? WHERE id = ?", (new_target, id))
        if result.rowcount == 0:
            return jsonify({"error": "Utensile non trovato"}), 404
        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tools/<int:id>', methods=['PUT'])
def update_tool_details(id):
    data = request.json
    
    alias, err = validate_required_string(data.get('alias'), 'Alias')
    if err: return jsonify({"error": err}), 400
    
    try:
        duplo = int(data.get('duplo', 1))
        if duplo < 1: duplo = 1
    except (TypeError, ValueError):
        duplo = 1
    
    position = data.get('position')
    if position is not None and position != '':
        try:
            position = int(position)
        except (TypeError, ValueError):
            position = None
    else:
        position = None
    
    try:
        db = get_db()
        result = db.execute('''UPDATE tools 
                      SET alias = ?, position = ?, duplo = ? 
                      WHERE id = ?''', 
                   (alias, position, duplo, id))
        if result.rowcount == 0:
            return jsonify({"error": "Utensile non trovato"}), 404
        db.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Utensile {alias} D{duplo} già esistente su questa macchina"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tools/<int:id>', methods=['DELETE'])
def delete_tool(id):
    try:
        db = get_db()
        tool = db.execute("SELECT id FROM tools WHERE id = ?", (id,)).fetchone()
        if not tool:
            return jsonify({"error": "Utensile non trovato"}), 404
        
        db.execute("DELETE FROM history WHERE tool_id = ?", (id,))
        db.execute("DELETE FROM tools WHERE id = ?", (id,))
        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# MATERIALS API (per macchina)
@app.route('/api/machines/<int:machine_id>/materials', methods=['GET'])
def get_materials(machine_id):
    try:
        db = get_db()
        materials = db.execute(
            "SELECT * FROM materials WHERE machine_id = ? ORDER BY factor DESC", 
            (machine_id,)
        ).fetchall()
        return jsonify([dict(m) for m in materials])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/machines/<int:machine_id>/materials', methods=['POST'])
def add_material(machine_id):
    data = request.json
    
    name, err = validate_required_string(data.get('name'), 'Nome materiale')
    if err: return jsonify({"error": err}), 400
    
    factor, err = validate_positive_number(data.get('factor'), 'Fattore')
    if err: return jsonify({"error": err}), 400
    
    try:
        db = get_db()
        db.execute("INSERT INTO materials (machine_id, name, factor) VALUES (?, ?, ?)", 
                  (machine_id, name, factor))
        db.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Materiale già esistente per questa macchina"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/materials/<int:id>', methods=['PUT'])
def update_material(id):
    data = request.json
    
    name, err = validate_required_string(data.get('name'), 'Nome materiale')
    if err: return jsonify({"error": err}), 400
    
    factor, err = validate_positive_number(data.get('factor'), 'Fattore')
    if err: return jsonify({"error": err}), 400
    
    try:
        db = get_db()
        result = db.execute("UPDATE materials SET name = ?, factor = ? WHERE id = ?", 
                           (name, factor, id))
        if result.rowcount == 0:
            return jsonify({"error": "Materiale non trovato"}), 404
        db.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Nome materiale già esistente per questa macchina"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/materials/<int:id>', methods=['DELETE'])
def delete_material(id):
    try:
        db = get_db()
        result = db.execute("DELETE FROM materials WHERE id = ?", (id,))
        if result.rowcount == 0:
            return jsonify({"error": "Materiale non trovato"}), 404
        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ACTIONS API
@app.route('/api/tools/<int:id>/session', methods=['POST'])
def add_session(id):
    data = request.json
    
    minutes, err = validate_positive_number(data.get('minutes'), 'Minuti')
    if err: return jsonify({"error": err}), 400
    
    factor, err = validate_positive_number(data.get('factor'), 'Fattore materiale')
    if err: return jsonify({"error": err}), 400
    
    mat_name = data.get('mat_name', 'Sconosciuto')
    
    try:
        db = get_db()
        tool = db.execute("SELECT id FROM tools WHERE id = ?", (id,)).fetchone()
        if not tool:
            return jsonify({"error": "Utensile non trovato"}), 404
        
        db.execute("INSERT INTO history (tool_id, action_type, delta_minutes, material_factor, material_name, final_norm_usage) VALUES (?, 'WORK', ?, ?, ?, 0)", 
                   (id, minutes, factor, mat_name))
        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tools/<int:id>/extend', methods=['POST'])
def extend_tool(id):
    data = request.json
    
    minutes, err = validate_positive_number(data.get('minutes'), 'Minuti estensione')
    if err: return jsonify({"error": err}), 400
    
    factor, err = validate_positive_number(data.get('factor'), 'Fattore materiale')
    if err: return jsonify({"error": err}), 400
    
    mat_name = data.get('mat_name', 'Sconosciuto')
    
    try:
        db = get_db()
        tool = db.execute("SELECT id FROM tools WHERE id = ?", (id,)).fetchone()
        if not tool:
            return jsonify({"error": "Utensile non trovato"}), 404
        
        db.execute("INSERT INTO history (tool_id, action_type, delta_minutes, material_factor, material_name, final_norm_usage) VALUES (?, 'EXT', ?, ?, ?, 0)", 
                   (id, minutes, factor, mat_name))
        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tools/<int:id>/reset', methods=['POST'])
def reset_tool(id):
    data = request.json
    end_status = data.get('status', 'OK')
    
    valid_statuses = ['OK', 'BROKEN', 'EARLY']
    if end_status not in valid_statuses:
        end_status = 'OK'
    
    db = get_db()
    
    try:
        db.execute("BEGIN IMMEDIATE")
        
        tool = db.execute("SELECT * FROM tools WHERE id = ?", (id,)).fetchone()
        if not tool:
            db.rollback()
            return jsonify({"error": "Utensile non trovato"}), 404
        
        status = get_tool_status_logic(id, tool['target_life_minutes'])
        
        if status['used_norm'] > 0:
            db.execute('''INSERT INTO completed_cycles 
                          (machine_id, alias, duplo, total_real_minutes, total_norm_minutes, target_at_time, end_status) 
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       (tool['machine_id'], tool['alias'], tool['duplo'], status['used_real'], status['used_norm'], tool['target_life_minutes'], end_status))
        
        db.execute("DELETE FROM history WHERE tool_id = ?", (id,))
        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500

# =====================================================
# REPORT API (Modificate per machine_id)
# =====================================================

@app.route('/api/tools/<int:id>/sessions', methods=['GET'])
def get_tool_sessions(id):
    try:
        db = get_db()
        tool = db.execute("SELECT * FROM tools WHERE id = ?", (id,)).fetchone()
        if not tool:
            return jsonify({"error": "Utensile non trovato"}), 404
        
        sessions = db.execute('''
            SELECT id, action_type, delta_minutes, material_factor, material_name, 
                   created_at, (delta_minutes * material_factor) as norm_minutes
            FROM history 
            WHERE tool_id = ? 
            ORDER BY created_at DESC
        ''', (id,)).fetchall()
        
        return jsonify({
            "tool": dict(tool),
            "sessions": [dict(s) for s in sessions],
            "summary": {
                "total_sessions": len([s for s in sessions if s['action_type'] == 'WORK']),
                "total_extensions": len([s for s in sessions if s['action_type'] == 'EXT'])
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/machines/<int:machine_id>/analytics/<alias>', methods=['GET'])
def get_analytics(machine_id, alias):
    try:
        db = get_db()
        cycles = db.execute('''SELECT * FROM completed_cycles 
                               WHERE machine_id = ? AND alias = ? 
                               ORDER BY end_date DESC LIMIT 50''', (machine_id, alias)).fetchall()
        
        if not cycles: 
            return jsonify({"has_data": False})
        
        total_cycles = len(cycles)
        broken_count = sum(1 for c in cycles if c['end_status'] == 'BROKEN')
        early_count = sum(1 for c in cycles if c['end_status'] == 'EARLY')
        ok_count = sum(1 for c in cycles if c['end_status'] == 'OK')
        
        valid_cycles = [c['total_norm_minutes'] for c in cycles if c['end_status'] in ['OK', 'BROKEN']]
        
        if valid_cycles:
            avg_life = np.mean(valid_cycles)
            std_life = np.std(valid_cycles)
            min_life = min(valid_cycles)
            max_life = max(valid_cycles)
        else:
            avg_life = std_life = min_life = max_life = 0
        
        trend = "STABILE"
        if len(valid_cycles) >= 6:
            mid = len(valid_cycles) // 2
            recent_avg = np.mean(valid_cycles[:mid])
            older_avg = np.mean(valid_cycles[mid:])
            diff_pct = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
            if diff_pct > 10:
                trend = "IN MIGLIORAMENTO ↑"
            elif diff_pct < -10:
                trend = "IN PEGGIORAMENTO ↓"
        
        suggestion = "Dati insufficienti"
        latest_target = cycles[0]['target_at_time']
        
        if total_cycles >= 3:
            if broken_count / total_cycles > 0.3: 
                suggestion = f"⚠️ ALTO RISCHIO: Si rompe spesso ({broken_count}/{total_cycles}). Abbassa il target (consigliato: {int(avg_life * 0.85)} min)."
            elif avg_life > latest_target * 1.15 and broken_count == 0:
                suggestion = f"✅ OTTIMALE: L'utensile regge bene. Puoi alzare il target fino a {int(avg_life * 0.95)} min."
            elif std_life > avg_life * 0.3:
                suggestion = f"⚡ INCONSISTENTE: Alta variabilità (σ={std_life:.1f}). Verifica qualità inserti o parametri di taglio."
            else:
                suggestion = "ℹ️ STABILE: Il target attuale sembra corretto."

        return jsonify({
            "has_data": True,
            "history": [dict(c) for c in cycles],
            "stats": {
                "avg_life": round(avg_life, 1),
                "std_life": round(std_life, 1),
                "min_life": round(min_life, 1),
                "max_life": round(max_life, 1),
                "broken_count": broken_count,
                "early_count": early_count,
                "ok_count": ok_count,
                "total_cycles": total_cycles,
                "broken_rate": f"{broken_count}/{total_cycles}",
                "trend": trend,
                "suggestion": suggestion
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/machines/<int:machine_id>/analytics/<alias>/by_material', methods=['GET'])
def get_analytics_by_material(machine_id, alias):
    try:
        db = get_db()
        
        tools = db.execute("SELECT id FROM tools WHERE machine_id = ? AND alias = ?", (machine_id, alias)).fetchall()
        tool_ids = [t['id'] for t in tools]
        
        if not tool_ids:
            return jsonify({"has_data": False})
        
        material_stats = {}
        
        placeholders = ','.join('?' * len(tool_ids))
        sessions = db.execute(f'''
            SELECT material_name, material_factor, delta_minutes, 
                   (delta_minutes * material_factor) as norm_minutes
            FROM history 
            WHERE tool_id IN ({placeholders}) AND action_type = 'WORK'
        ''', tool_ids).fetchall()
        
        for s in sessions:
            mat = s['material_name'] or 'Sconosciuto'
            if mat not in material_stats:
                material_stats[mat] = {
                    'total_real_minutes': 0,
                    'total_norm_minutes': 0,
                    'session_count': 0,
                    'factor': s['material_factor']
                }
            material_stats[mat]['total_real_minutes'] += s['delta_minutes']
            material_stats[mat]['total_norm_minutes'] += s['norm_minutes']
            material_stats[mat]['session_count'] += 1
        
        result = []
        for mat, stats in material_stats.items():
            result.append({
                'material': mat,
                'factor': stats['factor'],
                'total_real_minutes': round(stats['total_real_minutes'], 1),
                'total_norm_minutes': round(stats['total_norm_minutes'], 1),
                'session_count': stats['session_count'],
                'avg_session_minutes': round(stats['total_real_minutes'] / stats['session_count'], 1) if stats['session_count'] > 0 else 0
            })
        
        result.sort(key=lambda x: x['total_norm_minutes'], reverse=True)
        
        return jsonify({
            "has_data": len(result) > 0,
            "by_material": result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/machines/<int:machine_id>/analytics/<alias>/by_duplo', methods=['GET'])
def get_analytics_by_duplo(machine_id, alias):
    try:
        db = get_db()
        
        cycles = db.execute('''
            SELECT duplo, end_status, total_norm_minutes, total_real_minutes, target_at_time
            FROM completed_cycles 
            WHERE machine_id = ? AND alias = ?
        ''', (machine_id, alias)).fetchall()
        
        if not cycles:
            return jsonify({"has_data": False})
        
        duplo_stats = {}
        
        for c in cycles:
            d = c['duplo']
            if d not in duplo_stats:
                duplo_stats[d] = {'cycles': [], 'broken': 0, 'ok': 0, 'early': 0}
            duplo_stats[d]['cycles'].append(c['total_norm_minutes'])
            if c['end_status'] == 'BROKEN':
                duplo_stats[d]['broken'] += 1
            elif c['end_status'] == 'OK':
                duplo_stats[d]['ok'] += 1
            else:
                duplo_stats[d]['early'] += 1
        
        result = []
        for duplo, stats in sorted(duplo_stats.items()):
            cycles_list = stats['cycles']
            total = len(cycles_list)
            result.append({
                'duplo': duplo,
                'total_cycles': total,
                'avg_life': round(np.mean(cycles_list), 1) if cycles_list else 0,
                'std_life': round(np.std(cycles_list), 1) if len(cycles_list) > 1 else 0,
                'min_life': round(min(cycles_list), 1) if cycles_list else 0,
                'max_life': round(max(cycles_list), 1) if cycles_list else 0,
                'broken': stats['broken'],
                'ok': stats['ok'],
                'early': stats['early'],
                'broken_rate_pct': round(stats['broken'] / total * 100, 1) if total > 0 else 0
            })
        
        if len(result) > 1:
            best = max(result, key=lambda x: x['avg_life'])
            worst = min(result, key=lambda x: x['avg_life'])
            comparison = f"D{best['duplo']} è il migliore (media {best['avg_life']} min), D{worst['duplo']} il peggiore (media {worst['avg_life']} min)"
        else:
            comparison = "Serve più di un duplo per confrontare"
        
        return jsonify({
            "has_data": True,
            "by_duplo": result,
            "comparison": comparison
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/machines/<int:machine_id>/dashboard', methods=['GET'])
def get_machine_dashboard(machine_id):
    try:
        db = get_db()
        
        tools = db.execute("SELECT * FROM tools WHERE machine_id = ?", (machine_id,)).fetchall()
        
        critical_count = 0
        warning_count = 0
        ok_count = 0
        overtime_count = 0
        
        tools_status = []
        for t in tools:
            status = get_tool_status_logic(t['id'], t['target_life_minutes'])
            tools_status.append({
                'id': t['id'],
                'alias': t['alias'],
                'duplo': t['duplo'],
                'position': t['position'],
                'percent': status['percent'],
                'remaining': status['remaining_norm'],
                'is_overtime': status['is_overtime']
            })
            
            if status['is_overtime']:
                overtime_count += 1
            elif status['percent'] < 20:
                critical_count += 1
            elif status['percent'] < 50:
                warning_count += 1
            else:
                ok_count += 1
        
        one_month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        recent_cycles = db.execute('''
            SELECT end_status, COUNT(*) as cnt 
            FROM completed_cycles 
            WHERE machine_id = ? AND end_date >= ?
            GROUP BY end_status
        ''', (machine_id, one_month_ago)).fetchall()
        
        monthly_stats = {'OK': 0, 'BROKEN': 0, 'EARLY': 0}
        for r in recent_cycles:
            if r['end_status'] in monthly_stats:
                monthly_stats[r['end_status']] = r['cnt']
        
        problematic = db.execute('''
            SELECT alias, COUNT(*) as broken_count
            FROM completed_cycles 
            WHERE machine_id = ? AND end_status = 'BROKEN' AND end_date >= ?
            GROUP BY alias
            ORDER BY broken_count DESC
            LIMIT 5
        ''', (machine_id, one_month_ago)).fetchall()
        
        return jsonify({
            "total_tools": len(tools),
            "status_summary": {
                "critical": critical_count,
                "warning": warning_count,
                "ok": ok_count,
                "overtime": overtime_count
            },
            "monthly_cycles": monthly_stats,
            "monthly_total": sum(monthly_stats.values()),
            "problematic_tools": [dict(p) for p in problematic],
            "tools_by_status": sorted(tools_status, key=lambda x: x['percent'])
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Dashboard globale (tutte le macchine)
@app.route('/api/dashboard/global', methods=['GET'])
def get_global_dashboard():
    try:
        db = get_db()
        machines = db.execute("SELECT * FROM machines").fetchall()
        
        total_tools = 0
        total_critical = 0
        total_overtime = 0
        
        machines_summary = []
        for m in machines:
            tools = db.execute("SELECT * FROM tools WHERE machine_id = ?", (m['id'],)).fetchall()
            
            critical = 0
            overtime = 0
            for t in tools:
                status = get_tool_status_logic(t['id'], t['target_life_minutes'])
                if status['is_overtime']:
                    overtime += 1
                elif status['percent'] < 20:
                    critical += 1
            
            total_tools += len(tools)
            total_critical += critical
            total_overtime += overtime
            
            machines_summary.append({
                'id': m['id'],
                'name': m['name'],
                'tools': len(tools),
                'critical': critical,
                'overtime': overtime
            })
        
        one_month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        monthly_broken = db.execute('''
            SELECT COUNT(*) as cnt FROM completed_cycles 
            WHERE end_status = 'BROKEN' AND end_date >= ?
        ''', (one_month_ago,)).fetchone()['cnt']
        
        return jsonify({
            "total_machines": len(machines),
            "total_tools": total_tools,
            "total_critical": total_critical,
            "total_overtime": total_overtime,
            "monthly_broken": monthly_broken,
            "machines": machines_summary
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tools/<int:id>/prediction', methods=['GET'])
def get_tool_prediction(id):
    try:
        db = get_db()
        
        tool = db.execute("SELECT * FROM tools WHERE id = ?", (id,)).fetchone()
        if not tool:
            return jsonify({"error": "Utensile non trovato"}), 404
        
        status = get_tool_status_logic(id, tool['target_life_minutes'])
        
        sessions = db.execute('''
            SELECT delta_minutes, material_factor, created_at
            FROM history 
            WHERE tool_id = ? AND action_type = 'WORK'
            ORDER BY created_at ASC
        ''', (id,)).fetchall()
        
        if len(sessions) < 2:
            return jsonify({
                "has_prediction": False,
                "message": "Servono almeno 2 sessioni per calcolare una previsione"
            })
        
        first_session = datetime.fromisoformat(sessions[0]['created_at'].replace('Z', '+00:00').replace(' ', 'T'))
        last_session = datetime.fromisoformat(sessions[-1]['created_at'].replace('Z', '+00:00').replace(' ', 'T'))
        
        elapsed_days = (last_session - first_session).total_seconds() / 86400
        if elapsed_days < 0.01:
            elapsed_days = 1
        
        usage_rate_per_day = status['used_norm'] / elapsed_days if elapsed_days > 0 else 0
        
        if usage_rate_per_day <= 0:
            return jsonify({
                "has_prediction": False,
                "message": "Ritmo di usura non calcolabile"
            })
        
        remaining_days = status['remaining_norm'] / usage_rate_per_day if status['remaining_norm'] > 0 else 0
        predicted_date = datetime.now() + timedelta(days=remaining_days)
        
        return jsonify({
            "has_prediction": True,
            "current_status": status,
            "usage_rate_per_day": round(usage_rate_per_day, 2),
            "remaining_days": round(remaining_days, 1),
            "predicted_end_date": predicted_date.strftime('%Y-%m-%d'),
            "predicted_end_date_formatted": predicted_date.strftime('%d/%m/%Y'),
            "confidence": "ALTA" if len(sessions) >= 5 else "MEDIA" if len(sessions) >= 3 else "BASSA"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# EXPORT CSV
@app.route('/api/machines/<int:machine_id>/export/cycles', methods=['GET'])
def export_cycles_csv(machine_id):
    try:
        db = get_db()
        machine = db.execute("SELECT name FROM machines WHERE id = ?", (machine_id,)).fetchone()
        machine_name = machine['name'] if machine else 'Unknown'
        
        cycles = db.execute('''
            SELECT alias, duplo, total_real_minutes, total_norm_minutes, 
                   target_at_time, end_status, end_date
            FROM completed_cycles 
            WHERE machine_id = ?
            ORDER BY end_date DESC
        ''', (machine_id,)).fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        
        writer.writerow(['Alias', 'Duplo', 'Minuti Reali', 'Minuti Normalizzati', 
                        'Target', 'Stato Finale', 'Data Fine'])
        
        for c in cycles:
            writer.writerow([
                c['alias'], c['duplo'], c['total_real_minutes'], c['total_norm_minutes'],
                c['target_at_time'], c['end_status'], c['end_date']
            ])
        
        output.seek(0)
        filename = f"tlm_{machine_name}_cycles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/machines/<int:machine_id>/export/tools', methods=['GET'])
def export_tools_csv(machine_id):
    try:
        db = get_db()
        machine = db.execute("SELECT name FROM machines WHERE id = ?", (machine_id,)).fetchone()
        machine_name = machine['name'] if machine else 'Unknown'
        
        tools = db.execute("SELECT * FROM tools WHERE machine_id = ? ORDER BY position ASC", (machine_id,)).fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        
        writer.writerow(['Posizione', 'Alias', 'Duplo', 'Target', 
                        'Usato Norm', 'Usato Reale', 'Estensioni', 
                        'Capacità Totale', 'Rimanente', 'Percentuale', 'Overtime'])
        
        for t in tools:
            status = get_tool_status_logic(t['id'], t['target_life_minutes'])
            writer.writerow([
                t['position'] or 'MAG', t['alias'], t['duplo'], t['target_life_minutes'],
                status['used_norm'], status['used_real'], status['extensions_norm'],
                status['total_capacity'], status['remaining_norm'], status['percent'],
                'SI' if status['is_overtime'] else 'NO'
            ])
        
        output.seek(0)
        filename = f"tlm_{machine_name}_tools_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API per backup manuale
@app.route('/api/backup', methods=['POST'])
def manual_backup():
    """Esegue backup manuale"""
    try:
        success = backup_database()
        if success:
            return jsonify({"success": True, "message": f"Backup salvato in {BACKUP_PATH}"})
        else:
            return jsonify({"error": "Backup fallito - controlla i log"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/backup/status', methods=['GET'])
def backup_status():
    """Stato backup"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        backup_filename = f"tlm_data_backup_{today}.db"
        backup_filepath = os.path.join(BACKUP_PATH, backup_filename)
        
        backups = []
        if os.path.exists(BACKUP_PATH):
            for f in sorted(os.listdir(BACKUP_PATH), reverse=True)[:10]:
                if f.startswith("tlm_data_backup_") and f.endswith(".db"):
                    filepath = os.path.join(BACKUP_PATH, f)
                    size_mb = os.path.getsize(filepath) / (1024 * 1024)
                    backups.append({
                        "filename": f,
                        "size_mb": round(size_mb, 2),
                        "date": f.replace("tlm_data_backup_", "").replace(".db", "")
                    })
        
        return jsonify({
            "backup_path": BACKUP_PATH,
            "today_backup_exists": os.path.exists(backup_filepath),
            "recent_backups": backups
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def start_server():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    if not os.path.exists(DB_NAME): 
        init_db()
    else: 
        init_db()
    
    # === BACKUP AUTOMATICO ALL'AVVIO ===
    print("=" * 50)
    print("TLM Manager V6 - Avvio")
    print("=" * 50)
    backup_database()
    print("=" * 50)
    
    t = threading.Thread(target=start_server)
    t.daemon = True
    t.start()
    webview.create_window("TLM Manager V6", "http://127.0.0.1:5000", width=1400, height=900)
    webview.start()