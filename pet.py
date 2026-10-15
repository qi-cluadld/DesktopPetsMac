# -*- coding: utf-8 -*-
"""
AI 桌宠 · macOS 版引擎
====================================================================
用 Python + Tkinter 写的十只 AI 桌宠，和 Windows 版共享同一套素材与台词：

  · 形象：直接使用十只在 Windows 上渲染好的 PNG（images/*.png），所以长得一模一样
  · 台词：读各自仓库的 lines.json（用 utf-8-sig 处理 BOM）
  · 窗口：无边框 + 永远置顶；macOS 上尝试真透明背景，失败则退回浅色卡片
  · 行为：自己走动、上下浮动、说话气泡、左键戳一下、右键菜单
  · 联动：写 /tmp/desktoppets/*.json 心跳文件，靠近的两只会互相打招呼
  · 退出：右键菜单里有「退出」和「全部退出」；Esc 也能关（拿得到键盘时）

操作（Mac 说法）：
    两个手指点触控板 = 弹出菜单（或按住 Control 点一下 / 接了鼠标就点右键）
    左键点一下       = 戳它一下
    Esc              = 关掉当前这只（能收到键盘时）
"""

import json
import math
import os
import random
import sys
import time
import tkinter as tk

是否Mac = (sys.platform == 'darwin')

根目录 = os.path.dirname(os.path.abspath(__file__))
图片目录 = os.path.join(根目录, 'images')
台词目录 = os.path.join(根目录, 'pets')
联动目录 = os.path.join('/tmp' if 是否Mac else os.environ.get('TEMP', '/tmp'), 'desktoppets')

# 十只：键名 / 显示名 / 品牌色（用于菜单里的圆点）
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

窗口宽, 窗口高 = 168, 196      # 图片区 + 下方气泡区
图片边长 = 156


