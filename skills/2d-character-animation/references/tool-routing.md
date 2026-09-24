# 已安装 skills 的分工与来源

阅读基于本次环境中实际安装的版本，整理日期 2026-09-25。以下是原创组合方法，不是第三方 skill 的副本；这些工具均为可选能力，缺少某个 skill 不能让普通已有项目修复无故停止。

| Skill | 合适环节 | 需要补上的判断 |
| --- | --- | --- |
| `img2game2d` | 输入分析、分层契约、pivot 标定、受遮挡区域补全、阶段证据与导出 | 通用 pivot 表不是每个人物的真实关节；先检查视角、裁切和左右含义。既有 rig 只修局部时不重新跑整条生成流水线 |
| `spine-animation` | 需要 Spine 格式时的骨骼/slot/attachment、atlas、坐标转换、预览与导出 | 自动定位和预设 walk 是初值，不证明生理结构、绘制顺序、手型与持物正确；成功导出不等于质量通过 |
| `motion-design` | 预备、主动作、跟随、停顿与表情的叙事节奏 | UI 淡出/缩放建议不能替代真实人物走进门；舞台移动需要完整空间连续性 |
| `gsap-core` / `gsap-timeline` | 路径、并行子时间轴、标签与显式时序 | 位移补间不等于骨骼行走；总时长由最长并行分支决定 |
| `gsap-react` | scoped 生命周期、ref 与动画清理 | `contextSafe` 管理 GSAP 创建上下文，不会自动注销任意 timer、监听器或阻止所有过期业务回调 |
| `gsap-performance` | 批量测量、transform、变化更新与合成层管理 | transform 不保证无 paint，SVG 滤镜尤其需要真机/真场景测量；不可不加判断地给每根骨头加合成层 |
| `imagegen`（环境提供时） | 修手型、接缝、表情或原始立绘 | 指定只改的附件与保留的坐标；审查结果后再进入 bake，不靠生成结果自动改变骨长 |

## 有选择地组合

- **已有 Web 骨架，修肘关节**：本 skill 的结构检查 + 当前源码；需要补画才调用图像工具。不要默认装 Spine runtime。
- **从单张立绘建角色**：img2game2d 的分层/证据流程；若明确要求 Spine 再使用 spine-animation 的格式与导出辅助。
- **角色单独流畅、满场卡顿**：先使用性能测量与现有渲染后端优化；不是重新生成整套人物。
- **按钮/纯 UI 动效**：用项目原有 UI 动画工具；本 skill 不要求为普通按钮建立人体骨架。

实际调用外部 skill 时读取它当前的 SKILL.md；只继承当前环节必要的步骤。不要照搬固定数量的预设、通用人体 pivot 或本案例的全部美术限制。

## 官方参考与许可边界

- [Spine Runtimes License](https://esotericsoftware.com/spine-runtimes-license)：引入官方 runtime 前核对适用授权和版本。生成兼容 JSON 与集成 runtime 是两件事；改为 CDN 引用不自动免除许可义务。不在个人 skills 仓库附带 runtime。
- [GSAP React 官方文档](https://gsap.com/resources/React/)：说明 scoped context、useGSAP 与回调中创建的动画如何进入清理上下文。普通事件监听器、计时器和业务有效性仍由应用管理。
- [GSAP 官方 skills](https://github.com/greensock/gsap-skills)：具体工具指导的上游入口；安装版可能与上游不同，按当前文件核对。
- [Pillow ImageTransform](https://pillow.readthedocs.io/en/stable/reference/ImageTransform.html)：仿射变换的逆映射约定。
- 本地 `img2game2d` 声明 Apache-2.0，`motion-design` 声明 MIT（LottieFiles），GSAP skills 声明 MIT。本仓库未复制它们的文件。`spine-animation` 的本次安装来源记录为 `haxqer/skills`，未以其名称推断任何 runtime 授权。

检查器由本仓库独立编写。第三方工具的许可不延伸为用户素材的许可，也不意味着公开这个技能需要公开项目美术或代码。
