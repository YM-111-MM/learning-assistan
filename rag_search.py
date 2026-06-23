# rag_search.py - 超简单版
import os
import sqlite3
import json

# 禁用网络
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

# ==================== 简单问答 ====================
class SimpleRAG:
    def __init__(self):
        print("加载模型中...")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        print("连接向量库...")
        self.client = chromadb.PersistentClient(
            path="./note_vector_db",
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_collection("notes_collection")
        print(f"✅ 就绪！共 {self.collection.count()} 条笔记\n")
    
    def ask(self, question):
        # 1. 生成向量
        emb = self.model.encode([question]).tolist()[0]
        
        # 2. 检索
        results = self.collection.query(
            query_embeddings=[emb],
            n_results=2,
            include=["documents", "metadatas"]
        )
        
        # 3. 显示结果
        print(f"\n问题：{question}\n")
        print("-" * 50)
        
        if results['documents'] and results['documents'][0]:
            for i, (doc, meta) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0]
            )):
                print(f"【{meta['course']} - {meta['title']}】")
                print(f"{doc}\n")
        else:
            print("未找到相关笔记")
        
        print("-" * 50)

# ==================== 主程序 ====================
if __name__ == "__main__":
    rag = SimpleRAG()
    
    while True:
        q = input("\n你：").strip()
        if q in ['exit', 'quit', '退出']:
            print("再见！")
            break
        if q == 'list':
            conn = sqlite3.connect('learning.db')
            cur = conn.cursor()
            cur.execute("SELECT course, title, content FROM notes")
            for r in cur.fetchall():
                print(f"\n【{r[0]}】{r[1]}\n{r[2]}")
            conn.close()
            continue
        if q:
            rag.ask(q)
# 对外暴露统一调用函数，给agent导入使用
def ask_note(question):
    rag = SimpleRAG()
    # 先捕获输出，再返回文本给Agent
    import io, sys
    buf = io.StringIO()
    sys.stdout = buf
    rag.ask(question)
    sys.stdout = sys.__stdout__
    return buf.getvalue()