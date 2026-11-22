// Model 3D mesin MedDrop (Three.js, bentuk dasar).
// Setiap bagian adalah satu THREE.Group dengan nama tetap (lihat PARTS), sehingga nanti
// bisa diganti model dari Fusion 360 tanpa mengubah logika animasi.
// Satuan: meter. Sumbu y ke atas, sisi depan mesin menghadap +z.

import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";

export const PARTS = {
  body: ["Machine frame", "Outer panels and the frame that holds every component."],
  kiosk_screen: ["Kiosk screen", "Touchscreen for the member number, instructions, and results."],
  member_scanner_window: ["Member card scanner", "Reads a member card or a code from the app."],
  status_led: ["Status light", "Blue: ready. Yellow: checking. Green: accepted. Red: rejected."],
  hatch_lock: ["Door lock light", "Red means the front door is locked, so items cannot be swapped during a check."],
  front_hatch: ["Front door", "Sliding door for inserting medicine."],
  verification_chamber: ["Inspection chamber", "Closed chamber where the medicine is photographed, scanned, and weighed."],
  camera: ["Camera and barcode scanner", "Photographs the package from above and reads its barcode."],
  load_cell_plate: ["Scale (load cell)", "Weighs the item to catch empty packages or swapped contents."],
  trap_door: ["Two-way trap door", "Tilts back to drop medicine into the bin, or forward to hand the item back."],
  return_hatch: ["Return door", "Where rejected items are handed back."],
  collection_bin: ["Collection bin", "Holds accepted medicine. Emptied by a licensed hazardous waste (B3) handler."],
  electronics_bay: ["Electronics bay", "Microcontroller, door motor drivers, and power supply."],
};

const COLOR = {
  shell: 0xf2f6f4, trim: 0x0e7c5a, trimDark: 0x0a5a42, interior: 0xe3eae6, steel: 0xb4bfba,
  steelDark: 0x6f7c76, glass: 0x13261f, bin: 0x2f8f68, binFill: 0x1d5e44, pcb: 0x1f6b4a,
  item: 0xffffff, lockOn: 0xd2423a, lockOff: 0x1e9e5a,
};
export const LED_COLOR = { blue: 0x2f7dd1, yellow: 0xe0a100, green: 0x1e9e5a, red: 0xd2423a };
const SCREEN_TONE = { idle: "#0c3b2e", busy: "#5c4300", ok: "#0f5a37", bad: "#6b1f1a" };

// Posisi penting.
const PLATE_Y = 0.78;                                  // tinggi engsel trap door (lantai ruang verifikasi)
const ITEM_SIZE = new THREE.Vector3(0.13, 0.05, 0.09);
const ITEM_ON_PLATE = new THREE.Vector3(0, PLATE_Y + 0.01 + ITEM_SIZE.y / 2, 0.12);
const ITEM_OUTSIDE_FRONT = new THREE.Vector3(0, 0.88, 0.62);
const ITEM_IN_RETURN = new THREE.Vector3(0, 0.59 + ITEM_SIZE.y / 2, 0.22);
const BIN = { x: 0, y: 0.085, z: -0.09, w: 0.6, h: 0.5, d: 0.35 };
const TRAP_ANGLE = { closed: 0, to_bin: -0.9, to_return: 0.9 };
const HATCH_SLIDE = 0.235;
const RETURN_OPEN_ANGLE = 1.15;
const MAX_ITEMS_IN_BIN = 6;

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const easeIn = (t) => t * t;

function tween(ms, update, ease = easeInOut) {
  if (reduceMotion || ms <= 0) {
    update(1);
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const start = performance.now();
    const frame = (now) => {
      const t = Math.min(1, (now - start) / ms);
      update(ease(t));
      if (t < 1) requestAnimationFrame(frame);
      else resolve();
    };
    requestAnimationFrame(frame);
  });
}

