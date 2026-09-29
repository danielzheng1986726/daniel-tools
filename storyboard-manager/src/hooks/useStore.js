import { useState, useEffect, useCallback } from "react";
import { openDB } from "idb";
import { generateId } from "../data/constants";
import { SYMBIOTIC_FUTURE_SHOTS } from "../data/defaultShots";

// ── IndexedDB 初始化（存储图片/视频等二进制资产）────────────────────
const DB_NAME = "storyboard-assets";
const DB_VERSION = 1;

async function getDB() {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains("assets")) {
        db.createObjectStore("assets");
      }
    },
  });
}

export async function saveAsset(projectId, key, file) {
  const db = await getDB();
  const arrayBuffer = await file.arrayBuffer();
  const assetKey = `${projectId}:${key}`;
  await db.put("assets", { buffer: arrayBuffer, type: file.type, name: file.name }, assetKey);
  return assetKey;
}

export async function loadAsset(assetKey) {
  if (!assetKey) return null;
  try {
    const db = await getDB();
    const asset = await db.get("assets", assetKey);
    if (!asset) return null;
    const blob = new Blob([asset.buffer], { type: asset.type });
    return { url: URL.createObjectURL(blob), type: asset.type, name: asset.name };
  } catch {
    return null;
  }
}

export async function deleteAsset(assetKey) {
  try {
    const db = await getDB();
    await db.delete("assets", assetKey);
  } catch {}
}

export async function deleteProjectAssets(projectId) {
  const db = await getDB();
  const allKeys = await db.getAllKeys("assets");
  for (const key of allKeys) {
    if (key.startsWith(`${projectId}:`)) {
      await db.delete("assets", key);
    }
  }
}

// ── 项目数据结构 ──────────────────────────────────────────────────────
function createProject(name, type = "fashion_show", client = "") {
  const id = generateId();
  return {
    id,
    name,
    type,
    client,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    totalDuration: "",
    colorArc: "",
    sections: ["opening", "runway", "finale"],
    // 服装 meta（可从 Brief 导入）
    costumeMeta: {},
    // 全局素材引用 key（存在 IndexedDB 里）
    assets: {
      runway: null,    // 秀场概念图 key
      costumes: Array(10).fill(null), // 服装图 keys
    },
    // 镜头数组
    shots: [],
  };
}

// ── localStorage 工具 ────────────────────────────────────────────────
const PROJECTS_KEY = "storyboard:projects";
const CURRENT_KEY = "storyboard:currentProject";

