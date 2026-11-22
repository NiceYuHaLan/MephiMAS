const $ = (id) => document.getElementById(id);

const STATUS_LABELS = {
  IDLE: "свободен",
  ASSIGNED: "принял заказ",
  WAITING_STATION: "ждёт станцию",
  COOKING: "готовит",
  REPORTING: "отчитывается",
  REPAIRING: "ремонт",
  ASSIGNING: "распределяет",
  AWAITING_ACCEPT: "ждёт ответа",
  AUCTIONING: "торги",
  BIDDING: "делает ставку",
  COORDINATING_STATIONS: "согласует станции",
  ARBITRATING: "арбитраж",
  MAINTENANCE: "обслуживание",
  TAKING_ORDER: "принимает заказ",
  WAITING_SERVE: "ждёт подачи",
  SERVING: "подаёт",
  OBSERVING: "наблюдает",
  REQUESTING: "запрашивает",
  WAITING: "ожидает",
};

let current = null;
let scenariosReady = false;
let mechanismsReady = false;

async function api(path, options) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...options,
  });
  return response.json();
}

function text(node, value) {
  node.textContent = value == null ? "" : String(value);
}

function badge(status, label) {
  const span = document.createElement("span");
  span.className = `badge ${status}`;
  text(span, label);
  return span;
}

function renderScenarioSelect(scenarios) {
  if (scenariosReady || !scenarios) return;
  const select = $("scenario");
  select.replaceChildren();
  for (const scenario of scenarios) {
    const option = document.createElement("option");
    option.value = scenario.name;
    text(option, scenario.title);
    select.appendChild(option);
  }
  scenariosReady = true;
}

function renderMechanismSelect(mechanisms) {
  if (mechanismsReady || !mechanisms) return;
  const select = $("mechanism");
  select.replaceChildren();
  for (const mechanism of mechanisms) {
    const option = document.createElement("option");
    option.value = mechanism.name;
    text(option, mechanism.label);
    select.appendChild(option);
  }
  mechanismsReady = true;
}

function renderStats(data) {
  const metrics = data.metrics || {};
  text($("stat-tick"), data.tick);
  text($("stat-limit"), `из ${data.tick_limit}`);
  text($("stat-served"), `${metrics.orders_served || 0}/${metrics.orders_total || 0}`);
  text($("stat-messages"), metrics.messages_total || 0);
  text($("stat-coord"), `протокол ${metrics.coordination_messages || 0} · $/заказ ${metrics.coordination_cost || 0}`);
  text($("stat-revenue"), metrics.revenue || 0);
  text($("stat-tips"), `чаевые ${metrics.tips || 0}`);
  text($("stat-wait"), metrics.avg_wait || 0);
  text($("stat-makespan"), metrics.makespan || 0);
  text($("stat-latency"), metrics.assignment_latency_avg || 0);
  text($("stat-gini"), `${metrics.gini_workload || 0} / ${metrics.jain_workload || 0}`);
  text($("stat-spend"), `платежи ${metrics.coordination_spend || 0}`);
}

function renderOrders(orders) {
  const body = $("orders-body");
  body.replaceChildren();
  for (const order of orders) {
    const row = document.createElement("tr");
    const number = document.createElement("td");
    text(number, order.id + (order.priority ? " !" : ""));
    const customer = document.createElement("td");
    text(customer, `${order.customer} · стол ${order.table}`);
    const items = document.createElement("td");
    text(items, order.items.join(", "));
    const status = document.createElement("td");
    status.appendChild(badge(order.status, order.status_label));
    const cook = document.createElement("td");
    text(cook, order.assignee || "—");
    const wait = document.createElement("td");
    const late = order.status === "served" && order.wait > order.deadline - order.created;
    text(wait, `${order.wait} / ${order.deadline - order.created}${late ? " !" : ""}`);
    row.append(number, customer, items, status, cook, wait);
    body.appendChild(row);
  }
}

