"""
星际围攻 3D（STELLAR SIEGE 3D）v62
- 界面文字全部简体中文（中文字体在 fonts/msyh.ttc）
- 驾驶舱改成 2D 贴图（textures/cockpit.png，中间挖空当窗口）
- 两个结局：按 K 降落到新行星 = 结局一；按 O 冲进星云被黑洞吞掉 = 结局二
- 音效 20 个 + 循环背景音乐，全部本地合成/加载
"""
from ursina import *
import math, random
import os, wave, struct
import sys
import time as _pytime
from pathlib import Path

try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except Exception:
    BASE_DIR = os.getcwd()

def _now_ms():
    """_now_ms."""
    return int(_pytime.monotonic() * 1000)

app = Ursina()
window.title = "星际围攻 3D  |  STELLAR SIEGE 3D"
window.color = color.black
camera.background_color = color.black
# 窗口/任务栏图标用封面（不同 Ursina 版本属性名不一样，取不到就算了）
for _icon_attr in ('icon', 'icon_filename'):
    try:
        setattr(window, _icon_attr, os.path.join(BASE_DIR, 'cover.ico'))
        break
    except Exception:
        pass

# ?Ursina
C_LIME = getattr(color, 'lime', color.green)
C_GRAY = getattr(color, 'gray', color.white)

# ================= 音效（纯代码合成 WAV，无外部素材） =================
# Ursina 找贴图/字体时只在 application.asset_folder 里找。默认它是"启动脚本所在目录"，
# 如果从别处 exec 这个文件就会错位（中文会变成方块）。这里强制指到游戏目录。
try:
    application.asset_folder = Path(BASE_DIR)
except Exception:
    try:
        application.asset_folder = BASE_DIR
    except Exception:
        pass

AUDIO_RATE = 22050
SFX = {}
SFX_ON = True
SFX_BACKEND = 'none'
MUSIC = None
MUSIC_ON = True
_MUSIC_VOL = 0.30
MUSIC_SOURCE = 'generated'
_WINSOUND = None
_music_started = False
from pathlib import Path

def _wav_write(path, samples, rate=None):
    rate = rate or AUDIO_RATE
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b''.join(struct.pack('<h', int(max(-1.0, min(1.0, s)) * 32000))
                               for s in samples))

def _beep(freq, dur, decay=8.0, gain=0.6):
    return [math.sin(2 * math.pi * freq * i / AUDIO_RATE) * math.exp(-decay * i / AUDIO_RATE) * gain
            for i in range(int(AUDIO_RATE * dur))]

def _noise(dur, decay=10.0, gain=0.5):
    return [(random.random() * 2 - 1) * math.exp(-decay * i / AUDIO_RATE) * gain
            for i in range(int(AUDIO_RATE * dur))]

def _sweep(f0, f1, dur, decay=6.0, gain=0.6):
    out, phase = [], 0.0
    for i in range(int(AUDIO_RATE * dur)):
        t = i / AUDIO_RATE
        phase += 2 * math.pi * (f0 + (f1 - f0) * (t / dur)) / AUDIO_RATE
        out.append(math.sin(phase) * math.exp(-decay * t) * gain)
    return out

def _offset(track, sec):
    return [0.0] * int(AUDIO_RATE * sec) + track

def _mix(*tracks):
    n = max(len(t) for t in tracks)
    out = [0.0] * n
    for t in tracks:
        for i, v in enumerate(t):
            out[i] += v
    return [max(-1.0, min(1.0, v)) for v in out]

SOUND_SPECS = {
    'laser':     lambda: _sweep(1400, 260, 0.13, 9, 0.45),
    'laser2':    lambda: _sweep(900, 200, 0.10, 11, 0.45),
    'hit':       lambda: _noise(0.06, 14, 0.40),
    'explosion': lambda: _mix(_noise(0.50, 6, 0.75), _sweep(240, 40, 0.50, 4, 0.45)),
    'pickup':    lambda: _mix(_beep(880, 0.09, 10, 0.40), _offset(_beep(1320, 0.10, 10, 0.40), 0.05)),
    'ui':        lambda: _beep(660, 0.06, 16, 0.40),
    'damage':    lambda: _mix(_beep(120, 0.18, 8, 0.60), _noise(0.12, 10, 0.35)),
    'charge':    lambda: _sweep(300, 900, 0.30, 2, 0.30),
    'dash':      lambda: _sweep(1800, 300, 0.22, 7, 0.45),
    'alarm':     lambda: _mix(*[_offset(_beep(880 if i % 2 == 0 else 620, 0.10, 6, 0.45), i * 0.12)
                                for i in range(4)]),
    'land':      lambda: _sweep(600, 60, 1.20, 1.5, 0.50),
    'victory':   lambda: _mix(*[_offset(_beep(f, 0.22, 6, 0.40), i * 0.16)
                                for i, f in enumerate((523, 659, 784, 1047))]),
    'enemy_laser': lambda: _sweep(620, 190, 0.12, 10, 0.35),
    'shield':    lambda: _sweep(400, 950, 0.26, 4, 0.40),
    'switch':    lambda: _beep(1200, 0.045, 18, 0.30),
    'pause':     lambda: _mix(_beep(520, 0.09, 10, 0.35), _offset(_beep(390, 0.12, 10, 0.35), 0.09)),
    'nebula':    lambda: _mix(_noise(0.90, 2.0, 0.35), _sweep(320, 70, 0.90, 1.8, 0.35)),
    'warp':      lambda: _mix(_noise(1.20, 0.8, 0.30), _sweep(90, 1200, 1.20, 0.9, 0.40)),
    'type':      lambda: _beep(1600, 0.030, 22, 0.22),
    'death':     lambda: _mix(_noise(1.20, 3.0, 0.85), _sweep(180, 30, 1.20, 2.2, 0.60),
                              _offset(_beep(70, 0.8, 3, 0.5), 0.1)),
}

def _init_sfx():
    """合成本地 wav 并加载成 Audio。

    关键坑（真实原因，已用真机验证）：Ursina 8.x 的 Audio 只有传 pathlib.Path 时才会
    直接加载该文件；传 str 会把"绝对路径"当成资源名去 asset_folder 里搜，结果 clip=None，
    play() 只打印 "has no audio clip" —— 表现就是**完全没声音**。
    """
    global SFX_ON, SFX_BACKEND, _WINSOUND
    folder = os.path.join(BASE_DIR, 'sounds')
    try:
        os.makedirs(folder, exist_ok=True)
        for name, maker in SOUND_SPECS.items():
            path = os.path.join(folder, name + '.wav')
            if not os.path.exists(path):
                _wav_write(path, maker())
    except Exception:
        SFX_ON = False
        return

    try:
        Audio.volume_multiplier = 1.0        # Ursina 默认 0.5，会让所有音量减半
    except Exception:
        pass

    loaded = 0
    for name in SOUND_SPECS:
        path = os.path.join(folder, name + '.wav')
        try:
            a = Audio(Path(path), autoplay=False, volume=0.8)
            if getattr(a, 'clip', None) is not None:
                a.base_volume = 0.8
                SFX[name] = a
                loaded += 1
        except Exception:
            pass

    try:
        import winsound as _ws
        _WINSOUND = _ws
    except Exception:
        _WINSOUND = None

    if loaded:
        SFX_BACKEND = 'ursina'
    elif _WINSOUND is not None:
        SFX_BACKEND = 'winsound'             # OpenAL 起不来时用系统 winsound 兜底
    else:
        SFX_BACKEND = 'none'
        SFX_ON = False

def _sound_path(name):
    return os.path.join(BASE_DIR, 'sounds', name + '.wav')

def play_sfx(name, volume=None, pitch=None):
    if not SFX_ON:
        return
    vol = 0.8 if volume is None else volume
    a = SFX.get(name)
    if a is not None:
        try:
            a.volume = vol
            if pitch is not None:
                a.pitch = pitch
            a.play()
            return
        except Exception:
            pass
    if _WINSOUND is not None:
        try:
            _WINSOUND.PlaySound(_sound_path(name),
                                _WINSOUND.SND_FILENAME | _WINSOUND.SND_ASYNC)
        except Exception:
            pass

def _make_music(seconds=18.0, rate=11025):
    """_make_music."""
    n = int(rate * seconds)
    out = [0.0] * n
    chords = ((220.00, 261.63, 329.63),   # Am
              (174.61, 220.00, 261.63),   # F
              (261.63, 329.63, 392.00),   # C
              (196.00, 246.94, 293.66))   # G
    seg = seconds / len(chords)
    for ci, chord in enumerate(chords):
        start = ci * seg
        for f in chord:
            for det in (0.9975, 1.0025):     # two slightly detuned voices -> slow chorus
                ff = f * det
                ph = random.uniform(0, math.tau)
                for i in range(int(rate * (seg + 1.0))):
                    t = i / rate
                    idx = int((start - 0.5 + t) * rate)
                    if 0 <= idx < n:
                        env = math.sin(math.pi * min(1.0, max(0.0, t / (seg + 1.0))))
                        out[idx] += math.sin(2 * math.pi * ff * t + ph) * env * 0.035
        fb = chord[0] * 0.5                  #
        for i in range(int(rate * seg)):
            idx = int(start * rate) + i
            if idx >= n:
                break
            t = i / rate
            env = 0.35 + 0.65 * math.exp(-2.5 * t)
            out[idx] += math.sin(2 * math.pi * fb * t) * env * 0.05
    scale = (440.00, 523.25, 659.25, 783.99, 880.00)   #
    cur = 0.6
    while cur < seconds - 0.6:
        f = random.choice(scale)
        for i in range(int(rate * 0.5)):
            idx = int(cur * rate) + i
            if idx >= n:
                break
            tt = i / rate
            out[idx] += math.sin(2 * math.pi * f * tt) * math.exp(-7 * tt) * 0.05
        cur += random.choice((0.42, 0.55, 0.7, 0.85))
    peak = max(1e-6, max(abs(v) for v in out))
    out = [v / peak * 0.9 for v in out]
    fade = int(rate * 1.0)                   #
    for i in range(fade):
        k = i / fade
        out[i] *= k
        out[n - 1 - i] *= k
    return out

def _init_music():
    global MUSIC
    path = os.path.join(BASE_DIR, 'sounds', 'music.wav')
def _custom_music_path():
    """如果 sounds/ 里有 music_custom.wav/.ogg/.mp3，就优先用它当背景音乐。"""
    for name in ('music_custom.wav', 'music_custom.ogg', 'music_custom.mp3', 'music_custom.m4a'):
        p = os.path.join(BASE_DIR, 'sounds', name)
        if os.path.exists(p):
            return p
    return None

def _init_music():
    global MUSIC, MUSIC_SOURCE
    path = _custom_music_path()
    try:
        if path is None:
            path = os.path.join(BASE_DIR, 'sounds', 'music.wav')
            if not os.path.exists(path):
                _wav_write(path, _make_music(), rate=11025)
        MUSIC_SOURCE = os.path.basename(path)
        MUSIC = Audio(Path(path), autoplay=False, loop=True, volume=_MUSIC_VOL, group='music')
        if getattr(MUSIC, 'clip', None) is None:
            MUSIC = None
    except Exception:
        MUSIC = None

_init_sfx()
_init_music()

def start_music():
    global _music_started
    if _music_started or not MUSIC_ON:
        return
    _music_started = True
    if MUSIC is not None:
        try:
            MUSIC.volume = _MUSIC_VOL
            MUSIC.play()
            return
        except Exception:
            pass
    if _WINSOUND is not None:                # 兜底：系统级循环播放
        try:
            _WINSOUND.PlaySound(os.path.join(BASE_DIR, 'sounds', 'music.wav'),
                                _WINSOUND.SND_FILENAME | _WINSOUND.SND_ASYNC | _WINSOUND.SND_LOOP)
        except Exception:
            pass

def stop_music():
    if MUSIC is not None:
        try:
            MUSIC.volume = 0.0
        except Exception:
            pass
    elif _WINSOUND is not None:
        try:
            _WINSOUND.PlaySound(None, _WINSOUND.SND_PURGE)
        except Exception:
            pass

# ================= 多语言 + 设置项 =================
STRINGS = {
    'zh': {
        'game_title': '星 际 围 攻',
        'menu_start': '开始游戏',
        'menu_settings': '设置',
        'menu_credits': '制作者名单',
        'menu_quit': '退出游戏',
        'menu_hint': '鼠标点击按钮，或按 1 / 2 / 3 / 4',
        'settings_title': '设  置',
        'credits_title': '制 作 者 名 单',
        'credits_back': '返回',
        'credits_body': (
            '【制作人】许智皓\n'
            '　　全部玩法设计 · 关卡与结局构思 · 反复试玩找 Bug · 提出每一条修改需求\n'
            '\n'
            '【程序 / 调试】DeepSeek（AI 编程助手）\n'
            '　　Python + Ursina 代码实现 · 体素建模 · 音效合成 · 打包启动器\n'
            '　　修掉主菜单卡死、导弹打不到母舰、灰色大板等一堆 Bug\n'
            '\n'
            '【开发引擎】Python 3.14 + Ursina 8.3 + Panda3D 1.10\n'
            '【音频】全部由代码程序化合成（20 个音效 + 循环 BGM）\n'
            '【制作成本】46.56 元（DeepSeek API 调用费用）\n'
            '【版本】v75 · 6 个结局 · 单文件源码约 145 KB\n'
            '\n'
            '—— 感谢你一路把它从一个太空小游戏，改成了现在这个样子。'
        ),
        'settings_volume': '音量',
        'settings_brightness': '亮度',
        'settings_language': '语言',
        'settings_lighting': '光影',
        'settings_back': '返回',
        'on': '开',
        'off': '关',
        'lang_name': '中文',
        'hud_hp': '生命 {v}',
        'hud_water': '水分 [E]  {v}',
        'hud_food': '食物 [F]  {v}',
        'hud_energy': '能量 [J]  {v}',
        'hud_weapon': '武器 {name}  [1/2/3]',
        'weapon_0': '单发', 'weapon_1': '散射', 'weapon_2': '连射',
        'cam_1': '视角：追尾', 'cam_2': '视角：第一人称', 'cam_3': '视角：驾驶舱',
        'mission': '目标：抵达新的行星，别被钛战机干掉。',
        'prompt_land': '[ K ] 降落',
        'prompt_nebula': '[ O ] 进入星云',
        'over': '飞船已被摧毁  -  按 R 重新开始，ESC 返回主菜单',
        'alarm': '！！ 船体受损 ！！',
        'intro_title': '星 际 围 攻',
        'story_1': '异时空的星球大战文明穿越而来，一路只剩灰烬。',
        'story_2': '这一次，死星停在了你的星球上空。',
        'story_3': '炸毁前一刻，你逃了出来。',
        'story_4': '现在，你必须找到新的家园。',
        'intro_skip': '按 空格 跳过片头',
        'landing_1': '降落程序启动',
        'landing_2': '正在接近行星表面',
        'landing_3': '发现新的行星',
        'landing_4': '一颗有海洋和云层的绿色星球',
        'landing_5': '你必须重建自己的文明',
        'end_tag_1': '结局 一',
        'end_tag_2': '结局 二',
        'end_tag_3': '结局 三',
        'end_tag_4': '结局 四',
        'end_tag_5': '结局 五',
        'end_tag_6': '结局 六',
        'end_title_1': '任务完成',
        'end_title_2': '意外坠入黑洞', 
        'end_title_3': '永远留下',
        'end_title_4': '再被摧毁',
        'end_title_5': '歼星舰陨落',
        'end_title_6': '毁灭的希望',
        'end_body_3': '你被帝国的钛战机击落\n你的文明被完全消灭了。',
        'end_body_4': '你不顾警示回去了\n被那颗死星摧毁了\n你的文明灰飞烟灭了',
        'end_body_5': '你击沉了猎兵级歼星舰\n你拥有了这里。',
        'end_body_6': '你去挑战猎兵级歼星舰\n可你是失败了\n就连希望也不复存在....',
        'menu_endings': '结局收集',
        'settings_clear': '清空结局',
        'settings_cleared': '已清空',
        'boss_name': '猎兵级歼星舰',
        'boss_warn': '警告：猎兵级歼星舰出现！',
        'boss_dir': '歼星舰 {d}m {a}',
        'hud_special': '导弹 [4]  炸弹 [5]',
        'hud_hint': ('W/S 前进后退 · A/D 左右转 · ↑↓ 抬头低头 · Space 冲刺\n'
                     'W + Shift 双倍加速（耗电也双倍）\n'
                     'J 停住充电 · F 吃 · E 喝 · R 护盾 · P 换视角 · M 静音\n'
                     '4 导弹 · 5 炸弹 · K 降落 · O 星云 · F2 隐藏提示'),
        'ds_warn': '警告：检测到死星武器锁定了你',
        'ds_warn2': '立即离开这片空域！',
        'end_stats': '击杀 {k}    等级 {l}    得分 {s}',
        'end_prompt': '按 R 重新开始   |   按 ESC 返回主菜单',
        'btn_restart': '重新开始',
        'btn_menu': '返回主菜单',
        'epitaph': ('你出于好奇，\n驶入了星云。\n\n'
                    '很不幸，你被\n虚空吞没了。\n\n'
                    '你的文明也将\n就此中断了。'),
        'diag_engine': '引擎',
        'diag_audio': '音频',
        'diag_hide': 'F1 隐藏',
        'diag_off': '关',
    },
    'en': {
        'game_title': 'STELLAR SIEGE',
        'menu_start': 'START GAME',
        'menu_settings': 'SETTINGS',
        'menu_credits': 'CREDITS',
        'menu_quit': 'QUIT',
        'menu_hint': 'CLICK A BUTTON, OR PRESS 1 / 2 / 3 / 4',
        'settings_title': 'SETTINGS',
        'credits_title': 'CREDITS',
        'credits_back': 'BACK',
        'credits_body': (
            'PRODUCER  XU ZHIHao (许智皓)\n'
            '    All gameplay design, level & ending ideas, play-testing, feature requests\n'
            '\n'
            'CODE & DEBUGGING  DeepSeek (AI coding assistant)\n'
            '    Python + Ursina implementation, voxel art, procedural audio, launcher\n'
            '\n'
            'ENGINE  Python 3.14 + Ursina 8.3 + Panda3D 1.10\n'
            'AUDIO   Fully synthesized in code (20 SFX + looping BGM)\n'
            'BUDGET  46.56 CNY (DeepSeek API usage)\n'
            'VERSION  v75 - 6 endings - single file ~145 KB'
        ),
        'settings_volume': 'VOLUME',
        'settings_brightness': 'BRIGHTNESS',
        'settings_language': 'LANGUAGE',
        'settings_lighting': 'LIGHTING',
        'settings_back': 'BACK',
        'on': 'ON',
        'off': 'OFF',
        'lang_name': 'ENGLISH',
        'hud_hp': 'HP {v}',
        'hud_water': 'WATER [E]  {v}',
        'hud_food': 'FOOD [F]  {v}',
        'hud_energy': 'ENERGY [J]  {v}',
        'hud_weapon': 'WPN {name}  [1/2/3]',
        'weapon_0': 'SINGLE', 'weapon_1': 'SPREAD', 'weapon_2': 'RAPID',
        'cam_1': 'CAM: TAIL', 'cam_2': 'CAM: FIRST PERSON', 'cam_3': 'CAM: BRIDGE',
        'mission': "TARGET: REACH THE NEW PLANET. DON'T GET SHOT DOWN BY TIE FIGHTERS.",
        'prompt_land': '[ K ] TO LAND',
        'prompt_nebula': '[ O ] ENTER NEBULA',
        'over': 'SHIP DESTROYED  -  R TO RETRY, ESC FOR MAIN MENU',
        'alarm': '!! HULL BREACH !!',
        'intro_title': 'STELLAR SIEGE',
        'story_1': 'A STAR-WAR CIVILIZATION FROM ANOTHER REALITY CAME THROUGH.',
        'story_2': 'THIS TIME, THEIR DEATH STAR HANGS ABOVE YOUR PLANET.',
        'story_3': 'YOU ESCAPED MOMENTS BEFORE THE BLAST.',
        'story_4': 'NOW YOU MUST FIND A NEW HOME.',
        'intro_skip': 'PRESS SPACE TO SKIP',
        'landing_1': 'LANDING SEQUENCE INITIATED',
        'landing_2': 'APPROACHING PLANET SURFACE',
        'landing_3': 'NEW PLANET FOUND',
        'landing_4': 'A GREEN WORLD WITH OCEANS AND CLOUDS',
        'landing_5': 'YOU MUST REBUILD YOUR CIVILIZATION',
        'end_tag_1': 'ENDING 1',
        'end_tag_2': 'ENDING 2',
        'end_tag_3': 'ENDING 3',
        'end_tag_4': 'ENDING 4',
        'end_tag_5': 'ENDING 5',
        'end_tag_6': 'ENDING 6',
        'end_title_1': 'MISSION COMPLETE',
        'end_title_2': 'LOST TO A BLACK HOLE',
        'end_title_3': 'LEFT BEHIND',
        'end_title_4': 'DESTROYED AGAIN',
        'end_title_5': 'STAR DESTROYER DOWN',
        'end_title_6': 'HOPE DESTROYED',
        'end_body_3': 'IMPERIAL TIE FIGHTERS SHOT YOU DOWN\nYOUR CIVILIZATION IS GONE.',
        'end_body_4': 'YOU WENT BACK DESPITE THE WARNINGS\nAND WERE DESTROYED BY THE DEATH STAR\nYOUR CIVILIZATION TURNED TO DUST',
        'end_body_5': 'YOU SANK THE VENATOR-CLASS STAR DESTROYER\nTHIS PLACE IS YOURS NOW.',
        'end_body_6': 'YOU CHALLENGED THE VENATOR-CLASS STAR DESTROYER\nBUT YOU FAILED\nNOW EVEN HOPE IS GONE....',
        'menu_endings': 'ENDINGS',
        'settings_clear': 'CLEAR ENDINGS',
        'settings_cleared': 'CLEARED',
        'boss_name': 'VENATOR-CLASS STAR DESTROYER',
        'boss_warn': 'WARNING: VENATOR-CLASS STAR DESTROYER INBOUND',
        'boss_dir': 'DESTROYER {d}m {a}',
        'hud_special': 'MISSILE [4]  BOMB [5]',
        'hud_hint': ('W/S FORWARD-BACK · A/D TURN · UP/DOWN PITCH · SPACE DASH\n'
                     'W + SHIFT = DOUBLE SPEED (BUT 2X POWER DRAIN)\n'
                     'HOLD J CHARGE · F EAT · E DRINK · R SHIELD · P CAMERA · M MUTE\n'
                     '4 MISSILE · 5 BOMB · K LAND · O NEBULA · F2 HIDE'),
        'ds_warn': 'WARNING: DEATH STAR WEAPON IS LOCKING ON',
        'ds_warn2': 'LEAVE THIS SECTOR NOW',
        'end_stats': 'KILLS {k}    LEVEL {l}    SCORE {s}',
        'end_prompt': 'R TO RESTART   |   ESC FOR MAIN MENU',
        'btn_restart': 'RESTART',
        'btn_menu': 'MAIN MENU',
        'epitaph': ('YOU ENTERED THE NEBULA\nOUT OF CURIOSITY.\n\n'
                    'UNFORTUNATELY YOU WERE\nSWALLOWED BY THE VOID.\n\n'
                    'YOUR CIVILIZATION\nCANNOT CONTINUE.'),
        'diag_engine': 'ENGINE',
        'diag_audio': 'AUDIO',
        'diag_hide': 'F1 HIDE',
        'diag_off': 'OFF',
    },
}
LANG = 'zh'

