"""
Netflix-style video player with in-video language and subtitle controls.
Serves video files via a local HTTP server and renders a custom HTML5 player.
"""
import streamlit.components.v1 as components
import os
import threading
import http.server
import socketserver
import json

# ── Local file server ──
_server_started = False
_server_port = 8765


class CORSHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with CORS headers for cross-origin video loading."""
    
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def log_message(self, format, *args):
        pass  # Suppress server logs


def start_file_server(directory: str):
    """Start a background HTTP server to serve video files from the output directory."""
    global _server_started
    if _server_started:
        return
    
    os.chdir(directory)
    
    def _run():
        global _server_port
        while True:
            try:
                with socketserver.TCPServer(("", _server_port), CORSHandler) as httpd:
                    print(f"File server started on port {_server_port}")
                    httpd.serve_forever()
            except OSError as e:
                if "Address already in use" in str(e):
                    _server_port += 1
                else:
                    break
    
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    _server_started = True


def netflix_player(per_lang_videos: dict, srt_paths: dict, output_dir: str):
    """
    Renders a Netflix-style HTML5 video player with in-video controls.
    
    per_lang_videos: dict mapping language name -> MP4 file path
    srt_paths: dict mapping language name -> SRT file path
    output_dir: absolute path to the output directory being served
    """
    # Start the file server
    start_file_server(output_dir)
    
    langs = list(per_lang_videos.keys())
    first_lang = langs[0]
    
    # Build URL map (filename only since server serves from output dir)
    video_urls_js = "var videoUrls = {};\n"
    for lang, path in per_lang_videos.items():
        filename = os.path.basename(path)
        video_urls_js += f'videoUrls["{lang}"] = "http://localhost:{_server_port}/{filename}";\n'
    
    # Parse SRT to JS cue data
    subtitle_data_js = "var subtitleData = {};\n"
    for lang, path in srt_paths.items():
        cues = _parse_srt(path)
        cue_array = json.dumps(cues, ensure_ascii=False)
        subtitle_data_js += f'subtitleData["{lang}"] = {cue_array};\n'
    
    # Audio menu
    audio_items = "".join([
        f'<div class="mi{" sel" if l == first_lang else ""}" data-l="{l}" onclick="swAudio(\'{l}\')">'
        f'<span class="dot"></span>{l}</div>'
        for l in langs
    ])
    
    # Sub menu
    sub_items = (
        '<div class="mi sel" data-l="off" onclick="swSub(\'off\')"><span class="dot"></span>Off</div>'
        + "".join([
            f'<div class="mi" data-l="{l}" onclick="swSub(\'{l}\')">'
            f'<span class="dot"></span>{l}</div>'
            for l in srt_paths.keys()
        ])
    )

    html = f"""
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#000;font-family:'Inter',sans-serif}}

