# -*- coding: utf-8 -*-
"""
AI 桌宠 · macOS 版 v0.2
====================================================================
v0.2 相对 v0.1 的三处改动：

  1. 每只桌宠一个独立进程 + 独立「根窗口」
     原因：macOS 上 wm_attributes('-transparent') 只对根窗口(Tk)生效，
     对 Toplevel 无效 —— 这正是 v0.1 背景下不去、看起来像浅色方块的真因。
     所以 `python3 pet.py` 现在是一个监督进程：它把十只分别拉起来；
     `python3 pet.py grok` 则只跑一只（单只调试用）。

  2. 气泡平时隐藏，只在说话时出现约 3 秒
     v0.1 里每只身上永远挂着一个白框，是"丑"的另一半原因。

  3. 透明失败时不再裸奔：退回一个圆角浅色卡片，并在报告里写明用了哪种模式。

其它：素材用 images/*.png（真透明 + 紧裁 + 320px），台词读 pets/*.json
      （utf-8-sig 处理 BOM），联动走 /tmp/desktoppets/*.json 心跳。

操作（Mac 说法）：两个手指点触控板 = 菜单；左键 = 戳一下；Esc = 关掉这一只。
"""

import json
import math
import os
import random
import subprocess
import sys
import time
import tkinter as tk

是否Mac = (sys.platform == 'darwin')
根目录 = os.path.dirname(os.path.abspath(__file__))
图片目录 = os.path.join(根目录, 'images')
台词目录 = os.path.join(根目录, 'pets')
联动目录 = os.path.join('/tmp' if 是否Mac else os.environ.get('TEMP', '/tmp'), 'desktoppets')

宠物表 = [
    ('gemini',   '小星星', '#4285F4'),
    ('deepseek', '小鲸鱼', '#4D6BFE'),
    ('chatgpt',  '小花',   '#10A37F'),
    ('claude',   '小太阳', '#D97757'),
    ('doubao',   '小豆包', '#3B82F6'),
    ('qwen',     '小千',   '#5B5BD6'),
    ('copilot',  '小飞',   '#0A84FF'),
    ('glm',      '小象',   '#2F6BFF'),
    ('grok',     '小格',   '#1B1B1F'),
    ('apple',    '小智',   '#FF6A9A'),
]

显示边长 = 200          # 宠物在屏幕上的显示边长（素材是 320，会缩到 200）
气泡高 = 46             # 说话时上方留出的气泡条
窗口宽 = 显示边长 + 24
窗口高 = 显示边长 + 24 + 气泡高
说话时长 = 3.0          # 一句话显示几秒


def 报告(文字):
    """立刻输出（flush），避免 v0.1 那种"报告是空的"问题。"""
    print(文字, flush=True)


