// Pengendali simulasi: menghubungkan state machine, model 3D, API, dan tampilan.

import { api } from "./api.js";
import { Machine3D, PARTS } from "./machine3d.js";
import { MachineStateMachine, STATE_LABELS } from "./statemachine.js";
import * as ui from "./ui.js";

const $ = (selector) => document.querySelector(selector);
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const now = () => new Date().toLocaleTimeString("en-GB");

const app = {
  config: null,
  items: [],
  member: null,   // status anggota terakhir dari server
  card: null,     // kartu yang dipilih
  weight: null,   // berat yang "ditimbang"
  attempt: null,  // setoran yang sedang berjalan
  lastRun: null,  // untuk tombol Repeat last drop-off
  upload: { url: null, barcode: "" },  // foto unggahan sendiri
  kioskView: { kind: "idle" },
};
let sm;
let machine;

async function init() {
  try {
    [app.config, app.items] = await Promise.all([api.config(), api.items()]);
  } catch (error) {
    $("#kiosk").innerHTML = ui.kioskHtml({ kind: "fatal", message: error.message }, {});
    return;
  }
  app.classNames = Object.fromEntries(app.config.classes.map((c) => [c.class_id, c.display]));
  machine = new Machine3D($("#viewport"));
  sm = new MachineStateMachine(onStateChange);
  onStateChange({ to: "IDLE", outputs: sm.outputs, violations: [] });
  bindEvents();
  setKiosk({ kind: "idle" });
  api.bin(app.config.machine_bin_id).then((bin) => machine.setBinFill(bin.fill_pct)).catch(() => {});
  document.fonts?.ready.then(() => setKiosk(app.kioskView));  // gambar ulang layar 3D setelah font siap
}

function onStateChange({ to, outputs, violations }) {
  document.body.dataset.state = to;
  $("#machine-status").innerHTML = ui.statusHtml(STATE_LABELS[to], outputs);
  if (app.attempt) app.attempt.trail.push(to);
  for (const message of violations) addLogRow({ kind: "bug", time: now(), message: `${to}: ${message}` });
  renderCards();
}

// Pindah state, lalu gerakkan pintu dan trap door sesuai keluaran state itu.
async function go(to) {
  sm.transition(to);
  await machine.applyOutputs(sm.outputs);
}

function setKiosk(view) {
  app.kioskView = view;
  $("#kiosk").innerHTML = ui.kioskHtml(view, { member: app.member, demoMembers: app.config.demo_members });
  machine.setScreen(ui.screenFor(view, app.member));
}

// ---------- alur kios ----------

async function startSession(rawToken) {
  const token = String(rawToken || "").trim().toUpperCase();
  if (!["IDLE", "DONE"].includes(sm.state)) return;
  if (!token) return setKiosk({ kind: "idle", error: "Enter your member number first." });
  await go("AUTH");
  setKiosk({ kind: "message", heading: "Checking member number…" });
  try {
    const [member, bin] = await Promise.all([api.member(token), api.bin(app.config.machine_bin_id)]);
    machine.setBinFill(bin.fill_pct);
    if (!bin.accepting) throw new Error("This machine is full. Please use another drop-off point.");
    app.member = member;
  } catch (error) {
    await go("IDLE");
    app.member = null;
    return setKiosk({ kind: "idle", token, error: error.message });
  }
  await go("HATCH_OPEN");
  setKiosk({ kind: "hatch" });
}

