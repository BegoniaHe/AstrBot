# Session Control

Session control is useful for workflows that need several consecutive inputs
without sending every step to the LLM, such as surveys, games, or guided
configuration.

The public SDK exports `session_waiter` and `SessionController` from
`astrbot.api.util`:

```python
import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.util import SessionController, session_waiter
```

This example waits for subsequent messages in the same session after receiving
`/idiom-chain`:

```python
@filter.command("idiom-chain")
async def idiom_chain(self, event: AstrMessageEvent):
    yield event.plain_result('Send a four-character idiom, or "exit" to stop.')

    @session_waiter(timeout=60, record_history_chains=False)
    async def waiter(
        controller: SessionController,
        next_event: AstrMessageEvent,
    ) -> None:
        idiom = next_event.message_str.strip()

        if idiom == "exit":
            await next_event.send(
                next_event.plain_result("Idiom chain ended.").chain
            )
            controller.stop()
            return

        if len(idiom) != 4:
            await next_event.send(
                next_event.plain_result(
                    "The idiom must contain four characters. Try again."
                ).chain
            )
            controller.keep(timeout=60, reset_timeout=True)
            return

        result = next_event.make_result()
        result.chain = [Comp.Plain("先见之明")]
        await next_event.send(result.chain)

        # Wait for another message and restart the 60-second timeout.
        controller.keep(timeout=60, reset_timeout=True)

    try:
        await waiter(event)
    except TimeoutError:
        yield event.plain_result("The session timed out.")
    except Exception:
        logger.exception("Idiom-chain session failed")
        yield event.plain_result(
            "The session ended unexpectedly. Contact the administrator."
        )
    finally:
        event.stop_event()
```

The waiter already handles a subsequent event, so it cannot use `yield`.
Send results with `await next_event.send(...)` instead. The
`await waiter(event)` call remains pending until `controller.stop()`, a
timeout, or an exception from the handler.

## Default Session Key

The default session filter uses `event.unified_msg_origin` as its key, not only
`sender_id`. This string identifies the platform instance and corresponding
conversation. Only later events that produce the same
`unified_msg_origin` enter the active waiter.

Internal extension types such as `SessionFilter` are not exported from
`astrbot.api.util`. Plugins should not import
`astrbot.core.utils.session_waiter` to customize the key; internal interfaces
may change with the core implementation.

## SessionController

- `keep(timeout, reset_timeout=True)` keeps waiting and restarts the specified
  timeout from now.
- `keep(timeout, reset_timeout=False)` adds `timeout` to, or subtracts it from,
  the remaining time. A resulting timeout at or below zero ends the session.
- `stop()` ends the session immediately.
- `get_history_chains()` returns recorded message chains. Subsequent inputs are
  recorded only when the decorator uses `record_history_chains=True`.

When a wait times out, `await waiter(event)` raises `TimeoutError`. Handle
timeouts and other errors at the outer level, and stop any other long-running
tasks created by the plugin in `terminate()`.
