# app.py - 纯 Streamlit 优化修复版
import streamlit as st
import os

# ========== 从 Streamlit Secrets 设置环境变量（必须最先执行） ==========
if hasattr(st, 'secrets'):
    if "ZHIPU_API_KEY" in st.secrets:
        os.environ["ZHIPU_API_KEY"] = st.secrets["ZHIPU_API_KEY"]
    if "ZHIPU_BASE_URL" in st.secrets:
        os.environ["ZHIPU_BASE_URL"] = st.secrets["ZHIPU_BASE_URL"]
    if "ZHIPU_MODEL" in st.secrets:
        os.environ["ZHIPU_MODEL"] = st.secrets["ZHIPU_MODEL"]
    print("✅ 已从 Secrets 设置环境变量")

# ========== 提前初始化会话缓存，避免按键报错 ==========
if "msg" not in st.session_state:
    st.session_state.msg = ""
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "👋 你好！我是个人学习助手，支持添加任务、查询知识点、生成学习计划。\n示例：添加音乐课程，截止后天"}]

# 环境变量加载完成后再导入业务模块
from agent_lite import main_agent, TaskAgent, PlanAgent

# 页面基础配置
st.set_page_config(page_title="📚 个人学习助手", page_icon="📚")
st.title("📚 个人学习助手")
st.caption("🤖 三Agent协同工作 · 支持任意课程简洁指令输入")

# 顶部快捷功能按钮
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("📝 添加任务", use_container_width=True):
        st.session_state.msg = "添加人工智能课程任务，完成代码，截止今天"
with col2:
    if st.button("📖 查询笔记", use_container_width=True):
        st.session_state.msg = "什么是列表推导式"
with col3:
    if st.button("📅 生成计划", use_container_width=True):
        st.session_state.msg = "生成学习计划"
with col4:
    if st.button("📋 查看任务", use_container_width=True):
        st.session_state.msg = "查看任务"

# 渲染历史聊天记录
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# 消息统一处理函数
def process_message(prompt):
    prompt = prompt.strip()
    # 内置固定指令优先本地处理，减少大模型调用
    if prompt == "查看任务":
        ta = TaskAgent()
        tasks = ta.list_tasks()
        ta.close()
        if not tasks:
            return "📭 当前没有未完成任务 🎉"
        result = "📋 当前任务列表：\n"
        for i, (tid, course, task, deadline) in enumerate(tasks, 1):
            result += f"{i}. 【{course}】{task}（截止：{deadline}）\n"
        return result
    if prompt in ["生成计划", "学习计划"]:
        pa = PlanAgent()
        return pa.make_plan()
    # 通用指令交给意图解析Agent
    try:
        return main_agent(prompt)
    except Exception as e:
        return f"❌ 处理失败：{str(e)}"

# 自动执行快捷按钮生成的预设消息
if st.session_state.msg and st.session_state.msg.strip():
    user_text = st.session_state.msg.strip()
    st.session_state.msg = ""  # 清空防止重复执行
    # 写入对话记录并渲染
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.write(user_text)
    # 调用助手回复
    with st.chat_message("assistant"):
        with st.spinner("AI思考中..."):
            reply = process_message(user_text)
        st.write(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

# 底部输入框，支持自由输入自定义指令
if user_input := st.chat_input("输入指令，例如：添加音乐课程，截止后天"):
    # 保存用户消息
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)
    # 生成并展示回答
    with st.chat_message("assistant"):
        with st.spinner("AI思考中..."):
            reply = process_message(user_input)
        st.write(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