function renderStations(stations) {
  const box = $("stations");
  box.replaceChildren();
  for (const station of stations) {
    const card = document.createElement("div");
    card.className = "card" + (station.broken ? " broken" : station.occupant ? " working" : "");
    const head = document.createElement("div");
    head.className = "card-head";
    const name = document.createElement("span");
    text(name, station.id);
    const state = document.createElement("span");
    state.className = "state " + (station.broken ? "bad" : station.occupant ? "" : "ok");
    text(state, station.broken ? "неисправна" : station.occupant ? "занята" : "свободна");
    head.append(name, state);
    const sub = document.createElement("div");
    sub.className = "card-sub";
    text(
      sub,
      station.broken
        ? `${station.kind_label}: ожидает Sandy`
        : station.occupant
          ? `${station.kind_label}: ${station.occupant}`
          : `${station.kind_label}: готова к работе`
    );
    card.append(head, sub);
    box.appendChild(card);
  }
}

function renderAgents(agents) {
  const box = $("agents");
  box.replaceChildren();
  for (const agent of agents) {
    const card = document.createElement("div");
    card.className = "card" + (agent.state === "COOKING" ? " working" : "");
    const head = document.createElement("div");
    head.className = "card-head";
    const name = document.createElement("span");
    text(name, agent.id);
    const state = document.createElement("span");
    state.className = "state";
    text(state, STATUS_LABELS[agent.state] || agent.state);
    head.append(name, state);
    const sub = document.createElement("div");
    sub.className = "card-sub";
    text(sub, agent.role + (agent.detail ? ` · ${agent.detail}` : ""));
    card.append(head, sub);
    box.appendChild(card);
  }
}

function renderInventory(inventory) {
  const box = $("inventory");
  box.replaceChildren();
  for (const item of inventory) {
    const chip = document.createElement("span");
    chip.className = "chip";
    const label = document.createTextNode(`${item.label} `);
    const value = document.createElement("b");
    text(value, item.qty);
    chip.append(label, value);
    box.appendChild(chip);
  }
}

const SCENE_TABLES = Array.from({ length: 9 }, (_, index) => {
  const number = index + 1;
  const column = number <= 3 ? number - 1 : number <= 6 ? number - 4 : number - 7;
  const row = number <= 3 ? 0 : number <= 6 ? 1 : 2;
  return { number, x: 10 + column * 15, y: 19 + row * 21 };
});

const MAIN_AGENTS = {
  krabs: { label: "Крабс", kind: "krabs" },
  spongebob: { label: "Спанч Боб", kind: "spongebob" },
  patrick: { label: "Патрик", kind: "patrick" },
  squidward: { label: "Сквидвард", kind: "squidward" },
  sandy: { label: "Сэнди", kind: "sandy" },
  plankton: { label: "Планктон", kind: "plankton" },
};

