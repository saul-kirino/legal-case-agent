---
name: legal-case-search
description: "从法律案例知识库中检索真实判例。当用户询问法律问题、罪名、量刑、判决时使用此技能。支持盗窃、抢劫、诈骗、自首、初犯、缓刑、罚金等案件类型。"
always: false
metadata: '{"nanobot.requires.bins": ["python"]}'
---

# 法律案例检索技能

当用户问题涉及法律案件或量刑时，必须立即执行本技能,从案例库中检索真实判例。。

## 执行步骤

1. 从用户输入中提取核心案情关键词作为查询词。例如：

   - 用户："盗窃8000元自首初犯怎么判"
   - 查询词："盗窃 8000元 自首 初犯"

2. 使用 `exec` 工具执行以下命令，将 `{query}` 替换为查询词，`{top_k}` 设为 5：

   ```bash
   python D:\code\langchat\Langchain-Chatchat-master\libs\chatchat-server\chatchat\legal-case-agent\case_retriever.py "{query}" 5
   ```

3.如果命令输出包含案例信息，按系统提示词的格式整理为表格、量刑区间，并附上免责声明。

4.如果输出包含 `❌` 或 `未找到`，则回复“暂时未找到相关案例，请尝试更具体的案情描述。”

## 重要约束

- ✅ **必须真实执行上述命令**，禁止编造任何案例数据
  - ✅ **必须在回答末尾附加免责声明**
  - ❌ **禁止在未执行检索前给出任何量刑预测**
  - ❌ **禁止自称律师或提供正式法律意见**

  ## 示例

  **用户提问**：我朋友盗窃了8000元，有自首，初犯，会判多久？

  **正确流程**：
  1. 提取查询词："盗窃 8000元 自首 初犯"
  2. 执行：`python D:\code\langchat\Langchain-Chatchat-master\libs\chatchat-server\chatchat\legal-case-agent\case_retriever.py "盗窃 8000元 自首 初犯" 5`
  3. 等待命令返回真实案例
  4. 格式化输出并附加免责声明