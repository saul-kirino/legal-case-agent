# case_retriever.py
"""
【检索引擎桥接层】
职责：作为 Agent 与旧版 RAG 引擎之间的桥梁。
架构设计：通过 subprocess 跨环境调用 Python 3.10 的 LangChain-Chatchat 检索脚本，
实现新旧项目依赖解耦，确保在 NanoBot (Python 3.12) 环境下能稳定调用成熟的法律检索能力。
"""
import subprocess
import json
import sys
from typing import Dict

# 【关键配置】旧项目的 Python 解释器路径
OLD_PROJECT_PYTHON = r"C:\Users\kirino\.conda\envs\chat\python.exe"

# 检索脚本路径：指向经过优化的混合检索引擎
SEARCH_SCRIPT = r"D:\code\langchat\Langchain-Chatchat-master\libs\chatchat-server\chatchat\legal_case_search.py"


def search_cases(query: str, top_k: int = 5) -> str:
    """
    【核心检索逻辑】供上层 Agent 或子进程调用。

    技术亮点：
    1. 采用 RRF (Reciprocal Rank Fusion) 融合向量检索与关键词检索。
    2. 引入 BGE-Reranker 进行精排，解决法律专有名词匹配不准的问题。
    3. 包含完整的异常处理与超时保护，确保机器人服务的稳定性。
    """
    try:
        # 1. 构建跨环境调用命令
        cmd = [
            OLD_PROJECT_PYTHON,
            SEARCH_SCRIPT,
            query,
            str(top_k)
        ]

        # 2. 执行子进程（工程优化点：设置 timeout 防止检索卡死导致整个服务不可用）

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            encoding='utf-8',
            errors='ignore'  # 忽略无法解码的字符
        )

        # 3. 检查执行状态（体现系统的健壮性）

        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else "未知错误"
            return f"❌ 检索执行失败 (返回码: {result.returncode}):\n{error_msg[:500]}"

        # 4. 检查是否有输出
        if not result.stdout or not result.stdout.strip():
            return "❌ 检索脚本没有返回任何输出"

        # 5. 解析 JSON 结果
        try:
            response = json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            return f"❌ 结果解析失败: {e}\n原始输出: {result.stdout[:500]}"

        if not response.get('success'):
            return f"❌ {response.get('message', '未知错误')}"

        data = response.get('data', [])
        if not data:
            return "未在知识库中找到相似案例。"

        # 6. 格式化输出：将结构化数据转换为 LLM 易于理解的 Markdown 格式
        # 这种“中间表示”能有效减少大模型在处理长文本时的幻觉

        formatted = "## 检索到的相似案例\n\n"

        for i, case in enumerate(data, 1):
            formatted += f"**案例 {i}**（相似度: {case.get('score', 'N/A')}）\n"
            formatted += f"- 案情摘要：{case.get('facts', '无')[:200]}...\n"
            formatted += f"- 被告人：{case.get('defendant', '无')}\n"
            formatted += f"- 罪名：{case.get('accusation', '无')}\n"
            formatted += f"- 相关法条：{case.get('articles', '无')}\n"
            formatted += f"- 判决结果：{case.get('sentence', '无')}\n"
            if case.get('fine'):
                formatted += f"- 罚金：{case['fine']}\n"
            formatted += "\n"
        # 调试日志：方便在终端观察工具是否被成功触发
        print("【DEBUG：工具调用成功，返回真实案例】", file=sys.stderr)
        return formatted

    except subprocess.TimeoutExpired:
        return "❌ 检索超时（超过60秒）"
    except FileNotFoundError:
        return f"❌ 找不到 Python 解释器: {OLD_PROJECT_PYTHON}\n请检查路径配置"
    except Exception as e:
        import traceback
        return f"❌ 检索失败: {str(e)}\n{traceback.format_exc()}"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("query", type=str, help="案情描述")
    parser.add_argument("top_k", type=int, nargs="?", default=5, help="返回案例数")
    args = parser.parse_args()
    print(search_cases(args.query, args.top_k))