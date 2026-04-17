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

### Cascade regeling (primaire + secundaire bron)
De primaire bron (bijv. airco) gaat altijd als eerste aan. De secundaire bron (bijv. vloerverwarming) springt pas bij als de primaire bron het doel niet haalt binnen de ingestelde tijd. Gebruik ook zonder secundaire bron (primary-only).

**Voorbeeld tijdlijn** — doeltemperatuur 20 °C, huidig 17 °C:
```
00:00  Te koud → Airco (primaire) gaat aan
00:30  Na 30 min: temp 18,2°C — nog 1,8°C tekort → Vloerverwarming (secundaire) aan
00:55  Temperatuur bereikt 20°C
01:05  Vloerverwarming (na vertraging) uit → Airco uit
```

| Instelling | Standaard | Beschrijving |
|-----------|-----------|-------------|
| Wachttijd secundaire | 30 min | Hoe lang de primaire bron de kans krijgt |
| Temperatuurtekort | 1,5 °C | Hoeveel onder doel om secundaire te activeren |
| Uitschakelvertraging | 10 min | Secundaire nog even aan na bereiken doel |
| **Onmiddellijke drempel** | 3,0 °C | Bij groter tekort → secundaire meteen aan, zonder wachttijd |

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
Stel tijdblokken in per dag via de service `smart_climate.set_schedule`:

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
- **Raamsensor**: koppel een `binary_sensor` (bijv. een contactschakelaar) rechtstreeks. Zodra de sensor "aan" gaat, stopt de verwarming direct. Bij sluiten hervat hij automatisch.
- **Temperatuurval**: detecteert een snelle temperatuurdaling (instelbare drempel en tijdvenster) als alternatief zonder sensor
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

### Koeling blokkeren bij lage buitentemperatuur
Stel een buitentemperatuurdrempel in (bijv. 16 °C). Als het buiten kouder is, wordt koeling volledig geblokkeerd — handig bij airco's die anders onnodig zouden koelen terwijl het buiten al koud is.

### Geleidelijke temperatuurovergang (ramp)
Bij een preset- of temperatuurwissel klimt de doeltemperatuur stapsgewijs naar het nieuwe doel. Zo gaat de verwarming niet meteen vol aan bij een grote sprong (bijv. Eco → Comfort), maar warmt de ruimte rustig op.

| Instelling | Standaard | Beschrijving |
|-----------|-----------|-------------|
| Stapgrootte | 0,5 °C | Temperatuursprong per stap |
| Stapinterval | 5 min | Wachttijd tussen stappen |

### Persistent notification bij vertraging
Activeer een melding als de ruimte na een instelbaar aantal minuten het doel nog niet heeft bereikt. De melding verschijnt in Home Assistant en verdwijnt automatisch zodra het doel bereikt is of de thermostaat wordt uitgezet. Optioneel wordt ook een pushbericht gestuurd via een `notify.*`-service (bijv. je mobiele app).

### Vorstbeveiliging
Stel een minimale temperatuur in (bijv. 5 °C). Als de ruimtetemperatuur hieronder zakt, wordt de verwarming automatisch geactiveerd — ook als de thermostaat op UIT staat. Zo voorkom je bevroren leidingen bij langdurige afwezigheid.

### Sensorfailsafe
Als de temperatuursensor langer dan de ingestelde tijd geen update geeft (bijv. 30 minuten), schakelt het systeem alle verwarming/koeling uit. Zo voorkom je dat de verwarming doorloopt bij een defecte of gevallen sensor.

### Vochtcomfortcorrectie
Koppel een luchtvochtigheidssensor. Bij hoge vochtigheid voelt een temperatuur warmer aan, dus de doeltemperatuur wordt automatisch iets verlaagd (en omgekeerd). De correctie is instelbaar met een referentievochtigheid en een comfortfactor (°C per % afwijking).

> **Let op:** de vochtcorrectie is alleen actief in pure **verwarmingsmodus (HEAT)**. Bij koelen (COOL / Auto) geldt altijd de ingestelde doeltemperatuur zonder aanpassing.

### Prijsgestuurde setback
Koppel een energieprijssensor (bijv. Nordpool of ENTSO-E). Als de stroomprijs boven de drempelwaarde stijgt, wordt de doeltemperatuur automatisch verlaagd (bij verwarmen) of verhoogd (bij koelen) met de ingestelde setback-waarde. Bij dalende prijs keert het systeem automatisch terug naar het oorspronkelijke doel.

### Hold mode (tijdelijke temperatuuroverschrijving)
Overschrijf de doeltemperatuur voor een bepaalde duur via een service. Na afloop keert het systeem automatisch terug naar het vorige doel (preset of schema).

```yaml
service: smart_climate.set_hold
target:
  entity_id: climate.woonkamer
data:
  temperature: 22
  duration: 120   # minuten
```

```yaml
service: smart_climate.clear_hold
target:
  entity_id: climate.woonkamer
```

