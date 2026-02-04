# TLM Manager V6 - Multi-Macchina

## 🆕 Novità V6

Questa versione introduce la **gestione multi-macchina**: ogni CNC in officina ha la sua lista utensili separata.

### Flusso di Utilizzo

```
Apertura App → Selezione Macchina → Lista Utensili della Macchina
```

### Funzionalità

- **Pagina Selezione Macchina** (landing page)
  - Vista di tutte le macchine con statistiche
  - Aggiungi/Modifica/Elimina macchine
  - Overview globale (totale utensili, critici, rotture mese)

- **Gestione Utensili per Macchina**
  - Ogni macchina ha la sua lista utensili separata
  - Dashboard specifica per macchina
  - Storico cicli tracciato per macchina
  - Export CSV separato per macchina

- **Materiali Condivisi**
  - I materiali sono globali (condivisi tra tutte le macchine)

---

## 📁 Struttura File

```
TLM_V6/
├── app.py
├── templates/
│   └── index.html
├── Avvia_TLM.vbs      ← Avvio silenzioso
├── Avvia_TLM.bat      ← Avvio con terminale
├── requirements.txt
└── LEGGIMI.md
```

---

## 🚀 Primo Avvio

1. **Installa dipendenze:**
   ```
   pip install -r requirements.txt
   ```

2. **Avvia l'applicazione:**
   - Doppio click su `Avvia_TLM.vbs` (silenzioso)
   - Oppure: `python app.py`

3. **Crea la prima macchina:**
   - Click su "+ Aggiungi Macchina"
   - Inserisci nome (es. "DMG DMU 50")
   - Opzionale: descrizione (es. "Reparto Fresatura")

4. **Seleziona la macchina** per entrare nella gestione utensili

---

## 🔧 Avvio Automatico (Windows)

### Metodo Rapido

1. Premi `Win + R` → digita `shell:startup` → Invio
2. Crea collegamento a `Avvia_TLM.vbs`
3. Sposta il collegamento nella cartella Startup

L'app partirà automaticamente ad ogni accensione del PC.

---

## 📊 Struttura Database

| Tabella | Descrizione |
|---------|-------------|
| `machines` | Elenco macchine CNC |
| `tools` | Utensili (legati a machine_id) |
| `materials` | Materiali (globali) |
| `history` | Sessioni ciclo corrente |
| `completed_cycles` | Storico cicli conclusi |

---

## 🔄 Migrazione da V5

Se hai già dati dalla V5, il database è compatibile:
- Gli utensili esistenti verranno assegnati a `machine_id = 1`
- Dovrai creare almeno una macchina per vederli

---

## 💡 Suggerimenti

- **Naming macchine**: Usa nomi chiari (es. "DMG 1 - Fresatura", "Mazak QTN - Torneria")
- **Descrizioni**: Utili per indicare reparto, turno, operatore responsabile
- **Backup**: Il file `tlm_data.db` contiene tutti i dati - salvalo periodicamente

---

## Requisiti

- Python 3.8+
- Windows 10/11 (per pywebview)
- Librerie: flask, pywebview, numpy
