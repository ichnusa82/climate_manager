# Climate Manager

🇮🇹 Italiano · [🇬🇧 English](README.en.md)

Integrazione personalizzata per Home Assistant che gestisce le zone di riscaldamento e raffrescamento: un termostato per ogni zona, con valvole, caldaia, pompa, climatizzatore, fasce orarie, finestre e antigelo.

Ogni zona diventa un'entità `climate` più alcune entità di supporto, e si configura tutta da interfaccia, senza YAML.

## Cosa fa

- **Ingresso a scelta:** sensore di temperatura oppure termostato fisico (contatto chiuso = richiesta di calore).
- **Uscite:** una o più valvole/relè, uscita di accensione caldaia, uscita pompa, climatizzatore.
- **Modalità:** Spento, Caldo, Freddo (solo con climatizzatore) e Auto (con fasce orarie).
- **Preset:** per scegliere quali valvole tenere attive (utile se una zona ha più elettrovalvole).
- **Setpoint caldaia:** un setpoint unico, condiviso da tutte le zone con la stessa caldaia, con valore di override.
- **Fasce orarie:** temperatura comfort dentro le fasce, temperatura ridotta fuori. Funzionano sia con la sonda sia con il termostato fisico.
- **Calendari di blocco:** se un calendario è attivo, il programma si blocca (spegne o usa la temperatura ridotta).
- **Finestre:** se una finestra resta aperta oltre il ritardo, il riscaldamento della zona si sospende.
- **Antigelo:** sotto la temperatura impostata scalda sempre, anche da spento.
- **Sorgente caldo - freddo:** con un climatizzatore configurato si sceglie se il caldo viene dal riscaldamento, dal climatizzatore o da entrambi.

## Installazione

### Manuale
1. Copia la cartella `climate_manager` in `config/custom_components/`.
2. Riavvia Home Assistant.
3. Vai in **Impostazioni → Dispositivi e servizi → Aggiungi integrazione** e cerca **Climate Manager**.

### HACS
Quando sarà pubblicata: HACS → Integrazioni → menu ⋮ → Repository personalizzati → incolla l'indirizzo del repository, categoria *Integrazione* → installa e riavvia.

> Se arrivi dalla versione precedente chiamata "Termostati" (cartella `radiant`): elimina la vecchia integrazione, cancella la cartella `radiant`, installa `climate_manager`, riavvia e ricrea i termostati con gli stessi nomi.

## Creare un termostato

Aggiungi l'integrazione una volta **per ogni zona**. Il modulo chiede:

| Campo | Significato |
|---|---|
| Nome | Nome della zona (deve essere unico) |
| Relè / elettrovalvole | Uno o più `switch` o `input_boolean` da comandare |
| Tipo di ingresso | Sensore di temperatura o termostato fisico |
| Sensore di temperatura | Qualsiasi `sensor` (anche sonde Modbus) |
| Contatto del termostato fisico | `binary_sensor`, `switch` o `input_boolean` |
| Contatto invertito | Attivalo se il contatto aperto significa richiesta di calore |
| Uscita caldaia / pompa | Opzionali: si accendono quando la zona chiede calore |
| Climatizzatore | Opzionale: entità `climate`, `switch` o `input_boolean` |
| Setpoint caldaia | Opzionale: `number` o `input_number` (per esempio quello letto dall'ESP8266) |
| Entità di override | Se è accesa, la caldaia usa il setpoint di override |
| Setpoint di override | Valore usato quando l'override è attivo |
| Temperatura comfort / ridotta | Usate in modalità Auto dentro e fuori dalle fasce |
| Calendari di blocco e modalità | Cosa fare quando un calendario è attivo |
| Sensore Finestra / Ritardo | Sensori di apertura e minuti prima di sospendere |
| Antigelo Temperatura | Sotto questa temperatura scalda sempre. 0 = disattivato |
| Abilita modalità freddo | Mostra la modalità Freddo; richiede il climatizzatore (la selezione Estate/Inverno resta comunque) |
| Tolleranza caldo / freddo | Isteresi di accensione e spegnimento |
| Ciclo minimo di accensione | Minuti minimi di accensione, 0 = disattivato |
| Temperatura minima / massima | Limiti del termostato (di default 15 e 30 °C) |

Tutte le impostazioni si possono cambiare dopo: **Dispositivi e servizi → Climate Manager → Configura**.

## Entità create

Per ogni zona trovi nel dispositivo:

**Controlli**
- Il **termostato** (`climate`), con preset per le valvole.
- **Sorgente caldo - freddo:** solo se è configurato un climatizzatore.
- **Setpoint caldaia:** solo se è configurato il setpoint. È unico: le altre zone con la stessa caldaia lo creano disabilitato.
- Un interruttore **«… attiva»** per ogni valvola, se la zona ne ha almeno due. Serve a escludere una valvola senza cambiare preset.

**Configurazione (editor delle fasce da dashboard)**
Servono a creare e modificare le fasce senza aprire il menu delle opzioni. Sono in ordine:

1. 01 Fascia: sceglie quale fascia modificare, oppure «Nuova fascia»
2. 02–08 Fascia Lunedì … Domenica: i giorni
3. 09 Inizio fascia oraria
4. 10 Fine fascia oraria
5. 11 Salva fascia oraria
6. 12 Elimina fascia
7. 13 Elimina tutte le fasce

Per creare una fascia: lascia «Nuova fascia», attiva i giorni, imposta inizio e fine, premi **Salva**. Per modificarne una: scegline una dal selettore, cambia i valori e premi **Salva**. Se la fine è prima dell'inizio, la fascia passa la mezzanotte.

Queste entità sono nella sezione *Configurazione* e non compaiono nelle dashboard generate in automatico: aggiungile a mano alle tue card.

## Card cronotermostato (cavalieri)

L'integrazione installa da sola una card per la dashboard (non serve aggiungere risorse). Ogni cavaliere è un intervallo di 30 minuti: **alto = comfort / in fascia**, **basso = ridotta / fuori fascia**. Tocca o trascina per cambiarli, copia un giorno sugli altri e premi **Salva**.

```yaml
type: custom:climate-manager-schedule-card
entity: climate.salone
step: 30          # 15, 30 o 60 minuti (facoltativo)
show_week: true   # riepilogo della settimana (facoltativo)
title: Salone     # facoltativo
```

Le fasce si possono impostare anche con l'azione `climate_manager.set_schedule`:

```yaml
action: climate_manager.set_schedule
target:
  entity_id: climate.salone
data:
  slots:
    - days: [mon, tue, wed, thu, fri]
      start: "06:30"
      end: "08:30"
```

Il programma attuale è nell'attributo `schedule` del termostato.

## Come funziona

### Termostato con sonda
Scalda quando la temperatura scende sotto l'obiettivo meno la *tolleranza caldo* e si ferma quando supera l'obiettivo più la tolleranza. Lo stesso vale per il freddo con la *tolleranza freddo*. Il ciclo minimo evita accensioni troppo ravvicinate.

### Termostato fisico
La zona scalda quando il contatto chiede calore. Le fasce orarie, se ci sono, decidono quando il contatto è ascoltato.

### Modalità Auto
Disponibile quando esiste almeno una fascia. Dentro le fasce usa la temperatura comfort, fuori la ridotta. Se cambi la temperatura a mano, la modifica vale fino al prossimo cambio di fascia. Con un termostato fisico, fuori fascia il riscaldamento resta spento.

### Estate / Inverno
Funziona solo sui termostati con climatizzatore e con la **Sorgente caldo - freddo** impostata su *Climatizzatore*; con le altre sorgenti l'entità **Stagione** è non disponibile e Auto scalda soltanto. In *Inverno* la modalità Auto scalda con le fasce (temperature comfort/ridotta). In *Estate* raffresca con le stesse fasce e con le temperature comfort/ridotta estive (predefinite 26 / 28 °C, modificabili nelle opzioni). Con il termostato a contatto, dentro le fasce il contatto comanda il climatizzatore in caldo o in freddo secondo la stagione. Nella card cronotermostato il pulsante Inverno/Estate compare solo in questo caso.

### Caldaia, pompa e setpoint
La caldaia e la pompa si accendono quando almeno una zona chiede calore e solo con il riscaldamento (mai in modalità Freddo). Il setpoint caldaia è unico: se l'entità di override è accesa, viene scritto il setpoint di override.

### Climatizzatore e sorgente
- **Freddo** usa sempre il climatizzatore.
- **Caldo** usa la sorgente scelta: Riscaldamento, Climatizzatore oppure Riscaldamento + Climatizzatore insieme. Il combinato funziona solo in caldo.

### Priorità
L'antigelo ha la precedenza su tutto, poi vengono finestra aperta e blocco calendario, infine le regole normali.

## Opzioni (menu Configura)

- **Impostazioni e valvole**
- **Aggiungi / Modifica / Cambia l'ordine / Elimina preset** (con almeno due valvole)
- **Aggiungi / Modifica / Elimina fasce orarie**

## Lingue

Italiano e inglese, secondo la lingua di Home Assistant. Le fasce usano le sigle dei giorni della lingua scelta.

## Domande frequenti

**Il setpoint caldaia torna a 28.** È il valore minimo ammesso. Succede se nessuna zona chiede calore e non c'è un valore salvato: controlla che l'entità di override e il setpoint siano quelli giusti.

**Non vedo le entità delle fasce.** Sono nella sezione *Configurazione* del dispositivo.

**Ho cambiato nome a una zona e gli entity ID sono rimasti vecchi.** Home Assistant non rinomina gli entity ID esistenti. Cambiali dalle impostazioni dell'entità.

## Limiti noti

L'integrazione è stata scritta e controllata nel codice, ma non è ancora stata provata a lungo su impianti diversi. Segnala i problemi nel repository.

## Licenza

MIT