const MODEL_SVGS = {
  krabs: `
    <svg viewBox="0 0 64 80" aria-hidden="true" focusable="false">
      <ellipse cx="32" cy="75" rx="21" ry="4" fill="#000" opacity=".28"/>
      <g stroke="#a52d23" stroke-width="5" stroke-linecap="round">
        <path d="M20 60 L12 73"/><path d="M28 63 L24 76"/>
        <path d="M36 63 L40 76"/><path d="M44 60 L52 73"/>
      </g>
      <g fill="#e94b3c" stroke="#a52d23" stroke-width="2" stroke-linejoin="round">
        <path d="M13 38 Q3 36 5 27 Q7 20 15 23 Q21 26 17 37 Z"/>
        <path d="M51 38 Q61 36 59 27 Q57 20 49 23 Q43 26 47 37 Z"/>
      </g>
      <path d="M22 31 L21 18" stroke="#e94b3c" stroke-width="5" stroke-linecap="round"/>
      <path d="M42 31 L43 18" stroke="#e94b3c" stroke-width="5" stroke-linecap="round"/>
      <ellipse cx="32" cy="46" rx="19" ry="20" fill="#e94b3c" stroke="#a52d23" stroke-width="2"/>
      <ellipse cx="26" cy="39" rx="4" ry="2.5" fill="#ff9b90" opacity=".7"/>
      <path d="M19 53 Q32 62 45 53 L43 64 Q32 70 21 64 Z" fill="#4f9fc9" stroke="#2d6d91" stroke-width="1.5"/>
      <circle cx="21" cy="15" r="8" fill="#f4f7fa" stroke="#a52d23" stroke-width="1.8"/>
      <circle cx="43" cy="15" r="8" fill="#f4f7fa" stroke="#a52d23" stroke-width="1.8"/>
      <circle cx="22.5" cy="16" r="3" fill="#10202d"/>
      <circle cx="41.5" cy="16" r="3" fill="#10202d"/>
      <circle cx="23.5" cy="15" r="1" fill="#fff"/>
      <circle cx="42.5" cy="15" r="1" fill="#fff"/>
      <path d="M25 49 Q32 55 39 49" stroke="#6e1c16" stroke-width="2" fill="none" stroke-linecap="round"/>
      <path d="M29 47 L32 51 L35 47" fill="#f4f7fa" stroke="#6e1c16" stroke-width="1" stroke-linejoin="round"/>
    </svg>`,
  spongebob: `
    <svg viewBox="0 0 64 80" aria-hidden="true" focusable="false">
      <ellipse cx="32" cy="75" rx="20" ry="4" fill="#000" opacity=".28"/>
      <rect x="23" y="57" width="6" height="17" rx="3" fill="#dfb32c"/>
      <rect x="35" y="57" width="6" height="17" rx="3" fill="#dfb32c"/>
      <rect x="20" y="70" width="11" height="6" rx="3" fill="#2d2119"/>
      <rect x="33" y="70" width="11" height="6" rx="3" fill="#2d2119"/>
      <path d="M15 38 Q7 42 9 51" stroke="#f2c94c" stroke-width="6" fill="none" stroke-linecap="round"/>
      <path d="M49 38 Q57 42 55 51" stroke="#f2c94c" stroke-width="6" fill="none" stroke-linecap="round"/>
      <rect x="14" y="15" width="36" height="44" rx="8" fill="#f5cf4b" stroke="#c79a17" stroke-width="2"/>
      <g fill="#d9ad29" opacity=".8">
        <ellipse cx="20" cy="25" rx="3" ry="4"/>
        <ellipse cx="43" cy="23" rx="4" ry="3"/>
        <ellipse cx="45" cy="49" rx="3" ry="4"/>
        <ellipse cx="19" cy="49" rx="4" ry="3"/>
        <ellipse cx="33" cy="35" rx="2.5" ry="3"/>
      </g>
      <path d="M14 49 Q32 55 50 49 L50 60 Q32 66 14 60 Z" fill="#f4f7fa"/>
      <path d="M32 51 L28 55 L32 59 L36 55 Z" fill="#ff6b5e" stroke="#c7483f" stroke-width="1"/>
      <circle cx="24" cy="31" r="8" fill="#f4f7fa" stroke="#c79a17" stroke-width="1.5"/>
      <circle cx="40" cy="31" r="8" fill="#f4f7fa" stroke="#c79a17" stroke-width="1.5"/>
      <circle cx="26" cy="32" r="3" fill="#10202d"/>
      <circle cx="38" cy="32" r="3" fill="#10202d"/>
      <circle cx="27" cy="31" r="1" fill="#fff"/>
      <circle cx="39" cy="31" r="1" fill="#fff"/>
      <path d="M20 42 Q32 51 44 42" stroke="#8b6b12" stroke-width="2" fill="none" stroke-linecap="round"/>
      <path d="M28 45 L28 49 M36 45 L36 49" stroke="#8b6b12" stroke-width="1.5" stroke-linecap="round"/>
    </svg>`,
  patrick: `
    <svg viewBox="0 0 64 80" aria-hidden="true" focusable="false">
      <ellipse cx="32" cy="75" rx="18" ry="4" fill="#000" opacity=".28"/>
      <path d="M32 8 L41 31 L62 33 L46 47 L51 68 L32 56 L13 68 L18 47 L2 33 L23 31 Z"
            fill="#ef8bab" stroke="#c64f73" stroke-width="2" stroke-linejoin="round"/>
      <path d="M32 14 L38 31 L53 33 L42 43 L45 57 L32 49 L19 57 L22 43 L11 33 L26 31 Z"
            fill="#ffa6b9" opacity=".38"/>
      <path d="M22 52 Q32 48 42 52 L44 62 Q32 66 20 62 Z" fill="#55b58e" stroke="#2f7f61" stroke-width="1.5"/>
      <circle cx="26" cy="56" r="2" fill="#8e6cc9"/>
      <circle cx="36" cy="60" r="2" fill="#8e6cc9"/>
      <circle cx="24" cy="33" r="6" fill="#f4f7fa" stroke="#c64f73" stroke-width="1.2"/>
      <circle cx="40" cy="33" r="6" fill="#f4f7fa" stroke="#c64f73" stroke-width="1.2"/>
      <circle cx="26" cy="34" r="2.5" fill="#10202d"/>
      <circle cx="38" cy="34" r="2.5" fill="#10202d"/>
      <path d="M18 27 Q24 23 30 27" stroke="#a9425f" stroke-width="1.5" fill="none" stroke-linecap="round"/>
      <path d="M34 27 Q40 23 46 27" stroke="#a9425f" stroke-width="1.5" fill="none" stroke-linecap="round"/>
      <path d="M25 44 Q32 51 39 44" stroke="#9a3e58" stroke-width="2" fill="none" stroke-linecap="round"/>
    </svg>`,
  squidward: `
    <svg viewBox="0 0 64 80" aria-hidden="true" focusable="false">
      <ellipse cx="32" cy="75" rx="19" ry="4" fill="#000" opacity=".28"/>
      <g stroke="#5ab8b2" stroke-width="6" fill="none" stroke-linecap="round">
        <path d="M21 56 Q16 68 18 76"/><path d="M29 59 Q27 70 30 76"/>
        <path d="M35 59 Q37 70 34 76"/><path d="M43 56 Q48 68 46 76"/>
      </g>
      <path d="M18 21 Q32 7 46 21 L48 42 Q48 58 32 61 Q16 58 16 42 Z"
            fill="#6cc7c1" stroke="#3a9a94" stroke-width="2"/>
      <path d="M21 54 L45 54 L42 64 L22 64 Z" fill="#b98a5a" stroke="#8d633d" stroke-width="1.5"/>
      <path d="M26 54 L32 59 L38 54" fill="#f4f7fa" opacity=".9"/>
      <path d="M32 30 Q37 38 32 47 Q28 38 32 30" fill="#4aa8a2" stroke="#3a9a94" stroke-width="1.5"/>
      <ellipse cx="24" cy="31" rx="6" ry="7" fill="#f4f7fa" stroke="#3a9a94" stroke-width="1.2"/>
      <ellipse cx="40" cy="31" rx="6" ry="7" fill="#f4f7fa" stroke="#3a9a94" stroke-width="1.2"/>
      <circle cx="25" cy="32" r="2.5" fill="#10202d"/>
      <circle cx="39" cy="32" r="2.5" fill="#10202d"/>
      <path d="M18 27 Q24 24 30 27" stroke="#3a9a94" stroke-width="1.5" fill="none" stroke-linecap="round"/>
      <path d="M34 27 Q40 24 46 27" stroke="#3a9a94" stroke-width="1.5" fill="none" stroke-linecap="round"/>
      <path d="M24 49 Q32 45 40 49" stroke="#2d6d68" stroke-width="2" fill="none" stroke-linecap="round"/>
    </svg>`,
  sandy: `
    <svg viewBox="0 0 64 80" aria-hidden="true" focusable="false">
      <ellipse cx="32" cy="75" rx="18" ry="4" fill="#000" opacity=".28"/>
      <rect x="18" y="53" width="28" height="19" rx="8" fill="#eef4f8" stroke="#aebfc9" stroke-width="1.5"/>
      <path d="M19 60 L45 60" stroke="#cbd9e2" stroke-width="1.5"/>
      <circle cx="15" cy="28" r="9" fill="#c88a4a" stroke="#9a6430" stroke-width="1.5"/>
      <circle cx="49" cy="28" r="9" fill="#c88a4a" stroke="#9a6430" stroke-width="1.5"/>
      <circle cx="32" cy="36" r="18" fill="#d09a5c" stroke="#9a6430" stroke-width="2"/>
      <ellipse cx="32" cy="44" rx="10" ry="8" fill="#f0d3b0"/>
      <ellipse cx="32" cy="40" rx="3" ry="2" fill="#5a3a21"/>
      <path d="M28 47 Q32 50 36 47" stroke="#7a4a28" stroke-width="1.5" fill="none" stroke-linecap="round"/>
      <circle cx="26" cy="35" r="4" fill="#f4f7fa"/>
      <circle cx="38" cy="35" r="4" fill="#f4f7fa"/>
      <circle cx="27" cy="35.5" r="1.8" fill="#10202d"/>
      <circle cx="37" cy="35.5" r="1.8" fill="#10202d"/>
      <circle cx="32" cy="35" r="25" fill="rgba(180,230,255,.14)" stroke="#c8efff" stroke-width="2"/>
      <path d="M14 24 Q22 13 37 13" stroke="rgba(255,255,255,.8)" stroke-width="2" fill="none" stroke-linecap="round"/>
    </svg>`,
  plankton: `
    <svg viewBox="0 0 64 80" aria-hidden="true" focusable="false">
      <ellipse cx="32" cy="75" rx="14" ry="4" fill="#000" opacity=".28"/>
      <path d="M27 26 Q23 12 19 8" stroke="#4e9a48" stroke-width="3" fill="none" stroke-linecap="round"/>
      <path d="M37 26 Q41 12 45 8" stroke="#4e9a48" stroke-width="3" fill="none" stroke-linecap="round"/>
      <circle cx="19" cy="7" r="3" fill="#7bc96f" stroke="#4e9a48"/>
      <circle cx="45" cy="7" r="3" fill="#7bc96f" stroke="#4e9a48"/>
      <path d="M18 44 Q12 46 11 52" stroke="#7bc96f" stroke-width="4" fill="none" stroke-linecap="round"/>
      <path d="M46 44 Q52 46 53 52" stroke="#7bc96f" stroke-width="4" fill="none" stroke-linecap="round"/>
      <path d="M27 63 L25 74 M37 63 L39 74" stroke="#4e9a48" stroke-width="4" stroke-linecap="round"/>
      <ellipse cx="32" cy="46" rx="14" ry="19" fill="#7bc96f" stroke="#4e9a48" stroke-width="2"/>
      <circle cx="32" cy="35" r="11" fill="#f4f7fa" stroke="#4e9a48" stroke-width="1.5"/>
      <circle cx="32" cy="37" r="5" fill="#10202d"/>
      <circle cx="34" cy="35" r="1.5" fill="#fff"/>
      <path d="M27 51 Q32 55 37 51" stroke="#2d6d2a" stroke-width="1.5" fill="none" stroke-linecap="round"/>
    </svg>`,
};

