# 9292 OV

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=vinnie1234&repository=HomeAssistant9292&category=integration)
[![Add the integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ov_9292)

Public transport journeys from **9292** in Home Assistant: the next departure, arrival, travel time, delay and transfers between two places, linked to a person, plus a card with the legs of the journey and a map.

## Setup

1. Open **HACS**, search for **9292 OV** and choose **Download**, then restart Home Assistant. (Or use the *Open in HACS* button above.)
2. **Settings → Devices & Services → Add integration → 9292 OV**, choose the refresh interval.
3. Open **Configure** on the integration and choose **Add a route**.

## Adding a route

**In the card (with live search):** as an administrator the card shows *Route toevoegen* and a pencil per route. Type a place, station, stop or address and the matches appear while you type, without pressing anything; click one to choose it. The same form sets the name, the person and when to travel, and has a *Verwijderen* button. Options the form does not show (excluded travel modes, extra interchange time, accessibility, less walking) are kept when you edit a route, and can be changed in the settings below. Turn it off with `show_edit: false`.

**In the integration settings:** the steps below work without the card, but a form in Home Assistant cannot search while you type: you type, press submit and pick from the list.

1. **Route:** give it a name, optionally a person and travel options (see the table below).
2. **Start:** type a place, station, stop or address (for example `Veenendaal Centrum` or a street and place) and pick the right match from the list 9292 suggests.
3. **End:** the same for the destination.

Routes can be edited and removed later via **Configure**. When editing, leave a search empty to keep that place as it is.

| Option | Meaning |
|---|---|
| Name | Shown in the device name, e.g. `Work` |
| Person | Optional. Links the route to a `person`: device name `9292 Work (Vincent)` and attribute `person` on every sensor |
| When to travel | *Now* (live, default), *Leave at a certain time* or *Arrive by a certain time*, see below |
| Exclude travel modes | Bus, Ferry, On demand, Metro, Train, Tram, Services with surcharge. Excluding everything returns no journeys |
| Extra interchange time | Extra minutes for every transfer |
| Plan with accessibility / Less walking | As on 9292.nl |

## When a route travels

By default a route is live: the sensors show the next journeys from this moment. Choose *Leave at a certain time* or *Arrive by a certain time* to plan around a moment instead. You then set:

| Setting | Meaning |
|---|---|
| Time | A fixed time of day, e.g. `08:00` |
| Days | The days it applies to, e.g. Monday to Friday. The route plans for the next of these days |
| Time from an entity | Optional, **replaces** the fixed time. Use an `input_datetime`, a `time` entity, a `sensor` with a timestamp or a `calendar` (the start of the next event). The route re-plans as soon as the entity changes |
| Offset | Minutes added to the time, e.g. `-10` plans 10 minutes earlier. Useful for a calendar event: arrive 10 minutes before it starts |

How the time moves on by itself:

- **Fixed time:** the route plans for today while the time has not passed. *Leave* stays on that time for 30 minutes after it, *Arrive* switches immediately; then the next selected day takes over, so on Friday evening the route shows Monday morning.
- **Entity with a time of day** (`input_datetime` with only a time, a `time` entity): handled like a fixed time, so it repeats every selected day.
- **Entity with a date and time** (`input_datetime` with date, a timestamp sensor, a calendar event): used exactly as it is. When that moment has passed, the route has no time and shows as unavailable until the entity gets a new one.

Examples: an `input_datetime.work_start` set to 09:00 with *Arrive by* and offset `-15`; or `calendar.work` with *Arrive by* to always be on time for your next appointment.

The Lines sensor has the attributes `timing` (`now`, `departure` or `arrival`) and `target_time` (the moment the route is planned around), and the card shows e.g. *Vertrekken om 08:00 · morgen* under the route name.

*Arrive by* asks 9292 for journeys that arrive at that time; check the first results against 9292.nl the first time.

## Reading a route

Every route is a device (`9292 <name> (<person>)`) with these sensors. They describe the **next journey that is not cancelled**, leaving from now.

| Sensor | Value |
|---|---|
| Departure | Real-time departure (the planned time is in the attribute `planned_departure`) |
| Arrival | Arrival time |
| Travel time | Minutes |
| Delay | Minutes between planned and real-time departure |
| Transfers | Number of transfers |
| Lines | Line numbers, e.g. `83 · 3245 · 3147`, with the attributes below |

Attributes of the **Lines** sensor:

| Attribute | Example |
|---|---|
| `from`, `to` | `Veenendaal`, `Nijmegen` |
| `legs` | `[{mode: Walking, line: null}, {mode: Bus, line: "83"}, {mode: FastTrain, line: "3245"}]` |
| `lines`, `operators`, `modes` | `["83", "3245"]`, `["RRReis", "NS"]`, `["Bus", "FastTrain"]` |
| `price`, `occupancy`, `detour` | `13.32`, `2`, `false` |
| `person` | `person.vincent` |
| `upcoming` | The next 5 journeys with `departure_actual`, `arrival`, `duration_min`, `delay_min`, `transfers`, `legs`, `lines`, `cancelled` |

Entity ids follow the device and sensor names, for example `sensor.9292_work_vincent_departure`. Check the exact ids under **Settings → Devices & Services → 9292 OV**.

### Using it in templates

```yaml
# Minutes until the next departure
{{ ((states('sensor.9292_work_vincent_departure') | as_datetime) - now()).total_seconds() // 60 | int }}

# The second journey, from the upcoming list
{% set trip = state_attr('sensor.9292_work_vincent_lines', 'upcoming')[1] %}
{{ as_timestamp(trip.departure_actual) | timestamp_custom('%H:%M') }} - {{ trip.duration_min }} min

# Everything that belongs to a person
{{ states.sensor | selectattr('attributes.person', 'eq', 'person.vincent') | map(attribute='entity_id') | list }}
```

### Automation examples

Notify when the next journey is delayed:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.9292_work_vincent_delay
    above: 10
actions:
  - action: notify.notify
    data:
      message: "OV naar werk heeft {{ states('sensor.9292_work_vincent_delay') }} min vertraging"
```

Notify 15 minutes before departure, only when the person is home:

```yaml
triggers:
  - trigger: time_pattern
    minutes: "/1"
conditions:
  - condition: state
    entity_id: person.vincent
    state: home
  - condition: template
    value_template: >
      {{ 14 < ((states('sensor.9292_work_vincent_departure') | as_datetime) - now()).total_seconds() / 60 <= 15 }}
actions:
  - action: notify.notify
    data:
      message: "Over 15 minuten vertrekt je OV (lijnen {{ states('sensor.9292_work_vincent_lines') }})"
```

## The card

The integration adds the card `custom:ov-9292-card`; it appears in the card picker as *9292 OV*. It shows per route the next departure with delay, arrival, travel time, a strip of the legs (walk, bus, train with line numbers), the following journeys (click one to show its legs) and a map with the start (A) and end (B). *Bekijk op kaart* zooms to a route.

**Reisdetails** expands a journey like on 9292.nl: every stop with planned time (struck through) and real-time (red when late), platform (*Spoor* for trains, *Perron* for buses), the walk with minutes and metres, the transfer time, the bus with its line number and direction, the list of stops, and messages of the operator. For trains only the kind (IC / Sprinter) is shown, not the train number. With the details open the map draws the real route per leg: buses and trains as coloured lines, walking dotted.

```yaml
type: custom:ov-9292-card
show_map: true          # map next to / under the list
show_legs: true         # walk, bus, train with line numbers
show_upcoming: true     # the following journeys
max_upcoming: 3         # 1 - 5
show_person: true       # name and picture of the person on the route
show_price: false       # price, when 9292 gives one
show_details: true      # button Reisdetails: stops, platforms, transfers, disruptions
show_edit: true         # administrators: add / edit / remove routes in the card, with live place search
person: person.vincent  # only routes of this person
my_routes_only: false   # only routes of the person linked to the logged-in user
height: 520             # card height in px on wide screens
```

All options can also be set in the card editor. Without the details open the map shows the start and end of the route with a dashed line between them; the real route appears when you open *Reisdetails* of the selected route.

If the card does not show after an update, refresh the browser (Ctrl+F5).

## Notes

- The integration uses the same unofficial API as 9292.nl, including the request signature its website sends. It can stop working if 9292 changes that; there is no official support.
- Routes made before places could be searched keep working but show the 9292 id as name and have no marker on the map until you edit them and search the places again.
