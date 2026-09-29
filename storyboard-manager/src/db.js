import { openDB } from 'idb';
import { getPreset } from './projectTypes.js';

const DB_NAME = 'storyboard-studio';
const DB_VERSION = 1;

async function getDB() {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains('projects')) {
        db.createObjectStore('projects', { keyPath: 'id' });
      }
    },
  });
}

export async function getAllProjects() {
  const db = await getDB();
  const all = await db.getAll('projects');
  return all.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
}

export async function getProject(id) {
  const db = await getDB();
  return db.get('projects', id);
}

export async function saveProject(project) {
  const db = await getDB();
  const updated = { ...project, updatedAt: new Date().toISOString() };
  await db.put('projects', updated);
  return updated;
}

export async function deleteProject(id) {
  const db = await getDB();
  return db.delete('projects', id);
}

/**
 * 创建新项目。
 * typeId 对应 projectTypes.js 中的预设 key。
 * 项目把 shotTypes / sectionMeta 等配置存入自身，
 * 运行时完全从项目数据读取，不依赖全局常量。
 */
export function newProject(typeId = 'fashion_show', overrides = {}) {
  const preset = getPreset(typeId);
  return {
    id: crypto.randomUUID(),
    projectType: typeId,
    name: '新项目',
    client: '',
    description: '',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    // ── 从预设继承，可在项目内覆盖 ──
    shotTypes: preset.shotTypes,
    subjectLabel: preset.subjectLabel,
    subjectSlotLabel: preset.subjectSlotLabel,
    venueLabel: preset.venueLabel,
    sections: preset.defaultSections,
    sectionMeta: preset.sectionMeta,
    subjectCount: preset.defaultSubjectCount,
    assets: {
      venue: null,
      subjects: Array(preset.defaultSubjectCount).fill(null),
    },
    shots: [],
    ...overrides,
  };
}
