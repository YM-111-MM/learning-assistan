# app.py - Streamlit 版本（不依赖 gradio）
import streamlit as st
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

# 聊天历史
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "👋 你好！我是个人学习助手，有什么可以帮你的？"}]

# 显示历史
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# 特殊指令快速处理
def process_message(prompt):
    if prompt.strip() == "查看任务":
        ta = TaskAgent()
        tasks = ta.list_tasks()
        if not tasks:
            return "📭 当前没有未完成任务 🎉"
        result = "📋 当前任务列表：\n"
        for i, (tid, c, t, d) in enumerate(tasks, 1):
            result += f"{i}. 【{c}】{t}（截止：{d}）\n"
        return result
    if prompt.strip() in ["生成计划", "学习计划"]:
        pa = PlanAgent()
        return pa.make_plan()
    try:
        return main_agent(prompt)
    except Exception as e:
        return f"❌ 处理失败：{e}"

# 输入
if prompt := st.chat_input("输入指令..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            response = process_message(prompt)
        st.write(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