export class Machine3D {
  constructor(container) {
    this.container = container;
    this.physical = { frontHatch: "closed", trapDoor: "closed", returnHatch: "closed" };
    this.xrayMaterials = [];
    this.binItems = [];
    this.item = null;
    this.itemLocation = null;
    this.ledPulse = false;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xf6faf8);
    this.camera = new THREE.PerspectiveCamera(35, 1, 0.05, 20);
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.minDistance = 0.9;
    this.controls.maxDistance = 4.5;
    this.controls.maxPolarAngle = Math.PI * 0.53;
    this.resetView();

    this.#buildLights();
    this.#buildGround();
    this.#buildBody();
    this.#buildKiosk();
    this.#buildFrontDevices();
    this.#buildChamber();
    this.#buildTrapDoor();
    this.#buildReturn();
    this.#buildBin();
    this.#buildElectronics();
    this.setScreen({ heading: "Drop off unused medicine", body: "Enter your member number." });

    new ResizeObserver(() => this.#resize()).observe(container);
    this.#resize();
    const clock = new THREE.Clock();
    this.renderer.setAnimationLoop(() => {
      const t = clock.getElapsedTime();
      this.ledMaterial.emissiveIntensity = this.ledPulse && !reduceMotion ? 0.55 + 0.45 * Math.sin(t * 7) : 1;
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
    });
  }

  // ---------- pembangun bagian ----------

