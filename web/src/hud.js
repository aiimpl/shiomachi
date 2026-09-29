// On-screen text: compass strip (heading, where the wind comes from, the destination), speed in knots, the apparent
// wind dial, wind / time / tide, messages, and the title card. Directions: +x east, -z north.
const DIRS = ['北', '北東', '東', '南東', '南', '南西', '西', '北西'];
const DIRS16 = ['北', '北北東', '北東', '東北東', '東', '東南東', '南東', '南南東', '南', '南南西', '南西', '西南西', '西', '西北西', '北西', '北北西'];
const deg = (r) => ((r * 57.29578) % 360 + 360) % 360;
// bearing (clockwise from north) of a vector in world xz
export const bearing = (dx, dz) => deg(Math.atan2(dx, -dz));

export function makeHUD() {
  const $ = (id) => document.getElementById(id);
  const strip = $('strip');
  // build the compass ticks once: every 15 degrees, labels every 45
  for (let a = -360; a <= 720; a += 15) {
    const t = document.createElement('i');
    t.className = a % 45 === 0 ? 'lab' : 'tick';
    t.style.left = `${a * 4}px`;
    if (a % 45 === 0) t.textContent = DIRS[((a / 45) % 8 + 8) % 8];
    strip.appendChild(t);
  }
  const windMark = $('windmark'), destMark = $('destmark');
  let msgT = 0;
  return {
    message(text, sec = 6) { $('msg').textContent = text; $('msg').classList.add('on'); msgT = sec; },
    update({ boat, hour, wind, tide, dest, dt }) {
      const h = Math.floor(hour), m = Math.floor((hour - h) * 60);
      $('time').textContent = `${h}時${String(m).padStart(2, '0')}分`;
      $('spd').textContent = (Math.max(boat.speed, 0) * 1.9438).toFixed(1);
      const hd = bearing(Math.sin(boat.heading), Math.cos(boat.heading));     // forward is (sin h, cos h) in xz
      strip.style.transform = `translateX(${-hd * 4}px)`;
      const wv = wind.uniforms.uWind.value;
      const from = bearing(-wv.x, -wv.y);
      const rel = (a) => ((a - hd + 540) % 360) - 180;
      windMark.style.left = `${rel(from) * 4 + 300}px`;
      windMark.style.opacity = Math.abs(rel(from)) < 72 ? 1 : 0;
      $('wind').textContent = `${DIRS16[Math.round(from / 22.5) % 16]}の風 ${wind.speed.toFixed(0)}m`;
      if (dest) {
        const dx = dest.x - boat.pos.x, dz = dest.z - boat.pos.z, d = Math.hypot(dx, dz);
        const b = bearing(dx, dz);
        destMark.style.left = `${Math.max(-290, Math.min(290, rel(b) * 4)) + 300}px`;
        $('dest').textContent = `${dest.name}まで ${(d / 1000).toFixed(1)}km`;
      }
      const tv = tide.uniforms.uTide.value;
      $('tide').textContent = Math.abs(tv) < 0.2 ? '潮どまり' : `${tv > 0 ? '上げ潮' : '下げ潮'}（${tv > 0 ? '東' : '西'}へ流れる）`;
      // apparent wind on the dial: relative to the bow, pointing where it blows
      const aw = boat.appWind;
      const awFrom = bearing(-aw.x, -aw.y);
      $('awarrow').style.transform = `rotate(${(rel(awFrom) + 180).toFixed(1)}deg)`;
      $('trim').textContent = boat.ctl.trimAuto ? '船頭まかせ' : '手で帆を合わせる';
      $('anchor').style.display = boat.ctl.anchor ? 'block' : 'none';
      if (msgT > 0) { msgT -= dt; if (msgT <= 0) $('msg').classList.remove('on'); }
    },
  };
}