def t(key, **kw):
    """取当前语言的文案，缺 key 时回退中文/原 key。"""
    table = STRINGS.get(LANG) or STRINGS['zh']
    s = table.get(key)
    if s is None:
        s = STRINGS['zh'].get(key, key)
    if kw:
        try:
            return s.format(**kw)
        except Exception:
            return s
    return s

# 设置项（会存到 settings.json）
SETTINGS = {'volume': 0.8, 'brightness': 1.0, 'lang': 'zh', 'lighting': True,
            'endings': [False, False, False, False, False, False]}
ENDINGS_COUNT = 6
ENDINGS_FILE = os.path.join(BASE_DIR, 'settings.json')
SETTINGS_FILE = os.path.join(BASE_DIR, 'settings.json')
LIGHTING_ON = True
_bright_overlay = None

def _load_settings():
    global LANG, LIGHTING_ON
    try:
        import json
        with open(SETTINGS_FILE, encoding='utf-8') as f:
            data = json.load(f)
        for k in ('volume', 'brightness', 'lang', 'lighting'):
            if k in data:
                SETTINGS[k] = data[k]
        if isinstance(data.get('endings'), list):
            ends = [bool(v) for v in data['endings'][:ENDINGS_COUNT]]
            ends += [False] * (ENDINGS_COUNT - len(ends))
            SETTINGS['endings'] = ends
    except Exception:
        pass
    LANG = SETTINGS.get('lang', 'zh')
    if LANG not in STRINGS:
        LANG = 'zh'
    LIGHTING_ON = bool(SETTINGS.get('lighting', True))

def _save_settings():
    try:
        import json
        SETTINGS['lang'] = LANG
        SETTINGS['lighting'] = LIGHTING_ON
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(SETTINGS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def unlock_ending(idx):
    """记录某个结局已达成（存盘 + 刷新菜单图标）。"""
    try:
        ends = SETTINGS.setdefault('endings', [False] * ENDINGS_COUNT)
        while len(ends) < ENDINGS_COUNT:
            ends.append(False)
        if 0 <= idx < ENDINGS_COUNT and not ends[idx]:
            ends[idx] = True
            _save_settings()
            try:
                _refresh_ending_icons()
            except Exception:
                pass
    except Exception:
        pass

def apply_volume():
    """总音量：直接调 Ursina 的全局音量系数（同时影响音效和音乐）。"""
    try:
        Audio.volume_multiplier = max(0.0, min(1.0, SETTINGS['volume']))
    except Exception:
        pass
    if MUSIC is not None:
        try:
            MUSIC.volume = _MUSIC_VOL * SETTINGS['volume']
        except Exception:
            pass

def _bright_texture(b):
    """亮度贴图：<1 用黑色半透明压暗，>1 用白色半透明提亮（预生成好的 PNG，避免运行时依赖 Pillow）。"""
    if b < 0.999:
        lvl = int(round((1.0 - b) / 0.05)) * 5
        lvl = max(0, min(50, lvl))
        return f'textures/ui/dim_{lvl:02d}.png'
    if b > 1.001:
        lvl = int(round((b - 1.0) / 0.05)) * 5
        lvl = max(0, min(20, lvl))
        return f'textures/ui/lit_{lvl:02d}.png'
    return None

def apply_brightness():
    """亮度：在 3D 世界之上、HUD 之下盖一层半透明黑/白（正 z 在后面，不会盖住 UI）。"""
    global _bright_overlay
    if _bright_overlay is None:
        return
    tex = _bright_texture(SETTINGS['brightness'])
    try:
        _bright_overlay.texture = tex or 'textures/ui/dim_00.png'
    except Exception:
        return
    # 主菜单/设置界面自己有专门的压暗层，这里只在游戏里生效
    try:
        _bright_overlay.enabled = (tex is not None) and not game_state.get('menu')
    except Exception:
        pass

def apply_lighting():
    """光影开关：太阳光晕 / 星空着色 / 驾驶舱辉光 / 星云辉光 一起开关。

    关掉后画面会明显变"平"：没有太阳眩光和暖色星空，星星全变白色小点。
    """
    global LIGHTING_ON
    LIGHTING_ON = bool(SETTINGS.get('lighting', True))
    for _d, _e in globals().get('sun_layers', ()):
        try:
            _e.visible = LIGHTING_ON
        except Exception:
            pass
    for name in ('_reactor_glow', '_lamp_glow'):
        e = globals().get(name)
        if e is not None:
            try:
                e.enabled = LIGHTING_ON
            except Exception:
                pass
    # 星空：开 = 按太阳方位着色；关 = 纯白小点
    for s in globals().get('stars', ()):
        try:
            s.color = getattr(s, 'base_color', color.white) if LIGHTING_ON else color.white
        except Exception:
            pass
    # 行星：开 = 按太阳的明暗层次，关 = 平涂单色
    for e in globals().get('planet_parts', ()):
        try:
            if LIGHTING_ON:
                e.color = getattr(e, '_tone', e.color)
            else:
                e.color = getattr(e, '_flat', e.color)
        except Exception:
            pass
    # 星云/黑洞的辉光层（如果存在）
    for name in ('nebula_group', 'bh_group'):
        g = globals().get(name)
        if g is not None:
            try:
                g.enabled = True if not LIGHTING_ON else g.enabled
            except Exception:
                pass

def _set_language(lang):
    global LANG
    if lang not in STRINGS:
        return
    LANG = lang
    SETTINGS['lang'] = lang
    _save_settings()
    try:
        _apply_language()
    except Exception:
        pass

def _diag_texts():
    return {'engine': t('diag_engine'), 'audio': t('diag_audio'),
            'hide': t('diag_hide'), 'off': t('diag_off')}

def _apply_audio_state():
    """M 键静音/恢复：只改音量，绝不调用 stop()（Ursina 的 stop() 默认会 destroy 掉 Audio）。"""
    if MUSIC is not None:
        try:
            MUSIC.volume = (_MUSIC_VOL * SETTINGS['volume']) if MUSIC_ON else 0.0
        except Exception:
            pass
    for a in SFX.values():
        try:
            a.volume = getattr(a, 'base_volume', 0.8) if SFX_ON else 0.0
        except Exception:
            pass
    if not SFX_ON and _WINSOUND is not None:
        try:
            _WINSOUND.PlaySound(None, _WINSOUND.SND_PURGE)
        except Exception:
            pass

_load_settings()


# ================= starfield =================
SUN_DIR = Vec3(0.50, 0.60, 0.65).normalized()    # sun direction (light + shading)
star_field_radius = 320
STAR_COLORS = (color.white, color.white, color.white, color.white,
               color.azure, color.cyan, color.yellow, color.orange, color.violet)
stars = []
for _ in range(200):          # 只剩近处少数方块星：远处交给银河全景贴图
    base = random.choice((0.35, 0.5, 0.7, 1.0, 1.6, 2.4))
    _d = Vec3(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)).normalized()
    _align = _d.dot(SUN_DIR)
    if _align > 0.55:
        _col = random.choice((color.white, color.white, color.yellow))
    elif _align > 0.1:
        _col = random.choice((color.white, color.light_gray, color.yellow))
    else:
        _col = random.choice((color.azure, color.cyan, C_GRAY, color.violet))
    s = Entity(model='cube', color=_col, scale=base, unlit=True)
    s.position = _d * random.uniform(star_field_radius * 0.35, star_field_radius)
    s.base_scale = base
    s.base_color = _col
    s.twinkle = random.uniform(0.0, math.tau)
    stars.append(s)

stars_twinkle_t = 0.0

# layered square sun = pseudo bloom / glare
sun_layers = []
for _dist, _size, _col in ((2400, 80, color.white), (2700, 150, color.yellow),
                           (3000, 240, color.orange), (3300, 360, color.red)):
    sun_layers.append((_dist, Entity(model='cube', color=_col, unlit=True, scale=_size)))

def update_sun():
    """update_sun."""
    anchor = INTRO_POS if game_state.get("intro") else player.position
    for dist, e in sun_layers:
        e.position = anchor + SUN_DIR * dist

def _wrap_field(items, radius):
    """_wrap_field."""
    for s in items:
        dx = s.x - player.x
        dy = s.y - player.y
        dz = s.z - player.z
        if dx > radius: s.x -= radius * 2
        elif dx < -radius: s.x += radius * 2
        if dy > radius: s.y -= radius * 2
        elif dy < -radius: s.y += radius * 2
        if dz > radius: s.z -= radius * 2
        elif dz < -radius: s.z += radius * 2

def _set_text(obj, value):
    """只在文字真正变化时赋值（Ursina 每次给 Text.text 赋值都会重建字体网格，很贵）。"""
    try:
        if obj.text != value:
            obj.text = value
    except Exception:
        pass


def update_stars():
    global stars_twinkle_t
    if game_state.get('menu') or game_state['endgame']:
        return
    _wrap_field(stars, star_field_radius)

    # ?10Hz 360 ?scale  CPU
    if not LIGHTING_ON:
        return          # 光影关掉：星星不再闪烁
    stars_twinkle_t += time.dt
    if stars_twinkle_t < 0.1:
        return
    stars_twinkle_t = 0.0
    for i, s in enumerate(stars):
        if s.base_scale > 1.2 or i % 3:
            continue
        s.twinkle += 0.3
        s.scale = s.base_scale * (0.8 + 0.3 * math.sin(s.twinkle))

# =================  =================
enemies, bullets, pickups, particles = [], [], [], []
mothership = None
game_state = {
    "over": False, "paused": False, "time": 0.0,
    "landing": False, "landing_timer": 0.0, "endgame": False,
    "intro": False, "nebula": False,
    "menu": True, "settings": False, "handoff": False,
}
camera_mode = 1
camera_rig = Entity(position=(0,0,0))
shake_t = 0.0          # ??
PLANET_R = 300.0          #
LAND_DIST = PLANET_R + 220  # Z K
planet_pos = Vec3(0, 0, 4000)
planet_parts = [] # ?Mesh?planet_cube_centers = []   # }/
landing_start_pos = Vec3(0, 0, 0)   #  K "?

# Z
CULL_DIST = 700.0
MAX_ENEMIES = 34
MIN_NEAR_ENEMIES = 12      #  700

# K 降落时逐条打出的字幕（时间点固定，文案按语言取）
LANDING_TIMES = (0.5, 3.0, 5.5, 7.5, 9.5)
LANDING_KEYS = ('landing_1', 'landing_2', 'landing_3', 'landing_4', 'landing_5')
SETTLE_AT = 12.0     # settlement panel appears at this many seconds
CPS = 24.0           # typewriter speed (chars per second)

def _sphere_points(n):
    """_sphere_points."""
    pts = []
    ga = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        y = 1 - (i / float(n - 1)) * 2
        ring = math.sqrt(max(0.0, 1 - y * y))
        theta = ga * i
        pts.append(Vec3(math.cos(theta) * ring, y, math.sin(theta) * ring))
    return pts

def _is_land(v):
    """_is_land."""
    a = math.sin(v.x * 3.1 + 1.7) * math.cos(v.y * 2.7 - 0.4) * math.sin(v.z * 3.4 + 2.2)
    b = 0.55 * math.sin(v.x * 7.3 - 1.1) * math.sin(v.y * 6.1 + 0.8) * math.cos(v.z * 5.9 - 1.9)
    c = 0.30 * math.cos(v.x * 13.0 + 0.5) * math.sin(v.z * 12.0 - 1.3)
    return (a + b + c) > -0.2

_CUBE_TRIS = ((1, 5, 7), (1, 7, 3), (4, 0, 2), (4, 2, 6), (0, 1, 3), (0, 3, 2),
              (5, 4, 6), (5, 6, 7), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6))

def _merged_cube_mesh(cubes):
    """_merged_cube_mesh."""
    verts, tris = [], []
    for center, size in cubes:
        if isinstance(size, (int, float)):
            sx = sy = sz = float(size)
        else:
            sx, sy, sz = float(size[0]), float(size[1]), float(size[2])
        hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
        base = len(verts)
        for dx in (-hx, hx):
            for dy in (-hy, hy):
                for dz in (-hz, hz):
                    verts.append((center.x + dx, center.y + dy, center.z + dz))
        for a, b, c in _CUBE_TRIS:
            tris.append((base + a, base + b, base + c))
            tris.append((base + a, base + c, base + b))
    return Mesh(vertices=verts, triangles=tris, mode='triangle')

def _color_key(col):
    return (round(col[0], 3), round(col[1], 3), round(col[2], 3))

def spawn_planet():
    """重建主行星：更细的体素壳（4 级明暗 + 陆地起伏 + 极冠 + 云层）+ 合并 Mesh。

    所有体素按颜色分组合并，最后只产生个位数个 draw call，加细节几乎不额外开销。
    """
    global planet_parts, planet_cube_centers
    for p in planet_parts:
        destroy(p)
    planet_parts.clear()
    planet_cube_centers = []

    n = 900
    step = 2 * PLANET_R / math.sqrt(n) * 1.24
    groups = {}

    def add(center, size, col):
        key = _color_key(col)
        if key not in groups:
            groups[key] = [col, []]
        groups[key][1].append((center, size))
        planet_cube_centers.append(center)

    # 4 级明暗（朝向太阳的那面更亮）
    LAND_TONES = (color.green, color.green, C_LIME, C_LIME)
    SEA_TONES = (color.blue, color.blue, color.azure, color.azure)
    ICE = (color.white, color.light_gray)
    sun_len = math.sqrt(0.45 ** 2 + 0.55 ** 2 + 1.0)

    for v in _sphere_points(n):
        lit = (-0.45 * v.x + 0.55 * v.y - 1.0 * v.z) / sun_len
        tone = 0 if lit < 0.0 else (1 if lit < 0.35 else (2 if lit < 0.7 else 3))
        land = _is_land(v)

        # 极冠
        if abs(v.y) > 0.87:
            add(planet_pos + v * (PLANET_R + 16),
                step * random.uniform(1.30, 1.45), ICE[tone % 2])
            continue

        # 陆地有起伏：用第二个噪声决定高度
        if land:
            h = 10 + 26 * (0.5 + 0.5 * math.sin(v.x * 9.0 + v.z * 7.0))
            add(planet_pos + v * (PLANET_R + h),
                step * random.uniform(1.32, 1.46), LAND_TONES[tone])
        else:
            add(planet_pos + v * PLANET_R,
                step * random.uniform(1.30, 1.42), SEA_TONES[tone])

    # 云层：成团的白云（比壳层更靠外、块更大）
    clouds = _sphere_points(70)
    random.shuffle(clouds)
    for v in clouds[:52]:
        if random.random() < 0.35:
            continue
        base = planet_pos + v * (PLANET_R + 58)
        for _ in range(random.randint(2, 4)):
            off = Vec3(random.uniform(-28, 28), random.uniform(-18, 18), random.uniform(-28, 28))
            add(base + off, step * random.uniform(1.6, 2.3), color.white)

    # 内部填充（透过缝隙看进去是海洋色，保证"实心"）
    fill = step * 2.6
    n_axis = int(PLANET_R / fill)
    INNER_COLORS = (color.blue, color.blue, color.azure)
    for ix in range(-n_axis, n_axis + 1):
        for iy in range(-n_axis, n_axis + 1):
            for iz in range(-n_axis, n_axis + 1):
                off = Vec3(ix * fill, iy * fill, iz * fill)
                if off.length() > PLANET_R - fill * 0.55:
                    continue
                add(planet_pos + off, fill * 1.08, random.choice(INNER_COLORS))

    # 平涂色（光影关掉时用）：陆=绿、海=蓝、冰/云=白
    flat_colors = {}
    for _c in LAND_TONES:
        flat_colors[_color_key(_c)] = color.green
    for _c in SEA_TONES:
        flat_colors[_color_key(_c)] = color.blue
    for _c in ICE:
        flat_colors[_color_key(_c)] = color.white
    flat_colors[_color_key(color.white)] = color.white

    for key, (col, cubes) in groups.items():
        _e = Entity(model=_merged_cube_mesh(cubes), color=col, unlit=True)
        _e._tone = col                                    # 按太阳的明暗色
        _e._flat = flat_colors.get(key, col)              # 平涂色
        planet_parts.append(_e)


# ================= ?+ ?Complementary ?================
# Ursina/Panda3D ?Lumen/SSAO/Bloom  shader
SHIP_SUN = Vec3(-0.55, 0.78, -0.30).normalized()
C_PINK = getattr(color, 'pink', color.white)

PALETTES = {
    'metal':  (color.dark_gray, color.gray, color.light_gray),   #
    'bright': (color.gray, color.light_gray, color.white),       # ?
    'canopy': (color.blue, color.azure, color.cyan),             #
    'engine': (color.orange, color.yellow, color.white),         # /
    'red':    (color.red, color.red, color.orange),              #
    'orange': (color.orange, color.orange, color.yellow),
    'violet': (color.magenta, color.violet, C_PINK),             #
    'gold':   (color.orange, color.yellow, color.white),
    'green':  (color.green, color.lime, C_LIME),
}

def _tone(off, palette_name, levels=3):
    """_tone."""
    pal = PALETTES[palette_name]
    if off.length() < 0.06:
        return pal[1]
    lit = 0.5 + 0.5 * (off.normalized().dot(SHIP_SUN))
    if levels == 2:
        return pal[0] if lit < 0.55 else pal[2]
    if lit < 0.40:
        return pal[0]
    if lit < 0.72:
        return pal[1]
    return pal[2]

def _make_ship(parent, cube_specs, levels=3):
    """_make_ship."""
    groups = {}
    for off, size, pal_name in cube_specs:
        pos = Vec3(*off)
        col = _tone(pos, pal_name, levels)
        key = _color_key(col)
        if key not in groups:
            groups[key] = [col, []]
        groups[key][1].append((pos, size))
    parts = []
    for col, cubes in groups.values():
        e = Entity(parent=parent, model=_merged_cube_mesh(cubes), color=col, unlit=True)
        parts.append((e, col))
    return parts

