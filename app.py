import gradio as gr
# 导入原有三Agent调度核心函数
from agent import main_agent

def chat_with_agent(message, history):
    # history为对话历史，直接传入用户消息给多Agent调度函数
    res = main_agent(message)
    return res

# 一键生成网页对话界面
gr.ChatInterface(
    fn=chat_with_agent,
    title="📚 个人学习助手",
    description="支持功能：添加任意课程任务、查询课堂笔记、自动生成今日学习计划、查看全部待办任务"
).launch(server_name="127.0.0.1")