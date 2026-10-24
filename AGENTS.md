# AGENTS.md — daniel-tools

这是一个**公开仓库**，收 Daniel 顺手做的小工具。一个工具一个文件夹，个人网站 https://danielzheng1986726.github.io/works/ 的「顺手做的」一段链接到这里。

## 硬规矩

1. **公开仓库，只放假数据。** 代码、README、示例里不能出现真实的密钥、token、邮箱、手机号、姓名、本机绝对路径（`/Users/...`）、飞书表 ID、签名 Team ID、个人照片、日记、日历、报价。占位统一用 `replace-with-your-key`、`alice@example.com`、`example.com`。
2. **需要 key 的工具**：代码从环境变量读，文件夹里放 `.env.example`（假值）。
3. **会删除或改写数据的工具**：默认只列清单不动手（DRY_RUN），README 第一段写风险。
4. **从私有仓库搬过来只复制文件，不带 git 历史。**
5. **推送前跑隐私扫描**：`bash scripts/privacy_scan.sh`，零命中才能推。`git push` 等于发布，先问 Daniel。
6. **不收**：碰别人平台规则的（批量投递、爬虫、刷量）、跟 Daniel 求职相关的、不是 Daniel 写的、处理候选人/薪酬/日记/健康数据的。

## 每个工具文件夹的 README 固定写

- 第一行标题：中文名
- 一句痛点（站在 Daniel 角度：……太麻烦，所以写了这个）
- 形态 / 状态（在用、已停）/ 最后改动日期
- 怎么用、依赖、风险与边界
- 迁移说明：原来在哪（只写「私有仓库」或「本机项目」，不写路径）、哪天搬来、搬来时是否重新跑过

新增工具后，同步更新根目录 README 的索引表和网站 `daniel-site/src/content/tools/`。

新增工具走「上架」口令，流程正本在 `~/.agents/skills/shelve-tool/SKILL.md`。根 README 的索引表不要手改，改完网站的 `tools.json` 后跑 `python3 scripts/build_index.py` 重新生成。

## 讲解短片的门槛

不是每个工具都配讲解片。上架时就按下面五条判断，五条都过才进「待做」队列，什么时候做由 Daniel 定；有一条不过就列备选或不做，写一句理由。

1. 在用（「用过一次」「已停」不做；刚上架的到做片前再确认一次还在用）
2. 外行一看就认得这个麻烦（观众是 HR 和小团队，不是程序员）
3. 用之前和用之后的差别，画面上看得出来
4. 45 秒讲得完一件事
5. 能用假数据演示

判断结果和队列记在本机的 HANDOFF.md「讲解片」一节。片子用 guizang-product-video-skill 做，规矩沿用已归档的 tool-promo-videos 项目（竖版 9:16、只有字幕加音乐、片尾不引向 GitHub、画面里只有假数据）。