### Seizoensdetectie (auto HEAT/COOL)
Stel twee drempeltemperaturen in op basis van de buitentemperatuur. Het systeem schakelt automatisch van verwarmings- naar koelingsmodus (en terug) zodra de buitentemperatuur de drempel passeert. Zo hoef je niet handmatig de modus te wisselen bij seizoensovergangen.

| Instelling | Standaard | Beschrijving |
|-----------|-----------|-------------|
| Koeldrempel | 22 °C buiten | Boven deze temperatuur → COOL |
| Verwarmingsdrempel | 18 °C buiten | Onder deze temperatuur → HEAT |

### Vakantiekalender (HA calendar)
Koppel een Home Assistant calendar-entiteit als vakantiekalender. Als er een actief vakantie-evenement is, schakelt Smart Climate automatisch naar het **Afwezig**-preset. Bij het einde van het evenement keert het systeem terug naar de normale werking.

### Weerscompensatie
Past de doeltemperatuur aan op basis van de buitentemperatuur via een instelbare helling (stooklijn). Bij koud weer wordt de stooktemperatuur automatisch verhoogd.

> **Let op:** de weerscompensatie is alleen actief in pure **verwarmingsmodus (HEAT)**. Bij koelen (COOL / Auto) geldt altijd de ingestelde doeltemperatuur zonder aanpassing.

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
| `sensor` | `sensor.<naam>_koeltijd_vandaag` | Uren koeling vandaag |
| `sensor` | `sensor.<naam>_verbruik_verwarming_vandaag` | kWh verbruik vandaag (vereist watt > 0) |
| `sensor` | `sensor.<naam>_verbruik_koeling_vandaag` | kWh koeling vandaag (vereist watt > 0) |
| `sensor` | `sensor.<naam>_effectieve_doeltemperatuur` | Werkelijk stuurpunt incl. alle correcties (°C) |
| `sensor` | `sensor.<naam>_verwarmingssnelheid` | Geleerde °C/min (EMA over sessies) |
| `sensor` | `sensor.<naam>_tijd_tot_doel` | Geschatte minuten tot doeltemperatuur |
| `sensor` | `sensor.<naam>_volgende_schema` | Volgende schema-overgang (bijv. "do 17:30 → comfort") |
| `sensor` | `sensor.<naam>_pid_uitvoer` | PID-uitvoerwaarde 0–100 % (alleen PID) |
| `sensor` | `sensor.<naam>_hold_resterende_tijd` | Resterende minuten hold-modus |
| `binary_sensor` | `binary_sensor.<naam>_prijssetback_actief` | Aan als prijsgestuurde setback actief is |
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

## Configuratiewizard

De integratie wordt ingesteld via een 7-staps wizard in de Home Assistant UI:

1. **Apparaat** — sensor, verwarming, koeling, buitensensor
2. **Algoritme** — keuze + basisparameters (tolerantie, min/max temp)
3. **PID-parameters** — Kp, Ki, Kd (alleen bij PID-algoritme)
4. **Presets** — temperatuur per preset + boostduur
5. **Geavanceerd** — aanwezigheid, raamsensor, raamdetectie, koeling blokkeren, weerscompensatie, AC-ruststand, temperatuur ramp, notificatie, vorstbeveiliging, sensorfailsafe, vochtcorrectie, energieprijssetback, seizoensdetectie, vakantiekalender
6. **Cascade** — primaire bron (airco), secundaire bron (vloer), wachttijd, drempel, onmiddellijke drempel
7. **Pomp** — pompentiteit, zones, anti-vastloop, na-looptijd, vroeg starten

Alle instellingen zijn achteraf te wijzigen via **Integraties → Smart Climate → Configureren** (inclusief cascade- en pompstappen).

### Diagnostics
Via **Instellingen → Integraties → Smart Climate → Diagnostics** download je een volledig statusoverzicht: actieve modus, cascade-staat, geleerde verwarmingssnelheid, PID-integral, ramp-doel en meer. Handig bij het melden van problemen.

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
| `cascade_primary_on` | Primaire bron (airco) actief |
| `cascade_secondary_on` | Secundaire bron (vloer) actief |
| `cascade_reason` | Reden van huidige cascade-status |
| `cascade_secondary_since_min` | Minuten dat secundaire bron actief is |
| `window_open` | Raam open (sensor of temperatuurval) |
| `hold_active` | Hold-modus actief |
| `hold_temp` | Hold doeltemperatuur |
| `hold_remaining_min` | Resterende holdtijd (min) |
| `frost_protection_active` | Vorstbeveiliging actief |
| `humidity_adjustment` | Vochtcorrectie offset (°C) |
| `price_setback_active` | Prijsgestuurde setback actief |
| `season_mode` | Automatische modus (HEAT/COOL) |
| `vacation_active` | Vakantiekalender actief |

---

## Licentie

MIT License — vrij te gebruiken en aan te passen.
