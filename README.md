# Internet Status for Home Assistant

Is the internet up, does your DNS server answer, and what is your public IP
address? Internet Status checks all three and shows them in one card, with a
graph of the ping times of the last day.

Everything is set up in the user interface, no YAML needed.

## What you get

- **Online**: on when one of the ping hosts answers (default 1.1.1.1 and
  9.9.9.9, every minute). With more than one host, one provider having a bad
  day does not mark your internet as down.
- **Ping** and **Packet loss**: the round-trip time and loss to the best
  answering host, kept in the history for graphs.
- **DNS**: on when your DNS server answers with an address for a test name.
  By default it tests the DNS server your network hands out (on Home
  Assistant OS this is read from the host's network settings, and looked up
  again regularly, so a new router or DHCP change is followed).
- **DNS response time**: how long the DNS server took to answer.
- **Public IP**: your public IPv4 address, from a service of your choice
  (default every 15 minutes):
  - [ipify](https://www.ipify.org): open source, states it keeps no logs;
  - [Mullvad](https://mullvad.net/en/check): states it keeps no logs;
  - your own URL that answers with the IP address, as plain text or as JSON
    with an `ip` field;
  - or not at all.
- An **Internet Status** card in the dashboard card picker: a green or red
  status bar for a quick answer, the three statuses with a coloured icon, and
  Home Assistant's history graph of the ping times. See [The card](#the-card).

All hosts, the DNS server, the test name, the service and the intervals can be
changed later with **Configure** on the integration.

## Installation

### HACS (custom repository)

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=milamaja&repository=ha-internet-status&category=integration)

The button opens this repository in HACS (it uses [My Home Assistant](https://www.home-assistant.io/integrations/my/), which is on by default). Or add it by hand:

1. In HACS, open the menu (three dots, top right) and choose **Custom repositories**.
2. Add `https://github.com/milamaja/ha-internet-status` with category **Integration**.
3. Install **Internet Status** and restart Home Assistant
   (**Settings, System**, power icon top right, **Restart Home Assistant**).

Don't have HACS yet? See [the HACS installation guide](https://hacs.xyz/docs/use/).

### Manual

1. Copy the folder `custom_components/internet_status` into the `custom_components` folder of your Home Assistant configuration directory.
2. Restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up Internet Status.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=internet_status)

Or go to **Settings, Devices & services, Add integration** and search for
**Internet Status**. The defaults work for most homes: click **Submit**.

| Setting | Default | |
|---|---|---|
| Ping hosts | `1.1.1.1, 9.9.9.9` | One or more addresses or names, separated by commas |
| Ping every | 60 s | |
| DNS server | empty | Empty: the DNS server your network hands out |
| Name to look up | `home-assistant.io` | The DNS server has to answer with an address for it |
| Check DNS every | 60 s | |
| Public IP service | ipify | ipify, Mullvad, your own URL, or none |
| Own URL | | Only for "Own URL" |
| Look up the public IP every | 15 min | |

## The card

The **Internet Status** card gives the quick answer to "is it the internet,
or is it this website?", and the details behind it.

<p><img src="https://raw.githubusercontent.com/milamaja/ha-internet-status/main/images/card.png" width="420" alt="Internet Status card: Internet OK, DNS, public IP and the ping graph of the last day"></p>

- **Status bar** at the top:
  - green **Internet OK**, with the current ping time;
  - red **No internet**: none of the ping hosts answers;
  - red **DNS not working**: the internet is reachable, but the DNS server
    does not answer, so websites and apps cannot find their servers;
  - grey **Status unknown**: the checks have no result yet, for example just
    after Home Assistant started.

  The public IP does not count: a service that does not answer does not mean
  your internet is down.
- **Details**: a row each for **Internet** (online or offline, ping time,
  packet loss when there is any), **DNS** (OK or the problem, response time,
  the server that was asked) and **Public IP**, with a green, red or grey icon.
- **Graph**: Home Assistant's own history graph of the ping times, by default
  of the last 24 hours. Hover or tap it for the values.

Tap the status bar or a row to open its details and history, or set your own
`tap_action` (see the options).

### Adding the card

1. Open your dashboard, click the **pencil** (top right) to edit it.
2. Click **Add card** and search for **Internet Status**.
3. Change the options below if you like.
4. Click **Save**.

### Options

| Option in the editor | YAML | Default | |
|---|---|---|---|
| Title (optional) | `title` | none | A title above the status bar |
| Internet Status device | `device_id` | the first one | Leave it empty: there is one Internet Status set-up |
| Show internet, DNS and public IP | `show_details` | on | The three rows under the status bar |
| Show the ping graph | `show_graph` | on | The history graph of the ping times |
| Hours in the graph | `hours_to_show` | 24 | 1 to 168 hours |
| Tap action | `tap_action` | none | What a tap on the status bar or a row does, as in other cards (navigate, more-info, perform-action, ...). Empty: open the details of what you tapped |

With **Show internet, DNS and public IP** and **Show the ping graph** both
off, the card is just the coloured status bar: small enough for any
dashboard or wall tablet.

The card fills the width of its column, or of its section when that is wider.

```yaml
type: custom:internet-status-card
title: Internet          # optional
show_details: true       # Internet, DNS and Public IP rows
show_graph: true         # ping graph
hours_to_show: 24        # hours in the graph
```

### Only when something is wrong

<p><img src="https://raw.githubusercontent.com/milamaja/ha-internet-status/main/images/card-down.png" width="420" alt="The compact card when the internet is down: No internet"></p>

Show the compact card at the top of a dashboard only while the internet or
DNS is down, with Home Assistant's own visibility conditions. For example as
the first section of a sections dashboard, spanning its full width:

```yaml
type: grid
column_span: 4           # the full width of a dashboard with 4 columns
cards:
  - type: custom:internet-status-card
    show_details: false
    show_graph: false
visibility:
  - condition: or
    conditions:
      - condition: state
        entity: binary_sensor.internet_online
        state: "off"
      - condition: state
        entity: binary_sensor.internet_dns
        state: "off"
```

In the editor this is the **Visibility** tab of the section (or of the card).
The entity names above are the defaults; check yours under **Settings,
Devices & services, Internet Status**.

### The entities in other cards

The entities work in any other card as well, for example a tile card for
**Online**, or a history graph of **DNS response time**.

## Notes

- Pings need permission to send ICMP. Home Assistant OS and the usual Docker
  set-ups allow this. If not, the log says so and the internet check is off;
  the DNS and public IP checks keep working.
- The public IP is looked up over IPv4: with IPv6 every device has its own
  address, IPv4 is the address of the connection.

## License

MIT, see [LICENSE](LICENSE).
