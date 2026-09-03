// 全站共用的小工具：导航、厂商图标、金额格式。没有构建步骤，直接引。

const PAGES = [
  ['index.html', '价格总表'],
  ['vendors.html', '按厂商看'],
  ['bench.html', '模型评测'],
  ['tools.html', '订阅与渠道'],
  ['promos.html', '活动与优惠'],
  ['free.html', '公益站'],
];

// 品牌色，用于图标底色；没列到的按名字算一个稳定的色相
const BRAND = {
  OpenAI: '#10a37f', Anthropic: '#d97757', Google: '#4285f4', DeepSeek: '#4d6bfe',
  xAI: '#111', Meta: '#0866ff', Mistral: '#fa520f', Cohere: '#39594d',
  Perplexity: '#20808d', MiniMax: '#f23f5d', OpenRouter: '#6467f2',
  Together: '#0f6fff', Fireworks: '#5b21b6', Groq: '#f55036', Cerebras: '#f4511e',
  'AWS Bedrock': '#ff9900', 'Azure OpenAI': '#0078d4', 'Azure AI': '#0078d4',
  Vercel: '#111', DeepInfra: '#3b82f6', Novita: '#7c3aed', Databricks: '#ff3621',
  'GitHub Copilot': '#24292f', 'GitHub Models': '#24292f', NVIDIA: '#76b900',
  '智谱 Z.ai': '#3859ff', '月之暗面 Kimi': '#16182f', 字节豆包: '#325ab4',
  阿里通义千问: '#615ced', 阿里云百炼: '#615ced', '阿里通义千问(国际)': '#615ced',
  百度文心: '#2932e1', 腾讯混元: '#0052d9', 阶跃星辰: '#0a5fff',
  Cursor: '#111', Claude: '#d97757', Kiro: '#8c4fff', Trae: '#ff2d55',
  Zed: '#084ccf', v0: '#111', Cline: '#3b82f6', 'Augment Code': '#111',
};

function brandColor(name) {
  if (BRAND[name]) return BRAND[name];
  let h = 0;
  for (const c of name) h = (h * 31 + c.codePointAt(0)) % 360;
  return `hsl(${h} 52% 45%)`;
}

// 图标就是首字母方块：不依赖外部图片，离线可用，不会 404
function logo(_icon, name) {
  const ch = (name.match(/[A-Za-z0-9\u4e00-\u9fa5]/) || ['·'])[0].toUpperCase();
  return `<div class="logo" style="--c:${brandColor(name)}">${ch}</div>`;
}

function money(v) {
  if (v == null) return '<span class="na">未公布</span>';
  if (v === 0) return '<span class="free">免费</span>';
  return '$' + (v < 0.01 ? v.toFixed(4) : +v.toFixed(2));
}

// 价格分档，用于给数字上色：越贵越红
function tier(v) {
  if (v == null) return '';
  if (v === 0) return 't0';
  if (v < 0.5) return 't1';
  if (v < 3) return 't2';
  if (v < 15) return 't3';
  return 't4';
}

function buildNav() {
  const here = location.pathname.split('/').pop() || 'index.html';
  const nav = document.querySelector('nav');
  if (!nav) return;
  nav.innerHTML = PAGES.map(([href, label]) =>
    `<a href="${href}"${href === here ? ' class="on"' : ''}>${label}</a>`).join('');
}
buildNav();