  #part(name) {
    const group = new THREE.Group();
    group.name = name;
    this.scene.add(group);
    return group;
  }

  #mesh(geometry, material, parent, [x, y, z] = [0, 0, 0]) {
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  }

  #box(w, h, d, material, parent, position) {
    return this.#mesh(new THREE.BoxGeometry(w, h, d), material, parent, position);
  }

  #xray(material) {
    this.xrayMaterials.push(material);
    return material;
  }

  #buildLights() {
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0xcfe2d9, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(1.6, 3, 2.2);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    Object.assign(sun.shadow.camera, { left: -1, right: 1, top: 2, bottom: -0.2, near: 0.5, far: 6 });
    this.scene.add(sun);
  }

  #buildGround() {
    // Lantai hanya menampilkan bayangan, agar tidak terlihat sebagai piringan di belakang mesin.
    const ground = new THREE.Mesh(new THREE.CircleGeometry(3, 48), new THREE.ShadowMaterial({ opacity: 0.16 }));
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    this.scene.add(ground);
  }

  #buildBody() {
    const body = this.#part("body");
    const shell = this.#xray(new THREE.MeshStandardMaterial({ color: COLOR.shell, roughness: 0.45, metalness: 0.05 }));
    const trim = this.#xray(new THREE.MeshStandardMaterial({ color: COLOR.trim, roughness: 0.5 }));
    const zFront = 0.295;
    this.#box(0.7, 1.6, 0.01, shell, body, [0, 0.8, -0.295]);
    this.#box(0.01, 1.6, 0.6, shell, body, [-0.345, 0.8, 0]);
    this.#box(0.01, 1.6, 0.6, shell, body, [0.345, 0.8, 0]);
    this.#box(0.7, 0.01, 0.6, shell, body, [0, 1.595, 0]);
    this.#box(0.72, 0.06, 0.62, new THREE.MeshStandardMaterial({ color: COLOR.trimDark }), body, [0, 0.03, 0]);
    // Panel depan dengan dua bukaan: ruang verifikasi (y 0.78 sampai 1.00) dan pengembalian (y 0.58 sampai 0.70).
    this.#box(0.7, 0.6, 0.01, shell, body, [0, 1.3, zFront]);
    this.#box(0.17, 0.22, 0.01, shell, body, [-0.265, 0.89, zFront]);
    this.#box(0.17, 0.22, 0.01, shell, body, [0.265, 0.89, zFront]);
    this.#box(0.7, 0.08, 0.01, shell, body, [0, 0.74, zFront]);
    this.#box(0.23, 0.12, 0.01, shell, body, [-0.235, 0.64, zFront]);
    this.#box(0.23, 0.12, 0.01, shell, body, [0.235, 0.64, zFront]);
    this.#box(0.7, 0.52, 0.01, shell, body, [0, 0.32, zFront]);
    // Bingkai hijau di sekitar bukaan dan pita merek di atas.
    for (const [w, h, x, y] of [[0.4, 0.012, 0, 1.006], [0.4, 0.012, 0, 0.774], [0.012, 0.24, -0.194, 0.89],
      [0.012, 0.24, 0.194, 0.89], [0.27, 0.01, 0, 0.705], [0.27, 0.01, 0, 0.575]]) {
      this.#box(w, h, 0.01, trim, body, [x, y, zFront + 0.008]);
    }
    this.#box(0.7, 0.09, 0.012, trim, body, [0, 1.545, zFront + 0.004]);
    const mark = new THREE.Mesh(new THREE.PlaneGeometry(0.32, 0.05),
      new THREE.MeshBasicMaterial({ map: this.#textTexture("MedDrop", 512, 80, "#ffffff", "#0e7c5a"), transparent: true }));
    mark.position.set(0, 1.545, zFront + 0.011);
    body.add(mark);
  }

  #buildKiosk() {
    const kiosk = this.#part("kiosk_screen");
    this.#box(0.47, 0.31, 0.03, new THREE.MeshStandardMaterial({ color: 0x1b2b25, roughness: 0.6 }), kiosk, [0, 1.3, 0.31]);
    this.screenCanvas = document.createElement("canvas");
    this.screenCanvas.width = 768;
    this.screenCanvas.height = 480;
    this.screenTexture = new THREE.CanvasTexture(this.screenCanvas);
    this.screenTexture.colorSpace = THREE.SRGBColorSpace;
    const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.43, 0.27), new THREE.MeshBasicMaterial({ map: this.screenTexture }));
    screen.position.set(0, 1.3, 0.3255);
    kiosk.add(screen);
  }

  #buildFrontDevices() {
    const scanner = this.#part("member_scanner_window");
    this.#box(0.17, 0.065, 0.012, new THREE.MeshStandardMaterial({ color: COLOR.trim }), scanner, [0, 1.105, 0.301]);
    this.#box(0.15, 0.048, 0.012, new THREE.MeshStandardMaterial({ color: COLOR.glass, roughness: 0.15, metalness: 0.3 }),
      scanner, [0, 1.105, 0.304]);

    const led = this.#part("status_led");
    this.ledMaterial = new THREE.MeshStandardMaterial({ color: LED_COLOR.blue, emissive: LED_COLOR.blue, emissiveIntensity: 1 });
    this.#box(0.36, 0.014, 0.012, this.ledMaterial, led, [0, 1.035, 0.302]);

    const lock = this.#part("hatch_lock");
    this.lockMaterial = new THREE.MeshStandardMaterial({ color: COLOR.lockOn, emissive: COLOR.lockOn, emissiveIntensity: 0.8 });
    const lamp = this.#mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.012, 24), this.lockMaterial, lock, [0.25, 0.97, 0.302]);
    lamp.rotation.x = Math.PI / 2;

    const hatch = this.#part("front_hatch");
    const door = this.#xray(new THREE.MeshStandardMaterial({ color: 0xe7eeea, roughness: 0.35, metalness: 0.1 }));
    this.hatchDoor = new THREE.Group();
    hatch.add(this.hatchDoor);
    this.#box(0.38, 0.235, 0.01, door, this.hatchDoor, [0, 0.89, 0.284]);
    this.#box(0.16, 0.014, 0.012, this.#xray(new THREE.MeshStandardMaterial({ color: COLOR.trim })), this.hatchDoor, [0, 0.795, 0.288]);
  }

  #buildChamber() {
    const chamber = this.#part("verification_chamber");
    const wall = new THREE.MeshStandardMaterial({ color: COLOR.interior, roughness: 0.8, side: THREE.DoubleSide });
    this.#box(0.006, 0.22, 0.34, wall, chamber, [-0.18, 0.89, 0.12]);
    this.#box(0.006, 0.22, 0.34, wall, chamber, [0.18, 0.89, 0.12]);
    this.#box(0.36, 0.006, 0.34, wall, chamber, [0, 1.0, 0.12]);
    this.#box(0.36, 0.22, 0.006, wall, chamber, [0, 0.89, -0.05]);
    const light = new THREE.PointLight(0xffffff, 0.35, 0.6);
    light.position.set(0, 0.96, 0.15);
    chamber.add(light);

    const camera = this.#part("camera");
    const dark = new THREE.MeshStandardMaterial({ color: 0x24302b, roughness: 0.4 });
    this.#mesh(new THREE.CylinderGeometry(0.024, 0.024, 0.03, 24), dark, camera, [0, 0.98, 0.1]);
    this.#mesh(new THREE.CylinderGeometry(0.013, 0.013, 0.008, 24),
      new THREE.MeshStandardMaterial({ color: 0x0a1a3a, roughness: 0.05, metalness: 0.6 }), camera, [0, 0.962, 0.1]);
  }

  #buildTrapDoor() {
    this.trapDoor = this.#part("trap_door");
    this.trapDoor.position.set(0, PLATE_Y, 0.12);  // engsel di tengah: bisa miring dua arah
    this.#box(0.34, 0.01, 0.32, new THREE.MeshStandardMaterial({ color: COLOR.steelDark, roughness: 0.5, metalness: 0.4 }),
      this.trapDoor, [0, -0.005, 0]);
    const plate = new THREE.Group();
    plate.name = "load_cell_plate";
    this.trapDoor.add(plate);
    this.#box(0.27, 0.008, 0.25, new THREE.MeshStandardMaterial({ color: COLOR.steel, roughness: 0.3, metalness: 0.6 }),
      plate, [0, 0.006, 0]);
    this.#box(0.04, 0.014, 0.2, new THREE.MeshStandardMaterial({ color: 0x3d4a44 }), plate, [0, -0.018, 0]);
    this.#mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.36, 16), new THREE.MeshStandardMaterial({ color: 0x3d4a44 }),
      this.trapDoor, [0, -0.012, 0]).rotation.z = Math.PI / 2;
  }

  #buildReturn() {
    const group = this.#part("return_hatch");
    const tray = new THREE.MeshStandardMaterial({ color: COLOR.interior, roughness: 0.8 });
    this.#box(0.24, 0.01, 0.15, tray, group, [0, 0.585, 0.215]);
    this.#box(0.006, 0.05, 0.15, tray, group, [-0.12, 0.61, 0.215]);
    this.#box(0.006, 0.05, 0.15, tray, group, [0.12, 0.61, 0.215]);
    this.#box(0.24, 0.12, 0.006, tray, group, [0, 0.64, 0.14]);
    this.returnDoor = new THREE.Group();
    this.returnDoor.position.set(0, 0.58, 0.3);  // engsel di sisi bawah, membuka ke luar
    group.add(this.returnDoor);
    this.#box(0.24, 0.12, 0.012, this.#xray(new THREE.MeshStandardMaterial({ color: 0xe7eeea, roughness: 0.35 })),
      this.returnDoor, [0, 0.06, 0]);
    this.#box(0.1, 0.012, 0.014, this.#xray(new THREE.MeshStandardMaterial({ color: COLOR.trim })), this.returnDoor, [0, 0.1, 0.006]);
  }

  #buildBin() {
    const bin = this.#part("collection_bin");
    // Dinding agak tembus pandang agar isi bin terlihat dalam mode tembus pandang.
    const wall = new THREE.MeshStandardMaterial({ color: COLOR.bin, roughness: 0.6, transparent: true, opacity: 0.55, depthWrite: false });
    const { x, y, z, w, h, d } = BIN;
    this.#box(w, 0.01, d, wall, bin, [x, y, z]);
    this.#box(0.008, h, d, wall, bin, [x - w / 2, y + h / 2, z]);
    this.#box(0.008, h, d, wall, bin, [x + w / 2, y + h / 2, z]);
    this.#box(w, h, 0.008, wall, bin, [x, y + h / 2, z - d / 2]);
    this.#box(w, h * 0.6, 0.008, wall, bin, [x, y + h * 0.3, z + d / 2]);
    this.binFill = this.#box(w - 0.02, 1, d - 0.02,
      new THREE.MeshStandardMaterial({ color: COLOR.binFill, transparent: true, opacity: 0.55 }), bin, [x, y, z]);
    this.setBinFill(0);
  }

  #buildElectronics() {
    const bay = this.#part("electronics_bay");
    this.#box(0.6, 0.36, 0.2, new THREE.MeshStandardMaterial({ color: 0x4a5752, roughness: 0.7 }), bay, [0, 1.33, -0.18]);
    this.#box(0.5, 0.26, 0.004, new THREE.MeshStandardMaterial({ color: COLOR.pcb, roughness: 0.6 }), bay, [0, 1.33, -0.078]);
    const chip = new THREE.MeshStandardMaterial({ color: 0x15201c });
    for (const [w, h, cx, cy] of [[0.08, 0.05, -0.12, 1.38], [0.05, 0.05, 0.05, 1.37], [0.12, 0.04, 0.12, 1.27], [0.04, 0.07, -0.18, 1.27]]) {
      this.#box(w, h, 0.012, chip, bay, [cx, cy, -0.072]);
    }
  }

  #textTexture(text, w, h, color, background) {
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = color;
    ctx.font = `700 ${Math.round(h * 0.62)}px "Atkinson Hyperlegible", system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, w / 2, h / 2 + 2);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }

  #resize() {
    const { clientWidth: w, clientHeight: h } = this.container;
    if (!w || !h) return;
    this.renderer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  // ---------- kontrol tampilan ----------

  resetView() {
    this.camera.position.set(1.85, 1.55, 2.5);
    this.controls.target.set(0, 0.8, 0);
    this.controls.update();
  }

  setXray(on) {
    for (const m of this.xrayMaterials) {
      m.transparent = on;
      m.opacity = on ? 0.13 : 1;
      m.depthWrite = !on;
      m.needsUpdate = true;
    }
    this.xray = on;
  }

  /** Bagian mesin di bawah titik layar (x, y piksel relatif kanvas), atau null. */
  partAt(x, y) {
    const { clientWidth: w, clientHeight: h } = this.container;
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(new THREE.Vector2((x / w) * 2 - 1, -(y / h) * 2 + 1), this.camera);
    const skipInXray = new Set(["body", "front_hatch", "return_hatch"]);
    for (const hit of raycaster.intersectObjects(this.scene.children, true)) {
      let node = hit.object;
      while (node && !PARTS[node.name]) node = node.parent;
      if (!node) continue;
      if (this.xray && skipInXray.has(node.name)) continue;
      return node.name;
    }
    return null;
  }

  setLed(color) {
    this.ledMaterial.color.setHex(LED_COLOR[color]);
    this.ledMaterial.emissive.setHex(LED_COLOR[color]);
    this.ledPulse = color === "yellow";
  }

  setLock(locked) {
    const c = locked ? COLOR.lockOn : COLOR.lockOff;
    this.lockMaterial.color.setHex(c);
    this.lockMaterial.emissive.setHex(c);
  }

  /** Cerminan isi layar kios pada model 3D. tone: idle | busy | ok | bad */
  setScreen({ heading, body = "", tone = "idle" }) {
    const ctx = this.screenCanvas.getContext("2d");
    const { width: w, height: h } = this.screenCanvas;
    ctx.fillStyle = SCREEN_TONE[tone];
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "rgba(255,255,255,0.7)";
    ctx.font = `700 30px "Atkinson Hyperlegible", system-ui, sans-serif`;
    ctx.fillText("MedDrop", 40, 60);
    ctx.fillStyle = "#ffffff";
    ctx.font = `700 62px "Atkinson Hyperlegible", system-ui, sans-serif`;
    let y = this.#wrap(ctx, heading, 40, 160, w - 80, 70);
    ctx.font = `400 36px "Atkinson Hyperlegible", system-ui, sans-serif`;
    this.#wrap(ctx, body, 40, y + 30, w - 80, 46);
    this.screenTexture.needsUpdate = true;
  }

  #wrap(ctx, text, x, y, maxWidth, lineHeight) {
    let line = "";
    for (const word of String(text).split(" ")) {
      const test = line ? `${line} ${word}` : word;
      if (ctx.measureText(test).width > maxWidth && line) {
        ctx.fillText(line, x, y);
        line = word;
        y += lineHeight;
      } else {
        line = test;
      }
    }
    if (line) ctx.fillText(line, x, y);
    return y + lineHeight;
  }

  setBinFill(fillPct) {
    const level = Math.max(0.002, Math.min(1, fillPct / 100)) * (BIN.h - 0.02);
    this.binFill.scale.y = level;
    this.binFill.position.y = BIN.y + 0.005 + level / 2;
    this.binLevel = level;
  }

  // ---------- aktuator ----------

  /** Gerakkan aktuator menuju keluaran state machine. Penutupan selalu dijalankan sebelum pembukaan. */
  async applyOutputs(outputs) {
    this.setLed(outputs.led);
    this.setLock(outputs.frontLocked);
    const closing = [];
    const opening = [];
    const plan = (current, target, run) => {
      if (current !== target) (target === "closed" ? closing : opening).push(run);
    };
    plan(this.physical.frontHatch, outputs.frontHatch, () => this.#moveFrontHatch(outputs.frontHatch));
    plan(this.physical.returnHatch, outputs.returnHatch, () => this.#moveReturnHatch(outputs.returnHatch));
    plan(this.physical.trapDoor, outputs.trapDoor, () => this.#moveTrapDoor(outputs.trapDoor));
    await Promise.all(closing.map((run) => run()));
    await Promise.all(opening.map((run) => run()));
  }

  // Bagian dianggap terbuka sejak mulai membuka sampai selesai menutup.
  #setPhysical(key, value) {
    this.physical[key] = value;
  }

  async #moveFrontHatch(target) {
    const from = this.hatchDoor.position.y;
    const to = target === "open" ? HATCH_SLIDE : 0;
    if (target === "open") this.#setPhysical("frontHatch", "open");
    await tween(650, (t) => { this.hatchDoor.position.y = from + (to - from) * t; });
    if (target === "closed") this.#setPhysical("frontHatch", "closed");
  }

  async #moveReturnHatch(target) {
    const from = this.returnDoor.rotation.x;
    const to = target === "open" ? RETURN_OPEN_ANGLE : 0;
    if (target === "open") this.#setPhysical("returnHatch", "open");
    await tween(550, (t) => { this.returnDoor.rotation.x = from + (to - from) * t; });
    if (target === "closed") this.#setPhysical("returnHatch", "closed");
  }

  async #moveTrapDoor(target) {
    const from = this.trapDoor.rotation.x;
    const to = TRAP_ANGLE[target];
    if (target !== "closed") this.#setPhysical("trapDoor", target);
    const tilt = tween(600, (t) => { this.trapDoor.rotation.x = from + (to - from) * t; });
    const carry = this.itemLocation === "plate" && target !== "closed" ? this.#carryItem(target) : null;
    await Promise.all([tilt, carry]);
    if (target === "closed") this.#setPhysical("trapDoor", "closed");
  }

  // ---------- barang ----------

  /** Barang (kotak bertekstur foto kartu) masuk lewat pintu depan ke pelat load cell. */
  async insertItem(photoUrl) {
    this.#removeItem();
    const texture = new THREE.TextureLoader().load(photoUrl);
    texture.colorSpace = THREE.SRGBColorSpace;
    const side = new THREE.MeshStandardMaterial({ color: COLOR.item, roughness: 0.6 });
    const face = new THREE.MeshStandardMaterial({ map: texture, roughness: 0.6 });
    this.item = new THREE.Mesh(new THREE.BoxGeometry(ITEM_SIZE.x, ITEM_SIZE.y, ITEM_SIZE.z), [side, side, face, side, face, side]);
    this.item.castShadow = true;
    this.item.position.copy(ITEM_OUTSIDE_FRONT);
    this.scene.add(this.item);
    this.itemLocation = "moving";
    await this.#moveItem(ITEM_ON_PLATE, 900);
    this.itemLocation = "plate";
  }

  async #carryItem(direction) {
    const start = this.item.position.clone();
    if (direction === "to_bin") {
      const edge = new THREE.Vector3(0, PLATE_Y - 0.03, -0.03);
      const landing = new THREE.Vector3((Math.random() - 0.5) * 0.3, BIN.y + this.binLevel + ITEM_SIZE.y / 2 + 0.01,
        BIN.z + (Math.random() - 0.5) * 0.12);
      await tween(380, (t) => { this.item.position.lerpVectors(start, edge, t); this.item.rotation.x = -0.9 * t; }, easeIn);
      const spin = (Math.random() - 0.5) * 1.2;
      await tween(520, (t) => {
        this.item.position.lerpVectors(edge, landing, t);
        this.item.rotation.x = -0.9 * (1 - t);
        this.item.rotation.y = spin * t;
      }, easeIn);
      this.itemLocation = "bin";
      this.binItems.push(this.item);
      if (this.binItems.length > MAX_ITEMS_IN_BIN) this.scene.remove(this.binItems.shift());
      this.item = null;
    } else {
      const edge = new THREE.Vector3(0, PLATE_Y - 0.03, 0.28);
      await tween(380, (t) => { this.item.position.lerpVectors(start, edge, t); this.item.rotation.x = 0.9 * t; }, easeIn);
      await tween(420, (t) => {
        this.item.position.lerpVectors(edge, ITEM_IN_RETURN, t);
        this.item.rotation.x = 0.9 * (1 - t);
      }, easeIn);
      this.itemLocation = "return";
    }
  }

  /** Pengguna mengambil barang: dari baki pengembalian, atau dari pelat bila terjadi gangguan. */
  async takeItem() {
    if (!this.item) return;
    const exit = this.itemLocation === "return"
      ? new THREE.Vector3(0, ITEM_IN_RETURN.y + 0.03, 0.6)
      : ITEM_OUTSIDE_FRONT.clone();
    await this.#moveItem(exit, 700);
    this.#removeItem();
  }

  #moveItem(target, ms) {
    const start = this.item.position.clone();
    return tween(ms, (t) => this.item.position.lerpVectors(start, target, t));
  }

  #removeItem() {
    if (this.item) this.scene.remove(this.item);
    this.item = null;
    this.itemLocation = null;
  }

  /** Kembalikan mesin ke posisi awal seketika (tombol Reset). */
  resetAll() {
    this.#removeItem();
    this.hatchDoor.position.y = 0;
    this.returnDoor.rotation.x = 0;
    this.trapDoor.rotation.x = 0;
    this.physical = { frontHatch: "closed", trapDoor: "closed", returnHatch: "closed" };
    this.setLed("blue");
    this.setLock(true);
  }
}