const VISITOR_PALETTE = [
  { body: "#63b3ed", fin: "#3b7fa8" },
  { body: "#f2c14e", fin: "#b3861e" },
  { body: "#ff8a7f", fin: "#b94d45" },
  { body: "#7bc96f", fin: "#4e9a48" },
  { body: "#b794f6", fin: "#7350b5" },
  { body: "#f6a6c1", fin: "#b85d7c" },
  { body: "#5cc8c2", fin: "#2f8f8a" },
];

function visitorPalette(name) {
  let hash = 0;
  for (const char of String(name)) hash = (hash * 31 + char.codePointAt(0)) >>> 0;
  return VISITOR_PALETTE[hash % VISITOR_PALETTE.length];
}

function visitorSvg(name) {
  const { body, fin } = visitorPalette(name);
  return `
    <svg viewBox="0 0 64 80" aria-hidden="true" focusable="false">
      <ellipse cx="34" cy="75" rx="18" ry="4" fill="#000" opacity=".25"/>
      <path d="M15 45 L4 34 L6 55 Z" fill="${fin}" opacity=".9"/>
      <ellipse cx="35" cy="45" rx="20" ry="15" fill="${body}" stroke="${fin}" stroke-width="2"/>
      <path d="M27 32 Q32 25 38 32" fill="${fin}" opacity=".8"/>
      <path d="M28 58 Q35 64 40 58" fill="${fin}" opacity=".55"/>
      <path d="M25 44 Q30 47 35 44" stroke="${fin}" stroke-width="1.2" fill="none" opacity=".7"/>
      <circle cx="43" cy="40" r="6" fill="#f4f7fa" stroke="${fin}" stroke-width="1.2"/>
      <circle cx="45" cy="40" r="3" fill="#10202d"/>
      <circle cx="46" cy="39" r="1" fill="#fff"/>
      <path d="M47 48 Q52 50 48 53" stroke="${fin}" stroke-width="1.5" fill="none" stroke-linecap="round"/>
    </svg>`;
}

