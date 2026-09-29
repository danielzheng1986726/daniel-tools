/**
 * 项目类型预设
 * 每个预设定义：shotTypes、subjectConfig、sectionMeta、默认段落
 * 存入项目 JSON 后，app 完全从项目数据读取，不再依赖全局常量
 */

export const PROJECT_TYPES = {
  fashion_show: {
    id: 'fashion_show',
    label: 'AI 时装秀',
    icon: '👗',
    description: '多服装、多模特、完整叙事弧线的走秀影片',
    subjectLabel: '服装',
    subjectSlotLabel: '服装参考图',
    venueLabel: '秀场概念图',
    shotTypes: {
      A: { label: '空间',  color: 'bg-slate-700 text-slate-200',   tip: '纯环境镜头，无人脸，技术风险最低' },
      B: { label: '英雄',  color: 'bg-violet-800 text-violet-200', tip: '模特正/侧面展示，核心镜头' },
      C: { label: '特写',  color: 'bg-cyan-800 text-cyan-200',     tip: '面料/配饰/细节，小景深' },
      D: { label: '群走',  color: 'bg-amber-800 text-amber-200',   tip: '多模特同框，技术难度最高' },
      E: { label: '俯拍',  color: 'bg-emerald-800 text-emerald-200', tip: '高角度，展示整体造型结构' },
      F: { label: '呼吸',  color: 'bg-teal-800 text-teal-200',     tip: '段落间隔镜头，让观众视觉重置' },
    },
    defaultSections: ['opening', 'runway', 'finale'],
    sectionMeta: {
      opening: { label: '开场', accent: 'border-l-blue-500',   tag: 'bg-blue-900/60 text-blue-300' },
      runway:  { label: '走秀', accent: 'border-l-violet-500', tag: 'bg-violet-900/60 text-violet-300' },
      finale:  { label: '谢幕', accent: 'border-l-amber-500',  tag: 'bg-amber-900/60 text-amber-300' },
    },
    defaultSubjectCount: 10,
  },

  brand_film: {
    id: 'brand_film',
    label: '品牌短片',
    icon: '🎬',
    description: '15–45 秒品牌形象/产品展示短片，含叙事结构',
    subjectLabel: '产品',
    subjectSlotLabel: '产品参考图',
    venueLabel: '场景概念图',
    shotTypes: {
      A: { label: '开场',  color: 'bg-slate-700 text-slate-200',   tip: '品牌氛围建立，无产品出现' },
      B: { label: '展示',  color: 'bg-violet-800 text-violet-200', tip: '产品主体正面/侧面，核心镜头' },
      C: { label: '细节',  color: 'bg-cyan-800 text-cyan-200',     tip: '产品局部特写，材质/工艺/Logo' },
      D: { label: '场景',  color: 'bg-amber-800 text-amber-200',   tip: '产品在使用场景中出现' },
      E: { label: '俯拍',  color: 'bg-emerald-800 text-emerald-200', tip: '平铺/俯角，常见于时尚平面风格' },
      F: { label: '过渡',  color: 'bg-teal-800 text-teal-200',     tip: '转场/呼吸镜头，节奏调节' },
    },
    defaultSections: ['intro', 'showcase', 'outro'],
    sectionMeta: {
      intro:    { label: '引入', accent: 'border-l-blue-500',   tag: 'bg-blue-900/60 text-blue-300' },
      showcase: { label: '展示', accent: 'border-l-violet-500', tag: 'bg-violet-900/60 text-violet-300' },
      outro:    { label: '收尾', accent: 'border-l-amber-500',  tag: 'bg-amber-900/60 text-amber-300' },
    },
    defaultSubjectCount: 5,
  },

  ecommerce: {
    id: 'ecommerce',
    label: '电商展示',
    icon: '🛍️',
    description: '单品/多SKU快节奏展示，主打转化',
    subjectLabel: '单品',
    subjectSlotLabel: '商品参考图',
    venueLabel: '背景/场景图',
    shotTypes: {
      A: { label: '吸睛',  color: 'bg-rose-800 text-rose-200',    tip: '封面级开场，快速建立视觉焦点' },
      B: { label: '正面',  color: 'bg-violet-800 text-violet-200', tip: '商品正面完整展示' },
      C: { label: '细节',  color: 'bg-cyan-800 text-cyan-200',     tip: '面料/做工/尺码标等细节特写' },
      D: { label: '穿搭',  color: 'bg-amber-800 text-amber-200',   tip: '模特上身效果，展示穿着感' },
      E: { label: '氛围',  color: 'bg-emerald-800 text-emerald-200', tip: '生活方式场景，软性种草' },
      F: { label: '促单',  color: 'bg-pink-800 text-pink-200',     tip: '价格/促销信息引导，结尾行动帧' },
    },
    defaultSections: ['hook', 'display', 'cta'],
    sectionMeta: {
      hook:    { label: '吸睛', accent: 'border-l-rose-500',   tag: 'bg-rose-900/60 text-rose-300' },
      display: { label: '展示', accent: 'border-l-violet-500', tag: 'bg-violet-900/60 text-violet-300' },
      cta:     { label: '行动', accent: 'border-l-pink-500',   tag: 'bg-pink-900/60 text-pink-300' },
    },
    defaultSubjectCount: 3,
  },

  campaign: {
    id: 'campaign',
    label: '活动宣传',
    icon: '🎪',
    description: '活动/发布会/节日营销类宣传片，场景驱动',
    subjectLabel: '素材',
    subjectSlotLabel: '品牌素材',
    venueLabel: '主视觉/KV图',
    shotTypes: {
      A: { label: '氛围',  color: 'bg-slate-700 text-slate-200',   tip: '场景/空间建立，无特定主角' },
      B: { label: '人物',  color: 'bg-violet-800 text-violet-200', tip: '人物出场/展示，情感连接' },
      C: { label: '特写',  color: 'bg-cyan-800 text-cyan-200',     tip: '物件/符号/表情细节' },
      D: { label: '全景',  color: 'bg-amber-800 text-amber-200',   tip: '活动现场全貌，制造规模感' },
      E: { label: '高潮',  color: 'bg-rose-800 text-rose-200',     tip: '情绪顶点，最强视觉冲击' },
      F: { label: '收尾',  color: 'bg-teal-800 text-teal-200',     tip: '品牌露出/Slogan/余韵' },
    },
    defaultSections: ['buildup', 'climax', 'brand'],
    sectionMeta: {
      buildup: { label: '铺垫', accent: 'border-l-blue-500',   tag: 'bg-blue-900/60 text-blue-300' },
      climax:  { label: '高潮', accent: 'border-l-rose-500',   tag: 'bg-rose-900/60 text-rose-300' },
      brand:   { label: '收尾', accent: 'border-l-amber-500',  tag: 'bg-amber-900/60 text-amber-300' },
    },
    defaultSubjectCount: 6,
  },
};

/** 从 projectType id 取预设，找不到返回 fashion_show */
export function getPreset(typeId) {
  return PROJECT_TYPES[typeId] || PROJECT_TYPES.fashion_show;
}