function loadProjects() {
  try {
    const raw = localStorage.getItem(PROJECTS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function saveProjects(projects) {
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
}

// ── 主 Hook ──────────────────────────────────────────────────────────
export function useStore() {
  const [projects, setProjects] = useState(loadProjects);
  const [currentProjectId, setCurrentProjectId] = useState(
    () => localStorage.getItem(CURRENT_KEY) || null
  );

  // 同步到 localStorage
  useEffect(() => {
    saveProjects(projects);
  }, [projects]);

  useEffect(() => {
    if (currentProjectId) localStorage.setItem(CURRENT_KEY, currentProjectId);
    else localStorage.removeItem(CURRENT_KEY);
  }, [currentProjectId]);

  const currentProject = projects.find(p => p.id === currentProjectId) || null;

  // ── 项目操作 ──────────────────────────────────────────────────────
  const createNewProject = useCallback((name, type, client) => {
    const project = createProject(name, type, client);
    setProjects(prev => [...prev, project]);
    setCurrentProjectId(project.id);
    return project;
  }, []);

  const createProjectFromTemplate = useCallback((name, type, client, templateShots) => {
    const project = createProject(name, type, client);
    project.shots = templateShots.map(s => ({ ...s, cameraRefs: [] }));
    setProjects(prev => [...prev, project]);
    setCurrentProjectId(project.id);
    return project;
  }, []);

  const importProjectFromBrief = useCallback((briefData) => {
    const { project: projectMeta, costumeMeta, shots } = briefData;
    const id = generateId();
    const project = {
      id,
      name: projectMeta.name,
      type: projectMeta.type,
      client: projectMeta.client,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      totalDuration: projectMeta.totalDuration,
      colorArc: projectMeta.colorArc,
      sections: projectMeta.sections,
      costumeMeta,
      assets: { runway: null, costumes: Array(10).fill(null) },
      shots,
    };
    setProjects(prev => [...prev, project]);
    setCurrentProjectId(id);
    return project;
  }, []);

  const deleteProject = useCallback(async (projectId) => {
    await deleteProjectAssets(projectId);
    setProjects(prev => prev.filter(p => p.id !== projectId));
    if (currentProjectId === projectId) setCurrentProjectId(null);
  }, [currentProjectId]);

  const duplicateProject = useCallback((projectId) => {
    const original = projects.find(p => p.id === projectId);
    if (!original) return;
    const copy = {
      ...JSON.parse(JSON.stringify(original)),
      id: generateId(),
      name: `${original.name}（副本）`,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      // 副本不复制二进制资产 key，因为 IndexedDB 里没有复制
      assets: { runway: null, costumes: Array(10).fill(null) },
    };
    setProjects(prev => [...prev, copy]);
    return copy;
  }, [projects]);

  // ── 更新当前项目 ──────────────────────────────────────────────────
  const updateCurrentProject = useCallback((updater) => {
    setProjects(prev => prev.map(p => {
      if (p.id !== currentProjectId) return p;
      const updated = typeof updater === "function" ? updater(p) : { ...p, ...updater };
      return { ...updated, updatedAt: new Date().toISOString() };
    }));
  }, [currentProjectId]);

  // ── 镜头操作 ──────────────────────────────────────────────────────
  const updateShot = useCallback((shotId, updater) => {
    updateCurrentProject(p => ({
      ...p,
      shots: p.shots.map(s => {
        if (s.id !== shotId) return s;
        return typeof updater === "function" ? updater(s) : { ...s, ...updater };
      }),
    }));
  }, [updateCurrentProject]);

  const reorderShots = useCallback((newShots) => {
    updateCurrentProject(p => ({ ...p, shots: newShots }));
  }, [updateCurrentProject]);

  const addShot = useCallback((afterId = null) => {
    const newShot = {
      id: `s${generateId()}`,
      section: "runway",
      title: "新镜头",
      types: ["B"],
      duration: "4s",
      desc: "",
      costumes: [],
      model: "",
      camera: "",
      cameraTip: "",
      cameraRefs: [],
      subshots: [],
      prompt: "",
      notes: "",
    };
    updateCurrentProject(p => {
      const shots = [...p.shots];
      if (afterId) {
        const idx = shots.findIndex(s => s.id === afterId);
        shots.splice(idx + 1, 0, newShot);
      } else {
        shots.push(newShot);
      }
      return { ...p, shots };
    });
    return newShot.id;
  }, [updateCurrentProject]);

  const deleteShot = useCallback((shotId) => {
    updateCurrentProject(p => ({
      ...p,
      shots: p.shots.filter(s => s.id !== shotId),
    }));
  }, [updateCurrentProject]);

  // ── 素材操作 ──────────────────────────────────────────────────────
  const updateAssets = useCallback((updater) => {
    updateCurrentProject(p => ({
      ...p,
      assets: typeof updater === "function" ? updater(p.assets) : { ...p.assets, ...updater },
    }));
  }, [updateCurrentProject]);

  return {
    projects,
    currentProject,
    currentProjectId,
    setCurrentProjectId,
    createNewProject,
    createProjectFromTemplate,
    importProjectFromBrief,
    deleteProject,
    duplicateProject,
    updateCurrentProject,
    updateShot,
    reorderShots,
    addShot,
    deleteShot,
    updateAssets,
  };
}
