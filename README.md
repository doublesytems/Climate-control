# Smart Climate

Een geavanceerde HACS custom integration voor Home Assistant met slimme klimaatbesturing voor vloerverwarming en andere verwarmings-/koelsystemen.

---

## Functies

### Drie regelalgoritmen
| Algoritme | Beschrijving |
|-----------|-------------|
| **Hysterese** | Klassiek aan/uit met instelbare koude- en warme tolerantie |
| **PID** | Proportioneel-Integraal-Differentiaal regelaar met anti-windup en outputbegrenzing |
| **Voorspellend** | Leert de verwarmings-/koelsnelheid van de ruimte via lineaire regressie |

### Zelflerend (Tado-stijl)
- Na elke verwarmingssessie berekent het algoritme de werkelijke °C/min en past zijn interne schatting aan via een **Exponentieel Voortschrijdend Gemiddelde (EMA)**
- Geleerde snelheden en PID-status worden **persistent opgeslagen** en overleven een herstart van Home Assistant
- **Vroeg starten**: het systeem berekent automatisch wanneer de verwarming moet starten zodat de ruimte precies op temperatuur is bij een schema-wijziging — net zoals Tado

### Presets
| Preset | Standaard | Beschrijving |
|--------|-----------|-------------|
| Comfort | 20 °C | Dagelijks gebruik |
| Eco | 17 °C | Energiebesparend |
| Slaap | 16 °C | Slaapstand |
| Afwezig | 12 °C | Niemand thuis |
| Boost | 24 °C | Tijdelijk snel opwarmen |
| Schema | — | Volgt het weekschema |

### Weekschema
Stel tijdblokken in per dag via de service `smart_climate.set_schedule`. Voorbeeld:

```yaml
service: smart_climate.set_schedule
target:
  entity_id: climate.woonkamer
data:
  entries:
    - days: [0, 1, 2, 3, 4]   # ma–vr
      start: "07:00"
      preset: comfort
    - days: [0, 1, 2, 3, 4]
      start: "09:00"
      preset: eco
    - days: [0, 1, 2, 3, 4]
      start: "17:30"
      preset: comfort
    - days: [0, 1, 2, 3, 4]
      start: "23:00"
      preset: sleep
    - days: [5, 6]             # za–zo
      start: "08:00"
      preset: comfort
```

### Aanwezigheidsdetectie
- Koppel `person`-, `device_tracker`- of `binary_sensor`-entiteiten
- Schakelt automatisch naar **Afwezig** als iedereen weg is
- Herstelt het vorige preset bij thuiskomst

### Raamdetectie
- Detecteert een snelle temperatuurdaling (instelbare drempel en tijdvenster)
- Zet de verwarming automatisch uit tijdens het verluchten
- Hervat na een instelbare pauzetijd

### Vakantiestand
```yaml
service: smart_climate.set_vacation
target:
  entity_id: climate.woonkamer
data:
  start_date: "2025-07-01"
  end_date: "2025-07-14"
  temperature: 12
```

### Boost
```yaml
service: smart_climate.set_boost
target:
  entity_id: climate.woonkamer
data:
  duration: 60        # minuten
  target_temperature: 24
```

### Weerscompensatie
Past de doeltemperatuur aan op basis van de buitentemperatuur via een instelbare helling. Bij koud weer wordt de stooktemperatuur automatisch verhoogd.

### Vloerverwarmingspomp
- **Volgt zones**: pomp aan als een of meer zones verwarmingsvraag hebben
- **Na-looptijd**: blijft draaien nadat alle zones sluiten (restwarmte verdelen)
- **Minimale looptijd**: beschermt de pomp tegen snel in- en uitschakelen
- **Anti-vastloop**: draait elke 24 uur (instelbaar) automatisch 30 minuten om vastlopen te voorkomen
- **Voorkeurstijd**: anti-vastloop bij voorkeur om 02:00 (instelbaar)
- **Handmatig starten**:
```yaml
service: smart_climate.trigger_pump_exercise
target:
  entity_id: switch.vloerverwarming_pomp
data:
  duration: 30   # minuten (optioneel)
```