# ?/  /  /  /  / ?/ ?/  /  /
PLAYER_SHIP_CUBES = [
    # nose
    ((0, 0, 3.30), (0.45, 0.30, 0.80), 'bright'),
    ((0, 0, 2.70), (0.85, 0.55, 0.90), 'metal'),
    # cockpit rim + canopy glass
    ((0, 0.30, 1.85), (0.95, 0.20, 1.45), 'metal'),
    ((0, 0.46, 1.85), (0.78, 0.36, 1.28), 'canopy'),
    # fuselage
    ((0, 0, 1.20), (1.30, 0.75, 2.20), 'metal'),
    ((0, 0, -0.30), (1.15, 0.65, 2.00), 'metal'),
    ((0, -0.50, 0.40), (1.05, 0.28, 2.60), 'metal'),
    # spine fin + red tip
    ((0, 0.62, -0.65), (0.22, 0.70, 1.70), 'bright'),
    ((0, 1.00, -1.15), (0.14, 0.42, 0.60), 'red'),
    # main wings + wingtips
    ((-1.55, 0.02, 0.25), (2.30, 0.16, 1.70), 'metal'),
    ((1.55, 0.02, 0.25), (2.30, 0.16, 1.70), 'metal'),
    ((-2.85, 0.02, 0.05), (0.85, 0.13, 1.15), 'metal'),
    ((2.85, 0.02, 0.05), (0.85, 0.13, 1.15), 'metal'),
    # red stripes on wings
    ((-1.75, 0.11, 0.30), (0.70, 0.04, 0.55), 'red'),
    ((1.75, 0.11, 0.30), (0.70, 0.04, 0.55), 'red'),
    # wingtip cannons + muzzle glow
    ((-2.95, 0.02, 1.05), (0.16, 0.16, 1.60), 'bright'),
    ((2.95, 0.02, 1.05), (0.16, 0.16, 1.60), 'bright'),
    ((-2.95, 0.02, 1.95), (0.22, 0.22, 0.22), 'engine'),
    ((2.95, 0.02, 1.95), (0.22, 0.22, 0.22), 'engine'),
    # twin engine nacelles
    ((-0.52, 0.10, -1.55), (0.72, 0.72, 1.30), 'metal'),
    ((0.52, 0.10, -1.55), (0.72, 0.72, 1.30), 'metal'),
    # nozzles + flame + hot core
    ((-0.52, 0.10, -2.30), (0.62, 0.62, 0.45), 'bright'),
    ((0.52, 0.10, -2.30), (0.62, 0.62, 0.45), 'bright'),
    ((-0.52, 0.10, -2.66), (0.52, 0.52, 0.22), 'engine'),
    ((0.52, 0.10, -2.66), (0.52, 0.52, 0.22), 'engine'),
    ((-0.52, 0.10, -2.86), (0.22, 0.22, 0.12), 'engine'),
    ((0.52, 0.10, -2.86), (0.22, 0.22, 0.12), 'engine'),
    # tail fins + antenna
    ((-0.95, 0.45, -1.35), (0.14, 0.95, 0.85), 'metal'),
    ((0.95, 0.45, -1.35), (0.14, 0.95, 0.85), 'metal'),
    ((0, 1.06, -1.75), (0.07, 0.55, 0.07), 'bright'),
]

# four enemy ship designs (each kind has its own silhouette)
ENEMY_SHIP_CUBES = {
    # TIE/ln 钛战机：中央球形驾驶舱 + 两根连接臂 + 两侧六边形太阳能板
    'basic': [
        ((0, 0, 0), (0.95, 0.95, 0.95), 'bright'),          # 球形驾驶舱
        ((0, 0, 0.52), (0.55, 0.55, 0.14), 'metal'),        # 前窗
        ((0, 0.42, 0.10), (0.34, 0.16, 0.34), 'bright'),    # 顶部舱盖
        ((-0.72, 0, 0), (0.55, 0.16, 0.30), 'metal'),       # 左连接臂
        ((0.72, 0, 0), (0.55, 0.16, 0.30), 'metal'),        # 右连接臂
        ((-1.36, 0, 0), (0.16, 1.55, 1.55), 'metal'),       # 左侧太阳能板
        ((1.36, 0, 0), (0.16, 1.55, 1.55), 'metal'),        # 右侧太阳能板
        ((-1.36, 0, 0.10), (0.06, 1.15, 1.15), 'dark'),     # 左板内侧
        ((1.36, 0, 0.10), (0.06, 1.15, 1.15), 'dark'),      # 右板内侧
        ((0, 0, -0.62), (0.40, 0.40, 0.16), 'orange'),      # 尾喷口
    ],
    # TIE 拦截机：四片斜切翼
    'fast': [
        ((0, 0, 0), (0.78, 0.78, 0.78), 'bright'),
        ((0, 0, 0.44), (0.44, 0.44, 0.12), 'metal'),
        ((-0.62, 0, 0), (0.45, 0.14, 0.26), 'metal'),
        ((0.62, 0, 0), (0.45, 0.14, 0.26), 'metal'),
        ((-1.15, 0.42, 0), (0.14, 1.05, 0.85), 'metal'),
        ((1.15, 0.42, 0), (0.14, 1.05, 0.85), 'metal'),
        ((-1.15, -0.42, 0), (0.14, 1.05, 0.85), 'metal'),
        ((1.15, -0.42, 0), (0.14, 1.05, 0.85), 'metal'),
        ((-1.15, 0, 0.55), (0.06, 0.9, 0.4), 'red'),
        ((1.15, 0, 0.55), (0.06, 0.9, 0.4), 'red'),
        ((0, 0, -0.52), (0.32, 0.32, 0.14), 'orange'),
    ],
}

def _make_ship(parent, cube_specs, levels=3):
    """_make_ship."""
    groups = {}
    for off, size, pal_name in cube_specs:
        pos = Vec3(*off)
        col = _tone(pos, pal_name, levels)
        key = _color_key(col)
        if key not in groups:
            groups[key] = [col, []]
        groups[key][1].append((pos, size))
    parts = []
    for col, cubes in groups.values():
        e = Entity(parent=parent, model=_merged_cube_mesh(cubes), color=col, unlit=True)
        parts.append((e, col))
    return parts

# ?/  /  /  /  / ?/ ?/  /  /
PLAYER_SHIP_CUBES = [
    # nose
    ((0, 0, 3.30), (0.45, 0.30, 0.80), 'bright'),
    ((0, 0, 2.70), (0.85, 0.55, 0.90), 'metal'),
    # cockpit rim + canopy glass
    ((0, 0.30, 1.85), (0.95, 0.20, 1.45), 'metal'),
    ((0, 0.46, 1.85), (0.78, 0.36, 1.28), 'canopy'),
    # fuselage
    ((0, 0, 1.20), (1.30, 0.75, 2.20), 'metal'),
    ((0, 0, -0.30), (1.15, 0.65, 2.00), 'metal'),
    ((0, -0.50, 0.40), (1.05, 0.28, 2.60), 'metal'),
    # spine fin + red tip
    ((0, 0.62, -0.65), (0.22, 0.70, 1.70), 'bright'),
    ((0, 1.00, -1.15), (0.14, 0.42, 0.60), 'red'),
    # main wings + wingtips
    ((-1.55, 0.02, 0.25), (2.30, 0.16, 1.70), 'metal'),
    ((1.55, 0.02, 0.25), (2.30, 0.16, 1.70), 'metal'),
    ((-2.85, 0.02, 0.05), (0.85, 0.13, 1.15), 'metal'),
    ((2.85, 0.02, 0.05), (0.85, 0.13, 1.15), 'metal'),
    # red stripes on wings
    ((-1.75, 0.11, 0.30), (0.70, 0.04, 0.55), 'red'),
    ((1.75, 0.11, 0.30), (0.70, 0.04, 0.55), 'red'),
    # wingtip cannons + muzzle glow
    ((-2.95, 0.02, 1.05), (0.16, 0.16, 1.60), 'bright'),
    ((2.95, 0.02, 1.05), (0.16, 0.16, 1.60), 'bright'),
    ((-2.95, 0.02, 1.95), (0.22, 0.22, 0.22), 'engine'),
    ((2.95, 0.02, 1.95), (0.22, 0.22, 0.22), 'engine'),
    # twin engine nacelles
    ((-0.52, 0.10, -1.55), (0.72, 0.72, 1.30), 'metal'),
    ((0.52, 0.10, -1.55), (0.72, 0.72, 1.30), 'metal'),
    # nozzles + flame + hot core
    ((-0.52, 0.10, -2.30), (0.62, 0.62, 0.45), 'bright'),
    ((0.52, 0.10, -2.30), (0.62, 0.62, 0.45), 'bright'),
    ((-0.52, 0.10, -2.66), (0.52, 0.52, 0.22), 'engine'),
    ((0.52, 0.10, -2.66), (0.52, 0.52, 0.22), 'engine'),
    ((-0.52, 0.10, -2.86), (0.22, 0.22, 0.12), 'engine'),
    ((0.52, 0.10, -2.86), (0.22, 0.22, 0.12), 'engine'),
    # tail fins + antenna
    ((-0.95, 0.45, -1.35), (0.14, 0.95, 0.85), 'metal'),
    ((0.95, 0.45, -1.35), (0.14, 0.95, 0.85), 'metal'),
    ((0, 1.06, -1.75), (0.07, 0.55, 0.07), 'bright'),
]

# four enemy ship designs (each kind has its own silhouette)
ENEMY_SHIP_CUBES = {
    'basic': [                                        # red interceptor
        ((0, 0, 1.15), (0.55, 0.35, 1.10), 'bright'),
        ((0, 0, 0.15), (1.05, 0.50, 1.80), 'metal'),
        ((0, 0.42, -0.35), (0.16, 0.55, 0.95), 'metal'),
        ((-1.25, 0, -0.10), (1.75, 0.12, 1.20), 'metal'),
        ((1.25, 0, -0.10), (1.75, 0.12, 1.20), 'metal'),
        ((-1.35, 0.09, 0.10), (0.95, 0.05, 0.65), 'red'),
        ((1.35, 0.09, 0.10), (0.95, 0.05, 0.65), 'red'),
        ((-1.25, 0.02, 0.75), (0.12, 0.12, 0.95), 'bright'),
        ((1.25, 0.02, 0.75), (0.12, 0.12, 0.95), 'bright'),
        ((-0.38, 0, -1.20), (0.45, 0.45, 0.55), 'metal'),
        ((0.38, 0, -1.20), (0.45, 0.45, 0.55), 'metal'),
        ((-0.38, 0, -1.55), (0.36, 0.36, 0.20), 'orange'),
        ((0.38, 0, -1.55), (0.36, 0.36, 0.20), 'orange'),
    ],
    'fast': [                                         # orange dart
        ((0, 0, 1.45), (0.40, 0.24, 1.30), 'bright'),
        ((0, 0, 0.30), (0.70, 0.34, 1.90), 'orange'),
        ((0, 0.30, -0.10), (0.30, 0.35, 0.90), 'orange'),
        ((-0.85, 0, -0.35), (1.20, 0.10, 0.90), 'metal'),
        ((0.85, 0, -0.35), (1.20, 0.10, 0.90), 'metal'),
        ((-0.85, 0.07, -0.20), (0.70, 0.04, 0.55), 'orange'),
        ((0.85, 0.07, -0.20), (0.70, 0.04, 0.55), 'orange'),
        ((-0.30, 0, -1.05), (0.34, 0.34, 0.45), 'metal'),
        ((0.30, 0, -1.05), (0.34, 0.34, 0.45), 'metal'),
        ((-0.30, 0, -1.35), (0.26, 0.26, 0.16), 'engine'),
        ((0.30, 0, -1.35), (0.26, 0.26, 0.16), 'engine'),
    ],
    'tank': [                                         # violet heavy bomber
        ((0, 0, 1.30), (0.90, 0.60, 1.00), 'bright'),
        ((0, 0, 0.20), (1.60, 0.90, 2.00), 'metal'),
        ((0, 0.55, 0.10), (1.10, 0.35, 1.40), 'violet'),
        ((0, -0.55, 0.10), (1.30, 0.30, 1.80), 'metal'),
        ((-1.55, 0, -0.20), (1.40, 0.35, 1.30), 'violet'),
        ((1.55, 0, -0.20), (1.40, 0.35, 1.30), 'violet'),
        ((-1.55, 0.20, 0.55), (0.18, 0.18, 1.10), 'bright'),
        ((1.55, 0.20, 0.55), (0.18, 0.18, 1.10), 'bright'),
        ((-0.60, 0, -1.35), (0.80, 0.80, 0.70), 'metal'),
        ((0.60, 0, -1.35), (0.80, 0.80, 0.70), 'metal'),
        ((-0.60, 0, -1.80), (0.62, 0.62, 0.24), 'engine'),
        ((0.60, 0, -1.80), (0.62, 0.62, 0.24), 'engine'),
        ((0, 0.90, -0.30), (0.14, 0.55, 0.70), 'bright'),
    ],
    'shooter': [                                      # gold gunship
        ((0, 0, 0.90), (0.80, 0.55, 1.20), 'bright'),
        ((0, 0, 0.00), (1.15, 0.70, 1.60), 'metal'),
        ((0, 0.45, -0.10), (0.70, 0.35, 0.90), 'gold'),
        ((-1.10, 0, -0.10), (1.30, 0.16, 1.10), 'metal'),
        ((1.10, 0, -0.10), (1.30, 0.16, 1.10), 'metal'),
        ((-1.10, 0.10, 0.10), (0.70, 0.05, 0.60), 'orange'),
        ((1.10, 0.10, 0.10), (0.70, 0.05, 0.60), 'orange'),
        ((0, 0.05, 1.75), (0.22, 0.22, 1.70), 'bright'),
        ((0, 0.05, 2.55), (0.28, 0.28, 0.25), 'engine'),
        ((-0.42, 0, -1.20), (0.44, 0.44, 0.60), 'metal'),
        ((0.42, 0, -1.20), (0.44, 0.44, 0.60), 'metal'),
        ((-0.42, 0, -1.55), (0.34, 0.34, 0.20), 'engine'),
        ((0.42, 0, -1.55), (0.34, 0.34, 0.20), 'engine'),
    ],
}


def build_player_ship(parent):
    """build_player_ship."""
    return _make_ship(parent, PLAYER_SHIP_CUBES)

def build_enemy_ship(parent, kind):
    return _make_ship(parent, ENEMY_SHIP_CUBES.get(kind, ENEMY_SHIP_CUBES['basic']), levels=2)

class Player(Entity):
    def __init__(self):
        super().__init__(position=(0,0,0))
        self.parts = build_player_ship(self)

        self.speed = 45
        self.turn_speed = 90
        self.pitch_speed = 70
        self.yaw = 0
        self.pitch = 0

        self.hp = 100; self.maxhp = 100; self.damage = 10
        self.level = 1; self.exp = 0; self.exp_next = 20; self.kills = 0; self.score = 0
        self.fire_cd = 0; self.fire_rate = 0.15
        self.dash_cd = 0; self.heal_cd = 0; self.invuln = 0; self.shield_cd = 0; self.shield_active = 0
        self.missile_cd = 0; self.bomb_cd = 0
        self.boosting = False; self.boost_fov = 0.0
        self.thirst = 100.0; self.hunger = 100.0
        self.weapon = 0; self.weapon_names = ["单发", "散射", "连射"]; self.hit_timer = 0
        self.charge_sfx_cd = 0
        self.flash_on = False
        self.vel = Vec3(0, 0, 0)          #
        self.target_yaw = 0.0             #
        self.target_pitch = 0.0

        self.energy = 1000.0
        self.max_energy = 1000.0

    def gain_exp(self, amt):
        self.exp += amt
        while self.exp >= self.exp_next:
            self.exp -= self.exp_next; self.level += 1; self.exp_next = int(self.exp_next * 1.4)
            self.maxhp += 20; self.hp = self.maxhp; self.damage += 2; burst(self.position, color.yellow, 20)
            play_sfx('pickup', pitch=1.5, volume=0.5)     # ?
    def update(self):
        if game_state.get("menu") or game_state.get("handoff"):
            return
        if game_state["intro"] or game_state["nebula"]: return
        if game_state["over"] or game_state["paused"] or game_state["endgame"]: return

        dt = min(time.dt, 0.1)

        # ======  ======
        if game_state["landing"]:
            game_state["landing_timer"] += dt

            to_center = landing_start_pos - planet_pos
            if to_center.length() < 0.001:
                to_center = Vec3(0, 0, -1)
            surface = planet_pos + to_center.normalized() * PLANET_R

            to_s = surface - self.position
            remain = to_s.length()
            if remain > 0.5:
                self.position += to_s.normalized() * min(remain, 170 * dt)

            self.rotation_y += 40 * dt
            self.rotation_x += 18 * dt

            if self.visible and (self.position - planet_pos).length() < PLANET_R + 20:
                self.visible = False          # ?                burst(self.position, color.orange, 40)

            if game_state["landing_timer"] >= SETTLE_AT:
                _enter_endgame()          # ?                play_sfx('victory', volume=0.6)
            return

        # ====== }/======
        if held_keys['a']: self.target_yaw -= self.turn_speed * dt
        if held_keys['d']: self.target_yaw += self.turn_speed * dt
        if held_keys['up arrow']: self.target_pitch -= self.pitch_speed * dt
        if held_keys['down arrow']: self.target_pitch += self.pitch_speed * dt
        self.target_pitch = max(-80, min(80, self.target_pitch))

        k_rot = min(1.0, dt * 7.0)
        self.yaw = lerp(self.yaw, self.target_yaw, k_rot)
        self.pitch = lerp(self.pitch, self.target_pitch, k_rot)
        self.rotation = Vec3(self.pitch, self.yaw, 0)

        # W / S 前后；按住 W 再按 Shift 双倍速度、双倍耗电
        moving = held_keys['w'] or held_keys['s']
        shift_held = bool(held_keys['shift'] or held_keys['left shift']
                          or held_keys['right shift'])
        want_boost = bool(held_keys['w']) and shift_held
        was_boosting = self.boosting
        self.boosting = want_boost and self.energy > 1.0

        desired = Vec3(0, 0, 0)
        if moving:
            spd = self.speed
            drain = 6.0 * dt
            if self.boosting:
                spd *= 2.0
                drain *= 2.0
            desired = self.forward * (spd if held_keys['w'] else -self.speed * 0.6)
            self.energy = max(0, self.energy - drain)
            if self.energy <= 0:
                desired = Vec3(0, 0, 0)
                self.boosting = False
        if self.boosting and not was_boosting:
            play_sfx('dash', volume=0.35, pitch=1.15)
        # 加速时视野略微拉宽，速度感更强
        self.boost_fov = lerp(self.boost_fov, 10.0 if self.boosting else 0.0,
                              min(1.0, dt * 5.0))
        self.vel = lerp(self.vel, desired, min(1.0, dt * 4.0))
        self.position += self.vel * dt

        if self.vel.length() > 4 and random.random() < (0.85 + (0.5 if self.boosting else 0.0)):
            trail = Entity(model='cube',
                           color=random.choice((color.yellow, color.orange, color.white)),
                           scale=random.uniform(0.25, 0.6),
                           position=self.position - self.forward * 2.9, unlit=True)
            trail.vel = Vec3(0, 0, 0)
            trail.life = 0.4
            particles.append(trail)

        for a in ('fire_cd','dash_cd','heal_cd','invuln','shield_cd','shield_active',
                  'charge_sfx_cd','missile_cd','bomb_cd'):
            v = getattr(self, a)
            if v > 0: setattr(self, a, v-dt)

        if game_state["time"] > 1.0:
            self.thirst = max(0, self.thirst - 0.7*dt)
            self.hunger = max(0, self.hunger - 0.5*dt)
            if self.thirst <= 0: self.hp -= 3*dt
            if self.hunger <= 0: self.hp -= 2*dt
        if self.hp <= 0 and not game_state["over"]:
            self.hp = 0
            game_state["over"] = True
            global shake_t, death_ending, death_t
            shake_t = 1.2
            big_boom(self.position)
            for child, _ in self.parts:
                child.visible = False
            play_sfx('death', volume=1.0)
            if killed_by_boss:
                # 被海盗母舰打死 -> 结局六（母舰一炮轰掉新行星）
                start_ending6()
            else:
                # 被海盗小兵打死 -> 结局三（黑屏 + "永远留下"）
                death_ending = True
                death_t = 0.0

        if not moving and held_keys['j']:
            self.energy = min(self.max_energy, self.energy + 400 * dt)
            if self.charge_sfx_cd <= 0:
                self.charge_sfx_cd = 0.35
                play_sfx('charge', volume=0.25)
            if random.random() < 0.8:
                p_pos = self.position + (self.right * random.uniform(-2.5, 2.5)) + (self.forward * random.uniform(-1, 1))
                p_color = color.white if random.random() < 0.5 else color.cyan
                p = Entity(model='cube', color=p_color, scale=0.3, position=p_pos, unlit=True)
                p.animate_position(self.position + (self.up * 3), duration=0.4)
                p.animate_scale(0, duration=0.4)
                destroy(p, delay=0.4)

        if held_keys['left mouse'] and self.fire_cd <= 0:
            self.shoot()

        if held_keys['space'] and self.dash_cd <= 0: self.dash()
        if held_keys['q'] and self.heal_cd <= 0 and self.hp < self.maxhp:
            self.hp = min(self.maxhp, self.hp+30); self.heal_cd = 3; burst(self.position, color.green, 10)
            play_sfx('pickup', volume=0.3)
        if held_keys['e'] and self.thirst < 100:
            self.thirst = min(100, self.thirst+40); burst(self.position, color.azure, 10)
            play_sfx('pickup', volume=0.3)
        if held_keys['f'] and self.hunger < 100:
            self.hunger = min(100, self.hunger+40); burst(self.position, color.orange, 10)
            play_sfx('pickup', volume=0.3)
        if held_keys['r'] and self.shield_cd <= 0:
            self.shield_active = 4.0; self.shield_cd = 8.0; burst(self.position, color.blue, 20)
            play_sfx('shield', volume=0.45)

        if self.hit_timer > 0:
            self.hit_timer -= dt
            for child, _ in self.parts: child.color = color.white
        elif self.flash_on:
            self.flash_on = False
            for child, orig in self.parts: child.color = orig

    def shoot(self):
        if self.energy < 5: return
        self.energy -= 5
        self.fire_cd = self.fire_rate
        fwd = self.forward
        play_sfx('laser2' if self.weapon == 2 else 'laser',
                 volume=0.35, pitch=random.uniform(0.92, 1.08))

        if self.weapon == 0:
            Bullet(self.position + fwd*3.6, fwd, self.damage, True)
        elif self.weapon == 1:
            for ang in (-15, 0, 15):
                rad = math.radians(ang)
                d = Vec3(fwd.x + math.sin(rad)*fwd.z, fwd.y, fwd.z - math.sin(rad)*fwd.x).normalized()
                Bullet(self.position + d*3.6, d, int(self.damage*0.8), True)
            self.fire_cd = 0.25
        elif self.weapon == 2:
            Bullet(self.position + fwd*3.6, fwd, int(self.damage*0.5), True)
            self.fire_cd = 0.06

    def dash(self):
        if self.energy < 20: return
        self.energy -= 20
        self.dash_cd = 1.5; self.invuln = 0.4
        self.position += self.forward * 15; burst(self.position, color.cyan, 15)
        play_sfx('dash', volume=0.4)

    def take_damage(self, dmg, boss=False):
        if game_state.get('menu'): return
        if self.invuln > 0 or self.shield_active > 0 or game_state["landing"]: return
        global alarm_t, killed_by_boss
        if boss:
            killed_by_boss = True
        alarm_t
        self.hp -= dmg; self.invuln = 0.5; self.hit_timer = 0.2; self.flash_on = True
        alarm_t = 1.2                     # trigger bridge alarm
        play_sfx('damage', volume=0.5)
        play_sfx('alarm', volume=0.45)

