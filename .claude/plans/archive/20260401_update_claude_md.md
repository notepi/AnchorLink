# 更新 CLAUDE.md

## Context

用户确认 PRD 文档测试通过，需要更新 CLAUDE.md：
1. 添加 docs/prd.md 到文档索引
2. 确认协作流程的 plan 路径在项目目录下

## 修改内容

### 文档索引更新

在 `## 文档索引` 部分添加 prd.md：

```markdown
| 文档 | 内容 |
|------|------|
| docs/prd.md | 产品需求文档（PRD） |
| docs/file_structure.md | 项目目录结构 |
| docs/field_glossary.md | 指标字典（85个字段） |
| docs/pool_governance.md | 股票池治理规范 |
```

### 协作流程确认

当前路径 `.claude/plans/active/` 是相对路径，指向项目根目录下的 `.claude/plans/active/`，已经正确。

## 文件修改

| 文件 | 操作 |
|------|------|
| CLAUDE.md | 更新文档索引 |

## 验证

确认 CLAUDE.md 文档索引包含 prd.md