# agent_lite.py - 修复 OpenAI 客户端初始化
import json
import sqlite3
import re
import os
from openai import OpenAI

# ========== 自动创建数据库 ==========
if not os.path.exists("learning.db"):
    conn = sqlite3.connect("learning.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course TEXT,
            task TEXT,
            deadline TEXT,
            status INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course TEXT,
            title TEXT,
            content TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("✅ 数据库创建成功")

# ========== 加载配置 ==========
def load_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("⚠️ 找不到 config.json")
        return {}

cfg = load_config()

# ========== 初始化 OpenAI 客户端（只使用智谱） ==========
api_key = cfg.get("zhipu_api_key", "").strip()
base_url = cfg.get("zhipu_base_url", "https://open.bigmodel.cn/api/paas/v4/").strip()
model = cfg.get("zhipu_model", "glm-4-flash")  # 从 config.json 读取模型名

if not api_key:
    print("⚠️ 警告：未配置 zhipu_api_key，请检查 config.json 或 Streamlit Secrets")
    client = None
else:
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        print(f"✅ 智谱客户端初始化成功，使用模型：{model}")
    except Exception as e:
        print(f"❌ 智谱客户端初始化失败：{e}")
        client = None

# ========== 任务管理Agent ==========
class TaskAgent:
    def __init__(self):
        self.conn = sqlite3.connect("learning.db")
        self.cur = self.conn.cursor()

    def add_task(self, course, task, deadline):
        sql = "INSERT INTO todos(course, task, deadline, status) VALUES (?,?,?,0)"
        self.cur.execute(sql, (course, task, deadline))
        self.conn.commit()
        return f"✅ 已添加：【{course}】{task}，截止{deadline}"

    def list_tasks(self):
        self.cur.execute("SELECT id,course,task,deadline FROM todos WHERE status=0")
        return self.cur.fetchall()

    def show_all_tasks(self):
        data = self.list_tasks()
        if not data:
            return "📋 当前暂无未完成待办任务"
        res = "📋 全部未完成待办清单：\n"
        for idx, (tid, c, t, d) in enumerate(data, 1):
            res += f"{idx}. 【{c}】{t} | 截止：{d}\n"
        return res

    def delete_task(self, keyword):
        self.cur.execute("SELECT id, course, task, deadline FROM todos WHERE task LIKE ? AND status=0", (f'%{keyword}%',))
        rows = self.cur.fetchall()
        if not rows:
            return f"❌ 未找到包含 '{keyword}' 的未完成任务"
        task_id, course, task, deadline = rows[0]
        self.cur.execute("DELETE FROM todos WHERE id = ?", (task_id,))
        self.conn.commit()
        return f"🗑️ 已删除：【{course}】{task}（截止：{deadline}）"

    def delete_by_course(self, course):
        """按课程名删除所有任务"""
        self.cur.execute("SELECT id, course, task, deadline FROM todos WHERE course LIKE ? AND status=0", (f'%{course}%',))
        rows = self.cur.fetchall()
        if not rows:
            return f"❌ 未找到课程 '{course}' 的未完成任务"
        count = len(rows)
        self.cur.execute("DELETE FROM todos WHERE course LIKE ? AND status=0", (f'%{course}%',))
        self.conn.commit()
        task_list = "\n".join([f"  • 【{r[1]}】{r[2]}（截止：{r[3]}）" for r in rows])
        return f"🗑️ 已删除 {count} 条任务：\n{task_list}"

# ========== 笔记问答Agent（直接用大模型，不用向量检索） ==========
class NoteAgent:
    def ask(self, question):
        if client is None:
            return "❌ 未配置 API 密钥，请检查 config.json 或 Streamlit Secrets"
        try:
            resp = client.chat.completions.create(
                model=model,  # 使用 model 变量
                messages=[{"role": "user", "content": question}],
                temperature=0.3
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"❌ 大模型调用失败：{e}"

# ========== 学习计划Agent ==========
class PlanAgent:
    def make_plan(self):
        ta = TaskAgent()
        task_list = ta.list_tasks()
        if not task_list:
            return "🎉 当前无未完成待办，无需生成学习计划"
        task_str = ""
        for row in task_list:
            # row 是 (id, course, task, deadline)
            c = row[1]  # course
            t = row[2]  # task
            d = row[3]  # deadline
            task_str += f"课程：{c} 任务：{t} 截止：{d}\n"
        prompt = f"根据以下待办任务生成合理的今日学习计划：\n{task_str}"
        
        if client is None:
            return "❌ 未配置 API 密钥，请检查 config.json 或 Streamlit Secrets"
        
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"❌ 大模型调用失败：{e}"

# ========== 意图解析 ==========
def parse_intent(user_input):
    # 本地关键词兜底
    if "查看任务" in user_input or "查看所有任务" in user_input:
        return {"intent":"list_task","course":"","task":"","deadline":"","keyword":""}
    
    # 生成计划
    if any(w in user_input for w in ["计划", "安排", "今日"]):
        return {"intent":"make_plan","course":"","task":"","deadline":"","keyword":""}
    
    # 添加任务
    if any(w in user_input for w in ["添加", "新增"]) and any(w in user_input for w in ["任务", "作业"]):
        courses = ['人工智能', 'Python', '数学', '英语', '语文', '物理', '化学', '生物', '历史', '地理']
        course = "Python"
        for c in courses:
            if c in user_input:
                course = c
                break
        task = user_input
        for c in courses:
            task = task.replace(c, '')
        for w in ['添加', '新增', '任务', '作业', '课程', '截止']:
            task = task.replace(w, '')
        task = task.replace('：', '').replace(':', '').strip()
        if not task:
            task = "完成任务"
        deadline = "今天"
        if '今天' in user_input:
            deadline = '今天'
        elif '明天' in user_input:
            deadline = '明天'
        elif '后天' in user_input:
            deadline = '后天'
        return {"intent":"add_todo","course":course,"task":task,"deadline":deadline}
    
    # 完成任务
    if '完成' in user_input and any(w in user_input for w in ['任务', '作业']):
        keyword = user_input.replace('完成', '').replace('任务', '').replace('作业', '').strip()
        if not keyword:
            keyword = "作业"
        return {"intent":"complete_todo","course":"","task":"","deadline":"","keyword":keyword}
    
    # 删除任务
    if "删除" in user_input and ("任务" in user_input or "作业" in user_input):
        courses = ['人工智能', 'Python', '数学', '英语', '语文', '物理', '化学', '生物', '历史', '地理']
        course = ""
        for c in courses:
            if c in user_input:
                course = c
                break
        if course:
            return {"intent": "delete_course", "course": course, "task": "", "deadline": "", "keyword": ""}
        else:
            keyword = user_input.replace('删除', '').replace('任务', '').replace('作业', '').strip()
            if keyword:
                return {"intent": "delete_todo", "course": "", "task": "", "deadline": "", "keyword": keyword}
    
    # 查询笔记
    if any(w in user_input for w in ['是什么', '什么是', '怎么用']):
        keyword = user_input
        for w in ['是什么', '什么是', '怎么用']:
            keyword = keyword.replace(w, '')
        keyword = keyword.strip()
        if keyword:
            return {"intent":"query_note","course":"","task":"","deadline":"","keyword":keyword}
    
    # 如果 client 为 None，直接返回未知
    if client is None:
        return {"intent": "unknown"}

    prompt = f"""分析用户输入，提取意图和关键信息，只输出JSON。

意图类型：
1. add_todo - 添加任务
2. query_note - 查询笔记
3. make_plan - 生成计划
4. list_task - 查看所有未完成任务
5. delete_todo - 删除指定任务
6. delete_course - 删除整个课程的任务

字段说明：
- course: 课程名称
- task: 任务内容
- deadline: 截止时间
- keyword: 查询/删除关键词

用户输入：{user_input}

只输出JSON，格式：{{"intent":"", "course":"", "task":"", "deadline":"", "keyword":""}}"""

    try:
        resp = client.chat.completions.create(
            model=model,  # 使用 model 变量
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        content = resp.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"⚠️ 解析失败：{e}")
        return {"intent": "unknown"}

# ========== 主路由 ==========
def main_agent(user_input):
    intent_data = parse_intent(user_input)
    intent = intent_data.get('intent', '')
    print(f"🎯 识别意图：{intent}")
    
    if intent == 'add_todo':
        course = intent_data.get("course", "").strip()
        task = intent_data.get("task", "").strip()
        deadline = intent_data.get("deadline", "").strip()
        
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
    
    elif intent == "list_task":
        return TaskAgent().show_all_tasks()
    
    elif intent == "delete_todo":
        keyword = intent_data.get("keyword", "").strip()
        if not keyword:
            return "❌ 请指定要删除的任务关键词"
        return TaskAgent().delete_task(keyword)
    
    elif intent == "delete_course":
        course = intent_data.get("course", "").strip()
        if not course:
            return "❌ 请指定要删除的课程名称"
        return TaskAgent().delete_by_course(course)
    
    else:
        return """❌ 无法识别指令
💡 支持的指令：
  📝 添加任务：'添加人工智能课程任务，完成代码，截止今天'
  📖 查询笔记：'什么是列表推导式'
  📅 生成计划：'帮我安排今天的学习计划'
  📋 查看任务：'查看任务'
  🗑️ 删除任务：'删除音乐任务'
"""
