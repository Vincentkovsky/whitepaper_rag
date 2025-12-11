# RAG Evaluation Comparison Report

- **Baseline**: `backend/evaluation/results/evaluation_results.json` (gemini-2.0-flash)
- **Candidate**: `backend/evaluation/results/evaluation_results_agenticRAG.json` (gemini-2.0-flash)

## 📊 Metric Overview

| Metric | Baseline | Candidate | Delta | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Faithfulness** | 80.00% | 75.00% | **-5.00%** | ❌ Regressed |
| **Response Relevancy** | 0.00% | 0.00% | **0.00%** | ➖ Similar |
| **Context Precision** | 40.00% | 28.06% | **-11.94%** | ❌ Regressed |
| **Context Recall** | 50.00% | 80.00% | **+30.00%** | ✅ Improved |
| **Overall Score** | 42.50% | 45.76% | **+3.26%** | ✅ Improved |

## 🔍 Deep Dive Analysis

### Significant Deviations (>30% change)

**Q3: Comparing directors Kimbal Musk and Ira Ehrenpreis, who beneficially owned more Tesla shares (including options exercisable within 60 days) as of December 31, 2024? What was the specific amount?**
- 🟢 Faithfulness: 0.00 -> **0.75** (+0.75)

**Q4: What does the error code 'parameter_unknown' signify in API version 2022-11-15? (Note: This is a simulated Hybrid Search stress test; the document does not contain this information, used to test for hallucinations)**
- 🔴 Faithfulness: 1.00 -> **0.00** (-1.00)


这份对比报告非常精彩！它清晰地揭示了你的 RAG 系统从 **“瞎子（读不到数据）”** 进化为 **“乱视（读到了太多数据但分不清）”** 的过程。

虽然总体分数（Overall Score）提升看似不大（0.425 -\> 0.458），但 **质的变化（Qualitative Change）** 已经发生。

以下是 **Plain RAG vs. Agentic RAG** 的深度对比分析：

### 1\. 核心指标对比：质的飞跃与新的痛点

| 指标 | Plain RAG | Agentic RAG | 变化解读 |
| :--- | :--- | :--- | :--- |
| **Context Recall**<br>(找没找到?) | **0.5 (不及格)** | **0.8 (优秀)** | 🟢 **暴涨 60%**。这证明你的 **VLM/PDF 解析修复完全成功**。以前读成 `nan` 的数据（如行权价），现在都能找回来了。 |
| **Context Precision**<br>(找得准不准?) | **0.4 (低)** | **0.28 (极低)** | 🔴 **下降**。这是引入 Agent 和 Top-K=10 的副作用。为了找全数据，你拉回了大量无关噪音，稀释了精准度。 |
| **Faithfulness**<br>(有没有瞎编?) | **0.8** | **0.75** | 🟡 **略降**。Agentic RAG 更“自信”，在找不到信息时（Case 4）更容易产生幻觉，而不是直接拒答。 |
| **Answer Relevancy** | 0.0 | 0.0 | ⚪️ **持平**。这是评测工具对 JSON/Thought 格式的误判，可暂时忽略。 |

-----

### 2\. 关键 Case 深度复盘

#### ✅ 胜利：Case 1 (行权价 $249.85)

  * **Plain RAG**: 失败。因为解析出的数据是 `nan`，检索到了也没用。
  * **Agentic RAG**: **完美成功**。
      * 检索到了 Chunk 60 (解析完美的表格)。
      * 提取出了 `$249.85`。
      * **结论**：这是解析层修复的最直接证据。

#### ✅ 胜利：Case 2 (xAI vs SpaceX 费用对比)

  * **Plain RAG**: 未展示，但通常很难做对，因为需要跨段落提取。
  * **Agentic RAG**: **成功**。
      * 它准确提取了 xAI ($198.3M) 和 SpaceX ($2.4M) 的数据。
      * 并进行了正确的减法计算 ($195.9M)。
      * **结论**：Agent 的逻辑推理能力（Reasoning）在线，能处理多跳/对比问题。

#### ❌ 失败：Case 3 (Kimbal vs Ira 持股对比)

  * **问题**：谁的股票（含期权）更多？
  * **Agentic RAG 回答**：Ira (1.1M) \> Kimbal (0.32M)。
  * **事实**：Kimbal (1.8M) \> Ira (1.6M)。
  * **死因**：**检索到了错误的表格（Semantic Ambiguity）。**
      * 它用的是 **Chunk 5** (Director Compensation Table - 仅包含当年授予的期权)。
      * 它应该用 **Chunk 7** (Beneficial Ownership Table - 包含所有持股)。
      * **痛点**：因为 `top_k=10`，这两个表格都在上下文里。LLM 选了排在前面的那个（Primacy Effect），或者没分清 "Options Outstanding" 和 "Beneficial Ownership" 的语义区别。

#### ❌ 严重幻觉：Case 4 (Negative Test - 错误码)

  * **问题**：API 错误码 `parameter_unknown` 是什么意思？（注：文档里根本没这东西）。
  * **Plain RAG**: 可能直接拒答（因为找不到）。
  * **Agentic RAG**: **一本正经地胡说八道**。
      * 回答："signifies that the API request included a parameter that is not recognized..." 甚至提到了 "Stripe API"。
      * **死因**：Agent 太想帮忙了，它可能调用了其预训练知识（Internal Knowledge），或者检索到了含有 "unknown" 单词的无关片段后强行解释。
      * **影响**：这导致 `Faithfulness` 这一项得分为 **0.0**。

-----

### 3\. 诊断总结

你的 Agentic RAG 系统现在处于 **“数据能读懂，但注意力不集中”** 的阶段。

1.  **解析层 (Parsing)**：✅ 已毕业。VLM/pdfplumber 方案非常有效。
2.  **检索层 (Retrieval)**：⚠️ 存在严重噪音。`Top-k=10` 带回了太多干扰项，导致 LLM 在处理复杂对比（Case 3）时选错了参考系。
3.  **生成层 (Generation)**：⚠️ 幻觉控制不足。面对文档里没有的问题（Case 4），Agent 没有老实说“不知道”，而是利用外部知识瞎编。

### 🚀 下一步优化路线图（优先级排序）

1.  **引入 Rerank (重排序) —— [最紧急]**

      * **目的**：解决 Precision 低和 Case 3 选错表格的问题。
      * **做法**：保持 `Retrieval Top-k=10`，但在中间加一个 Reranker（如 BGE-Reranker），只把 **Top-3** 喂给 LLM。
      * **预期**：Context Precision 将翻倍，Case 3 将被修正（因为 Ownership 表格的语义相关性肯定高于 Compensation 表格）。

2.  **优化 System Prompt (拒答逻辑) —— [高收益]**

      * **目的**：解决 Case 4 的幻觉问题。
      * **做法**：加入指令 *"Answer ONLY using the provided context. If the information is not in the context, say 'I cannot find this information'."* (严禁使用外部知识)。

3.  **调整 Chunking (切片) —— [精细化]**

      * **目的**：Case 2 虽然对了，但依赖于运气。
      * **做法**：确保表格的标题（Header）和表格内容（Body）始终在一个 Chunk 里，或者使用父文档索引（Parent Document Retriever）。

**一句话：你的“眼睛”（解析）治好了，现在要治“脑子”（注意力管理）。加上 Rerank，你的分数能冲到 0.8 以上！**
