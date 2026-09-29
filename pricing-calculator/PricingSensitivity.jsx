import { useState, useMemo } from "react";

// 下面所有数字（底价、分成比例、终端报价）都是示例数，换成你自己的。

const COLORS = {
  danger: "#FEE2E2",
  dangerText: "#991B1B",
  warning: "#FEF3C7",
  warningText: "#92400E",
  safe: "#D1FAE5",
  safeText: "#065F46",
  great: "#DBEAFE",
  greatText: "#1E40AF",
  bg: "#FAFAF9",
  card: "#FFFFFF",
  border: "#E7E5E4",
  muted: "#78716C",
  text: "#1C1917",
  accent: "#292524",
};

function getZone(hourly) {
  if (hourly < 100) return { bg: COLORS.danger, text: COLORS.dangerText, label: "低于底线" };
  if (hourly < 150) return { bg: COLORS.warning, text: COLORS.warningText, label: "可接受" };
  if (hourly < 250) return { bg: COLORS.safe, text: COLORS.safeText, label: "健康" };
  return { bg: COLORS.great, text: COLORS.greatText, label: "优秀" };
}

function formatCurrency(n) {
  return "¥" + n.toLocaleString("zh-CN");
}

export default function PricingSensitivity() {
  // 示例数，换成你自己的：底价、分成比例、预估工时
  const [basePrice, setBasePrice] = useState(1000);
  const [splitPct, setSplitPct] = useState(30);
  const [workHours, setWorkHours] = useState(40);
  const [activeTab, setActiveTab] = useState("matrix");

  // 示例数，换成你自己的：矩阵/分析里要覆盖的报价档位
  const endPrices = [8000, 10000, 12000, 15000, 18000, 20000, 25000, 30000];
  const basePrices = [1000, 2000, 3000, 4000];
  const splits = [30, 40, 50];

  const calc = (endPrice, base, split, hours) => {
    const remainder = Math.max(0, endPrice - base);
    const yourTotal = base + remainder * (split / 100);
    const partnerTotal = endPrice - yourTotal;
    const hourly = yourTotal / hours;
    return { yourTotal, partnerTotal, hourly, remainder };
  };

  const currentCalc = useMemo(() => {
    return endPrices.map((ep) => {
      const r = calc(ep, basePrice, splitPct, workHours);
      return { endPrice: ep, ...r };
    });
  }, [basePrice, splitPct, workHours]);

  const matrixData = useMemo(() => {
    const results = [];
    for (const bp of basePrices) {
      for (const sp of splits) {
        const row = { basePrice: bp, split: sp, cells: [] };
        for (const ep of [10000, 15000, 20000, 25000, 30000]) {
          const r = calc(ep, bp, sp, workHours);
          row.cells.push({ endPrice: ep, ...r });
        }
        results.push(row);
      }
    }
    return results;
  }, [workHours]);

  const breakEvenPrice = useMemo(() => {
    const targetHourly = 100;
    const targetTotal = targetHourly * workHours;
    if (basePrice >= targetTotal) return basePrice;
    const neededFromSplit = targetTotal - basePrice;
    const neededRemainder = neededFromSplit / (splitPct / 100);
    return basePrice + neededRemainder;
  }, [basePrice, splitPct, workHours]);

  const SliderControl = ({ label, value, onChange, min, max, step, format, sublabel }) => (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <span style={{ fontSize: 13, color: COLORS.muted }}>{label}</span>
        <span style={{ fontSize: 18, fontWeight: 600, color: COLORS.text }}>{format(value)}</span>
      </div>
      {sublabel && <div style={{ fontSize: 11, color: COLORS.muted, marginBottom: 4 }}>{sublabel}</div>}
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ width: "100%", accentColor: COLORS.accent }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: COLORS.muted }}>
        <span>{format(min)}</span>
        <span>{format(max)}</span>
      </div>
    </div>
  );

  const TabButton = ({ id, label }) => (
    <button
      onClick={() => setActiveTab(id)}
      style={{
        padding: "8px 16px",
        fontSize: 13,
        fontWeight: activeTab === id ? 600 : 400,
        color: activeTab === id ? COLORS.text : COLORS.muted,
        background: activeTab === id ? COLORS.card : "transparent",
        border: activeTab === id ? `1px solid ${COLORS.border}` : "1px solid transparent",
        borderRadius: 6,
        cursor: "pointer",
        transition: "all 0.15s",
      }}
    >
      {label}
    </button>
  );

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 20, fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", color: COLORS.text, background: COLORS.bg, minHeight: "100vh" }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0, letterSpacing: -0.3 }}>定价敏感性分析</h1>
        <p style={{ fontSize: 13, color: COLORS.muted, margin: "4px 0 0" }}>底价 + 分成模型 · 示例数据，换成你自己的合作框架</p>
      </div>

      {/* Controls */}
      <div style={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 10, padding: 20, marginBottom: 20 }}>
        <SliderControl
          label="制作底价"
          sublabel="无论项目卖多少，你至少拿到的金额"
          value={basePrice}
          onChange={setBasePrice}
          min={1000}
          max={5000}
          step={500}
          format={formatCurrency}
        />
        <SliderControl
          label="你的分成比例"
          sublabel={`剩余利润中你拿 ${splitPct}%，合作方拿 ${100 - splitPct}%`}
          value={splitPct}
          onChange={setSplitPct}
          min={20}
          max={60}
          step={10}
          format={(v) => v + "%"}
        />
        <SliderControl
          label="预估工时"
          sublabel="类似规模项目的工作小时数"
          value={workHours}
          onChange={setWorkHours}
          min={20}
          max={60}
          step={5}
          format={(v) => v + " 小时"}
        />
      </div>

      {/* Key Metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 20 }}>
        <div style={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 11, color: COLORS.muted, marginBottom: 4 }}>盈亏平衡点</div>
          <div style={{ fontSize: 20, fontWeight: 600 }}>{formatCurrency(Math.round(breakEvenPrice))}</div>
          <div style={{ fontSize: 11, color: COLORS.muted }}>终端报价需 ≥ 此值才能达到 ¥100/h</div>
        </div>
        <div style={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 11, color: COLORS.muted, marginBottom: 4 }}>底价保底时薪</div>
          <div style={{ fontSize: 20, fontWeight: 600 }}>¥{Math.round(basePrice / workHours)}/h</div>
          <div style={{ fontSize: 11, color: COLORS.muted }}>即使项目以底价成交</div>
        </div>
        <div style={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 11, color: COLORS.muted, marginBottom: 4 }}>¥10,000 项目到手</div>
          {(() => {
            const r = calc(10000, basePrice, splitPct, workHours);
            const zone = getZone(r.hourly);
            return (
              <>
                <div style={{ fontSize: 20, fontWeight: 600 }}>{formatCurrency(Math.round(r.yourTotal))}</div>
                <div style={{ fontSize: 11, color: zone.text }}>时薪 ¥{Math.round(r.hourly)} · {zone.label}</div>
              </>
            );
          })()}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 16, background: COLORS.bg, padding: 2, borderRadius: 8 }}>
        <TabButton id="matrix" label="全景矩阵" />
        <TabButton id="detail" label="逐价分析" />
        <TabButton id="compare" label="方案对比" />
      </div>

      {/* Tab Content */}
      {activeTab === "matrix" && (
        <div style={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 10, padding: 16, overflowX: "auto" }}>
          <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 12 }}>
            时薪矩阵（工时 {workHours}h）
            <span style={{ fontWeight: 400, color: COLORS.muted }}> · 行 = 底价×分成 · 列 = 终端报价</span>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr>
                <th style={{ padding: "8px 6px", textAlign: "left", borderBottom: `2px solid ${COLORS.border}`, color: COLORS.muted, fontWeight: 500, minWidth: 110 }}>底价 / 分成</th>
                {[10000, 15000, 20000, 25000, 30000].map((ep) => (
                  <th key={ep} style={{ padding: "8px 6px", textAlign: "center", borderBottom: `2px solid ${COLORS.border}`, color: COLORS.muted, fontWeight: 500 }}>
                    {formatCurrency(ep)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrixData.map((row, i) => {
                const isFirstOfGroup = i % 3 === 0;
                return (
                  <tr key={i} style={{ borderTop: isFirstOfGroup && i > 0 ? `2px solid ${COLORS.border}` : undefined }}>
                    <td style={{ padding: "6px", borderBottom: `1px solid ${COLORS.border}`, fontWeight: isFirstOfGroup ? 600 : 400, fontSize: 11 }}>
                      {isFirstOfGroup && <span>{formatCurrency(row.basePrice)}</span>}
                      {isFirstOfGroup ? " / " : "          "}
                      <span style={{ color: COLORS.muted }}>你{row.split}%</span>
                    </td>
                    {row.cells.map((cell, j) => {
                      const zone = getZone(cell.hourly);
                      const isSelected = row.basePrice === basePrice && row.split === splitPct;
                      return (
                        <td
                          key={j}
                          style={{
                            padding: "6px",
                            textAlign: "center",
                            borderBottom: `1px solid ${COLORS.border}`,
                            background: zone.bg,
                            fontWeight: isSelected ? 700 : 400,
                            outline: isSelected ? "2px solid #292524" : "none",
                            borderRadius: isSelected ? 4 : 0,
                          }}
                        >
                          <div style={{ color: zone.text, fontWeight: 600 }}>¥{Math.round(cell.hourly)}/h</div>
                          <div style={{ color: zone.text, fontSize: 10, opacity: 0.7 }}>{formatCurrency(Math.round(cell.yourTotal))}</div>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: 11, color: COLORS.muted }}>
            <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: COLORS.danger, marginRight: 4 }}></span>低于 ¥100/h 底线</span>
            <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: COLORS.warning, marginRight: 4 }}></span>¥100-150 可接受</span>
            <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: COLORS.safe, marginRight: 4 }}></span>¥150-250 健康</span>
            <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: COLORS.great, marginRight: 4 }}></span>¥250+ 优秀</span>
          </div>
        </div>
      )}

      {activeTab === "detail" && (
        <div style={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>
            逐价分析
            <span style={{ fontWeight: 400, color: COLORS.muted }}> · 底价 {formatCurrency(basePrice)} · 你 {splitPct}% · 工时 {workHours}h</span>
          </div>
          <div style={{ fontSize: 11, color: COLORS.muted, marginBottom: 12 }}>
            盈亏平衡点：终端报价 ≥ {formatCurrency(Math.round(breakEvenPrice))}
          </div>
          {currentCalc.map((row, i) => {
            const zone = getZone(row.hourly);
            return (
              <div key={i} style={{ marginBottom: 12, padding: 12, background: zone.bg, borderRadius: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>终端 {formatCurrency(row.endPrice)}</span>
                  <span style={{ fontWeight: 600, fontSize: 14, color: zone.text }}>¥{Math.round(row.hourly)}/h · {zone.label}</span>
                </div>
                <div style={{ display: "flex", height: 20, borderRadius: 4, overflow: "hidden", marginBottom: 6 }}>
                  <div style={{ width: `${(basePrice / row.endPrice) * 100}%`, background: "#292524", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <span style={{ color: "white", fontSize: 9, fontWeight: 600 }}>底价</span>
                  </div>
                  <div style={{ width: `${(row.remainder * splitPct / 100 / row.endPrice) * 100}%`, background: "#78716C", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <span style={{ color: "white", fontSize: 9 }}>你的分成</span>
                  </div>
                  <div style={{ flex: 1, background: "#D6D3D1", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <span style={{ color: "#57534E", fontSize: 9 }}>合作方的部分</span>
                  </div>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: zone.text }}>
                  <span>你到手 {formatCurrency(Math.round(row.yourTotal))}（底价 {formatCurrency(basePrice)} + 分成 {formatCurrency(Math.round(row.yourTotal - basePrice))}）</span>
                  <span>合作方到手 {formatCurrency(Math.round(row.partnerTotal))}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {activeTab === "compare" && (
        <div style={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 12 }}>
            三种方案对比
            <span style={{ fontWeight: 400, color: COLORS.muted }}> · 工时 {workHours}h · 终端报价 ¥10,000</span>
          </div>
          {[
            { name: "保守方案", desc: "底价 ¥1,000 · 你拿 30%", base: 1000, split: 30 },
            { name: "均衡方案", desc: "底价 ¥2,000 · 你拿 40%", base: 2000, split: 40 },
            { name: "进取方案", desc: "底价 ¥3,000 · 你拿 50%", base: 3000, split: 50 },
          ].map((plan, i) => {
            const scenarios = [
              { label: "低价项目 ¥8K", ep: 8000 },
              { label: "中价项目 ¥15K", ep: 15000 },
              { label: "高价项目 ¥25K", ep: 25000 },
            ];
            return (
              <div key={i} style={{ marginBottom: 16, padding: 16, border: `1px solid ${COLORS.border}`, borderRadius: 8 }}>
                <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2 }}>{plan.name}</div>
                <div style={{ fontSize: 11, color: COLORS.muted, marginBottom: 12 }}>{plan.desc}</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                  {scenarios.map((s, j) => {
                    const r = calc(s.ep, plan.base, plan.split, workHours);
                    const zone = getZone(r.hourly);
                    return (
                      <div key={j} style={{ background: zone.bg, borderRadius: 6, padding: 10, textAlign: "center" }}>
                        <div style={{ fontSize: 10, color: zone.text, marginBottom: 4 }}>{s.label}</div>
                        <div style={{ fontSize: 16, fontWeight: 700, color: zone.text }}>{formatCurrency(Math.round(r.yourTotal))}</div>
                        <div style={{ fontSize: 11, color: zone.text }}>¥{Math.round(r.hourly)}/h</div>
                        <div style={{ fontSize: 10, color: zone.text, opacity: 0.6, marginTop: 2 }}>合作方 {formatCurrency(Math.round(r.partnerTotal))}</div>
                      </div>
                    );
                  })}
                </div>
                <div style={{ marginTop: 8, fontSize: 11, color: COLORS.muted }}>
                  盈亏平衡点：终端 ≥ {formatCurrency(Math.round((() => {
                    const target = 100 * workHours;
                    if (plan.base >= target) return plan.base;
                    return plan.base + (target - plan.base) / (plan.split / 100);
                  })()))}
                </div>
              </div>
            );
          })}

          <div style={{ marginTop: 12, padding: 12, background: "#F5F5F4", borderRadius: 8, fontSize: 12, color: COLORS.muted, lineHeight: 1.6 }}>
            <div style={{ fontWeight: 600, color: COLORS.text, marginBottom: 4 }}>读数指南（示例解读，换成你自己的数字后重新看结论）</div>
            <div>保守方案的安全垫最薄——¥8K 项目时薪仅 ¥{Math.round(calc(8000, 1000, 30, workHours).hourly)}，可能低于底线。但它对合作方最友好，适合关系初期降低对方阻力。</div>
            <div style={{ marginTop: 4 }}>进取方案在多数价位更安全，但合作方在低价项目里分到的金额会明显变少，可能影响对方的推动意愿。</div>
            <div style={{ marginTop: 4 }}>均衡方案通常是折中——低价项目刚过底线，中高价位开始舒适。</div>
          </div>
        </div>
      )}

      {/* Bottom Note */}
      <div style={{ marginTop: 20, padding: 12, fontSize: 11, color: COLORS.muted, lineHeight: 1.6, borderTop: `1px solid ${COLORS.border}` }}>
        <strong>模型假设：</strong>底价是你无论终端成交价如何都拿到的固定金额。分成基数 = 终端报价 − 底价。工具成本（软件会员等）不在此模型中，需另行处理。本分析不含概率分布，所有数字为确定性的"如果…那么…"关系。
      </div>
    </div>
  );
}