const SCENE_POINTS = {
  counter: [63, 67],
  pass: [66, 50],
  dispatch: [88, 44],
  office: [90, 61],
  workshop: [91, 75],
  kitchen: [70, 35],
  entrance: [52, 88],
  window: [96, 9],
};

const STATION_POINTS = {
  "grill-1": [68, 20],
  "fryer-1": [78, 20],
  "soda-1": [88, 20],
  "assembly-1": [78, 36],
};

const OPEN_ORDER_STATUSES = new Set(["new", "assigned", "queued", "in_progress", "completed"]);

const scene = {
  ready: false,
  layer: null,
  actors: new Map(),
  visitors: new Map(),
  departed: new Set(),
  scenario: null,
  tick: -1,
};

function initScene() {
  if (scene.ready) return;
  const tables = $("tables");
  const layer = $("scene-actors");
  if (!tables || !layer) return;

  for (const table of SCENE_TABLES) {
    const node = document.createElement("div");
    node.className = "table";
    node.style.left = `${table.x}%`;
    node.style.top = `${table.y}%`;
    const number = document.createElement("span");
    number.className = "table-number";
    text(number, table.number);
    node.append(number);
    tables.append(node);
  }

  for (const [id, config] of Object.entries(MAIN_AGENTS)) {
    const node = makeActor(id, config.label, config.kind);
    layer.append(node);
    scene.actors.set(id, node);
  }

  scene.layer = layer;
  scene.ready = true;
}

