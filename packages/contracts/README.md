# Contracts

本目录存放 DramePulse 跨模块共享的数据契约。

当前契约来自 `docs/develop-docs/architecture-design.md` 中定义的三个核心对象：

- `Highlight Asset`：高光资产，回答“哪里值得互动”；
- `Interaction Plan`：互动方案，回答“如何与用户互动”；
- `User Event`：用户行为事件，回答“用户如何反馈”。

## 目录说明

```text
schemas/
```

存放 JSON Schema，用于约束前端、后端和 pipeline 之间交换的数据结构。

```text
examples/
```

存放与 schema 对应的最小示例，便于开发、测试和文档引用。

## 使用原则

- 修改字段前，先确认 `docs/develop-docs/architecture-design.md` 中的模块契约是否也需要同步更新。
- API、fixture、pipeline 输出和前端 mock 数据应优先遵循这里的 schema。
- 字段名保持英文，业务文档说明可以使用中文。
