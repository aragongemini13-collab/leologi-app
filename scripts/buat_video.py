import asyncio
import datetime
import glob
import json
import os
import subprocess
import textwrap
import requests
import edge_tts
from PIL import Image, ImageDraw, ImageFilter, ImageFont

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
UPLOAD_PRESET = os.environ.get("CLOUDINARY_UPLOAD_PRESET", "")
GDRIVE_WEBHOOK_URL = os.environ.get("GDRIVE_WEBHOOK_URL", "")

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
HISTORY_FILE = "riwayat_topik.json"

PILAR_HARIAN = {
    0: ("SENIN TEKNOLOGI", "Teknologi modern, kecerdasan buatan, dan inovasi digital yang mudah dipahami"),
    1: ("SELASA PRODUKTIF", "Produktivitas kerja, manajemen waktu, dan trik alat digital sehari-hari"),
    2: ("RABU SAINS & LOGIKA", "Fakta sains menarik, cara berpikir kritis, atau fenomena alam di sekitar kita"),
    3: ("KAMIS CYBER SAFE", "Keamanan digital, privasi data pribadi, dan kebiasaan aman di internet"),
    4: ("JUMAT CARA KERJA", "Penjelasan singkat cara kerja hal sehari-hari seperti GPS, QRIS, Cloud, atau baterai"),
    5: ("SABTU SKILL & KARIER", "Keterampilan modern, cara belajar efektif, dan wawasan dunia kerja"),
    6: ("MINGGU WAWASAN", "Sejarah penemuan penting, pola pikir berkembang, atau fakta unik dunia"),
}


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                return []
    return []


