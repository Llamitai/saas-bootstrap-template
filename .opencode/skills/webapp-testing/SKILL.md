---
name: webapp-testing
description: >
  Inspect and exercise browser interactions with Playwright or available browser
  tools: rendered state, selectors, console/network, focus and screenshots.
  Use verify-change for gate selection and technical evidence.
license: Complete terms in LICENSE.txt
---

# Web application testing

Use this execution guidance for the browser scenario selected by verify-change
or the active frontend workflow. Read the project's verification guide and
frontend Playwright config for commands, installation, gate selection and
service setup; do not maintain a second runner or acceptance checklist here.

Use the existing TypeScript Playwright suite; do not add a parallel Python product suite. The bundled Python examples/helpers remain available for standalone, explicitly requested automation. Run a helper with --help before adapting it. They are not the project's E2E gate.

Inspect rendered state before acting: navigate, wait for a meaningful locator or response, inspect DOM/screenshot, then use role/label selectors. Assert user-visible result and recovery; inspect relevant console/network errors. Use keyboard, focus and a narrow viewport for affected UI. Do not wait for networkidle universally (polling/SSE can keep a connection open) or use arbitrary sleeps instead of locator assertions.

Use the isolated service lifecycle and E2E_PORT/E2E_RUN_ID from the verification
guide. Never reuse an unidentified running server. Declare mocked network
explicitly; mocks and screenshots do not prove real API compatibility. Return
observations and limits to verify-change and the existing acceptance record.
