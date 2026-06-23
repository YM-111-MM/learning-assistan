# app.py - 使用轻量版 agent_lite
import gradio as gr
from agent_lite import main_agent, TaskAgent, PlanAgent
import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"
# ========== 辅助函数 ==========
def show_tasks():
    ta = TaskAgent()
    tasks = ta.list_tasks()
    if not tasks:
        return "📭 当前没有未完成任务 🎉"
    result = "📋 当前任务列表：\n"
    for i, (tid, c, t, d) in enumerate(tasks, 1):
        result += f"{i}. 【{c}】{t}（截止：{d}）\n"
    return result

def make_plan():
    pa = PlanAgent()
    return pa.make_plan()

# ========== 聊天函数 ==========
def chat_with_agent(message, history):
    if not message:
        return ""
    
    # 特殊指令快速响应
    if message.strip() == "查看任务":
        return show_tasks()
    if message.strip() in ["生成计划", "学习计划"]:
        return make_plan()
    
    # 调用主Agent
    try:
        return main_agent(message)
    except Exception as e:
        return f"❌ 处理失败：{e}"

# ========== 创建界面 ==========
def create_interface():
    with gr.Blocks(
        title="📚 个人学习助手",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container { max-width: 800px; margin: auto; }
        .header { text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; color: white; }
        .footer { text-align: center; padding: 10px; color: #666; font-size: 12px; }
        """
    ) as demo:
        # 头部
        gr.HTML("""
        <div class="header">
            <h1>📚 个人学习助手</h1>
            <p>🤖 三Agent协同工作 · 支持任意课程自由输入</p>
        </div>
        """)
        
        # 快捷按钮
        with gr.Row():
            btn_add = gr.Button("📝 添加任务", variant="primary")
            btn_query = gr.Button("📖 查询笔记", variant="secondary")
            btn_plan = gr.Button("📅 生成计划", variant="success")
            btn_list = gr.Button("📋 查看任务", variant="warning")
        
        # 聊天区域
        chatbot = gr.Chatbot(height=400)
        
        # 输入区域
        with gr.Row():
            msg = gr.Textbox(
                placeholder="输入指令...",
                scale=9,
                container=False
            )
            submit_btn = gr.Button("发送", variant="primary", scale=1)
        
        # 示例
        gr.Examples(
            examples=[
                ["添加人工智能课程任务，完成代码，截止今天"],
                ["什么是列表推导式"],
                ["生成学习计划"],
                ["查看任务"],
            ],
            inputs=msg,
            label="💡 快速示例"
        )
        
        # 状态
        state = gr.State([])
        
        # 事件绑定
        def respond(message, history):
            if not message:
                return "", history
            response = chat_with_agent(message, history)
            history.append((message, response))
            return "", history
        
        submit_btn.click(respond, [msg, state], [msg, chatbot])
        msg.submit(respond, [msg, state], [msg, chatbot])
        
        # 快捷按钮
        btn_add.click(lambda: "添加人工智能课程任务，完成代码，截止今天", outputs=[msg])
        btn_query.click(lambda: "什么是列表推导式", outputs=[msg])
        btn_plan.click(lambda: "生成学习计划", outputs=[msg])
        btn_list.click(lambda: "查看任务", outputs=[msg])
        
        # 底部
        gr.HTML("""
        <div class="footer">
            🤖 个人学习助手 v1.0 · 支持任意课程自由输入
        </div>
        """)
    
    return demo

# ========== 启动 ==========
if __name__ == "__main__":
    demo = create_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
