"""
Client API per comunicare con TLM Service Flask
"""
import requests
from typing import Optional, Dict, List
from config import TLM_API_BASE_URL


class TLMAPIClient:
    """Client per interagire con l'API Flask TLM"""
    
    def __init__(self, base_url: str = TLM_API_BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    # === MACCHINE ===
    
    def get_machines(self) -> List[Dict]:
        """Ottieni lista macchine"""
        try:
            response = self.session.get(f"{self.base_url}/api/machines")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Errore get_machines: {e}")
            return []
    
    def get_machine(self, machine_id: int) -> Optional[Dict]:
        """Ottieni info singola macchina"""
        try:
            response = self.session.get(f"{self.base_url}/api/machines/{machine_id}")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Errore get_machine: {e}")
            return None
    
    # === UTENSILI ===
    
    def get_tools(self, machine_id: int) -> List[Dict]:
        """Ottieni lista utensili per macchina"""
        try:
            response = self.session.get(f"{self.base_url}/api/machines/{machine_id}/tools")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Errore get_tools: {e}")
            return []
    
    def get_tool_info(self, tool_id: int) -> Optional[Dict]:
        """Ottieni info dettagliate utensile (non esiste nella API, calcoliamo da lista)"""
        # L'API non ha endpoint GET /api/tools/<id>
        # Dobbiamo cercare l'utensile nella lista
        return None
    
    # === AZIONI UTENSILI ===
    
    def add_work_session(self, tool_id: int, delta_minutes: float, 
                        material_name: Optional[str] = None, 
                        material_factor: float = 1.0) -> Dict:
        """
        Aggiungi sessione di lavoro
        POST /api/tools/<id>/session
        """
        try:
            # IMPORTANTE: Flask si aspetta questi nomi esatti
            payload = {
                "minutes": delta_minutes,      # NON delta_minutes
                "factor": material_factor,     # NON material_factor
                "mat_name": material_name or "Sconosciuto"  # NON material_name
            }
            
            response = self.session.post(
                f"{self.base_url}/api/tools/{tool_id}/session",
                json=payload
            )
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}
    
    def extend_tool_life(self, tool_id: int, delta_minutes: float,
                        material_name: Optional[str] = None,
                        material_factor: float = 1.0) -> Dict:
        """
        Estendi vita utensile
        POST /api/tools/<id>/extend
        """
        try:
            # IMPORTANTE: Flask si aspetta questi nomi esatti
            payload = {
                "minutes": delta_minutes,      # NON delta_minutes
                "factor": material_factor,     # NON material_factor
                "mat_name": material_name or "Sconosciuto"  # NON material_name
            }
            
            response = self.session.post(
                f"{self.base_url}/api/tools/{tool_id}/extend",
                json=payload
            )
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}
    
    def reset_tool(self, tool_id: int, end_status: str = "OK") -> Dict:
        """
        Reset utensile
        POST /api/tools/<id>/reset
        end_status: 'OK', 'BROKEN', 'EARLY'
        """
        try:
            payload = {"end_status": end_status}
            response = self.session.post(
                f"{self.base_url}/api/tools/{tool_id}/reset",
                json=payload
            )
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}
    
    def update_tool_target(self, tool_id: int, new_target: int) -> Dict:
        """
        Aggiorna target vita utensile
        POST /api/tools/<id>/update_target
        """
        try:
            payload = {"new_target": new_target}
            response = self.session.post(
                f"{self.base_url}/api/tools/{tool_id}/update_target",
                json=payload
            )
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}
    
    # === MATERIALI ===
    
    def get_materials(self, machine_id: int) -> List[Dict]:
        """Ottieni lista materiali per macchina"""
        try:
            response = self.session.get(f"{self.base_url}/api/machines/{machine_id}/materials")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Errore get_materials: {e}")
            return []
    
    # === DASHBOARD E ANALYTICS ===
    
    def get_machine_dashboard(self, machine_id: int) -> Optional[Dict]:
        """Ottieni dashboard macchina"""
        try:
            response = self.session.get(f"{self.base_url}/api/machines/{machine_id}/dashboard")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Errore get_dashboard: {e}")
            return None
    
    def get_tool_prediction(self, tool_id: int) -> Optional[Dict]:
        """Ottieni previsione durata utensile"""
        try:
            response = self.session.get(f"{self.base_url}/api/tools/{tool_id}/prediction")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Errore get_prediction: {e}")
            return None
    
    # === UTILITY ===
    
    def health_check(self) -> bool:
        """Verifica connessione API"""
        try:
            response = self.session.get(f"{self.base_url}/api/machines", timeout=5)
            return response.status_code == 200
        except:
            return False


# === FORMATTAZIONE MESSAGGI ===

def format_tool_status(tool: Dict) -> str:
    """Formatta info utensile per Telegram"""
    alias = tool.get('alias', 'N/A')
    duplo = tool.get('duplo', 1)
    position = tool.get('position', 'N/A')
    
    used_norm = tool.get('used_norm', 0)
    remaining_norm = tool.get('remaining_norm', 0)
    total_capacity = tool.get('total_capacity', 0)
    percent = tool.get('percent', 0)
    is_overtime = tool.get('is_overtime', False)
    
    # Emoji stato
    if is_overtime:
        emoji = "🔴"
        status = "FUORI TEMPO"
    elif percent < 20:
        emoji = "🟠"
        status = "CRITICO"
    elif percent < 50:
        emoji = "🟡"
        status = "ATTENZIONE"
    else:
        emoji = "🟢"
        status = "OK"
    
    msg = f"""
{emoji} **{alias}** (D{duplo})
━━━━━━━━━━━━━━━
📍 Posizione: {position}
📊 Stato: **{status}**

⏱ Usato: {used_norm:.1f} min norm
⏳ Rimasto: {remaining_norm:.1f} min norm
📈 Capacità: {total_capacity:.1f} min
📉 Percentuale: {percent:.1f}%
"""
    return msg.strip()


def format_tool_list(tools: List[Dict]) -> str:
    """Formatta lista utensili compatta"""
    if not tools:
        return "Nessun utensile trovato"
    
    lines = ["📋 **Lista Utensili**\n"]
    
    for tool in tools:
        alias = tool.get('alias', 'N/A')
        duplo = tool.get('duplo', 1)
        percent = tool.get('percent', 0)
        is_overtime = tool.get('is_overtime', False)
        
        if is_overtime:
            emoji = "🔴"
        elif percent < 20:
            emoji = "🟠"
        elif percent < 50:
            emoji = "🟡"
        else:
            emoji = "🟢"
        
        lines.append(f"{emoji} {alias} D{duplo} - {percent:.0f}%")
    
    return "\n".join(lines)