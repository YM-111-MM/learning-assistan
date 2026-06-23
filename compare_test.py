import json
from openai import OpenAI

# 读取智谱API配置
def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

cfg = load_config()
client = OpenAI(
    api_key=cfg["zhipu_api_key"],
    base_url=cfg["zhipu_base_url"]
)

# 纯直问LLM，不读取向量库、不检索本地笔记
def ask_llm_only(question):
    prompt = f"回答下面的问题：{question}"
    response = client.chat.completions.create(
        model="glm-5.2",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    test_q = "什么是列表推导式"
    print("===== 模式：不检索本地笔记，直接调用大模型 =====")
    print(f"提问：{test_q}")
    res = ask_llm_only(test_q)
    print("\n大模型通用回答：")
    print(res)