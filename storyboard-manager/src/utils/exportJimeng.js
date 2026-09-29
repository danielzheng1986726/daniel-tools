/**
 * 即梦（Seedance）脚本导出
 * 产出纯文本格式，可复制粘贴至即梦 Agent 聊天窗口
 * 支持整片模式 + 单镜头模式，含一致性锚点块
 */

/**
 * 从项目数据提取一致性锚点（5-8 个贯穿全片的关键描述）
 * 优先从 description 和首镜头的 prompt 中归纳
 */
function extractAnchors(project) {
  const shots = project.shots || [];
  const desc = project.description || '';
  const anchors = [];

  // 从项目描述提取风格关键词
  if (desc) {
    const styleWords = desc.match(/[^，。；\s]{2,}/g) || [];
    if (styleWords.length > 0) {
      anchors.push(`· 风格：${desc.slice(0, 80)}${desc.length > 80 ? '…' : ''}`);
    }
  }

  // 从首个有内容的 prompt 提取主体/光影/色彩等高频词
  const firstPrompt = (shots[0]?.promptZh || shots[0]?.prompt || shots[0]?.desc || '').slice(0, 300);
  if (firstPrompt) {
    const keywords = ['chiaroscuro', '明暗', '暖色', 'golden', '琥珀', '暗调', 'cinematic', '浅景深', 'bokeh', '9:16'];
    const found = keywords.filter(k => firstPrompt.toLowerCase().includes(k.toLowerCase()));
    if (found.length > 0) {
      anchors.push(`· 光影/色彩：${found.join('、')}`);
    }
  }

  if (anchors.length === 0) anchors.push('· 请在下方镜头中保持一致的主体、色彩与光影风格');
  return anchors;
}

/**
 * 获取镜头的 prompt 文本（中文优先，英文备用）
 * 中文：promptZh 优先，空则用 desc
 * 英文：prompt 优先，空则回退到 desc（仍可作参考）
 */
function getShotPrompt(shot, lang) {
  if (lang === 'zh') {
    return (shot.promptZh || shot.desc || '').trim();
  }
  const en = (shot.prompt || '').trim();
  if (en) return en;
  // 英文暂无时，仍输出 desc 供参考（标注为中文）
  return (shot.desc || '').trim() ? `(英文暂缺，以下为中文描述供参考)\n${(shot.desc || '').trim()}` : '';
}

/**
 * 解析 duration 字符串（如 "3s"）为秒数
 */
function parseDuration(dur) {
  if (!dur) return 0;
  const m = String(dur).match(/(\d+)/);
  return m ? parseInt(m[1], 10) : 0;
}

/**
 * 生成时间码，如 [00:00-00:03]
 */
function toTimecode(startSec, endSec) {
  const fmt = s => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  };
  return `[${fmt(startSec)}-${fmt(endSec)}]`;
}

/**
 * 生成单镜头即梦格式文本（中英文均可）
 */
function formatShot(shot, startSec, lang, shotIndex) {
  const dur = parseDuration(shot.duration) || 3;
  const endSec = startSec + dur;
  const timecode = toTimecode(startSec, endSec);
  const prompt = getShotPrompt(shot, lang);
  const camera = (shot.camera || '').trim();
  const cameraTip = (shot.cameraTip || '').trim();
  const cameraLine = [camera, cameraTip].filter(Boolean).join(' | ') || '—';
  const subshots = (shot.subshots || []);
  const model = (shot.model || '').trim();

  let out = `───────────────────────────────────────\n`;
  out += `${timecode} #${shotIndex} ${shot.title}（${cameraLine}）\n\n`;
  if (prompt) {
    out += `${prompt}\n\n`;
  } else if (lang === 'zh') {
    out += `（无画面描述，请补充 promptZh 或 desc）\n\n`;
  } else {
    out += `（英文暂缺）\n\n`;
  }
  if (model) {
    out += `模特/人物：${model}\n\n`;
  }
  if (subshots.length > 0) {
    out += `节拍：\n`;
    subshots.forEach((ss, i) => {
      out += `  ${i + 1}. ${ss}\n`;
    });
  }
  return out;
}

/**
 * 生成整片模式即梦脚本（主用中文）
 * @returns { { text: string, charCount: number } }
 */
export function exportJimengFull(project, options = {}) {
  const lang = options.lang || 'zh';
  const shots = project.shots || [];
  const anchors = extractAnchors(project);
  const totalSec = shots.reduce((a, s) => a + parseDuration(s.duration), 0);

  let out = `═══════════════════════════════════════\n`;
  out += `${project.name || '未命名项目'} — AI视频分镜脚本（即梦）\n`;
  out += `═══════════════════════════════════════\n\n`;
  out += `【风格】${project.description || '（请补充项目描述）'}\n`;
  out += `【时长】${totalSec}秒（${shots.length}镜头）\n`;
  out += `【画面】9:16 竖屏，1080p\n\n`;
  out += `【一致性锚点 — 以下描述贯穿全片】\n`;
  out += anchors.join('\n') + '\n\n';

  let startSec = 0;
  shots.forEach((shot, i) => {
    out += formatShot(shot, startSec, lang, i + 1);
    startSec += parseDuration(shot.duration) || 3;
  });

  out += `───────────────────────────────────────\n`;
  out += `（复制上方全部内容粘贴至即梦 Agent 聊天窗口）\n`;

  return { text: out, charCount: out.length };
}

/**
 * 生成单镜头模式：每个镜头独立成块，便于逐条复制
 * @returns { { text: string, charCount: number, perShot: string[] } }
 */
export function exportJimengPerShot(project, options = {}) {
  const lang = options.lang || 'zh';
  const shots = project.shots || [];
  const anchors = extractAnchors(project);
  const header = `═══════════════════════════════════════\n`
    + `${project.name || '未命名项目'} — 单镜头 Prompt（即梦）\n`
    + `═══════════════════════════════════════\n\n`
    + `【一致性锚点】\n${anchors.join('\n')}\n\n`;

  const perShot = [];
  let startSec = 0;
  shots.forEach((shot, i) => {
    const block = formatShot(shot, startSec, lang, i + 1);
    perShot.push(block);
    startSec += parseDuration(shot.duration) || 3;
  });

  const fullText = header + perShot.join('\n');
  return { text: fullText, charCount: fullText.length, perShot };
}
