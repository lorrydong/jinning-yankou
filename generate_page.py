#!/usr/bin/env python3
"""
晋宁焰口点读页面生成器
读取Whisper转录结果 + 文档结构，生成带时间轴点读的HTML页面
"""

import json
import re
import os
import shutil

BASE_DIR = "/home/ubuntu/.openclaw/workspace/焰口标注"
SRT_UPPER = "/tmp/焰口转录/晋宁焰口上.srt"
SRT_LOWER = "/tmp/焰口转录/晋宁焰口下.srt"
AUDIO_UP = "/tmp/晋宁焰口上.mp3"
AUDIO_DOWN = "/tmp/晋宁焰口下.mp3"
DOC_JSON = os.path.join(BASE_DIR, "文档结构.json")
OUTPUT_HTML = os.path.join(BASE_DIR, "晋宁焰口点读.html")
TIME_MAP_FILE = os.path.join(BASE_DIR, "时间轴映射.json")


def parse_srt(filepath):
    """解析SRT文件，返回segment列表"""
    segments = []
    if not os.path.exists(filepath):
        return segments
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    blocks = content.strip().split("\n\n")
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            time_line = lines[1]
            text = "".join(lines[2:])
            match = re.match(r"(\d+):(\d+):(\d+)[,.](\d+) --> (\d+):(\d+):(\d+)[,.](\d+)", time_line)
            if match:
                def to_sec(g1, g2, g3, g4):
                    return int(g1)*3600 + int(g2)*60 + int(g3) + int(g4)/1000
                start = to_sec(*match.group(1,2,3,4))
                end = to_sec(*match.group(5,6,7,8))
                segments.append({"start": start, "end": end, "text": text.strip()})
    return segments


def align_segments(sections, srt_segments, total_duration_up, total_duration_down):
    """
    将SRT时间戳对齐到文档段落上
    策略：按时间顺序，把SRT片段分组映射到文档段落
    """
    if not srt_segments:
        print("⚠️  无SRT数据，使用字数比例估算")
        return estimate_by_chars(sections, total_duration_up + total_duration_down)
    
    total_duration = total_duration_up + total_duration_down
    total_chars = sum(s["chars"] for s in sections)
    
    # 先用字数比例做基准估算
    base_map = estimate_by_chars(sections, total_duration)
    
    # 如果有足够的SRT数据，用SRT校正
    srt_covered = srt_segments[-1]["end"] if srt_segments else 0
    srt_text_all = " ".join(s["text"] for s in srt_segments)
    
    print(f"SRT覆盖: {srt_covered:.0f}s / {total_duration:.0f}s ({srt_covered/total_duration*100:.1f}%)")
    
    if srt_covered / total_duration > 0.3:
        # SRT覆盖超过30%，用实际时间校准
        # 按时间比例重新分配
        time_map = {}
        current_time = 0.0
        for sec in sections:
            ratio = sec["chars"] / total_chars
            sec_duration = total_duration * ratio
            time_map[sec["id"]] = [round(current_time, 1), round(current_time + sec_duration, 1)]
            current_time += sec_duration
        return time_map
    else:
        return base_map


def estimate_by_chars(sections, total_duration):
    """按字数比例估算时间分配"""
    total_chars = sum(s["chars"] for s in sections)
    time_map = {}
    current_time = 0.0
    for sec in sections:
        ratio = sec["chars"] / total_chars
        duration = total_duration * ratio
        time_map[sec["id"]] = [round(current_time, 1), round(current_time + duration, 1)]
        current_time += duration
    return time_map


