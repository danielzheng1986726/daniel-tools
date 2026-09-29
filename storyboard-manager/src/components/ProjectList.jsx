import { useState, useEffect } from 'react';
import { Plus, FolderOpen, Trash2, FileJson, Clock, User, ChevronRight } from 'lucide-react';
import { getAllProjects, saveProject, deleteProject, newProject } from '../db.js';
import { PROJECT_TYPES } from '../projectTypes.js';
import symbioticData from '../data/symbiotic-future.json';

export default function ProjectList({ onOpen }) {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState('list'); // 'list' | 'choose-type' | 'import'
  const [importText, setImportText] = useState('');
  const [importError, setImportError] = useState('');

  useEffect(() => {
    getAllProjects().then(p => { setProjects(p); setLoading(false); });
  }, []);

  async function createFromType(typeId) {
    const p = newProject(typeId, {
      name: PROJECT_TYPES[typeId].label + ' · ' + new Date().toLocaleDateString('zh-CN'),
    });
    const saved = await saveProject(p);
    setProjects(prev => [saved, ...prev]);
    onOpen(saved.id);
  }

  async function loadDemo() {
    const p = newProject('fashion_show', {
      ...symbioticData,
      id: crypto.randomUUID(),
      projectType: 'fashion_show',
      createdAt: new Date().toISOString(),
      subjectCount: symbioticData.costumeCount || 10,
      assets: {
        venue: null,
        subjects: Array(symbioticData.costumeCount || 10).fill(null),
      },
      shots: (symbioticData.shots || []).map(s => ({
        referenceMedia: [],
        ...s,
        subjects: s.costumes || [],
      })),
    });
    const saved = await saveProject(p);
    setProjects(prev => [saved, ...prev]);
    onOpen(saved.id);
  }

  async function handleImport() {
    setImportError('');
    try {
      const data = JSON.parse(importText);
      if (!data.shots) throw new Error('缺少 shots 字段，请检查 JSON 格式');
      const typeId = data.projectType || 'fashion_show';
      const subjectCount = data.subjectCount || data.costumeCount || 10;
      const p = newProject(typeId, {
        ...data,
        id: crypto.randomUUID(),
        createdAt: new Date().toISOString(),
        subjectCount,
        assets: data.assets || {
          venue: null,
          subjects: Array(subjectCount).fill(null),
        },
        shots: (data.shots || []).map(s => ({
          referenceMedia: [],
          ...s,
          subjects: s.subjects || s.costumes || [],
        })),
      });
      const saved = await saveProject(p);
      setProjects(prev => [saved, ...prev]);
      setStep('list');
      setImportText('');
      onOpen(saved.id);
    } catch (e) {
      setImportError(e.message);
    }
  }

  async function handleDelete(id, e) {
    e.stopPropagation();
    if (!confirm('确认删除此项目？此操作不可撤销。')) return;
    await deleteProject(id);
    setProjects(prev => prev.filter(p => p.id !== id));
  }

  function fmt(iso) {
    return new Date(iso).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  // ── Step: choose project type ──
  if (step === 'choose-type') {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100" style={{ fontFamily: "'Noto Sans SC', -apple-system, sans-serif" }}>
        <div className="max-w-2xl mx-auto px-6 py-16">
          <button onClick={() => setStep('list')} className="text-zinc-600 hover:text-zinc-400 text-sm mb-8 flex items-center gap-1">
            ← 返回
          </button>
          <h2 className="text-xl font-bold text-zinc-100 mb-2">选择项目类型</h2>
          <p className="text-sm text-zinc-500 mb-8">每种类型有独立的镜头标签、段落结构和素材字段配置，可在创建后继续调整。</p>
          <div className="space-y-3">
            {Object.values(PROJECT_TYPES).map(type => (
              <button
                key={type.id}
                onClick={() => createFromType(type.id)}
                className="w-full flex items-center gap-4 rounded-2xl border border-zinc-800 bg-zinc-900/50 hover:bg-zinc-900 hover:border-zinc-700 p-5 text-left transition-all group">
                <span className="text-2xl">{type.icon}</span>
                <div className="flex-1">
                  <h3 className="text-sm font-semibold text-zinc-100 mb-0.5">{type.label}</h3>
                  <p className="text-xs text-zinc-500">{type.description}</p>
                  <div className="flex gap-1.5 mt-2 flex-wrap">
                    {Object.values(type.shotTypes).map(t => (
                      <span key={t.label} className={`text-[10px] px-1.5 py-0.5 rounded ${t.color}`}>{t.label}</span>
                    ))}
                  </div>
                </div>
                <ChevronRight size={16} className="text-zinc-600 group-hover:text-zinc-400 shrink-0" />
              </button>
            ))}
          </div>
          <div className="mt-6 rounded-xl border border-dashed border-zinc-800 p-4">
            <p className="text-xs text-zinc-600 mb-3">或者，直接加载「奇幻世界 · AI 时装秀」演示项目</p>
            <button onClick={loadDemo}
              className="text-xs text-zinc-500 hover:text-zinc-300 border border-zinc-800 hover:border-zinc-600 px-3 py-1.5 rounded-lg transition-colors">
              加载演示项目
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Step: import JSON ──
  if (step === 'import') {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100" style={{ fontFamily: "'Noto Sans SC', -apple-system, sans-serif" }}>
        <div className="max-w-2xl mx-auto px-6 py-16">
          <button onClick={() => setStep('list')} className="text-zinc-600 hover:text-zinc-400 text-sm mb-8 flex items-center gap-1">
            ← 返回
          </button>
          <h2 className="text-xl font-bold text-zinc-100 mb-2">从 JSON 导入项目</h2>
          <p className="text-sm text-zinc-500 mb-2 leading-relaxed">
            在 Claude 里把项目需求沟通好后，让 Claude 输出项目 JSON，粘贴到下方即可创建项目。
          </p>
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 mb-4">
            <p className="text-[11px] text-zinc-600 mb-1 font-medium">最小必填字段</p>
            <pre className="text-[10px] text-zinc-500 leading-relaxed overflow-x-auto">{`{
  "name": "项目名称",
  "projectType": "brand_film",   // fashion_show / brand_film / ecommerce / campaign
  "client": "客户名",
  "subjectCount": 3,             // 产品/服装/单品数量
  "shots": [
    {
      "id": "s01", "section": "intro",
      "title": "品牌开场", "types": ["A"],
      "duration": "3s", "desc": "画面描述",
      "subjects": [], "camera": "运镜说明",
      "subshots": [], "prompt": "提示词", "notes": ""
    }
  ]
}`}</pre>
          </div>
          <textarea
            value={importText}
            onChange={e => setImportText(e.target.value)}
            placeholder="粘贴 Claude 输出的 JSON..."
            className="w-full h-48 bg-zinc-800 text-zinc-200 text-xs font-mono rounded-xl p-3 border border-zinc-700 focus:border-zinc-500 outline-none resize-y"
          />
          {importError && <p className="text-xs text-red-400 mt-2">⚠ {importError}</p>}
          <button
            onClick={handleImport}
            className="mt-3 px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors">
            导入并打开
          </button>
        </div>
      </div>
    );
  }

  // ── Main list ──
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100" style={{ fontFamily: "'Noto Sans SC', -apple-system, sans-serif" }}>
      <div className="max-w-2xl mx-auto px-6 py-16">
        <div className="mb-10">
          <h1 className="text-2xl font-bold text-zinc-100 mb-1">Storyboard Studio</h1>
          <p className="text-sm text-zinc-500">AI 视频项目分镜管理系统</p>
        </div>
        <div className="flex gap-3 mb-8">
          <button onClick={() => setStep('choose-type')}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors">
            <Plus size={15} /> 新建项目
          </button>
          <button onClick={() => setStep('import')}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm font-medium border border-zinc-700 transition-colors">
            <FileJson size={15} /> 从 JSON 导入
          </button>
        </div>

        {loading ? (
          <p className="text-zinc-600 text-sm">加载中...</p>
        ) : projects.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-zinc-800 p-12 text-center">
            <p className="text-zinc-600 text-sm mb-1">暂无项目</p>
            <p className="text-zinc-700 text-xs">新建项目，或从 JSON 导入</p>
          </div>
        ) : (
          <div className="space-y-3">
            {projects.map(p => {
              const typeInfo = PROJECT_TYPES[p.projectType];
              return (
                <div key={p.id}
                  onClick={() => onOpen(p.id)}
                  className="group flex items-center gap-4 rounded-2xl border border-zinc-800 bg-zinc-900/50 hover:bg-zinc-900 hover:border-zinc-700 p-4 cursor-pointer transition-all">
                  <div className="w-10 h-10 rounded-xl bg-zinc-800 border border-zinc-700/60 flex items-center justify-center shrink-0 text-xl">
                    {typeInfo?.icon || '📋'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-zinc-100 truncate">{p.name}</h3>
                    <div className="flex items-center gap-3 mt-0.5">
                      {typeInfo && <span className="text-[10px] text-zinc-600">{typeInfo.label}</span>}
                      {p.client && <span className="flex items-center gap-1 text-xs text-zinc-500"><User size={10} />{p.client}</span>}
                      <span className="flex items-center gap-1 text-xs text-zinc-600"><Clock size={10} />{fmt(p.updatedAt)}</span>
                      <span className="text-xs text-zinc-700">{p.shots?.length || 0} 镜头</span>
                    </div>
                  </div>
                  <button onClick={e => handleDelete(p.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-2 rounded-lg hover:bg-red-950 text-zinc-600 hover:text-red-400 transition-all">
                    <Trash2 size={14} />
                  </button>
                </div>
              );
            })}
          </div>
        )}
        <div className="mt-16 text-center text-xs text-zinc-800">Storyboard Studio · 数据存储在本地浏览器</div>
      </div>
    </div>
  );
}
