# bot.py - deletions-proof sürüm (tek-gönderim + temiz attribution)
import asyncio
import threading
import time
import traceback
import json
import re
from datetime import datetime
from flask import Flask, request, Response
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ========== AYARLAR ==========
api_id = 17570480
api_hash = "18c5be05094b146ef29b0cb6f6601f1f"
STRING_SESSION = "1ApWapzMBuzn4w931iuDQKpfd5VNwQn_YGuxiWl-sulb5H7QwaTmu2WY-G0DxbRuMTUvMLFWCPT-YP61bf7HDmNRO7VgvLIn0Dt6vYJZjrDrIqtSGC4mdIyYeDOUnl5u8fPHNtjxk7XDt78dFfe70ZxjjY1k87Aim5y4ou-LlyM1GJ3aL88jYMrCMSWB0oaLfEKIDmz3hHVgUxm7y5qJHoxaOnhCg-BojF4tPIoYbqgKz9rcwE3eZTd9ZrbOzePNjQac9zalvii1KEjCGNpXkHLmNPLPa_IMXy9hk5j85anSHtxH0c2RYcmhdMkn1AuLljPlO-gEQwxMMYaQPLqIpGEj__xJthHE="
BOT_USERNAME = "SDBBSxBOT"
YAPIMCI_TEXT = "👷 Yapımcı: @Keneviiiz ve @Nabi_backend (Telegram'dan ulaşabilirsiniz) 😁"

# ========== TELETHON ==========
loop = asyncio.new_event_loop()
client = TelegramClient(StringSession(STRING_SESSION), api_id, api_hash, loop=loop)

async def _start_client():
    await client.start()
    me = await client.get_me()
    print(f"✅ Telethon bağlandı: @{me.username} ({me.id})")

def _start_loop_thread():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_start_client())
    loop.run_forever()

_thread = threading.Thread(target=_start_loop_thread, daemon=True)
_thread.start()

# ========== GÜVENLİ GÖNDERME VE TOPLAMA ==========
async def _send_and_collect(cmd: str, first_timeout: int = 12, collect_seconds: int = 25, fetch_limit: int = 60):
    parts_by_id = {}
    try:
        sent = await client.send_message(BOT_USERNAME, cmd)
    except Exception as e:
        raise RuntimeError(f"Mesaj gönderilemedi: {e}")

    first_future = loop.create_future()

    async def _process_msg_obj(msg):
        try:
            if msg is None:
                return
            text = msg.text or ""
            if getattr(msg, "id", 0) >= getattr(sent, "id", 0):
                parts_by_id[msg.id] = text
                if not first_future.done():
                    first_future.set_result(True)
        except Exception as ex:
            print("process_msg_obj hata:", ex)

    async def _new_handler(event):
        await _process_msg_obj(event.message)

    async def _edit_handler(event):
        await _process_msg_obj(event.message)

    client.add_event_handler(_new_handler, events.NewMessage(from_users=BOT_USERNAME))
    client.add_event_handler(_edit_handler, events.MessageEdited(from_users=BOT_USERNAME))

    try:
        await asyncio.wait_for(first_future, timeout=first_timeout)
    except asyncio.TimeoutError:
        pass

    await asyncio.sleep(collect_seconds)

    try:
        client.remove_event_handler(_new_handler)
    except Exception:
        pass
    try:
        client.remove_event_handler(_edit_handler)
    except Exception:
        pass

    try:
        bot_entity = await client.get_entity(BOT_USERNAME)
        msgs = await client.get_messages(BOT_USERNAME, limit=fetch_limit)
        for m in reversed(msgs):
            if getattr(m, "sender_id", None) == getattr(bot_entity, "id", None):
                if hasattr(sent, "date") and hasattr(m, "date"):
                    if m.date >= sent.date:
                        parts_by_id[m.id] = m.text or ""
                else:
                    if getattr(m, "id", 0) >= getattr(sent, "id", 0):
                        parts_by_id[m.id] = m.text or ""
    except Exception as e:
        print("Fallback get_messages hatası:", e)

    if not parts_by_id:
        return ["⏳ Cevap gelmedi"]

    ordered = [parts_by_id[k] for k in sorted(parts_by_id.keys())]
    return ordered

