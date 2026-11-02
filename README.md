# 9292 OV

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Public transport journeys from **9292** as Home Assistant sensors: the next departure, arrival, travel time, delay and transfers between two places, linked to a person.

## Setup

1. Install via HACS (custom repository, category *Integration*) and restart Home Assistant.
2. **Settings → Devices & Services → Add integration → 9292 OV**, choose the refresh interval.
3. Open **Configure** on the integration and choose **Add a route**.

## Routes

| Field | Meaning |
|---|---|
| Name | Shown in the device name, e.g. `Work` |
| From / To | 9292 location ids: the part after `from=` / `to=` in a 9292.nl URL, e.g. `utrecht/voorbeeldstraat-1` or `station-nijmegen`. Spaces and capitals are converted |
| Person | Optional. Links the route to a `person`: device name `9292 Work (Vincent)` and attribute `person` on every sensor |
| Exclude travel modes | Bus, Ferry, On demand, Metro, Train, Tram, Services with surcharge. Excluding everything returns no journeys |
| Extra interchange time | Extra minutes for every transfer |
| Plan with accessibility / Less walking | As on 9292.nl |

Routes can be edited and removed later via **Configure**.

## Sensors per route

| Sensor | Value |
|---|---|
| Departure | Real-time departure of the next journey (planned time in `planned_departure`) |
| Arrival | Arrival time |
| Travel time | Minutes |
| Delay | Minutes between planned and real-time departure |
| Transfers | Number of transfers |
| Lines | Line numbers, with `modes`, `operators`, `price`, `occupancy` and the `upcoming` journeys as attributes |

Cancelled journeys are skipped for the next-departure sensors but appear in `upcoming`.

### Automation example

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

## Notes

- The integration uses the same unofficial API as 9292.nl, including the request signature its website sends. It can stop working if 9292 changes that; there is no official support.
- Places are plain 9292 ids; there is no search-as-you-type yet.