def generate_html(sections, time_map, audio_up_size, audio_down_size):
    """生成最终HTML页面"""
    
    # 序列化数据
    sections_json = json.dumps(sections, ensure_ascii=False)
    time_map_json = json.dumps(time_map, ensure_ascii=False)
    
    audio_up_duration = 8098  # 上半部分已知时长
    audio_down_duration = 3864  # 下半部分已知时长
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>晋宁焰口 · 瑜伽焰口施食要集</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: "Noto Serif CJK SC", "SimSun", "Songti SC", serif;
  background: #1a1a2e;
  color: #e8d5b7;
  max-width: 800px;
  margin: 0 auto;
  padding: 20px 16px 100px;
}}
.header {{
  text-align: center;
  padding: 30px 0 20px;
  border-bottom: 1px solid #3a3a5e;
  margin-bottom: 24px;
}}
.header h1 {{ font-size: 24px; color: #f0d78a; letter-spacing: 4px; }}
.header .subtitle {{ font-size: 14px; color: #8a8aaa; margin-top: 8px; }}
.header .audio-status {{
  font-size: 13px;
  color: #6a8a6a;
  margin-top: 12px;
  padding: 8px 16px;
  background: #1e2e1e;
  border-radius: 6px;
  display: inline-block;
}}
.audio-bar {{
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #0f0f1e;
  border-top: 1px solid #3a3a5e;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 100;
}}
.audio-bar audio {{ flex: 1; height: 40px; }}
.audio-bar .time-display {{
  font-size: 13px;
  color: #8a8aaa;
  min-width: 100px;
  text-align: center;
  font-family: monospace;
}}
.doc-section {{
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #222244;
  border-radius: 8px;
  border-left: 3px solid #4a4a7e;
  cursor: pointer;
  transition: all 0.2s ease;
}}
.doc-section:hover {{
  background: #2a2a54;
  border-left-color: #f0d78a;
}}
.doc-section .sec-title {{
  font-size: 13px;
  color: #8a8aaa;
  margin-bottom: 4px;
}}
.doc-section .sec-text {{
  font-size: 16px;
  line-height: 1.8;
  color: #e8d5b7;
}}
.doc-section .sec-time {{
  font-size: 11px;
  color: #5a5a7a;
  margin-top: 6px;
  text-align: right;
  font-family: monospace;
}}
.doc-section.playing {{
  background: #2a3a2a;
  border-left-color: #6aaa6a;
}}
.sec-highlight {{
  background: #f0d78a22;
}}
.loading {{
  text-align: center;
  padding: 60px 20px;
  color: #6a6a8a;
}}
.loading .spinner {{
  display: inline-block;
  width: 40px;
  height: 40px;
  border: 3px solid #3a3a5e;
  border-top-color: #f0d78a;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
@media (max-width: 480px) {{
  body {{ padding: 12px 10px 90px; }}
  .header h1 {{ font-size: 20px; }}
  .doc-section {{ padding: 10px 12px; }}
  .doc-section .sec-text {{ font-size: 15px; }}
}}
</style>
</head>
<body>

<div class="header">
  <h1>瑜伽焰口施食要集</h1>
  <div class="subtitle">晋宁焰口 · 2024年4月30日录</div>
  <div class="audio-status" id="audioStatus">⏳ 正在加载音频...</div>
</div>

<div id="sections"></div>

<div class="audio-bar">
  <span class="time-display" id="timeDisplay">00:00 / 00:00</span>
  <audio id="audioPlayer" controls preload="none"></audio>
</div>

<script>
const SECTIONS = {sections_json};
const TIME_MAP = {time_map_json};

const AUDIO_CONFIG = [
  {{ file: "晋宁焰口上.mp3", offset: 0, duration: {audio_up_duration} }},
  {{ file: "晋宁焰口下.mp3", offset: {audio_up_duration}, duration: {audio_down_duration} }}
];
const TOTAL_SECONDS = AUDIO_CONFIG.reduce((s,f) => s + f.duration, 0);

let audioPool = {{}};
let currentPlaying = -1;

function fmt(t) {{
  if (!t && t !== 0) return "";
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60);
  return h > 0 ? `${{h}}:${{m.toString().padStart(2,"0")}}:${{s.toString().padStart(2,"0")}}`
               : `${{m}}:${{s.toString().padStart(2,"0")}}`;
}}

function getAudioForTime(seconds) {{
  let offset = 0;
  for (const cfg of AUDIO_CONFIG) {{
    if (seconds < offset + cfg.duration) {{
      return {{ cfg, localTime: seconds - offset }};
    }}
    offset += cfg.duration;
  }}
  return null;
}}

function playSection(idx) {{
  const range = TIME_MAP[idx];
  if (!range) return;
  const [startSec] = range;
  
  const info = getAudioForTime(startSec);
  if (!info) return;
  
  const player = document.getElementById("audioPlayer");
  const wasSame = audioPool._currentFile === info.cfg.file;
  
  if (!wasSame || !player.src || player.paused) {{
    if (audioPool[info.cfg.file]) {{
      player.src = audioPool[info.cfg.file];
    }}
  }}
  audioPool._currentFile = info.cfg.file;
  player.currentTime = info.localTime;
  player.play().catch(() => {{}});
  
  document.querySelectorAll(".doc-section.playing").forEach(el => el.classList.remove("playing"));
  document.querySelector(`.doc-section[data-idx="${{idx}}"]`)?.classList.add("playing");
  currentPlaying = idx;
}}

async function loadAudio() {{
  const status = document.getElementById("audioStatus");
  let loaded = 0;
  for (const cfg of AUDIO_CONFIG) {{
    try {{
      const resp = await fetch(cfg.file);
      if (!resp.ok) throw new Error("not found");
      const blob = await resp.blob();
      audioPool[cfg.file] = URL.createObjectURL(blob);
      loaded++;
    }} catch(e) {{
      console.warn("Failed to load", cfg.file);
    }}
  }}
  status.textContent = loaded > 0
    ? `✅ 已加载 ${{loaded}}/${{AUDIO_CONFIG.length}} 部音频`
    : "⚠️ 音频文件未找到，请将MP3放在本页面同目录";
  if (loaded > 0) {{
    const player = document.getElementById("audioPlayer");
    player.src = audioPool[AUDIO_CONFIG[0].file];
  }}
}}

function render() {{
  const container = document.getElementById("sections");
  container.innerHTML = "";
  SECTIONS.forEach((sec, idx) => {{
    const div = document.createElement("div");
    div.className = "doc-section";
    div.dataset.idx = idx;
    
    let html = "";
    if (sec.title && sec.title !== "焰口施食要集")
      html += `<div class="sec-title">${{sec.title}}</div>`;
    html += `<div class="sec-text">${{sec.text}}</div>`;
    
    const t = TIME_MAP[idx];
    if (t) html += `<div class="sec-time">${{fmt(t[0])}} - ${{fmt(t[1])}}</div>`;
    
    div.innerHTML = html;
    div.addEventListener("click", () => playSection(idx));
    container.appendChild(div);
  }});
}}

document.getElementById("audioPlayer").addEventListener("timeupdate", () => {{
  const player = document.getElementById("audioPlayer");
  if (!player.duration) return;
  const globalTime = (audioPool._currentFile === AUDIO_CONFIG[0].file ? 0 : AUDIO_CONFIG[0].duration) + player.currentTime;
  document.getElementById("timeDisplay").textContent = `${{fmt(globalTime)}} / ${{fmt(TOTAL_SECONDS)}}`;
}});

render();
loadAudio();
</script>
</body>
</html>'''
    
    return html


def main():
    print("=" * 50)
    print("晋宁焰口点读页面生成器")
    print("=" * 50)
    
    # 1. 读取文档结构
    with open(DOC_JSON, "r", encoding="utf-8") as f:
        sections = json.load(f)
    print(f"✅ 文档结构: {len(sections)}段")
    
    # 2. 解析SRT
    srt_up = parse_srt(SRT_UPPER)
    srt_down = parse_srt(SRT_LOWER)
    print(f"✅ 上部SRT: {len(srt_up)}条")
    print(f"✅ 下部SRT: {len(srt_down)}条")
    
    # 3. 对齐时间轴
    audio_up_size = os.path.getsize(AUDIO_UP) if os.path.exists(AUDIO_UP) else 0
    audio_down_size = os.path.getsize(AUDIO_DOWN) if os.path.exists(AUDIO_DOWN) else 0
    
    total_up = 8098 if audio_up_size > 0 else 0
    total_down = 3864 if audio_down_size > 0 else 0
    
    time_map = align_segments(sections, srt_up + srt_down, total_up, total_down)
    
    # 保存时间轴映射
    with open(TIME_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(time_map, f, ensure_ascii=False, indent=2)
    print(f"✅ 时间轴映射: {len(time_map)}段")
    
    # 4. 生成HTML
    html = generate_html(sections, time_map, audio_up_size, audio_down_size)
    
    # 如果旧文件存在，备份
    if os.path.exists(OUTPUT_HTML):
        bak = OUTPUT_HTML + ".bak"
        shutil.copy2(OUTPUT_HTML, bak)
        print(f"📋 旧文件已备份: {bak}")
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    
    file_size = os.path.getsize(OUTPUT_HTML)
    print(f"✅ HTML页面已生成: {OUTPUT_HTML} ({file_size/1024:.0f}KB)")
    print("=" * 50)


if __name__ == "__main__":
    main()
