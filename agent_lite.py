# agent_lite.py - 修复 Streamlit 云端 openai proxies 兼容 + 数据库资源泄漏 + 任意课程增删指令识别
import json
import sqlite3
import re
import os
import tempfile
from openai import OpenAI
from httpx import Client

# ========== 自动创建数据库（云端临时目录，解决权限报错） ==========
db_path = os.path.join(tempfile.gettempdir(), "learning.db")
print(f"📂 数据库路径：{db_path}")

if not os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
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
    # 1. 从环境变量读取（Streamlit Secrets 注入）
    zhipu_api_key = os.environ.get("ZHIPU_API_KEY", "")
    if zhipu_api_key:
        print("✅ 从环境变量读取配置")
        return {
            "zhipu_api_key": zhipu_api_key,
            "zhipu_base_url": os.environ.get("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"),
            "zhipu_model": os.environ.get("ZHIPU_MODEL", "glm-4-flash"),
            "sqlite_path": db_path
        }
    
    # 2. 本地 config.json 兜底
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            print("✅ 从 config.json 读取配置")
            return json.load(f)
    except FileNotFoundError:
        print("⚠️ 找不到 config.json")
        return {}
    except json.JSONDecodeError as e:
        print(f"⚠️ config.json 格式错误：{e}")
        return {}

cfg = load_config()
print(f"🔑 API Key 长度: {len(cfg.get('zhipu_api_key', ''))}")

# ========== 初始化 OpenAI 客户端（修复proxies自动注入报错） ==========
api_key = cfg.get("zhipu_api_key", "").strip()
base_url = cfg.get("zhipu_base_url", "https://open.bigmodel.cn/api/paas/v4/").strip()
model = cfg.get("zhipu_model", "glm-4-flash")

print(f"🔑 API Key 长度: {len(api_key)}")
print(f"📡 Base URL: {base_url}")
print(f"🤖 Model: {model}")

client = None
if api_key:
    try:
        # 自定义httpx客户端，屏蔽平台自动注入代理参数
        http_client = Client()
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client
        )
        print(f"✅ 智谱客户端初始化成功，使用模型：{model}")
    except Exception as e:
        print(f"❌ 智谱客户端初始化失败：{e}")

# ========== 任务管理Agent（自动关闭数据库连接，避免泄漏） ==========
class TaskAgent:
    def __init__(self):
        self.conn = sqlite3.connect(db_path)
        self.cur = self.conn.cursor()

    def close(self):
        if self.conn:
            self.conn.close()

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
        self.cur.execute("SELECT id, course, task, deadline FROM todos WHERE course LIKE ? AND status=0", (f'%{course}%',))
        rows = self.cur.fetchall()
        if not rows:
            return f"❌ 未找到课程 '{course}' 的未完成任务"
        count = len(rows)
        self.cur.execute("DELETE FROM todos WHERE course LIKE ? AND status=0", (f'%{course}%',))
        self.conn.commit()
        task_list = "\n".join([f"  • 【{r[1]}】{r[2]}（截止：{r[3]}）" for r in rows])
        return f"🗑️ 已删除 {count} 条任务：\n{task_list}"

# ========== 笔记问答Agent ==========
class NoteAgent:
    def ask(self, question):
        if client is None:
            return "❌ 未配置 API 密钥，请检查 Streamlit Secrets"
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": question}],
                temperature=0.3
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"❌ 大模型调用失败：{str(e)}"

# ========== 学习计划Agent（已修复变量名错误） ==========
class PlanAgent:
    def make_plan(self):
        ta = TaskAgent()
        task_list = ta.list_tasks()
        ta.close()
        if not task_list:
            return "🎉 当前无未完成待办，无需生成学习计划"
        task_str = ""
        for row in task_list:
            c = row[1]
            t = row[2]
            d = row[3]
            # 修复：把 {task} 改成 {t}
            task_str += f"课程：{c} 任务：{t} 截止：{d}\n"
        prompt = f"根据以下待办任务生成合理的今日学习计划：\n{task_str}"
        
        if client is None:
            return "❌ 未配置 API 密钥，请检查 Streamlit Secrets"
        
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"❌ 大模型调用失败：{str(e)}"

