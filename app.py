from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
import json, requests, os, re
import yfinance as yf
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)

client = OpenAI(
    base_url="http://localhost:11434/v1/",
    api_key="ollama"
)

def get_weather(city):
    try:
        r = requests.get(f"https://wttr.in/{city}?format=%C+%t", timeout=10)
        return f"The weather in {city} is {r.text.strip()}" if r.status_code == 200 else "Weather API failed"
    except Exception as e:
        return str(e)

def run_command(cmd):
    try:
        out = os.popen(cmd).read()
        return out if out.strip() else "Command executed successfully."
    except Exception as e:
        return str(e)

def get_stock_price(stock):
    try:
        data = yf.Ticker(stock.upper()).history(period="1d")
        if data.empty:
            return "Stock not found"
        return f"{stock.upper()} current price: ${data['Close'].iloc[-1]:.2f}"
    except Exception as e:
        return str(e)

available_tools = {
    "get_weather": get_weather,
    "run_command": run_command,
    "get_stock_price": get_stock_price
}

SYSTEM_PROMPT = """
You are a helpful AI assistant.
Always return ONLY valid JSON.

Plan:
{"step":"plan","content":"reason"}

Action:
{"step":"action","function":"tool_name","input":"tool input"}

Output:
{"step":"output","content":"final answer"}

Tools:
get_weather(city)
run_command(cmd)
get_stock_price(stock)

Think step by step.
"""

def extract_json(text):
    text = text.strip()
    try:
        return json.loads(text)
    except:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group())
    raise ValueError("Invalid JSON")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    query = request.json.get('message')

    messages = [
        {"role":"system","content":SYSTEM_PROMPT},
        {"role":"user","content":query}
    ]

    while True:
        response = client.chat.completions.create(
            model="llama3.2:3b",
            response_format={"type":"json_object"},
            messages=messages
        )

        parsed = extract_json(response.choices[0].message.content)
        step = parsed.get("step")

        if step == "plan":
            messages.append({"role":"assistant","content":json.dumps(parsed)})
            continue

        if step == "action":
            tool = parsed["function"]
            inp = parsed["input"]
            output = available_tools.get(tool, lambda x:"Tool not found")(inp)

            messages.append({"role":"assistant","content":json.dumps(parsed)})
            messages.append({"role":"user","content":json.dumps({"step":"observe","output":output})})
            continue

        if step == "output":
            return jsonify({"reply": parsed["content"]})

if __name__ == '__main__':
    app.run(debug=True)
