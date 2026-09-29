# 接单定价计算器

跟合作方谈"底价 + 分成"这种报价模式时，脑子里心算不同报价档位下自己到手多少、时薪多少太累，所以写了这个：拖动底价、分成比例、预估工时三个滑块，实时看矩阵、逐价分析和方案对比。

- 形态：React 组件
- 状态：已停（一次性用于某次报价谈判，之后没再维护）
- 最后改动：2026-03-06

## 怎么用

最简单的方式是丢进 [CodeSandbox](https://codesandbox.io/) 或 [StackBlitz](https://stackblitz.com/) 的 React 模板，把 `PricingSensitivity.jsx` 的内容替换掉默认的 `App.jsx`，直接就能跑（组件是 default export，无需额外路由）。

本地跑的话，在任意已有的 React 项目里：

```bash
cp PricingSensitivity.jsx src/PricingSensitivity.jsx
```

然后在你的入口文件里引入并渲染：

```jsx
import PricingSensitivity from "./PricingSensitivity";

export default function App() {
  return <PricingSensitivity />;
}
```

组件不依赖任何第三方库（纯 `useState`/`useMemo` + 内联样式），装好 React + ReactDOM 即可跑。

## 依赖

- React 18+（`useState`、`useMemo`），无其他第三方包
- 一个能跑 JSX 的构建环境（Vite / Create React App / CodeSandbox 等任一即可）

## 风险与边界

- 纯前端计算器，不读写任何外部数据，无副作用，无特别风险。
- 代码里所有底价、分成比例、终端报价的默认值和档位（比如 ¥1,000/2,000/3,000 底价、30%/40%/50% 分成、¥10,000 报价）都是示例数，用之前先改成自己的真实参数。
- 「读数指南」里的文字解读是基于示例数字写的说明性文字，换了参数之后这段话的具体结论不会自动更新（数字会更新，但文字描述是写死的），仅供参考怎么读这个工具，不代表真实建议。

## 迁移说明

2026-09-29 从 Daniel 的私有仓库复制过来（不带原 git 历史），文件名从 `定价敏感性分析.jsx` 改为 `PricingSensitivity.jsx`。迁移时做了：把代码里真实的合作方姓名换成「合作方」，真实项目名（原本出现在某个滑块的说明文字里）换成通用描述，真实的底价/分成比例/终端报价默认值和档位全部换成示例数（底价 1000/2000/3000、分成 30%/40%/50%、报价 10000 附近），内部变量名 `danielTotal`/`qiuTotal` 改成通用的 `yourTotal`/`partnerTotal`，顶部加了「示例数，换成你自己的」注释。计算逻辑本身未改动。迁移时做了括号配平的静态检查（当时机器上没有现成的 JSX 语法检查工具，没有跑完整的 JSX/Babel 语法校验，也没有在浏览器里重新渲染过）。
