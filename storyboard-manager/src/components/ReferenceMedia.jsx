import { useState, useRef } from 'react';
import { Upload, X, Play, Image as ImageIcon, Video, GripVertical } from 'lucide-react';

async function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = e => resolve(e.target.result);
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}

function MediaThumb({ item, onRemove, onCaptionChange }) {
  const [editCaption, setEditCaption] = useState(false);
  const [cap, setCap] = useState(item.caption || '');
  const isVideo = item.type === 'video';

  return (
    <div className="group relative rounded-xl border border-zinc-700 bg-zinc-800/50 overflow-hidden">
      <div className="relative w-full aspect-video bg-zinc-900">
        {isVideo ? (
          <video src={item.dataUrl} className="w-full h-full object-cover" />
        ) : (
          <img src={item.dataUrl} alt={item.name} className="w-full h-full object-cover" />
        )}
        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
          {isVideo && (
            <a href={item.dataUrl} target="_blank" rel="noreferrer"
              className="p-1.5 rounded-full bg-white/20 hover:bg-white/30">
              <Play size={12} className="text-white" />
            </a>
          )}
          <button onClick={onRemove} className="p-1.5 rounded-full bg-red-500/80 hover:bg-red-500">
            <X size={12} className="text-white" />
          </button>
        </div>
        <span className="absolute top-1.5 left-1.5 flex items-center gap-1 px-1.5 py-0.5 rounded bg-black/60 text-[9px] text-zinc-300">
          {isVideo ? <Video size={9} /> : <ImageIcon size={9} />}
          {isVideo ? '视频' : '图片'}
        </span>
      </div>
      <div className="px-2 py-1.5">
        {editCaption ? (
          <input
            autoFocus
            value={cap}
            onChange={e => setCap(e.target.value)}
            onBlur={() => { onCaptionChange(cap); setEditCaption(false); }}
            onKeyDown={e => { if (e.key === 'Enter') { onCaptionChange(cap); setEditCaption(false); } }}
            className="w-full text-[10px] bg-zinc-700 rounded px-1.5 py-0.5 text-zinc-200 outline-none border border-zinc-500"
          />
        ) : (
          <p onClick={() => setEditCaption(true)}
            className="text-[10px] text-zinc-500 truncate cursor-pointer hover:text-zinc-400">
            {item.caption || item.name || '点击添加说明'}
          </p>
        )}
      </div>
    </div>
  );
}

export default function ReferenceMedia({ media = [], onChange }) {
  const imgRef = useRef(null);
  const vidRef = useRef(null);
  const [warning, setWarning] = useState('');

  async function handleFiles(files, type) {
    setWarning('');
    const newItems = [];
    for (const file of files) {
      if (type === 'video' && file.size > 100 * 1024 * 1024) {
        setWarning('视频文件超过 100MB，建议压缩后上传');
        continue;
      }
      const dataUrl = await readFileAsDataURL(file);
      newItems.push({
        id: crypto.randomUUID(),
        type,
        name: file.name,
        dataUrl,
        caption: '',
      });
    }
    onChange([...media, ...newItems]);
  }

  function remove(id) {
    onChange(media.filter(m => m.id !== id));
  }

  function updateCaption(id, caption) {
    onChange(media.map(m => m.id === id ? { ...m, caption } : m));
  }

  return (
    <div className="space-y-2">
      {media.length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {media.map(item => (
            <MediaThumb
              key={item.id}
              item={item}
              onRemove={() => remove(item.id)}
              onCaptionChange={cap => updateCaption(item.id, cap)}
            />
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <button
          onClick={() => imgRef.current?.click()}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-[11px] transition-colors">
          <ImageIcon size={11} /> 上传参考图
        </button>
        <button
          onClick={() => vidRef.current?.click()}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-[11px] transition-colors">
          <Video size={11} /> 上传运镜视频
        </button>
        <input ref={imgRef} type="file" accept="image/*" multiple className="hidden"
          onChange={e => handleFiles(Array.from(e.target.files), 'image')} />
        <input ref={vidRef} type="file" accept="video/*" multiple className="hidden"
          onChange={e => handleFiles(Array.from(e.target.files), 'video')} />
      </div>
      {warning && <p className="text-[10px] text-amber-400">{warning}</p>}
    </div>
  );
}
