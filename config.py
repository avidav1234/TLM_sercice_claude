"""
Configurazione Bot Telegram per TLM Service
"""

# === CONFIGURAZIONE BOT ===
BOT_TOKEN = "7201531525:AAHgM1c4zoc87Xciu56edu1Yz6eQnU4Ivuw"  # Da @BotFather

# === CONFIGURAZIONE API TLM ===
# URL dell'app Flask sulla rete aziendale
# Il bot DEVE girare su un PC nella rete aziendale per accedere a questo URL
TLM_API_BASE_URL = "http://192.168.244.132:5000"  # Cambia con IP/porta della tua app Flask

# === MESSAGGI ===
MSG_WELCOME = """
🔧 **TLM Service Bot - Vetimec**

Gestisci gli utensili CNC da Telegram!

Seleziona una macchina per iniziare.
"""

MSG_HELP = """
📖 **Guida Comandi**

**/start** - Seleziona macchina
**/help** - Questa guida

**Workflow:**
1️⃣ Seleziona macchina
2️⃣ Seleziona utensile dalla lista
3️⃣ Scegli azione:
   • ⏱ **Lavoro** - Aggiungi tempo lavorato
   • ⚡ **Ext+** - Estendi vita utensile
   • 📊 **Stats** - Vedi statistiche
   • 🔄 **Reset** - Resetta utensile
"""
