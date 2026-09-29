// Startup and the frame loop. Physics at a fixed 1/120 s, rendering on requestAnimationFrame.
// Render order: ship shadow map -> mirrored world (reflection, half res) -> world without water (colour + depth for
// refraction) -> water on top -> bloom and tone mapping (post.js).
import * as THREE from 'three';
import { makeSky, makeSkyUniforms, sunDirection, patchHaze } from './sky.js';
import { makeSea, seaUniforms } from './waves.js';
import { Wind } from './wind.js';
import { makeOcean } from './ocean.js';
import { Wake } from './wake.js';
import { loadShip } from './ship.js';
import { Boat } from './boat.js';
import { Shadows, patchShadow } from './shadows.js';
import { Post } from './post.js';
import { Q as QL, MOBILE } from './quality.js';
import { Input } from './input.js';
import { OrbitCam } from './cam.js';
import { makeHUD } from './hud.js';
import { loadIslands } from './islands.js';
import { makeTrees } from './trees.js';
import { loadPorts } from './port.js';
import { Sound } from './audio.js';
import { Tide } from './tide.js';
import { makeCrew } from './people.js';
import { makeBoats } from './boats.js';

const QS = new URLSearchParams(location.search);
const RENDER = QS.has('render');
const W = 1600, H = 900;
const PR = RENDER ? 2 : Math.min(devicePixelRatio || 1, 1.5);
const DT = 1 / 120;

const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(PR);
renderer.setSize(W, H, false);
renderer.toneMapping = THREE.NoToneMapping;
renderer.localClippingEnabled = true;

const scene = new THREE.Scene();
const world = new THREE.Group();       // everything that is mirrored for the water reflection
scene.add(world);
const camera = new THREE.PerspectiveCamera(40, W / H, 0.3, 30000);

// ---- Time of day: the Seto Inland Sea (34.4 N), early October
const LAT = 34.4, DAY = 280;
let hour = parseFloat(QS.get('t') ?? '6.85');
const TIME_SCALE = parseFloat(QS.get('ts') ?? '20');     // game seconds per real second (1 hour = 3 minutes)
const sunDir = sunDirection(LAT, DAY, hour);
const sunCol = new THREE.Color();
const skyU = makeSkyUniforms(sunDir, new THREE.Vector3());
const U = { uTime: { value: 0 } };
const sky = makeSky(skyU);
world.add(sky);
const sunLight = new THREE.DirectionalLight(0xffffff, 1);
scene.add(sunLight, sunLight.target);
const hemi = new THREE.HemisphereLight(0xffffff, 0xffffff, 1);
scene.add(hemi);

// sunlight colour and strength from the elevation: the long, hazy path near the horizon reddens and dims it
function lightFromSun() {
  const el = Math.asin(sunDir.y);
  const air = 1 / Math.max(Math.sin(Math.max(el, 0.01)) + 0.15 * Math.pow(Math.max(el, 0) * 57.3 + 3.885, -1.253), 0.02);
  const tr = [Math.exp(-0.035 * air), Math.exp(-0.075 * air), Math.exp(-0.16 * air)];
  const up = THREE.MathUtils.smoothstep(el, -0.06, 0.05);
  const I = 7.0 * up;
  sunCol.setRGB(tr[0] * I, tr[1] * I, tr[2] * I);
  skyU.uSunCol.value.set(sunCol.r, sunCol.g, sunCol.b);
  sunLight.color.copy(sunCol); sunLight.intensity = 1;
  sunLight.position.copy(sunDir).multiplyScalar(100);
  const dusk = THREE.MathUtils.clamp(1 - (el - 0.02) / 0.3, 0, 1);
  skyU.uDusk.value = dusk * dusk;
  skyU.uNight.value = THREE.MathUtils.clamp((-el - 0.02) / 0.12, 0, 1);
  // sky light from above (blue-grey), bounce from the sea below (dark blue-green)
  const k = THREE.MathUtils.clamp(0.15 + sunDir.y * 1.6, 0.02, 1.0) * (1 - skyU.uNight.value * 0.9);
  // hazy air scatters a lot of light: the shade is lit by a bright, pale sky
  hemi.color.setRGB(0.62 * k, 0.68 * k, 0.78 * k);
  hemi.groundColor.setRGB(0.1 * k, 0.12 * k, 0.12 * k);
  hemi.intensity = 2.2;
}
lightFromSun();

