import jsPDF from "jspdf";
import html2canvas from "html2canvas";

/**
 * 导出客户版 PDF
 * 思路：渲染一个隐藏的"客户视图" div，用 html2canvas 截图后写入 jsPDF。
 * 每张截图对应一页，适合 A4 横版展示。
 */
export async function exportClientPDF(project, assetUrls, onProgress) {
  const { shots } = project;
  const pdf = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
  const pageW = 297; // A4 landscape mm
  const pageH = 210;

  // 创建隐藏渲染容器
  const container = document.createElement("div");
  container.style.cssText = `
    position: fixed; top: -9999px; left: -9999px;
    width: 1122px; /* ~297mm @ 96dpi */
    background: #09090b;
    font-family: 'Noto Sans SC', 'Noto Sans', sans-serif;
  `;
  document.body.appendChild(container);

  // 封面页
  container.innerHTML = renderCoverHTML(project);
  const coverCanvas = await html2canvas(container, { scale: 2, useCORS: true, backgroundColor: "#09090b" });
  pdf.addImage(coverCanvas.toDataURL("image/jpeg", 0.92), "JPEG", 0, 0, pageW, pageH);

  // 每个镜头一页
  for (let i = 0; i < shots.length; i++) {
    onProgress && onProgress(Math.round(((i + 1) / shots.length) * 100));
    const shot = shots[i];
    container.innerHTML = renderShotHTML(shot, i, shots.length, project, assetUrls);
    const canvas = await html2canvas(container, { scale: 2, useCORS: true, backgroundColor: "#09090b" });
    pdf.addPage();
    pdf.addImage(canvas.toDataURL("image/jpeg", 0.92), "JPEG", 0, 0, pageW, pageH);
  }

  document.body.removeChild(container);

  const fileName = `${project.name}_分镜脚本_客户版_${new Date().toLocaleDateString("zh-CN").replace(/\//g, "")}.pdf`;
  pdf.save(fileName);
}

/**
 * 导出内部完整版 PDF（含 Prompt 和技术备注）
 */
export async function exportInternalPDF(project, assetUrls, onProgress) {
  const { shots } = project;
  const pdf = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
  const pageW = 297;
  const pageH = 210;

  const container = document.createElement("div");
  container.style.cssText = `
    position: fixed; top: -9999px; left: -9999px;
    width: 1122px;
    background: #09090b;
    font-family: 'Noto Sans SC', 'Noto Sans', sans-serif;
  `;
  document.body.appendChild(container);

  // 封面页
  container.innerHTML = renderCoverHTML(project, true);
  const coverCanvas = await html2canvas(container, { scale: 2, useCORS: true, backgroundColor: "#09090b" });
  pdf.addImage(coverCanvas.toDataURL("image/jpeg", 0.92), "JPEG", 0, 0, pageW, pageH);

  for (let i = 0; i < shots.length; i++) {
    onProgress && onProgress(Math.round(((i + 1) / shots.length) * 100));
    const shot = shots[i];
    container.innerHTML = renderShotHTML(shot, i, shots.length, project, assetUrls, true);
    const canvas = await html2canvas(container, { scale: 2, useCORS: true, backgroundColor: "#09090b" });
    pdf.addPage();
    pdf.addImage(canvas.toDataURL("image/jpeg", 0.92), "JPEG", 0, 0, pageW, pageH);
  }

  document.body.removeChild(container);

  const fileName = `${project.name}_分镜脚本_内部版_${new Date().toLocaleDateString("zh-CN").replace(/\//g, "")}.pdf`;
  pdf.save(fileName);
}

// ── HTML 渲染器 ─────────────────────────────────────────────────────

const SECTION_LABELS = { opening: "开场", runway: "走秀", finale: "谢幕" };
const TYPE_LABELS = { A:"空间", B:"英雄", C:"特写", D:"群走", E:"俯拍", F:"呼吸" };
const TYPE_COLORS = {
  A:"#64748b", B:"#7c3aed", C:"#0891b2", D:"#d97706", E:"#059669", F:"#0d9488"
};