def 读台词(键):
    if 键 is None:
        return {}
    路径 = os.path.join(台词目录, 键 + '.json')
    if not os.path.exists(路径):
        return {}
    try:
        with open(路径, encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        报告(f'读台词失败 {路径}: {e}')
        return {}


class 桌宠:
    def __init__(self, 序号, 键, 显示名, 颜色):
        self.序号 = 序号
        self.键 = 键
        self.显示名 = 显示名
        self.颜色 = 颜色
        self.数据 = 读台词(键)
        self.全部台词 = []
        for 组 in self.数据.get('lines', {}).values():
            if isinstance(组, list):
                self.全部台词.extend(组)

        # ---------------- 根窗口（关键：每进程一个 Tk 根窗口） ----------------
        self.root = tk.Tk()
        self.root.title(显示名)
        self.root.overrideredirect(True)
        try:
            self.root.attributes('-topmost', True)
        except Exception:
            pass

        self.透明 = False
        self.画布背景 = '#f7f8fc'
        if 是否Mac:
            # macOS：让根窗口背景真正透明
            try:
                self.root.configure(bg='systemTransparent')
                self.root.wm_attributes('-transparent', True)
                self.画布背景 = 'systemTransparent'
                self.透明 = True
            except Exception as e:
                报告(f'[{显示名}] 透明模式不可用，改用卡片：{e}')

        try:
            self.cv = tk.Canvas(self.root, width=窗口宽, height=窗口高,
                                bg=self.画布背景, highlightthickness=0, bd=0)
        except Exception:
            self.画布背景 = '#f7f8fc'
            self.透明 = False
            self.cv = tk.Canvas(self.root, width=窗口宽, height=窗口高,
                                bg=self.画布背景, highlightthickness=0, bd=0)
        self.cv.pack()

        # 不透明时给个圆角卡片，别裸着
        if not self.透明:
            self.圆角(self.cv, 2, 2, 窗口宽 - 2, 窗口高 - 2, 22,
                      fill='#f7f8fc', outline='#e3e7f2')

        # ---------------- 宠物本体 ----------------
        self.图 = None
        图路径 = os.path.join(图片目录, 键 + '.png')
        if os.path.exists(图路径):
            try:
                self.原图 = tk.PhotoImage(file=图路径)
                倍 = max(1, int(round(self.原图.width() / 显示边长)))
                self.图 = self.原图.subsample(倍, 倍) if 倍 > 1 else self.原图
                self.cv.create_image(窗口宽 // 2, 气泡高 + 显示边长 // 2 + 6, image=self.图)
            except Exception as e:
                报告(f'[{显示名}] 载入图片失败：{e}')
        if self.图 is None:
            self.cv.create_oval(20, 气泡高 + 10, 显示边长 + 4, 气泡高 + 显示边长 - 6,
                                fill=颜色, outline='')

        # ---------------- 气泡（默认隐藏） ----------------
        self.气泡底 = self.cv.create_rectangle(6, 6, 窗口宽 - 6, 气泡高 - 4,
                                               fill='white', outline='#e3e7f2', state='hidden')
        self.气泡字 = self.cv.create_text(窗口宽 // 2, (气泡高 - 4) // 2 + 4, text='',
                                          fill='#39405a', width=窗口宽 - 24, state='hidden')
        self.气泡隐藏时刻 = 0.0

        # ---------------- 位置与状态 ----------------
        self.x = 140 + (序号 % 5) * 90
        self.y = 420 + (序号 // 5) * 130
        self.速度 = random.choice([-1.8, -1.2, 1.2, 1.8])
        self.帧 = 0
        self.上次说话帧 = -999
        self.root.geometry(f'{窗口宽}x{窗口高}+{int(self.x)}+{int(self.y)}')

        # ---------------- 菜单 ----------------
        self.菜单 = tk.Menu(self.root, tearoff=0)
        self.菜单.add_command(label=f'{显示名} · 打个招呼', command=lambda: self.说一句('Greet', '嗨！'))
        self.菜单.add_command(label='换句台词', command=lambda: self.说一句())
        self.菜单.add_command(label='走快点', command=self.快)
        self.菜单.add_command(label='走慢点', command=self.慢)
        self.菜单.add_separator()
        self.菜单.add_command(label='让这只休息（关闭）', command=self.关掉)
        self.菜单.add_command(label='全部退出', command=self.全部退出)

        for 目标 in (self.root, self.cv):
            目标.bind('<Button-1>', self.戳)
            目标.bind('<Button-3>', self.弹菜单)
            目标.bind('<Control-Button-1>', self.弹菜单)
        self.root.bind('<Escape>', lambda e: self.关掉())
        try:
            self.root.focus_force()
        except Exception:
            pass

        报告(f'[{显示名}] 透明={self.透明} 屏幕={self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}')
        self.写心跳()

    # ------------------------------------------------------------ 小工具
    @staticmethod
    def 圆角(cv, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return cv.create_polygon(pts, smooth=True, **kw)

    # ------------------------------------------------------------ 说话
    def 说(self, 文字):
        self.cv.itemconfig(self.气泡字, text=文字, state='normal')
        self.cv.itemconfig(self.气泡底, state='normal')
        self.气泡隐藏时刻 = time.time() + 说话时长

    def 收气泡(self):
        self.cv.itemconfig(self.气泡字, state='hidden')
        self.cv.itemconfig(self.气泡底, state='hidden')

    def 说一句(self, 组=None, 默认='……'):
        台词 = None
        if 组 and 组 in self.数据.get('lines', {}) and self.数据['lines'][组]:
            台词 = random.choice(self.数据['lines'][组])
        elif self.全部台词:
            台词 = random.choice(self.全部台词)
        if not 台词:
            台词 = 默认
        名字 = self.数据.get('name', self.显示名)
        self.说(台词.replace('{you}', '你').replace('{me}', 名字))
        self.上次说话帧 = self.帧

    # ------------------------------------------------------------ 交互
    def 戳(self, e=None):
        self.说一句('Pat', '嘿嘿~')
        self.cv.delete('heart')
        self.cv.create_text(窗口宽 - 26, 气泡高 + 20, text='♥', fill='#ff5a8a',
                            font=('Arial', 18, 'bold'), tags='heart')
        self.root.after(1100, lambda: self.cv.delete('heart'))

    def 弹菜单(self, e):
        try:
            self.菜单.tk_popup(e.x_root, e.y_root)
        finally:
            self.菜单.grab_release()

    def 快(self):
        self.速度 *= 1.35
        self.说('加速！')

    def 慢(self):
        self.速度 *= 0.74
        self.说('慢一点~')

    def 关掉(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def 全部退出(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        # 通知监督进程收工（删掉自己的心跳，监督进程发现没心跳就退）
        try:
            os.remove(os.path.join(联动目录, f'pet_{self.序号}.json'))
        except Exception:
            pass

    # ------------------------------------------------------------ 联动
    def 写心跳(self):
        try:
            os.makedirs(联动目录, exist_ok=True)
            with open(os.path.join(联动目录, f'pet_{self.序号}.json'), 'w', encoding='utf-8') as f:
                json.dump({'key': self.键, 'name': self.显示名, 'x': int(self.x),
                           'y': int(self.y), 'ts': time.time()}, f, ensure_ascii=False)
        except Exception:
            pass

    def 看邻居(self):
        最好, 最短 = None, 10 ** 9
        try:
            文件们 = [x for x in os.listdir(联动目录) if x.startswith('pet_') and x.endswith('.json')]
        except Exception:
            return
        for 名 in 文件们:
            if 名 == f'pet_{self.序号}.json':
                continue
            try:
                with open(os.path.join(联动目录, 名), encoding='utf-8') as f:
                    数据 = json.load(f)
            except Exception:
                continue
            if time.time() - 数据.get('ts', 0) > 15:
                continue
            距 = math.hypot(数据.get('x', 0) - self.x, 数据.get('y', 0) - self.y)
            if 距 < 最短:
                最短, 最好 = 距, 数据
        if 最好 and 最短 < 240 and self.帧 - self.上次说话帧 > 150:
            self.说(f'嗨，{最好.get("name", "你")}！')
            self.上次说话帧 = self.帧

    # ------------------------------------------------------------ 心跳（30fps）
    def 循环(self):
        self.帧 += 1
        self.x += self.速度
        屏宽 = self.root.winfo_screenwidth()
        if self.x < 0 or self.x > 屏宽 - 窗口宽:
            self.速度 = -self.速度
            self.x = max(0, min(self.x, 屏宽 - 窗口宽))
        浮动 = math.sin(self.帧 / 12) * 3
        self.root.geometry(f'+{int(self.x)}+{int(self.y + 浮动)}')
        if self.气泡隐藏时刻 and time.time() > self.气泡隐藏时刻:
            self.收气泡()
            self.气泡隐藏时刻 = 0.0
        if self.帧 % 30 == 0:
            self.写心跳()
        if self.帧 % 40 == 0:
            self.看邻居()
        if self.帧 % 190 == 0:
            self.说一句()
        self.root.after(33, self.循环)

    def 跑(self):
        self.循环()
        self.root.mainloop()


# ====================================================================
#  监督模式：不带参数 = 把十只分别拉起来（每只一个进程 + 根窗口）
#  单只模式：python3 pet.py grok
# ====================================================================
def 跑全部():
    try:
        os.makedirs(联动目录, exist_ok=True)
    except Exception:
        pass
    报告('=' * 56)
    报告('  AI 桌宠 · macOS版 v0.2')
    报告('  两个手指点触控板 = 菜单；左键 = 戳一下；Esc = 关掉一只')
    报告('=' * 56)
    有图的 = [k for k, _, _ in 宠物表 if os.path.exists(os.path.join(图片目录, k + '.png'))]
    报告(f'  找到素材 {len(有图的)}/10')
    脚本 = os.path.abspath(__file__)
    起的 = 0
    for k in 有图的:
        try:
            subprocess.Popen([sys.executable, 脚本, k],
                             stdout=sys.stdout, stderr=sys.stderr,
                             start_new_session=True, cwd=根目录)
            起的 += 1
            time.sleep(0.35)
        except Exception as e:
            报告(f'  启动 {k} 失败: {e}')
    报告(f'  已拉起来 {起的} 只（每只一个进程）')
    报告('  关闭方式：任意一只的菜单 → 「全部退出」')


def 跑一只(键):
    条目 = None
    for i, (k, 名, 色) in enumerate(宠物表):
        if k == 键:
            条目 = (i, k, 名, 色)
    if 条目 is None:
        报告(f'未知的宠物：{键}（可选：{", ".join(k for k, _, _ in 宠物表)}）')
        return
    桌宠(*条目).跑()


if __name__ == '__main__':
    参数 = [a for a in sys.argv[1:] if not a.startswith('-')]
    if 参数:
        跑一只(参数[0])
    else:
        跑全部()