.P{{position:relative;width:100%;max-width:960px;margin:0 auto;background:#000;border-radius:6px;overflow:hidden;user-select:none}}
.P video{{width:100%;display:block;background:#000}}

/* Subtitle */
.SO{{position:absolute;bottom:68px;left:0;right:0;text-align:center;pointer-events:none;z-index:5;padding:0 30px}}
.ST{{display:inline-block;background:rgba(0,0,0,0.82);color:#fff;font-size:16px;font-weight:500;padding:5px 14px;border-radius:4px;line-height:1.5;text-shadow:0 1px 3px #000;max-width:90%}}

/* Controls */
.CB{{position:absolute;bottom:0;left:0;right:0;background:linear-gradient(transparent,rgba(0,0,0,0.92) 40%);padding:24px 14px 10px;display:flex;flex-direction:column;gap:5px;opacity:0;transition:opacity .25s;z-index:10}}
.P:hover .CB{{opacity:1}}

/* Progress */
.PW{{width:100%;height:4px;background:rgba(255,255,255,.15);border-radius:2px;cursor:pointer;position:relative}}
.PW:hover{{height:6px}}
.PF{{height:100%;background:#a855f7;border-radius:2px;width:0%;pointer-events:none;transition:width .1s linear}}

.CR{{display:flex;align-items:center;justify-content:space-between}}
.CL,.CRR{{display:flex;align-items:center;gap:12px}}

.B{{background:none;border:none;color:#fff;cursor:pointer;padding:3px;display:flex;align-items:center;transition:transform .12s,color .12s;outline:none}}
.B:hover{{transform:scale(1.15);color:#a855f7}}

.T{{color:rgba(255,255,255,.65);font-size:11px;letter-spacing:.3px}}

/* Badge */
.LB{{position:absolute;top:12px;left:12px;background:rgba(168,85,247,.85);color:#fff;padding:3px 10px;border-radius:4px;font-size:11px;font-weight:600;z-index:8;opacity:0;transition:opacity .3s;pointer-events:none;letter-spacing:.5px}}
.P:hover .LB{{opacity:1}}

/* Settings popup */
.SP{{position:absolute;bottom:54px;right:12px;background:rgba(15,23,42,.97);backdrop-filter:blur(16px);border:1px solid rgba(168,85,247,.15);border-radius:8px;color:#fff;min-width:240px;z-index:50;display:none;box-shadow:0 8px 28px rgba(0,0,0,.7)}}
.SP.on{{display:block}}

.TBS{{display:flex;border-bottom:1px solid rgba(255,255,255,.08)}}
.TB{{flex:1;padding:11px;text-align:center;font-size:12px;font-weight:600;cursor:pointer;color:rgba(255,255,255,.35);border-bottom:2px solid transparent;transition:all .2s}}
.TB.on{{color:#fff;border-bottom-color:#a855f7}}

.PN{{display:none;padding:4px 0}}
.PN.on{{display:block}}

.mi{{display:flex;align-items:center;gap:9px;padding:9px 16px;cursor:pointer;font-size:12.5px;color:rgba(255,255,255,.65);transition:background .12s}}
.mi:hover{{background:rgba(255,255,255,.05)}}
.mi.sel{{color:#fff;font-weight:600}}

.dot{{width:14px;height:14px;border-radius:50%;border:2px solid rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.mi.sel .dot{{border-color:#a855f7}}
.mi.sel .dot::after{{content:'';width:6px;height:6px;border-radius:50%;background:#a855f7}}

/* Volume */
.VS{{-webkit-appearance:none;width:55px;height:3px;background:rgba(255,255,255,.2);border-radius:2px;outline:none;cursor:pointer}}
.VS::-webkit-slider-thumb{{-webkit-appearance:none;width:10px;height:10px;border-radius:50%;background:#fff;cursor:pointer}}

svg{{fill:currentColor}}
</style>
</head><body>

<div class="P" id="p">
  <video id="v" playsinline preload="auto"></video>
  <div class="LB" id="lb">{first_lang}</div>
  <div class="SO"><span class="ST" id="sd" style="display:none"></span></div>

  <div class="CB">
    <div class="PW" id="pw"><div class="PF" id="pf"></div></div>
    <div class="CR">
      <div class="CL">
        <button class="B" onclick="pp()" title="Play/Pause">
          <svg id="ip" width="22" height="22" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
          <svg id="ipa" width="22" height="22" viewBox="0 0 24 24" style="display:none"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
        </button>
        <button class="B" onclick="sk(-10)"><svg width="18" height="18" viewBox="0 0 24 24"><path d="M12.5 5V1l-5 5 5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6h-2c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/></svg></button>
        <button class="B" onclick="sk(10)"><svg width="18" height="18" viewBox="0 0 24 24"><path d="M11.5 5V1l5 5-5 5V7c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6h2c0 4.42-3.58 8-8 8s-8-3.58-8-8 3.58-8 8-8z"/></svg></button>
        <button class="B" onclick="tm()"><svg width="18" height="18" viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 8.5v7a4.47 4.47 0 002.5-3.5zM14 3.23v2.06a6.99 6.99 0 010 13.42v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg></button>
        <input type="range" class="VS" id="vs" min="0" max="1" step="0.05" value="1" oninput="v.volume=this.value">
        <span class="T" id="td">0:00 / 0:00</span>
      </div>
      <div class="CRR">
        <button class="B" id="sb" onclick="tg()"><svg width="22" height="22" viewBox="0 0 24 24"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 14H4V6h16v12zM6 10h2v2H6zm0 4h8v2H6zm10 0h2v2h-2zm-6-4h8v2h-8z"/></svg></button>
        <button class="B" onclick="fs()"><svg width="18" height="18" viewBox="0 0 24 24"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg></button>
      </div>
    </div>
  </div>

  <div class="SP" id="sp">
    <div class="TBS">
      <div class="TB on" id="ta" onclick="stb('a')">🔊 Audio</div>
      <div class="TB" id="ts" onclick="stb('s')">💬 Subtitles</div>
    </div>
    <div class="PN on" id="pa">{audio_items}</div>
    <div class="PN" id="ps">{sub_items}</div>
  </div>
</div>

<script>
{video_urls_js}
{subtitle_data_js}

var v=document.getElementById('v'),cL="{first_lang}",cS="off",pl=false;

// Load first video
v.src=videoUrls[cL];
v.load();

function pp(){{
  if(pl){{v.pause();document.getElementById('ip').style.display='';document.getElementById('ipa').style.display='none'}}
  else{{v.play();document.getElementById('ip').style.display='none';document.getElementById('ipa').style.display=''}}
  pl=!pl
}}

function sk(s){{v.currentTime+=s}}
function tm(){{v.muted=!v.muted}}

v.addEventListener('timeupdate',function(){{
  if(v.duration){{
    document.getElementById('pf').style.width=(v.currentTime/v.duration*100)+'%';
    document.getElementById('td').textContent=ft(v.currentTime)+' / '+ft(v.duration);
  }}
  uS();
}});

document.getElementById('pw').addEventListener('click',function(e){{
  var r=this.getBoundingClientRect();
  v.currentTime=((e.clientX-r.left)/r.width)*v.duration;
}});

function ft(s){{var m=Math.floor(s/60),sec=Math.floor(s%60);return m+':'+(sec<10?'0':'')+sec}}

function swAudio(l){{
  if(l===cL)return;
  var t=v.currentTime,wp=pl;
  v.src=videoUrls[l];
  v.load();
  v.addEventListener('loadeddata',function h(){{
    v.currentTime=t;
    if(wp){{v.play();pl=true;document.getElementById('ip').style.display='none';document.getElementById('ipa').style.display=''}}
    v.removeEventListener('loadeddata',h)
  }});
  cL=l;
  document.getElementById('lb').textContent=l;
  document.querySelectorAll('#pa .mi').forEach(function(e){{e.classList.toggle('sel',e.dataset.l===l)}});
}}

function swSub(l){{
  cS=l;
  document.querySelectorAll('#ps .mi').forEach(function(e){{e.classList.toggle('sel',e.dataset.l===l)}});
  if(l==='off')document.getElementById('sd').style.display='none';
}}

function uS(){{
  var d=document.getElementById('sd');
  if(cS==='off'||!subtitleData[cS]){{d.style.display='none';return}}
  var t=v.currentTime,c=subtitleData[cS],f=false;
  for(var i=0;i<c.length;i++){{
    if(t>=c[i].start&&t<=c[i].end){{d.textContent=c[i].text;d.style.display='inline-block';f=true;break}}
  }}
  if(!f)d.style.display='none';
}}

function tg(){{document.getElementById('sp').classList.toggle('on')}}
function stb(t){{
  document.getElementById('ta').classList.toggle('on',t==='a');
  document.getElementById('ts').classList.toggle('on',t==='s');
  document.getElementById('pa').classList.toggle('on',t==='a');
  document.getElementById('ps').classList.toggle('on',t==='s');
}}

document.getElementById('p').addEventListener('click',function(e){{
  if(!e.target.closest('#sp')&&!e.target.closest('#sb'))document.getElementById('sp').classList.remove('on')
}});

function fs(){{
  var el=document.getElementById('p');
  if(!document.fullscreenElement)el.requestFullscreen();else document.exitFullscreen()
}}

v.addEventListener('ended',function(){{
  pl=false;document.getElementById('ip').style.display='';document.getElementById('ipa').style.display='none'
}});
</script>
</body></html>
"""
    components.html(html, height=580, scrolling=False)


def _parse_srt(srt_path: str) -> list[dict]:
    """Parse SRT to list of cue dicts."""
    cues = []
    if not os.path.exists(srt_path):
        return cues
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()
    for block in content.strip().split("\n\n"):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        try:
            ss, es = lines[1].split(" --> ")
            cues.append({
                "start": _ts(ss.strip()),
                "end": _ts(es.strip()),
                "text": " ".join(lines[2:])
            })
        except Exception:
            continue
    return cues


def _ts(t: str) -> float:
    t = t.replace(",", ".")
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)
