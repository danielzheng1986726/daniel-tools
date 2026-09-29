// Gemini Notebook 批量删除脚本 v2（在 DevTools Console 里跑）
// 用法：
//   1. Chrome 打开 https://notebook.google.com/?authuser=0 ，停在「My notebooks」列表视图
//   2. Cmd+Option+J 打开 Console，粘贴全文回车，弹窗点确定
//   3. 中途想停：在 Console 输入  window.__stopNbDelete = true
//
// v2 改动：每删一个等 5 秒；每次点击之间等 1 秒；
//          某一步没等到就关掉菜单/弹窗重试，不再直接停，连续失败 5 次才停。
// 删除不可恢复。KEEP 里填想保留的标题关键词（包含即保留）。

(async () => {
  const DRY_RUN = true;       // 先跑一遍看清单，确认没问题再改成 false 真删
  const KEEP = [];            // 例：['会议记录', '读书']
  const STEP_DELAY = 5000;    // 每删完一个等多久（毫秒）
  const CLICK_DELAY = 1000;   // 两次点击之间等多久（毫秒）
  const MAX_FAILS = 5;        // 连续失败几次后停止

  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, timeout = 10000) => {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) {
      const v = fn();
      if (v) return v;
      await sleep(200);
    }
    return null;
  };

  const titleOf = row => row.querySelector('td')?.textContent.trim() ?? '';
  const isKept = title => KEEP.some(k => title.includes(k));
  const allRows = () => [...document.querySelectorAll('tr.mat-mdc-row')];
  const rowsToDelete = () => allRows().filter(r => !isKept(titleOf(r)));
  const overlay = () => document.querySelector('.cdk-overlay-container');
  const openDialog = () =>
    [...(overlay()?.querySelectorAll('mat-dialog-container, [role=dialog]') ?? [])]
      .find(d => /delete this notebook/i.test(d.textContent));

  // 关掉残留的菜单/弹窗，回到干净状态
  const resetUI = async () => {
    for (let i = 0; i < 3; i++) {
      document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      overlay()?.querySelector('.cdk-overlay-backdrop')?.click();
      await sleep(500);
    }
  };

  const targets = rowsToDelete().map(titleOf);
  console.log(`共 ${allRows().length} 个 notebook，将删除 ${targets.length} 个`);
  console.table(targets);

  if (DRY_RUN) {
    console.log('DRY_RUN 模式，未删除任何内容。');
    return;
  }
  if (!confirm(`确定永久删除 ${targets.length} 个 notebook？此操作不可恢复。`)) return;

  window.__stopNbDelete = false;
  let done = 0, fails = 0;

  const deleteOne = async row => {
    const title = titleOf(row);

    // 1. 点行尾三个点
    const moreBtn = row.querySelector('button[aria-label="Project Actions Menu"]');
    if (!moreBtn) return `找不到三点按钮：${title}`;
    moreBtn.scrollIntoView({ block: 'center' });
    await sleep(300);
    moreBtn.click();
    await sleep(CLICK_DELAY);

    // 2. 菜单里点 Delete
    const delItem = await waitFor(() =>
      [...(overlay()?.querySelectorAll('[role=menuitem]') ?? [])]
        .find(e => /delete/i.test(e.textContent)));
    if (!delItem) return `菜单里没找到 Delete：${title}`;
    delItem.click();
    await sleep(CLICK_DELAY);

    // 3. 确认弹窗 "Delete this notebook?" 里点 Delete
    const confirmBtn = await waitFor(() => {
      const dlg = openDialog();
      return dlg && [...dlg.querySelectorAll('button')]
        .find(b => b.textContent.trim().toLowerCase() === 'delete');
    });
    if (!confirmBtn) return `没等到确认弹窗：${title}`;
    confirmBtn.click();

    // 4. 等弹窗关掉、这一行从列表消失
    await waitFor(() => !openDialog(), 15000);
    const gone = await waitFor(() => !allRows().some(r => titleOf(r) === title && r === row && r.isConnected), 20000);
    if (!gone) return `删除后该行没消失：${title}`;
    return null;
  };

  while (!window.__stopNbDelete) {
    const row = rowsToDelete()[0];
    if (!row) break;
    const title = titleOf(row);

    const err = await deleteOne(row);
    if (err) {
      fails++;
      console.warn(`✗ 第 ${fails} 次失败（${err}），关掉弹窗后重试`);
      if (fails >= MAX_FAILS) { console.warn(`连续失败 ${MAX_FAILS} 次，停止`); break; }
      await resetUI();
      await sleep(STEP_DELAY);
      continue;
    }

    fails = 0;
    done++;
    console.log(`✓ ${done}/${targets.length} 已删除：${title}`);
    await sleep(STEP_DELAY);
  }

  console.log(`结束：删除 ${done} 个，剩余 ${allRows().length} 个`);
})();
