import json
import sqlite3
import re
from openai import OpenAI
from rag_search import ask_note

# 加载智谱API配置
def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)
cfg = load_config()
client = OpenAI(api_key=cfg["zhipu_api_key"], base_url=cfg["zhipu_base_url"])

# ========== 步骤1：定义三个Agent（实训要求完整保留） ==========
class TaskAgent:
    """任务管理Agent"""
    def __init__(self):
        self.conn = sqlite3.connect("learning.db")
        self.cur = self.conn.cursor()

    def add_task(self, course, task, deadline):
        # 新增查重逻辑，防止重复添加相同任务
        self.cur.execute("SELECT id FROM todos WHERE course=? AND task=? AND deadline=? AND status=0",
                         (course, task, deadline))
        exist = self.cur.fetchone()
        if exist:
            return f"⚠️ 该任务已存在：【{course}】{task}，截止{deadline}，无需重复添加"

        sql = "INSERT INTO todos(course, task, deadline, status) VALUES (?,?,?,0)"
        self.cur.execute(sql, (course, task, deadline))
        self.conn.commit()
        return f"✅ 已添加：【{course}】{task}，截止{deadline}"

    def list_tasks(self):
        # 查询4个字段：id,course,task,deadline
        self.cur.execute("SELECT id,course,task,deadline FROM todos WHERE status=0")
        return self.cur.fetchall()

    # 格式化输出全部任务
    def show_all_tasks(self):
        data = self.list_tasks()
        if not data:
            return "📋 当前暂无未完成待办任务"
        res = "📋 全部未完成待办清单：\n"
        for idx, (tid, c, t, d) in enumerate(data,1):
            res += f"{idx}. 【{c}】{t} | 截止：{d}\n"
        return res


class NoteAgent:
    """笔记问答Agent（接入大模型润色）"""
    def ask(self, question):
        # 1. 检索笔记
        notes = ask_note(question)
        
        # 2. 没找到笔记
        if "未找到" in notes or not notes:
            return f"❌ 未找到与 '{question}' 相关的笔记"
        
        # 3. 调用大模型润色回答
        prompt = f"""根据以下笔记内容回答问题。

笔记：
{notes}

问题：{question}

要求：只根据笔记回答，语言自然流畅。"""

        try:
            resp = client.chat.completions.create(
                model="glm-5.2",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"⚠️ 大模型调用失败：{e}\n\n原始笔记：\n{notes}"


class PlanAgent:
    """学习计划Agent（修复解包数量报错）"""
    def make_plan(self):
        ta = TaskAgent()
        task_list = ta.list_tasks()
        if not task_list:
            return "🎉 当前无未完成待办，无需生成学习计划"
        task_str = ""
        # 修复：接收4个字段 tid,c,t,d，匹配SQL查询结果
        for tid, c, t, d in task_list:
            task_str += f"课程：{c} 任务：{t} 截止：{d}\n"
        prompt = f"根据以下待办任务生成合理的今日学习计划：\n{task_str}"
        resp = client.chat.completions.create(
            model="glm-5.2",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return resp.choices[0].message.content


# ========== 步骤2：意图解析（新增list_task意图，识别查看任务） ==========
def parse_intent(user_input):
    # 本地关键词兜底：优先匹配查看任务，不依赖大模型
    if "查看任务" in user_input or "查看所有任务" in user_input:
        return {"intent":"list_task","course":"","task":"","deadline":"","keyword":""}

    prompt = f"""分析用户输入，提取意图和关键信息，只输出JSON。

意图类型：
1. add_todo - 添加任务（用户要添加作业/任务/待办）
2. query_note - 查询笔记（用户问"什么是/怎么用/如何"）
3. make_plan - 生成计划（用户要"安排/生成/制定"计划）
4. list_task - 查看所有未完成任务（输入查看任务）

字段说明：
- course: 课程名称（从输入中提取，如"数学""Python""人工智能""英语"等，任意课程都支持）
- task: 任务内容（要做什么）
- deadline: 截止时间（今天/明天/后天/周五前/下周一等）
- keyword: 查询关键词（query_note时使用）

用户输入：{user_input}

只输出JSON，格式：{{"intent":"", "course":"", "task":"", "deadline":"", "keyword":""}}"""

    try:
        resp = client.chat.completions.create(
            model="glm-5.2",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        content = resp.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"⚠️ 解析失败：{e}")
        return {"intent": "", "course": "", "task": "", "deadline": "", "keyword": ""}


# ========== 步骤3：Agent路由（新增list_task分支） ==========
def main_agent(user_input):
    intent_data = parse_intent(user_input)
    intent = intent_data.get('intent', '')
    
    print(f"🎯 识别意图：{intent}")
    
    if intent == 'add_todo':
        course = intent_data.get("course", "").strip()
        task = intent_data.get("task", "").strip()
        deadline = intent_data.get("deadline", "").strip()
        
        # 兜底：如果大模型没提取到，用规则补全
        if not course:
            courses = ['人工智能', 'Python', '数学', '英语', '语文', '物理', '化学', '生物', '历史', '地理']
            for c in courses:
                if c in user_input:
                    course = c
                    break
            if not course:
                course = "Python"
        
        if not task:
            task = user_input
            for c in courses:
                task = task.replace(c, '')
            task = task.replace('添加', '').replace('任务', '').replace('作业', '').replace('截止', '').strip()
            if not task:
                task = "完成任务"
        
        if not deadline:
            if '今天' in user_input:
                deadline = '今天'
            elif '明天' in user_input:
                deadline = '明天'
            elif '后天' in user_input:
                deadline = '后天'
            else:
                deadline = '今天'
        
        return TaskAgent().add_task(course, task, deadline)
    
    elif intent == 'query_note':
        keyword = intent_data.get("keyword", "").strip()
        if not keyword:
            keyword = user_input
        return NoteAgent().ask(keyword)
    
    elif intent == 'make_plan':
        return PlanAgent().make_plan()
    
    # 查看任务分支
    elif intent == "list_task":
        return TaskAgent().show_all_tasks()
    
    else:
        return """❌ 无法识别指令

💡 支持的指令：
  📝 添加任务：'帮我添加数学课程任务，完成习题，截止今天'
  📖 查询笔记：'什么是列表推导式'
  📅 生成计划：'帮我安排今天的学习计划'
  📋 查看任务：'查看任务'
"""


# ========== 程序入口 ==========
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 三Agent协同学习助手（修复解包报错+防重复任务）")
    print("=" * 60)
    print("\n📌 支持任意课程自由输入：")
    print("  📝 添加任务：'添加人工智能课程任务，完成多Agent代码，截止今天'")
    print("  📖 查询笔记：'什么是列表推导式'")
    print("  📅 生成计划：'帮我安排今天的学习计划'")
    print("  📋 查看任务：'查看任务'")
    print("  💬 输入 'exit' 退出")
    print("=" * 60)
    
    while True:
        msg = input("\n👤 你：").strip()
        if msg in ["退出", "exit"]:
            print("👋 再见！")
            break
        if not msg:
            continue
        
        try:
            result = main_agent(msg)
            print("\n" + "-" * 50)
            print(result)
            print("-" * 50)
        except Exception as e:
            print(f"❌ 处理失败：{e}")