"""
Bot Telegram per TLM Service - Workflow Completo
Gestione utensili CNC tramite Telegram con accesso da rete 5G
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from api_client import TLMAPIClient, format_tool_status
from config import BOT_TOKEN, MSG_WELCOME, MSG_HELP

# === CONFIGURAZIONE LOGGING ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === CLIENT API ===
api = TLMAPIClient()


# === HELPER FUNCTIONS ===

def get_status_emoji(percent: float, is_overtime: bool) -> str:
    """Ritorna emoji stato basato su percentuale"""
    if is_overtime:
        return "🔴"
    elif percent < 20:
        return "🟠"
    elif percent < 50:
        return "🟡"
    else:
        return "🟢"


# === COMANDI PRINCIPALI ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler comando /start
    Mostra lista macchine disponibili
    """
    # Verifica connessione API
    if not api.health_check():
        await update.message.reply_text(
            "❌ **Errore Connessione**\n\n"
            "Impossibile connettersi al server TLM!\n"
            "Verifica che l'app Flask sia attiva sulla rete aziendale.",
            parse_mode='Markdown'
        )
        return
    
    # Reset context
    context.user_data.clear()
    
    # Carica macchine dal database
    machines = api.get_machines()
    
    if not machines:
        await update.message.reply_text(
            "❌ Nessuna macchina trovata nel database"
        )
        return
    
    # Crea bottoni macchine
    keyboard = []
    for machine in machines:
        machine_name = machine.get('name', 'N/A')
        machine_id = machine.get('id')
        keyboard.append([
            InlineKeyboardButton(
                f"🏭 {machine_name}", 
                callback_data=f"machine_{machine_id}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        MSG_WELCOME,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler comando /help"""
    await update.message.reply_text(MSG_HELP, parse_mode='Markdown')


# === CALLBACK HANDLERS ===

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler principale per tutti i callback"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    # Log dettagliato
    logger.info(f"Callback ricevuto - User: {user_id}, Data: {data}")
    
    # Selezione macchina
    if data.startswith("machine_"):
        logger.info(f"→ Selezione macchina")
        await handle_machine_selection(query, context, data)
    
    # Ricerca utensile
    elif data == "search_tool":
        logger.info(f"→ Avvio ricerca utensile")
        await start_tool_search(query, context)
    
    # Filtri per stato
    elif data.startswith("filter_"):
        logger.info(f"→ Filtro per stato")
        await show_filtered_tools(query, context, data)
    
    # Vedi tutti (semplice o paginato)
    elif data == "show_all_tools":
        logger.info(f"→ Mostra tutti gli utensili")
        await show_all_tools_list(query, context)
    
    elif data.startswith("show_all_tools_page_"):
        logger.info(f"→ Mostra pagina utensili")
        await show_all_tools_paginated(query, context, data)
    
    # Selezione utensile
    elif data.startswith("tool_"):
        logger.info(f"→ Selezione utensile")
        await handle_tool_selection(query, context, data)
    
    # Azioni utensile
    elif data.startswith("action_"):
        logger.info(f"→ Azione utensile")
        await handle_action_selection(query, context, data)
    
    # Input tempo
    elif data.startswith("time_"):
        logger.info(f"→ Input tempo")
        await handle_time_input(query, context, data)
    
    # Selezione materiale
    elif data.startswith("material_"):
        logger.info(f"→ Selezione materiale")
        await handle_material_selection(query, context, data)
    
    # Conferma reset
    elif data.startswith("reset_"):
        logger.info(f"→ Reset utensile")
        await handle_reset_confirmation(query, context, data)
    
    # Torna a macchine
    elif data == "back_to_machines":
        logger.info(f"→ Torna a macchine")
        await show_machines(query, context)
    
    # Torna a utensili
    elif data == "back_to_tools":
        logger.info(f"→ Torna a utensili")
        machine_id = context.user_data.get('selected_machine_id')
        if machine_id:
            await show_tools(query, context, machine_id)
    
    else:
        logger.warning(f"⚠️  Callback non gestito: {data}")


# === STEP 1: SELEZIONE MACCHINA ===

async def handle_machine_selection(query, context, data: str):
    """
    Gestisce selezione macchina
    Salva la macchina selezionata e mostra gli utensili
    """
    machine_id = int(data.split("_")[1])
    
    # Salva nel context
    context.user_data['selected_machine_id'] = machine_id
    
    # Carica info macchina
    machine = api.get_machine(machine_id)
    machine_name = machine.get('name', 'N/A') if machine else 'N/A'
    context.user_data['selected_machine_name'] = machine_name
    
    # Mostra utensili
    await show_tools(query, context, machine_id)


async def show_machines(query, context):
    """Mostra lista macchine"""
    machines = api.get_machines()
    
    if not machines:
        await query.edit_message_text("❌ Nessuna macchina trovata")
        return
    
    keyboard = []
    for machine in machines:
        machine_name = machine.get('name', 'N/A')
        machine_id = machine.get('id')
        keyboard.append([
            InlineKeyboardButton(
                f"🏭 {machine_name}", 
                callback_data=f"machine_{machine_id}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        MSG_WELCOME,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# === STEP 2: LISTA UTENSILI ===

async def start_tool_search(query, context):
    """
    Avvia modalità ricerca utensile
    """
    machine_name = context.user_data.get('selected_machine_name', 'N/A')
    
    # Imposta flag ricerca
    context.user_data['awaiting_tool_search'] = True
    
    keyboard = [[InlineKeyboardButton("❌ Annulla", callback_data="back_to_tools")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🔍 **Ricerca Utensile - {machine_name}**\n\n"
        f"Scrivi parte del nome dell'utensile:\n"
        f"(Esempi: `FS25`, `T12`, `D50`, `FRESA`)\n\n"
        f"La ricerca trova tutti gli utensili che **contengono** il testo.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_filtered_tools(query, context, data: str):
    """
    Mostra utensili filtrati per stato
    """
    filter_type = data.split("_")[1]  # critical, warning, ok
    machine_id = context.user_data.get('selected_machine_id')
    machine_name = context.user_data.get('selected_machine_name', 'N/A')
    
    tools = api.get_tools(machine_id)
    
    # Filtra per stato
    if filter_type == "critical":
        filtered = [t for t in tools if t.get('percent', 0) < 20 or t.get('is_overtime', False)]
        title = "🔴 Utensili Critici"
    elif filter_type == "warning":
        filtered = [t for t in tools if 20 <= t.get('percent', 0) < 50]
        title = "🟡 Utensili in Attenzione"
    else:  # ok
        filtered = [t for t in tools if t.get('percent', 0) >= 50]
        title = "🟢 Utensili OK"
    
    if not filtered:
        await query.answer("Nessun utensile in questo stato", show_alert=True)
        return
    
    # Mostra lista filtrata
    await show_tools_list(query, context, filtered, title)


async def show_all_tools_list(query, context):
    """
    Mostra tutti gli utensili (se <= 20)
    """
    machine_id = context.user_data.get('selected_machine_id')
    tools = api.get_tools(machine_id)
    
    await show_tools_list(query, context, tools, "📋 Tutti gli Utensili")


async def show_all_tools_paginated(query, context, data: str):
    """
    Mostra tutti gli utensili con paginazione (pagine da 20)
    """
    page = int(data.split("_")[-1])
    machine_id = context.user_data.get('selected_machine_id')
    machine_name = context.user_data.get('selected_machine_name', 'N/A')
    
    tools = api.get_tools(machine_id)
    
    # Paginazione
    PAGE_SIZE = 20
    total_pages = (len(tools) + PAGE_SIZE - 1) // PAGE_SIZE
    start_idx = page * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, len(tools))
    page_tools = tools[start_idx:end_idx]
    
    # Crea bottoni
    keyboard = []
    for tool in page_tools:
        alias = tool.get('alias', 'N/A')
        duplo = tool.get('duplo', 1)
        percent = tool.get('percent', 0)
        is_overtime = tool.get('is_overtime', False)
        tool_id = tool.get('id')
        
        emoji = get_status_emoji(percent, is_overtime)
        button_text = f"{emoji} {alias} D{duplo} ({percent:.0f}%)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"tool_{tool_id}")])
    
    # Bottoni navigazione
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Precedente", callback_data=f"show_all_tools_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Successiva ➡️", callback_data=f"show_all_tools_page_{page+1}"))
    
    keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🔙 Menu Utensili", callback_data="back_to_tools")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"🏭 **{machine_name}**\n\n📋 **Tutti gli Utensili** (Pag. {page+1}/{total_pages})\nMostrando {start_idx+1}-{end_idx} di {len(tools)}"
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')


async def show_tools_list(query, context, tools: list, title: str):
    """
    Mostra lista utensili (helper generico)
    """
    machine_name = context.user_data.get('selected_machine_name', 'N/A')
    
    keyboard = []
    for tool in tools:
        alias = tool.get('alias', 'N/A')
        duplo = tool.get('duplo', 1)
        percent = tool.get('percent', 0)
        is_overtime = tool.get('is_overtime', False)
        tool_id = tool.get('id')
        
        emoji = get_status_emoji(percent, is_overtime)
        button_text = f"{emoji} {alias} D{duplo} ({percent:.0f}%)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"tool_{tool_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Menu Utensili", callback_data="back_to_tools")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"🏭 **{machine_name}**\n\n{title}\nTrovati: {len(tools)}"
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')


async def show_tools(query, context, machine_id: int):
    """
    Mostra opzioni ricerca utensili o lista completa
    ORDINAMENTO: Mantiene l'ordine del database (come nell'app principale)
    """
    machine_name = context.user_data.get('selected_machine_name', 'N/A')
    
    # Carica utensili dal database
    tools = api.get_tools(machine_id)
    
    if not tools:
        await query.edit_message_text(
            f"🏭 **{machine_name}**\n\n"
            f"❌ Nessun utensile trovato",
            parse_mode='Markdown'
        )
        return
    
    total_tools = len(tools)
    
    # Conteggio per stato
    critical_count = sum(1 for t in tools if t.get('percent', 0) < 20 or t.get('is_overtime', False))
    warning_count = sum(1 for t in tools if 20 <= t.get('percent', 0) < 50)
    ok_count = sum(1 for t in tools if t.get('percent', 0) >= 50)
    
    # Menu principale selezione utensile
    keyboard = [
        [InlineKeyboardButton(f"🔍 Cerca per nome", callback_data="search_tool")],
    ]
    
    # Filtri per stato (solo se ci sono utensili in quello stato)
    filter_buttons = []
    if critical_count > 0:
        filter_buttons.append(InlineKeyboardButton(f"🔴 Critici ({critical_count})", callback_data="filter_critical"))
    if warning_count > 0:
        filter_buttons.append(InlineKeyboardButton(f"🟡 Attenzione ({warning_count})", callback_data="filter_warning"))
    if ok_count > 0:
        filter_buttons.append(InlineKeyboardButton(f"🟢 OK ({ok_count})", callback_data="filter_ok"))
    
    # Aggiungi filtri (2 per riga)
    if filter_buttons:
        keyboard.append(filter_buttons[:2])
        if len(filter_buttons) > 2:
            keyboard.append(filter_buttons[2:])
    
    # Vedi tutti (con paginazione se > 20)
    if total_tools <= 20:
        keyboard.append([InlineKeyboardButton(f"📋 Vedi tutti ({total_tools})", callback_data="show_all_tools")])
    else:
        keyboard.append([InlineKeyboardButton(f"📋 Vedi tutti ({total_tools} - paginati)", callback_data="show_all_tools_page_0")])
    
    keyboard.append([InlineKeyboardButton("🔙 Cambia Macchina", callback_data="back_to_machines")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"""🏭 **{machine_name}**

📊 **Stato utensili:**
🔴 Critici: {critical_count}
🟡 Attenzione: {warning_count}
🟢 OK: {ok_count}
📦 Totale: {total_tools}

**Come vuoi procedere?**"""
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# === STEP 3: DETTAGLI UTENSILE E AZIONI ===

async def handle_tool_selection(query, context, data: str):
    """
    Mostra dettagli utensile e azioni disponibili
    """
    tool_id = int(data.split("_")[1])
    machine_id = context.user_data.get('selected_machine_id')
    
    if not machine_id:
        await query.edit_message_text("❌ Errore: macchina non selezionata")
        return
    
    # Carica utensili e trova quello selezionato
    tools = api.get_tools(machine_id)
    tool = next((t for t in tools if t['id'] == tool_id), None)
    
    if not tool:
        await query.edit_message_text("❌ Utensile non trovato")
        return
    
    # Salva nel context
    context.user_data['selected_tool_id'] = tool_id
    context.user_data['selected_tool_info'] = tool
    
    # Formatta messaggio con info utensile
    message = format_tool_status(tool)
    
    # Bottoni azioni
    keyboard = [
        [InlineKeyboardButton("⏱ Lavoro", callback_data=f"action_work")],
        [InlineKeyboardButton("⚡ Ext+", callback_data=f"action_extend")],
        [InlineKeyboardButton("📊 Stats", callback_data=f"action_stats")],
        [InlineKeyboardButton("🔄 Reset", callback_data=f"action_reset")],
        [InlineKeyboardButton("🔙 Lista Utensili", callback_data="back_to_tools")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# === STEP 4: GESTIONE AZIONI ===

async def handle_action_selection(query, context, data: str):
    """Gestisce la selezione dell'azione"""
    action = data.split("_")[1]
    
    if action == "work":
        await start_work_flow(query, context)
    elif action == "extend":
        await start_extend_flow(query, context)
    elif action == "stats":
        await show_stats(query, context)
    elif action == "reset":
        await start_reset_flow(query, context)


# === WORKFLOW: LAVORO ===

async def start_work_flow(query, context):
    """
    Avvia workflow Lavoro:
    1. Chiede tempo
    2. Memorizza
    3. Chiede materiale
    4. Invia all'app
    """
    context.user_data['pending_action'] = 'work'
    
    tool = context.user_data.get('selected_tool_info', {})
    alias = tool.get('alias', 'N/A')
    
    # Bottoni tempo rapido
    keyboard = [
        [InlineKeyboardButton("15 min", callback_data="time_15")],
        [InlineKeyboardButton("30 min", callback_data="time_30")],
        [InlineKeyboardButton("60 min", callback_data="time_60")],
        [InlineKeyboardButton("90 min", callback_data="time_90")],
        [InlineKeyboardButton("✏️ Altro (scrivi)", callback_data="time_manual")],
        [InlineKeyboardButton("❌ Annulla", callback_data="back_to_tools")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"⏱ **Lavoro - {alias}**\n\n"
        f"Seleziona minuti lavorati:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# === WORKFLOW: EXT+ ===

async def start_extend_flow(query, context):
    """
    Avvia workflow Ext+:
    1. Chiede tempo
    2. Memorizza
    3. Chiede materiale
    4. Invia all'app
    """
    context.user_data['pending_action'] = 'extend'
    
    tool = context.user_data.get('selected_tool_info', {})
    alias = tool.get('alias', 'N/A')
    
    keyboard = [
        [InlineKeyboardButton("15 min", callback_data="time_15")],
        [InlineKeyboardButton("30 min", callback_data="time_30")],
        [InlineKeyboardButton("60 min", callback_data="time_60")],
        [InlineKeyboardButton("90 min", callback_data="time_90")],
        [InlineKeyboardButton("✏️ Altro (scrivi)", callback_data="time_manual")],
        [InlineKeyboardButton("❌ Annulla", callback_data="back_to_tools")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"⚡ **Ext+ - {alias}**\n\n"
        f"Seleziona minuti di estensione:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# === WORKFLOW: STATS ===

async def show_stats(query, context):
    """Mostra statistiche utensile"""
    tool_id = context.user_data.get('selected_tool_id')
    
    if not tool_id:
        await query.answer("❌ Errore: utensile non selezionato", show_alert=True)
        return
    
    # Carica predizione/stats
    prediction = api.get_tool_prediction(tool_id)
    
    if not prediction or not prediction.get('has_data'):
        await query.edit_message_text(
            "📊 **Statistiche**\n\n"
            "❌ Dati insufficienti per statistiche.\n"
            "Serve completare almeno un ciclo.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Indietro", callback_data=f"tool_{tool_id}")
            ]]),
            parse_mode='Markdown'
        )
        return
    
    pred = prediction['prediction']
    
    message = f"""
📊 **Statistiche Utensile**

⏱ **Vita Media:** {pred.get('avg_life', 0):.1f} min
📈 **Deviazione Std:** {pred.get('std_life', 0):.1f} min
⬇️ **Min Osservato:** {pred.get('min_life', 0):.1f} min
⬆️ **Max Osservato:** {pred.get('max_life', 0):.1f} min

💔 **Tasso Rottura:** {pred.get('broken_rate_pct', 0):.1f}%
🔢 **Cicli Completati:** {pred.get('total_cycles', 0)}
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Indietro", callback_data=f"tool_{tool_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message.strip(),
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# === WORKFLOW: RESET ===

async def start_reset_flow(query, context):
    """
    Avvia workflow Reset:
    Mostra opzioni: OK usura normale, Rotto, Anticipato
    """
    tool = context.user_data.get('selected_tool_info', {})
    alias = tool.get('alias', 'N/A')
    tool_id = context.user_data.get('selected_tool_id')
    
    keyboard = [
        [InlineKeyboardButton("✅ OK - Usura Normale", callback_data="reset_OK")],
        [InlineKeyboardButton("💔 Rotto", callback_data="reset_BROKEN")],
        [InlineKeyboardButton("⏰ Anticipato", callback_data="reset_EARLY")],
        [InlineKeyboardButton("❌ Annulla", callback_data=f"tool_{tool_id}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🔄 **Reset - {alias}**\n\n"
        f"⚠️ Questa azione resetterà i contatori.\n\n"
        f"Seleziona motivo reset:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# === GESTIONE INPUT TEMPO ===

async def handle_time_input(query, context, data: str):
    """
    Gestisce input tempo (rapido o manuale)
    Dopo aver ricevuto il tempo, passa alla selezione materiale
    """
    time_value = data.split("_")[1]
    
    if time_value == "manual":
        # Richiedi input manuale
        await query.edit_message_text(
            "✏️ **Inserimento Manuale**\n\n"
            "Scrivi i minuti e invia il messaggio.\n"
            "(Es: 47.5)",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_manual_input'] = True
        return
    
    # Salva tempo nel context
    minutes = float(time_value)
    context.user_data['selected_minutes'] = minutes
    
    # Passa alla selezione materiale
    await show_material_selection(query, context)


# === GESTIONE INPUT MANUALE ===

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce input testuale (per tempo manuale e ricerca utensili)"""
    
    # === RICERCA UTENSILE ===
    if context.user_data.get('awaiting_tool_search'):
        search_query = update.message.text.strip().upper()
        machine_id = context.user_data.get('selected_machine_id')
        machine_name = context.user_data.get('selected_machine_name', 'N/A')
        
        logger.info(f"Ricerca utensile: '{search_query}' in macchina {machine_id}")
        
        # Carica tutti gli utensili
        all_tools = api.get_tools(machine_id)
        
        # Cerca utensili che contengono la query (case-insensitive)
        matching_tools = [
            tool for tool in all_tools 
            if search_query in tool.get('alias', '').upper()
        ]
        
        logger.info(f"Trovati {len(matching_tools)} utensili matching")
        
        # Pulisci flag
        context.user_data.pop('awaiting_tool_search', None)
        
        if not matching_tools:
            keyboard = [
                [InlineKeyboardButton("🔍 Cerca altro", callback_data="search_tool")],
                [InlineKeyboardButton("🔙 Menu Utensili", callback_data="back_to_tools")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"❌ **Nessun utensile trovato**\n\n"
                f"Ricerca: `{search_query}`\n\n"
                f"Prova con un altro termine.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        # Mostra risultati
        keyboard = []
        for tool in matching_tools:
            alias = tool.get('alias', 'N/A')
            duplo = tool.get('duplo', 1)
            percent = tool.get('percent', 0)
            is_overtime = tool.get('is_overtime', False)
            tool_id = tool.get('id')
            
            emoji = get_status_emoji(percent, is_overtime)
            button_text = f"{emoji} {alias} D{duplo} ({percent:.0f}%)"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"tool_{tool_id}")])
        
        # Bottoni navigazione
        keyboard.append([InlineKeyboardButton("🔍 Cerca altro", callback_data="search_tool")])
        keyboard.append([InlineKeyboardButton("🔙 Menu Utensili", callback_data="back_to_tools")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🔍 **Risultati ricerca: `{search_query}`**\n\n"
            f"Trovati **{len(matching_tools)}** utensili:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # === INSERIMENTO MANUALE TEMPO ===
    if not context.user_data.get('awaiting_manual_input'):
        return
    
    try:
        minutes = float(update.message.text.replace(',', '.'))
        
        if minutes <= 0:
            await update.message.reply_text("❌ Inserisci un numero positivo")
            return
        
        # Salva nel context
        context.user_data['selected_minutes'] = minutes
        context.user_data.pop('awaiting_manual_input', None)
        
        # Mostra selezione materiale
        machine_id = context.user_data.get('selected_machine_id')
        materials = api.get_materials(machine_id)
        
        if not materials:
            await update.message.reply_text("❌ Nessun materiale trovato")
            return
        
        action = context.user_data.get('pending_action', 'work')
        tool = context.user_data.get('selected_tool_info', {})
        alias = tool.get('alias', 'N/A')
        
        keyboard = []
        for mat in materials:
            mat_name = mat.get('name', 'N/A')
            mat_id = mat.get('id')
            mat_factor = mat.get('factor', 1.0)
            keyboard.append([
                InlineKeyboardButton(
                    f"{mat_name} (x{mat_factor})", 
                    callback_data=f"material_{mat_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("❌ Annulla", callback_data="back_to_tools")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        action_emoji = "⏱" if action == "work" else "⚡"
        action_text = "Lavoro" if action == "work" else "Ext+"
        
        await update.message.reply_text(
            f"{action_emoji} **{action_text} - {alias}**\n\n"
            f"✅ Tempo: {minutes} min\n\n"
            f"Seleziona materiale:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Inserisci un numero valido (es: 47.5)")


# === SELEZIONE MATERIALE ===

async def show_material_selection(query, context):
    """
    Mostra lista materiali della macchina
    Carica materiali reali dal database
    """
    machine_id = context.user_data.get('selected_machine_id')
    
    # Carica materiali dal database per questa macchina
    materials = api.get_materials(machine_id)
    
    if not materials:
        await query.edit_message_text(
            "❌ Nessun materiale configurato per questa macchina.\n"
            "Configura i materiali nell'app TLM principale.",
            parse_mode='Markdown'
        )
        return
    
    action = context.user_data.get('pending_action', 'work')
    tool = context.user_data.get('selected_tool_info', {})
    alias = tool.get('alias', 'N/A')
    minutes = context.user_data.get('selected_minutes', 0)
    
    # Crea bottoni materiali
    keyboard = []
    for mat in materials:
        mat_name = mat.get('name', 'N/A')
        mat_id = mat.get('id')
        mat_factor = mat.get('factor', 1.0)
        
        keyboard.append([
            InlineKeyboardButton(
                f"{mat_name} (fattore x{mat_factor})", 
                callback_data=f"material_{mat_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("❌ Annulla", callback_data="back_to_tools")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    action_emoji = "⏱" if action == "work" else "⚡"
    action_text = "Lavoro" if action == "work" else "Ext+"
    
    await query.edit_message_text(
        f"{action_emoji} **{action_text} - {alias}**\n\n"
        f"✅ Tempo: {minutes} min\n\n"
        f"Seleziona materiale:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# === CONFERMA E INVIO ===

async def handle_material_selection(query, context, data: str):
    """
    Gestisce selezione materiale e invia dati all'app
    """
    try:
        logger.info(f"Material selection callback: {data}")
        
        mat_id = int(data.split("_")[1])
        machine_id = context.user_data.get('selected_machine_id')
        
        logger.info(f"Material ID: {mat_id}, Machine ID: {machine_id}")
        
        # Carica info materiale
        materials = api.get_materials(machine_id)
        logger.info(f"Materials loaded: {len(materials)} items")
        
        material = next((m for m in materials if m['id'] == mat_id), None)
        
        if not material:
            logger.error(f"Material not found: mat_id={mat_id}")
            await query.answer("❌ Materiale non trovato", show_alert=True)
            return
        
        mat_name = material.get('name', 'N/A')
        mat_factor = material.get('factor', 1.0)
        
        logger.info(f"Material selected: {mat_name} (factor: {mat_factor})")
        
        # Recupera dati dal context
        action = context.user_data.get('pending_action')
        tool_id = context.user_data.get('selected_tool_id')
        minutes = context.user_data.get('selected_minutes')
        
        logger.info(f"Action: {action}, Tool ID: {tool_id}, Minutes: {minutes}")
        
        if not action or not tool_id or minutes is None:
            logger.error(f"Missing context data - action:{action}, tool_id:{tool_id}, minutes:{minutes}")
            await query.answer("❌ Errore: dati mancanti. Riprova da capo.", show_alert=True)
            return
        
        # Invia all'app Flask
        logger.info(f"Sending to Flask: action={action}, tool_id={tool_id}, minutes={minutes}, material={mat_name}")
        
        if action == "work":
            result = api.add_work_session(tool_id, minutes, mat_name, mat_factor)
        else:  # extend
            result = api.extend_tool_life(tool_id, minutes, mat_name, mat_factor)
        
        logger.info(f"Flask response: {result}")
        
        if result.get('success'):
            # Successo!
            action_text = "Lavoro aggiunto" if action == "work" else "Estensione applicata"
            
            logger.info(f"✅ Success: {action_text}")
            await query.answer(f"✅ {action_text}!", show_alert=True)
            
            # Pulisci context
            context.user_data.pop('pending_action', None)
            context.user_data.pop('selected_minutes', None)
            
            # Torna ai dettagli utensile (aggiornati)
            await handle_tool_selection(query, context, f"tool_{tool_id}")
        else:
            error_msg = result.get('error', 'Sconosciuto')
            logger.error(f"❌ Flask error: {error_msg}")
            await query.answer(
                f"❌ Errore: {error_msg}", 
                show_alert=True
            )
    except Exception as e:
        logger.error(f"Exception in handle_material_selection: {e}", exc_info=True)
        await query.answer(f"❌ Errore interno: {str(e)}", show_alert=True)


# === CONFERMA RESET ===

async def handle_reset_confirmation(query, context, data: str):
    """
    Gestisce conferma reset
    """
    status = data.split("_")[1]  # OK, BROKEN, EARLY
    tool_id = context.user_data.get('selected_tool_id')
    
    # Mappa stati
    status_map = {
        'OK': 'Usura Normale',
        'BROKEN': 'Rotto',
        'EARLY': 'Anticipato'
    }
    
    # Invia reset all'app
    result = api.reset_tool(tool_id, status)
    
    if result['success']:
        await query.answer(
            f"✅ Reset completato ({status_map.get(status, status)})", 
            show_alert=True
        )
        
        # Torna alla lista utensili
        machine_id = context.user_data.get('selected_machine_id')
        await show_tools(query, context, machine_id)
    else:
        await query.answer(
            f"❌ Errore: {result.get('error', 'Sconosciuto')}", 
            show_alert=True
        )


# === MAIN ===

def main():
    """Avvia il bot"""
    # Verifica token
    if BOT_TOKEN == "INSERISCI_QUI_IL_TOKEN":
        logger.error("ERRORE: Configura BOT_TOKEN in config.py!")
        return
    
    # Verifica connessione API
    if not api.health_check():
        logger.warning("⚠️  ATTENZIONE: API TLM non raggiungibile!")
        logger.warning("Il bot partirà comunque, ma non potrà funzionare correttamente.")
        logger.warning("Verifica che l'app Flask TLM sia attiva.")
    else:
        logger.info("✅ API TLM raggiungibile")
    
    # Crea application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handler comandi
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Handler callback buttons
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Handler input testo
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    
    # Avvia bot
    logger.info("🤖 TLM Bot avviato e pronto!")
    logger.info("📱 Il bot è accessibile da qualsiasi rete (anche 5G)")
    logger.info("💻 Assicurati che questo PC possa accedere all'app Flask sulla rete aziendale")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()