async function placeItem() {
  const card = app.card?.item_id === "upload" ? uploadCard() : app.card;
  if (sm.state !== "HATCH_OPEN" || !card?.photo_url) return;
  const weight = Number(app.weight);
  app.attempt = { card, weight, member: app.member, trail: ["HATCH_OPEN"], time: now() };
  app.lastRun = { token: app.member.token, card, weight };

  setKiosk({ kind: "message", heading: "Medicine inside", body: "Closing and locking the door." });
  await go("ITEM_PLACED");
  await machine.insertItem(card.photo_url);
  await go("HATCH_CLOSED_LOCKED");
  await go("VERIFYING");
  setKiosk({ kind: "verifying" });

  let result;
  try {
    [result] = await Promise.all([
      api.verify({ memberToken: app.member.token, binId: app.config.machine_bin_id, weightG: weight, card }),
      wait(900),  // biar animasi "memeriksa" sempat terlihat
    ]);
  } catch (error) {
    app.attempt.error = error.message;
    await go("ERROR");
    return setKiosk({ kind: "error", message: error.message });
  }
  app.attempt.result = result;
  app.member = result.member;
  machine.setBinFill(result.bin.fill_pct);
  showSignals(app.attempt);

  if (result.decision === "ACCEPT") {
    await go("ACCEPTED");
    setKiosk({ kind: "accepted", result });
    await wait(1100);
    await go("TRAP_OPEN");  // barang ikut jatuh ke bin
    await go("ITEM_DROPPED");
    await go("CONFIRMED");
    await wait(400);
    await go("DONE");
    finishAttempt();
    setKiosk({ kind: "done" });
  } else {
    setKiosk({ kind: "rejected", result, canRetrieve: false });
    await go("REJECTED");  // barang dialihkan ke baki pengembalian
    await go("RETURN_OPEN");
    setKiosk({ kind: "rejected", result, canRetrieve: true });
  }
}

async function retrieveItem() {
  if (!["RETURN_OPEN", "ERROR"].includes(sm.state)) return;
  await machine.takeItem();
  if (sm.state === "RETURN_OPEN") await go("ITEM_RETRIEVED");
  await go("DONE");
  finishAttempt();
  setKiosk({ kind: "done" });
}

async function backToIdle() {
  if (!["HATCH_OPEN", "DONE"].includes(sm.state)) return;
  await go("IDLE");
  app.member = null;
  setKiosk({ kind: "idle" });
}

async function repeatLast() {
  const run = app.lastRun;
  if (!run || !["IDLE", "DONE"].includes(sm.state)) return;
  selectCard(run.card.item_id, run.weight);
  await startSession(run.token);
  await placeItem();
}

// ---------- kartu, rincian, riwayat ----------

function selectCard(itemId, weight) {
  if (itemId === "upload") {
    app.weight = weight ?? app.weight ?? 20;
    app.card = uploadCard();
  } else {
    app.card = app.items.find((card) => card.item_id === itemId) || null;
    app.weight = weight ?? app.card?.weight_g ?? null;
  }
  renderCards();
}

// Foto unggahan diperlakukan seperti kartu, tapi tanpa hasil yang "seharusnya".
function uploadCard() {
  const barcode = app.upload.barcode || null;
  return {
    item_id: "upload", label: "Your own photo", photo_url: app.upload.url, barcode,
    barcode_image_url: barcode ? `/media/barcodes/${barcode}.png` : null,
    weight_g: app.weight, expected_decision: null, expected_reason: null,
  };
}

function renderCards() {
  if (!sm) return;
  const canPlace = sm.state === "HATCH_OPEN" && Boolean(app.card);
  $("#card-list").innerHTML = ui.cardListHtml(app.items, app.card?.item_id);
  $("#card-detail").innerHTML = app.card?.item_id === "upload"
    ? ui.uploadDetailHtml(app.upload, app.config.products, app.weight, canPlace)
    : ui.cardDetailHtml(app.card, app.weight, canPlace);
  $("#btn-repeat").disabled = !app.lastRun || !["IDLE", "DONE"].includes(sm.state);
}

// Harapan hasil: dari kartu, kecuali anggota sudah kehabisan kuota sebelum menyetor.
function expectationFor(attempt) {
  if (attempt.member.remaining_today === 0) {
    return { decision: "REJECT", reason: "QUOTA",
      note: "This member has already used up today's drop-offs, so any item should be rejected." };
  }
  if (!attempt.card.expected_decision) return null;  // foto unggahan sendiri
  const note = attempt.weight !== attempt.card.weight_g
    ? "The weight was changed by hand, so the result may differ from the scenario." : "";
  return { decision: attempt.card.expected_decision, reason: attempt.card.expected_reason, note };
}

