import os
import threading
from datetime import datetime, timedelta
 
import webview
from flask import jsonify
 
from app import app, get_db, get_tool_status_logic, DB_NAME, init_db, backup_database, start_server
 
 
def get_tool_prediction_v2(id):
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
 
        sessions_count = len(sessions)
        if sessions_count < 2:
            return jsonify({
                "has_prediction": False,
                "sessions_count": sessions_count,
                "message": "Servono almeno 2 sessioni per calcolare una previsione"
            })
 
        first_session = datetime.fromisoformat(
            sessions[0]['created_at'].replace('Z', '+00:00').replace(' ', 'T')
        )
        last_session = datetime.fromisoformat(
            sessions[-1]['created_at'].replace('Z', '+00:00').replace(' ', 'T')
        )
 
        elapsed_days = (last_session - first_session).total_seconds() / 86400
        if elapsed_days < 0.01:
            elapsed_days = 1
 
        usage_rate_per_day = status['used_norm'] / elapsed_days if elapsed_days > 0 else 0
 
        if usage_rate_per_day <= 0:
            return jsonify({
                "has_prediction": False,
                "sessions_count": sessions_count,
                "message": "Ritmo di usura non calcolabile"
            })
 
        remaining_days = status['remaining_norm'] / usage_rate_per_day if status['remaining_norm'] > 0 else 0
        predicted_date = datetime.now() + timedelta(days=remaining_days)
 
        return jsonify({
            "has_prediction": True,
            "sessions_count": sessions_count,
            "current_status": status,
            "usage_rate_per_day": round(usage_rate_per_day, 2),
            "remaining_days": round(remaining_days, 1),
            "predicted_end_date": predicted_date.strftime('%Y-%m-%d'),
            "predicted_end_date_formatted": predicted_date.strftime('%d/%m/%Y'),
            "confidence": "ALTA" if sessions_count >= 5 else "MEDIA" if sessions_count >= 3 else "BASSA"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
 
 
# Override prediction endpoint with UX-enhanced payload
app.view_functions['get_tool_prediction'] = get_tool_prediction_v2
 
 
if __name__ == '__main__':
    if not os.path.exists(DB_NAME):
        init_db()
    else:
        init_db()
 
    # === BACKUP AUTOMATICO ALL'AVVIO ===
    print("=" * 50)
    print("TLM Manager V6.1 - Avvio")
    print("=" * 50)
    backup_database()
    print("=" * 50)
 
    t = threading.Thread(target=start_server)
    t.daemon = True
    t.start()
    webview.create_window("TLM Manager V6.1", "http://127.0.0.1:5000", width=1400, height=900)
    webview.start()