function makeActor(id, label, kind) {
  const node = document.createElement("div");
  node.className = `actor ${kind}`;
  node.dataset.actor = id;
  node.setAttribute("aria-label", label);

  const model = document.createElement("span");
  model.className = "actor-model";
  model.innerHTML = kind === "visitor" ? visitorSvg(label) : MODEL_SVGS[kind] || visitorSvg(label);

  const name = document.createElement("span");
  name.className = "actor-label";
  text(name, label);

  const state = document.createElement("span");
  state.className = "actor-state";

  node.append(model, name, state);
  return node;
}

function makeVisitor(order) {
  const node = makeActor(order.id, order.customer, "visitor");
  node.dataset.order = order.id;
  return node;
}

function placeActor(node, [x, y]) {
  const nextLeft = `${x}%`;
  const nextTop = `${y}%`;
  const oldLeft = Number.parseFloat(node.style.left);
  const moved = Boolean(node.style.left) && (node.style.left !== nextLeft || node.style.top !== nextTop);

  if (moved && Number.isFinite(oldLeft) && x !== oldLeft) {
    node.classList.toggle("faces-left", x < oldLeft);
  }

  node.style.left = nextLeft;
  node.style.top = nextTop;

  if (moved) {
    node.classList.add("is-moving");
    window.clearTimeout(node._moveTimer);
    node._moveTimer = window.setTimeout(() => node.classList.remove("is-moving"), 650);
  }
}

function indexStations(stations) {
  const byId = new Map();
  const byAgent = new Map();
  let broken = null;
  for (const station of stations) {
    byId.set(station.id, station);
    if (station.occupant) byAgent.set(station.occupant, station);
    if (station.broken && !broken) broken = station;
  }
  return { byId, byAgent, broken };
}

function stationPoint(agentId, tracks) {
  const station = tracks.byAgent.get(agentId);
  if (station && STATION_POINTS[station.id]) {
    const [x, y] = STATION_POINTS[station.id];
    return [x + 4.3, y + 1.4];
  }
  const offset = agentId === "spongebob" ? -2 : 2;
  return [SCENE_POINTS.kitchen[0] + offset, SCENE_POINTS.kitchen[1]];
}

