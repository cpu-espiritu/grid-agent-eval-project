# the agent: question -> SQL -> execute -> answer, plain Python loop, no framework
# the model may retry its SQL after an error or empty result, up to MAX_ATTEMPTS (3) queries
# returns a full trace (every SQL attempt, errors, token usage) so failures can be tagged later

import json
import time

import duckdb
from openai import OpenAI

from agent import config
from agent.prompts import PROMPT_VERSION, build_system_prompt
from agent.schema import describe_schema


def connect():
    # read-only so the model can't change the data; UTC so timestamptz output doesn't depend on the laptop
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    con.execute("SET TimeZone = 'UTC'")
    return con


def format_result(columns, rows):
    shown = rows[:config.MAX_ROWS_TO_MODEL]
    text = json.dumps({"columns": columns, "rows": shown}, default=str)
    if len(rows) > len(shown):
        text += f"\n({len(rows)} rows in total, first {len(shown)} shown)"
    return text


def run_sql(con, sql):
    # returns (columns, rows, error)
    try:
        cur = con.execute(sql)
        return [d[0] for d in cur.description], cur.fetchall(), None
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"


class Agent:
    def __init__(self, client=None, con=None):
        self.client = client or OpenAI()  # reads OPENAI_API_KEY
        self.con = con or connect()
        self.system_prompt = build_system_prompt(describe_schema(self.con))
        self.settings = {
            "model": config.MODEL,
            "temperature": config.TEMPERATURE,  # None = model default
            "prompt_version": PROMPT_VERSION,
            "max_attempts": config.MAX_ATTEMPTS,
        }

    def _call(self, messages, usage):
        kwargs = {"model": config.MODEL, "messages": messages, "response_format": {"type": "json_object"}}
        if config.TEMPERATURE is not None:
            kwargs["temperature"] = config.TEMPERATURE
        resp = self.client.chat.completions.create(**kwargs)
        if resp.usage:
            usage["input_tokens"] += resp.usage.prompt_tokens
            usage["output_tokens"] += resp.usage.completion_tokens
        content = resp.choices[0].message.content
        messages.append({"role": "assistant", "content": content})
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"_unparsed": content}

    def ask(self, question):
        start = time.time()
        messages = [{"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": question}]
        usage = {"input_tokens": 0, "output_tokens": 0}
        attempts = []
        reply = None

        try:
            reply = self._call(messages, usage)
            while "sql" in reply and "answer" not in reply:
                sql = reply["sql"]
                columns, rows, error = run_sql(self.con, sql)
                attempts.append({"sql": sql, "error": error,
                                 "row_count": None if error else len(rows),
                                 "rows_preview": None if error else json.loads(
                                     json.dumps(rows[:5], default=str))})

                if error is None and rows:
                    messages.append({"role": "user", "content":
                                     f"Query result:\n{format_result(columns, rows)}\n\nNow give your final answer."})
                    reply = self._call(messages, usage)
                    break
                if len(attempts) >= config.MAX_ATTEMPTS:
                    problem = error or "the query returned no rows"
                    messages.append({"role": "user", "content":
                                     f"{problem}\n\nNo query attempts left. Give your final answer now."})
                    reply = self._call(messages, usage)
                    break
                problem = f"Query failed: {error}" if error else "Query returned no rows."
                messages.append({"role": "user", "content": f"{problem} Send a corrected query or your final answer."})
                reply = self._call(messages, usage)
            status = "answered" if "answer" in reply else "no_answer"
        except Exception as e:  # API errors are recorded, not raised, so one bad call doesn't stop an eval run
            status = "api_error"
            reply = {"_error": f"{type(e).__name__}: {e}"}

        last_ok = next((a["sql"] for a in reversed(attempts) if a["error"] is None and a["row_count"]), None)
        return {
            "question": question,
            "answer": reply.get("answer") if reply else None,
            "explanation": reply.get("explanation") if reply else None,
            "status": status,
            "final_sql": last_ok,
            "attempts": attempts,
            "n_attempts": len(attempts),
            "error": reply.get("_error") or reply.get("_unparsed") if reply else None,
            "usage": usage,
            "latency_s": round(time.time() - start, 2),
            **self.settings,
        }