function showSignals(attempt) {
  $("#signals").innerHTML = ui.signalsHtml({
    result: attempt.result, card: attempt.card, weight: attempt.weight,
    expected: expectationFor(attempt), config: app.config, classNames: app.classNames,
  });
}

function finishAttempt() {
  const a = app.attempt;
  if (!a) return;
  const expected = expectationFor(a);
  addLogRow({
    time: a.time,
    member: a.member.token,
    card: a.card.label,
    weight: a.weight,
    decision: a.result?.decision,
    reason: a.result?.reason_code,
    error: a.error,
    matches: expected && a.result
      ? a.result.decision === expected.decision && (!expected.reason || a.result.reason_code === expected.reason)
      : null,
    trail: a.trail,
  });
  app.attempt = null;
}

function addLogRow(entry) {
  $("#log-empty")?.remove();
  $("#log-body").insertAdjacentHTML("afterbegin", ui.logRowHtml(entry));
}

// ---------- event ----------

function bindEvents() {
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button || button.disabled) return;
    const actions = {
      "demo-member": () => startSession(button.dataset.token),
      "select-card": () => selectCard(button.dataset.id),
      "reset-weight": () => { app.weight = app.card.weight_g; renderCards(); },
      place: placeItem,
      retrieve: retrieveItem,
      cancel: backToIdle,
      finish: backToIdle,
      again: () => startSession(app.member?.token),
    };
    actions[button.dataset.action]?.();
  });

  document.addEventListener("submit", (event) => {
    if (event.target.dataset.form !== "member") return;
    event.preventDefault();
    startSession(new FormData(event.target).get("token"));
  });

  // Slider dan kotak angka berat saling mengikuti.
  document.addEventListener("input", (event) => {
    if (!["weight-range", "weight-number"].includes(event.target.id)) return;
    app.weight = Number(event.target.value);
    $(event.target.id === "weight-range" ? "#weight-number" : "#weight-range").value = event.target.value;
  });
  document.addEventListener("change", (event) => {
    const { id } = event.target;
    if (id === "upload-file" && event.target.files[0]) {
      app.upload.url = URL.createObjectURL(event.target.files[0]);
    } else if (id === "upload-barcode") {
      app.upload.barcode = event.target.value;
    } else if (!["weight-range", "weight-number"].includes(id)) {
      return;
    }
    renderCards();
  });

  $("#btn-xray").addEventListener("click", (event) => {
    const on = event.currentTarget.getAttribute("aria-pressed") !== "true";
    event.currentTarget.setAttribute("aria-pressed", String(on));
    machine.setXray(on);
  });
  $("#btn-camera").addEventListener("click", () => machine.resetView());
  $("#btn-repeat").addEventListener("click", repeatLast);
  $("#btn-reset").addEventListener("click", () => location.reload());

  // Nama bagian mesin saat kursor di atasnya.
  const viewport = $("#viewport");
  const tooltip = $("#part-tooltip");
  viewport.addEventListener("pointermove", (event) => {
    const rect = viewport.getBoundingClientRect();
    const part = machine.partAt(event.clientX - rect.left, event.clientY - rect.top);
    tooltip.hidden = !part;
    if (!part) return;
    const [name, description] = PARTS[part];
    tooltip.innerHTML = `<strong>${ui.esc(name)}</strong><span>${ui.esc(description)}</span>`;
    tooltip.style.left = `${event.clientX - rect.left + 14}px`;
    tooltip.style.top = `${event.clientY - rect.top + 14}px`;
  });
  viewport.addEventListener("pointerleave", () => { tooltip.hidden = true; });
}

init();