function renderCoverHTML(project, isInternal = false) {
  return `
    <div style="width:1122px;height:794px;background:#09090b;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:80px;box-sizing:border-box;">
      <div style="color:#3f3f46;font-size:11px;letter-spacing:4px;text-transform:uppercase;margin-bottom:24px;">
        ${isInternal ? "INTERNAL · 内部文件" : "STORYBOARD · 分镜脚本"}
      </div>
      <h1 style="color:#fafafa;font-size:48px;font-weight:700;margin:0 0 16px;text-align:center;line-height:1.2;">
        ${project.name}
      </h1>
      <div style="color:#71717a;font-size:16px;margin-bottom:48px;">
        ${project.client ? `客户：${project.client} · ` : ""}${project.totalDuration ? `时长：${project.totalDuration} · ` : ""}${project.shots?.length || 0} 个镜头
      </div>
      ${project.colorArc ? `
      <div style="border:1px solid #27272a;border-radius:8px;padding:16px 24px;max-width:600px;text-align:center;">
        <div style="color:#52525b;font-size:10px;letter-spacing:2px;margin-bottom:8px;">色彩叙事弧线</div>
        <div style="color:#a1a1aa;font-size:14px;">${project.colorArc}</div>
      </div>` : ""}
      <div style="position:absolute;bottom:40px;color:#27272a;font-size:11px;">
        ${new Date().toLocaleDateString("zh-CN", { year:"numeric", month:"long", day:"numeric" })} · Storyboard Studio
      </div>
    </div>
  `;
}

