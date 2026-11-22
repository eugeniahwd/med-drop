// State machine mesin MedDrop. Murni logika (tanpa DOM/3D) agar bisa diuji dengan `node --test`.
//
// Alur: IDLE → AUTH → HATCH_OPEN → ITEM_PLACED → HATCH_CLOSED_LOCKED → VERIFYING
//   → ACCEPTED → TRAP_OPEN → ITEM_DROPPED → CONFIRMED → DONE
//   → REJECTED → RETURN_OPEN → ITEM_RETRIEVED → DONE
// ERROR (aman): pintu depan dibuka kembali agar barang bisa diambil.
//
// Setiap state menetapkan keluaran aktuator. Trap door dua arah: "to_bin" (miring ke
// belakang, barang jatuh ke bin) atau "to_return" (miring ke depan, barang ke baki pengembalian).

export const STATE_LABELS = {
  IDLE: "Ready",
  AUTH: "Checking member",
  HATCH_OPEN: "Front door open",
  ITEM_PLACED: "Item placed",
  HATCH_CLOSED_LOCKED: "Door closed and locked",
  VERIFYING: "Checking",
  ACCEPTED: "Accepted",
  TRAP_OPEN: "Dropping into bin",
  ITEM_DROPPED: "Item in bin",
  CONFIRMED: "Drop-off recorded",
  REJECTED: "Rejected, returning item",
  RETURN_OPEN: "Return door open",
  ITEM_RETRIEVED: "Item collected",
  DONE: "Done",
  ERROR: "Fault, front door reopened",
};

const closed = { frontHatch: "closed", frontLocked: true, trapDoor: "closed", returnHatch: "closed" };

export const OUTPUTS = {
  IDLE: { ...closed, led: "blue" },
  AUTH: { ...closed, led: "blue" },
  HATCH_OPEN: { ...closed, frontHatch: "open", frontLocked: false, led: "blue" },
  ITEM_PLACED: { ...closed, frontHatch: "open", frontLocked: false, led: "blue" },
  HATCH_CLOSED_LOCKED: { ...closed, led: "yellow" },
  VERIFYING: { ...closed, led: "yellow" },
  ACCEPTED: { ...closed, led: "green" },
  TRAP_OPEN: { ...closed, trapDoor: "to_bin", led: "green" },
  ITEM_DROPPED: { ...closed, trapDoor: "to_bin", led: "green" },
  CONFIRMED: { ...closed, led: "green" },
  REJECTED: { ...closed, trapDoor: "to_return", led: "red" },
  RETURN_OPEN: { ...closed, returnHatch: "open", led: "red" },
  ITEM_RETRIEVED: { ...closed, led: "red" },
  DONE: { ...closed, led: "blue" },
  ERROR: { ...closed, frontHatch: "open", frontLocked: false, led: "red" },
};

export const TRANSITIONS = {
  IDLE: ["AUTH"],
  AUTH: ["HATCH_OPEN", "IDLE"],
  HATCH_OPEN: ["ITEM_PLACED", "IDLE"],
  ITEM_PLACED: ["HATCH_CLOSED_LOCKED"],
  HATCH_CLOSED_LOCKED: ["VERIFYING"],
  VERIFYING: ["ACCEPTED", "REJECTED"],
  ACCEPTED: ["TRAP_OPEN"],
  TRAP_OPEN: ["ITEM_DROPPED"],
  ITEM_DROPPED: ["CONFIRMED"],
  CONFIRMED: ["DONE"],
  REJECTED: ["RETURN_OPEN"],
  RETURN_OPEN: ["ITEM_RETRIEVED"],
  ITEM_RETRIEVED: ["DONE"],
  ERROR: ["DONE"],
  DONE: ["AUTH", "IDLE"],
};
// Gangguan bisa terjadi kapan pun selama ada barang di dalam mesin.
for (const state of ["ITEM_PLACED", "HATCH_CLOSED_LOCKED", "VERIFYING", "ACCEPTED", "TRAP_OPEN", "REJECTED"]) {
  TRANSITIONS[state].push("ERROR");
}

// Pintu depan wajib terkunci dari penutupan sampai keputusan keluar (anti-penukaran barang).
const MUST_BE_LOCKED = ["HATCH_CLOSED_LOCKED", "VERIFYING"];

/** Daftar pelanggaran keselamatan untuk keluaran aktuator `outputs` pada `state` (kosong = aman). */
export function checkInterlocks(state, outputs) {
  const violations = [];
  if (outputs.frontHatch !== "closed" && outputs.trapDoor !== "closed") {
    violations.push("Front door and trap door open at the same time");
  }
  if (outputs.returnHatch !== "closed" && outputs.trapDoor !== "closed") {
    violations.push("Return door and trap door open at the same time");
  }
  if (MUST_BE_LOCKED.includes(state) && !(outputs.frontHatch === "closed" && outputs.frontLocked)) {
    violations.push("Front door not locked during the check");
  }
  return violations;
}

export class MachineStateMachine {
  constructor(onChange = () => {}) {
    this.onChange = onChange;
    this.state = "IDLE";
    this.history = ["IDLE"];
  }

  get outputs() {
    return OUTPUTS[this.state];
  }

  can(to) {
    return (TRANSITIONS[this.state] || []).includes(to);
  }

  /** Pindah state. Transisi yang tidak ada di tabel ditolak dengan error. */
  transition(to) {
    if (!this.can(to)) {
      throw new Error(`Invalid transition: ${this.state} → ${to}`);
    }
    const from = this.state;
    this.state = to;
    this.history.push(to);
    const change = { from, to, outputs: OUTPUTS[to], violations: checkInterlocks(to, OUTPUTS[to]) };
    this.onChange(change);
    return change;
  }

  /** Reset simulasi: kembali ke IDLE tanpa melewati tabel transisi. */
  reset() {
    const from = this.state;
    this.state = "IDLE";
    this.history = ["IDLE"];
    this.onChange({ from, to: "IDLE", outputs: OUTPUTS.IDLE, violations: [], reset: true });
  }
}
