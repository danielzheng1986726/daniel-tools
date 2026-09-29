/**
 * constants.js
 * 只保留与具体项目类型无关的通用工具函数。
 * 镜头类型标签（shotTypes）已移入 projectTypes.js，
 * 按项目类型各自配置，不再全局硬编码。
 */

export const SUBJECT_STYLES = [
  { border: 'border-rose-600/60',    text: 'text-rose-300',    bg: 'bg-rose-900/40' },
  { border: 'border-sky-600/60',     text: 'text-sky-300',     bg: 'bg-sky-900/40' },
  { border: 'border-lime-600/60',    text: 'text-lime-300',    bg: 'bg-lime-900/40' },
  { border: 'border-fuchsia-600/60', text: 'text-fuchsia-300', bg: 'bg-fuchsia-900/40' },
  { border: 'border-teal-600/60',    text: 'text-teal-300',    bg: 'bg-teal-900/40' },
  { border: 'border-orange-600/60',  text: 'text-orange-300',  bg: 'bg-orange-900/40' },
  { border: 'border-indigo-600/60',  text: 'text-indigo-300',  bg: 'bg-indigo-900/40' },
  { border: 'border-pink-600/60',    text: 'text-pink-300',    bg: 'bg-pink-900/40' },
  { border: 'border-emerald-600/60', text: 'text-emerald-300', bg: 'bg-emerald-900/40' },
  { border: 'border-yellow-600/60',  text: 'text-yellow-300',  bg: 'bg-yellow-900/40' },
];

/** 服装/产品过时关键词检测（时装秀专用，其他项目类型可忽略此函数） */
const COSTUME_META = {
  1:  { keywords: ['粗花呢','蕾丝贴花','旗袍','tweed','lace','qipao'] },
  2:  { keywords: ['蜜桃','挂脖','连体衣','peach','halter'] },
  3:  { keywords: ['锦缎','羽毛帽','提花面料','brocade','jacquard','pink suit'] },
  4:  { keywords: ['亮黄','流苏','fringe','tassel','yellow'] },
  5:  { keywords: ['斗篷','皮短裤','雕塑帽','feather cape','cloak'] },
  6:  { keywords: ['天蓝','不对称','单肩','pleated','asymmetric'] },
  7:  { keywords: ['酒红','皮革','crop top','羽毛裙','leather','burgundy'] },
  8:  { keywords: ['鸵鸟毛','小麦色鸵鸟','ostrich'] },
  9:  { keywords: ['巨型蓬裙','彩色羽毛','多彩蓬裙','champagne','multicolor'] },
  10: { keywords: ['淡粉提花','大蓬裙','花冠','ball gown','floral crown'] },
};

export function detectStale(shot) {
  const cur = new Set(shot.subjects || shot.costumes || []);
  const text = [shot.desc, shot.promptZh, shot.prompt, shot.notes, ...(shot.subshots || [])].join(' ').toLowerCase();
  const stale = [];
  for (let n = 1; n <= 10; n++) {
    if (cur.has(n)) continue;
    const m = COSTUME_META[n];
    if (m && m.keywords.some(kw => text.includes(kw.toLowerCase()))) stale.push(n);
  }
  return stale;
}

export function newShotId() {
  return 's' + Math.random().toString(36).slice(2, 7);
}
