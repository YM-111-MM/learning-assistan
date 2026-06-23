import sqlite3

# 连接数据库
conn = sqlite3.connect('learning.db')
cur = conn.cursor()

# 1. 创建待办表
cur.execute('''
CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY,
    course TEXT,
    task TEXT,
    deadline TEXT,
    status TEXT
)
''')
# 插入10条待办数据
todo_data = [
    (1,"Python","完成列表推导式课堂作业","2026-06-20","未完成"),
    (2,"Python","练习for循环嵌套打印九九乘法表","2026-06-21","未完成"),
    (3,"Python","整理函数位置参数、关键字参数笔记","2026-06-22","未完成"),
    (4,"Python","调试文件读写with语句案例代码","2026-06-23","已完成"),
    (5,"Python","复习字典增删改查基础操作","2026-06-24","未完成"),
    (6,"英语","背诵Unit5全部核心单词","2026-06-20","已完成"),
    (7,"英语","完成4篇阅读理解专项习题","2026-06-21","未完成"),
    (8,"英语","整理虚拟语气三种时态用法","2026-06-22","未完成"),
    (9,"英语","跟读听力短文3遍并复述","2026-06-23","未完成"),
    (10,"英语","仿写if条件状语从句英语作文","2026-06-24","未完成")
]
cur.executemany("INSERT OR REPLACE INTO todos VALUES (?,?,?,?,?)", todo_data)

# 2. 创建笔记表
cur.execute('''
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    course TEXT,
    title TEXT,
    content TEXT
)
''')
# 插入10条笔记数据
note_data = [
    (1,"Python","列表推导式","[x*2 for x in range(10)] 快速生成元素翻倍新列表，简化多层for循环代码"),
    (2,"Python","for循环嵌套","外层循环控制行数，内层循环控制列数，典型场景：打印九九乘法表"),
    (3,"Python","函数位置参数","调用函数时严格按照定义顺序传参，参数个数必须一一对应，不能多也不能少"),
    (4,"Python","文件读取with语法","with open(\"test.txt\",\"r\") as f: 自动关闭文件，无需手动执行close()，避免资源泄露"),
    (5,"Python","字典安全取值","dict.get(\"key\",默认值)，键不存在时不会抛出报错，返回设置的默认值"),
    (6,"英语","Unit5重点单词","talent天赋、schedule计划表、challenge挑战、improve提升、volunteer志愿者"),
    (7,"英语","现在虚拟语气","If I were you , I would spend more time on study. 表达与当下事实相反的假设"),
    (8,"英语","阅读做题技巧","先看题干关键词，再回原文定位同义替换句子，快速排除无关选项"),
    (9,"英语","听力抓取重点","预读选项预判话题，重点听数字、转折词but/however后面的内容"),
    (10,"英语","真实条件状语从句","If引导真实条件句规则：主句一般将来时，if从句使用一般现在时")
]
cur.executemany("INSERT OR REPLACE INTO notes VALUES (?,?,?,?)", note_data)

# 保存并关闭
conn.commit()
conn.close()
print("数据库初始化完成，已创建todos、notes两张表")