function renderShotHTML(shot, index, total, project, assetUrls, isInternal = false) {
  const sectionLabel = SECTION_LABELS[shot.section] || shot.section;
  const typeLabels = (shot.types || []).map(t => ({
    label: TYPE_LABELS[t] || t,
    color: TYPE_COLORS[t] || "#52525b"
  }));

  const costumeNames = (shot.costumes || []).map(num => {
    const meta = project.costumeMeta?.[num];
    return meta ? `#${num} ${meta.name}` : `参考图 ${num}`;
  });

  // 找运镜参考图（取第一张）
  const firstCameraRef = shot.cameraRefs?.[0]?.dataUrl || null;

  return `
    <div style="width:1122px;min-height:794px;background:#09090b;padding:48px;box-sizing:border-box;display:grid;grid-template-columns:1fr 320px;gap:48px;">

      <!-- 左栏：主要信息 -->
      <div>
        <!-- 头部 -->
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:32px;">
          <span style="color:#3f3f46;font-size:11px;font-family:monospace;width:32px;">${String(index + 1).padStart(2,"0")}</span>
          <span style="background:#18181b;border:1px solid #27272a;color:#71717a;font-size:10px;padding:4px 10px;border-radius:20px;letter-spacing:1px;">
            ${sectionLabel}
          </span>
          ${typeLabels.map(t => `<span style="background:${t.color}22;border:1px solid ${t.color}44;color:${t.color};font-size:10px;padding:4px 10px;border-radius:4px;">${t.label}</span>`).join("")}
          <span style="margin-left:auto;color:#52525b;font-size:12px;font-family:monospace;">${shot.duration}</span>
        </div>

        <!-- 标题 -->
        <h2 style="color:#fafafa;font-size:28px;font-weight:700;margin:0 0 20px;line-height:1.3;">
          ${shot.title}
        </h2>

        <!-- 画面描述 -->
        <div style="color:#a1a1aa;font-size:13px;line-height:1.8;margin-bottom:24px;max-height:160px;overflow:hidden;">
          ${shot.desc}
        </div>

        <!-- 模特 -->
        ${shot.model ? `
        <div style="margin-bottom:16px;">
          <div style="color:#52525b;font-size:10px;letter-spacing:1px;margin-bottom:6px;">模特方向</div>
          <div style="color:#71717a;font-size:12px;">${shot.model}</div>
        </div>` : ""}

        <!-- 服装 -->
        ${costumeNames.length > 0 ? `
        <div style="margin-bottom:16px;">
          <div style="color:#52525b;font-size:10px;letter-spacing:1px;margin-bottom:6px;">出现服装</div>
          <div style="display:flex;flex-wrap:wrap;gap:8px;">
            ${costumeNames.map(n => `<span style="background:#18181b;border:1px solid #27272a;color:#a1a1aa;font-size:11px;padding:4px 10px;border-radius:4px;">${n}</span>`).join("")}
          </div>
        </div>` : ""}

        <!-- 运镜 -->
        ${shot.camera ? `
        <div style="margin-bottom:16px;">
          <div style="color:#52525b;font-size:10px;letter-spacing:1px;margin-bottom:6px;">运镜参考</div>
          <div style="color:#71717a;font-size:12px;">${shot.camera}</div>
          ${shot.cameraTip ? `<div style="color:#3f3f46;font-size:11px;margin-top:4px;">↳ ${shot.cameraTip}</div>` : ""}
        </div>` : ""}

        <!-- 镜头规划 -->
        ${shot.subshots?.length > 0 ? `
        <div style="margin-bottom:16px;">
          <div style="color:#52525b;font-size:10px;letter-spacing:1px;margin-bottom:8px;">镜头规划</div>
          ${shot.subshots.map((ss, i) => `
          <div style="display:flex;gap:12px;margin-bottom:4px;">
            <span style="color:#3f3f46;font-family:monospace;font-size:11px;min-width:16px;">${i + 1}.</span>
            <span style="color:#71717a;font-size:12px;">${ss}</span>
          </div>`).join("")}
        </div>` : ""}

        <!-- 内部版：Prompt -->
        ${isInternal && shot.prompt ? `
        <div style="margin-top:20px;background:#18181b;border:1px solid #27272a;border-radius:8px;padding:16px;">
          <div style="color:#52525b;font-size:10px;letter-spacing:1px;margin-bottom:8px;">AI PROMPT</div>
          <pre style="color:#52525b;font-size:10px;white-space:pre-wrap;word-break:break-all;margin:0;font-family:monospace;max-height:120px;overflow:hidden;">${shot.prompt}</pre>
        </div>` : ""}
      </div>

      <!-- 右栏：视觉参考 -->
      <div style="display:flex;flex-direction:column;gap:16px;">
        ${firstCameraRef ? `
        <div>
          <div style="color:#52525b;font-size:10px;letter-spacing:1px;margin-bottom:8px;">运镜参考图</div>
          <img src="${firstCameraRef}" style="width:100%;border-radius:8px;object-fit:cover;max-height:200px;" />
        </div>` : `
        <div style="width:100%;height:180px;background:#18181b;border:1px dashed #27272a;border-radius:8px;display:flex;align-items:center;justify-content:center;">
          <span style="color:#3f3f46;font-size:11px;">运镜参考图待上传</span>
        </div>`}

        <!-- 内部版：技术备注 -->
        ${isInternal && shot.notes ? `
        <div style="background:#27180a;border:1px solid #92400e44;border-radius:8px;padding:14px;">
          <div style="color:#78350f;font-size:10px;letter-spacing:1px;margin-bottom:6px;">内部备注</div>
          <div style="color:#b45309;font-size:11px;line-height:1.6;">${shot.notes}</div>
        </div>` : ""}

        <!-- 页码 -->
        <div style="margin-top:auto;padding-top:16px;border-top:1px solid #18181b;display:flex;justify-content:space-between;align-items:center;">
          <span style="color:#27272a;font-size:10px;">${project.name}</span>
          <span style="color:#27272a;font-size:10px;font-family:monospace;">${index + 1} / ${total}</span>
        </div>
      </div>
    </div>
  `;
}

/**
 * 将项目导出为 JSON 文件（用于备份和在 Claude 对话里恢复）
 */
export function exportProjectJSON(project) {
  // 导出时去掉 IndexedDB key（二进制资产），保留文字数据
  const exportData = {
    _exportedAt: new Date().toISOString(),
    _version: "1.0",
    project: {
      name: project.name,
      type: project.type,
      client: project.client,
      totalDuration: project.totalDuration,
      colorArc: project.colorArc,
      sections: project.sections,
    },
    costumes: Object.entries(project.costumeMeta || {}).map(([id, meta]) => ({
      id: parseInt(id), name: meta.name, keywords: meta.keywords || [],
    })),
    shots: project.shots.map(s => ({
      id: s.id, section: s.section, title: s.title, types: s.types,
      duration: s.duration, desc: s.desc, costumes: s.costumes,
      model: s.model, camera: s.camera, cameraTip: s.cameraTip,
      subshots: s.subshots, prompt: s.prompt, notes: s.notes,
      // cameraRefs 不导出（是 blob URL，不可序列化）
    })),
  };

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${project.name}_Brief_${new Date().toLocaleDateString("zh-CN").replace(/\//g, "")}.json`;
  a.click();
  URL.revokeObjectURL(url);
}
