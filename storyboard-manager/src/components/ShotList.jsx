import { DndContext, closestCenter, PointerSensor, useSensor, useSensors, DragOverlay } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, useSortable, arrayMove } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useState } from 'react';
import ShotCard from './ShotCard.jsx';

function SortableShotCard(props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: props.shot.id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1 };
  return (
    <div ref={setNodeRef} style={style}>
      <ShotCard {...props} dragHandleProps={{ ...attributes, ...listeners }} />
    </div>
  );
}

const FALLBACK_SECTION_META = {
  opening: { label: '开场', accent: 'border-l-blue-500',   tag: 'bg-blue-900/60 text-blue-300' },
  runway:  { label: '走秀', accent: 'border-l-violet-500', tag: 'bg-violet-900/60 text-violet-300' },
  finale:  { label: '谢幕', accent: 'border-l-amber-500',  tag: 'bg-amber-900/60 text-amber-300' },
  intro:    { label: '引入', accent: 'border-l-blue-500',   tag: 'bg-blue-900/60 text-blue-300' },
  showcase: { label: '展示', accent: 'border-l-violet-500', tag: 'bg-violet-900/60 text-violet-300' },
  outro:    { label: '收尾', accent: 'border-l-amber-500',  tag: 'bg-amber-900/60 text-amber-300' },
  hook:     { label: '吸睛', accent: 'border-l-rose-500',   tag: 'bg-rose-900/60 text-rose-300' },
  display:  { label: '展示', accent: 'border-l-violet-500', tag: 'bg-violet-900/60 text-violet-300' },
  cta:      { label: '行动', accent: 'border-l-pink-500',   tag: 'bg-pink-900/60 text-pink-300' },
  buildup:  { label: '铺垫', accent: 'border-l-blue-500',   tag: 'bg-blue-900/60 text-blue-300' },
  climax:   { label: '高潮', accent: 'border-l-rose-500',   tag: 'bg-rose-900/60 text-rose-300' },
  brand:    { label: '收尾', accent: 'border-l-amber-500',  tag: 'bg-amber-900/60 text-amber-300' },
};

export default function ShotList({ shots, assets, subjectCount, subjectLabel, shotTypes, onShotsChange, showPrompt, isInternal, sectionMeta }) {
  const [activeId, setActiveId] = useState(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  function handleDragEnd({ active, over }) {
    setActiveId(null);
    if (!over || active.id === over.id) return;
    const oldIndex = shots.findIndex(s => s.id === active.id);
    const newIndex = shots.findIndex(s => s.id === over.id);
    onShotsChange(arrayMove(shots, oldIndex, newIndex));
  }

  function updateShot(id, updated) {
    onShotsChange(shots.map(s => s.id === id ? updated : s));
  }

  const sections = [...new Set(shots.map(s => s.section))];
  const meta = { ...FALLBACK_SECTION_META, ...(sectionMeta || {}) };

  const activeShot = activeId ? shots.find(s => s.id === activeId) : null;

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter}
      onDragStart={e => setActiveId(e.active.id)} onDragEnd={handleDragEnd}>
      <SortableContext items={shots.map(s => s.id)} strategy={verticalListSortingStrategy}>
        <div className="space-y-6">
          {sections.map(sk => {
            const sec = meta[sk] || { label: sk, accent: 'border-l-zinc-500', tag: 'bg-zinc-800 text-zinc-300' };
            const ss = shots.filter(s => s.section === sk);
            const dur = ss.reduce((a, s) => a + (parseInt(s.duration) || 0), 0);
            return (
              <div key={sk}>
                <div className={`flex items-center gap-3 mb-3 pl-1 border-l-2 ${sec.accent}`}>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${sec.tag}`}>{sec.label}</span>
                  <span className="text-xs text-zinc-500">{dur}s</span>
                  <span className="text-[10px] text-zinc-700">{ss.length} 镜头</span>
                  <div className="flex-1 h-px bg-zinc-800/50" />
                </div>
                <div className="space-y-2 ml-1">
                  {ss.map(shot => (
                    <SortableShotCard key={shot.id} shot={shot} assets={assets}
                      subjectCount={subjectCount} subjectLabel={subjectLabel} shotTypes={shotTypes}
                      onUpdate={updated => updateShot(shot.id, updated)}
                      showPrompt={showPrompt} isInternal={isInternal} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </SortableContext>
      <DragOverlay>
        {activeShot && (
          <div className="opacity-90 rotate-1 scale-105 shadow-2xl">
            <ShotCard shot={activeShot} assets={assets} subjectCount={subjectCount}
              subjectLabel={subjectLabel} shotTypes={shotTypes} onUpdate={() => {}} showPrompt={false} isInternal={isInternal} />
          </div>
        )}
      </DragOverlay>
    </DndContext>
  );
}