class Bullet(Entity):
    def __init__(self, pos, direction, dmg, friendly=True, boss=False, speed=None,
                 size=1.0):
        col = color.cyan if friendly else (color.red if boss else color.orange)
        sc = (0.35, 0.35, 2.2) if boss else (0.2, 0.2, 1.5)
        super().__init__(model='cube', color=col,
                         scale=(sc[0] * size, sc[1] * size, sc[2] * size),
                         position=pos, unlit=True)
        self.boss = boss
        self.speed = speed if speed else (300 if friendly else (70 if boss else 50))
        self.direction = direction.normalized(); self.look_at(self.position + self.direction, axis=Vec3.forward)
        self.dmg = dmg; self.friendly = friendly; self.life = 2.8
        bullets.append(self)
    def update(self):
        self.position += self.direction * self.speed * min(time.dt, 0.1); self.life -= time.dt
        if self.life <= 0: destroy(self)
    def on_destroy(self):
        if self in bullets: bullets.remove(self)


# ================= 特殊武器：追踪导弹 / 全屏炸弹 =================
missiles = []
MISSILE_DMG = 70
MISSILE_LIFE = 6.0
MISSILE_SPEED = 95.0
BOMB_DMG = 90
BOMB_RADIUS = 1500.0
MISSILE_CD = 2.2
BOMB_CD = 16.0


class Missile(Entity):
    """按 4 发射：自动追踪最近的敌机（优先母舰），命中后范围爆炸。"""

    def __init__(self, pos, direction):
        super().__init__(model='cube', color=color.orange, unlit=True,
                         scale=(0.5, 0.5, 2.2), position=pos)
        self.vel = direction.normalized() * MISSILE_SPEED
        self.life = MISSILE_LIFE
        self.target = None
        self.look_at(self.position + self.vel, axis=Vec3.forward)
        missiles.append(self)
        play_sfx('laser2', volume=0.5, pitch=0.7)

    def _pick_target(self):
        best, best_d = None, 1e18
        if mothership is not None and mothership.alive:
            best, best_d = mothership, (mothership.position - self.position).length_squared()
        for e in enemies:
            d = (e.position - self.position).length_squared()
            if d < best_d:
                best, best_d = e, d
        return best

    def update(self):
        dt = min(time.dt, 0.1)
        self.life -= dt
        if self.life <= 0:
            destroy(self)
            return
        if self.target is None or getattr(self.target, 'hp', 1) <= 0:
            self.target = self._pick_target()
        if self.target is not None:
            want = (self.target.position - self.position).normalized() * MISSILE_SPEED
            self.vel = lerp(self.vel, want, min(1.0, dt * 3.5))
        self.position += self.vel * dt
        self.look_at(self.position + self.vel, axis=Vec3.forward)
        # 命中检测
        if mothership is not None and mothership.alive:
            if mothership.hit_test(self.position):
                mothership.take_damage(MISSILE_DMG, self.position)
                self._boom()
                return
        for e in enemies[:]:
            if (e.position - self.position).length_squared() < 6.0 ** 2:
                e.take_damage(MISSILE_DMG)
                self._boom()
                return

    def _boom(self):
        big_boom(self.position)
        play_sfx('explosion', volume=0.55)
        destroy(self)

    def on_destroy(self):
        if self in missiles:
            missiles.remove(self)


def fire_missile():
    if player.missile_cd > 0 or game_state["over"] or game_state["endgame"]:
        return
    player.missile_cd = MISSILE_CD
    Missile(player.position + player.forward * 4.0, player.forward)


_bomb_flash_t = 0.0


def fire_bomb():
    """按 5：全屏炸弹，范围内敌机全部重创，屏幕闪白。

    整个函数包在 try/except 里并写 crash.log —— 之前有用户按 5 直接崩，
    这样即使真出问题也能留下线索而不是整局卡死。
    """
    global _bomb_flash_t
    if game_state.get('menu') or player.bomb_cd > 0 or game_state["over"] or game_state["endgame"]:
        return
    try:
        player.bomb_cd = BOMB_CD
        _bomb_flash_t = 0.18
        play_sfx('explosion', volume=1.0)
        play_sfx('warp', volume=0.6)
        for e in enemies[:]:
            try:
                if (e.position - player.position).length_squared() < BOMB_RADIUS ** 2:
                    e.take_damage(BOMB_DMG)
                    burst(e.position, color.orange, 6)
            except Exception:
                pass
        if mothership is not None and mothership.alive:
            if (mothership.position - player.position).length_squared() < (BOMB_RADIUS + 900) ** 2:
                mothership.take_damage(BOMB_DMG * 2,
                                   mothership.position + Vec3(random.uniform(-300, 300),
                                                              random.uniform(-60, 60),
                                                              random.uniform(-500, 500)))
        big_boom(player.position)
    except Exception:
        _log_exc('fire_bomb')

class Enemy(Entity):
    def __init__(self, kind="basic"):
        theta = random.uniform(0, math.tau)
        phi = math.acos(random.uniform(-1.0, 1.0))   #
        r = random.uniform(150, 380)
        d = Vec3(r * math.sin(phi) * math.cos(theta),
                 r * math.cos(phi),
                 r * math.sin(phi) * math.sin(theta))
        if random.random() < 0.6:
            d = (d + player.forward * r * 1.2).normalized() * r
        pos = player.position + d
        if (pos - planet_pos).length() < PLANET_R + 80:
            pos = player.position - d

        stats = {"basic": (1.0, 30, 8.0, 15), "fast": (0.8, 18, 12.0, 12), "tank": (2.5, 90, 5.0, 30), "shooter": (1.2, 40, 6.0, 20)}
        s, hp, speed, exp = stats[kind]
        super().__init__(scale=s, position=pos)
        self.parts = build_enemy_ship(self, kind)
        self.kind = kind; self.hp = hp; self.maxhp = hp; self.speed = speed; self.exp = exp
        self.shoot_cd = random.uniform(1,3); self.hit_timer = 0; self.flash_on = False; enemies.append(self)

    def update(self):
        if game_state["over"] or game_state["landing"] or game_state["nebula"] or game_state["endgame"]: return
        dt = min(time.dt, 0.1); to_p = player.position - self.position; dist = to_p.length()
        if dist > 0:
            d = to_p.normalized(); self.look_at(player.position, axis=Vec3.forward)
            #  45?5~12
            spd = self.speed * (1.0 if dist < 130 else 3.2)
            if self.kind == "shooter":
                if dist > 25: self.position += d*spd*dt
                elif dist < 15: self.position -= d*spd*dt
                self.shoot_cd -= dt
                if self.shoot_cd <= 0 and dist < 60:
                    self.shoot_cd = 2.0
                    Bullet(self.position, d, 8, False)
                    play_sfx('enemy_laser', volume=0.25, pitch=random.uniform(0.9, 1.1))
            else: self.position += d*spd*dt
        if dist < 3.0: player.take_damage(10)
        if self.hit_timer > 0:
            self.hit_timer -= dt
            for child, _ in self.parts: child.color = color.white
        elif self.flash_on:
            self.flash_on = False
            for child, orig in self.parts: child.color = orig

    def take_damage(self, dmg):
        self.hp -= dmg; self.hit_timer = 0.1; self.flash_on = True
        if self.hp <= 0: self.die()
        else: play_sfx('hit', volume=0.3, pitch=random.uniform(0.9, 1.15))

    def die(self):
        player.kills += 1; player.score += self.exp * 10; player.gain_exp(self.exp)
        for child, orig in self.parts:
            p = Entity(model='cube', color=orig, scale=0.5, position=self.position, unlit=True)
            p.vel = Vec3(random.uniform(-15,15), random.uniform(-15,15), random.uniform(-15,15))
            p.life = 0.5; particles.append(p)
        burst(self.position, color.orange, 14)
        burst(self.position, color.yellow, 8)
        play_sfx('explosion', volume=0.45, pitch=random.uniform(0.9, 1.15))
        r = random.random()
        if r < 0.3: Pickup(self.position, "exp")
        elif r < 0.5: Pickup(self.position, "hp")
        elif r < 0.65: Pickup(self.position, "water")
        elif r < 0.8: Pickup(self.position, "food")
        destroy(self)
    def on_destroy(self):
        if self in enemies: enemies.remove(self)

class Pickup(Entity):
    def __init__(self, pos, kind):
        colors = {"exp": color.green, "hp": color.red, "water": color.azure, "food": color.orange}
        super().__init__(model='cube', color=colors[kind], scale=0.4, position=pos, unlit=True)
        self.kind = kind; self.life = 15.0; pickups.append(self)
    def update(self):
        self.life -= time.dt; self.rotation_y += 90*time.dt
        d = (player.position - self.position).length()
        if d < 10: self.position += (player.position - self.position).normalized()*20*time.dt
        if d < 2.5: self.collect()
        if self.life <= 0: destroy(self)
    def collect(self):
        if self.kind == "exp": player.gain_exp(10)
        elif self.kind == "hp": player.hp = min(player.maxhp, player.hp+20)
        elif self.kind == "water": player.thirst = min(100, player.thirst+40)
        elif self.kind == "food": player.hunger = min(100, player.hunger+40)
        burst(self.position, self.color, 8); destroy(self)
        play_sfx('pickup', volume=0.35)
    def on_destroy(self):
        if self in pickups: pickups.remove(self)

MAX_PARTICLES = 420          # 粒子上限：太多会拖慢帧率


def burst(pos, color=color.white, n=10):
    if len(particles) > MAX_PARTICLES:
        return
    for _ in range(n):
        p = Entity(model='cube', color=color, scale=random.uniform(0.1,0.3), position=pos, unlit=True)
        p.vel = Vec3(random.uniform(-5,5), random.uniform(-5,5), random.uniform(-5,5))
        p.life = 0.4; particles.append(p)

def big_boom(center):
    """big_boom."""
    if len(particles) > MAX_PARTICLES:
        return
    # 1) 火球
    for _ in range(70):
        e = Entity(model='cube', unlit=True,
                   color=random.choice((color.white, color.yellow, color.orange, color.red)),
                   scale=random.uniform(0.4, 1.6),
                   position=center + Vec3(random.uniform(-1.2, 1.2),
                                          random.uniform(-1.2, 1.2),
                                          random.uniform(-1.2, 1.2)))
        d = Vec3(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)).normalized()
        e.vel = d * random.uniform(10, 55)
        e.life = random.uniform(0.7, 1.6)
        particles.append(e)
    # 2) shockwave ring of bright cubes
    for i in range(24):
        ang = math.tau * i / 24
        e = Entity(model='cube', color=color.white, unlit=True, scale=0.8,
                   position=center + Vec3(math.cos(ang), math.sin(ang), 0) * 1.4)
        e.vel = Vec3(math.cos(ang), math.sin(ang), 0) * random.uniform(45, 65)
        e.life = 0.6
        particles.append(e)
    # 3) debris chunks
    for _ in range(14):
        e = Entity(model='cube', unlit=True,
                   color=random.choice((color.dark_gray, C_GRAY, color.red)),
                   scale=random.uniform(0.5, 1.1), position=center)
        d = Vec3(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)).normalized()
        e.vel = d * random.uniform(6, 26)
        e.life = random.uniform(1.0, 1.8)
        particles.append(e)

def update_particles():
    for p in particles[:]:
        p.position += p.vel * time.dt; p.scale *= 0.9; p.life -= time.dt
        if p.life <= 0: destroy(p); particles.remove(p)

def cull_far():
    """cull_far."""
    for e in enemies[:]:
        if (e.position - player.position).length() > CULL_DIST:
            destroy(e)
    for p in pickups[:]:
        if (p.position - player.position).length() > CULL_DIST:
            destroy(p)


# ================= 海盗母舰（结局五） =================
MOTHER_POS = Vec3(2900, 160, 4900)
MOTHER_ENGAGE_DIST = 2200.0       # 玩家靠近到这个距离 -> 母舰开始攻击
MOTHER_SPAWN_DIST = MOTHER_ENGAGE_DIST   # 兼容旧代码
MOTHER_HP = 1600
MOTHER_SCALE = 0.44          # 舰体整体缩放（原尺寸 1320 长，贴近时会糊满全屏）
MOTHER_HIT_R = 330.0              # 子弹命中判定半径
MOTHER_GUN_CD = 2.0
MOTHER_FIGHTER_CD = 6.0

# 母舰建模：分段收窄的船体（不再是"一块大板"）+ 装甲细节 + 舰桥/引擎/炮塔
# 猎兵级歼星舰（Venator-class）：楔形舰体，机头朝 -z，双舰桥在舰尾
MOTHER_CUBES = []

# 楔形主舰体：从机头到舰尾逐段变宽
_HULL_SEGS = [
    (-880, 90, 60, 130),
    (-760, 190, 84, 140),
    (-620, 320, 106, 160),
    (-470, 450, 122, 170),
    (-320, 560, 134, 170),
    (-160, 650, 144, 180),
    (0, 730, 154, 190),
    (180, 790, 160, 200),
    (360, 830, 164, 200),
    (520, 860, 158, 170),
]
for (_z, _w, _h, _l) in _HULL_SEGS:
    MOTHER_CUBES.append(((0, 0, _z), (_w, _h, _l), 'hull'))

MOTHER_CUBES += [
    # 楔面上下的装甲板（让斜面有层次）
    ((0, 78, -100), (520, 26, 700), 'deck'),
    ((0, -78, -100), (480, 26, 700), 'dark'),
    ((0, 82, 400), (620, 26, 300), 'deck'),
    # 舰桥塔（Venator 尾部两座）
    ((-96, 200, 330), (120, 90, 140), 'bridge'),
    ((96, 200, 330), (120, 90, 140), 'bridge'),
    ((-96, 270, 330), (90, 60, 110), 'bridge'),
    ((96, 270, 330), (90, 60, 110), 'bridge'),
    ((-96, 275, 274), (70, 14, 12), 'window'),
    ((96, 275, 274), (70, 14, 12), 'window'),
    ((0, 320, 330), (26, 70, 26), 'light'),
    # 舰桥与舰体之间的上层结构
    ((0, 165, 400), (260, 70, 260), 'deck'),
    ((0, 160, 180), (200, 50, 200), 'deck'),
    # 腹部机库
    ((0, -95, -60), (300, 26, 520), 'dark'),
    ((0, -110, -60), (250, 10, 460), 'glow'),
    # 尾部四台主引擎
    ((-150, 0, 640), (150, 130, 60), 'glow'),
    ((150, 0, 640), (150, 130, 60), 'glow'),
    ((-150, 0, 700), (110, 95, 40), 'hot'),
    ((150, 0, 700), (110, 95, 40), 'hot'),
    ((-300, 0, 660), (80, 80, 50), 'glow'),
    ((300, 0, 660), (80, 80, 50), 'glow'),
    # 舰体识别条纹
    ((-230, 82, -420), (110, 12, 300), 'red'),
    ((230, 82, -420), (110, 12, 300), 'red'),
    # 炮塔底座（炮头由代码另建）
    ((-260, 96, -140), (110, 44, 110), 'deck'),
    ((260, 96, -140), (110, 44, 110), 'deck'),
    ((0, 112, 130), (110, 44, 110), 'deck'),
    # 舷灯
    ((-330, 66, -60), (24, 24, 24), 'red'),
    ((330, 66, -60), (24, 24, 24), 'red'),
]

# 表面细节
random.seed(23)
for _ in range(26):
    _x = random.uniform(-360, 360)
    _z = random.uniform(-780, 560)
    # 越靠舰尾越宽，细节别跑到舰体外面
    _limit = 380 + 480 * ((_z + 880) / 1440.0)
    if abs(_x) > _limit * 0.92:
        _x *= 0.85
    MOTHER_CUBES.append(((_x, 94, _z), (random.uniform(30, 80), 12, random.uniform(36, 100)),
                         'deck' if random.random() < 0.6 else 'dark'))

MOTHER_COLORS = {
    'hull': color.dark_gray, 'deck': C_GRAY, 'bridge': color.light_gray,
    'red': color.red, 'glow': color.orange, 'hot': color.yellow,
    'dark': color.black, 'light': color.white, 'window': color.cyan,
}