function agentPoint(agent, tracks) {
  if (agent.id === "squidward") {
    if (agent.state === "TAKING_ORDER") return [61, 65];
    if (agent.state === "WAITING_SERVE") return SCENE_POINTS.pass;
    if (agent.state === "SERVING") return [63, 56];
    return SCENE_POINTS.counter;
  }

  if (agent.id === "krabs") {
    if (agent.state === "MAINTENANCE") {
      if (tracks.broken) {
        const [x, y] = STATION_POINTS[tracks.broken.id] || SCENE_POINTS.workshop;
        return [x - 4.5, y + 1.5];
      }
      return SCENE_POINTS.workshop;
    }
    if (agent.state === "COORDINATING_STATIONS") return [64, 45];
    if (["ASSIGNING", "AWAITING_ACCEPT", "ARBITRATING"].includes(agent.state)) {
      return SCENE_POINTS.dispatch;
    }
    return SCENE_POINTS.office;
  }

  if (agent.id === "sandy") {
    if (agent.state === "REPAIRING" && tracks.broken) {
      const [x, y] = STATION_POINTS[tracks.broken.id] || SCENE_POINTS.workshop;
      return [x, y + 5];
    }
    return SCENE_POINTS.workshop;
  }

  if (agent.id === "plankton") {
    if (agent.state === "REQUESTING") return SCENE_POINTS.entrance;
    if (agent.state === "WAITING") return [93, 30];
    return SCENE_POINTS.window;
  }

  if (agent.state === "REPORTING") {
    const offset = agent.id === "spongebob" ? -2.2 : 2.2;
    return [SCENE_POINTS.pass[0] + offset, SCENE_POINTS.pass[1] + 2];
  }
  if (agent.state === "WAITING_STATION") {
    const offset = agent.id === "spongebob" ? -2 : 2;
    return [64 + offset, 43];
  }
  return stationPoint(agent.id, tracks);
}

function visitorPoint(order) {
  const index = Math.max(1, Number(order.table) || 1) - 1;
  const table = SCENE_TABLES[index % SCENE_TABLES.length];
  return [table.x, table.y - 5.6];
}

function updateSceneStations(tracks) {
  for (const node of document.querySelectorAll(".station-unit")) {
    const station = tracks.byId.get(node.dataset.station);
    const busy = Boolean(station && station.occupant);
    const broken = Boolean(station && station.broken);
    node.classList.toggle("is-busy", busy);
    node.classList.toggle("is-broken", broken);
    const status = node.querySelector(".station-status");
    if (status) text(status, broken ? "неисправна" : busy ? "занята" : "свободна");
  }
}

function clearVisitors() {
  for (const node of scene.visitors.values()) node.remove();
  scene.visitors.clear();
  scene.departed.clear();
}

function leaveVisitor(orderId, node) {
  scene.departed.add(orderId);
  if (!node) return;
  placeActor(node, SCENE_POINTS.entrance);
  node.classList.add("leaving");
  window.setTimeout(() => {
    node.remove();
    if (scene.visitors.get(orderId) === node) scene.visitors.delete(orderId);
  }, 700);
}

function renderVisitors(orders) {
  if (!scene.layer) return;

  for (const order of orders) {
    if (OPEN_ORDER_STATUSES.has(order.status)) {
      if (scene.departed.has(order.id)) continue;
      const point = visitorPoint(order);
      let node = scene.visitors.get(order.id);
      if (!node) {
        node = makeVisitor(order);
        scene.visitors.set(order.id, node);
        node.dataset.status = order.status;
        placeActor(node, SCENE_POINTS.entrance);
        scene.layer.append(node);
        window.requestAnimationFrame(() => {
          window.requestAnimationFrame(() => {
            if (scene.visitors.get(order.id) === node) placeActor(node, point);
          });
        });
      } else {
        placeActor(node, point);
      }
      node.dataset.status = order.status;
      node.classList.toggle("priority", Boolean(order.priority));
      const state = node.querySelector(".actor-state");
      text(state, (order.priority ? "! " : "") + (order.status_label || order.status));
    } else if (!scene.departed.has(order.id)) {
      leaveVisitor(order.id, scene.visitors.get(order.id));
    }
  }

  const active = new Set(
    orders
      .filter((order) => OPEN_ORDER_STATUSES.has(order.status))
      .map((order) => order.id)
  );
  for (const [orderId, node] of scene.visitors) {
    if (!active.has(orderId) && !scene.departed.has(orderId)) {
      leaveVisitor(orderId, node);
    }
  }
}

function renderScene(data) {
  if (!scene.ready) initScene();
  if (!scene.ready) return;

  const scenario = data.scenario || {};
  if (data.tick < scene.tick || scenario.name !== scene.scenario) clearVisitors();
  scene.scenario = scenario.name;
  scene.tick = data.tick;

  const tracks = indexStations(data.stations || []);
  updateSceneStations(tracks);

  for (const agent of data.agents || []) {
    const node = scene.actors.get(agent.id);
    if (!node) continue;
    placeActor(node, agentPoint(agent, tracks));
    node.dataset.state = agent.state;
    const state = node.querySelector(".actor-state");
    text(state, STATUS_LABELS[agent.state] || agent.state);
    node.title = `${MAIN_AGENTS[agent.id].label}: ${agent.role}${agent.detail ? ` · ${agent.detail}` : ""}`;
  }

  renderVisitors(data.orders || []);
}