// ---- Sea, wind
const wind = new Wind({ speed: parseFloat(QS.get('wind') ?? '6.5'), dir: parseFloat(QS.get('wdir') ?? '0.9') });
const sea = makeSea({ wind: wind.speed, windDir: wind.dir, swellDir: 1.35, swellH: 0.35 });
const seaU = seaUniforms(sea);

// ---- Post, reflection and shadows
const post = new Post(renderer, W * PR, H * PR, { samples: MOBILE ? 0 : 4, levels: QL.bloomLevels });
const rtRefl = new THREE.WebGLRenderTarget(Math.round(W * PR * 0.5), Math.round(H * PR * 0.5), { type: THREE.HalfFloatType, depthBuffer: true });
const shadows = new Shadows(renderer, sunDir, { shipRes: MOBILE ? 1024 : 1536 });
const patch = (m, o) => patchHaze(patchShadow(m, shadows), skyU, o);

// ---- Islands
// ?noland skips them (for looking at the ship alone)
const islands = QS.has('noland') ? { group: new THREE.Group(), shadowCasters: [], height: () => -40, update() {} } : await loadIslands('data/', patch);
world.add(islands.group);
for (const m of islands.shadowCasters) shadows.addCaster(m);
const trees = QS.has('noland') ? null : makeTrees(islands, patch);
if (trees) world.add(trees.group);
const ports = QS.has('noland') ? null : await loadPorts('data/', islands, patch, renderer.capabilities.getMaxAnisotropy());
if (ports) { world.add(ports.group); for (const m of ports.group.children) shadows.addCaster(m); }
const boats = QS.has('noland') ? null : makeBoats(islands, sea, patch);
if (boats) world.add(boats.group);

// ---- Ship
const ship = await loadShip('data/', { aniso: renderer.capabilities.getMaxAnisotropy(), patch, U, skyU, seaU });
world.add(ship.group, ship.ropeGroup);
const crew = makeCrew(ship, patch);
for (const m of [...ship.casters, ...crew.meshes]) shadows.addCaster(m, { ship: true });
shadows.renderLand(new THREE.Vector3());
let lastLandSun = sunDir.clone();
const tide = new Tide(islands.map?.strait ?? { x: 285, z: 60, dir: 2.16, width: 240 });
tide.setHour(hour);
const boat = new Boat(ship.meta, sea, wind, islands.height, tide);
// Start: in the home harbour, sail down, bow toward the harbour mouth. Destination: the other harbour
const ports0 = islands.map?.ports ?? [];
const home = ports0[0], dest = ports0[1] ? { name: ports0[1].name, x: ports0[1].x, z: ports0[1].z } : null;
if (home) boat.place(home.x + Math.sin(home.face) * 40, home.z + Math.cos(home.face) * 40, home.face);
else boat.place(0, 0, parseFloat(QS.get('hd') ?? '2.3'));
boat.ctl.hoist = 0; boat.hoist = 0;

// ---- Water (drawn after the world so it can refract what is below)
const wake = new Wake(renderer, ship.meta.stations);
const waterScene = new THREE.Scene();
const ocean = makeOcean({ skyU, seaU, wakeU: wake.uniforms, windU: wind.uniforms, tideU: tide.uniforms, reflTarget: rtRefl, refrTarget: post.refr,
  shipShadowU: shadows.uniforms, timeU: U.uTime, quality: { oceanRings: MOBILE ? 150 : 240, oceanSeg: MOBILE ? 256 : 420 } });
waterScene.add(ocean.mesh);

// ---- Environment map for the wood's sky reflections: the sky rendered into a small cube
const pmrem = new THREE.PMREMGenerator(renderer);
const envScene = new THREE.Scene();
const envSky = new THREE.Mesh(sky.geometry, sky.material); envSky.scale.setScalar(0.005);
envScene.add(envSky);
envScene.add(new THREE.Mesh(new THREE.CircleGeometry(40, 24).rotateX(-Math.PI / 2).translate(0, -0.5, 0), new THREE.MeshBasicMaterial({ color: new THREE.Color(0.02, 0.04, 0.045) })));
let envRT = null;
function rebuildEnv() { envRT?.dispose(); envRT = pmrem.fromScene(envScene, 0.02); scene.environment = envRT.texture; }
rebuildEnv();
scene.traverse((o) => { if (o.material?.isMeshStandardMaterial) o.material.envMapIntensity = 0.9; });

