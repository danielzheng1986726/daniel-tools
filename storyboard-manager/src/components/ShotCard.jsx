import { useState } from 'react';
import { ChevronDown, ChevronRight, Eye, EyeOff, Check, X, Plus, AlertTriangle, GripVertical, Camera } from 'lucide-react';
import { SUBJECT_STYLES, detectStale } from '../constants.js';
import ReferenceMedia from './ReferenceMedia.jsx';

function TypeBadge({ type, shotTypes }) {
  const t = (shotTypes || {})[type];
  if (!t) return null;
  return <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${t.color}`} title={t.tip || ''}>{t.label}</span>;
}

function EditableText({ value, onChange, multiline, placeholder, className, readOnly }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  if (readOnly) {
    return (
      <div className={`text-zinc-500 italic text-xs ${className || ''}`}>
        {value || placeholder}
      </div>
    );
  }
  if (editing) {
    const Tag = multiline ? 'textarea' : 'input';
    return (
      <div className="flex gap-1.5 items-start">
        <Tag className={`flex-1 bg-zinc-800 text-zinc-200 text-xs rounded px-2 py-1.5 border border-zinc-600 focus:border-zinc-400 outline-none ${multiline ? 'resize-y' : ''} ${className || ''}`}
          style={multiline ? { minHeight: '60px' } : undefined}
          value={draft} onChange={e => setDraft(e.target.value)}
          onKeyDown={e => { if (!multiline && e.key === 'Enter') { onChange(draft); setEditing(false); } }}
          autoFocus />
        <button onClick={() => { onChange(draft); setEditing(false); }} className="text-emerald-500 hover:text-emerald-400 mt-1"><Check size={12} /></button>
        <button onClick={() => { setDraft(value); setEditing(false); }} className="text-zinc-500 hover:text-zinc-300 mt-1"><X size={12} /></button>
      </div>
    );
  }
  return (
    <div className={`cursor-pointer hover:bg-zinc-800/50 rounded px-1 py-0.5 transition-colors ${className || ''}`} onClick={() => { setDraft(value); setEditing(true); }}>
      {value ? value : <span className="text-zinc-700 italic text-xs">{placeholder || '点击编辑...'}</span>}
    </div>
  );
}

function SubjectBadge({ num, thumb, onRemove }) {
  const s = SUBJECT_STYLES[(num - 1) % SUBJECT_STYLES.length];
  return (
    <span className={`inline-flex items-center gap-1 pr-2 rounded-full border ${s.border} ${s.bg} overflow-hidden`}>
      {thumb
        ? <img src={thumb} className="w-5 h-5 rounded-full object-cover" alt="" />
        : <span className="w-5 h-5 rounded-full bg-zinc-800 flex items-center justify-center text-[8px] text-zinc-500">{num}</span>
      }
      <span className={`text-[10px] ${s.text}`}>#{num}</span>
      {onRemove && <button onClick={e => { e.stopPropagation(); onRemove(); }} className="opacity-40 hover:opacity-100 ml-0.5"><X size={8} /></button>}
    </span>
  );
}

function SubjectEditor({ subjects, assets, subjectCount, onChange, subjectLabel }) {
  const [adding, setAdding] = useState(false);
  const subjectAssets = assets.subjects || assets.costumes || [];
  const avail = Array.from({ length: subjectCount }, (_, i) => i + 1).filter(n => !subjects.includes(n));
  return (
    <div className="flex flex-wrap items-center gap-1.5 min-h-[28px] rounded-lg px-1.5 py-1">
      {subjects.map(n => (
        <SubjectBadge key={n} num={n} thumb={subjectAssets[n - 1]?.url} onRemove={() => onChange(subjects.filter(c => c !== n))} />
      ))}
      {subjects.length === 0 && <span className="text-[10px] text-zinc-600 italic">无特定{subjectLabel}（远景/空镜）</span>}
      {adding ? (
        <div className="flex flex-wrap gap-1 items-center">
          {avail.map(n => (
            <button key={n} onClick={() => { onChange([...subjects, n].sort((a, b) => a - b)); setAdding(false); }}
              className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-zinc-800 text-zinc-400 hover:bg-zinc-700 border border-zinc-700">
              {subjectAssets[n - 1]?.url ? <img src={subjectAssets[n - 1].url} className="w-3.5 h-3.5 rounded-full object-cover" alt="" /> : null}
              +{n}
            </button>
          ))}
          <button onClick={() => setAdding(false)} className="text-zinc-600 hover:text-zinc-400"><X size={11} /></button>
        </div>
      ) : (avail.length > 0 && <button onClick={() => setAdding(true)} className="text-zinc-700 hover:text-zinc-400"><Plus size={13} /></button>)}
    </div>
  );
}

export default function ShotCard({ shot, assets, subjectCount = 5, subjectLabel = '主体', shotTypes = {}, onUpdate, showPrompt, dragHandleProps, isInternal }) {
  const [expanded, setExpanded] = useState(false);
  const [promptVisible, setPromptVisible] = useState(false);
  const [promptLang, setPromptLang] = useState('zh'); // 'zh' | 'en'
  const stale = detectStale(shot);
  const sp = showPrompt || promptVisible;
  const subjects = shot.subjects || shot.costumes || [];
  const subjectAssets = assets.subjects || assets.costumes || [];

  // 中文：promptZh 优先，空则用 desc；英文：prompt，空则显示缺省提示
  const promptZhValue = (shot.promptZh || shot.desc || '').trim();
  const promptEnValue = (shot.prompt || '').trim();
  const hasEn = promptEnValue.length > 0;

  return (
    <div className={`rounded-xl border overflow-hidden transition-colors ${stale.length > 0 ? 'border-amber-800/50 bg-zinc-900/50' : 'border-zinc-800/80 bg-zinc-900/50'}`}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3">
        {dragHandleProps && (
          <div {...dragHandleProps} className="cursor-grab active:cursor-grabbing text-zinc-700 hover:text-zinc-500 shrink-0">
            <GripVertical size={14} />
          </div>
        )}
        <div className="flex items-center gap-2 flex-1 cursor-pointer select-none" onClick={() => setExpanded(!expanded)}>
          <span className="text-xs font-mono text-zinc-600 w-8 shrink-0">{shot.id}</span>
          {expanded ? <ChevronDown size={13} className="text-zinc-500 shrink-0" /> : <ChevronRight size={13} className="text-zinc-500 shrink-0" />}
          <div className="flex items-center gap-1 shrink-0">
            {(shot.types || []).map(t => <TypeBadge key={t} type={t} shotTypes={shotTypes} />)}
          </div>
          <h3 className="flex-1 text-sm font-semibold text-zinc-100 truncate">{shot.title}</h3>
          {stale.length > 0 && <AlertTriangle size={13} className="text-amber-400 shrink-0" />}
          <span className="text-xs font-mono text-zinc-500 shrink-0">{shot.duration}</span>
        </div>
      </div>

      {/* Always visible summary */}
      <div className="px-4 pb-3 -mt-1 space-y-1.5">
        <div className="flex items-center gap-1.5 flex-wrap min-h-[24px]">
          <span className="text-[10px] text-zinc-600 uppercase tracking-wider shrink-0 w-8">{subjectLabel}</span>
          {subjects.length > 0
            ? subjects.map(n => <SubjectBadge key={n} num={n} thumb={subjectAssets[n - 1]?.url} />)
            : <span className="text-[10px] text-zinc-600 italic">—</span>
          }
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-zinc-600 uppercase tracking-wider shrink-0 w-8">运镜</span>
          <span className="text-[11px] text-zinc-400">{shot.camera}</span>
        </div>
        {shot.referenceMedia?.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-zinc-600 uppercase tracking-wider shrink-0 w-8">参考</span>
            <div className="flex gap-1">
              {shot.referenceMedia.slice(0, 4).map(m => (
                <div key={m.id} className="w-8 h-8 rounded overflow-hidden border border-zinc-700">
                  {m.type === 'video' ? <video src={m.dataUrl} className="w-full h-full object-cover" /> : <img src={m.dataUrl} className="w-full h-full object-cover" alt="" />}
                </div>
              ))}
              {shot.referenceMedia.length > 4 && <span className="text-[10px] text-zinc-600 ml-1">+{shot.referenceMedia.length - 4}</span>}
            </div>
          </div>
        )}
      </div>

      {stale.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg bg-amber-950/40 border border-amber-700/40 px-3 py-2 mx-4 mb-2">
          <AlertTriangle size={13} className="text-amber-400 shrink-0 mt-0.5" />
          <p className="text-[11px] text-amber-300/90">描述中可能仍含已移除主体的关键词：{stale.map(n => `#${n}`).join(', ')}</p>
        </div>
      )}

      {/* Expanded */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-zinc-800/50 pt-3">
          <div>
            <span className="text-[10px] text-zinc-600 uppercase tracking-wider">画面描述</span>
            <div className="mt-1 text-xs text-zinc-300 leading-relaxed">
              <EditableText value={shot.desc} onChange={v => onUpdate({ ...shot, desc: v })} multiline placeholder="描述这个镜头的画面..." />
            </div>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-[10px] text-zinc-600 uppercase tracking-wider shrink-0 mt-0.5">模特/人物</span>
            <div className="flex-1">
              <EditableText value={shot.model || ''} onChange={v => onUpdate({ ...shot, model: v })} placeholder="模特/人物描述..." className="text-xs text-zinc-400" />
            </div>
          </div>
          {isInternal && (
            <div>
              <span className="text-[10px] text-zinc-600 uppercase tracking-wider">{subjectLabel}分配</span>
              <div className="mt-1">
                <SubjectEditor subjects={subjects} assets={assets} subjectCount={subjectCount} subjectLabel={subjectLabel}
                  onChange={v => onUpdate({ ...shot, subjects: v })} />
              </div>
            </div>
          )}
          <div>
            <span className="text-[10px] text-zinc-600 uppercase tracking-wider flex items-center gap-1.5"><Camera size={11} /> 运镜参考</span>
            <div className="mt-1 text-xs text-zinc-400">
              <EditableText value={shot.camera} onChange={v => onUpdate({ ...shot, camera: v })} placeholder="运镜参考..." />
              {shot.cameraTip && <p className="text-[10px] text-zinc-600 mt-0.5 px-1">↳ {shot.cameraTip}</p>}
            </div>
            <div className="mt-2">
              <ReferenceMedia media={shot.referenceMedia || []} onChange={v => onUpdate({ ...shot, referenceMedia: v })} />
            </div>
          </div>
          <div>
            <span className="text-[10px] text-zinc-600 uppercase tracking-wider">镜头规划</span>
            <div className="mt-1 space-y-1">
              {(shot.subshots || []).map((ss, i) => (
                <div key={i} className="flex gap-2 text-xs px-1">
                  <span className="text-zinc-600 font-mono shrink-0">{i + 1}.</span>
                  <span className="text-zinc-400">{ss}</span>
                </div>
              ))}
            </div>
          </div>
          {isInternal && (
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <button onClick={() => setPromptVisible(!sp)}
                  className="flex items-center gap-1.5 text-[10px] text-zinc-600 hover:text-zinc-400 uppercase tracking-wider transition-colors">
                  {sp ? <EyeOff size={11} /> : <Eye size={11} />}{sp ? '隐藏 Prompt' : '显示 Prompt（技术执行参考）'}
                </button>
                {sp && (
                  <div className="flex gap-1">
                    <button onClick={() => setPromptLang('zh')}
                      className={`px-1.5 py-0.5 rounded text-[10px] transition-colors ${promptLang === 'zh' ? 'bg-violet-800/60 text-violet-300 border border-violet-600/50' : 'text-zinc-500 hover:text-zinc-400 border border-zinc-700'}`}>
                      中
                    </button>
                    <button onClick={() => setPromptLang('en')}
                      className={`px-1.5 py-0.5 rounded text-[10px] transition-colors ${promptLang === 'en' ? 'bg-violet-800/60 text-violet-300 border border-violet-600/50' : 'text-zinc-500 hover:text-zinc-400 border border-zinc-700'}`}
                      title={!hasEn ? '英文暂缺' : ''}>
                      EN {!hasEn && <span className="text-zinc-600">(暂缺)</span>}
                    </button>
                  </div>
                )}
              </div>
              {sp && (
                <div className="mt-2" key={promptLang}>
                  {promptLang === 'zh' ? (
                    <EditableText
                      value={shot.promptZh ?? shot.desc ?? ''}
                      onChange={v => onUpdate({ ...shot, promptZh: v })}
                      multiline
                      placeholder="中文 Prompt（即梦主用），可与画面描述相同或更详细..."
                      className="font-mono text-[11px] leading-relaxed whitespace-pre-wrap bg-zinc-800/80 max-h-48 overflow-y-auto" />
                  ) : hasEn ? (
                    <EditableText
                      value={shot.prompt}
                      onChange={v => onUpdate({ ...shot, prompt: v })}
                      multiline
                      placeholder="English prompt for Veo / Seedance..."
                      className="font-mono text-[11px] leading-relaxed whitespace-pre-wrap bg-zinc-800/80 max-h-48 overflow-y-auto" />
                  ) : (
                    <EditableText
                      value=""
                      onChange={v => onUpdate({ ...shot, prompt: v })}
                      multiline
                      placeholder="英文暂缺，点击添加 English prompt..."
                      className="font-mono text-[11px] leading-relaxed whitespace-pre-wrap bg-zinc-800/80 max-h-48 overflow-y-auto" />
                  )}
                </div>
              )}
            </div>
          )}
          <div>
            <span className="text-[10px] text-zinc-600 uppercase tracking-wider">备注</span>
            <div className="mt-1 text-xs text-zinc-500">
              <EditableText value={shot.notes || ''} onChange={v => onUpdate({ ...shot, notes: v })} placeholder="点击添加备注..." />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