function messageDetail(content) {
  const keys = ["event", "action", "order_id", "station_id", "task_index", "reason"];
  const parts = [];
  for (const key of keys) {
    if (content && content[key] !== undefined) parts.push(`${key}=${content[key]}`);
  }
  return parts.join(" ") || JSON.stringify(content || {});
}

function renderMessages(messages) {
  const box = $("messages");
  box.replaceChildren();
  for (const message of [...messages].reverse()) {
    const line = document.createElement("div");
    line.className = "msg";
    const tick = document.createElement("span");
    tick.className = "tick";
    text(tick, `t${message.tick}`);
    const perf = document.createElement("span");
    perf.className = "perf";
    text(perf, message.performative_label || message.performative);
    const route = document.createElement("span");
    route.className = "route";
    const arrow = document.createElement("span");
    arrow.className = "arrow";
    text(arrow, "→");
    route.append(document.createTextNode(message.sender), arrow, document.createTextNode(message.receiver));
    const detail = document.createElement("div");
    detail.className = "detail";
    text(detail, messageDetail(message.content));
    route.appendChild(detail);
    line.append(tick, perf, route);
    box.appendChild(line);
  }
}

function render(data) {
  current = data;
  renderScenarioSelect(data.scenarios);
  renderMechanismSelect(data.mechanisms);
  const scenario = data.scenario || {};
  text($("scenario-title"), scenario.title || "");
  text($("scenario-desc"), scenario.description || "");
  const select = $("scenario");
  if (scenario.name && select.value !== scenario.name) select.value = scenario.name;
  const mechanism = data.mechanism || {};
  const mechanismSelect = $("mechanism");
  if (mechanism.name && mechanismSelect.value !== mechanism.name) {
    mechanismSelect.value = mechanism.name;
  }
  text($("mechanism-badge"), mechanism.label || "");

  const pill = $("run-status");
  pill.className = "pill";
  if (data.finished) {
    pill.classList.add("done");
    text(pill, "завершено");
  } else if (data.auto) {
    pill.classList.add("running");
    text(pill, "выполняется");
  } else {
    text(pill, "пауза");
  }

  const autoButton = $("btn-auto");
  autoButton.textContent = data.auto ? "Пауза" : "Запустить";
  autoButton.disabled = data.finished;
  $("btn-step").disabled = data.finished;

  renderStats(data);
  renderScene(data);
  renderOrders(data.orders || []);
  renderStations(data.stations || []);
  renderAgents(data.agents || []);
  renderInventory(data.inventory || []);
  renderMessages(data.messages || []);
}

async function load() {
  try {
    render(await api("/api/state"));
  } catch (error) {
    const pill = $("run-status");
    pill.className = "pill";
    text(pill, "нет связи");
  }
}

async function post(path, payload) {
  try {
    render(await api(path, { method: "POST", body: JSON.stringify(payload || {}) }));
  } catch (error) {
    load();
  }
}

$("btn-auto").addEventListener("click", () => {
  post("/api/auto", { enabled: !(current && current.auto) });
});

$("btn-step").addEventListener("click", () => post("/api/step"));

$("btn-reset").addEventListener("click", () => {
  post("/api/reset", {
    scenario: $("scenario").value,
    mechanism: $("mechanism").value,
  });
});

$("scenario").addEventListener("change", () => {
  post("/api/reset", {
    scenario: $("scenario").value,
    mechanism: $("mechanism").value,
  });
});

$("mechanism").addEventListener("change", () => {
  post("/api/reset", {
    scenario: $("scenario").value,
    mechanism: $("mechanism").value,
  });
});

$("speed").addEventListener("input", () => {
  const ms = Number($("speed").value);
  text($("speed-label"), `${(ms / 1000).toFixed(1)} с`);
  post("/api/auto", {
    enabled: current ? current.auto : false,
    interval: ms / 1000,
  });
});

initScene();
load();
setInterval(load, 500);
