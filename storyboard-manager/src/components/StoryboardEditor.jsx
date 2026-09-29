import { useState, useEffect, useCallback } from 'react';
import { ArrowLeft, Eye, EyeOff, Download, Plus, RefreshCw, FileJson, Printer, Copy } from 'lucide-react';
import { getProject, saveProject } from '../db.js';
import { newShotId } from '../constants.js';
import { getPreset } from '../projectTypes.js';
import AssetLibrary from './AssetLibrary.jsx';
import ShotList from './ShotList.jsx';
import ClientView from './ClientView.jsx';
import { exportJimengFull, exportJimengPerShot } from '../utils/exportJimeng.js';

function SubjectSummary({ shots, assets, subjectCount, subjectLabel }) {
  const subjectAssets = assets.subjects || assets.costumes || [];
  const usage = {};
  for (let n = 1; n <= subjectCount; n++) usage[n] = [];
  shots.forEach(s => (s.subjects || s.costumes || []).forEach(n => { if (usage[n]) usage[n].push(s.title); }));
  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4">
      <h3 className="text-xs font-semibold text-zinc-300 mb-3 uppercase tracking-wider">{subjectLabel}出场总览</h3>
      <div className="space-y-2">
        {Object.entries(usage).map(([num, app]) => {
          const n = parseInt(num);
          const th = subjectAssets[n - 1]?.url;
          return (
            <div key={num} className="flex items-center gap-2.5">
              {th
                ? <img src={th} className="w-8 h-8 rounded-md object-cover border border-zinc-700" alt="" />
                : <div className="w-8 h-8 rounded-md border border-dashed border-zinc-700 bg-zinc-800 flex items-center justify-center text-[10px] text-zinc-600">{n}</div>
              }
              <span className="text-[11px] text-zinc-400 w-8 shrink-0">#{n}</span>
              <div className="flex-1 h-px bg-zinc-800" />
              {app.length > 0
                ? <span className="text-[10px] text-zinc-500 text-right">{app.join(' · ')}</span>
                : <span className="text-[10px] text-red-400/60">⚠ 未分配</span>
              }
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ExportMenu({ project, onClose, onJimengExport }) {
  function exportJSON() {
    const blob = new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(project.name || 'project').replace(/\s+/g, '-')}-storyboard.json`;
    a.click();
    URL.revokeObjectURL(url);
    onClose();
  }
  function printClient() { window.print(); onClose(); }
  function openJimeng() {
    onJimengExport?.();
    onClose();
  }
  return (
    <div className="absolute right-0 top-10 z-50 w-52 rounded-xl border border-zinc-700 bg-zinc-900 shadow-xl overflow-hidden">
      <div className="p-1">
        <button onClick={exportJSON} className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 transition-colors">
          <FileJson size={14} className="text-zinc-500" /> 导出 JSON 备份
        </button>
        <button onClick={openJimeng} className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 transition-colors">
          <Copy size={14} className="text-zinc-500" /> 导出即梦脚本
        </button>
        <button onClick={printClient} className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 transition-colors">
          <Printer size={14} className="text-zinc-500" /> 打印 / 导出 PDF
        </button>
      </div>
      <div className="px-3 pb-2">
        <p className="text-[10px] text-zinc-700 leading-relaxed">PDF：切换到客户视图后打印，浏览器自动生成</p>
      </div>
    </div>
  );
}

function JimengExportModal({ project, onClose }) {
  const [mode, setMode] = useState('full'); // 'full' | 'perShot'
  const [lang, setLang] = useState('zh');
  const result = mode === 'full'
    ? exportJimengFull(project, { lang })
    : exportJimengPerShot(project, { lang });
  const LIMIT = 20000;

  async function copyToClipboard() {
    try {
      await navigator.clipboard.writeText(result.text);
      onClose();
    } catch (e) {
      console.warn('Clipboard failed', e);
    }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70" onClick={onClose}>
      <div className="w-full max-w-2xl max-h-[85vh] rounded-2xl border border-zinc-700 bg-zinc-900 shadow-2xl overflow-hidden flex flex-col"
        onClick={e => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-zinc-100">导出即梦脚本</h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300 text-xs">关闭</button>
        </div>
        <div className="px-4 py-2 flex gap-3 flex-wrap border-b border-zinc-800">
          <div className="flex gap-1">
            <button onClick={() => setMode('full')}
              className={`px-2 py-1 rounded text-[11px] ${mode === 'full' ? 'bg-violet-700/50 text-violet-300' : 'bg-zinc-800 text-zinc-400'}`}>
              整片模式
            </button>
            <button onClick={() => setMode('perShot')}
              className={`px-2 py-1 rounded text-[11px] ${mode === 'perShot' ? 'bg-violet-700/50 text-violet-300' : 'bg-zinc-800 text-zinc-400'}`}>
              单镜头模式
            </button>
          </div>
          <div className="flex gap-1">
            <button onClick={() => setLang('zh')}
              className={`px-2 py-1 rounded text-[11px] ${lang === 'zh' ? 'bg-violet-700/50 text-violet-300' : 'bg-zinc-800 text-zinc-400'}`}>
              中文
            </button>
            <button onClick={() => setLang('en')}
              className={`px-2 py-1 rounded text-[11px] ${lang === 'en' ? 'bg-violet-700/50 text-violet-300' : 'bg-zinc-800 text-zinc-400'}`}>
              English
            </button>
          </div>
          <span className={`text-[11px] ml-auto ${result.charCount > LIMIT ? 'text-amber-400' : 'text-zinc-500'}`}>
            {result.charCount.toLocaleString()} / {LIMIT.toLocaleString()} 字
          </span>
        </div>
        <textarea readOnly value={result.text}
          className="flex-1 min-h-[200px] p-4 bg-zinc-950 text-zinc-200 text-xs font-mono leading-relaxed resize-none outline-none"
          style={{ fontFamily: 'ui-monospace, monospace' }} />
        <div className="px-4 py-3 border-t border-zinc-800">
          <button onClick={copyToClipboard}
            className="w-full py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium flex items-center justify-center gap-2">
            <Copy size={14} /> 复制到剪贴板（粘贴至即梦 Agent 聊天）
          </button>
        </div>
      </div>
    </div>
  );
}

export default function StoryboardEditor({ projectId, clientMode, setClientMode, onBack }) {
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [showJimengModal, setShowJimengModal] = useState(false);
  const [editName, setEditName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');

  useEffect(() => {
    getProject(projectId).then(p => {
      if (p) {
        // Ensure assets use 'subjects' key (migrate old 'costumes')
        const count = p.subjectCount || p.costumeCount || 10;
        const subjects = Array.from({ length: count }, (_, i) =>
          (p.assets?.subjects || p.assets?.costumes || [])[i] || null
        );
        setProject({ ...p, subjectCount: count, assets: { ...p.assets, subjects } });
      }
      setLoading(false);
    });
  }, [projectId]);

  const save = useCallback(async (p) => {
    if (!p) return;
    setSaving(true);
    await saveProject(p);
    setTimeout(() => setSaving(false), 600);
  }, []);

  useEffect(() => {
    if (!project) return;
    const timer = setTimeout(() => save(project), 1500);
    return () => clearTimeout(timer);
  }, [project, save]);

  function updateProject(updates) {
    setProject(prev => ({ ...prev, ...updates }));
  }

  function addShot() {
    const sections = project.sections || ['opening'];
    const newShot = {
      id: newShotId(),
      section: sections[0],
      title: '新镜头',
      types: ['B'],
      duration: '4s',
      desc: '',
      subjects: [],
      model: '',
      camera: '',
      cameraTip: '',
      subshots: [],
      promptZh: '',
      prompt: '',
      notes: '',
      referenceMedia: [],
    };
    updateProject({ shots: [...(project.shots || []), newShot] });
  }

  if (loading) return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <p className="text-zinc-600 text-sm">加载中...</p>
    </div>
  );

  if (!project) return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <div className="text-center">
        <p className="text-zinc-400 mb-4">项目不存在</p>
        <button onClick={onBack} className="text-violet-400 hover:text-violet-300 text-sm">返回</button>
      </div>
    </div>
  );

  // Resolve config from project (falls back to preset if missing)
  const preset = getPreset(project.projectType || 'fashion_show');
  const shotTypes = project.shotTypes || preset.shotTypes;
  const subjectLabel = project.subjectLabel || preset.subjectLabel;
  const subjectSlotLabel = project.subjectSlotLabel || preset.subjectSlotLabel;
  const venueLabel = project.venueLabel || preset.venueLabel;
  const subjectCount = project.subjectCount || preset.defaultSubjectCount;
  const totalDuration = (project.shots || []).reduce((a, s) => a + (parseInt(s.duration) || 0), 0);

  if (clientMode) {
    return (
      <>
        <div className="no-print fixed top-4 right-4 z-50 flex items-center gap-2">
          <div className="relative">
            <button onClick={() => setShowExport(!showExport)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm hover:bg-zinc-700 transition-colors">
              <Download size={13} /> 导出
            </button>
            {showExport && <ExportMenu project={project} onClose={() => setShowExport(false)} onJimengExport={() => setShowJimengModal(true)} />}
          </div>
          <button onClick={() => setClientMode(false)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-700 text-zinc-300 text-sm hover:bg-zinc-800 transition-colors">
            <EyeOff size={13} /> 退出客户视图
          </button>
        </div>
        <ClientView project={project} />
        {showJimengModal && project && (
          <JimengExportModal project={project} onClose={() => setShowJimengModal(false)} />
        )}
      </>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100" style={{ fontFamily: "'Noto Sans SC', -apple-system, sans-serif" }}>
      <div className="sticky top-0 z-40 backdrop-blur-xl bg-zinc-950/90 border-b border-zinc-800/50">
        <div className="max-w-3xl mx-auto px-4 py-3">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="text-zinc-600 hover:text-zinc-400 transition-colors">
              <ArrowLeft size={16} />
            </button>
            {editName ? (
              <input autoFocus value={nameDraft} onChange={e => setNameDraft(e.target.value)}
                onBlur={() => { updateProject({ name: nameDraft }); setEditName(false); }}
                onKeyDown={e => { if (e.key === 'Enter') { updateProject({ name: nameDraft }); setEditName(false); } }}
                className="flex-1 bg-zinc-800 text-zinc-100 text-sm font-bold rounded px-2 py-0.5 border border-zinc-600 outline-none" />
            ) : (
              <h1 onClick={() => { setNameDraft(project.name); setEditName(true); }}
                className="flex-1 text-base font-bold text-zinc-100 cursor-pointer hover:text-white truncate">
                {project.name}
              </h1>
            )}
            <div className="flex items-center gap-2 text-[10px] text-zinc-500 shrink-0">
              <span className="hidden sm:inline">{(project.shots || []).length}镜 · {totalDuration}s</span>
              {saving && <span className="flex items-center gap-1"><RefreshCw size={10} className="animate-spin" />保存中</span>}
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <button onClick={() => setShowPrompt(!showPrompt)}
                className={`flex items-center gap-1 px-2 py-1 rounded-lg border text-[11px] transition-colors ${showPrompt ? 'border-violet-700 bg-violet-950/50 text-violet-300' : 'border-zinc-700 text-zinc-400 hover:bg-zinc-800'}`}>
                {showPrompt ? <EyeOff size={11} /> : <Eye size={11} />} Prompt
              </button>
              <button onClick={() => setClientMode(true)}
                className="flex items-center gap-1 px-2 py-1 rounded-lg border border-zinc-700 text-zinc-400 hover:bg-zinc-800 text-[11px] transition-colors">
                <Eye size={11} /> 客户视图
              </button>
              <div className="relative">
                <button onClick={() => setShowExport(!showExport)}
                  className="flex items-center gap-1 px-2 py-1 rounded-lg border border-zinc-700 text-zinc-400 hover:bg-zinc-800 text-[11px] transition-colors">
                  <Download size={11} /> 导出
                </button>
                {showExport && <ExportMenu project={project} onClose={() => setShowExport(false)} onJimengExport={() => setShowJimengModal(true)} />}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-4 space-y-4">
        {/* Meta */}
        <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4 space-y-2">
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-[10px] text-zinc-600 uppercase tracking-wider block mb-1">客户</label>
              <input value={project.client || ''} onChange={e => updateProject({ client: e.target.value })}
                placeholder="客户名称..." className="w-full bg-transparent text-sm text-zinc-300 outline-none border-b border-zinc-800 focus:border-zinc-600 pb-0.5 transition-colors" />
            </div>
            <div className="flex-1">
              <label className="text-[10px] text-zinc-600 uppercase tracking-wider block mb-1">项目描述</label>
              <input value={project.description || ''} onChange={e => updateProject({ description: e.target.value })}
                placeholder="一句话描述..." className="w-full bg-transparent text-sm text-zinc-300 outline-none border-b border-zinc-800 focus:border-zinc-600 pb-0.5 transition-colors" />
            </div>
          </div>
        </div>

        <div className="rounded-lg bg-zinc-800/30 border border-zinc-700/30 px-3 py-2 text-[11px] text-zinc-500 leading-relaxed">
          🎯 拖动左侧 ⠿ 手柄可调整镜头顺序。展开卡片可编辑描述、上传运镜参考图/视频。
        </div>

        <AssetLibrary
          assets={project.assets}
          subjectCount={subjectCount}
          venueLabel={venueLabel}
          subjectSlotLabel={subjectSlotLabel}
          onUpdate={assets => updateProject({ assets })}
        />

        <ShotList
          shots={project.shots || []}
          assets={project.assets}
          subjectCount={subjectCount}
          subjectLabel={subjectLabel}
          shotTypes={shotTypes}
          onShotsChange={shots => updateProject({ shots })}
          showPrompt={showPrompt}
          isInternal={true}
          sectionMeta={project.sectionMeta}
        />

        <button onClick={addShot}
          className="w-full py-3 rounded-xl border border-dashed border-zinc-800 text-zinc-600 hover:text-zinc-400 hover:border-zinc-700 text-sm flex items-center justify-center gap-2 transition-colors">
          <Plus size={15} /> 添加新镜头
        </button>

        <SubjectSummary shots={project.shots || []} assets={project.assets}
          subjectCount={subjectCount} subjectLabel={subjectLabel} />

        {/* Shot type legend */}
        <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4">
          <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-3">镜头类型图例</h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(shotTypes).map(([k, v]) => (
              <span key={k} className={`px-2 py-0.5 rounded text-[10px] ${v.color}`} title={v.tip || ''}>
                {k} = {v.label}
              </span>
            ))}
          </div>
        </div>

        <div className="text-center pb-8 pt-2">
          <p className="text-[10px] text-zinc-800">Storyboard Studio · 数据实时保存到本地浏览器</p>
        </div>
      </div>

      {showJimengModal && project && (
        <JimengExportModal project={project} onClose={() => setShowJimengModal(false)} />
      )}
    </div>
  );
}
