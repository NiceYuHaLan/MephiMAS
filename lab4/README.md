# Лабораторная работа №4 — Диверсионный анализ и оценка надёжности МАС

Многоагентная кухня «Красти Крабс» под неблагоприятными воздействиями:
подделка и искажение сообщений, повтор, подмена цели агента,
циклическое удержание ресурса, противоречивые указания, внедрение
инструкций и недоступность инструмента. Для каждого сценария собирается
трасса, выявляются отказы, включаются защитные ограничения и повторно
оценивается устойчивость.

## Что нового относительно lab3

- Слой безопасности `src/security/`: шлюз сообщений, ключи HMAC-SHA256,
  семь защитных ограничений и монитор инцидентов.
- Восемь неблагоприятных сценариев (`src/security/attacks/`).
- Восстановление после отказа: аудит завершения и карантин заказа,
  истечение лизинга станции, аварийный ремонт инструмента.
- Метрики надёжности: `failures_total`, `integrity_score`,
  `phantom_served`, `double_serve`, `double_assignment`, `cycle_events`,
  `lost_orders`, `attacks_blocked`, `false_positives`.
- CLI `--attack` / `--defense` / `--suite`, Web-UI с выбором атаки и
  тумблером защиты.
- Сценарии `single_order` и `tool_outage`.

## Структура

```text
lab4/
├── README.md
├── REPORT.pdf           # отчёт в PDF
├── results/             # attacks.csv / attacks.json
├── docs/                # диаграммы протокола конфликта и слоя безопасности
├── src/
│   ├── main.py          # CLI: симуляция, --compare, --suite
│   ├── experiments.py   # матрица прогонов и отчёт по атакам
│   ├── simulation.py    # сборка сцены с атакой и защитой
│   ├── core/            # сообщения с подписью/nonce, шина с шлюзом
│   ├── domain/          # заказы, станции, среда, восстановление
│   ├── agents/          # агенты, аудит, карантин, порча цели/поведения
│   ├── mechanisms/      # base / central / contract_net / auction
│   ├── conflict/        # fcfs / arbitration / negotiation, лизинг станций
│   ├── security/        # base / gateway / guards / attacks
│   ├── metrics/         # метрики, включая показатели надёжности
│   ├── scenarios/       # сценарии, включая single_order и tool_outage
│   └── ui/              # web-интерфейс
└── tests/               # unittest, включая test_security.py
```

## Модель угроз

| Атака | Класс | Сценарий | Проявление отказа |
|---|---|---|---|
| `forgery` | недостоверное сообщение | `dinner_rush` | поддельное `order_complete` → фантомная выдача |
| `tampering` | искажение сообщения | `dinner_rush` | подмена `order_id` при валидной подписи |
| `replay` | повтор сообщения | `dinner_rush` | повторное завершение уже выданного заказа |
| `goal_substitution` | подмена цели агента | `dinner_rush` | Patrick завершает заказ без шагов |
| `cyclic_delegation` | циклическая передача | `dinner_rush` | SpongeBob навсегда удерживает станцию |
| `contradictory` | противоречивые указания | `single_order` | двойное назначение заказа |
| `instruction_injection` | внедрение инструкции | `dinner_rush` | Plankton шлёт `order_complete` как команду |
| `tool_unavailable` | недоступность средства | `tool_outage` | Sandy не выполняет инструментальную задачу |

Каждая атака реализует `Attack.setup / on_tick / on_send`; сообщения
подаются в шину через `submit_raw` либо агент переводится в
скомпрометированное состояние.

## Защитный слой

Шлюз `SecurityGateway` проверяет каждое сообщение цепочкой ограничений
(`guard`) в фиксированном порядке; при отказе сообщение не доставляется,
а в трассу пишется `security_blocked`.

| Ограничение | Проверка |
|---|---|
| `authentication` | HMAC-подпись и известный отправитель |
| `provenance` | недоверенный агент не может давать команды |
| `authorization` | права по performative, действию и событию |
| `integrity` | HMAC канонического payload |
| `replay` | nonce и окно 8 тиков |
| `consistency` | FSM заказа и станции |
| `cycle` | повтор заявки на станцию в одном тике |

Дополнительно работают механизмы восстановления:

- **Аудит завершения** — Krabs сверяет прогресс шагов; при расхождении
  заказ уходит в карантин и переназначается.
- **Лизинг станции** — резерв без владельца дольше 4 тиков снимается,
  заказ освобождается.
- **Аварийный ремонт** — сломанная станция восстанавливается через
  6 тиков, чтобы инструмент не блокировал систему навсегда.

## Запуск

Требуется Python 3.10+ (проверено на 3.14), внешних зависимостей нет.

```bash
cd lab4

# список сценариев, механизмов, режимов конфликта, атак и защит
python3 -m src.main --list

# одна симуляция
python3 -m src.main --scenario smoke --quiet
python3 -m src.main --scenario dinner_rush --attack forgery
python3 -m src.main --scenario dinner_rush --attack forgery --defense on

# полный матричный прогон: контроль + 8 атак × {off, on}
python3 -m src.main --suite

# сравнение режимов конфликта (как в lab3)
python3 -m src.main --compare --mechanisms central \
  --scenarios station_rush,dinner_rush --conflicts fcfs,negotiation,arbitration
```

Веб-интерфейс:

```bash
python3 -m src.ui.web --scenario dinner_rush --defense off
# затем http://127.0.0.1:8000/ — селектор «Атака» и тумблер «Защита»
```

## Результаты

`python3 -m src.main --suite` сохраняет `results/attacks.csv` и
`results/attacks.json` и печатает сводную таблицу. Контрольные прогоны
(защита включена, атаки нет) полностью совпадают с базовой линией:
0 блокировок, 0 отказов, 0 ложных срабатываний.

| Атака | Без защиты | С защитой |
|---|---|---|
| `forgery` | 2/7 обслужено, 6 отказов | 7/7, 1 блокировка, 0 отказов |
| `tampering` | 7/7, 1 фантомная выдача | 7/7, 1 блокировка, 0 отказов |
| `replay` | 7/7, 1 повтор | 7/7, 1 блокировка, 0 отказов |
| `goal_substitution` | 7/7, 5 фантомных выдач | 7/7, аудит и переназначение |
| `cyclic_delegation` | 1/7, 6 потерянных заказов | 7/7, лизинг и переназначение |
| `contradictory` | 1/1, двойное назначение | 1/1, 1 блокировка |
| `instruction_injection` | 2/7, 6 отказов | 7/7, 1 блокировка |
| `tool_unavailable` | 1/2, 1 потерянный заказ | 2/2, аварийный ремонт |

Интегральная оценка `integrity_score = 1 − failures_total / orders_total`
достигает 1.0 для всех атак при включённой защите.

## Проверка

```bash
python3 -m unittest discover -s tests -t . -v
python3 -m compileall -q src tests
```

## Отчёт

`REPORT.pdf` — итоговый отчёт по лабораторной работе.

Диаграммы при необходимости пересобираются так:

```bash
dot -Tsvg docs/conflict.dot -o docs/conflict.svg
dot -Tsvg docs/security.dot -o docs/security.svg
```