class Mothership(Entity):
    """猎兵级歼星舰：1600 血，三座防卫炮 + 主炮，会从腹部机库放出钛战机；打掉它 = 结局五。"""

    def __init__(self):
        super().__init__(position=MOTHER_POS, scale=MOTHER_SCALE, unlit=True)
        self.alive = True
        self.active = False        # 玩家靠近前不开战
        self.hp = MOTHER_HP
        self.maxhp = MOTHER_HP
        self.t = 0.0
        self.gun_cd = MOTHER_GUN_CD
        self.fighter_cd = MOTHER_FIGHTER_CD
        self.hit_flash = 0.0
        self.parts = []
        self.turrets = []
        self._build()
        self._build_turrets()

    def _build(self):
        groups = {}
        for (pos, scale, key) in MOTHER_CUBES:
            col = MOTHER_COLORS[key]
            k = _color_key(col)
            if k not in groups:
                groups[k] = [col, []]
            groups[k][1].append((Vec3(*pos), Vec3(*scale)))
        for col, cubes in groups.values():
            e = Entity(parent=self, model=_merged_cube_mesh(cubes), color=col, unlit=True)
            self.parts.append((e, col))

    def _build_turrets(self):
        """三座防卫炮：底座 + 炮塔 + 双炮管，预先合并成一个 Mesh，用 rotation 瞄准。"""
        spots = [(-250, 60, -190), (250, 60, -190), (0, 100, 250)]
        for (bx, by, bz) in spots:
            cubes = [
                (Vec3(0, -44, 0), Vec3(110, 46, 110)),      # 底座
                (Vec3(0, 0, 0), Vec3(80, 48, 86)),          # 炮塔
                (Vec3(-22, 2, 62), Vec3(16, 16, 116)),      # 左炮管
                (Vec3(22, 2, 62), Vec3(16, 16, 116)),       # 右炮管
                (Vec3(0, 26, -8), Vec3(50, 20, 50)),        # 顶盖
            ]
            tur_ent = Entity(parent=self, model=_merged_cube_mesh(cubes),
                             color=C_GRAY, unlit=True,
                             position=(bx, by + 40, bz))
            muzzle = Entity(parent=tur_ent, model='cube', color=color.orange,
                            scale=0.01, position=(0, 2, 124), unlit=True)
            self.parts.append((tur_ent, C_GRAY))
            self.turrets.append({'ent': tur_ent, 'head': tur_ent, 'muzzle': muzzle,
                                 'cd': random.uniform(0.4, 1.6), 'flash': 0.0})

    def _fire_turret(self, tur, angles, dmg, speed, spread_pitch=0.0):
        head = tur['head']
        try:
            fwd = head.forward            # Ursina 没有 world_forward
            fwd = Vec3(fwd.x, fwd.y, fwd.z).normalized()
        except Exception:
            ry = math.radians(float(getattr(head, 'world_rotation_y', head.rotation_y)))
            fwd = Vec3(math.sin(ry), 0.0, math.cos(ry))
        try:
            origin = head.world_position + fwd * 110
        except Exception:
            origin = head.position + fwd * 110
        for ang in angles:
            a = math.radians(ang)
            d = Vec3(fwd.x * math.cos(a) + fwd.z * math.sin(a),
                     fwd.y + math.tan(math.radians(spread_pitch)),
                     -fwd.x * math.sin(a) + fwd.z * math.cos(a)).normalized()
            Bullet(origin, d, dmg, False, boss=True, speed=speed, size=1.25)
        tur['flash'] = 0.08
        play_sfx('enemy_laser', volume=0.4, pitch=random.uniform(0.8, 1.0))

    def flash_hit(self, pos):
        """被打中：闪白/红光 + 火花 + 命中光圈。"""
        self.hit_flash = 0.24
        if pos is None:
            pos = self.position + Vec3(random.uniform(-260, 260),
                                       random.uniform(-60, 60),
                                       random.uniform(-400, 400))
        for _ in range(7):
            p = Entity(model='cube', unlit=True,
                       color=random.choice((color.white, color.yellow, color.orange)),
                       scale=random.uniform(5, 16), position=pos)
            p.vel = Vec3(random.uniform(-120, 120), random.uniform(-120, 120),
                         random.uniform(-120, 120))
            p.life = random.uniform(0.25, 0.55)
            particles.append(p)
        flare = Entity(model='cube', unlit=True, color=color.white,
                       scale=46, position=pos)
        flare.vel = Vec3(0, 0, 0)
        flare.life = 0.16
        particles.append(flare)
        global shake_t
        shake_t = max(shake_t, 0.14)

    def hit_test(self, pos):
        """判断一点是否落在船体上（把点转到船体局部坐标，用长方体近似）。"""
        d = pos - self.position
        ry = math.radians(-self.rotation_y)
        c, sn = math.cos(ry), math.sin(ry)
        lx = d.x * c - d.z * sn
        lz = d.x * sn + d.z * c
        k = MOTHER_SCALE
        return abs(lx) < 440 * k and abs(d.y) < 280 * k and abs(lz) < 820 * k

    def take_damage(self, dmg, pos=None):
        if not self.alive:
            return
        self.hp -= dmg
        self.flash_hit(pos)
        if self.hp <= 0:
            self.hp = 0
            self.die()

    def die(self):
        global boss_ending, death_t, mothership
        if not self.alive:
            return
        self.alive = False
        for _ in range(3):
            big_boom(self.position + Vec3(random.uniform(-160, 160),
                                          random.uniform(-80, 80),
                                          random.uniform(-260, 260)))
        play_sfx('explosion', volume=1.0)
        play_sfx('victory', volume=0.7)
        self.visible = False
        boss_ending = True
        death_ending = False
        ds_ending = False
        nebula_ending = False
        game_state['over'] = True
        death_t = 0.0
        try:
            _boss_ui_show(False)
        except Exception:
            pass

    def think(self):
        if not self.alive or ending6:
            return
        dt = min(time.dt, 0.1)
        self.t += dt
        # 轻微上下浮动
        self.y = MOTHER_POS.y + math.sin(self.t * 0.6) * 12
        if not self.active:
            return          # 还没进入战斗：不开炮、不放飞机、不显示血条
        # 受击：船体底色 -> 亮银白 的快速脉冲（不再是整船纯红）+ 命中点火花
        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt)
            k = max(0.0, self.hit_flash / 0.24)
            k = k if int(self.hit_flash * 60) % 2 == 0 else k * 0.35
            for e, base in self.parts:
                e.color = _mix_color(base, color.white, 0.60 * k)
            if self.hit_flash <= 0:
                for e, base in self.parts:
                    e.color = base

        # ---- 3 座防卫炮：靠近就启动，跟踪玩家，按距离切换 1/2/3 号武器 ----
        to_player = player.position
        for tur in self.turrets:
            head = tur['head']
            if tur['flash'] > 0:
                tur['flash'] = max(0.0, tur['flash'] - dt)
                try:
                    tur['muzzle'].scale = 26 if tur['flash'] > 0 else 0.01
                except Exception:
                    pass
            if not player.visible:
                continue
            try:
                d = to_player - head.world_position
                flat = math.hypot(d.x, d.z)
                head.rotation_y = math.degrees(math.atan2(d.x, d.z))
                head.rotation_x = -math.degrees(math.atan2(d.y, flat))
            except Exception:
                pass
            tur['cd'] -= dt
            if tur['cd'] > 0:
                continue
            dist = (to_player - head.world_position).length()
            if dist > 800:
                # 远距离：1 号武器（单发，伤害高）
                tur['cd'] = 1.7
                self._fire_turret(tur, (0.0,), 22, 100)
            elif dist > 500:
                # 中距离：2 号武器（三连散射）
                tur['cd'] = 2.0
                self._fire_turret(tur, (-15.0, 0.0, 15.0), 14, 95)
            else:
                # 近距离：3 号武器（快速连射）
                tur['cd'] = 0.20
                self._fire_turret(tur, (0.0,), 8, 140, spread_pitch=random.uniform(-1.5, 1.5))
        # 主炮：朝玩家打
        self.gun_cd -= dt
        if self.gun_cd <= 0 and not game_state['over']:
            self.gun_cd = MOTHER_GUN_CD
            for off in (Vec3(-270, 70, -230), Vec3(270, 70, -230), Vec3(0, 130, -300)):
                start = self.position + off
                d = (player.position - start).normalized()
                Bullet(start + d * 8, d, 16, False, boss=True)
            play_sfx('enemy_laser', volume=0.45, pitch=0.75)
        # 从腹部机库放出钛战机（歼星舰的招牌手段）
        self.fighter_cd -= dt
        if self.fighter_cd <= 0 and len(enemies) < 26 and not game_state['over']:
            self.fighter_cd = MOTHER_FIGHTER_CD
            hangar = self.position + Vec3(0, -70 * MOTHER_SCALE, -60 * MOTHER_SCALE)
            play_sfx('warp', volume=0.45, pitch=1.35)
            burst(hangar, color.cyan, 8)
            for _ in range(2):
                e = Enemy('fast' if random.random() < 0.55 else 'basic')
                e.position = hangar + Vec3(random.uniform(-140, 140),
                                           random.uniform(-40, 40),
                                           random.uniform(-260, -60))
                e.look_at(player.position, axis=Vec3.forward)
        # 血条
        try:
            _boss_ui_show(True, self.hp / float(self.maxhp))
        except Exception:
            pass


def update_mothership():
    """母舰一直存在于世界里（远处就能看见），靠近到一定距离才开战。"""
    global mothership
    if game_state.get('menu') or game_state['intro'] or game_state['endgame'] \
            or game_state.get('handoff') or game_state['landing'] or game_state['nebula']:
        return
    if mothership is None:
        # 出生就给一艘，玩家老远就能看到它（不再"飞近了突然闪现"）
        mothership = Mothership()
    if not mothership.alive:
        return
    dist = (mothership.position - player.position).length()
    if not mothership.active and dist <= MOTHER_ENGAGE_DIST:
        mothership.active = True
        play_sfx('alarm', volume=0.6)
        play_sfx('nebula', volume=0.5)
        burst(player.position, color.red, 12)
    mothership.think()


# ================= 结局六：被母舰打死 -> 它一炮轰掉新行星 =================
def start_ending6():
    global ending6, ending6_state, ending6_t, death_t
    ending6 = True
    ending6_state = 'boom'
    ending6_t = 0.0
    death_t = 0.0
    try:
        _hud_visible(False)      # 过场里别显示血条/提示
        _boss_ui_show(False)
        _set_text(over_text, '')
    except Exception:
        pass


def _destroy_planet():
    """新行星被炮弹命中：连续爆炸 + 整颗藏起来。"""
    global _bomb_flash_t
    for _ in range(4):
        big_boom(planet_pos + Vec3(random.uniform(-160, 160),
                                   random.uniform(-160, 160),
                                   random.uniform(-160, 160)))
    for e in planet_parts:
        try:
            e.visible = False
        except Exception:
            pass
    play_sfx('explosion', volume=1.0)
    play_sfx('death', volume=0.7)
    _bomb_flash_t = 0.35


def update_ending6():
    """母舰转向行星 -> 开炮 -> 行星炸掉 -> 黑屏。"""
    global ending6_state, ending6_t, ds_projectile
    if not ending6 or game_state['endgame']:
        return
    dt = min(time.dt, 0.1)
    ending6_t += dt
    ms = mothership

    if ending6_state == 'boom':
        if ending6_t >= 1.0:
            ending6_state = 'aim'
            ending6_t = 0.0
            play_sfx('charge', volume=0.8)

    elif ending6_state == 'aim':
        if ms is not None:
            # 模型机头朝 -z，所以让 +z 背对行星 = 炮口对准行星
            away = ms.position - planet_pos
            ms.look_at(ms.position + away, axis=Vec3.forward)
        if ending6_t >= 1.3:
            ending6_state = 'fire'
            ending6_t = 0.0

    elif ending6_state == 'fire':
        if ds_projectile is None and ms is not None:
            d = (planet_pos - ms.position).normalized()
            p = Entity(model='cube', color=color.yellow, unlit=True,
                       scale=(34, 34, 34), position=ms.position + d * 600)
            p.vel = d * 2600
            ds_projectile = p
            play_sfx('laser2', volume=0.9, pitch=0.6)
        if ds_projectile is not None:
            ds_projectile.position += ds_projectile.vel * dt
            if (ds_projectile.position - planet_pos).length() < PLANET_R + 140:
                destroy(ds_projectile)
                ds_projectile = None
                _destroy_planet()
                ending6_state = 'hit'
                ending6_t = 0.0
        if ending6_state == 'fire' and ending6_t > 2.4:
            if ds_projectile is not None:
                destroy(ds_projectile)
                ds_projectile = None
            _destroy_planet()
            ending6_state = 'hit'
            ending6_t = 0.0

    elif ending6_state == 'hit':
        if ending6_t >= 1.4:
            ending6_state = 'done'
            _enter_endgame()

def spawn_loop():
    # 主菜单里绝对不能再刷怪（否则玩家在菜单会被打、还会一直扣血）
    if game_state.get("menu") or game_state["intro"] or game_state["nebula"] \
            or game_state.get("handoff"):
        invoke(spawn_loop, delay=0.5); return
    if game_state["over"] or game_state["paused"] or game_state["landing"]: invoke(spawn_loop, delay=1); return
    # keep a minimum number of enemies within CULL_DIST of the player
    near = sum(1 for e in enemies if (e.position - player.position).length() < CULL_DIST)
    if len(enemies) < MAX_ENEMIES and near < MIN_NEAR_ENEMIES:
        r = random.random()
        if r < 0.6: Enemy("basic")
        elif r < 0.8: Enemy("fast")
        elif r < 0.9: Enemy("tank")
        else: Enemy("shooter")
    invoke(spawn_loop, delay=max(0.22, 1.0 - game_state["time"]*0.01))

def check_collisions():
    if game_state["landing"] or game_state["nebula"]: return
    ms = mothership
    for b in bullets[:]:
        if ms is not None and ms.alive and b.friendly:
            if ms.hit_test(b.position):
                ms.take_damage(b.dmg, b.position)
                burst(b.position, color.orange, 3)
                destroy(b)
                continue
        for e in enemies[:]:
            if (b.position - e.position).length_squared() < 6.25: e.take_damage(b.dmg); destroy(b); break
        else:
            if not b.friendly and (player.position - b.position).length_squared() < 6.25:
                player.take_damage(b.dmg, boss=getattr(b, 'boss', False)); destroy(b)

def global_update():
    if game_state.get('menu'):
        invoke(global_update, delay=0.1)     # 主菜单里只保持心跳，不做任何模拟
        return
    update_particles()
    check_collisions()
    update_stars()
    cull_far()
    if (not game_state["over"] and not game_state["paused"]
            and not game_state.get("handoff") and not game_state["intro"]):
        game_state["time"] += time.dt
    # 距离剔除/碰撞不需要 33Hz：交替执行，省一半开销
    invoke(global_update, delay=0.045)

# ================= camera =================
camera.parent = camera_rig
camera.position = (0, 0, 0)
camera.rotation = (0, 0, 0)

# ================= 天空：程序化生成的银河全景（等距柱状投影） =================
sky_dome = None
try:
    if os.path.exists(os.path.join(BASE_DIR, 'textures', 'sky_pano.jpg')):
        sky_dome = Sky(texture='textures/sky_pano')
        try:
            sky_dome.color = Vec4(0.80, 0.82, 0.90, 1.0)   # 稍微压暗，别抢画面
        except Exception:
            pass
except Exception:
    sky_dome = None
# Ursina 8.3 的默认垂直 FOV 只有 40，视野窄得像长焦；改成 68 更符合太空飞行手感
try:
    camera.fov = 68
except Exception:
    pass

def update_camera():
    if not player: return

    # 结局六过场：把镜头拉到母舰侧后方，让"母舰"和"新行星"同框
    if ending6 and not game_state['endgame'] and mothership is not None:
        try:
            to_ms = (mothership.position - planet_pos).normalized()
            cam = planet_pos + to_ms * 2600 + Vec3(0, 1300, 0)
            camera_rig.position = cam
            camera_rig.look_at((mothership.position + planet_pos) * 0.5
                               + Vec3(0, 60, 0), axis=Vec3.forward)
            camera.position = (0, 0, 0)
            camera.rotation = (0, 0, 0)
            return
        except Exception:
            pass

    if game_state["landing"]:
        # camera stays where it was and tracks the ship
        camera.look_at(player.position, axis=Vec3.forward)
        return

    camera_rig.position = player.position
    camera_rig.rotation = Vec3(player.pitch, player.yaw, 0)

    if camera_mode == 1:
        camera.position = (0, 8, -28)
        camera.rotation_x = 15
        try:
            base_fov = CAMERA_BASE_FOV + getattr(player, 'boost_fov', 0.0)
            if abs(camera.fov - base_fov) > 0.05:
                camera.fov = base_fov
        except Exception:
            pass
    elif camera_mode == 2:
        camera.position = (0, 2, 6)
        camera.rotation_x = 0
    elif camera_mode == 3:
        camera.position = (0, 2, 6)
        camera.rotation_x = 0

    #  / D/
    amp = max(player.hit_timer * 10 if player.hit_timer > 0 else 0.0, shake_t * 16)
    if amp > 0:
        camera.position += Vec3(random.uniform(-amp, amp), random.uniform(-amp, amp),
                               random.uniform(-amp * 0.3, amp * 0.3))

# ================= UI =================
# 中文字体：必须放在项目里的 fonts/ 目录（Ursina 只会在 asset_folder/fonts_folder 里找字体，
# 传绝对路径会提示 "missing font" 且显示不出汉字）
CN_FONT = 'fonts/msyh.ttc'
if not os.path.exists(os.path.join(BASE_DIR, 'fonts', 'msyh.ttc')):
    if os.path.exists(os.path.join(BASE_DIR, 'fonts', 'simhei.ttf')):
        CN_FONT = 'fonts/simhei.ttf'

def _T(**kw):
    """创建带中文字体的 Text（统一入口，避免漏掉 font 参数）。"""
    kw.setdefault('font', CN_FONT)
    try:
        return Text(**kw)
    except Exception:
        kw.pop('font', None)
        return Text(**kw)

bar_x = -0.8
bar_w = 0.3
start_y = 0.42
gap = 0.08

mission_text = _T(text=t('mission'),
                  position=(0, 0.45), origin=(0,0), scale=1.1, color=color.yellow)

def make_bar(y, h, fg_color):
    return Entity(parent=camera.ui, model='quad', color=fg_color, scale=(bar_w, h), position=(bar_x, y), origin=(-0.5, 0))

hp_bar = make_bar(start_y, 0.03, color.red)
exp_bar = make_bar(start_y-gap, 0.015, color.cyan)
thirst_bar = make_bar(start_y-gap*2, 0.02, color.azure)
hunger_bar = make_bar(start_y-gap*3, 0.02, color.orange)
energy_bar = make_bar(start_y-gap*4, 0.02, color.violet)

def make_label(y):
    # 文字放在条的上方一点，避免和条重叠
    return _T(text="", position=(bar_x - 0.02, y + 0.045), scale=0.95, color=color.white)

label_hp = make_label(start_y)
label_water = make_label(start_y-gap*2)

label_food = make_label(start_y-gap*3)
label_energy = make_label(start_y-gap*4)
label_weapon = _T(text="", position=(bar_x, start_y-gap*5), scale=1.0, color=color.yellow)
label_special = _T(text="", position=(bar_x, start_y-gap*6), scale=0.8, color=C_GRAY)
label_boss_dir = _T(text="", position=(0, 0.30), origin=(0, 0), scale=0.9, color=color.orange)
# 底部操作提示（F2 显示/隐藏）
hint_text = _T(text="", position=(0, -0.415), origin=(0, 0), scale=0.56, color=C_GRAY)
label_camera = _T(text="", position=(0.3, 0.38), scale=1.0, color=color.white)

landing_prompt = _T(text="", position=(0, -0.3), origin=(0,0), scale=1.8, color=color.yellow)
nebula_prompt = _T(text="", position=(0, -0.3), origin=(0,0), scale=1.8, color=color.cyan)
over_text = _T(text="", position=(0, 0.0), origin=(0,0), scale=1.6, color=color.yellow)

# ---- 母舰血条（屏幕顶部） ----
boss_bar_bg = Entity(parent=camera.ui, model='quad', color=color.dark_gray,
                     scale=(0.86, 0.024), position=(0, 0.468), z=0.05, enabled=False)
boss_bar = Entity(parent=camera.ui, model='quad', color=color.red,
                  scale=(0.85, 0.016), position=(-0.425, 0.468), origin=(-0.5, 0),
                  z=0.0, enabled=False)
boss_label = _T(text="", position=(0, 0.436), origin=(0, 0), scale=0.85,
                color=color.white, z=-0.1)
boss_label.text = ""
_boss_last_hp = -1


def _boss_ui_show(show, frac=None):
    """显示/更新母舰血条（文字只在血量变化时才重设，避免每帧重建字体网格）。"""
    global _boss_last_hp
    try:
        boss_bar_bg.enabled = show
        boss_bar.enabled = show
        # 母舰出现时把顶部任务文字让出来
        _set_text(mission_text, '' if show else t('mission'))
        if not show:
            global _boss_last_hp
            _boss_last_hp = -1
            _set_text(boss_label, "")
            return
        if frac is not None:
            boss_bar.scale_x = 0.85 * max(0.001, min(1.0, frac))
            hp_int = int(round(frac * MOTHER_HP))
            if hp_int != _boss_last_hp:
                _boss_last_hp = hp_int
                _set_text(boss_label, f"{t('boss_name')}   {hp_int} / {MOTHER_HP}")
    except Exception:
        pass

# Python / Ursina version tag for the diag line
try:
    import ursina as _ursina_mod
    _URSINA_VER = getattr(_ursina_mod, '__version__', getattr(_ursina_mod, 'version', '?'))
except Exception:
    _URSINA_VER = '?'
def _audio_status():
    """DIAG 行里显示音频后端状态：urs:20/20 表示 Ursina/OpenAL 正常加载了全部音效。"""
    if not SFX_ON:
        return t('diag_off')
    tag = {'ursina': 'urs', 'winsound': 'winsnd', 'none': 'none'}.get(SFX_BACKEND, SFX_BACKEND)
    return f'{tag}:{len(SFX)}/{len(SOUND_SPECS)}'

def _diag_line(fps=None):
    bits = [f"PY {sys.version_info.major}.{sys.version_info.minor}",
            f"{t('diag_engine')} {_URSINA_VER}",
            f"{t('diag_audio')} {_audio_status()}"]
    if fps is not None:
        bits.append(f"FPS {fps}")
    return "  |  ".join(bits) + f"  |  {t('diag_hide')}"

diag_text = _T(text=_diag_line(), position=(-0.42, -0.47), origin=(0, 0),
               scale=0.7, color=C_GRAY)

# ---- 降落过场字幕 + 结算面板 ----
seq_text = _T(text="", position=(0, 0.15), origin=(0, 0), scale=1.4, color=color.yellow)

settle_tag = _T(text="", position=(0, 0.42), origin=(0, 0), scale=1.1, color=color.yellow)
settle_title = _T(text="", position=(0, 0.28), origin=(0, 0), scale=1.7, color=color.yellow)
settle_stats = _T(text="", position=(0, 0.06), origin=(0, 0), scale=1.1, color=color.yellow)
settle_prompt = _T(text="", position=(0, -0.42), origin=(0, 0), scale=0.95, color=color.yellow)

def _make_button(label, x, y=-0.30, w=0.3, h=0.11, scale=1.25):
    """按钮 = 一个纯色方块 + 一个独立的 Text（Button 自带的 text 会跟着按钮被压得很小）。"""
    b = Button(text='', scale=(w, h), position=(x, y), color=color.dark_gray)
    try:
        b.parent = camera.ui       # older Button versions may not default to the UI
    except Exception:
        pass
    b.visible = False
    b.label_text = _T(text=label, position=(x, y), origin=(0, 0), scale=scale,
                      color=color.yellow, z=-0.1)
    b.label_text.visible = False
    b.label_key = None
    return b

btn_restart = _make_button(t('btn_restart'), -0.19)
btn_restart.label_key = 'btn_restart'
btn_restart.on_click = lambda: (play_sfx('ui'), restart())
btn_exit = _make_button(t('btn_menu'), 0.19)
btn_exit.label_key = 'btn_menu'
btn_exit.on_click = lambda: (play_sfx('ui'), back_to_menu())

def _show_buttons(show):
    for b in (btn_restart, btn_exit):
        try:
            b.visible = show
            if getattr(b, 'label_text', None) is not None:
                b.label_text.visible = show
        except Exception:
            pass

HUD_ITEMS = (mission_text, hp_bar, exp_bar, thirst_bar, hunger_bar, energy_bar,
             label_hp, label_water, label_food, label_energy, label_weapon,
             label_special, label_camera, landing_prompt, nebula_prompt, label_boss_dir,
             hint_text)

def _hud_visible(show):
    for it in HUD_ITEMS:
        it.visible = show

# ================= 主菜单 / 设置界面 =================
_UI_ASPECT = 16.0 / 9.0
try:
    _UI_ASPECT = window.aspect_ratio
except Exception:
    pass

# 亮度覆盖层：在 3D 世界之上、HUD 之下（z 为正 = 更靠后，不会盖住 UI 文字）
_bright_overlay = Entity(parent=camera.ui, model='quad', texture='textures/ui/dim_00.png',
                         scale=(_UI_ASPECT, 1.0), z=0.5, enabled=False)

# ---- 黑场淡入淡出（片头 -> 交接镜头时用来遮住跳切） ----
_fade_overlay = Entity(parent=camera.ui, model='quad', texture='textures/ui/dim_00.png',
                       scale=(_UI_ASPECT, 1.0), z=0.06, enabled=False)