# ========== FLASK & HELPERS ==========
app = Flask(__name__)

def pretty_json_response(obj: dict, status: int = 200) -> Response:
    txt = json.dumps(obj, ensure_ascii=False, indent=2)
    return Response(txt, status=status, mimetype="application/json; charset=utf-8")

def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = re.sub(r"```.*?```", "", s, flags=re.DOTALL)
    s = s.replace("**", "").replace("__", "").replace("`", "")
    lines = [ln.rstrip() for ln in s.splitlines()]
    clean_lines = []
    for ln in lines:
        if re.match(r"^[\s\W]*$", ln): continue
        if re.match(r"^[━\-\*]{3,}$", ln.strip()): continue
        if re.search(r"(?i)powered\s*by[:\-\s]*@?\w+", ln): continue
        if re.search(r"(?i)🧩\s*powered\s*by", ln): continue
        if re.search(r"(?i)\b(bot\s*by|powered\s*by)\b.*@?\w+", ln): continue
        clean_lines.append(ln)

    out, prev_blank = [], False
    for ln in clean_lines:
        if ln.strip() == "":
            if not prev_blank: out.append("")
            prev_blank = True
        else:
            out.append(ln); prev_blank = False
    return "\n".join(out).strip()

def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen, out = set(), []
    for it in items:
        key = re.sub(r"\s+", " ", it.strip())
        if key in seen: continue
        seen.add(key); out.append(it)
    return out

def make_single_pretty(cevaplar: list[str]) -> str:
    normalized_parts = [normalize_text(p) for p in cevaplar if p]
    normalized_parts = [n for n in dedupe_preserve_order(normalized_parts) if n]
    if not normalized_parts: return "⏳ Cevap gelmedi"
    final = normalized_parts[0] if len(normalized_parts) == 1 else "\n\n".join(
        [f"--- Parça {i} ---\n{p}" for i,p in enumerate(normalized_parts,1)]
    )
    if YAPIMCI_TEXT not in final:
        final = final.rstrip() + "\n\n" + YAPIMCI_TEXT
    # son süpürge
    final = re.sub(r'(?im)^.*(bot\s*by|powered\s*by).*$', '', final)
    final = re.sub(r'\n{2,}', '\n\n', final).strip()
    return final

@app.route("/komut", methods=["GET"])
def komut_api():
    yapimci = YAPIMCI_TEXT
    cmd = request.args.get("cmd", "").strip()
    text = request.args.get("text", "").strip()
    if not cmd:
        return pretty_json_response({"yapimci": yapimci, "hata": "Komut girilmedi."}, status=400)

    if cmd.lower() == "yapayzeka" and text:
        text = text.title()

    full_cmd = f"/{cmd} {text}".strip()
    key = cmd.lower()
    collect_seconds = 63 if key == "yapayzeka" else 7

    try:
        future = asyncio.run_coroutine_threadsafe(
            _send_and_collect(full_cmd, first_timeout=12, collect_seconds=collect_seconds, fetch_limit=80),
            loop
        )
        cevaplar = future.result(timeout=collect_seconds + 7)
    except Exception as e:
        tb = traceback.format_exc()
        print("Hata (send_and_collect):", tb)
        return pretty_json_response({"yapimci": yapimci, "hata": str(e)}), 500

    single_pretty = make_single_pretty(cevaplar)

    result = {
        "yapimci": yapimci,
        "komut": full_cmd,
        "zaman": datetime.utcnow().isoformat() + "Z",
        "cevap_sayisi": 1,
        "cevaplar": [single_pretty],
        "not": "✨ Cevaplar birleştirildi, attribution temizlendi ve tek gönderim hazırlandı"
    }
    return pretty_json_response(result)
@app.route("/", methods=["GET"])
def root():
    """API ana endpoint: sadece yapımcı bilgisini gösterir."""
    return pretty_json_response({
        "yapimci": YAPIMCI_TEXT,
        "not": "Keneviz VIP API çalışıyor ✅"
    })

if __name__ == "__main__":
    print("✅ Başlatılıyor: http://127.0.0.1:5000/komut?cmd=yapayzeka&text=Merhaba")
    app.run(host="0.0.0.0", port=5000)
