#!/usr/bin/env python3
"""
【应用层：法律咨询 QQ 机器人】
职责：负责用户交互、业务逻辑编排与 API 调用。
架构设计：采用“规则过滤 + RAG 检索 + LLM 生成”的三段式链路，确保回答的专业性与可溯源性。
"""
import asyncio
import re
import sys
import requests
from case_retriever import search_cases

# ========== 配置 ==========
QQ_APPID = "1904007122"
QQ_SECRET = "uBTm6Ql7UrFe4Z5cAiHrS3fIvZEuaHzh"
NANOBOT_API_URL = "http://127.0.0.1:8900/v1/chat/completions"
MODEL = "qwen-max"
TEMPERATURE = 0.1  # 低温度设置，确保法律回答的严谨性与一致性
TIMEOUT = 120

# 【业务逻辑】法律关键词白名单
# 策略：通过简单的规则匹配过滤掉无关闲聊，减少不必要的 API 调用开销
LEGAL_KEYWORDS = [
    "罪", "判", "刑", "起诉", "盗窃", "抢劫", "诈骗",
    "自首", "初犯", "缓刑", "罚金", "判决", "案例",
    "立案", "公诉", "上诉", "辩护"
]

def is_legal_question(text: str) -> bool:
    """判断用户输入是否属于法律咨询范畴"""
    return any(kw in text for kw in LEGAL_KEYWORDS)

def ask_nanobot(prompt: str) -> str:
    """
    【LLM 交互层】调用 NanoBot Serve 提供的 OpenAI 兼容接口。
    面试亮点：使用标准的 HTTP POST 请求，便于后续迁移到任何支持 OpenAI 协议的云端服务。
    """
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
            return f"❌ AI 服务返回错误状态码 {resp.status_code}，请稍后重试。"
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ AI 服务暂时不可用：{str(e)[:200]}"

def build_prompt(user_question: str, cases: str) -> str:
    """
    【Prompt 工程】构建结构化提示词。
    核心技巧：通过 Few-shot 思想和明确的格式约束（表格、免责声明），引导 LLM 输出标准化内容。
    """
    return f"""请根据以下真实判例，回答用户的问题。

用户问题：
{user_question}

检索到的相似案例：
{cases}

请按照以下要求组织回答：
1. 以表格形式列出相似案例（包含案情要点、判决结果、审理法院）。
2. 根据这些案例，给出量刑区间分析。
3. 末尾必须附上声明：“⚠️ 声明：以上分析仅基于历史判例数据的统计参考，不构成法律建议，请咨询专业律师。”
4. 请务必保留检索到的案例中的被告人姓名、完整案情摘要和审理法院，不要省略或概括。
"""

def get_legal_reply(user_message: str) -> str:
    """
    【业务编排】处理法律问题的完整同步流程。
    1. 调用 RAG 引擎获取真实判例。
    2. 组装 Prompt 并调用大模型生成最终回复。
    """
    # 1. 检索真实案例
    cases = search_cases(user_message, top_k=5)
    if not cases or "未找到" in cases or cases.startswith("❌"):
        # 检索失败，仍尝试回答但告知无案例支持
        prompt = f"用户问题：{user_message}\n\n注意：当前未从知识库检索到案例，请基于一般法律知识回答，并提醒用户此为参考。"
    else:
        prompt = build_prompt(user_message, cases)

    # 2. 调用 API
    return ask_nanobot(prompt)

# ========== QQ 机器人部分 (使用 botpy) ==========
try:
    import botpy
    from botpy import Client, Intents
    from botpy.message import C2CMessage, GroupMessage
except ImportError:
    print("请先安装 qq-botpy：pip install qq-botpy")
    sys.exit(1)

class LegalBot(Client):
    def __init__(self, intents):
        super().__init__(intents=intents)
        self._msg_seq = 0  # 初始化消息序列号

    def _next_seq(self) -> int:
        """生成递增的消息序列号"""
        self._msg_seq += 1
        return self._msg_seq

    async def on_ready(self):
        print(f"✅ 法律机器人已上线：{self.robot.name}")

    async def on_c2c_message_create(self, message: C2CMessage):
        await self._handle_message(message, is_group=False)

    async def on_group_at_message_create(self, message: GroupMessage):
        await self._handle_message(message, is_group=True)

    async def _handle_message(self, message, is_group: bool):
        content = message.content.strip()
        if not content:
            return
        # 1. 前置过滤：非法律问题直接忽略，节省算力
        if not is_legal_question(content):
            return

        # 2. 发送“正在处理”的 Ack 响应，提升用户体验
        ack_content = "🔍 正在检索真实判例，请稍候..."
        if is_group:
            await self.api.post_group_message(
                group_openid=message.group_openid,
                msg_type=0,
                content=ack_content,
                msg_id=message.id,
                msg_seq=self._next_seq()  # 关键修改：使用动态序列号
            )
        else:
            user_id = getattr(message.author, "user_openid", None) or getattr(message.author, "id", None)
            await self.api.post_c2c_message(
                openid=user_id,
                msg_type=0,
                content=ack_content,
                msg_id=message.id,
                msg_seq=self._next_seq()  # 关键修改：使用动态序列号
            )

        # 3. 【并发优化】将耗时的同步检索+生成任务放入线程池执行，避免阻塞异步事件循环
        reply = await asyncio.to_thread(get_legal_reply, content)

        # 4. 发送正式回复
        if is_group:
            await self.api.post_group_message(
                group_openid=message.group_openid,
                msg_type=0,
                content=reply,
                msg_id=message.id,
                msg_seq=self._next_seq()  # 关键修改：使用动态序列号
            )
        else:
            user_id = getattr(message.author, "user_openid", None) or getattr(message.author, "id", None)
            await self.api.post_c2c_message(
                openid=user_id,
                msg_type=0,
                content=reply,
                msg_id=message.id,
                msg_seq=self._next_seq()  # 关键修改：使用动态序列号
            )
# ========== 启动 ==========
if __name__ == "__main__":
    # 配置意图：同时监听公域消息（群聊）和私域消息（单聊）
    intents = Intents(public_messages=True, direct_message=True)
    bot = LegalBot(intents=intents)
    print("🚀 启动法律咨询 QQ 机器人...")
    bot.run(appid=QQ_APPID, secret=QQ_SECRET)