_fade_from = 0.0
_fade_to = 0.0
_fade_t = 0.0
_fade_dur = 0.0


def _fade_alpha():
    if _fade_dur <= 0:
        return _fade_to
    k = min(1.0, _fade_t / _fade_dur)
    return _fade_from + (_fade_to - _fade_from) * k


def _start_fade(to, dur):
    global _fade_from, _fade_to, _fade_t, _fade_dur
    _fade_from = _fade_alpha()
    _fade_to = float(to)
    _fade_t = 0.0
    _fade_dur = max(0.01, float(dur))


def update_fade():
    global _fade_t, _fade_dur
    if _fade_dur <= 0:
        if getattr(_fade_overlay, 'enabled', False):
            _fade_overlay.enabled = False
        return
    _fade_t = min(_fade_dur, _fade_t + min(time.dt, 0.1))
    lvl = int(round(_fade_alpha() * 20.0)) * 5
    lvl = max(0, min(100, lvl))
    try:
        _fade_overlay.texture = f'textures/ui/dim_{lvl:02d}.png'
        _fade_overlay.enabled = lvl > 0
    except Exception:
        pass
    if _fade_t >= _fade_dur:
        _fade_dur = 0.0

menu_root = Entity(parent=camera.ui, enabled=True)
Entity(parent=menu_root, model='quad', texture='textures/menu_bg.png',
       scale=(_UI_ASPECT, 1.0), z=0.9)
Entity(parent=menu_root, model='quad', texture='textures/ui/dim_35.png',
       scale=(_UI_ASPECT, 1.0), z=0.8)
menu_title = _T(parent=menu_root, text=t('game_title'), position=(0, 0.335), origin=(0, 0),
               scale=2.3, color=color.yellow, z=-0.2)
Entity(parent=menu_root, model='quad', color=color.azure,
       scale=(0.46, 0.006), position=(0, 0.245), z=-0.15)
menu_hint = _T(parent=menu_root, text=t('menu_hint'), position=(0, -0.455), origin=(0, 0),
               scale=0.75, color=C_GRAY, z=-0.2)


def _menu_button(key, y, callback, w=0.46, h=0.115, scale=1.45):
    b = _make_button(t(key), 0, y, w, h, scale)
    b.label_key = key
    try:
        b.parent = menu_root
        b.label_text.parent = menu_root
    except Exception:
        pass
    b.enabled = True
    b.visible = True
    b.label_text.visible = True
    b.on_click = lambda: (play_sfx('ui'), callback())
    return b


btn_start = _menu_button('menu_start', 0.16, lambda: start_game(), h=0.105)
btn_settings = _menu_button('menu_settings', 0.04, lambda: open_settings(), h=0.105)
btn_credits = _menu_button('menu_credits', -0.08, lambda: open_credits(), h=0.105)
btn_quit = _menu_button('menu_quit', -0.20, lambda: application.quit(), h=0.105)

# ---- 右下角：结局收集图标（达成了=彩色，没达成=灰色） ----
ENDINGS_LABEL = _T(parent=menu_root, text=t('menu_endings'), position=(0.565, -0.335),
                   origin=(0, 0), scale=0.62, color=C_GRAY, z=-0.2)
ENDING_ICONS = []
for _i in range(ENDINGS_COUNT):
    _icon = Entity(parent=menu_root, model='quad',
                   texture=f'textures/ui/ending_{_i + 1}_off.png',
                   scale=(0.062, 0.062), position=(0.36 + _i * 0.082, -0.415), z=-0.2)
    ENDING_ICONS.append(_icon)


def _refresh_ending_icons():
    """按已达成状态切换彩色 / 灰色图标。"""
    ends = SETTINGS.get('endings') or [False] * ENDINGS_COUNT
    for i, icon in enumerate(ENDING_ICONS):
        try:
            on = bool(ends[i]) if i < len(ends) else False
            icon.texture = (f'textures/ui/ending_{i + 1}.png' if on
                            else f'textures/ui/ending_{i + 1}_off.png')
        except Exception:
            pass

# ---- 设置面板 ----
settings_root = Entity(parent=camera.ui, enabled=False)
Entity(parent=settings_root, model='quad', texture='textures/menu_bg.png',
       scale=(_UI_ASPECT, 1.0), z=0.9)
Entity(parent=settings_root, model='quad', texture='textures/ui/dim_70.png',
       scale=(_UI_ASPECT, 1.0), z=0.8)
settings_title = _T(parent=settings_root, text=t('settings_title'), position=(0, 0.36),
                    origin=(0, 0), scale=1.9, color=color.yellow, z=-0.2)

SETTINGS_ROWS = {}


def _setting_arrow(text, x, y, callback):
    # 注意：Ursina 的 Text 会把 '<' 当成富文本标签，所以箭头用 ASCII 的 - 和 +
    b = _make_button(text, x, y, w=0.07, h=0.07, scale=1.5)
    for e in (b, b.label_text):
        try:
            e.parent = settings_root
        except Exception:
            pass
    b.enabled = True
    b.visible = True
    b.label_text.visible = True
    b.on_click = lambda: (play_sfx('ui'), callback())
    return b


def _settings_row(key, y, on_minus, on_plus):
    label = _T(parent=settings_root, text=t(key), position=(-0.55, y), origin=(0, 0),
               scale=1.15, color=color.white, z=-0.2)
    value = _T(parent=settings_root, text="", position=(0.04, y), origin=(0, 0),
               scale=1.15, color=color.yellow, z=-0.2)
    minus = _setting_arrow('-', -0.14, y, on_minus)
    plus = _setting_arrow('+', 0.24, y, on_plus)
    SETTINGS_ROWS[key] = {'label': label, 'value': value, 'minus': minus, 'plus': plus}


def _vol_minus():
    SETTINGS['volume'] = max(0.0, round(SETTINGS['volume'] - 0.1, 2))
    apply_volume(); _refresh_settings_values(); _save_settings()


def _vol_plus():
    SETTINGS['volume'] = min(1.0, round(SETTINGS['volume'] + 0.1, 2))
    apply_volume(); _refresh_settings_values(); _save_settings()


def _bri_minus():
    SETTINGS['brightness'] = max(0.60, round(SETTINGS['brightness'] - 0.05, 2))
    apply_brightness(); _refresh_settings_values(); _save_settings()


def _bri_plus():
    SETTINGS['brightness'] = min(1.40, round(SETTINGS['brightness'] + 0.05, 2))
    apply_brightness(); _refresh_settings_values(); _save_settings()


def _lang_toggle():
    _set_language('en' if LANG == 'zh' else 'zh')


def _light_toggle():
    SETTINGS['lighting'] = not bool(SETTINGS.get('lighting', True))
    apply_lighting(); _refresh_settings_values(); _save_settings()


_settings_row('settings_volume', 0.24, _vol_minus, _vol_plus)
_settings_row('settings_brightness', 0.11, _bri_minus, _bri_plus)
_settings_row('settings_language', -0.02, _lang_toggle, _lang_toggle)
_settings_row('settings_lighting', -0.15, _light_toggle, _light_toggle)
btn_settings_back = _menu_button('settings_back', -0.40, lambda: close_settings(), w=0.3, h=0.10, scale=1.3)
btn_settings_back.parent = settings_root
btn_settings_back.label_text.parent = settings_root

# 清空结局数据
btn_clear_endings = _menu_button('settings_clear', -0.27, lambda: _clear_endings(), w=0.34, h=0.095, scale=1.2)
btn_clear_endings.parent = settings_root
btn_clear_endings.label_text.parent = settings_root
_clear_tip = _T(parent=settings_root, text="", position=(0.30, -0.24), origin=(0, 0),
                scale=0.7, color=color.orange, z=-0.2)


def _clear_endings():
    """把达成的结局全部清空（图标变灰）并提示一下。"""
    SETTINGS['endings'] = [False] * ENDINGS_COUNT
    _save_settings()
    _refresh_ending_icons()
    try:
        _clear_tip.text = t('settings_cleared')
    except Exception:
        pass


def _refresh_settings_values():
    rows = SETTINGS_ROWS
    if not rows:
        return
    try:
        rows['settings_volume']['value'].text = f"{int(round(SETTINGS['volume'] * 100))}%"
        rows['settings_brightness']['value'].text = f"{int(round(SETTINGS['brightness'] * 100))}%"
        rows['settings_language']['value'].text = t('lang_name')
        rows['settings_lighting']['value'].text = t('on') if SETTINGS.get('lighting', True) else t('off')
    except Exception:
        pass


def _apply_language():
    """切语言后刷新所有静态文字（动态的 HUD / 结算每帧自己取 t()）。"""
    g = globals()
    try:
        mission_text.text = t('mission')
    except Exception:
        pass
    for name, key in (('menu_title', 'game_title'), ('menu_hint', 'menu_hint'),
                      ('settings_title', 'settings_title'),
                      ('ENDINGS_LABEL', 'menu_endings'),
                      ('credits_title', 'credits_title'),
                      ('credits_body', 'credits_body')):
        e = g.get(name)
        if e is not None:
            try:
                e.text = t(key)
            except Exception:
                pass
    for b in (g.get('btn_start'), g.get('btn_settings'), g.get('btn_quit'),
              g.get('btn_settings_back'), g.get('btn_restart'), g.get('btn_exit'),
              g.get('btn_clear_endings')):
        if b is not None and getattr(b, 'label_key', None):
            try:
                b.label_text.text = t(b.label_key)
            except Exception:
                pass
    for key, row in SETTINGS_ROWS.items():
        try:
            row['label'].text = t(key)
        except Exception:
            pass
    # 注意：intro_skip 由 update_intro 每帧刷新，这里不要动它（否则主菜单里会冒出“按空格跳过片头”）
    _refresh_settings_values()
    try:
        diag_text.text = _diag_line()
    except Exception:
        pass


# ---- 制作者名单面板 ----
credits_root = Entity(parent=camera.ui, enabled=False)
Entity(parent=credits_root, model='quad', texture='textures/menu_bg.png',
       scale=(_UI_ASPECT, 1.0), z=0.9)
Entity(parent=credits_root, model='quad', texture='textures/ui/dim_90.png',
       scale=(_UI_ASPECT, 1.0), z=0.8)
credits_title = _T(parent=credits_root, text=t('credits_title'), position=(0, 0.46),
                   origin=(0, 0), scale=1.7, color=color.yellow, z=-0.2)
credits_body = _T(parent=credits_root, text=t('credits_body'), position=(0, 0.08),
                  origin=(0, 0), scale=0.78, color=color.white, z=-0.2)
btn_credits_back = _menu_button('credits_back', -0.42, lambda: close_credits(),
                                w=0.3, h=0.10, scale=1.3)
btn_credits_back.parent = credits_root
btn_credits_back.label_text.parent = credits_root


def open_credits():
    game_state['credits'] = True
    menu_root.enabled = False
    credits_root.enabled = True
    try:
        diag_text.enabled = False
    except Exception:
        pass
    play_sfx('ui', volume=0.4)


def close_credits():
    game_state['credits'] = False
    credits_root.enabled = False
    menu_root.enabled = bool(game_state.get('menu'))


def open_settings():
    try:
        if game_state.get('credits'):
            game_state['credits'] = False
            credits_root.enabled = False
    except Exception:
        pass
    game_state['settings'] = True
    menu_root.enabled = False
    settings_root.enabled = True
    try:
        diag_text.enabled = False
    except Exception:
        pass


def close_settings():
    game_state['settings'] = False
    settings_root.enabled = False
    menu_root.enabled = bool(game_state.get('menu'))


def _hide_menu():
    game_state['menu'] = False
    menu_root.enabled = False
    close_settings()
    close_credits()


def _show_menu():
    game_state['menu'] = True
    menu_root.enabled = True
    settings_root.enabled = False
    game_state['settings'] = False
    try:
        credits_root.enabled = False
        game_state['credits'] = False
    except Exception:
        pass
    _refresh_ending_icons()
    try:
        _clear_tip.text = ""
    except Exception:
        pass
    try:
        diag_text.enabled = False
    except Exception:
        pass
    apply_brightness()


def _landing_caption(tt):
    """降落字幕：按时间点逐条打出（打字机效果），文案跟随当前语言。"""
    out = []
    for t0, key in zip(LANDING_TIMES, LANDING_KEYS):
        if tt < t0:
            break
        line = t(key)
        out.append(line[:int((tt - t0) * CPS)])
    return "\n".join(out)

ui_text_t = 0.0
fps_t = 0.0
fps_frames = 0
_world_hidden = False
_type_last = 0          # ?
def _set_world_visible(show):
    """_set_world_visible."""
    global _world_hidden
    _world_hidden = not show
    for e in stars:
        e.visible = show
    for e in planet_parts:
        e.visible = show
    for e in nebula_parts:
        e.visible = show
    for e in bh_parts:
        e.visible = show
    for _d, _e in sun_layers:
        _e.visible = show
    nebula_group.visible = show
    bh_group.visible = show
    for _g in ('ruins_group', 'ds_group'):
        g = globals().get(_g)
        if g is not None:
            try:
                g.visible = show
            except Exception:
                pass
    for e in enemies + bullets + pickups + particles:
        e.visible = show
    if sky_dome is not None:
        try:
            sky_dome.visible = show
        except Exception:
            pass
    if mothership is not None:
        try:
            mothership.visible = show
            for _e, _c in getattr(mothership, 'parts', []):
                _e.visible = show
        except Exception:
            pass
    if not show:
        cockpit.visible = False
        alarm_bg.visible = False
        alarm_text.visible = False
        mission_text.visible = False
        void_bg.visible = False
        void_flash.visible = False
        _ds_alarm(False)
        b = globals().get('ds_beam')
        if b is not None:
            b.visible = False
        f = globals().get('ds_flash')
        if f is not None:
            f.enabled = False

# ================= 死星遗迹（结局四） =================
# 玩家身后的那片空域就是片头被炸掉的星球：现在只剩一堆碎片，旁边停着那颗死星。
# 注意要放得够远，否则一出生就进警报范围（用户反馈过这个问题）。
RUINS_POS = Vec3(0, 0, -7000)
DS_GAME_POS = RUINS_POS + Vec3(1400, 300, 1100)   # 和片头同一个相对位置
DS_GAME_R = 250.0
DS_WARN_DIST = 2700.0        # 进入这个距离开始报警
DS_AIM_DIST = 1350.0         # 进入这个距离死星开始瞄你
DS_AIM_TIME = 1.25           # 瞄准蓄能时间
DS_FIRE_TIME = 0.35          # 激光命中前的飞行时间

ruins_group = Entity(position=RUINS_POS)
ds_group = Entity(position=DS_GAME_POS)
ds_parts = []
ds_dish = None
ds_beam = None
ds_flash = None
ds_warn_bg = None
ds_warn_text = None
ds_state = 'idle'            # idle / warn / aim / fire / done
ds_t = 0.0


def build_ruins():
    """碎片场 + 死星本体 + 炮口 + 激光 + 警报 UI。"""
    global ds_dish, ds_beam, ds_flash, ds_warn_bg, ds_warn_text

    # 碎片场：原来那颗星球的位置
    groups = {}
    for _ in range(240):
        _d = Vec3(random.uniform(-1, 1), random.uniform(-0.8, 0.8), random.uniform(-1, 1)).normalized()
        _r = random.uniform(120, 620)
        _col = random.choice((color.gray, color.dark_gray, color.light_gray,
                              color.orange, color.red))
        key = _color_key(_col)
        if key not in groups:
            groups[key] = [_col, []]
        groups[key][1].append((_d * _r, random.uniform(6, 34)))
    for _col, cubes in groups.values():
        Entity(parent=ruins_group, model=_merged_cube_mesh(cubes), color=_col, unlit=True)
    # 几块大的
    for _ in range(18):
        _d = Vec3(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)).normalized()
        Entity(parent=ruins_group, model='cube', color=random.choice((color.gray, color.orange)),
               unlit=True, scale=random.uniform(30, 70), position=_d * random.uniform(200, 520),
               rotation=Vec3(random.uniform(0, 360), random.uniform(0, 360), random.uniform(0, 360)))

    # 死星本体（体素球，挂到 ds_group 上）
    for p in _voxel_ball(Vec3(0, 0, 0), DS_GAME_R, (color.dark_gray, C_GRAY), 200):
        p.parent = ds_group
        ds_parts.append(p)

    # 炮口：朝向玩家的可旋转方块
    ds_dish = Entity(parent=ds_group, model='cube', color=color.dark_gray, unlit=True,
                     scale=(DS_GAME_R * 0.55, DS_GAME_R * 0.55, DS_GAME_R * 0.18),
                     position=(0, DS_GAME_R * 0.72, 0))
    ds_dish.look_at(player.position, axis=Vec3.forward)

    # 激光束
    ds_beam = Entity(model='cube', color=color.lime, unlit=True, scale=(1, 1, 1))
    ds_beam.visible = False

    # 警报 UI（所有视角都显示）
    ds_warn_bg = Entity(parent=camera.ui, model='quad',
                        texture='textures/ui/alarm_vignette.png',
                        scale=(_UI_ASPECT, 1.0), z=0.35, enabled=False)
    ds_warn_text = _T(text=t('ds_warn'), position=(0, 0.33), origin=(0, 0),
                      scale=1.1, color=color.yellow, z=-0.3)
    ds_warn_text.text = ""
    ds_flash = Entity(parent=camera.ui, model='quad', texture='textures/ui/flash_white.png',
                      scale=(_UI_ASPECT, 1.0), z=0.45, enabled=False)


def _ds_alarm(show):
    if ds_warn_bg is None:
        return
    try:
        ds_warn_bg.enabled = show
        if not show:
            ds_warn_text.text = ""
    except Exception:
        pass


def update_deathstar():
    """死星：靠近报警 -> 瞄准 -> 开炮 -> 命中 = 结局四。"""
    global ds_state, ds_t, ds_ending, death_ending, death_t, shake_t
    if ds_warn_bg is None:
        return
    if game_state.get('menu') or game_state['over'] or game_state['endgame'] or game_state['landing'] \
            or game_state['nebula'] or game_state.get('handoff') or game_state['intro']:
        if ds_state in ('warn', 'aim'):
            _ds_alarm(False)
            ds_state = 'idle'
        return

    d = (player.position - DS_GAME_POS).length()

    if ds_state == 'done':
        return

    if ds_state == 'idle':
        if d < DS_WARN_DIST:
            ds_state = 'warn'
            ds_t = 0.0
            play_sfx('alarm', volume=0.5)
            _ds_alarm(True)
    elif ds_state == 'warn':
        ds_t += min(time.dt, 0.1)
        blink = int(ds_t * 4) % 2 == 0
        try:
            # 屏幕一直在闪：亮的那帧用整片红，暗的那帧用暗角
            ds_warn_bg.enabled = True
            ds_warn_bg.texture = ('textures/ui/flash_red.png' if blink
                                  else 'textures/ui/alarm_vignette.png')
            ds_warn_text.text = t('ds_warn') if blink else t('ds_warn2')
        except Exception:
            pass
        if d > DS_WARN_DIST + 400:
            ds_state = 'idle'
            _ds_alarm(False)
        elif d < DS_AIM_DIST:
            ds_state = 'aim'
            ds_t = 0.0
            play_sfx('charge', volume=0.6)
            _ds_alarm(True)
    elif ds_state == 'aim':
        ds_t += min(time.dt, 0.1)
        try:
            ds_dish.look_at(player.position, axis=Vec3.forward)
        except Exception:
            pass
        try:
            ds_warn_bg.enabled = True
            ds_warn_bg.texture = ('textures/ui/flash_red.png'
                                  if int(ds_t * 8) % 2 == 0 else 'textures/ui/alarm_vignette.png')
            ds_warn_text.text = t('ds_warn')
        except Exception:
            pass
        if ds_t >= DS_AIM_TIME:
            ds_state = 'fire'
            ds_t = 0.0
            play_sfx('warp', volume=0.5)
    elif ds_state == 'fire':
        ds_t += min(time.dt, 0.1)
        try:
            start = ds_dish.world_position
            end = player.position
            vec = end - start
            length = max(1.0, vec.length())
            ds_beam.visible = True
            ds_beam.position = start + vec * 0.5
            ds_beam.scale = (4, 4, length)
            ds_beam.look_at(end, axis=Vec3.forward)
            # 只有快命中的一瞬才闪白，避免整段都被白光糊住
            ds_flash.enabled = (DS_FIRE_TIME - ds_t) < 0.12
        except Exception:
            pass
        if ds_t >= DS_FIRE_TIME:
            # 命中：飞船炸成碎片 -> 黑屏 -> 结局四
            ds_beam.visible = False
            ds_flash.enabled = False
            _ds_alarm(False)
            shake_t = max(shake_t, 1.4)
            big_boom(player.position)
            for child, _ in player.parts:
                child.visible = False
            player.visible = False
            play_sfx('explosion', volume=1.0)
            play_sfx('death', volume=0.9)
            game_state['over'] = True
            ds_ending = True
            death_ending = False
            death_t = 0.0
            ds_state = 'done'


