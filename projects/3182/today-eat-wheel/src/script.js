const $ = (id) => document.getElementById(id);
const canvas = $("wheel");
const ctx = canvas.getContext("2d");
let rotation = 0;
let spinning = false;
let currentOptions = [];

const palette = [
  "#5B8FF9", "#61DDAA", "#65789B", "#F6BD16", "#7262fd",
  "#78D3F8", "#9661BC", "#F6903D", "#008685", "#F08BB4"
];

function getOptions() {
  return $("options").value
    .split(/\n+/)
    .map((x) => x.trim())
    .filter(Boolean)
    .slice(0, 20);
}

function drawWheel(options) {
  const n = options.length || 1;
  const cx = canvas.width / 2;
  const cy = canvas.height / 2;
  const r = canvas.width / 2 - 8;
  const step = (Math.PI * 2) / n;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(rotation);

  for (let i = 0; i < n; i++) {
    const start = i * step;
    const end = start + step;

    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, r, start, end);
    ctx.closePath();
    ctx.fillStyle = palette[i % palette.length];
    ctx.fill();

    ctx.save();
    ctx.rotate(start + step / 2);
    ctx.textAlign = "right";
    ctx.fillStyle = "#fff";
    ctx.font = "bold 18px Nunito Sans, sans-serif";
    const text = (options[i] || "吃饭").slice(0, 10);
    ctx.fillText(text, r - 18, 6);
    ctx.restore();
  }

  ctx.beginPath();
  ctx.arc(0, 0, 28, 0, Math.PI * 2);
  ctx.fillStyle = "#121826";
  ctx.fill();
  ctx.strokeStyle = "#7b8ba8";
  ctx.stroke();

  ctx.restore();
}

function pickResult(options) {
  const n = options.length;
  const step = (Math.PI * 2) / n;
  const normalized = ((Math.PI * 1.5 - rotation) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
  const idx = Math.floor(normalized / step) % n;
  return options[idx];
}

function spin() {
  if (spinning) return;
  const options = getOptions();
  if (options.length < 2) {
    alert("至少输入 2 个选项");
    return;
  }
  currentOptions = options;
  drawWheel(options);

  spinning = true;
  const speed = Number($("speed").value);
  const duration = 2200 + Math.random() * 1800;
  const start = performance.now();
  const base = speed * 0.01 + Math.random() * 0.01;

  function frame(now) {
    const t = (now - start) / duration;
    if (t >= 1) {
      spinning = false;
      const result = pickResult(options);
      $("result").textContent = `🍜 今天吃：${result}`;
      return;
    }
    const ease = 1 - Math.pow(1 - t, 3);
    rotation += (base * (1 - ease) + 0.005) * 8;
    drawWheel(options);
    requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
}

$("sampleBtn").addEventListener("click", () => {
  $("options").value = "黄焖鸡\n麻辣烫\n寿司\n兰州拉面\n沙拉\n汉堡";
  currentOptions = getOptions();
  drawWheel(currentOptions);
});

$("spinBtn").addEventListener("click", spin);
$("rerollBtn").addEventListener("click", spin);
$("copyBtn").addEventListener("click", async () => {
  const txt = $("result").textContent.trim();
  if (!txt || txt.includes("将在这里")) {
    alert("请先转盘");
    return;
  }
  await navigator.clipboard.writeText(txt);
  alert("结果已复制");
});

currentOptions = getOptions();
if (!currentOptions.length) currentOptions = ["黄焖鸡", "麻辣烫", "寿司", "兰州拉面"];
drawWheel(currentOptions);