def save_history(history, new_entry):
    history.append(new_entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def generate_script(history):
    now_wib = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=7)
    hari_ke = now_wib.weekday()
    tag_harian, tema_harian = PILAR_HARIAN[hari_ke]
    tanggal_str = now_wib.strftime("%Y-%m-%d")
    hari_ke_berapa = len(history) + 1

    recent_topics = [
        item["hook"]
        for item in history[-730:]
        if isinstance(item, dict) and "hook" in item
    ]
    daftar_larangan = "\n".join(f"- {t}" for t in recent_topics) if recent_topics else "- (belum ada)"

    prompt = (
        f"Kamu adalah kreator edukasi teknologi & wawasan untuk Instagram Reels @leologi.id.\n"
        f"Hari ke-{hari_ke_berapa} dari target 730 hari (2 tahun) konten harian. Tanggal: {tanggal_str}.\n"
        f"Pilar edukasi hari ini: {tema_harian}.\n\n"
        f"Pilih 1 topik edukasi yang jelas, akurat, dan bermanfaat untuk audiens umum.\n"
        f"DILARANG KERAS mengulang atau membuat topik yang sama/mirip dengan daftar di bawah ini:\n"
        f"{daftar_larangan}\n\n"
        f"Kembalikan JSON murni dengan 4 key:\n"
        f"- hook: Judul singkat pemancing perhatian maksimal 6 kata tanpa emoji.\n"
        f"- script: Naskah narasi bahasa Indonesia natural, mengalir, dan mudah dipahami untuk durasi 25-35 detik "
        f"(sekitar 65-85 kata), tanpa emoji, tanpa tanda bintang, akhiri dengan kalimat ajakan follow @leologi.id.\n"
        f"- cta_text: Teks singkat untuk pop-up di akhir video maksimal 5 kata (contoh: FOLLOW @LEOLOGI.ID TIAP HARI!).\n"
        f"- caption: Caption singkat Instagram yang relevan dengan topik diakhiri 5 hashtag edukasi."
    )

    candidate_models = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
    ]
    headers = {"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    last_error = None
    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            if resp.status_code == 404:
                print(f"Model {model_name} mengembalikan 404, mencoba model berikutnya...", flush=True)
                last_error = requests.HTTPError(f"404 for {model_name}", response=resp)
                continue
            resp.raise_for_status()

            result = resp.json()
            parts = result["candidates"][0]["content"]["parts"]
            raw = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            raw = raw.replace("```json", "").replace("```", "").strip()

            data = json.loads(raw)
            data["tag"] = tag_harian
            data["tanggal"] = tanggal_str
            data["hari_ke"] = hari_ke_berapa
            print(f"Berhasil memakai model: {model_name}", flush=True)
            return data
        except Exception as e:
            last_error = e

    raise last_error


async def generate_tts(text, out_audio="voice.mp3"):
    try:
        comm = edge_tts.Communicate(
            text, voice="id-ID-ArdiNeural", rate="+5%", boundary="WordBoundary"
        )
    except TypeError:
        comm = edge_tts.Communicate(text, voice="id-ID-ArdiNeural", rate="+5%")

    words = []
    with open(out_audio, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10_000_000
                dur = chunk["duration"] / 10_000_000
                words.append((start, start + dur, chunk["text"]))
    return words


def get_audio_duration(path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ]
    return float(subprocess.check_output(cmd).decode().strip())


def fmt_ass_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int((sec - int(sec)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass_subtitles(words, full_text, duration, out_ass="subs.ass"):
    if not words:
        tokens = full_text.split()
        step = duration / max(len(tokens), 1)
        words = [(i * step, (i + 1) * step, w) for i, w in enumerate(tokens)]

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,66,&H00FCFAF8,&H00007AFF,&H002A170F,&H80000000,-1,0,0,0,100,100,0,0,1,7,3,2,80,80,530,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    group_size = 3
    for i in range(0, len(words), group_size):
        group = words[i : i + group_size]
        for idx, (w_start, w_end, _) in enumerate(group):
            parts = []
            for j, (_, _, w_text) in enumerate(group):
                clean = w_text.replace("{", "").replace("}", "")
                if j == idx:
                    parts.append(
                        r"{\c&H00FFF000&\fscx118\fscy118\t(0,120,\fscx106\fscy106)}"
                        + clean
                        + r"{\c&H00FCFAF8&\fscx100\fscy100}"
                    )
                else:
                    parts.append(clean)
            next_start = group[idx + 1][0] if idx + 1 < len(group) else w_end + 0.08
            end_t = max(w_end, min(next_start, duration))
            lines.append(
                f"Dialogue: 0,{fmt_ass_time(w_start)},{fmt_ass_time(end_t)},Default,,0,0,0,,{' '.join(parts)}\n"
            )

    with open(out_ass, "w", encoding="utf-8") as f:
        f.writelines(lines)


def create_graphics(hook_text, tag_text, cta_text):
    bg = Image.new("RGB", (1080, 1920), "#0F172A")
    draw = ImageDraw.Draw(bg)

    for gx in range(0, 1080, 90):
        draw.line([(gx, 0), (gx, 1920)], fill=(23, 35, 60), width=1)
    for gy in range(0, 1920, 90):
        draw.line([(0, gy), (1080, gy)], fill=(23, 35, 60), width=1)

    font_tag = ImageFont.truetype(FONT_BOLD, 30)
    pill_text = f"LEOLOGI  •  {tag_text}"
    bbox = draw.textbbox((0, 0), pill_text, font=font_tag)
    tw = bbox[2] - bbox[0]
    draw.rounded_rectangle(
        [540 - tw // 2 - 34, 115, 540 + tw // 2 + 34, 177],
        radius=31, fill="#0B1220", outline="#00F0FF", width=3,
    )
    draw.text((540 - tw // 2, 129), pill_text, font=font_tag, fill="#00F0FF")

    font_hook = ImageFont.truetype(FONT_BOLD, 56)
    wrapped = textwrap.wrap(hook_text.upper(), width=22)[:2]
    y_text = 215
    for line in wrapped:
        lb = draw.textbbox((0, 0), line, font=font_hook)
        lw = lb[2] - lb[0]
        draw.text((540 - lw // 2, y_text), line, font=font_hook, fill="#F8FAFC")
        y_text += 72

    font_wm = ImageFont.truetype(FONT_BOLD, 32)
    wm = "@leologi.id"
    wb = draw.textbbox((0, 0), wm, font=font_wm)
    draw.text((540 - (wb[2] - wb[0]) // 2, 1575), wm, font=font_wm, fill="#FF7A00")
    bg.save("bg.png")

    glow = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([100, 100, 500, 500], fill=(0, 240, 255, 55))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    glow.save("glow.png")

    bar = Image.new("RGBA", (1080, 18), (0, 240, 255, 255))
    b_draw = ImageDraw.Draw(bar)
    b_draw.rectangle([1040, 0, 1080, 18], fill=(255, 122, 0, 255))
    bar.save("progress_bar.png")

    cta_img = Image.new("RGBA", (860, 110), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(cta_img)
    cdraw.rounded_rectangle([4, 4, 856, 106], radius=50, fill=(255, 122, 0, 240), outline=(0, 240, 255, 255), width=4)
    font_cta = ImageFont.truetype(FONT_BOLD, 34)
    cta_clean = cta_text.upper()[:34]
    cb = cdraw.textbbox((0, 0), cta_clean, font=font_cta)
    cdraw.text((430 - (cb[2] - cb[0]) // 2, 34), cta_clean, font=font_cta, fill="#0F172A")
    cta_img.save("cta.png")

    imgs = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
        imgs.extend(glob.glob(f"assets/{ext}"))
    if not imgs:
        raise FileNotFoundError("Tidak ada gambar di folder assets/. Upload gambar singa dulu!")

    size = 500
    mascot = Image.open(imgs[0]).convert("RGBA")
    min_side = min(mascot.size)
    left = (mascot.width - min_side) // 2
    top = (mascot.height - min_side) // 2
    mascot = mascot.crop((left, top, left + min_side, top + min_side)).resize((size - 24, size - 24), Image.LANCZOS)

    mask = Image.new("L", (size - 24, size - 24), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 24, size - 24], fill=255)

    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(badge)
    bdraw.ellipse([2, 2, size - 2, size - 2], outline="#FF7A00", width=8)
    bdraw.ellipse([10, 10, size - 10, size - 10], outline="#00F0FF", width=6)
    badge.paste(mascot, (12, 12), mask)
    badge.save("mascot_badge.png")


def render_video(duration, out_file="leologi_reel.mp4"):
    total = duration + 0.6
    cta_start = max(total - 4.5, 2.0)

    filter_complex = (
        "[0:v][3:v]overlay='240+180*sin(2*PI*t/6)':'420+120*cos(2*PI*t/5)'[bg_alive];"
        "[1:v]format=rgba,rotate='0.05*sin(2*PI*t/2.4)':c=none:ow=540:oh=540[mascot_anim];"
        "[bg_alive][mascot_anim]overlay='(W-w)/2':'400+18*sin(2*PI*t/2.0)'[v1];"
        "[2:a]showwaves=s=760x120:mode=cline:colors=0x00F0FF:rate=30,"
        "colorkey=0x000000:0.1:0.2[waves];"
        "[v1][waves]overlay='(W-w)/2':965[v2];"
        f"[v2][4:v]overlay='-W+W*(t/{total:.2f})':0[v3];"
        f"[v3][5:v]overlay='(W-w)/2':'if(lt(t-{cta_start:.2f},0.4),1920-(1920-1425)*((t-{cta_start:.2f})/0.4),1425)':enable='gt(t,{cta_start:.2f})'[v4];"
        "[v4]subtitles=subs.ass[vout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", "bg.png",
        "-loop", "1", "-i", "mascot_badge.png",
        "-i", "voice.mp3",
        "-loop", "1", "-i", "glow.png",
        "-loop", "1", "-i", "progress_bar.png",
        "-loop", "1", "-i", "cta.png",
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "2:a",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{total:.2f}", "-movflags", "+faststart",
        out_file,
    ]
    subprocess.run(cmd, check=True)


def upload_cloudinary(video_path):
    if not CLOUD_NAME or not UPLOAD_PRESET:
        print("Cloudinary belum diatur, melewati upload.", flush=True)
        return None
    url = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/video/upload"
    data = {
        "upload_preset": UPLOAD_PRESET,
        "folder": "leologi_reels",
    }
    with open(video_path, "rb") as f:
        resp = requests.post(url, files={"file": f}, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()["secure_url"]


def send_to_gdrive(payload):
    if not GDRIVE_WEBHOOK_URL:
        print("GDRIVE_WEBHOOK_URL belum diatur, melewati kirim ke Google Drive.", flush=True)
        return None
    resp = requests.post(GDRIVE_WEBHOOK_URL, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.text


def main():
    print("0. Membaca riwayat topik 2 tahun (730 hari)...", flush=True)
    history = load_history()
    print(f"Total video tercatat: {len(history)} / 730", flush=True)

    print("1. Meminta naskah edukasi harian anti-duplikat ke Gemini...", flush=True)
    content = generate_script(history)
    print(f"HARI KE: {content['hari_ke']} | TANGGAL: {content['tanggal']}", flush=True)
    print("PILAR:", content["tag"], flush=True)
    print("HOOK:", content["hook"], flush=True)
    print("CTA:", content.get("cta_text", "FOLLOW @LEOLOGI.ID!"), flush=True)
    print("SCRIPT:", content["script"], flush=True)
    print("CAPTION:\n", content["caption"], flush=True)

    print("\n2. Membuat suara narator Indonesia (Edge-TTS)...", flush=True)
    words = asyncio.run(generate_tts(content["script"]))
    duration = get_audio_duration("voice.mp3")
    print(f"Durasi suara: {duration:.2f} detik", flush=True)

    print("\n3. Membuat aset visual dinamis & subtitle bouncy...", flush=True)
    build_ass_subtitles(words, content["script"], duration)
    create_graphics(content["hook"], content["tag"], content.get("cta_text", "FOLLOW @LEOLOGI.ID TIAP HARI!"))

    print("\n4. Merender video animasi MP4 (1080x1920)...", flush=True)
    render_video(duration, "leologi_reel.mp4")

    print("\n5. Mengunggah video ke Cloudinary...", flush=True)
    video_url = upload_cloudinary("leologi_reel.mp4")
    print("SELESAI! Link Video Anda:", video_url, flush=True)

    print("\n5b. Mengirim video & naskah ke folder harian Google Drive...", flush=True)
    drive_res = send_to_gdrive({
        "hari_ke": content["hari_ke"],
        "tanggal": content["tanggal"],
        "tag": content["tag"],
        "hook": content["hook"],
        "script": content["script"],
        "caption": content["caption"],
        "video_url": video_url,
    })
    if drive_res is not None:
        print("Tersimpan di Google Drive:", drive_res, flush=True)

    print("\n6. Menyimpan topik ke riwayat_topik.json...", flush=True)
    save_history(history, {
        "hari_ke": content["hari_ke"],
        "tanggal": content["tanggal"],
        "tag": content["tag"],
        "hook": content["hook"],
        "video_url": video_url,
        "caption": content["caption"],
    })


if __name__ == "__main__":
    main()