def _enter_endgame():
    """进入结算面板（几个结局共用），顺便记录达成的结局。"""
    global end_t, _type_last
    game_state["endgame"] = True
    end_t = 0.0
    _type_last = 0
    over_text.text = ""          # 别让"飞船已被摧毁..."盖在结局文案上
    seq_text.text = ""
    _set_world_visible(False)
    _hud_visible(False)
    # 黑屏：连飞船和爆炸碎片一起收掉，免得浮在结局文字上
    try:
        for child, _c in player.parts:
            child.visible = False
        player.visible = False
        for _p in particles[:]:
            destroy(_p)
        particles.clear()
    except Exception:
        pass
    try:
        _boss_ui_show(False)
    except Exception:
        pass
    # 记录结局（0=行星 1=黑洞 2=海盗 3=死星 4=母舰）
    try:
        if ending6:
            unlock_ending(5)
        elif boss_ending:
            unlock_ending(4)
        elif ds_ending:
            unlock_ending(3)
        elif death_ending:
            unlock_ending(2)
        elif nebula_ending:
            unlock_ending(1)
        else:
            unlock_ending(0)
    except Exception:
        pass

def update_ui():
    global ui_text_t, fps_t, fps_frames, _type_last
    # ---- 交接镜头：HUD 保持隐藏 ----
    if game_state.get("handoff"):
        _hud_visible(False)
        seq_text.text = ""
        return
    # ---- 结算面板（用独立的 end_t 计时，不依赖 landing_timer） ----
    if game_state["endgame"]:
        et = end_t
        _hud_visible(False)
        seq_text.text = ""
        n = int(et * CPS)
        if n // 3 != _type_last:          # ?3
            _type_last = n // 3
            play_sfx('type', volume=0.12)

        if ending6:
            # 结局六：母舰轰掉了新行星
            settle_tag.text = t('end_tag_6')
            settle_stats.scale = 1.02
            title = t('end_title_6')
            settle_title.text = title[:max(0, n)]
            body_n = max(0, n - len(title) - 8)
            body = t('end_body_6')
            settle_stats.text = body[:body_n]
            done = body_n >= len(body)
        elif boss_ending:
            # 结局五：打掉海盗母舰
            settle_tag.text = t('end_tag_5')
            settle_stats.scale = 1.05
            title = t('end_title_5')
            settle_title.text = title[:max(0, n)]
            body_n = max(0, n - len(title) - 8)
            body = t('end_body_5')
            settle_stats.text = body[:body_n]
            done = body_n >= len(body)
        elif ds_ending or death_ending:
            # 结局三（被海盗打死）/ 结局四（回去被死星摧毁）：黑屏 + 短文案
            tag = t('end_tag_4') if ds_ending else t('end_tag_3')
            title = t('end_title_4') if ds_ending else t('end_title_3')
            body = t('end_body_4') if ds_ending else t('end_body_3')
            settle_tag.text = tag
            settle_stats.scale = 1.05
            settle_title.text = title[:max(0, n)]
            body_n = max(0, n - len(title) - 8)
            settle_stats.text = body[:body_n]
            done = body_n >= len(body)
        elif nebula_ending:
            # 结局二：被黑洞吞掉
            settle_tag.text = t('end_tag_2')
            settle_stats.scale = 1.0
            title = t('end_title_2')
            settle_title.text = title[:max(0, n)]
            body_n = max(0, n - len(title) - 8)
            epitaph = t('epitaph')
            settle_stats.text = epitaph[:body_n]
            done = body_n >= len(epitaph)
        else:
            # 结局一：抵达新行星
            settle_tag.text = t('end_tag_1')
            settle_stats.scale = 1.1
            title = t('end_title_1')
            settle_title.text = title[:max(0, n)]
            settle_stats.text = (t('end_stats', k=player.kills, l=player.level, s=player.score)
                                 if n >= len(title) else "")
            done = n >= len(title)

        _show_buttons(True)
        if done:
            blink = (_now_ms() // 500) % 2 == 0
            settle_prompt.text = t('end_prompt') if blink else ""
        else:
            settle_prompt.text = ""
        return

    # ---- A HUD ----
    if game_state["nebula"]:
        _hud_visible(False)
        seq_text.text = ""
        return

    # ----  ----
    if game_state["landing"]:
        _hud_visible(False)
        seq_text.text = _landing_caption(game_state["landing_timer"])
        return

    # ---- 结局六过场：HUD 全隐藏，只留过场画面 ----
    if ending6 and not game_state["endgame"]:
        _hud_visible(False)
        _set_text(seq_text, "")
        _set_text(over_text, "")
        return

    # ---- normal HUD (text refreshed at 10Hz: per-frame Text updates are expensive) ----
    _hud_visible(camera_mode != 3)
    seq_text.text = ""
    _set_text(over_text, t('over') if (game_state["over"] and not ending6) else "")
    blink = (_now_ms() // 250) % 2 == 0

    hp_bar.scale_x = bar_w * max(0.001, player.hp / player.maxhp)
    exp_bar.scale_x = bar_w * max(0.001, player.exp / player.exp_next)
    thirst_bar.scale_x = bar_w * max(0.001, player.thirst / 100)
    hunger_bar.scale_x = bar_w * max(0.001, player.hunger / 100)
    energy_bar.scale_x = bar_w * max(0.001, player.energy / player.max_energy)

    if player.hp <= 10: hp_bar.color = color.red if blink else color.white
    else: hp_bar.color = color.red
    if player.thirst <= 10: thirst_bar.color = color.red if blink else color.azure
    else: thirst_bar.color = color.azure
    if player.hunger <= 10: hunger_bar.color = color.red if blink else color.orange
    else: hunger_bar.color = color.orange

    ui_text_t += time.dt
    if ui_text_t >= 0.1:
        ui_text_t = 0.0
        label_hp.text = t('hud_hp', v=int(player.hp))
        label_water.text = t('hud_water', v=int(player.thirst))
        label_food.text = t('hud_food', v=int(player.hunger))
        label_energy.text = t('hud_energy', v=int(player.energy))
        label_weapon.text = t('hud_weapon', name=t('weapon_' + str(player.weapon)))
        label_special.text = t('hud_special')
        _set_text(hint_text, t('hud_hint') if game_state.get('hints', True) else "")

        label_camera.text = t('cam_' + str(camera_mode))

        dist = (player.position - planet_pos).length()
        if dist < LAND_DIST:
            _set_text(landing_prompt, t('prompt_land'))
        else:
            _set_text(landing_prompt, "")

        nb_dist = (player.position - NEBULA_POS).length()
        if nb_dist < NEBULA_ENTER_DIST:
            _set_text(nebula_prompt, t('prompt_nebula'))
        else:
            _set_text(nebula_prompt, "")

        # 母舰方向提示：告诉玩家它在哪边（不然真的找不到）
        if (mothership is not None and mothership.alive
                and (mothership.active or
                     (mothership.position - player.position).length() < 5200)):
            _d = mothership.position - player.position
            _dist = _d.length()
            _n = _d / max(1.0, _dist)
            _side = _n.dot(player.right)
            _front = _n.dot(player.forward)
            if _front < -0.3:
                _arrow = '↓'
            elif abs(_side) < 0.35:
                _arrow = '↑'
            else:
                _arrow = '→' if _side > 0 else '←'
            _set_text(label_boss_dir, t('boss_dir', d=int(_dist), a=_arrow))
        else:
            _set_text(label_boss_dir, "")

    #  DIAG
    fps_t += time.dt
    fps_frames += 1
    if fps_t >= 1.0:
        diag_text.text = _diag_line(int(fps_frames / fps_t))
        fps_t = 0.0
        fps_frames = 0

# ================= 驾驶舱（2D 贴图） =================
# 舱壁/控制台/陈设/船长全部画进一张带透明窗口的 1920x1080 贴图（textures/cockpit.png），
# 只在上面叠两个会呼吸的辉光贴图（反应堆 + 台灯），比之前一堆纯色方块精致得多。
cockpit = Entity(parent=camera.ui)
cockpit_t = 0.0

_reactor_glow = None
_lamp_glow = None
_panel = None

def _build_cockpit():
    """建驾驶舱贴图（贴图缺失就退回一块深色底板，保证不会崩）。"""
    global _reactor_glow, _lamp_glow, _panel
    tex = os.path.join(BASE_DIR, 'textures', 'cockpit.png')
    aspect = 16.0 / 9.0
    try:
        aspect = window.aspect_ratio
    except Exception:
        pass
    if os.path.exists(tex):
        _panel = Entity(parent=cockpit, model='quad', texture='textures/cockpit.png',
                        scale=(aspect, 1.0), position=(0, 0, 0.02))
    else:
        _panel = Entity(parent=cockpit, model='quad', color=color.dark_gray,
                        scale=(aspect, 1.0), position=(0, 0, 0.02))
    # 反应堆辉光（对应贴图里左侧反应堆的圆形灯口）
    _reactor_glow = Entity(parent=cockpit, model='quad', texture='textures/glow_cyan.png',
                           scale=(0.105, 0.185), position=(-0.79, -0.345, 0.0))
    # 台灯辉光（贴图里台灯的位置）
    _lamp_glow = Entity(parent=cockpit, model='quad', texture='textures/glow_amber.png',
                        scale=(0.085, 0.085), position=(-0.50, -0.39, 0.0))

def _cockpit_glow_ok():
    return _reactor_glow is not None and _lamp_glow is not None

_build_cockpit()

cockpit.visible = False

# ---- 受击报警（红色闪烁 + 中文警告） ----
alarm_t = 0.0
alarm_bg = Entity(parent=camera.ui, model='quad', color=color.red,
                  scale=(2.2, 1.2), visible=False)
alarm_text = _T(text=t('alarm'), position=(0, -0.36), origin=(0, 0),
                scale=1.8, color=color.white, visible=False)
alarm_text.parent = camera.ui

def update_alarm():
    """update_alarm."""
    global alarm_t
    if alarm_t > 0:
        alarm_t = max(0.0, alarm_t - min(time.dt, 0.1))
    show = (camera_mode == 3 and alarm_t > 0 and int(alarm_t * 10) % 2 == 0)
    alarm_bg.visible = show
    alarm_text.visible = show

def update_cockpit():
    """update_cockpit."""
    global cockpit_t
    on = (camera_mode == 3 and not game_state["intro"]
          and not game_state["landing"] and not game_state["endgame"])
    cockpit.visible = on
    if not on:
        return

    cockpit_t += min(time.dt, 0.1)
    t = cockpit_t
    if not _cockpit_glow_ok():
        return

    pulse = 0.78 + 0.22 * math.sin(t * 2.4)
    _reactor_glow.scale = (0.115 * pulse, 0.205 * pulse)
    _lamp_glow.scale = (0.10, 0.10 * (0.90 + 0.10 * math.sin(t * 11.0)))

# ================= nebula and black hole =================
NEBULA_POS = Vec3(-1400, 520, 2100)        # nebula sits ahead-left of the spawn point
NEBULA_ENTER_DIST = 1500.0                 # press O within this distance
BH_POS = NEBULA_POS
NEBULA_SWITCH_AT = 1.6
NEBULA_PULL_END = 7.0
NEBULA_END_AT = 8.6
# 墓志铭按语言取（见 STRINGS['zh'/'en']['epitaph']）

void_t = 0.0
void_start = Vec3(0, 0, 0)
nebula_ending = False
death_ending = False        # 结局三：被星际海盗打死
ds_ending = False           # 结局四：回去后被死星摧毁
boss_ending = False         # 结局五：打掉海盗母舰
killed_by_boss = False      # 是否被母舰的炮弹打死（决定走结局六）
ending6 = False             # 结局六：毁灭的希望
ending6_state = 'none'      # none -> boom -> aim -> fire -> hit -> done
ending6_t = 0.0
ds_projectile = None        # 母舰轰星球的那颗炮弹
death_t = 0.0               # 死亡后进结算面板的计时
end_t = 0.0                                # settlement panel timer (independent)
try:
    CAMERA_BASE_FOV = camera.fov
except Exception:
    CAMERA_BASE_FOV = 90.0

def _set_fov(v):
    try:
        camera.fov = v
    except Exception:
        pass

# ---- nebula: a ring of colored voxel clouds around the black hole ----
nebula_group = Entity(position=NEBULA_POS)
nebula_parts = []
_neb_groups = {}
for _ in range(620):
    _d = Vec3(random.uniform(-1, 1), random.uniform(-0.45, 0.45), random.uniform(-1, 1)).normalized()
    _r = random.uniform(650, 1200)               # keep the cloud away from the flight path
    _lit = _d.dot(SUN_DIR)                       # clouds facing the sun are brighter
    if _lit > 0.35:
        _col = random.choice((color.white, C_PINK, color.cyan))
    elif _lit > -0.1:
        _col = random.choice((color.violet, color.magenta, color.azure))
    else:
        _col = random.choice((color.violet, color.magenta, color.blue))
    _key = _color_key(_col)
    if _key not in _neb_groups:
        _neb_groups[_key] = [_col, []]
    _neb_groups[_key][1].append((_d * _r, random.uniform(12, 40)))
for _col, _cubes in _neb_groups.values():
    nebula_parts.append(Entity(parent=nebula_group, model=_merged_cube_mesh(_cubes), color=_col, unlit=True))

# ---- ?+ ?+  ----
bh_group = Entity(position=BH_POS)
bh_parts = []
_horizon = [(v * 92, 30.0) for v in _sphere_points(160)]
bh_parts.append(Entity(parent=bh_group, model=_merged_cube_mesh(_horizon),
                       color=color.black, unlit=True))
bh_disk = Entity(parent=bh_group)
_disk_groups = {}
for _ in range(240):
    _a = random.uniform(0, math.tau)
    _rr = random.uniform(140, 430)
    _p = Vec3(math.cos(_a) * _rr, random.uniform(-8, 8), math.sin(_a) * _rr)
    if _rr < 210:
        _c = random.choice((color.white, color.white, color.yellow))
    elif _rr < 320:
        _c = random.choice((color.yellow, color.orange))
    else:
        _c = random.choice((color.orange, color.red))
    _k2 = _color_key(_c)
    if _k2 not in _disk_groups:
        _disk_groups[_k2] = [_c, []]
    _disk_groups[_k2][1].append((_p, random.uniform(8, 22)))
for _col, _cubes in _disk_groups.values():
    bh_parts.append(Entity(parent=bh_disk, model=_merged_cube_mesh(_cubes), color=_col, unlit=True))
# ?
for _rad, _tilt, _col, _sz in ((96, 0, color.white, 15),
                               (118, 28, color.cyan, 10),
                               (150, -34, color.yellow, 9)):
    _ring = []
    _n = max(24, int(_rad / 2))
    for _i in range(_n):
        _a = math.tau * _i / _n
        _ring.append((Vec3(math.cos(_a) * _rad, math.sin(_a) * _rad, 0), _sz))
    bh_parts.append(Entity(parent=bh_group, model=_merged_cube_mesh(_ring),
                           color=_col, unlit=True, rotation_x=_tilt))

# ----  /  ----
void_bg = Entity(parent=camera.ui, model='quad', color=color.black, scale=(2.4, 1.4), visible=False)
void_flash = Entity(parent=camera.ui, model='quad', color=color.white, scale=(2.4, 1.4), visible=False)

def _near_nebula():
    return (player.position - NEBULA_POS).length() < NEBULA_ENTER_DIST

def start_nebula():
    """start_nebula."""
    global void_t, void_start, nebula_ending
    if (game_state["nebula"] or game_state["endgame"] or game_state["landing"]
            or game_state["intro"] or game_state["over"]):
        return
    game_state["nebula"] = True
    void_t = 0.0
    void_start = player.position
    nebula_ending = False
    void_bg.visible = False
    void_flash.visible = False
    _hud_visible(False)
    play_sfx('nebula', volume=0.7)

def update_nebula():
    """update_nebula."""
    global void_t, nebula_ending, end_t, camera_mode
    dt = min(time.dt, 0.1)
    void_t += dt
    t = void_t

    bh_disk.rotation_y += 55 * dt        # ?    nebula_group.rotation_y += 2.5 * dt  #

    if t < NEBULA_SWITCH_AT:
        camera_mode = 3                  # 
    else:
        if camera_mode != 1:
            play_sfx('warp', volume=0.6)  # ??
        camera_mode = 1                  # z
        k = min(1.0, (t - NEBULA_SWITCH_AT) / (NEBULA_PULL_END - NEBULA_SWITCH_AT))
        kk = k * k                       # ease-in
        _dirv = (void_start - BH_POS)
        if _dirv.length() < 0.01:
            _dirv = Vec3(0, 0, -1)
        _pull_target = BH_POS + _dirv.normalized() * (92 + 70)
        player.position = lerp(void_start, _pull_target, kk)
        player.look_at(BH_POS, axis=Vec3.forward)
        player.scale = (1.0, 1.0 + 0.9 * kk, 1.0 + 1.7 * kk)   # ?        _set_fov(CAMERA_BASE_FOV + 75.0 * kk)                  # ?= ?
    if t >= NEBULA_PULL_END and player.visible:
        player.visible = False
        void_flash.visible = True
        play_sfx('explosion', volume=0.8)

    if t >= NEBULA_PULL_END + 0.25:
        void_flash.visible = False
        void_bg.visible = True

    if t >= NEBULA_END_AT and not nebula_ending:
        nebula_ending = True
        game_state["nebula"] = False
        _enter_endgame()
        play_sfx('victory', volume=0.5)

# ================= intro cinematic: death star -> escape -> planet explosion =================
INTRO_POS = Vec3(0, 0, -9000)                 # intro scene sits far behind the spawn point
INTRO_PLANET_R = 420.0
INTRO_DS_POS = INTRO_POS + Vec3(1500, 260, 1250)
INTRO_DS_R = 250.0
INTRO_BEAM_AT = 1.4                           # death star fires
INTRO_BEAM_TRAVEL = 1.4                       # beam travel time
INTRO_IMPACT_AT = INTRO_BEAM_AT + INTRO_BEAM_TRAVEL      # 2.8s impact
INTRO_SHIP_AT = 1.7                           # ship launches (before the beam arrives)
INTRO_SHIP_FLY = 2.6                          # ship flight duration
INTRO_CAM_SWING_AT = 2.9                      # camera starts swinging behind the ship
INTRO_SWING_TIME = 1.8
INTRO_SHIP_SCALE = 14.0                       # ship is scaled up so it is visible
INTRO_SPEED = 0.5                             # 0.5 = half speed (about 17s total)
INTRO_LEN = 5.45
INTRO_SHIP_FLYOUT_AT = INTRO_SHIP_AT + INTRO_SHIP_FLY   # 4.3s: start flying out of frame
INTRO_HIDE_AT = 5.2                           # 5.2s: ship is far away -> hide it
INTRO_END_AT = 5.45                           # 隐藏后只留 0.25s，紧接着黑场交接

intro_t = 0.0
intro_hit = False
intro_active = True
intro_story_t = 0.0
intro_story_on = False
INTRO_STORY_LINE_T = 2.1        # 每句停留时间
INTRO_STORY_GAP = 0.6          # 最后一句放完再停一下
intro_dish_dir = (INTRO_POS - INTRO_DS_POS).normalized()
intro_cam_cur = INTRO_POS + Vec3(-260, 560, -2000)

def _smooth(x):
    """_smooth."""
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)

def _ease_out(x):
    x = max(0.0, min(1.0, x))
    return 1.0 - (1.0 - x) ** 3

def _voxel_ball(center, radius, colors, n):
    """_voxel_ball."""
    groups = {}
    step = 2 * radius / math.sqrt(n) * 1.35
    for v in _sphere_points(n):
        col = random.choice(colors)
        key = _color_key(col)
        if key not in groups:
            groups[key] = [col, []]
        groups[key][1].append((center + v * radius, step * random.uniform(1.0, 1.25)))
    return [Entity(model=_merged_cube_mesh(cubes), color=col, unlit=True)
            for col, cubes in groups.values()]

intro_planet_parts = []
intro_ds_parts = []
intro_beam = None
intro_beam_len = (INTRO_DS_POS - INTRO_POS).length() - INTRO_PLANET_R


def _reset_intro_story():
    global intro_story_t, intro_story_on
    intro_story_t = 0.0
    intro_story_on = True
    try:
        _set_text(story_text, "")
    except Exception:
        pass


def build_intro_scene():
    """重建片头场景（每次从主菜单开始游戏都会重建，因为 end_intro 会把它们 destroy 掉）。"""
    global intro_planet_parts, intro_ds_parts, intro_beam
    for p in list(intro_planet_parts) + list(intro_ds_parts):
        try:
            destroy(p)
        except Exception:
            pass
    if intro_beam is not None:
        try:
            destroy(intro_beam)
        except Exception:
            pass
    intro_planet_parts = _voxel_ball(INTRO_POS, INTRO_PLANET_R,
                                     (color.green, color.blue, color.azure, C_LIME), 360)
    intro_ds_parts = _voxel_ball(INTRO_DS_POS, INTRO_DS_R, (color.dark_gray, C_GRAY), 220)
    intro_ds_parts.append(Entity(model='cube', color=color.dark_gray, unlit=True,
                                 scale=INTRO_DS_R * 0.55,
                                 position=INTRO_DS_POS + intro_dish_dir * (INTRO_DS_R * 0.72)))
    intro_beam = Entity(model='cube', color=color.lime, unlit=True,
                        scale=(5, 5, 1), position=INTRO_DS_POS + intro_dish_dir * INTRO_DS_R)
    intro_beam.look_at(INTRO_POS, axis=Vec3.forward)
    intro_beam.visible = False


intro_title = _T(text=t('intro_title'), position=(0, 0.06), origin=(0, 0),
                 scale=2.2, color=color.yellow)
intro_skip = _T(text=t('intro_skip'), position=(0, -0.47), origin=(0, 0),
                scale=1.0, color=C_GRAY)
story_text = _T(text="", position=(0, -0.38), origin=(0, 0), scale=1.40,
                color=color.white)
_hud_visible(False)

def update_intro():
    global intro_t, intro_hit, intro_cam_cur, intro_story_t, intro_story_on
    if not intro_active or intro_beam is None:
        return
    dt = min(time.dt, 0.1)

    # ---- 第一阶段：背景故事，一句一句显示 ----
    if intro_story_on:
        intro_story_t += dt
        _lines = [t('story_1'), t('story_2'), t('story_3'), t('story_4')]
        _idx = int(intro_story_t / INTRO_STORY_LINE_T)
        if _idx < len(_lines):
            _set_text(story_text, _lines[_idx])
            if not intro_title.text:
                pass
        else:
            _set_text(story_text, "")
        _set_text(intro_title, "")
        # 镜头停在远处的远景，等着故事讲完
        intro_cam_cur = INTRO_POS + Vec3(-260, 560, -2000)
        camera_rig.position = intro_cam_cur
        camera_rig.look_at(INTRO_POS + Vec3(0, 60, 0), axis=Vec3.forward)
        intro_skip.text = t('intro_skip') if intro_story_t > 0.8 else ""
        if intro_story_t >= INTRO_STORY_LINE_T * len(_lines) + INTRO_STORY_GAP:
            intro_story_on = False
            intro_story_t = 0.0
            _set_text(story_text, "")
            intro_t = 0.0
            play_sfx('warp', volume=0.5)
        return
    prev = intro_t
    intro_t += dt * INTRO_SPEED
    tt = intro_t

    if prev < INTRO_BEAM_AT <= tt: play_sfx('charge', volume=0.5)
    if prev < INTRO_SHIP_AT <= tt: play_sfx('dash', volume=0.5)
    if prev < INTRO_IMPACT_AT <= tt: play_sfx('explosion', volume=0.7)

    # ---- 死星开炮 ----
    if INTRO_BEAM_AT <= tt < INTRO_IMPACT_AT:
        length = max(1.0, intro_beam_len * _smooth((tt - INTRO_BEAM_AT) / INTRO_BEAM_TRAVEL))
        intro_beam.visible = True
        intro_beam.position = INTRO_DS_POS + intro_dish_dir * (INTRO_DS_R + length * 0.5)
        intro_beam.scale = (5, 5, length)

    # ---- 飞船从星球上冲出（缓动），之后加速飞出画面并隐藏 ----
    if tt >= INTRO_SHIP_AT:
        player.scale = INTRO_SHIP_SCALE
        k = _ease_out((tt - INTRO_SHIP_AT) / INTRO_SHIP_FLY)
        ship_start = INTRO_POS + Vec3(70, 100, -460)      # just left the surface
        ship_end = INTRO_POS + Vec3(330, 340, -1750)
        if tt < INTRO_SHIP_FLYOUT_AT:
            player.position = lerp(ship_start, ship_end, k)
            # 机头一直朝着飞行方向（远离被毁的星球），不再回头看爆炸
            fly_vec = (ship_end - ship_start).normalized()
            player.look_at(player.position + fly_vec * 400, axis=Vec3.forward)
        else:
            # 朝"前方"（远离星球）加速冲出去（用参数化位移，避免逐帧累加飞太远）
            fly_dir = (ship_end - INTRO_POS).normalized()
            k2 = min(1.0, (tt - INTRO_SHIP_FLYOUT_AT) / max(0.01, INTRO_HIDE_AT - INTRO_SHIP_FLYOUT_AT))
            player.position = ship_end + fly_dir * (k2 ** 1.7) * 5200
            player.look_at(player.position + fly_dir * 400, axis=Vec3.forward)
        player.visible = tt < INTRO_HIDE_AT
    else:
        player.visible = False

    # ---- 星球被击中 ----
    if tt >= INTRO_IMPACT_AT and not intro_hit:
        intro_hit = True
        intro_beam.visible = False
        for p in intro_planet_parts:
            p.visible = False

    if INTRO_IMPACT_AT <= tt < INTRO_IMPACT_AT + 1.3:
        for _ in range(1):
            e = Entity(model='cube', unlit=True,
                       color=random.choice((color.yellow, color.orange, color.red, color.white)),
                       scale=random.uniform(18, 55),
                       position=INTRO_POS + Vec3(random.uniform(-1, 1), random.uniform(-1, 1),
                                                 random.uniform(-1, 1)) * (INTRO_PLANET_R * 0.8))
            d = Vec3(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)).normalized()
            e.vel = d * random.uniform(200, 520)
            e.life = 1.3
            particles.append(e)

    # ---- 镜头：先远景，再摇到飞船身后 ----
    cam_a = INTRO_POS + Vec3(-260, 560, -2000)
    cam_b = INTRO_POS + Vec3(-170, 430, -1620)
    base_cam = lerp(cam_a, cam_b, _smooth(tt / 3.2))
    base_look = INTRO_POS + Vec3(0, 60, 0)

    k_swing = _smooth((tt - INTRO_CAM_SWING_AT) / INTRO_SWING_TIME)
    if tt >= INTRO_SHIP_AT:
        behind = player.position + Vec3(30, 55, -260)     # camera sits behind the ship
        cam_look = player.position + Vec3(0, 25, 900)     # look past the ship toward the planet
        intro_cam_cur = lerp(base_cam, behind, k_swing)
        look_pt = lerp(base_look, cam_look, k_swing)
    else:
        intro_cam_cur = base_cam
        look_pt = base_look
    camera_rig.position = intro_cam_cur
    camera_rig.look_at(look_pt, axis=Vec3.forward)

    intro_title.text = t('intro_title') if 0.4 <= tt <= 3.4 else ""
    intro_skip.text = t('intro_skip') if tt > 1.0 else ""

    # 结尾淡出（0.35s），让切到交接镜头不突兀
    if tt >= INTRO_END_AT - 0.35:
        _start_fade(1.0, 0.35)
    if tt >= INTRO_LEN:
        end_intro()

