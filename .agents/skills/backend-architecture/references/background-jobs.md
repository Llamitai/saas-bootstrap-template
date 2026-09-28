# Background jobs (RabbitMQ)

Paths are relative to `backend/`. A deferred command is an ordinary command
dispatched with `run_async=True`; it is published to RabbitMQ and a worker
re-hydrates and runs it inline in its own session. The project profile says
whether a worker runs in a given environment.

| Piece | Location |
| --- | --- |
| Enqueuer (`MetaCommand` → persistent JSON message, publisher confirms) | `src/common/infrastructure/buses/rabbitmq_command_enqueuer.py` |
| Topology (exchange, quorum queue, DLX/DLQ) | `src/common/infrastructure/rabbitmq/topology.py` |
| Process-wide connection and channels (`RabbitMQBroker`) | `src/common/infrastructure/rabbitmq/broker.py` |
| Consumer (ack, retry, dead-letter, graceful stop) | `src/common/infrastructure/rabbitmq/consumer.py` |
| `MetaCommand` (`command_name` + `to_dict` payload) | `src/common/domain/buses/meta_command.py` |
| Registry of deferrable commands | `src/common/application/data/tasks_mapping.py` (`async_tasks_mapping`) |
| Resolver (lookup, `from_dict`, dispatch) | `src/common/application/async_tasks/resolver.py` |
| Worker (`CommandRunner`, `run_worker`) | `config/worker.py`, run with `python -m config.worker` |
| Exemplar | `SoftDeleteTenantCommand` dispatched by `src/tenants/presentation/endpoints/settings/soft_deleter.py` (202) |

## Required connections

1. A `@dataclass` command whose `to_dict`/`from_dict` round-trip JSON-safe values.
2. Its handler subscribed in the module wiring, like any command.
3. Its class registered in `async_tasks_mapping`.
4. `dispatch(command, run_async=True)`, which returns `None` once the broker
   confirmed the message; the endpoint answers without the result (202 in the
   exemplar).

Regular commands need no change to `config/worker.py`.

## Installed behavior to respect

- The API lifespan and the worker each open one robust connection
  (`RabbitMQBroker.connect`) and pass `broker.command_enqueuer()` to
  `build_async_bus`. Never open a connection per request or per command.
- `enqueue` waits for the publisher confirm and raises `CommandEnqueueError` on a
  nack, an unroutable message or a timeout (`RABBITMQ_PUBLISH_TIMEOUT_SECONDS`);
  the request fails instead of losing the command.
- The worker opens a session per message from `DatabaseConfig` and builds the
  domain and bus with the same builders as the API. Never capture the request
  session in a deferred command.
- Delivery is at least once. The worker acks only after success. A failure,
  exception or timeout (`AWS_LAMBDA_MAX_TIMEOUT`) is requeued after an
  exponential pause until the `RABBITMQ_DELIVERY_LIMIT`-th delivery, which is
  dead-lettered to `<queue>.dlq`. Malformed bodies and `NotRegisteredCommand`
  go to the DLQ at once. Handlers must be safe to run again.
- Concurrency per worker process equals `RABBITMQ_PREFETCH`. SIGTERM stops
  consuming and waits `RABBITMQ_SHUTDOWN_GRACE_SECONDS` for in-flight messages;
  unfinished ones are redelivered.
- Topology arguments are fixed at declaration; changing the delivery limit of an
  existing queue needs a RabbitMQ policy or a new queue.

## Common mistakes

- Expecting a return value from `run_async=True`.
- Forgetting `async_tasks_mapping`: the worker dead-letters `NotRegisteredCommand`.
- Registering a command in the mapping without subscribing its handler.
- `to_dict` with raw UUID/Decimal/datetime values.
- A non-idempotent handler (for example one that sends an email before a write
  that can still fail): a retry repeats the side effect.
