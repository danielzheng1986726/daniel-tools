import { useState, useRef } from 'react';
import { ChevronDown, ChevronRight, Image, Upload, X } from 'lucide-react';
import { SUBJECT_STYLES } from '../constants.js';

async function readFile(file) {
  return new Promise(r => {
    const x = new FileReader();
    x.onload = e => r({ url: e.target.result, name: file.name });
    x.readAsDataURL(file);
  });
}

function AssetSlot({ label, thumb, onUpload, onClear, borderClass, big }) {
  const ref = useRef(null);
  const sz = big ? 'w-20 h-20' : 'w-14 h-14';
  const handle = async e => {
    const f = e.target.files?.[0];
    if (!f) return;
    const d = await readFile(f);
    onUpload(d);
    e.target.value = '';
  };
  return (
    <div className="flex flex-col items-center gap-1">
      <div
        className={`${sz} rounded-lg border-2 overflow-hidden relative group cursor-pointer transition-colors ${thumb ? (borderClass || 'border-zinc-600') : 'border-dashed border-zinc-700 hover:border-zinc-500'}`}
        onClick={() => !thumb && ref.current?.click()}>
        {thumb ? (
          <>
            <img src={thumb} alt={label} className="w-full h-full object-cover" />
            <button onClick={e => { e.stopPropagation(); onClear(); }}
              className="absolute top-0 right-0 w-4 h-4 bg-black/70 rounded-bl flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              <X size={9} className="text-white" />
            </button>
          </>
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-zinc-600 hover:text-zinc-400 transition-colors">
            <Upload size={big ? 16 : 12} />
          </div>
        )}
      </div>
      <span className="text-[9px] text-zinc-500 text-center leading-tight truncate" style={{ maxWidth: big ? '5rem' : '3.5rem' }}>
        {label}
      </span>
      <input ref={ref} type="file" accept="image/*" className="hidden" onChange={handle} />
    </div>
  );
}

export default function AssetLibrary({ assets, subjectCount = 5, venueLabel = '场景概念图', subjectSlotLabel = '参考图', onUpdate }) {
  const [open, setOpen] = useState(true);

  const subjects = assets.subjects || assets.costumes || Array(subjectCount).fill(null);

  const setVenue = d => onUpdate({ ...assets, venue: d, subjects });
  const clearVenue = () => onUpdate({ ...assets, venue: null, subjects });

  const setSubject = (i, d) => {
    const s = [...subjects];
    s[i] = d;
    onUpdate({ ...assets, subjects: s });
  };
  const clearSubject = i => {
    const s = [...subjects];
    s[i] = null;
    onUpdate({ ...assets, subjects: s });
  };

  const uploadedCount = subjects.filter(Boolean).length;

  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 cursor-pointer select-none hover:bg-zinc-800/20 transition-colors" onClick={() => setOpen(!open)}>
        {open ? <ChevronDown size={13} className="text-zinc-500" /> : <ChevronRight size={13} className="text-zinc-500" />}
        <Image size={13} className="text-zinc-500" />
        <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex-1">素材库</span>
        <span className="text-[10px] text-zinc-600">{uploadedCount}/{subjectCount} {subjectSlotLabel} · {assets.venue ? '✓' : '—'} {venueLabel}</span>
      </div>
      {open && (
        <div className="px-4 pb-4 space-y-4">
          <div>
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5">{venueLabel}（所有镜头共用的 @图片1）</p>
            <div className="flex items-start gap-3">
              <AssetSlot label={venueLabel} thumb={assets.venue?.url} onUpload={setVenue} onClear={clearVenue} borderClass="border-white/30" big />
              <p className="text-[10px] text-zinc-600 leading-relaxed mt-2">上传后在每个 Prompt 中作为 @图片1 引用。</p>
            </div>
          </div>
          <div>
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5">{subjectSlotLabel}（@图片2 起）</p>
            <div className="flex flex-wrap gap-2">
              {Array.from({ length: subjectCount }, (_, i) => {
                const s = SUBJECT_STYLES[i % SUBJECT_STYLES.length];
                return (
                  <AssetSlot key={i} label={`#${i + 1}`} thumb={subjects[i]?.url}
                    onUpload={d => setSubject(i, d)} onClear={() => clearSubject(i)} borderClass={s.border} />
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