def end_intro():
    """片头结束：清掉片头场景，进入"交接镜头"（先正面看飞船飞向出生点，再快速飞回尾部视角）。"""
    global intro_active
    if not intro_active:
        return
    intro_active = False
    global intro_story_on
    intro_story_on = False
    try:
        _set_text(story_text, "")
    except Exception:
        pass
    game_state["intro"] = False

    for p in intro_planet_parts + intro_ds_parts:
        destroy(p)
    intro_planet_parts.clear()
    intro_ds_parts.clear()
    if intro_beam is not None:
        destroy(intro_beam)
    intro_title.text = ""
    intro_skip.text = ""

    start_handoff()


# ================= 交接镜头：正面看飞船飞回出生点 -> 快速飞回尾部视角 =================
HANDOFF_START = Vec3(0, 45, -2600)       # 飞船从出生点后方飞进来
HANDOFF_END = Vec3(0, 0, 0)              # 出生点
HANDOFF_FLY_TIME = 3.0                   # 飞向出生点的时间
HANDOFF_CAM_AHEAD = Vec3(0, 9, 48)       # 镜头在飞船正前方（回头看飞船，机头朝镜头飞来）
HANDOFF_SWING_TIME = 0.9                 # 镜头从正面飞回尾部的时间
HANDOFF_SKIP_AT = 0.9                    # 过了这个时间就可以按空格跳过

handoff_active = False
handoff_t = 0.0


def start_handoff():
    global handoff_active, handoff_t
    handoff_active = True
    handoff_t = 0.0
    game_state["handoff"] = True

    player.scale = 1.0
    player.vel = Vec3(0, 0, 0)
    player.position = HANDOFF_START
    player.rotation = Vec3(0, 0, 0)      # 机头朝 +z（地图/星球方向）
    player.yaw = 0
    player.pitch = 0
    player.target_yaw = 0
    player.target_pitch = 0
    player.visible = True
    player.hp = player.maxhp
    player.energy = player.max_energy

    _hud_visible(False)
    intro_skip.text = t('intro_skip')
    try:
        diag_text.enabled = False
    except Exception:
        pass
    _set_gameworld_visible(True)
    _start_fade(0.0, 0.55)      # 片头黑场之后无缝淡入交接镜头


def _set_gameworld_visible(show):
    """只切换"游戏世界"的那部分（主行星/星云/黑洞/遗迹/死星/太阳光晕），星星始终可见。

    片头镜头会朝 +z 看，如果游戏世界的行星、遗迹、死星都开着，就会在片头背景里
    看到"同一个场景"（用户反馈的 bug），所以片头期间把它们全部藏起来。
    """
    for e in planet_parts + nebula_parts + bh_parts:
        try:
            e.visible = show
        except Exception:
            pass
    for g in (nebula_group, bh_group, ruins_group, ds_group):
        try:
            g.visible = show
        except Exception:
            pass
    if mothership is not None:
        try:
            mothership.visible = show
            for _e, _c in getattr(mothership, 'parts', []):
                _e.visible = show
        except Exception:
            pass
    for _d, e in sun_layers:
        try:
            e.visible = show and LIGHTING_ON
        except Exception:
            pass


def finish_handoff():
    """交接镜头结束：回到正常游戏（尾部视角 + HUD + 开始刷怪）。"""
    global handoff_active
    handoff_active = False
    game_state["handoff"] = False
    game_state["time"] = 0.0

    _set_gameworld_visible(True)
    camera_rig.position = player.position
    camera_rig.rotation = Vec3(0, 0, 0)
    camera.position = (0, 8, -28)
    camera.rotation_x = 15
    camera.rotation = (15, 0, 0)
    _set_fov(CAMERA_BASE_FOV)

    intro_skip.text = ""
    _hud_visible(True)
    try:
        diag_text.enabled = True
    except Exception:
        pass


def update_handoff():
    global handoff_t
    if not handoff_active:
        return
    dt = min(time.dt, 0.1)
    handoff_t += dt
    k = _smooth(min(1.0, handoff_t / HANDOFF_FLY_TIME))

    # 1) 飞船从远处飞向出生点
    player.position = lerp(HANDOFF_START, HANDOFF_END, k)
    player.rotation = Vec3(0, 0, 0)
    player.visible = True

    # 2) 镜头：一开始在飞船正前方（回头看飞船），之后快速飞回尾部默认视角
    ahead_pos = player.position + HANDOFF_CAM_AHEAD
    tail_pos = player.position + Vec3(0, 8, -28)
    swing = _smooth((handoff_t - HANDOFF_FLY_TIME) / HANDOFF_SWING_TIME)

    cam_pos = lerp(ahead_pos, tail_pos, swing)
    look_at_ship = player.position + Vec3(0, 4, 0)
    look_ahead = player.position + Vec3(0, 6, 60)
    look_pt = lerp(look_at_ship, look_ahead, swing)

    camera_rig.position = cam_pos
    camera_rig.look_at(look_pt, axis=Vec3.forward)

    if handoff_t >= HANDOFF_FLY_TIME + HANDOFF_SWING_TIME:
        finish_handoff()

def input(key):
    global camera_mode, landing_start_pos, SFX_ON, MUSIC_ON, _music_started

    # ---- 主菜单 / 设置：先吃掉所有按键 ----
    if game_state.get('menu'):
        if game_state.get('credits'):
            if key in ('escape', 'backspace', 'enter', 'space', '4'):
                close_credits()
                play_sfx('ui', volume=0.4)
            return
        if game_state.get('settings'):
            if key in ('escape', 'backspace'):
                close_settings()
                play_sfx('ui', volume=0.4)
            return
        if key in ('1', 'enter', 'space'):
            start_game()
        elif key == '2':
            open_settings()
        elif key == '4':
            open_credits()
        elif key == '3' or key == 'escape':
            application.quit()
        return

    if key == 'm':                       # mute / unmute (sfx + music)
        SFX_ON = not SFX_ON
        MUSIC_ON = SFX_ON
        if SFX_ON:
            _music_started = False
            _apply_audio_state()
            start_music()
        else:
            _apply_audio_state()
    if key == 'f1':
        diag_text.enabled = not diag_text.enabled
    if game_state["intro"]:
        if key == 'space':
            end_intro()
        return
    if game_state.get("handoff"):
        # 交接镜头：过了 0.9 秒可以按空格直接结束
        if key == 'space' and handoff_t > HANDOFF_SKIP_AT:
            finish_handoff()
        return
    if game_state["endgame"] and key == 'r':
        restart()
    if game_state["endgame"] and key == 'escape':
        back_to_menu()
    if game_state["over"] and key == 'r':
        restart()
    if game_state["over"] and key == 'escape':
        back_to_menu()
    if game_state["landing"] or game_state["nebula"]:
        return

    if key == 'escape':
        back_to_menu()
    if key in ('1','2','3') and not game_state["over"]: player.weapon = int(key)-1
    if key == '4' and not game_state["over"]:
        fire_missile()
    if key == '5' and not game_state["over"]:
        fire_bomb()
    if key == 'p' and not game_state["over"]:
        camera_mode = camera_mode % 3 + 1
        play_sfx('switch', volume=0.3)
    if key == 'o' and not game_state["over"]:
        if _near_nebula():
            start_nebula()          #
        else:
            game_state["paused"] = not game_state["paused"]
            play_sfx('pause', volume=0.4)

    if key == 'k' and not game_state["over"]:
        dist = (player.position - planet_pos).length()
        if dist < LAND_DIST:
            game_state["landing"] = True
            game_state["landing_timer"] = 0.0
            landing_start_pos = player.position
            play_sfx('land', volume=0.6)

    if key == 'f2':
        # F2：显示 / 隐藏底部操作提示
        game_state['hints'] = not game_state.get('hints', True)
        play_sfx('pickup', volume=0.25)

def _reset_world():
    """把一局游戏的所有状态复位（主菜单开始 / 重开 / 回主菜单都走这里）。"""
    global end_t, nebula_ending, shake_t, camera_mode, handoff_active, handoff_t
    global death_ending, ds_ending, boss_ending, death_t, ds_state, ds_t, mothership
    global killed_by_boss, ending6, ending6_state, ending6_t, ds_projectile
    for lst in (enemies, bullets, pickups, particles, missiles):
        for e in lst[:]:
            try:
                destroy(e)
            except Exception:
                pass
        lst.clear()
    if mothership is not None:
        try:
            destroy(mothership)
        except Exception:
            pass
        mothership = None
    try:
        _boss_ui_show(False)
    except Exception:
        pass

    handoff_active = False
    handoff_t = 0.0
    game_state.update({
        "over": False, "paused": False, "time": 0.0,
        "landing": False, "landing_timer": 0.0, "endgame": False, "intro": False,
        "nebula": False, "handoff": False,
    })
    end_t = 0.0
    nebula_ending = False
    death_ending = False
    ds_ending = False
    boss_ending = False
    killed_by_boss = False
    ending6 = False
    ending6_state = 'none'
    ending6_t = 0.0
    ds_projectile = None
    death_t = 0.0
    ds_state = 'idle'
    ds_t = 0.0
    shake_t = 0.0
    camera_mode = 1
    try:
        void_bg.enabled = False
        void_flash.enabled = False
    except Exception:
        pass
    try:
        if ds_beam is not None:
            ds_beam.visible = False
        if ds_flash is not None:
            ds_flash.enabled = False
    except Exception:
        pass
    _ds_alarm(False)
    _set_fov(CAMERA_BASE_FOV)

    spawn_planet()

    player.hp = player.maxhp; player.thirst = 100; player.hunger = 100
    player.exp = 0; player.level = 1; player.kills = 0; player.score = 0
    player.position = (0, 0, 0); player.yaw = 0; player.pitch = 0
    player.target_yaw = 0; player.target_pitch = 0
    player.vel = Vec3(0, 0, 0)
    player.rotation = Vec3(0, 0, 0)
    player.scale = 1.0
    player.energy = player.max_energy
    # 死亡时把飞船的每个体素都设成 visible=False（爆炸后船体消失），重生必须逐个恢复，
    # 否则会出现"飞船隐身"——只设 player.visible=True 是不够的，子物体还是隐藏的。
    for child, _ in player.parts:
        child.visible = True
    player.visible = True

    seq_text.text = ""
    over_text.text = ""
    settle_tag.text = ""
    settle_title.text = ""
    settle_stats.text = ""
    settle_prompt.text = ""
    _show_buttons(False)
    _set_world_visible(True)
    apply_brightness()


def restart():
    """结算/死亡后按 R：直接重开一局（跳过片头）。"""
    _reset_world()
    game_state["intro"] = False
    game_state["menu"] = False
    _hide_menu()
    camera_rig.position = (0, 0, 0)
    camera_rig.rotation = Vec3(0, 0, 0)
    camera.position = (0, 8, -28)
    camera.rotation_x = 15
    _hud_visible(True)
    try:
        diag_text.enabled = True
    except Exception:
        pass


def start_game():
    """主菜单点「开始游戏」：复位 + 播放片头。"""
    global intro_t, intro_hit, intro_active, intro_cam_cur
    _reset_world()
    _hide_menu()
    game_state["menu"] = False
    game_state["intro"] = True
    intro_t = 0.0
    intro_hit = False
    intro_active = True
    intro_cam_cur = INTRO_POS + Vec3(-260, 560, -2000)
    _reset_intro_story()
    build_intro_scene()
    intro_title.text = ""
    intro_skip.text = ""
    player.visible = False
    player.scale = INTRO_SHIP_SCALE
    _set_gameworld_visible(False)     # 片头里不要看见游戏世界的行星/遗迹/死星
    _hud_visible(False)
    apply_brightness()
    _music_started_restart()


def _music_started_restart():
    global _music_started
    _music_started = False
    start_music()


def back_to_menu():
    """结算界面「返回主菜单」：清场并回到主菜单。"""
    _reset_world()
    game_state["intro"] = False
    try:
        intro_title.text = ""
        intro_skip.text = ""
    except Exception:
        pass
    player.visible = False
    _hud_visible(False)
    camera_rig.position = (0, 0, 0)
    camera_rig.rotation = Vec3(0, 0, 0)
    camera.position = (0, 0, 0)
    camera.rotation = (0, 0, 0)
    _set_fov(CAMERA_BASE_FOV)
    _show_menu()
    _refresh_settings_values()

def update():
    global end_t, shake_t, death_t
    start_music()
    update_fade()          # 黑场淡入淡出必须在"提前 return"之前推进
    if game_state.get('menu'):
        return
    if shake_t > 0:
        shake_t = max(0.0, shake_t - min(time.dt, 0.1))
    update_sun()
    if game_state["intro"]:
        update_intro()
        return
    if game_state.get("handoff"):
        update_handoff()
        return
    if not game_state["endgame"]:
        update_camera()
    if game_state["nebula"]:
        update_nebula()
    update_cockpit()
    update_alarm()
    update_deathstar()
    update_mothership()
    update_ending6()
    if game_state["over"] and not game_state["endgame"] and not ending6:
        # 死亡/击毁母舰后先看 1.6 秒爆炸，再黑屏进结局面板
        death_t += min(time.dt, 0.1)
        if death_t >= 1.6:
            _enter_endgame()
    if game_state["endgame"]:
        end_t += min(time.dt, 0.1)
    # 炸弹白闪计时（不用 invoke，避免某些 Ursina 版本里出问题）
    global _bomb_flash_t
    if _bomb_flash_t > 0:
        _bomb_flash_t = max(0.0, _bomb_flash_t - min(time.dt, 0.1))
        try:
            if ds_flash is not None:
                ds_flash.enabled = _bomb_flash_t > 0
        except Exception:
            pass
    update_ui()

player = Player()
spawn_planet()
build_ruins()
invoke(spawn_loop, delay=1)
invoke(global_update, delay=0.1)

# ---- 启动：应用设置 -> 进主菜单 ----
try:
    apply_volume()
    apply_lighting()
    apply_brightness()
    _refresh_settings_values()
    _apply_language()
except Exception:
    pass
game_state['menu'] = True
game_state['intro'] = False
game_state['endgame'] = False
player.visible = False
_menu_shown = _show_menu()
_hud_visible(False)
intro_title.text = ""
intro_skip.text = ""
alarm_text.visible = False
_bright_overlay.enabled = False
_set_world_visible(False)        # 菜单时把 3D 世界藏起来，只留封面背景
camera_rig.position = (0, 0, 0)
camera_rig.rotation = Vec3(0, 0, 0)
camera.position = (0, 0, 0)
camera.rotation = (0, 0, 0)


# ================= 崩溃日志（把异常写进 crash.log，方便定位） =================
CRASH_LOG = os.path.join(BASE_DIR, 'crash.log')
_crash_once = set()


def _log_exc(where):
    if where in _crash_once:
        return
    _crash_once.add(where)
    try:
        import traceback as _tb
        with open(CRASH_LOG, 'a', encoding='utf-8') as f:
            f.write(f"\n===== {_pytime.strftime('%Y-%m-%d %H:%M:%S')}  {where} =====\n")
            _tb.print_exc(file=f)
    except Exception:
        pass


def _guard_function(fn, where):
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except Exception:
            _log_exc(where)
    return wrapper


def _guard_method(cls, where):
    old = cls.__dict__.get('update')
    if old is None:
        return
    def wrapper(self, *a, **kw):
        try:
            return old(self, *a, **kw)
        except Exception:
            _log_exc(where)
    cls.update = wrapper


update = _guard_function(update, 'update()')
input = _guard_function(input, 'input()')
global_update = _guard_function(global_update, 'global_update()')
for _cls in (Player, Enemy, Bullet, Pickup, Missile):
    _guard_method(_cls, f'{_cls.__name__}.update')

app.run()