---

## Entiteiten per zone

| Platform | Entiteit | Beschrijving |
|----------|----------|-------------|
| `climate` | `climate.<naam>` | Thermostaat met presets en HVAC-modi |
| `sensor` | `sensor.<naam>_verwarmingstijd_vandaag` | Uren verwarming vandaag |
| `sensor` | `sensor.<naam>_verbruik_verwarming_vandaag` | kWh verbruik vandaag |
| `number` | `number.<naam>_pid_kp` | PID Kp live aanpasbaar |
| `number` | `number.<naam>_pid_ki` | PID Ki live aanpasbaar |
| `number` | `number.<naam>_pid_kd` | PID Kd live aanpasbaar |
| `select` | `select.<naam>_algoritme` | Algoritme wisselen zonder herstart |
| `switch` | `switch.<naam>_pomp` | Pompbeheerder met anti-vastloop |

---

## Installatie

### Via HACS (aanbevolen)
1. Ga in Home Assistant naar **HACS → Integraties**
2. Klik op de drie puntjes rechtsboven → **Aangepaste repositories**
3. Voeg toe: `https://github.com/doublesytems/Climate-control` — categorie: **Integratie**
4. Zoek naar **Smart Climate** en installeer
5. Herstart Home Assistant
6. Ga naar **Instellingen → Integraties → + Toevoegen → Smart Climate**

### Handmatig
1. Kopieer de map `custom_components/smart_climate/` naar `config/custom_components/smart_climate/`
2. Herstart Home Assistant
3. Voeg de integratie toe via de UI

---

## Kincony KC868-A6-V1 (10 zones)

De KC868-A6 heeft 6 relaisuitgangen. Voor 10 zones zijn 2 boards nodig:

```
Board 1 — relais 1-6  →  zone 1 t/m 6   (switch.zone_1 … switch.zone_6)
Board 2 — relais 1-4  →  zone 7 t/m 10  (switch.zone_7 … switch.zone_10)
Board 2 — relais 5    →  circulatiepomp  (switch.floor_pump)
Board 2 — relais 6    →  reserve
```

**Integratie via ESPHome (aanbevolen):**
1. Flash ESPHome firmware op het KC868-A6 board
2. Elke relay wordt automatisch een `switch`-entiteit in Home Assistant
3. Wijs elk relais toe als `heater`-entiteit bij het instellen van een Smart Climate zone
4. Wijs het pomprelais toe als `pump_entity` in de pompstap van de configuratiewizard

---

## Configuratiewizard

De integratie wordt ingesteld via een 6-staps wizard in de Home Assistant UI:

1. **Apparaat** — sensor, verwarming, koeling, buitensensor
2. **Algoritme** — keuze + basisparameters (tolerantie, min/max temp)
3. **PID-parameters** — Kp, Ki, Kd (alleen bij PID-algoritme)
4. **Presets** — temperatuur per preset + boostduur
5. **Geavanceerd** — aanwezigheid, raamdetectie, weerscompensatie, vermogen
6. **Pomp** — pompentiteit, zones, anti-vastloop, na-looptijd, vroeg starten

Alle instellingen zijn achteraf te wijzigen via **Integraties → Smart Climate → Configureren**.

---

## Extra state-attributen

De thermostaat-entiteit toont onder andere:

| Attribuut | Beschrijving |
|-----------|-------------|
| `algorithm` | Actief algoritme |
| `learned_heating_rate_c_per_min` | Geleerde verwarmingssnelheid |
| `early_start_active` | Vroeg starten actief |
| `window_open` | Raam open gedetecteerd |
| `presence_detected` | Aanwezigheid |
| `weather_temp_adjustment` | Weerscompensatie offset (°C) |
| `pid_output` | PID uitvoerwaarde (0–100) |
| `predicted_reach_time_min` | Geschatte tijd tot doeltemperatuur (min) |
| `boost_remaining_min` | Resterende boosttijd |
| `heater_runtime_today_h` | Verwarmingstijd vandaag (uren) |

---

## Licentie

MIT License — vrij te gebruiken en aan te passen.
