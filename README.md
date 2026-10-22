# Notify HTML Proxy

A tiny Home Assistant custom integration that puts a **plain-text → HTML
converting proxy** in front of another `notify` service.

## Why

Some notify services interpret `message` as HTML (for example the built-in
**Google Mail** integration), while most others treat it as plain text. When
both are members of the same `notify` group, you can't write a message that
looks right in both: `\n` is collapsed by HTML, and `<br />` shows up literally
in plain-text services.

This integration registers a new notify service that:

1. takes a plain-text `message`,
2. HTML-escapes it (`&`, `<`, `>`) and converts newlines to `<br>`,
3. forwards the call, with `title`, `target` and `data` unchanged, to the
   notify service you configured.

Put the proxy into your notify group instead of the HTML-interpreting service,
and keep writing plain text everywhere.

## Installation

### HACS (custom repository)

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/andreipoenaru/ha-notify-html-proxy` with
   category **Integration**.
3. Download **Notify HTML Proxy** and restart Home Assistant.

### Manual

Copy `custom_components/notify_html_proxy` into the `custom_components`
directory of your Home Assistant configuration and restart.

## Configuration

```yaml
notify:
  - platform: notify_html_proxy
    name: gmail_html                       # creates notify.gmail_html
    target_service: your_google_mail_service  # notify.your_google_mail_service
```

| Option           | Required | Description                                                                                  |
| ---------------- | -------- | -------------------------------------------------------------------------------------------- |
| `name`           | no       | Name of the service created by the proxy (`notify.<name>`). Defaults to `notify_html_proxy`. |
| `target_service` | yes      | The notify service to forward to. `notify.foo` and `foo` are both accepted.                  |

Use the proxy in a notify group in place of the original service:

```yaml
notify:
  - platform: group
    name: maintenance
    services:
      - action: mobile_app_my_phone
      - action: gmail_html
```

Then call it with plain text:

```yaml
action: notify.maintenance
data:
  title: Maintenance
  message: |
    First line
    Second line with <angle brackets> & ampersands
```

One proxy entry is needed per target service.

## Behavior and limitations

- Only `message` is converted. `title` (e.g. the email subject), `target` and
  `data` are forwarded untouched. Fields are only forwarded when set, so the
  target's own defaults still apply.
- URLs are **not** turned into links.
- Because the output is HTML, runs of spaces and leading indentation are
  collapsed by the mail client; only newlines are preserved.
- The target service is looked up when a message is sent, not at startup, so
  load order between integrations doesn't matter. If it doesn't exist, an
  error is raised and logged.
- `target_service` must not point to the proxy itself.
- This is a legacy YAML `notify` platform; changes to the configuration need a
  Home Assistant restart.

## Development

CI runs [hassfest](https://developers.home-assistant.io/blog/2020/04/16/hassfest/)
and the [HACS action](https://hacs.xyz/docs/publish/action/) on every push.

Releases: bump `version` in `custom_components/notify_html_proxy/manifest.json`
and publish a GitHub release whose tag matches it (e.g. `v0.1.0`).

## License

MIT
