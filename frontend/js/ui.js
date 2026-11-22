// HTML builders for the kiosk screen, medicine list, check details, machine status, and history.
// Buttons carry a data-action attribute; main.js handles them.

export const esc = (value) => String(value ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (x) => `${Math.round(x * 100)}%`;
const grams = (x) => `${Number(x).toLocaleString("en-US", { maximumFractionDigits: 2 })} g`;

export const REASON_LABELS = {
  OK: "Accepted",
  QUOTA: "Daily limit reached",
  PROHIBITED: "Prohibited item",
  UNIDENTIFIED: "Not recognized",
  BARCODE_INVALID: "Unregistered barcode",
  MISMATCH: "Barcode mismatch",
  LOW_CONFIDENCE: "Package unclear",
  WEIGHT_EMPTY: "Empty package",
  WEIGHT_OVER: "Too heavy",
};

// Decision engine rule order; every rule before the failing one has passed.
const RULES = [
  { codes: ["QUOTA"], label: "Daily limit not reached" },
  { codes: ["PROHIBITED"], label: "Not a prohibited item" },
  { codes: ["UNIDENTIFIED"], label: "Item recognized" },
  { codes: ["BARCODE_INVALID", "MISMATCH"], label: "Barcode registered and matching" },
  { codes: ["LOW_CONFIDENCE"], label: "Photo confident enough" },
  { codes: ["WEIGHT_EMPTY", "WEIGHT_OVER"], label: "Plausible weight" },
];

const ACTUATOR_TEXT = {
  open: "open", closed: "closed", to_bin: "tilted to bin", to_return: "tilted to return",
};
const SYMBOLOGY_TEXT = { EAN_13: "EAN-13", TEXT: "from scanner" };

// ---------- kiosk screen ----------

export function kioskHtml(view, { member, demoMembers }) {
  switch (view.kind) {
    case "idle":
      return `
        <h2 class="k-heading">Drop off unused medicine here</h2>
        <p class="k-text">Enter your member number to start.</p>
        <form class="k-form" data-form="member">
          <label for="member-input">Member number</label>
          <div class="k-row">
            <input id="member-input" name="token" autocomplete="off" spellcheck="false"
              placeholder="MBR-0001" value="${esc(view.token)}">
            <button type="submit" class="btn btn-primary">Start</button>
          </div>
        </form>
        ${view.error ? `<p class="k-alert" role="alert">${esc(view.error)}</p>` : ""}
        <p class="k-small">Demo members (fictional)</p>
        <div class="k-demo">
          ${demoMembers.map((m) => `
            <button type="button" class="demo-member" data-action="demo-member" data-token="${esc(m.token)}">
              <strong>${esc(m.token)}</strong><span>${esc(m.demo_role)}</span>
            </button>`).join("")}
        </div>`;
    case "message":
      return `<h2 class="k-heading">${esc(view.heading)}</h2>${view.body ? `<p class="k-text">${esc(view.body)}</p>` : ""}`;
    case "hatch":
      return `
        <h2 class="k-heading">Place your medicine inside</h2>
        <p class="k-text">Hi, ${esc(member.token)}. The door is open.</p>
        <p class="k-hint">Pick a medicine on the right, then press <em>Insert into machine</em>.</p>
        ${memberStats(member)}
        <button type="button" class="btn" data-action="cancel">Cancel</button>`;
    case "verifying":
      return `
        <h2 class="k-heading"><span class="spinner" aria-hidden="true"></span>Checking…</h2>
        <p class="k-text">The door stays locked until the check is done.</p>
        <ul class="k-steps"><li>Photographing the package</li><li>Reading the barcode</li><li>Weighing</li></ul>`;
    case "accepted": {
      const r = view.result;
      return `
        <p class="k-verdict ok">Accepted</p>
        <h2 class="k-heading">${esc(r.signals.photo.display)}</h2>
        <dl class="k-facts">
          <div><dt>Weight</dt><dd>${grams(r.signals.weight.measured_g)}</dd></div>
          <div><dt>Photo match</dt><dd>${pct(r.signals.photo.confidence)}</dd></div>
        </dl>
        <p class="k-points">+${r.points_awarded} points added</p>`;
    }
    case "rejected": {
      const r = view.result;
      return `
        <p class="k-verdict bad">Rejected</p>
        <p class="k-text">${esc(r.reason_text)}</p>
        ${view.canRetrieve
          ? `<p class="k-hint">The return door is open.</p>
             <button type="button" class="btn btn-primary" data-action="retrieve">Take your item</button>`
          : `<p class="k-hint">Returning your item…</p>`}`;
    }
    case "done":
      return `
        <h2 class="k-heading">Thank you!</h2>
        ${member ? memberStats(member) : ""}
        <div class="k-row">
          <button type="button" class="btn btn-primary" data-action="again">Drop off another</button>
          <button type="button" class="btn" data-action="finish">Finish</button>
        </div>`;
    case "error":
      return `
        <p class="k-verdict bad">Something went wrong</p>
        <p class="k-text">${esc(view.message)}</p>
        <p class="k-hint">The front door has reopened. Please take your item.</p>
        <button type="button" class="btn btn-primary" data-action="retrieve">Take your item</button>`;
    case "fatal":
      return `<p class="k-verdict bad">The simulation failed to load</p><p class="k-text">${esc(view.message)}</p>`;
    default:
      return "";
  }
}

function memberStats(member) {
  return `
    <dl class="k-facts">
      <div><dt>Your points</dt><dd>${member.points_total}</dd></div>
      <div><dt>Drop-offs left today</dt><dd>${member.remaining_today} of ${member.daily_limit}</dd></div>
    </dl>`;
}

/** Text mirrored on the 3D machine's screen for each kiosk view. */
export function screenFor(view, member) {
  switch (view.kind) {
    case "idle": return { heading: "Drop off unused medicine", body: "Enter your member number." };
    case "message": return { heading: view.heading, body: view.body || "", tone: "busy" };
    case "hatch": return { heading: "Place your medicine inside", body: "The door is open." };
    case "verifying": return { heading: "Checking…", body: "Photo, barcode, and weight.", tone: "busy" };
    case "accepted": return { heading: "Accepted", body: `${view.result.signals.photo.display}, +${view.result.points_awarded} points`, tone: "ok" };
    case "rejected": return { heading: "Rejected", body: REASON_LABELS[view.result.reason_code], tone: "bad" };
    case "done": return { heading: "Thank you!", body: member ? `Your points: ${member.points_total}` : "" };
    case "error": return { heading: "Something went wrong", body: "Please take your item.", tone: "bad" };
    default: return { heading: "MedDrop", body: "" };
  }
}

// ---------- medicine list ----------

function expectText(decision, reason) {
  return decision === "ACCEPT" ? "Should be accepted" : `Should be rejected: ${(REASON_LABELS[reason] || reason).toLowerCase()}`;
}

export function cardListHtml(items, selectedId) {
  return items.map((card) => `
    <li>
      <button type="button" class="card-row ${card.item_id === selectedId ? "is-selected" : ""}"
        data-action="select-card" data-id="${esc(card.item_id)}" aria-pressed="${card.item_id === selectedId}">
        <img src="${esc(card.photo_url)}" alt="" loading="lazy">
        <span class="card-text">
          <span class="card-label">${esc(card.label)}</span>
          <span class="card-expect ${card.expected_decision === "ACCEPT" ? "ok" : "bad"}">${esc(expectText(card.expected_decision, card.expected_reason))}</span>
        </span>
      </button>
    </li>`).join("");
}

export function cardDetailHtml(card, weight, canPlace) {
  if (!card) return `<p class="muted">Pick a medicine above.</p>`;
  const changed = Number(weight) !== card.weight_g;
  return `
    <div class="detail-media">
      <img src="${esc(card.photo_url)}" alt="Photo of ${esc(card.label)}">
      ${card.barcode_image_url
        ? `<img class="detail-barcode" src="${esc(card.barcode_image_url)}" alt="Barcode ${esc(card.barcode)}">`
        : `<p class="detail-nobarcode">No barcode</p>`}
    </div>
    <p class="detail-scenario">${esc(card.scenario)}</p>
    <label class="weight-label" for="weight-number">Weight on the scale</label>
    <div class="weight-controls">
      <input type="range" id="weight-range" min="0" max="400" step="0.1" value="${esc(weight)}" aria-label="Drag to change the weight">
      <input type="number" id="weight-number" min="0" max="5000" step="0.01" value="${esc(weight)}">
      <span>g</span>
    </div>
    ${changed ? `<p class="weight-note">Weight changed, so the result may differ from the scenario.
      <button type="button" class="link" data-action="reset-weight">Reset to ${grams(card.weight_g)}</button></p>` : ""}
    <button type="button" class="btn btn-primary btn-wide" data-action="place" ${canPlace ? "" : "disabled"}>Insert into machine</button>
    ${canPlace ? "" : `<p class="muted small">Enter a member number on the kiosk first to open the door.</p>`}`;
}

// ---------- machine status (compact; details on click) ----------

export function statusHtml(label, outputs) {
  return `
    <summary><span class="led led-${outputs.led}" aria-hidden="true"></span>${esc(label)}</summary>
    <dl class="status-list">
      <div><dt>Front door</dt><dd>${ACTUATOR_TEXT[outputs.frontHatch]}, ${outputs.frontLocked ? "locked" : "unlocked"}</dd></div>
      <div><dt>Trap door</dt><dd>${ACTUATOR_TEXT[outputs.trapDoor]}</dd></div>
      <div><dt>Return door</dt><dd>${ACTUATOR_TEXT[outputs.returnHatch]}</dd></div>
    </dl>`;
}

// ---------- check details ----------

export function signalsHtml({ result, card, weight, expected, config, classNames }) {
  const s = result.signals;
  const accepted = result.decision === "ACCEPT";
  const matches = result.decision === expected.decision && (!expected.reason || result.reason_code === expected.reason);
  return `
    <div class="verdict ${accepted ? "ok" : "bad"}">
      <p class="verdict-title">${accepted ? "Accepted" : `Rejected: ${esc(REASON_LABELS[result.reason_code].toLowerCase())}`}
        <code>${esc(result.reason_code)}</code></p>
      <p class="verdict-text">${esc(result.reason_text)}</p>
      ${matches
        ? `<p class="expect ok">This matches the scenario.</p>`
        : `<p class="expect warn" role="status">This does not match the scenario. ${esc(expectText(expected.decision, expected.reason))}.</p>`}
      ${expected.note ? `<p class="expect note">${esc(expected.note)}</p>` : ""}
    </div>
    <ol class="rules">${rulesHtml(result.reason_code)}</ol>
    <div class="signal-grid">
      ${photoSignal(s.photo, s.barcode.present, card, config, classNames)}
      ${barcodeSignal(s.barcode, card)}
      ${weightSignal(s.weight, weight)}
    </div>`;
}

function rulesHtml(reasonCode) {
  const failed = RULES.findIndex((r) => r.codes.includes(reasonCode));
  return RULES.map((rule, i) => {
    const status = failed === -1 || i < failed ? "pass" : i === failed ? "fail" : "skip";
    const text = { pass: "passed", fail: "failed", skip: "not checked" }[status];
    return `<li class="rule ${status}"><span>${esc(rule.label)}</span><span class="rule-status">${text}</span></li>`;
  }).join("");
}

function photoSignal(photo, barcodePresent, card, config, classNames) {
  const c = config.classifier;
  const threshold = barcodePresent ? c.threshold_with_barcode : c.threshold_photo_only;
  const name = (id) => classNames[id] || id;
  return `
    <section class="signal">
      <h3>Photo</h3>
      <img class="signal-img" src="${esc(card.photo_url)}" alt="">
      <p class="signal-main">${esc(name(photo.class_id))}</p>
      <div class="meter" role="img" aria-label="Confidence ${pct(photo.confidence)}, pass mark ${pct(threshold)}">
        <div class="meter-fill ${photo.confidence >= threshold ? "ok" : "bad"}" style="width:${photo.confidence * 100}%"></div>
        <span class="meter-mark" style="left:${c.min_confidence_floor * 100}%" title="Below this the item counts as not recognized"></span>
        <span class="meter-mark strong" style="left:${threshold * 100}%" title="Pass mark"></span>
      </div>
      <p class="signal-sub">Confidence ${pct(photo.confidence)}. The pass mark is ${pct(threshold)} ${barcodePresent ? "with a barcode" : "without a barcode"}; below ${pct(c.min_confidence_floor)} the item counts as not recognized.</p>
      <ol class="top3">${photo.top3.map(([cls, p]) => `<li><span>${esc(name(cls))}</span><span>${pct(p)}</span></li>`).join("")}</ol>
    </section>`;
}

function barcodeSignal(barcode, card) {
  if (!barcode.present) {
    return `<section class="signal"><h3>Barcode</h3><p class="signal-main">No barcode</p>
      <p class="signal-sub">Checked from the photo alone, so the confidence bar is higher.</p></section>`;
  }
  const kind = barcode.symbology ? ` (${esc(SYMBOLOGY_TEXT[barcode.symbology] || barcode.symbology)})` : "";
  return `
    <section class="signal">
      <h3>Barcode</h3>
      ${card.barcode_image_url ? `<img class="signal-img barcode" src="${esc(card.barcode_image_url)}" alt="">` : ""}
      <p class="signal-main">${barcode.decoded ? esc(barcode.decoded) : "Unreadable"}</p>
      <p class="signal-sub ${barcode.valid ? "" : "bad-text"}">
        ${barcode.valid ? `Registered as product ${esc(barcode.product_id)}${kind}.` : `Not registered in this machine${kind}.`}
      </p>
    </section>`;
}

function weightSignal(w, measured) {
  if (w.status === null) {
    return `<section class="signal"><h3>Weight</h3><p class="signal-main">${grams(measured)}</p>
      <p class="signal-sub">Not checked because the item was not recognized.</p></section>`;
  }
  const max = Math.max(w.over_limit_g * 1.3, measured * 1.1, 1);
  const at = (g) => `${Math.min(100, (g / max) * 100)}%`;
  const verdict = { OK: "plausible weight", EMPTY: "empty or incomplete package", OVER: "too heavy" }[w.status];
  return `
    <section class="signal">
      <h3>Weight</h3>
      <p class="signal-main ${w.status === "OK" ? "" : "bad-text"}">${grams(measured)}, ${verdict}</p>
      <div class="scale" role="img" aria-label="Weight ${grams(measured)}. Counted as empty up to ${grams(w.empty_limit_g)}, too heavy above ${grams(w.over_limit_g)}.">
        <span class="zone empty" style="width:${at(w.empty_limit_g)}"></span>
        <span class="zone ok" style="left:${at(w.empty_limit_g)};width:calc(${at(w.over_limit_g)} - ${at(w.empty_limit_g)})"></span>
        <span class="zone over" style="left:${at(w.over_limit_g)};right:0"></span>
        <span class="scale-marker" style="left:${at(measured)}"></span>
      </div>
      <p class="signal-sub">Counted as empty at ${grams(w.empty_limit_g)} or less (empty package ${grams(w.tare_g)}). Counted as too heavy above ${grams(w.over_limit_g)} (full package ${grams(w.gross_g)}).</p>
    </section>`;
}

// ---------- history ----------

export function logRowHtml(entry) {
  if (entry.kind === "bug") {
    return `<tr class="row-bug"><td>${esc(entry.time)}</td><td colspan="6"><strong>Interlock violation:</strong> ${esc(entry.message)}</td></tr>`;
  }
  const cls = entry.decision === "ACCEPT" ? "row-ok" : "row-bad";
  const decision = entry.error ? "Error" : entry.decision === "ACCEPT" ? "Accepted" : "Rejected";
  const reason = entry.error ? esc(entry.error) : `${esc(REASON_LABELS[entry.reason])} <code>${esc(entry.reason)}</code>`;
  const match = entry.error ? "n/a" : entry.matches ? "Yes" : `<strong class="bad-text">No</strong>`;
  return `
    <tr class="${cls}">
      <td>${esc(entry.time)}</td><td>${esc(entry.member)}</td><td>${esc(entry.card)}</td><td>${grams(entry.weight)}</td>
      <td>${decision}</td><td>${reason}<span class="trail">${esc(entry.trail.join(" → "))}</span></td><td>${match}</td>
    </tr>`;
}
