/**
 * Brief JSON Schema
 * ─────────────────────────────────────────────────────────────────────
 * 这是 Claude 对话 → App 的"翻译接口"。
 *
 * 工作流程：
 *   1. 在 Claude 里沟通项目需求，形成分镜方向
 *   2. 让 Claude 输出符合此格式的 JSON（直接粘贴下方 PROMPT）
 *   3. 在 App 里点「导入 Brief」，粘贴 JSON → 自动生成分镜脚本
 *   4. 在 App 里可视化编辑、上传素材、拖拽调整顺序
 *   5. 导出客户版 PDF 或内部完整版
 *
 * 对 Claude 的提示词（在对话末尾使用）：
 * ─────────────────────────────────────────────────────────────────────
 * 「请根据我们的讨论，输出一份符合以下结构的 JSON，我会导入到我的
 *   分镜脚本管理工具里：
 *
 *   {
 *     "project": { "name", "type", "client", "totalDuration", "colorArc", "sections": [] },
 *     "costumes": [ { "id": 1, "name": "...", "keywords": [] } ],
 *     "shots": [
 *       {
 *         "id": "s01", "section": "opening|runway|finale",
 *         "title": "", "types": ["A"|"B"|"C"|"D"|"E"|"F"],
 *         "duration": "4s", "desc": "", "costumes": [],
 *         "model": "", "camera": "", "cameraTip": "",
 *         "subshots": [], "prompt": "", "notes": ""
 *       }
 *     ]
 *   }
 *
 *   镜头类型说明：A=空间, B=英雄, C=特写, D=群走, E=俯拍, F=呼吸
 *   只输出 JSON，不要其他文字。」
 * ─────────────────────────────────────────────────────────────────────
 */

export const BRIEF_SCHEMA_VERSION = "1.0";

// 项目类型预设（用于新建项目时的模板选择）
export const PROJECT_TYPES = {
  fashion_show: {
    label: "AI 时装秀",
    description: "多镜头走秀，含空间呼吸结构",
    sections: ["opening", "runway", "finale"],
    defaultShotTypes: ["A", "B", "F"],
  },
  brand_film: {
    label: "品牌短片",
    description: "10-45秒产品/品牌宣传片",
    sections: ["intro", "product", "outro"],
    defaultShotTypes: ["B", "C", "A"],
  },
  social_content: {
    label: "社媒内容",
    description: "15秒竖版社媒短片",
    sections: ["main"],
    defaultShotTypes: ["B", "C"],
  },
  event_recap: {
    label: "活动回顾",
    description: "多镜头活动纪录片",
    sections: ["opening", "main", "closing"],
    defaultShotTypes: ["A", "B", "D", "C"],
  },
};

// 验证导入的 Brief JSON 结构
export function validateBrief(json) {
  const errors = [];

  if (!json.project) errors.push("缺少 project 字段");
  if (!json.project?.name) errors.push("缺少 project.name");
  if (!Array.isArray(json.shots)) errors.push("shots 必须是数组");
  if (!Array.isArray(json.costumes)) errors.push("costumes 必须是数组");

  if (json.shots) {
    json.shots.forEach((shot, i) => {
      if (!shot.id) errors.push(`shots[${i}] 缺少 id`);
      if (!shot.section) errors.push(`shots[${i}] 缺少 section`);
      if (!shot.title) errors.push(`shots[${i}] 缺少 title`);
    });
  }

  return { valid: errors.length === 0, errors };
}

// 将导入的 Brief JSON 转换为 App 内部数据格式
export function parseBrief(json) {
  const { valid, errors } = validateBrief(json);
  if (!valid) throw new Error(`Brief 格式错误：\n${errors.join("\n")}`);

  // 构建服装 meta 信息（从 brief 或使用默认值）
  const costumeMeta = {};
  (json.costumes || []).forEach(c => {
    costumeMeta[c.id] = { name: c.name, keywords: c.keywords || [] };
  });

  // 标准化镜头数据，补全缺失字段
  const shots = json.shots.map((shot, idx) => ({
    id: shot.id || `s${String(idx + 1).padStart(2, "0")}`,
    section: shot.section,
    title: shot.title,
    types: shot.types || ["B"],
    duration: shot.duration || "4s",
    desc: shot.desc || "",
    costumes: shot.costumes || [],
    model: shot.model || "",
    camera: shot.camera || "",
    cameraTip: shot.cameraTip || "",
    cameraRefs: [], // 导入时为空，由用户在 App 里上传
    subshots: shot.subshots || [],
    prompt: shot.prompt || "",
    notes: shot.notes || "",
  }));

  return {
    project: {
      name: json.project.name,
      type: json.project.type || "fashion_show",
      client: json.project.client || "",
      totalDuration: json.project.totalDuration || "",
      colorArc: json.project.colorArc || "",
      sections: json.project.sections || ["opening", "runway", "finale"],
    },
    costumeMeta,
    shots,
  };
}

// 示例 Brief（用于演示和测试）
export const EXAMPLE_BRIEF = {
  "project": {
    "name": "示例项目",
    "type": "brand_film",
    "client": "品牌名称",
    "totalDuration": "30s",
    "colorArc": "暗→亮，产品揭示结构",
    "sections": ["intro", "product", "outro"]
  },
  "costumes": [
    { "id": 1, "name": "主推款A", "keywords": ["关键词1", "关键词2"] }
  ],
  "shots": [
    {
      "id": "s01",
      "section": "intro",
      "title": "开场空镜",
      "types": ["A"],
      "duration": "5s",
      "desc": "简洁的开场画面，建立品牌基调",
      "costumes": [],
      "model": "无人",
      "camera": "从远到近的推镜",
      "cameraTip": "保持稳定，避免抖动",
      "subshots": ["远景建立环境 (~2s)", "推进到产品特写 (~3s)"],
      "prompt": "在这里填写 AI 生成提示词",
      "notes": "内部备注：技术风险低"
    }
  ]
};