// ---- Camera and input
const input = new Input();
const cam = new OrbitCam(camera, canvas);
const hud = makeHUD();
let started = RENDER || QS.has('skip'), arrived = false, dayStart = hour, logDist = 0;
const lastPos = new THREE.Vector3();
input.onPress = (code) => {
  if (!started) return;
  if (code === 'Space') {
    if (boat.ctl.anchor) { boat.ctl.anchor = null; hud.message('錨を上げた', 3); }
    else {
      const f = boat.forward(new THREE.Vector3());
      boat.ctl.anchor = { x: boat.pos.x + f.x * 12, z: boat.pos.z + f.z * 12, len: 30 };
      hud.message('錨を入れた', 3);
    }
  }
  if (code === 'KeyC') cam.cycle();
};
function checkArrival() {
  if (!dest || arrived || !started) return;
  const d = Math.hypot(dest.x - boat.pos.x, dest.z - boat.pos.z);
  if (d < 220 && boat.ctl.anchor) {
    arrived = true;
    const h = Math.floor(hour), mi = Math.floor((hour - h) * 60), took = (hour - dayStart);
    hud.message(`${dest.name}に着いた\n${h}時${String(mi).padStart(2, '0')}分　${(logDist / 1000).toFixed(1)}km を ${Math.floor(took)}時間${Math.round((took % 1) * 60)}分`, 12);
  } else if (d < 400 && !boat.ctl.anchor && Math.random() < 0.002) hud.message('港に入ったら Space で錨を入れる', 4);
}
const titleEl = document.getElementById('title'), goBtn = document.getElementById('go');
if (started) titleEl.classList.add('gone');
goBtn.disabled = false; goBtn.textContent = '舟を出す';
goBtn.addEventListener('click', () => {
  started = true; titleEl.classList.add('gone'); sound.start(); dayStart = hour;
  hud.message(`${home?.name ?? ''}\n${dest ? dest.name + 'へ' : ''}`, 5);
});
const sound = new Sound();
// browsers only allow audio after a gesture
for (const ev of ['pointerdown', 'keydown']) addEventListener(ev, () => sound.start(), { once: true });
const _camR = new THREE.Vector3();
function nearestLand() {
  if (!islands.map) return null;
  let best = null, bd = 2500;
  for (const is of islands.map.islands) {
    const d = Math.hypot(is.x - camera.position.x, is.z - camera.position.z) - is.r;
    if (d < bd) { bd = d; best = is; }
  }
  if (!best) return null;
  _camR.set(1, 0, 0).applyQuaternion(camera.quaternion);
  const dx = best.x - camera.position.x, dz = best.z - camera.position.z, L = Math.hypot(dx, dz) || 1;
  return (dx * _camR.x + dz * _camR.z) / L;
}

const clipUnder = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);
function renderReflection() {
  if (trees) trees.group.visible = false;         // trees are too small in the reflection to be worth drawing twice
  world.scale.y = -1; world.updateMatrixWorld(true);
  shadows.uniforms.uMirror.value = -1;
  renderer.clippingPlanes = [clipUnder];
  renderer.setRenderTarget(rtRefl); renderer.render(scene, camera);
  renderer.clippingPlanes = [];
  world.scale.y = 1; world.updateMatrixWorld(true);
  if (trees) trees.group.visible = true;
  shadows.uniforms.uMirror.value = 1;
  renderer.setRenderTarget(null);
}

