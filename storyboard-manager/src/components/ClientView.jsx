import { SUBJECT_STYLES } from '../constants.js';
import { getPreset } from '../projectTypes.js';

function TypeBadge({ type, shotTypes }) {
  const t = (shotTypes || {})[type];
  if (!t) return null;
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${t.color}`}>{t.label}</span>;
}

export default function ClientView({ project }) {
  if (!project) return null;
  const { name, client, description, shots = [], assets = {}, sectionMeta, projectType } = project;
  const preset = getPreset(projectType || 'fashion_show');
  const shotTypes = project.shotTypes || preset.shotTypes;
  const subjectAssets = assets.subjects || assets.costumes || [];
  const subjectCount = project.subjectCount || project.costumeCount || preset.defaultSubjectCount;

  const totalDuration = shots.reduce((a, s) => a + (parseInt(s.duration) || 0), 0);
  const sections = [...new Set(shots.map(s => s.section))];
  const sectionOrder = ['opening', 'intro', 'runway', 'showcase', 'hook', 'buildup', 'display', 'finale', 'climax', 'outro', 'cta', 'brand'];
  const orderedSections = [...sectionOrder.filter(s => sections.includes(s)), ...sections.filter(s => !sectionOrder.includes(s))];

  const FALLBACK = {
    opening: { label: '开场' }, runway: { label: '走秀' }, finale: { label: '谢幕' },
    intro: { label: '引入' }, showcase: { label: '展示' }, outro: { label: '收尾' },
    hook: { label: '吸睛' }, display: { label: '展示' }, cta: { label: '行动' },
    buildup: { label: '铺垫' }, climax: { label: '高潮' }, brand: { label: '收尾' },
  };

  return (
    <div className="min-h-screen bg-white text-zinc-900" style={{ fontFamily: "'Noto Sans SC', serif" }}>
      <div className="max-w-3xl mx-auto px-8 py-12">
        {/* Cover */}
        <div className="mb-12 pb-8 border-b border-zinc-200">
          <p className="text-xs text-zinc-400 uppercase tracking-widest mb-2">AI 视频分镜脚本</p>
          <h1 className="text-3xl font-bold text-zinc-900 mb-1">{name}</h1>
          {client && <p className="text-sm text-zinc-500 mb-4">客户：{client}</p>}
          {description && <p className="text-sm text-zinc-600 leading-relaxed max-w-xl">{description}</p>}
          <div className="flex gap-6 mt-6 text-sm">
            <div><span className="text-zinc-400">总镜头</span><span className="ml-2 font-semibold">{shots.length}</span></div>
            <div><span className="text-zinc-400">总时长</span><span className="ml-2 font-semibold">{totalDuration}s</span></div>
            <div><span className="text-zinc-400">段落</span><span className="ml-2 font-semibold">{orderedSections.length}</span></div>
          </div>
        </div>

        {/* Subject overview */}
        {subjectAssets.some(Boolean) && (
          <div className="mb-10">
            <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-4">素材总览</h2>
            <div className="flex flex-wrap gap-3">
              {Array.from({ length: subjectCount }, (_, i) => {
                const c = subjectAssets[i];
                const s = SUBJECT_STYLES[i % SUBJECT_STYLES.length];
                return (
                  <div key={i} className="flex flex-col items-center gap-1">
                    <div className={`w-16 h-16 rounded-xl border-2 overflow-hidden ${c ? s.border.replace('/60', '') : 'border-dashed border-zinc-300'}`}>
                      {c ? <img src={c.url} alt="" className="w-full h-full object-cover" /> :
                        <div className="w-full h-full bg-zinc-50 flex items-center justify-center text-zinc-400 text-xs">#{i + 1}</div>}
                    </div>
                    <span className="text-[10px] text-zinc-400">#{i + 1}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Shots by section */}
        {orderedSections.map(sk => {
          const sec = (sectionMeta || {})[sk] || FALLBACK[sk] || { label: sk };
          const sectionShots = shots.filter(s => s.section === sk);
          const secDur = sectionShots.reduce((a, s) => a + (parseInt(s.duration) || 0), 0);
          return (
            <div key={sk} className="mb-10">
              <div className="flex items-center gap-3 mb-5">
                <h2 className="text-base font-bold text-zinc-800">{sec.label}</h2>
                <span className="text-sm text-zinc-400">{secDur}s · {sectionShots.length} 个镜头</span>
              </div>
              <div className="space-y-5">
                {sectionShots.map((shot, idx) => {
                  const subjects = shot.subjects || shot.costumes || [];
                  return (
                    <div key={shot.id} className="rounded-2xl border border-zinc-200 overflow-hidden">
                      <div className="flex items-center gap-3 px-5 py-3 bg-zinc-50 border-b border-zinc-100">
                        <span className="text-xs font-mono text-zinc-400 w-8">{String(idx + 1).padStart(2, '0')}</span>
                        <div className="flex gap-1">{(shot.types || []).map(t => <TypeBadge key={t} type={t} shotTypes={shotTypes} />)}</div>
                        <h3 className="flex-1 text-sm font-semibold text-zinc-800">{shot.title}</h3>
                        <span className="text-xs font-mono text-zinc-500 bg-white border border-zinc-200 px-2 py-0.5 rounded">{shot.duration}</span>
                      </div>
                      <div className="px-5 py-4 space-y-3">
                        <p className="text-sm text-zinc-700 leading-relaxed">{shot.desc}</p>
                        <div className="grid grid-cols-2 gap-3 text-xs">
                          {shot.model && <div><span className="text-zinc-400 block mb-0.5">模特/人物</span><span className="text-zinc-600">{shot.model}</span></div>}
                          {shot.camera && <div><span className="text-zinc-400 block mb-0.5">运镜</span><span className="text-zinc-600">{shot.camera}</span></div>}
                        </div>
                        {subjects.length > 0 && (
                          <div>
                            <span className="text-xs text-zinc-400 block mb-1.5">出现素材</span>
                            <div className="flex gap-2">
                              {subjects.map(n => {
                                const c = subjectAssets[n - 1];
                                return (
                                  <div key={n} className="flex flex-col items-center gap-0.5">
                                    <div className="w-10 h-10 rounded-lg border border-zinc-200 overflow-hidden bg-zinc-50">
                                      {c ? <img src={c.url} alt="" className="w-full h-full object-cover" /> :
                                        <div className="w-full h-full flex items-center justify-center text-xs text-zinc-400">#{n}</div>}
                                    </div>
                                    <span className="text-[9px] text-zinc-400">#{n}</span>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                        {shot.subshots?.length > 0 && (
                          <div>
                            <span className="text-xs text-zinc-400 block mb-1.5">镜头规划</span>
                            <div className="space-y-1">
                              {shot.subshots.map((ss, i) => (
                                <div key={i} className="flex gap-2 text-xs">
                                  <span className="text-zinc-400 font-mono shrink-0">{i + 1}.</span>
                                  <span className="text-zinc-600">{ss}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {shot.referenceMedia?.filter(m => m.type === 'image').length > 0 && (
                          <div>
                            <span className="text-xs text-zinc-400 block mb-1.5">参考图</span>
                            <div className="flex gap-2">
                              {shot.referenceMedia.filter(m => m.type === 'image').map(m => (
                                <div key={m.id} className="w-16 h-16 rounded-lg border border-zinc-200 overflow-hidden">
                                  <img src={m.dataUrl} alt={m.caption || ''} className="w-full h-full object-cover" />
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}

        <div className="mt-16 pt-6 border-t border-zinc-100 text-center text-xs text-zinc-300">
          由 Storyboard Studio 生成 · {new Date().toLocaleDateString('zh-CN')}
        </div>
      </div>
    </div>
  );
}
