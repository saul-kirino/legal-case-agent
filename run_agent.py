#!/usr/bin/env python3
"""
【Agent 编排层】负责协调 RAG 检索与大模型生成。
架构说明：
1. 接收来自 qq_legal_bot 的用户提问。
2. 通过 subprocess 调用 case_retriever.py，实现 Python 3.10 环境的隔离调用。
3. 将检索结果组装成 Prompt，调用 NanoBot Serve 提供的 OpenAI 兼容接口。
"""
import sys
import requests
from case_retriever import search_cases

# ========== 配置 ==========
NANOBOT_API_URL = "http://127.0.0.1:8900/v1/chat/completions"
MODEL = "qwen-max"
TEMPERATURE = 0.1
TIMEOUT = 120

def build_prompt(user_question: str, cases: str) -> str:
    """将用户问题和检索到的案例拼接为 prompt"""
    return f"""请根据以下真实判例，回答用户的问题。

用户问题：
{user_question}

检索到的相似案例：
{cases}

请按照以下要求组织回答：
1. 以表格形式列出相似案例（包含案情要点、判决结果、审理法院）。
2. 根据这些案例，给出量刑区间分析。
3. 末尾必须附上声明：“⚠️ 声明：以上分析仅基于历史判例数据的统计参考，不构成法律建议，请咨询专业律师。”
"""

def ask_nanobot(prompt: str) -> str:
    """调用 NanoBot API 生成回答（只使用单条 user 消息）"""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": f"你是一个专业的法律案例分析助手。\n\n{prompt}"}
        ],
        "temperature": TEMPERATURE,
        "stream": False
    }
    try:
        resp = requests.post(
            NANOBOT_API_URL,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=TIMEOUT
        )
        if resp.status_code != 200:
            return f"❌ API 返回错误状态码 {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.ConnectionError:
        return "❌ 无法连接到 NanoBot API。请确保已执行 `nanobot serve -c case_agent_config.json`"
    except Exception as e:
        return f"❌ API 调用失败: {str(e)[:300]}"

def run(user_query: str):
    """主流程"""
    print(f"🔍 正在检索真实案例...")
    cases = search_cases(user_query, top_k=5)
    if not cases or "未找到" in cases or cases.startswith("❌"):
        print("⚠️ 未找到相似案例，使用模型自有知识回答。")
        prompt = f"用户问题：{user_query}\n\n注意：当前未从知识库检索到案例，请基于一般法律知识回答，并提醒用户此为参考。"
    else:
        prompt = build_prompt(user_query, cases)

    print("🤖 正在调用大模型生成回答...")
    answer = ask_nanobot(prompt)
    print("\n" + "=" * 60)
    print(answer)
    print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python run_agent.py \"您的法律问题\"")
        sys.exit(1)

    query = sys.argv[1]
    run(query)