let simT = 0, acc = 0;
const EXPOSURE = parseFloat(QS.get('ev') ?? '0.9');
function stepSim(dt) {
  // controls
  const c = boat.ctl, k = input.keys;
  if (k.KeyA) c.rudder = Math.min(c.rudder + dt * 0.8, 0.6);
  if (k.KeyD) c.rudder = Math.max(c.rudder - dt * 0.8, -0.6);
  if (!k.KeyA && !k.KeyD && input.autoCenter) c.rudder *= Math.exp(-dt * 0.8);
  if (k.KeyW) c.hoist = Math.min(c.hoist + dt * 0.5, 1);
  if (k.KeyS) c.hoist = Math.max(c.hoist - dt * 0.25, 0);
  if (k.KeyQ) c.brace = Math.min(c.brace + dt * 0.5, 1.25);
  if (k.KeyE) c.brace = Math.max(c.brace - dt * 0.5, -1.25);
  c.ro = k.KeyR ? 1 : 0;
  c.trimAuto = input.trim;
  if (input.trim) c.brace = autoTrim();
  acc += dt;
  while (acc >= DT) {
    acc -= DT; simT += DT;
    boat.step(DT, simT);
  }
  U.uTime.value = simT;
}
// "leave it to the master": set the yard so the sail meets the apparent wind at a good angle
function autoTrim() {
  const hd = boat.heading;
  const aw = boat.appWind;
  if (aw.lengthSq() < 0.01) return boat.ctl.brace;
  // apparent wind angle in ship frame (0 = from ahead)
  const from = Math.atan2(-aw.x, -aw.y);
  let rel = THREE.MathUtils.euclideanModulo(from - hd + Math.PI, Math.PI * 2) - Math.PI;
  // yard square to the ship downwind, braced up as the wind comes forward; the sail meets the wind at ~28 deg
  const target = Math.sign(rel) * THREE.MathUtils.clamp(Math.PI / 2 - Math.abs(rel) + 0.49, 0, 1.2);
  return target * -1;
}

let envAt = hour;
function advanceClock(dt) {
  if (window.__freezeClock || !started) return;
  hour += dt * TIME_SCALE / 3600;
  sunDirection(LAT, DAY, hour, sunDir); lightFromSun(); tide.setHour(hour);
  if (Math.abs(hour - envAt) > 0.25) { rebuildEnv(); envAt = hour; }
}
function frame(dt) {
  advanceClock(dt);
  stepSim(dt);
  logDist += boat.pos.distanceTo(lastPos) < 20 ? Math.hypot(boat.pos.x - lastPos.x, boat.pos.z - lastPos.z) : 0; lastPos.copy(boat.pos);
  ship.update(boat, { hoist: boat.hoist, brace: boat.brace, rudder: boat.rudder, sailDepth: boat.sail.depth, sailSide: boat.sail.side, flog: boat.sail.flog, draft: boat.sail.draft });
  const fwd = boat.forward(new THREE.Vector3());
  wake.step(dt, { pos: boat.pos, fwd: new THREE.Vector2(fwd.x, fwd.z).normalize(), vel: new THREE.Vector2(boat.vel.x, boat.vel.z), heave: boat.heave, sub: 1 });
  crew.update(simT, boat.rudder);
  boats?.update(dt, simT, camera.position);
  cam.update(dt, boat);
  ocean.update(camera);
  islands.update(camera.position);
  trees?.update(camera.position);
  if (sunDir.angleTo(lastLandSun) > 0.003) { shadows.renderLand(new THREE.Vector3(boat.pos.x, 0, boat.pos.z)); lastLandSun.copy(sunDir); }
  skyU.uCloudT.value = simT;
  shadows.renderShip(boat.pos.clone().setY(4));
  renderReflection();
  // the eye adapts: exposure rises as the light goes (about 4x by full night)
  const adapt = 1 + 3.2 * THREE.MathUtils.smoothstep(-sunDir.y, -0.04, 0.16);
  post.render(scene, camera, { exposure: EXPOSURE * adapt, t: simT, overlay: waterScene, thresh: 1.6 * adapt });
  hud.update({ boat, hour, wind, tide, dest, dt });
  checkArrival();
  // lamps: lit as the sun goes down
  const lampK = THREE.MathUtils.smoothstep(-sunDir.y, -0.07, 0.02);
  ship.setNight(lampK);
  if (ports) {
    let near = null, nd = 1e9;
    for (const l of ports.lanterns) { const d = l.distanceTo(boat.pos); if (d < nd) { nd = d; near = l; } }
    ports.setNight(lampK, near);
  }
  sound.update(dt, { speed: boat.speed, aw: boat.appWind.length(), gust: wind.gust(boat.pos.x, boat.pos.z, simT), roll: boat.heel,
    rollRate: boat.angV.dot(boat.forward(_camR.clone())), heave: boat.vel.y, flog: boat.sail.flog, force: boat.sail.force,
    landDir: nearestLand(), evening: sunDir.y < 0.14 && sunDir.y > -0.1 });
}