# ========== 意图解析（修复JSON脏文本解析崩溃 + 兼容无任务/作业短句 + 优化删除逻辑） ==========
def parse_intent(user_input):
    # 本地关键词兜底匹配
    if "查看任务" in user_input or "查看所有任务" in user_input:
        return {"intent":"list_task","course":"","task":"","deadline":"","keyword":""}
    if any(w in user_input for w in ["计划", "安排", "今日"]):
        return {"intent":"make_plan","course":"","task":"","deadline":"","keyword":""}
    
    # 修复：取消必须同时带「任务/作业」限制，只要有添加就识别新增任务
    if any(w in user_input for w in ["添加", "新增"]):
        courses = ['人工智能', 'Python', '数学', '英语', '语文', '绘画', '音乐', '物理', '化学', '生物', '历史', '地理']
        course = "自定义课程"
        for c in courses:
            if c in user_input:
                course = c
                break
        task = user_input
        for c in courses:
            task = task.replace(c, '')
        for w in ['添加', '新增', '课程', '截止']:
            task = task.replace(w, '')
        task = task.replace('：', '').replace(':', '').strip()
        task = task if task else "完成课程学习"
        deadline = "今天"
        # 兼容今天晚上、明天下午这类时间后缀
        if '今天' in user_input:
            deadline = '今天'
            if "晚上" in user_input or "下午" in user_input or "上午" in user_input:
                deadline = "今天晚上"
        elif '明天' in user_input:
            deadline = '明天'
            if "晚上" in user_input or "下午" in user_input or "上午" in user_input:
                deadline = "明天晚上"
        elif '后天' in user_input:
            deadline = '后天'
        return {"intent":"add_todo","course":course,"task":task,"deadline":deadline,"keyword":""}
    
    if '完成' in user_input and any(w in user_input for w in ['任务', '作业']):
        keyword = user_input.replace('完成', '').replace('任务', '').replace('作业', '').strip() or "作业"
        return {"intent":"complete_todo","keyword":keyword}

    # 全新优化删除逻辑：仅检测“删除”，无需带任务/作业
    if "删除" in user_input:
        # 提取关键词
        keyword = user_input.replace("删除","").replace("任务","").replace("作业","").strip()
        if not keyword:
            return {"intent":"unknown"}
        # 先匹配课程
        courses = ['人工智能', 'Python', '数学', '绘画', '音乐']
        for c in courses:
            if c in keyword:
                return {"intent":"delete_course","course":c,"keyword":""}
        return {"intent":"delete_todo","keyword":keyword}

    if any(w in user_input for w in ['是什么', '什么是', '怎么用']):
        keyword = user_input
        for w in ['是什么', '什么是', '怎么用']:
            keyword = keyword.replace(w, '')
        keyword = keyword.strip()
        if keyword:
            return {"intent":"query_note","keyword":keyword}
    if client is None:
        return {"intent": "unknown"}

    prompt = """分析用户输入，仅输出标准JSON，无多余文字。
意图枚举：add_todo / query_note / make_plan / list_task / delete_todo / delete_course
JSON字段：{"intent":"","course":"","task":"","deadline":"","keyword":""}
用户输入：{user_input}"""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt.format(user_input=user_input)}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        content = resp.choices[0].message.content.strip()
        # 过滤大模型多余换行/注释，只提取{}内容
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group()
        return json.loads(content)
    except Exception as e:
        print(f"⚠️ 意图解析失败：{e}")
        # 兜底：大模型报错时，只要包含添加就自动走add_todo，不会返回无法识别
        if "添加" in user_input:
            courses = ['人工智能', 'Python', '数学', '英语', '音乐', '绘画', '语文', '物理']
            course = "自定义课程"
            for c in courses:
                if c in user_input:
                    course = c
                    break
            return {
                "intent":"add_todo",
                "course":course,
                "task":"完成课程学习",
                "deadline":"今天"
            }
        return {"intent": "unknown"}

# ========== 主路由（用完自动关闭数据库连接） ==========
def main_agent(user_input):
    intent_data = parse_intent(user_input)
    intent = intent_data.get('intent', '')
    print(f"🎯 识别意图：{intent}")
    
    ta = TaskAgent()
    try:
        if intent == 'add_todo':
            course = intent_data.get("course", "").strip() or "Python"
            task = intent_data.get("task", "").strip() or "完成课程学习"
            deadline = intent_data.get("deadline", "").strip() or "今天"
            return ta.add_task(course, task, deadline)
        
        elif intent == 'query_note':
            keyword = intent_data.get("keyword", "").strip() or user_input
            return NoteAgent().ask(keyword)
        
        elif intent == 'make_plan':
            return PlanAgent().make_plan()
        
        elif intent == "list_task":
            return ta.show_all_tasks()
        
        elif intent == "delete_todo":
            keyword = intent_data.get("keyword", "").strip()
            if not keyword:
                return "❌ 请指定要删除的任务关键词"
            return ta.delete_task(keyword)
        
        elif intent == "delete_course":
            course = intent_data.get("course", "").strip()
            if not course:
                return "❌ 请指定要删除的课程名称"
            return ta.delete_by_course(course)
        
        else:
            return """❌ 无法识别指令
💡 支持指令示例：
  📝 添加任务：添加人工智能课程，截止今天晚上
  📖 查询笔记：什么是列表推导式
  📅 生成计划：帮我安排今日学习计划
  📋 查看任务：查看任务
  🗑️ 删除任务：删除人工智能 / 删除代码任务
"""
    finally:
        # 无论是否报错，强制关闭数据库连接，避免云端资源耗尽
        ta.close()