def 读台词(键):
    """读某一只的台词表。utf-8-sig：能自动处理 BOM（十只的 lines.json 都带 BOM）。"""
    路径 = os.path.join(台词目录, 键 + '.json')
    if not os.path.exists(路径):
        return {}
    try:
        with open(路径, encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        print(f'读 {路径} 失败：{e}')
        return {}


class 桌宠:
    def __init__(self, 主窗, 序号, 键, 显示名, 颜色):
        self.序号 = 序号
        self.键 = 键
        self.显示名 = 显示名
        self.颜色 = 颜色
        self.数据 = 读台词(键)
        self.全部台词 = []
        for 组 in self.数据.get('lines', {}).values():
            if isinstance(组, list):
                self.全部台词.extend(组)

        # ---- 窗口：无边框 + 置顶 ----
        self.win = tk.Toplevel(主窗)
        self.win.title(显示名)
        self.win.overrideredirect(True)
        try:
            self.win.attributes('-topmost', True)
        except Exception:
            pass

        # ---- 画布：优先尝试 macOS 的真透明背景 ----
        self.透明 = False
        self.cv = None
        for 背景 in ('systemTransparent', '#f6f7fb'):
            try:
                self.cv = tk.Canvas(self.win, width=窗口宽, height=窗口高,
                                    bg=背景, highlightthickness=0, bd=0)
                self.透明 = (背景 == 'systemTransparent')
                break
            except Exception:
                self.cv = None
        if self.cv is None:
            self.cv = tk.Canvas(self.win, width=窗口宽, height=窗口高,
                                bg='#f6f7fb', highlightthickness=0, bd=0)
        self.cv.pack()
        if self.透明:
            try:
                self.win.wm_attributes('-transparent', True)
            except Exception:
                self.透明 = False
                self.cv.configure(bg='#f6f7fb')

        # ---- 宠物图片 ----
        self.图 = None
        图路径 = os.path.join(图片目录, 键 + '.png')
        if os.path.exists(图路径):
            try:
                self.原图 = tk.PhotoImage(file=图路径)
                倍数 = max(1, int(round(self.原图.width() / 图片边长)))
                self.图 = self.原图.subsample(倍数, 倍数) if 倍数 > 1 else self.原图
                self.cv.create_image(窗口宽 // 2, 图片边长 // 2 + 6, image=self.图)
            except Exception as e:
                print(f'载入 {图路径} 失败：{e}')
        if self.图 is None:
            self.cv.create_oval(20, 20, 图片边长 - 4, 图片边长 - 4, fill=颜色, outline='')

        # ---- 气泡 ----
        self.气泡底 = self.cv.create_rectangle(6, 图片边长 + 12, 窗口宽 - 6, 窗口高 - 6,
                                               fill='white', outline='#dfe3ee')
        self.气泡字 = self.cv.create_text(窗口宽 // 2, 图片边长 + 30, text='',
                                          fill='#39405a', width=窗口宽 - 22)
        self.说('你好呀！')

        # ---- 位置与状态 ----
        self.x = 120 + 序号 * 60
        self.y = 420 + (序号 % 3) * 90
        self.速度 = random.choice([-1.8, -1.2, 1.2, 1.8])
        self.帧 = 0
        self.上次说话 = 0
        self.最近邻居 = None

        self.win.geometry(f'{窗口宽}x{窗口高}+{int(self.x)}+{int(self.y)}')

        # ---- 菜单（Mac 上两指点按 / Control+点击 都走 Button-3 或 Control-Button-1）----
        self.菜单 = tk.Menu(self.win, tearoff=0)
        self.菜单.add_command(label=f'{显示名} · 打个招呼', command=lambda: self.说一句('Greet', '嗨！'))
        self.菜单.add_command(label='换句台词', command=lambda: self.说一句())
        self.菜单.add_command(label='走快点', command=self.走快点)
        self.菜单.add_command(label='走慢点', command=self.走慢点)
        self.菜单.add_separator()
        self.菜单.add_command(label='让这只休息（关闭）', command=self.关掉)
        self.菜单.add_command(label='全部退出', command=self.全部退出)

        for 目标 in (self.win, self.cv):
            目标.bind('<Button-1>', self.戳一下)
            目标.bind('<Button-3>', self.弹菜单)
            目标.bind('<Control-Button-1>', self.弹菜单)      # Mac 上按住 Control 点
            目标.bind('<Double-Button-1>', self.戳一下)
        self.win.bind('<Escape>', lambda e: self.关掉())

        self.写心跳()

    # ------------------------------------------------------------ 说话
    def 说(self, 文字):
        self.cv.itemconfig(self.气泡字, text=文字)

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
        self.上次说话 = self.帧

    # ------------------------------------------------------------ 交互
    def 戳一下(self, e=None):
        self.说一句('Pat', '嘿嘿~')
        self.冒爱心()

    def 冒爱心(self):
        self.cv.delete('heart')
        self.cv.create_text(窗口宽 - 24, 26, text='♥', fill='#ff5a8a',
                            font=('Arial', 18, 'bold'), tags='heart')
        self.win.after(1100, lambda: self.cv.delete('heart'))

    def 弹菜单(self, e):
        try:
            self.菜单.tk_popup(e.x_root, e.y_root)
        finally:
            self.菜单.grab_release()

    def 走快点(self):
        self.速度 *= 1.35
        self.说('加速！')

    def 走慢点(self):
        self.速度 *= 0.74
        self.说('慢一点~')

    def 关掉(self):
        try:
            self.win.destroy()
        except Exception:
            pass
        self.已关 = True

    def 全部退出(self):
        try:
            self.win.master.destroy()
        except Exception:
            os._exit(0)

    # ------------------------------------------------------------ 联动
    def 写心跳(self):
        try:
            os.makedirs(联动目录, exist_ok=True)
            文件 = os.path.join(联动目录, f'pet_{self.序号}.json')
            with open(文件, 'w', encoding='utf-8') as f:
                json.dump({'key': self.键, 'name': self.显示名, 'x': int(self.x),
                           'y': int(self.y), 'ts': time.time()}, f)
        except Exception:
            pass

    def 看看邻居(self):
        """读同一台机器上其它桌宠的心跳；靠近了就说一句打招呼的台词。"""
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
            if time.time() - 数据.get('ts', 0) > 15:      # 15 秒没心跳 = 那只已经关了
                continue
            距 = math.hypot(数据.get('x', 0) - self.x, 数据.get('y', 0) - self.y)
            if 距 < 最短:
                最短, 最好 = 距, 数据
        self.最近邻居 = 最好
        if 最好 and 最短 < 220 and self.帧 - self.上次说话 > 150:
            self.说一句('Hello', f'嗨，{最好.get("name", "你")}！')

    # ------------------------------------------------------------ 心跳（30fps）
    def 循环(self):
        self.帧 += 1
        self.x += self.速度
        屏宽 = self.win.winfo_screenwidth()
        if self.x < 0 or self.x > 屏宽 - 窗口宽:            # 碰边掉头
            self.速度 = -self.速度
            self.x = max(0, min(self.x, 屏宽 - 窗口宽))
        浮动 = math.sin(self.帧 / 12) * 3
        self.win.geometry(f'+{int(self.x)}+{int(self.y + 浮动)}')
        if self.帧 % 30 == 0:
            self.写心跳()
        if self.帧 % 40 == 0:
            self.看看邻居()
        if self.帧 % 190 == 0:
            self.说一句()
        self.win.after(33, self.循环)


def main():
    print('=' * 56)
    print('  AI 桌宠 · macOS 版')
    print('  两个手指点触控板 = 菜单；左键 = 戳一下；Esc = 关闭一只')
    print('=' * 56)
    try:
        os.makedirs(联动目录, exist_ok=True)
    except Exception:
        pass
    主窗 = tk.Tk()
    主窗.withdraw()                     # 主窗不显示，只用它的 Toplevel 放宠物
    宠物们 = []
    for i, (键, 名, 色) in enumerate(宠物表):
        if not os.path.exists(os.path.join(图片目录, 键 + '.png')):
            continue
        宠物们.append(桌宠(主窗, i, 键, 名, 色))
    print(f'  已放出 {len(宠物们)} 只')
    if not 宠物们:
        print('  一张图片都没找到，请确认 images/ 目录里有 png')
    主窗.after(33, lambda: [p.循环() for p in 宠物们])
    主窗.mainloop()


if __name__ == '__main__':
    main()