// Resolution follows the frame time: the 3D image is drawn at 60-100 % of the canvas and scaled up in the last pass
let rscale = 1, dtSum = 0, dtN = 0;
function setScale(s) {
  rscale = s;
  const w = Math.round(W * PR * s), h = Math.round(H * PR * s);
  post.setSize(w, h);
  ocean.uniforms.uRefr.value = post.refr.texture;
  rtRefl.setSize(Math.round(w * 0.5), Math.round(h * 0.5));
  ocean.uniforms.uReflTexel.value.set(1 / rtRefl.width, 1 / rtRefl.height);
}
let last = performance.now();
function loop(now) {
  const dt = Math.min((now - last) / 1000, 0.1); last = now;
  frame(dt);
  dtSum += dt; dtN++;
  if (dtSum > 2) {
    const avg = dtSum / dtN;
    if (avg > 0.021 && rscale > 0.61) setScale(Math.max(0.6, rscale - 0.1));
    else if (avg < 0.0135 && rscale < 0.99) setScale(Math.min(1, rscale + 0.1));
    dtSum = 0; dtN = 0;
  }
  requestAnimationFrame(loop);
}
// probes for checks and recording (tools/probe.py): state, settings, physics-only steps, fixed-time frames
window.__boat = boat;
window.__ports = ports;
window.__H = islands.height;
window.__renderer = renderer;
window.__state = () => ({ t: +simT.toFixed(2), pos: boat.pos.toArray().map((v) => +v.toFixed(2)), speed: +boat.speed.toFixed(2),
  heel: +(boat.heel * 57.3).toFixed(1), pitch: +(boat.pitch * 57.3).toFixed(1), heading: +(boat.heading * 57.3).toFixed(1),
  hoist: +boat.hoist.toFixed(2), brace: +(boat.brace * 57.3).toFixed(1), aoa: +(boat.sail.aoa * 57.3).toFixed(1), sailF: Math.round(boat.sail.force),
  mass: Math.round(boat.mass), aw: boat.appWind.toArray().map((v) => +v.toFixed(2)) });
window.__set = (o) => {
  if (o.hour !== undefined) { hour = o.hour; sunDirection(LAT, DAY, hour, sunDir); lightFromSun(); tide.setHour(hour); rebuildEnv(); envAt = hour; }
  if (o.cam) cam.set(o.cam);
  if (o.ctl) Object.assign(boat.ctl, o.ctl);
  if (o.trim !== undefined) input.trim = o.trim;
  if (o.place) boat.place(...o.place);
  if (o.hide) for (const k of o.hide) ({ trees: trees?.group, land: islands.group, ports: ports?.group, ship: ship.group, ocean: ocean.mesh, ropes: ship.ropeGroup })[k].visible = false;
  if (o.show) for (const k of o.show) ({ trees: trees?.group, land: islands.group, ports: ports?.group, ship: ship.group, ocean: ocean.mesh, ropes: ship.ropeGroup })[k].visible = true;
  if (o.seaK !== undefined) { boat.seaK = o.seaK; seaU.uSeaK.value = o.seaK; }
  if (o.wind !== undefined) wind.set(o.wind, wind.dir);
};
window.__sim = (sec, ctl) => {
  if (ctl) Object.assign(boat.ctl, ctl);
  const out = [];
  for (let i = 0; i < sec * 120; i++) {
    if (input.trim) boat.ctl.brace = autoTrim();
    simT += DT; boat.step(DT, simT);
    if (i % 1200 === 0) out.push(window.__state());
  }
  U.uTime.value = simT;
  out.push(window.__state());
  return out;
};
window.__renderAt = (f, fps) => {
  const target = f / fps;
  while (simT < target - 1e-6) frame(Math.min(1 / fps, target - simT));
  return window.__state();
};
window.__ready = true;
if (!RENDER) requestAnimationFrame(loop);
