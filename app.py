# app.py - 纯 Streamlit 版本
import streamlit as st
import os

# ========== 从 Streamlit Secrets 设置环境变量 ==========
if hasattr(st, 'secrets'):
    if "ZHIPU_API_KEY" in st.secrets:
        os.environ["ZHIPU_API_KEY"] = st.secrets["ZHIPU_API_KEY"]
    if "ZHIPU_BASE_URL" in st.secrets:
        os.environ["ZHIPU_BASE_URL"] = st.secrets["ZHIPU_BASE_URL"]
    if "ZHIPU_MODEL" in st.secrets:
        os.environ["ZHIPU_MODEL"] = st.secrets["ZHIPU_MODEL"]
    print("✅ 已从 Secrets 设置环境变量")

# 提前初始化session_state，避免按钮赋值空报错
if "msg" not in st.session_state:
    st.session_state.msg = ""
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "👋 你好！我是个人学习助手，有什么可以帮你的？"}]

from agent_lite import main_agent, TaskAgent, PlanAgent

st.set_page_config(page_title="📚 个人学习助手", page_icon="📚")

st.title("📚 个人学习助手")
st.caption("🤖 三Agent协同工作 · 支持任意课程自由输入")

# 快捷按钮
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

# 显示历史聊天记录
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# 消息处理核心函数
def process_message(prompt):
    prompt = prompt.strip()
    if prompt == "查看任务":
        ta = TaskAgent()
        tasks = ta.list_tasks()
        if not tasks:
            return "📭 当前没有未完成任务 🎉"
        result = "📋 当前任务列表：\n"
        for i, (tid, c, t, d) in enumerate(tasks, 1):
            result += f"{i}. 【{c}】{t}（截止：{d}）\n"
        return result
    if prompt in ["生成计划", "学习计划"]:
        pa = PlanAgent()
        return pa.make_plan()
    try:
        return main_agent(prompt)
    except Exception as e:
        return f"❌ 处理失败：{str(e)}"

# 优先处理快捷按钮赋值的消息
if st.session_state.msg and st.session_state.msg.strip():
    prompt = st.session_state.msg.strip()
    # 清空缓存指令，防止重复触发
    st.session_state.msg = ""
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            response = process_message(prompt)
        st.write(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

# 底部聊天输入框
if prompt := st.chat_input("输入指令..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            response = process_message(prompt)
        st.write(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
