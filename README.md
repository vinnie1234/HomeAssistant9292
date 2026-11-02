# 9292 OV

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Public transport journeys from **9292** in Home Assistant: the next departure, arrival, travel time, delay and transfers between two places, linked to a person, plus a card with the legs of the journey and a map.

## Setup

1. Install via HACS (custom repository, category *Integration*) and restart Home Assistant.
2. **Settings → Devices & Services → Add integration → 9292 OV**, choose the refresh interval.
3. Open **Configure** on the integration and choose **Add a route**.

## Adding a route

1. **Route:** give it a name, optionally a person and travel options (see the table below).
2. **Start:** type a place, station, stop or address (for example `Veenendaal Centrum` or a street and place) and pick the right match from the list 9292 suggests.
3. **End:** the same for the destination.

Routes can be edited and removed later via **Configure**. When editing, leave a search empty to keep that place as it is.

| Option | Meaning |
|---|---|
| Name | Shown in the device name, e.g. `Work` |
| Person | Optional. Links the route to a `person`: device name `9292 Work (Vincent)` and attribute `person` on every sensor |
| Exclude travel modes | Bus, Ferry, On demand, Metro, Train, Tram, Services with surcharge. Excluding everything returns no journeys |
| Extra interchange time | Extra minutes for every transfer |
| Plan with accessibility / Less walking | As on 9292.nl |

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
person: person.vincent  # only routes of this person
my_routes_only: false   # only routes of the person linked to the logged-in user
height: 520             # card height in px on wide screens
```

All options can also be set in the card editor. Without the details open the map shows the start and end of the route with a dashed line between them; the real route appears when you open *Reisdetails* of the selected route.

If the card does not show after an update, refresh the browser (Ctrl+F5).

## Notes

- The integration uses the same unofficial API as 9292.nl, including the request signature its website sends. It can stop working if 9292 changes that; there is no official support.
- Routes made before places could be searched keep working but show the 9292 id as name and have no marker on the map until you edit them and search the places again.
